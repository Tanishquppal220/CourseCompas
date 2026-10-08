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
    db_user = (
        db.query(User)
        .filter(User.registration_number == user.registration_number)
        .first()
    )
    if db_user:
        raise HTTPException(
            status_code=400, detail="Registration number already registered"
        )

    hashed_password = get_password_hash(user.password)
    new_user = User(
        registration_number=user.registration_number,
        hashed_password=hashed_password,
        cgpa=user.cgpa,
        current_term=user.current_term,
        program=user.program,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.post("/api/auth/login", response_model=Token)
def login(user_credentials: UserLogin, db: Annotated[Session, Depends(get_db)]):
    user = (
        db.query(User)
        .filter(User.registration_number == user_credentials.registration_number)
        .first()
    )
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
                title = last_user["content"][:30] + (
                    "..." if len(last_user["content"]) > 30 else ""
                )
                new_session = ChatSession(id=session_id, user_id=user.id, title=title)
                db.add(new_session)
                db.commit()

            # Save the user's message
            db.add(
                ChatMessage(
                    session_id=session_id, role="user", content=last_user["content"]
                )
            )
            db.commit()

        # Fetch history
        chat_history = []
        if session_id:
            past_messages = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
                .all()
            )

            # Note: We exclude the very last user message we just inserted so we don't duplicate it.
            # Actually, `run_agent` takes `query` and `chat_history` separately, so we should slice out the last one.
            if past_messages:
                for m in past_messages[:-1]:
                    chat_history.append({"role": m.role, "content": m.content})

        # Execute the Agentic Loop
        from .agent import run_agent

        user_reg_no = user.registration_number if user else None

        response_text, sources = run_agent(
            last_user["content"], user_reg_no, chat_history
        )

        if user and session_id:
            # Save the assistant's message
            db.add(
                ChatMessage(
                    session_id=session_id, role="assistant", content=response_text
                )
            )
            db.commit()

    finally:
        db.close()

    return {"response": response_text, "sources": sources, "session_id": session_id}


@app.get("/api/chat/sessions")
def list_chat_sessions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [
        {"id": s.id, "title": s.title, "created_at": s.created_at} for s in sessions
    ]


@app.get("/api/chat/sessions/{session_id}")
def get_chat_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return {
        "id": session.id,
        "title": session.title,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
    }


