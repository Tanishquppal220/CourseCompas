# CourseCompass — Backend Service

The backend is a high-performance Python application built on **FastAPI**, **SQLAlchemy**, **pgvector**, **LangChain**, and **Hugging Face Sentence Transformers**. It provides the core conversational AI reasoning engine, hybrid document retrieval, relational curriculum querying, and user authentication, backed by **Neon Serverless PostgreSQL**.

---

## 1. Directory Structure

```text
backend/
├── app/
│   ├── main.py          # FastAPI application, route handlers, CORS, and startup
│   ├── auth.py          # JWT authentication, bcrypt password hashing, auth dependencies
│   ├── models.py        # SQLAlchemy models (Relational schema, pgvector chunks, FTS)
│   ├── database.py      # Database engine, connection pooling, and SessionLocal factory
│   ├── llm.py           # LLM agent configuration (AWS Bedrock Converse / Gemini)
│   ├── agent.py         # ReAct agent loop, tool definitions, student profile injection
│   ├── embeddings.py    # Dense vector embedding model (BAAI/bge-small-en-v1.5, 384 dim)
│   ├── reranker.py      # Cross-encoder reranking model (BAAI/bge-reranker-base)
│   └── retrieval.py     # Hybrid search orchestrator (dense vector + FTS tsvector)
├── data/
│   ├── Syllabus/        # 36+ Course Syllabus PDF documents
│   ├── IP/              # 39+ Course Instruction Plan (IP) PDF documents
│   ├── Schema.md        # Raw curriculum markdown specification
│   └── benefits_clean.md# Cleaned EduRevolution academic benefits policy text
├── scripts/
│   ├── seed.py          # Relational database seeder (terms, courses, baskets, slots)
│   ├── ingest.py        # End-to-end PDF parser, chunker, and vector embedder
│   ├── chunkers.py      # Domain-specific semantic chunkers for Syllabus, IP, & Benefits
│   ├── cleaners.py      # Text cleaners and boilerplate filters
│   ├── parse_pdf.py     # PDF layout extractor supporting PyMuPDF and Docling
│   └── add_fts.py       # Adds generated tsvector columns and GIN indexes
├── pyproject.toml       # Python dependencies and project metadata
├── uv.lock              # Deterministic uv dependency lockfile
└── .env.example         # Template for environment configuration
```

---

## 2. Installation & Setup

### 2.1 Prerequisites
- Python **3.13+**
- **Neon Database** connection string (Serverless PostgreSQL with `pgvector` enabled)
- `uv` package manager (recommended) or `pip`

### 2.2 Configure Environment
```bash
cp .env.example .env
```
Edit `.env` and configure your Neon database URL and LLM provider credentials:
```env
DATABASE_URL="postgresql://neondb_owner:<password>@<neon-host>.neon.tech/coursecompass?sslmode=require"
AWS_ACCESS_KEY_ID="your-key"
AWS_SECRET_ACCESS_KEY="your-secret"
AWS_REGION="us-east-1"
```

### 2.3 Install Dependencies
```bash
# Using uv:
uv sync

# Or using standard venv:
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 3. Database Initialization & Ingestion Pipeline

Execute the following three steps to initialize and populate your Neon database:

### Step 1: Seed Relational Curriculum
Creates tables in Neon and loads all 8 terms, 250+ courses, elective areas, baskets, and term slots:
```bash
uv run python scripts/seed.py
```

### Step 2: Parse & Embed Documents
Parses course Syllabus PDFs, IP PDFs, and `benefits_clean.md`, generates dense vectors, and creates HNSW indexes in Neon:
```bash
# Ingest everything incrementally (fast repeat runs):
uv run python scripts/ingest.py

# Ingest with 4 parallel worker processes (recommended for first run):
uv run python scripts/ingest.py --workers 4

# Ingest specific courses only:
uv run python scripts/ingest.py --courses CSE202 CSE205 INT108

# Ingest only academic benefits policy:
uv run python scripts/ingest.py --benefits-only

# Force re-parsing and re-embedding from scratch:
uv run python scripts/ingest.py --force-rebuild
```

### Step 3: Add Full-Text Search (FTS) Indexes
Configures generated `tsvector` columns and GIN indexes for hybrid search:
```bash
uv run python scripts/add_fts.py
```

---

## 4. Running the Server

Start the FastAPI application with auto-reload:
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API Base: `http://localhost:8000`
- Swagger Interactive UI: `http://localhost:8000/docs`
- ReDoc UI: `http://localhost:8000/redoc`

---

## 5. Development & Code Quality

```bash
# Lint code with Ruff
uv run ruff check .

# Format code with Ruff
uv run ruff format .
```
