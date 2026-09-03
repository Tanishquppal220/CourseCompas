from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.concurrency import asynccontextmanager
from sqlalchemy.orm import Session

from .auth import create_access_token, get_current_user, get_db, hash_password, verify_password
from .database import SessionLocal
from .models import ChatMessage as ChatMessageModel, ChatSession, User
from .schemas import (
    ChatRequest,
    ChatResponse,
    ChatSessionSummary,
    LoginRequest,
    LoginResponse,
    ProfileUpdateRequest,
    RegisterRequest,
    UserProfile,
)
from .services.llm import generate_chat_response
from .services.retrieval import search_benefits


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print("Shutting down RAG background workers...")
    try:
        from joblib import externals

        externals.loky.get_reusable_executor().shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(
    title="CourseCompass API",
    description="Academic Programme Personalization & Benefits RAG API",
    version="0.3.0",
    lifespan=lifespan,
)


# ─── Health Check ───────────────────────────────────────────────────────────

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "CourseCompass Academic & Benefits Assistant",
        "version": "0.3.0",
    }


# ─── Auth Routes ────────────────────────────────────────────────────────────

@app.post("/api/auth/register", response_model=LoginResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.registration_number == request.registration_number).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration number already exists",
        )

    user = User(
        registration_number=request.registration_number,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    profile = UserProfile(
        id=user.id,
        registration_number=user.registration_number,
        full_name=user.full_name,
        current_term=user.current_term,
        current_cgpa=float(user.current_cgpa) if user.current_cgpa else None,
        program_name=user.program_name,
        admission_year=user.admission_year,
        is_onboarded=bool(user.is_onboarded),
    )
    return LoginResponse(access_token=token, user=profile, needs_onboarding=True)


@app.post("/api/auth/login", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.registration_number == request.registration_number).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid registration number or password",
        )

    token = create_access_token(data={"sub": str(user.id)})
    profile = UserProfile(
        id=user.id,
        registration_number=user.registration_number,
        full_name=user.full_name,
        current_term=user.current_term,
        current_cgpa=float(user.current_cgpa) if user.current_cgpa else None,
        program_name=user.program_name,
        admission_year=user.admission_year,
        is_onboarded=bool(user.is_onboarded),
    )
    return LoginResponse(
        access_token=token,
        user=profile,
        needs_onboarding=not bool(user.is_onboarded),
    )


@app.get("/api/auth/me", response_model=UserProfile)
def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        id=current_user.id,
        registration_number=current_user.registration_number,
        full_name=current_user.full_name,
        current_term=current_user.current_term,
        current_cgpa=float(current_user.current_cgpa) if current_user.current_cgpa else None,
        program_name=current_user.program_name,
        admission_year=current_user.admission_year,
        is_onboarded=bool(current_user.is_onboarded),
    )


@app.put("/api/auth/profile", response_model=UserProfile)
def update_profile(
    request: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.full_name is not None:
        current_user.full_name = request.full_name
    current_user.current_term = request.current_term
    current_user.current_cgpa = request.current_cgpa
    current_user.program_name = request.program_name
    if request.admission_year is not None:
        current_user.admission_year = request.admission_year
    current_user.is_onboarded = 1

    db.commit()
    db.refresh(current_user)

    return UserProfile(
        id=current_user.id,
        registration_number=current_user.registration_number,
        full_name=current_user.full_name,
        current_term=current_user.current_term,
        current_cgpa=float(current_user.current_cgpa) if current_user.current_cgpa else None,
        program_name=current_user.program_name,
        admission_year=current_user.admission_year,
        is_onboarded=bool(current_user.is_onboarded),
    )


# ─── Benefits Search ───────────────────────────────────────────────────────

@app.get("/api/benefits/search")
def search_benefits_api(
    query: str = Query(..., description="User query about academic benefits"),
    limit: int = Query(5, ge=1, le=20, description="Number of results to retrieve"),
    section: str | None = Query(None, description="Optional section filter"),
    db: Session = Depends(get_db),
):
    results = search_benefits(db=db, query=query, limit=limit, section_filter=section)
    return {
        "query": query,
        "section_filter": section,
        "total_results": len(results),
        "results": results,
    }


# ─── Chat Routes ────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Get or create session
    session = None
    if request.session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == request.session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        # Create a new session, title from first user message
        first_user_msg = next((m.content for m in request.messages if m.role == "user"), "New Chat")
        title = first_user_msg[:100] if first_user_msg else "New Chat"
        session = ChatSession(user_id=current_user.id, title=title)
        db.add(session)
        db.commit()
        db.refresh(session)

    # Save the latest user message
    latest_user_msg = next(
        (m for m in reversed(request.messages) if m.role == "user"), None
    )
    if latest_user_msg:
        db.add(ChatMessageModel(session_id=session.id, role="user", content=latest_user_msg.content))
        db.commit()

    # Generate AI response
    response_text = generate_chat_response(request.messages, current_user)

    # Save the AI response
    db.add(ChatMessageModel(session_id=session.id, role="assistant", content=response_text))
    db.commit()

    return ChatResponse(response=response_text, session_id=session.id)


@app.get("/api/chat/sessions", response_model=list[ChatSessionSummary])
def list_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        ChatSessionSummary(
            id=s.id,
            title=s.title,
            updated_at=s.updated_at.isoformat() if s.updated_at else "",
        )
        for s in sessions
    ]


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    return {
        "id": session.id,
        "title": session.title,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in session.messages
        ],
    }


@app.delete("/api/chat/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Delete messages first, then session
    db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"detail": "Session deleted"}
