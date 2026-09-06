from typing import Annotated

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import SessionLocal


class ChatRequest(BaseModel):
    messages: list
    session_id: str | None = None



app = FastAPI(
    title="CourseCompass API",
    description="Academic Programme Personalization & Benefits RAG API",
    version="0.3.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Health Check ───────────────────────────────────────────────────────────


@app.get("/api/status")
async def read_root():
    return {
        "status": "ok",
        "service": "CourseCompass Academic & Benefits Assistant",
        "version": "0.3.0",
    }


# ─── Auth Routes ────────────────────────────────────────────────────────────

from datetime import timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    create_access_token,
    get_current_user,
    get_db,
    get_password_hash,
    verify_password,
)
from .models import User


@app.post("/api/auth/register", response_model=UserResponse)
def register(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    db_user = db.query(User).filter(User.registration_number == user.registration_number).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Registration number already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = User(
        registration_number=user.registration_number,
        hashed_password=hashed_password,
        cgpa=user.cgpa,
        current_term=user.current_term,
        program=user.program
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/api/auth/login", response_model=Token)
def login(user_credentials: UserLogin, db: Annotated[Session, Depends(get_db)]):
    user = db.query(User).filter(User.registration_number == user_credentials.registration_number).first()
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect registration number or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.registration_number}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse)
def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


# ─── Chat Routes ────────────────────────────────────────────────────────────


import uuid
from typing import Annotated

from fastapi import Request

from .models import ChatMessage, ChatSession


def get_optional_user(request: Request, db: Session):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    from jose import JWTError, jwt

    from .auth import ALGORITHM, SECRET_KEY
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        reg_num = payload.get("sub")
        if reg_num:
            return db.query(User).filter(User.registration_number == reg_num).first()
    except JWTError:
        pass
    return None


@app.post("/api/chat")
def chat_endpoint(request: ChatRequest, req: Request):
    last_user = next(
        (m for m in reversed(request.messages) if m.get("role") == "user"),
        None,
    )
    if not last_user:
        return {"response": "No user message found.", "sources": []}

    db = SessionLocal()
    session_id = request.session_id
    try:
        user = get_optional_user(req, db)
        
        # Determine or create session
        if user:
            if not session_id:
                session_id = str(uuid.uuid4())
                # Generate a short title from the first message
                title = last_user["content"][:30] + ("..." if len(last_user["content"]) > 30 else "")
                new_session = ChatSession(id=session_id, user_id=user.id, title=title)
                db.add(new_session)
                db.commit()
            
            # Save the user's message
            db.add(ChatMessage(session_id=session_id, role="user", content=last_user["content"]))
            db.commit()

        # Fetch history
        chat_history = []
        if session_id:
            past_messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at.asc()).all()
            
            # Note: We exclude the very last user message we just inserted so we don't duplicate it.
            # Actually, `run_agent` takes `query` and `chat_history` separately, so we should slice out the last one.
            if past_messages:
                for m in past_messages[:-1]:
                    chat_history.append({"role": m.role, "content": m.content})

        # Execute the Agentic Loop
        from .agent import run_agent
        user_reg_no = user.registration_number if user else None
        
        response_text, sources = run_agent(last_user["content"], user_reg_no, chat_history)

        if user and session_id:
            # Save the assistant's message
            db.add(ChatMessage(session_id=session_id, role="assistant", content=response_text))
            db.commit()

    finally:
        db.close()

    return {"response": response_text, "sources": sources, "session_id": session_id}


@app.get("/api/chat/sessions")
def list_chat_sessions(current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == current_user.id).order_by(ChatSession.created_at.desc()).all()
    return [{"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions]


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(session_id: str, current_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    return {
        "id": session.id,
        "title": session.title,
        "messages": [{"role": m.role, "content": m.content} for m in messages]
    }
