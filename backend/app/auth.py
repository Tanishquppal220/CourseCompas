import os
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import User

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "coursecompass-super-secret-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# Pydantic Schemas
class UserCreate(BaseModel):
    registration_number: str
    password: str
    cgpa: float | None = None
    current_term: str | None = None
    program: str | None = None


class UserLogin(BaseModel):
    registration_number: str
    password: str


class UserResponse(BaseModel):
    id: int
    registration_number: str
    cgpa: float | None = None
    current_term: str | None = None
    program: str | None = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


# Helper Functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


import bcrypt


def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8")[:72], hashed_password.encode("utf-8")
    )


def get_password_hash(password):
    salt = bcrypt.gensalt()
    # bcrypt limits to 72 bytes; truncate to avoid crashes on long passwords
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


from typing import Annotated


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        registration_number: str = payload.get("sub")
        if registration_number is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = (
        db.query(User).filter(User.registration_number == registration_number).first()
    )
    if user is None:
        raise credentials_exception
    return user
