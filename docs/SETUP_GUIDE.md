# CourseCompass — Setup & Installation Guide

This guide provides end-to-end instructions for setting up, configuring, and running **CourseCompass** on your local machine using **Neon Database** (Serverless PostgreSQL with `pgvector`).

---

## 1. System Prerequisites

CourseCompass uses a cloud-hosted serverless **Neon PostgreSQL** database with `pgvector` enabled, which means **Docker is no longer required** for local development!

### Hardware Requirements
- **CPU**: Multi-core processor (x86_64 or Apple Silicon ARM64).
- **RAM**: Minimum **4 GB** (8 GB+ recommended when generating local dense embeddings with SentenceTransformers).
- **Disk Space**: At least **2 GB** free disk space for Python packages and local embedding model caches.

### Software Requirements
| Software | Minimum Version | Installation Check |
| :--- | :--- | :--- |
| **Python** | 3.13+ | `python3 --version` |
| **uv** *(Recommended)* | 0.4+ | `uv --version` (or use `python -m venv` / `pip`) |
| **Node.js & npm** | Node.js 20+, npm 10+ | `node -v && npm -v` |
| **Git** | 2.30+ | `git --version` |

> [!TIP]
> We strongly recommend installing **[uv](https://docs.astral.sh/uv/)** for ultra-fast Python package and virtual environment management:
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

---

## 2. Repository Setup

Clone the repository to your local workspace:

```bash
git clone https://github.com/Tanishquppal220/CourseCompas.git CourseCompass
cd CourseCompass
```

The repository is organized into two primary subprojects:
- `backend/`: FastAPI application, LangChain ReAct agent, hybrid retrieval, and data ingestion pipelines.
- `frontend/`: React 19, Vite, TypeScript, and Tailwind CSS v4 single-page application.

---

## 3. Database Setup (Neon Serverless PostgreSQL)

CourseCompass connects to a **Neon Database** instance (PostgreSQL 16) with the `pgvector` extension enabled and SSL enforcement.

### 3.1 Obtaining Your Neon Connection String
If you have an existing Neon project:
1. Log in to the [Neon Console](https://console.neon.tech).
2. Select your project and navigate to the **Dashboard**.
3. Under **Connection Details**, copy the connection string (with pooled connection recommended):
   ```text
   postgresql://neondb_owner:<password>@<endpoint-pooler>.neon.tech/coursecompass?sslmode=require
   ```

> [!NOTE]
> Neon databases automatically provide native `pgvector` support, connection pooling, automated branch backups, and zero-maintenance scaling without running local Docker containers.

---

## 4. Backend Configuration & Setup

### 4.1 Configure Environment Variables
Navigate to the `backend/` directory and create your `.env` file:

```bash
cd backend
cp .env.example .env
```

Open `.env` in your text editor and set your Neon connection string and AI provider credentials:

```env
# Neon Database connection string (Cloud Neon PostgreSQL instance with pgvector)
DATABASE_URL="postgresql://neondb_owner:<your_password>@<your_neon_host>.neon.tech/coursecompass?sslmode=require"

# LLM Provider Credentials
# Option A: AWS Bedrock (Default configuration in app/llm.py)
AWS_ACCESS_KEY_ID="your-aws-access-key"
AWS_SECRET_ACCESS_KEY="your-aws-secret-key"
AWS_REGION="us-east-1"

# Option B: Google Gemini API (if switching provider in app/llm.py)
GOOGLE_API_KEY="your-google-api-key"

# Application Security
SECRET_KEY="replace-with-a-secure-random-secret-key-in-production"
```

#### Environment Variables Reference:
| Variable | Required | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | Neon PostgreSQL connection string (including `?sslmode=require`). |
| `LOCAL_DATABASE_URL` | Optional | Fallback local database URL (optional if using local Postgres). |
| `AWS_ACCESS_KEY_ID` | **Yes\*** | AWS access key with permissions to invoke Amazon Bedrock foundation models. |
| `AWS_SECRET_ACCESS_KEY` | **Yes\*** | AWS secret key corresponding to the access key. |
| `AWS_REGION` | **Yes\*** | AWS Region where Bedrock models are active (e.g., `us-east-1`). |
| `GOOGLE_API_KEY` | Optional | API Key for Google Gemini models if switching provider in `llm.py`. |
| `SECRET_KEY` | Optional | Secret key used for signing JWT access tokens (falls back to default in dev). |

*\* Required when using the default Amazon Bedrock model (`bedrock_converse:openai.gpt-oss-120b-1:0`).*

---

### 4.2 Install Python Dependencies
Using `uv`:

```bash
cd backend
uv sync
```

Or using standard `pip`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 5. Database Seeding & Ingestion Pipeline

To populate the curriculum tables in Neon, parse and embed course documents, and create the vector and Full-Text Search (FTS) indexes, execute the following 3 commands in order:

### Step 5.1: Seed Relational Curriculum Data
Creates the relational tables in your Neon database and inserts programs, terms (Terms 1–8), 250+ courses, elective baskets, basket options, and term slots:

```bash
# Inside backend/
uv run python scripts/seed.py
```

*Expected output:*
```text
Table schema verified.
Inserted 250 courses.
Created 10 terms with term slots.
Populated elective baskets and course basket mappings.
Seed complete!
```

### Step 5.2: Ingest & Embed Academic Documents & Benefits
Parses course syllabus PDFs, Instruction Plan (IP) PDFs, and the Academic Benefits policy (`benefits_clean.md`). Generates dense vector embeddings using `BAAI/bge-small-en-v1.5` (384-dimensional) and stores them directly in `course_doc_chunks` and `benefit_chunks` in Neon with HNSW indexes:

```bash
# Run incremental ingestion (uses PyMuPDF backend by default):
uv run python scripts/ingest.py
```

#### Ingestion CLI Options:
- `--workers N`: Run with `N` parallel worker processes to accelerate PDF parsing:
  ```bash
  uv run python scripts/ingest.py --workers 4
  ```
- `--courses CODE1 CODE2`: Ingest only specific courses (e.g., for testing):
  ```bash
  uv run python scripts/ingest.py --courses CSE202 CSE205 INT108
  ```
- `--benefits-only`: Ingest only the Academic Benefits policy markdown:
  ```bash
  uv run python scripts/ingest.py --benefits-only
  ```
- `--force-rebuild`: Invalidate cache and re-parse and re-embed all documents from scratch:
  ```bash
  uv run python scripts/ingest.py --force-rebuild
  ```

### Step 5.3: Add Full-Text Search (FTS) Columns & GIN Indexes
Adds generated `tsvector` columns and GIN indexes to both `course_doc_chunks` and `benefit_chunks` in Neon to enable hybrid retrieval (dense vector + lexical keyword matching):

```bash
uv run python scripts/add_fts.py
```

*Expected output:*
```text
Adding fts to course_doc_chunks...
Adding fts to benefit_chunks...
Done!
```

---

## 6. Running the Application

### 6.1 Start the Backend API Server
Launch the FastAPI development server:

```bash
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc Documentation**: `http://127.0.0.1:8000/redoc`

Verify the backend is operational:
```bash
curl http://127.0.0.1:8000/api/status
```
Response:
```json
{
  "status": "ok",
  "service": "CourseCompass Academic & Benefits Assistant",
  "version": "0.3.0"
}
```

---

### 6.2 Start the Frontend Development Server
Open a new terminal window, navigate to the `frontend/` directory, install dependencies, and launch Vite:

```bash
cd frontend
npm install
npm run dev
```

The frontend application will start at:
- **Web UI URL**: `http://localhost:5173`

The Vite dev server automatically proxies all `/api/*` requests to `http://127.0.0.1:8000`.

---

## 7. Verifying the Full Stack

1. Open your browser and navigate to `http://localhost:5173`.
2. Click **Register** on the top right:
   - Registration Number: `12200001`
   - Password: `Password123!`
   - Program: `B.Tech Computer Science and Engineering`
   - Current Term: `Term 5`
   - CGPA: `7.8`
3. Click **Login** to authenticate and save your JWT session.
4. Test queries in the chat box:
   - *"What are the prerequisites and syllabus topics for CSE205?"*
   - *"I did a 3-month startup internship with an 8,000 INR monthly stipend. Am I eligible for any academic benefits?"*
   - *"What is the attendance policy and how do I get the 10% attendance benefit?"*
   - *"I have a Scopus Q1 publication and a hackathon win. How should I stack these benefits across my courses?"*

---

## 8. Troubleshooting & Common Issues

### Issue 1: Neon Connection SSL Error
**Symptom:** `psycopg2.OperationalError: no pg_hba.conf entry for host ..., SSL off`.  
**Solution:**
Ensure `?sslmode=require` is appended to your `DATABASE_URL` in `.env`:
```env
DATABASE_URL="postgresql://neondb_owner:<password>@<host>.neon.tech/coursecompass?sslmode=require"
```

### Issue 2: Neon Connection Timeout or Pooled Endpoint
**Symptom:** Connection hangs or reports max client connections exceeded.  
**Solution:**
In the Neon Console, copy the connection string with connection pooling enabled (endpoint containing `-pooler` in the host).

### Issue 3: Bedrock `AccessDeniedException` or Model Not Found
**Symptom:** Backend returns 500 error when chatting: `AccessDeniedException: User is not authorized to perform: bedrock:InvokeModel`.  
**Solution:**
1. Ensure your AWS IAM User/Role has permissions for `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`.
2. Ensure model access has been enabled in the AWS Bedrock console for your region (`us-east-1` or `us-west-2`).
3. If using Google Gemini instead, update `app/llm.py` to use `ChatGoogleGenerativeAI` and set `GOOGLE_API_KEY`.

### Issue 4: Port Conflicts (8000 or 5173 in use)
**Symptom:** `address already in use` when starting Uvicorn or Vite.  
**Solution:**
- For FastAPI port conflict, specify an alternate port:
  ```bash
  uv run uvicorn app.main:app --port 8001
  ```
  (and update `target: 'http://127.0.0.1:8001'` in `frontend/vite.config.ts`).

---

## 9. Development Scripts Reference

| Command | Working Directory | Purpose |
| :--- | :--- | :--- |
| `uv run python scripts/seed.py` | `backend/` | Seeds curriculum relational database in Neon |
| `uv run python scripts/ingest.py` | `backend/` | Parses and embeds course documents and benefits into Neon |
| `uv run python scripts/add_fts.py` | `backend/` | Configures PostgreSQL Full-Text Search columns and GIN indexes |
| `uv run uvicorn app.main:app --reload` | `backend/` | Runs FastAPI backend server in reload mode |
| `uv run ruff check .` | `backend/` | Lints backend Python codebase |
| `uv run ruff format .` | `backend/` | Formats backend Python codebase |
| `npm run dev` | `frontend/` | Runs Vite frontend development server |
| `npm run build` | `frontend/` | Compiles TypeScript and builds production SPA into `frontend/dist/` |
| `npm run lint` | `frontend/` | Lints frontend React codebase |
