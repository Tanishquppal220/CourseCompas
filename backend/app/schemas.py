from pydantic import BaseModel


# --- Auth Schemas ---

class RegisterRequest(BaseModel):
    registration_number: str
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    registration_number: str
    password: str


class UserProfile(BaseModel):
    id: int
    registration_number: str
    full_name: str | None
    current_term: int | None
    current_cgpa: float | None
    program_name: str | None
    admission_year: int | None
    is_onboarded: bool

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
    needs_onboarding: bool


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    current_term: int
    current_cgpa: float
    program_name: str
    admission_year: int | None = None


# --- Chat Schemas ---

class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    session_id: int | None = None  # None = create new session


class ChatResponse(BaseModel):
    response: str
    session_id: int


class ChatSessionSummary(BaseModel):
    id: int
    title: str
    updated_at: str

    class Config:
        from_attributes = True
