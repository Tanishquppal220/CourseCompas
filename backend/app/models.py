from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Program(Base):
    __tablename__ = "programs"

    ProgramID = Column(Integer, primary_key=True, autoincrement=True)
    ProgramCode = Column(String(50), nullable=False)
    ProgramName = Column(String(255), nullable=False)
    AdmissionYear = Column(Integer, nullable=False)
    DurationYears = Column(Integer, nullable=False)

    terms = relationship("Term", back_populates="program")


class Course(Base):
    __tablename__ = "courses"

    CourseCode = Column(String(20), primary_key=True)
    CourseTitle = Column(String(255), nullable=False)
    L = Column(Integer, default=0)
    T = Column(Integer, default=0)
    P = Column(Integer, default=0)
    Credit = Column(Numeric(3, 1), default=0.0)
    ContactHours = Column(Numeric(4, 1), default=0.0)
    CourseType = Column(String(10), nullable=True)
    CourseNature = Column(String(10), nullable=True)

    curriculum_items = relationship("TermCurriculum", back_populates="course")
    basket_items = relationship("ElectiveBasket", back_populates="course")
    prerequisites = relationship("CoursePrerequisite", foreign_keys="CoursePrerequisite.CourseCode", back_populates="course")
    prerequisite_for = relationship("CoursePrerequisite", foreign_keys="CoursePrerequisite.PrereqCode", back_populates="prerequisite_course")


class Term(Base):
    __tablename__ = "terms"

    TermID = Column(Integer, primary_key=True, autoincrement=True)
    ProgramID = Column(Integer, ForeignKey("programs.ProgramID"), nullable=False)
    TermNumber = Column(Integer, nullable=False)
    TermPath = Column(String(100), nullable=False)

    program = relationship("Program", back_populates="terms")
    curriculum = relationship("TermCurriculum", back_populates="term")


class TermCurriculum(Base):
    __tablename__ = "term_curriculum"

    CurriculumID = Column(Integer, primary_key=True, autoincrement=True)
    TermID = Column(Integer, ForeignKey("terms.TermID"), nullable=False)
    CourseCode = Column(String(20), ForeignKey("courses.CourseCode"), nullable=True)
    PlaceholderName = Column(String(100), nullable=True)

    term = relationship("Term", back_populates="curriculum")
    course = relationship("Course", back_populates="curriculum_items")


class ElectiveBasket(Base):
    __tablename__ = "elective_baskets"

    BasketID = Column(Integer, primary_key=True, autoincrement=True)
    BasketName = Column(String(100), nullable=False)
    CourseCode = Column(String(20), ForeignKey("courses.CourseCode"), nullable=False)
    ElectiveArea = Column(String(100), nullable=True)

    course = relationship("Course", back_populates="basket_items")


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    CourseCode = Column(String(20), ForeignKey("courses.CourseCode"), primary_key=True)
    PrereqCode = Column(String(20), ForeignKey("courses.CourseCode"), primary_key=True)

    course = relationship("Course", foreign_keys=[CourseCode], back_populates="prerequisites")
    prerequisite_course = relationship("Course", foreign_keys=[PrereqCode], back_populates="prerequisite_for")


class BenefitChunk(Base):
    __tablename__ = "benefit_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_name = Column(String(255), default="Academic Benefits.pdf")
    section_title = Column(String(255), nullable=False)
    page_number = Column(Integer, nullable=False)
    chunk_type = Column(String(50), nullable=False)  # "policy_condition", "table_row", "faq", etc.
    content = Column(String, nullable=False)  # Text content of the chunk
    chunk_metadata = Column("metadata", JSONB, nullable=True)
    embedding = Column(Vector(384))


class SchemaChunk(Base):
    __tablename__ = "schema_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_name = Column(String(255), default="Schema.md")
    section_title = Column(String(255), nullable=False)
    chunk_type = Column(String(50), nullable=False)
    content = Column(String, nullable=False)
    chunk_metadata = Column("metadata", JSONB, nullable=True)
    embedding = Column(Vector(384))


class CourseDocumentChunk(Base):
    __tablename__ = "course_doc_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_code = Column(String(20), ForeignKey("courses.CourseCode"), nullable=False)
    doc_type = Column(String(20), nullable=False) # 'Syllabus' or 'IP'
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(String, nullable=False)
    embedding = Column(Vector(384))
    course = relationship("Course")