@app.delete("/api/chat/sessions/{session_id}")
def delete_chat_session(
    session_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted successfully"}


# ─── Browser Automation & Mock LMS Endpoints ─────────────────────────────────

from fastapi.responses import HTMLResponse


class AutomationSubmitRequest(BaseModel):
    candidate_info: dict
    target_url: str | None = None
    thread_id: str | None = None


class AutomationResumeRequest(BaseModel):
    thread_id: str
    status: str = "resolved"  # "resolved", "approved", "cancelled"
    message: str | None = None


@app.post("/api/automation/submit")
async def api_submit_automation(req: AutomationSubmitRequest):
    """Starts the LangGraph browser automation pipeline."""
    import uuid
    from .browser_agent import start_portal_automation

    thread_id = req.thread_id or f"lms_sub_{uuid.uuid4().hex[:8]}"
    result = await start_portal_automation(
        candidate_info=req.candidate_info,
        thread_id=thread_id,
        target_url=req.target_url,
    )
    return result


@app.get("/api/automation/status/{thread_id}")
async def api_automation_status(thread_id: str):
    """Inspects the current state of a browser automation thread."""
    from .browser_agent import get_portal_automation_status

    return await get_portal_automation_status(thread_id)


@app.post("/api/automation/resume")
async def api_automation_resume(req: AutomationResumeRequest):
    """Resumes a paused browser automation thread with human input."""
    from .browser_agent import resume_portal_automation

    result = await resume_portal_automation(
        thread_id=req.thread_id,
        resume_payload={"status": req.status, "message": req.message},
    )
    return result


@app.get("/mock-lms/apply", response_class=HTMLResponse)
async def mock_lms_form(challenge: str | None = None):
    """Mock university portal for testing automated form submission and challenges."""
    if challenge == "turnstile":
        return """
        <!DOCTYPE html>
        <html>
        <head><title>Just a moment... Cloudflare</title></head>
        <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: #faf9f5; margin: 0;">
            <div style="background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 450px;">
                <h2 style="color: #333; margin-top: 0;">Verifying you are human</h2>
                <p style="color: #666; font-size: 14px;">ums.lpu.in needs to review the security of your connection before proceeding.</p>
                <div id="turnstile-wrapper" style="margin: 25px auto; padding: 15px; border: 1px solid #e0e0e0; border-radius: 4px; display: inline-flex; align-items: center; gap: 12px; background: #fdfdfd;">
                    <input type="checkbox" id="cf-turnstile-cb" style="width: 24px; height: 24px; cursor: pointer;" onchange="if(this.checked){ window.location.href='/mock-lms/apply'; }">
                    <label for="cf-turnstile-cb" style="cursor: pointer; font-size: 15px; font-weight: 500;">Verify you are human</label>
                </div>
                <p style="font-size: 12px; color: #999; margin-bottom: 0;">Ray ID: <code>8b29f041a7c39e21</code> &bull; Performance & security by Cloudflare</p>
            </div>
        </body>
        </html>
        """

    if challenge == "render":
        return """
        <!DOCTYPE html>
        <html>
        <head><title>LMS Portal - Application</title></head>
        <body style="font-family: sans-serif; padding: 40px; background: #faf9f5;">
            <div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid #cc785c; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 50px auto;"></div>
            <p style="text-align: center; color: #666;">Loading dynamic form elements...</p>
            <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
            <div style="text-align: center; margin-top: 20px;">
                <button onclick="document.querySelector('.spinner').style.display='none'; document.getElementById('form-container').style.display='block';" style="padding: 8px 16px; background: #cc785c; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    Finish Loading Form
                </button>
            </div>
            <div id="form-container" style="display: none; max-width: 600px; margin: 30px auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h3>Special Academic Benefit Application</h3>
                <form action="/mock-lms/apply" method="POST">
                    <p><label>Full Name: <input type="text" name="name" required style="width: 100%; padding: 8px; margin-top: 4px;"></label></p>
                    <p><label>Registration Number: <input type="text" name="registration_number" required style="width: 100%; padding: 8px; margin-top: 4px;"></label></p>
                    <p><label>Email Address: <input type="email" name="email" required style="width: 100%; padding: 8px; margin-top: 4px;"></label></p>
                    <p><label>Course Code: <input type="text" name="course_code" required style="width: 100%; padding: 8px; margin-top: 4px;"></label></p>
                    <button type="submit" style="padding: 10px 20px; background: #cc785c; color: white; border: none; border-radius: 4px; cursor: pointer;">Submit Application</button>
                </form>
            </div>
        </body>
        </html>
        """

    return """
    <!DOCTYPE html>
    <html>
    <head><title>LMS Portal - Application Submission</title></head>
    <body style="font-family: sans-serif; background: #faf9f5; padding: 40px; margin: 0;">
        <div style="max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <h2 style="color: #252523; margin-top: 0;">EduRevolution — Special Academic Benefit Nomination</h2>
            <p style="color: #6c6a64; font-size: 14px;">Apply for course waivers, Continuous Assessment (CA) exemptions, or Grade Upgradation.</p>
            <hr style="border: 0; border-top: 1px solid #e6dfd8; margin: 20px 0;">
            <form action="/mock-lms/apply" method="POST">
                <p>
                    <label style="font-weight: 500; font-size: 14px;">Full Name<br>
                        <input type="text" name="name" placeholder="Student Name" required style="width: 100%; box-sizing: border-box; padding: 8px; margin-top: 4px; border: 1px solid #ccc; border-radius: 4px;">
                    </label>
                </p>
                <p>
                    <label style="font-weight: 500; font-size: 14px;">Registration Number<br>
                        <input type="text" name="registration_number" placeholder="12200000" required style="width: 100%; box-sizing: border-box; padding: 8px; margin-top: 4px; border: 1px solid #ccc; border-radius: 4px;">
                    </label>
                </p>
                <p>
                    <label style="font-weight: 500; font-size: 14px;">Email Address<br>
                        <input type="email" name="email" placeholder="student@example.edu" required style="width: 100%; box-sizing: border-box; padding: 8px; margin-top: 4px; border: 1px solid #ccc; border-radius: 4px;">
                    </label>
                </p>
                <p>
                    <label style="font-weight: 500; font-size: 14px;">Mapped Course Code<br>
                        <input type="text" name="course_code" placeholder="e.g. CSE205" required style="width: 100%; box-sizing: border-box; padding: 8px; margin-top: 4px; border: 1px solid #ccc; border-radius: 4px;">
                    </label>
                </p>
                <p>
                    <label style="font-weight: 500; font-size: 14px;">Benefit Category<br>
                        <select name="category" style="width: 100%; box-sizing: border-box; padding: 8px; margin-top: 4px; border: 1px solid #ccc; border-radius: 4px;">
                            <option value="Internship beyond Curriculum">Internship beyond Curriculum</option>
                            <option value="Technical Competitions / Hackathons">Technical Competitions / Hackathons</option>
                            <option value="Research Publications (Scopus)">Research Publications (Scopus)</option>
                            <option value="Patent">Patent Filed / Published / Granted</option>
                            <option value="10% Attendance Benefit">10% Attendance Benefit</option>
                        </select>
                    </label>
                </p>
                <p>
                    <label style="font-weight: 500; font-size: 14px;">Achievement Details & Proof Summary<br>
                        <textarea name="details" rows="3" placeholder="Duration, stipend/tier, publication link..." style="width: 100%; box-sizing: border-box; padding: 8px; margin-top: 4px; border: 1px solid #ccc; border-radius: 4px;"></textarea>
                    </label>
                </p>
                <button type="submit" style="background: #cc785c; color: white; padding: 10px 24px; border: none; border-radius: 4px; font-weight: 500; cursor: pointer; margin-top: 10px;">
                    Submit Application
                </button>
            </form>
        </div>
    </body>
    </html>
    """


@app.post("/mock-lms/apply", response_class=HTMLResponse)
async def mock_lms_submit(request: Request):
    """Processes mock form submission and returns reference confirmation."""
    import uuid

    form_data = await request.form()
    ref_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Application Submitted</title></head>
    <body style="font-family: sans-serif; background: #faf9f5; padding: 40px; text-align: center; margin: 0;">
        <div style="max-width: 500px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
            <h2 style="color: #2e7d32; margin-top: 0;">Application Submitted Successfully!</h2>
            <p class="alert-success" style="color: #444; font-size: 15px;">Your nomination has been forwarded to the Standing Committee for review.</p>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 4px; margin: 20px 0;">
                <p style="margin: 0; font-size: 13px; color: #777;">Confirmation Reference:</p>
                <p id="reference-number" style="margin: 5px 0 0 0; font-size: 20px; font-weight: bold; color: #cc785c;">{ref_id}</p>
            </div>
            <p style="font-size: 13px; color: #888;">Applicant: {form_data.get('name', 'Student')} (Reg: {form_data.get('registration_number', 'N/A')})</p>
            <p style="font-size: 13px; color: #888;">Course: {form_data.get('course_code', 'N/A')} &bull; Category: {form_data.get('category', 'N/A')}</p>
        </div>
    </body>
    </html>
    """


