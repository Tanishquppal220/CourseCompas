"""Database connection, session factory, and schema bootstrap."""

import os
from pathlib import Path

from alembic.config import Config
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.models import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("LOCAL_DATABASE_URL")


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Alembic revision history lives next to this module (backend/alembic.ini).
BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def upgrade_schema() -> None:
    """Create the vector extension + ORM tables, then apply Alembic migrations.

    The ORM models (``app.models.Base``) are the schema truth; ``create_all``
    populates a fresh database and ``alembic upgrade head`` brings pre-existing
    databases to the latest revision. Both are idempotent, so this is safe to
    call at the start of every ingest/seed run -- the single place that answers
    "how does the schema get created/updated?".
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    command.upgrade(Config(str(ALEMBIC_INI)), "head")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()