from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Embedding dimension for all vector chunk tables.
# Matches the embedding model configured in app.embeddings.
EMBEDDING_DIM = 384


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    registration_number = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Academic Profile Information
    cgpa = Column(Numeric(4, 2), nullable=True)
    current_term = Column(String(50), nullable=True)
    program = Column(String(150), nullable=True)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(String(36), primary_key=True)  # UUID string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(50), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())


class CourseType(Base):
    __tablename__ = "course_types"

    code = Column(String(8), primary_key=True)
    description = Column(String(100))


class CourseNature(Base):
    __tablename__ = "course_natures"

    code = Column(String(8), primary_key=True)
    description = Column(String(150))


class ElectiveArea(Base):
    __tablename__ = "elective_areas"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)

    lecture_hours = Column(Integer, nullable=False, default=0)
    tutorial_hours = Column(Integer, nullable=False, default=0)
    practical_hours = Column(Integer, nullable=False, default=0)
    credits = Column(Numeric(4, 1), nullable=False)
    contact_hours = Column(Numeric(4, 1), nullable=False)


class Term(Base):
    __tablename__ = "terms"

    id = Column(Integer, primary_key=True)
    number = Column(Integer, nullable=False)
    variant = Column(String(30), nullable=True)
    label = Column(String(100), nullable=False)

    slots = relationship("TermSlot", back_populates="term", order_by="TermSlot.s_no")

    __table_args__ = (
        UniqueConstraint("number", "variant", name="uq_term_number_variant"),
    )


class ElectiveBasket(Base):
    __tablename__ = "elective_baskets"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    term_id = Column(Integer, ForeignKey("terms.id"), nullable=True)

    term = relationship("Term")
    options = relationship(
        "BasketOption", back_populates="basket", cascade="all, delete-orphan"
    )


class BasketOption(Base):
    __tablename__ = "basket_options"

    id = Column(Integer, primary_key=True)
    basket_id = Column(Integer, ForeignKey("elective_baskets.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    elective_area_id = Column(Integer, ForeignKey("elective_areas.id"), nullable=True)
    s_no = Column(Integer, nullable=True)

    basket = relationship("ElectiveBasket", back_populates="options")
    course = relationship("Course")
    elective_area = relationship("ElectiveArea")

    __table_args__ = (
        UniqueConstraint(
            "basket_id", "course_id", "elective_area_id", name="uq_basket_course_area"
        ),
    )


class TermSlot(Base):
    __tablename__ = "term_slots"

    id = Column(Integer, primary_key=True)
    term_id = Column(Integer, ForeignKey("terms.id"), nullable=False)
    s_no = Column(Integer, nullable=False)
    display_name = Column(String(150), nullable=True)

    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    basket_id = Column(Integer, ForeignKey("elective_baskets.id"), nullable=True)

    course_type_code = Column(
        String(8), ForeignKey("course_types.code"), nullable=False
    )
    course_nature_code = Column(
        String(8), ForeignKey("course_natures.code"), nullable=False
    )

    term = relationship("Term", back_populates="slots")
    course = relationship("Course")
    basket = relationship("ElectiveBasket")
    course_type = relationship("CourseType")
    course_nature = relationship("CourseNature")

    __table_args__ = (UniqueConstraint("term_id", "s_no", name="uq_term_sno"),)


# Embedded models for API responses


class CourseDocumentChunk(Base):
    __tablename__ = "course_doc_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    course_code = Column(
        String(20),
        ForeignKey("courses.code"),
        nullable=False,
        index=True,
    )

    document_name = Column(String(255), nullable=True)

    doc_type = Column(
        String(20),
        nullable=False,
    )  # Syllabus, IP

    section_title = Column(String(255), nullable=True)

    page_number = Column(Integer, nullable=False)

    chunk_index = Column(Integer, nullable=False)

    chunk_type = Column(
        String(50),
        nullable=False,
    )
    # unit
    # lecture
    # practical
    # course_outcome
    # table_row

    content = Column(Text, nullable=False)

    chunk_metadata = Column(
        "metadata",
        JSONB,
        nullable=True,
    )

    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)

    # Full Text Search column
    # Full Text Search column
    fts = Column(TSVECTOR, index=True)

    course = relationship("Course")


class BenefitChunk(Base):
    __tablename__ = "benefit_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)

    document_name = Column(
        String(255),
        nullable=False,
        default="Academic Benefits.pdf",
    )

    section_title = Column(String(255), nullable=True)

    page_number = Column(Integer, nullable=False)

    chunk_index = Column(Integer, nullable=False)

    chunk_type = Column(
        String(50),
        nullable=False,
    )

    content = Column(Text, nullable=False)

    chunk_metadata = Column(
        "metadata",
        JSONB,
        nullable=True,
    )

    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)

    # Full Text Search column
    fts = Column(TSVECTOR, index=True)
