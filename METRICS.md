# Repository Metrics & Technical Analysis

This document provides a factual, evidence-backed audit of the **CourseCompass** repository. All findings reflect code and assets present in the codebase. Items that do not exist are explicitly labeled **not present**.

---

## 1. Exact Tech Stack & Dependency Versions

### 1.1 Backend Runtime & Core Services
- **Python Version**: `>=3.13` (configured in `backend/pyproject.toml`)
- **Package & Environment Manager**: `uv` (`backend/uv.lock` present)
- **Database & Vector Storage**: PostgreSQL with `pgvector` extension

### 1.2 Backend Dependencies (`backend/pyproject.toml`)

#### Production Dependencies
| Package | Version Specifier | Category / Purpose |
| :--- | :--- | :--- |
| `fastapi[standard]` | `>=0.141.1` | REST API web framework & standard server stack |
| `sqlalchemy` | `>=2.0.0` | Relational ORM & SQL query builder |
| `psycopg2-binary` | `>=2.9.9` | PostgreSQL database adapter |
| `pgvector` | `>=0.2.0` | Vector similarity search extension bindings for PostgreSQL |
| `pydantic-settings` | `>=2.0.0` | Settings management via environment variables |
| `alembic` | `>=1.13.0` | Database migrations management |
| `pypdf` | `>=5.0.0` | PDF reading and text extraction |
| `pdfplumber` | `>=0.11.10` | Detailed PDF text and table extraction |
| `pandas` | `>=3.0.5` | Data analysis and tabular manipulation |
| `sentence-transformers` | `>=6.0.1` | Local sentence embeddings and cross-encoder rerankers |
| `python-dotenv` | `>=1.2.3` | Environment variable file (.env) loading |
| `langchain` | `>=1.3.18` | LLM application orchestration framework |
| `langchain-google-genai` | `>=4.4.0` | Google Gemini API integration for LangChain |
| `langchain-text-splitters` | `>=1.1.2` | Text chunking algorithms |
| `langchain-aws` | `>=1.7.5` | Amazon Bedrock integration for LangChain |
| `langgraph` | `>=1.2.11` | Stateful, multi-actor LLM agent workflows |
| `langchain-community` | `>=0.4.2` | LangChain community tool integrations |
| `python-jose[cryptography]` | `>=3.5.0` | JWT token generation and authentication verification |
| `passlib[bcrypt]` | `>=1.7.4` | Password hashing utility |
| `pymupdf` | `>=1.28.2` | High-performance PDF processing engine |
| `pymupdf-layout` | `>=1.28.2` | Document layout detection extension for PyMuPDF |
| `pymupdf4llm` | `>=1.28.2` | Markdown extraction from PDFs for LLMs |
| `ruff` | `>=0.16.6` | Fast Python linter and code formatter |
| `playwright` | `>=1.62.0` | Headless and headed browser automation |
| `nest-asyncio` | `>=1.6.0` | Patch for concurrent asyncio event loops |

#### Backend Development Dependencies (`dependency-groups.dev`)
| Package | Version Specifier | Category / Purpose |
| :--- | :--- | :--- |
| `pytest` | `>=9.1.1` | Testing framework |
| `pytest-asyncio` | `>=1.4.0` | Asynchronous test execution for pytest |
| `python-docx` | `>=1.2.0` | Parsing and reading DOCX syllabus documents |

#### Additional Package Manifests
- `requirements.txt`: **not present**

---

### 1.3 Frontend Dependencies (`frontend/package.json`)

#### Runtime & Tooling
- **Language**: TypeScript (`~6.0.2`)
- **Build Tool / Bundler**: Vite (`^8.2.2`)
- **UI Framework**: React (`^19.2.8`), React DOM (`^19.2.8`)

#### Production Dependencies
| Package | Version Specifier | Purpose |
| :--- | :--- | :--- |
| `@base-ui/react` | `^1.7.0` | Accessible unstyled UI components |
| `@fontsource-variable/geist` | `^5.3.0` | Geist variable font |
| `@fontsource/cormorant-garamond` | `^5.3.0` | Cormorant Garamond serif font |
| `@shadcn/react` | `^0.3.1` | Shadcn UI primitives |
| `@tailwindcss/typography` | `^0.5.20` | Typographic prose styling for rendered markdown |
| `@tailwindcss/vite` | `^4.3.3` | Tailwind CSS v4 Vite plugin |
| `class-variance-authority` | `^0.7.1` | Component variant styling utility |
| `clsx` | `^2.1.1` | Utility for conditionally constructing className strings |
| `cn` | `^0.2.5` | Helper for joining class names |
| `lucide-react` | `^1.39.0` | Icon library for React |
| `react` | `^19.2.8` | Core UI library |
| `react-dom` | `^19.2.8` | DOM rendering for React |
| `react-markdown` | `^10.1.0` | Markdown renderer for LLM chat messages |
| `react-router-dom` | `^7.18.3` | Declarative client-side routing |
| `rehype-highlight` | `^7.0.2` | Syntax highlighting for code blocks in markdown |
| `rehype-raw` | `^7.0.0` | HTML parsing within markdown |
| `remark-gfm` | `^4.0.1` | GitHub Flavored Markdown support |
| `shadcn` | `^4.21.0` | UI component registry tool |
| `tailwind-merge` | `^3.6.0` | Merge Tailwind CSS classes without conflict |
| `tailwindcss` | `^4.3.3` | Utility-first CSS framework |
| `tw-animate-css` | `^1.4.0` | Animation classes for Tailwind |

#### Frontend Development Dependencies
| Package | Version Specifier | Purpose |
| :--- | :--- | :--- |
| `@eslint/js` | `^10.0.1` | ESLint JavaScript configurations |
| `@types/node` | `^24.13.3` | TypeScript definitions for Node.js |
| `@types/react` | `^19.2.18` | TypeScript definitions for React |
| `@types/react-dom` | `^19.2.4` | TypeScript definitions for React DOM |
| `@vitejs/plugin-react` | `^6.1.0` | Vite plugin for React Fast Refresh |
| `eslint` | `^10.9.0` | JavaScript / TypeScript linter |
| `eslint-plugin-react-hooks` | `^7.1.1` | React Hooks linting rules |
| `eslint-plugin-react-refresh` | `^0.5.4` | Hot module replacement lint rules |
| `globals` | `^17.11.0` | Global variable definitions for linters |
| `typescript` | `~6.0.2` | TypeScript compiler |
| `typescript-eslint` | `^8.67.0` | TypeScript toolchain for ESLint |
| `vite` | `^8.2.2` | Modern frontend dev server and bundler |

---

### 1.4 Model Files & Referenced Architectures
- **Committed Model Files in Repository Source Tree (`.pt`, `.pth`, `.tflite`, `.xgb`, `.onnx`, `.bin`, `.safetensors`, `.pkl`)**: **not present**
  *(Note: Cached internal `.onnx` and `.pkl` artifacts are located strictly within Python virtual environment packages (`backend/.venv/`) for upstream dependencies `rapidocr-onnxruntime` and `pymupdf`, and PyMuPDF document hash caches in `backend/.cache/pymupdf/`, but no model weights or checkpoints are authored or committed in the project codebase).*

- **Referenced Pretrained & Cloud Models**:
  - **Dense Text Embedding Model**: `BAAI/bge-small-en-v1.5`
    - Referenced in: `backend/app/embeddings.py` (Line 9)
    - Output vector dimension: `384`
    - Execution library: `sentence-transformers`
    - *(Historical comment in the old `backend/scripts/ingest.py` referenced `Qwen3-Embedding-0.6B`; the active codebase uses `BAAI/bge-small-en-v1.5`. The comment was dropped when `ingest.py` became a thin CLI over `backend/scripts/ingestion/`.)*
  - **Cross-Encoder Reranker Model**: `BAAI/bge-reranker-base`
    - Referenced in: `backend/app/reranker.py` (Line 13)
    - Execution library: `sentence-transformers`
  - **LLM Reasoning & Agent Engine**: `bedrock_converse:openai.gpt-oss-120b-1:0` (active)
    - Referenced in: `backend/app/llm.py` (Line 10)
    - Alternative model referenced in comments: `bedrock_converse:us.meta.llama4-maverick-17b-instruct-v1:0` (`backend/app/llm.py` Line 11)
    - Execution provider: AWS Bedrock Converse API via `langchain-aws`

---

## 2. Training Configurations & Dataset Inventory

### 2.1 Hyperparameters
| Hyperparameter | Status | Value / Code Reference |
| :--- | :--- | :--- |
| **Learning Rate (`lr`)** | **not present** | No training loops or optimizer definitions in codebase |
| **Epochs** | **not present** | No training loops or epoch schedules in codebase |
| **Training Batch Size** | **not present** | No model training pipeline exists in codebase |
| **Gamma ($\gamma$)** | **not present** | No reinforcement learning or discount factors in codebase |
| **Epsilon ($\epsilon$) Schedule** | **not present** | No exploration/exploitation policies in codebase |
| **Replay Buffer Size** | **not present** | No experience replay buffers in codebase |

#### Non-Training / Operational Batch Sizes Present
- **Embedding Inference Batch Size**: `BATCH_SIZE = 64` (defined in `backend/app/embeddings.py` Line 11 for batch encoding text chunks).

---

### 2.2 Dataset Paths & Dataset Sizes

- **Image / Label Dataset Folders (e.g. YOLO, COCO, VOC)**: **not present** (0 image files, 0 label files in project source tree).
- **Document & Knowledge Base Datasets**:
  - `backend/data/Syllabus/`: **36 files** (All 36 are `.pdf` files containing course syllabus documents from Lovely Professional University).
  - `backend/data/IP/`: **39 files** (38 `.pdf` files and 1 `.docx` file [`CSE273.docx`] containing Instruction Plans with lecture breakdowns, evaluation criteria, and marks weightages).
  - `backend/data/benefits_clean.md`: **1 document** (25,619 bytes / 25 KB; structured Markdown detailing the 8 EduRevolution benefit pathways: 10% Attendance Benefit, Duty Leave, Grade Upgradation, Internships, NPTEL/MOOCs equivalence, Project benefits, RPL, and SCRGM).
  - `backend/data/Schema.md`: **1 document** (41,257 bytes / 41 KB; schema specification of curriculum structures, baskets, and courses).
  - `backend/scripts/seeding/`: the relational seed dataset, split into `curriculum_data.py` (data: 972 lines, 42,975 bytes; course codes, elective baskets, Terms 1-8 slot plans), `loaders.py` (idempotent get-or-create helpers), and `load_curriculum.py` (`load_all` + `run`).

---

## 3. Evaluation Results, Metrics, Benchmarks & Confusion Matrices

| Evaluation Asset Type | Status | Findings & Notes |
| :--- | :--- | :--- |
| **Jupyter Notebooks (`.ipynb`)** | **not present** | 0 `.ipynb` notebook files exist in the repository. |
| **Results Directory (`results/`)** | **not present** | No standalone results folder exists. |
| **Confusion Matrices** | **not present** | No evaluation confusion matrices are present. *(Note: The phrase "confusion matrix" appears solely as an academic syllabus topic covered in Lecture 11 of the CSE274 machine learning course parsed inside `backend/results.md`).* |
| **Benchmark / Offline Model Metrics (`accuracy`, `precision`, `recall`, `F1`, `ROC-AUC`)** | **not present** | No model training or validation benchmark scores exist in the repository. *(Note: `docs/ARCHITECTURE.md` uses "precision" purely conceptually when describing retrieval chunk quality: "Top 5 Highest-Precision Chunks").* |
| **Evaluation Logs** | **not present** | No model test logs exist. *(Files with `.log` extensions in `backend/profiles/portal_session/` are Chromium LevelDB session state logs generated during Playwright execution).* |
| **Test Suite Verification** | **present (Functional)** | `backend/tests/test_browser_automation.py` provides automated integration tests for Playwright browser interaction, mock LMS form filling, and blocker diagnostic detection. |

---

## 4. Largest / Most Complex Function in the Codebase

### Function Identification
- **Function Name**: `form_filling_node(state: LMSAutomationState)`
- **File**: `backend/app/browser_agent.py`
- **Location**: Lines 305 to 522
- **Function Length**: **218 lines**
- **Estimated Cyclomatic Complexity**: **~52**

### 3-Line Explanation
1. Automates a Playwright browser session to populate academic benefit claim forms with candidate details (name, registration number, course code, category, proof description) using prioritized accessible role selectors and CSS fallback heuristics.
2. Performs real-time DOM diagnostics to identify rendering blockers (CAPTCHA gates, MFA requirements, missing fields, or modal dialogs), capturing base64 diagnostic screenshots and routing workflow execution into human-in-the-loop escalation upon detection.
3. Submits the form, validates subsequent DOM alert states for input rejections or confirmation identifiers, closes the browser context cleanly, and emits structured completion status back to the LangGraph state machine.

---

## 5. Dependency Graph Summary

### 5.1 Backend Python Modules (`backend/`)
- `backend/app/__init__.py`: imports none (empty package initialization)
- `backend/app/agent.py`: imports `app.browser_agent`, `app.database`, `app.llm`, `app.models`, `app.retrieval`
- `backend/app/auth.py`: imports `app.database`, `app.models`
- `backend/app/browser_agent.py`: imports none (leaf module)
- `backend/app/database.py`: imports none (leaf module)
- `backend/app/embeddings.py`: imports none (leaf module)
- `backend/app/llm.py`: imports none (leaf module)
- `backend/app/main.py`: imports `app.agent`, `app.auth`, `app.browser_agent`, `app.database`, `app.models`
- `backend/app/models.py`: imports none (leaf module)
- `backend/app/reranker.py`: imports none (leaf module)
- `backend/app/retrieval.py`: imports `app.embeddings`, `app.models`, `app.reranker`
- `backend/scripts/add_fts.py`: imports `alembic.command`, `alembic.config`
- `backend/scripts/ingest.py`: imports `ingestion.cli`
- `backend/scripts/seed.py`: imports `seeding.load_curriculum`
- `backend/scripts/ingestion/cli.py`: imports `ingestion.pipeline`
- `backend/scripts/ingestion/pipeline.py`: imports `app.database`, `app.embeddings`, `app.models`, `ingestion.chunking`, `ingestion.console`, `ingestion.database`, `ingestion.parsing`, `ingestion.paths`
- `backend/scripts/ingestion/database.py`: imports `app.database`, `app.models`
- `backend/scripts/ingestion/paths.py`: imports none (leaf module)
- `backend/scripts/ingestion/console.py`: imports none (leaf module)
- `backend/scripts/ingestion/parsing/parser.py`: imports `ingestion.parsing.cache`, `ingestion.parsing.config`, `ingestion.parsing.models`, `ingestion.parsing.pymupdf_parser`
- `backend/scripts/ingestion/parsing/pymupdf_parser.py`: imports `ingestion.parsing.models`
- `backend/scripts/ingestion/parsing/cache.py`: imports `ingestion.parsing.config`, `ingestion.parsing.models`
- `backend/scripts/ingestion/parsing/config.py`: imports `ingestion.paths`
- `backend/scripts/ingestion/parsing/models.py`: imports none (leaf module)
- `backend/scripts/ingestion/cleaning/instruction_plan.py`: imports `ingestion.cleaning.text`
- `backend/scripts/ingestion/cleaning/text.py`: imports none (leaf module)
- `backend/scripts/ingestion/chunking/chunk.py`: imports `ingestion.cleaning`, `ingestion.chunking.metadata`
- `backend/scripts/ingestion/chunking/metadata.py`: imports none (leaf module)
- `backend/scripts/ingestion/chunking/syllabus.py`: imports `ingestion.cleaning`, `ingestion.chunking.chunk`, `ingestion.chunking.metadata`
- `backend/scripts/ingestion/chunking/instruction_plan.py`: imports `ingestion.cleaning`, `ingestion.chunking.chunk`, `ingestion.chunking.metadata`
- `backend/scripts/ingestion/chunking/benefits.py`: imports `ingestion.chunking.chunk`, `ingestion.chunking.metadata`
- `backend/scripts/seeding/load_curriculum.py`: imports `app.database`, `app.models`, `seeding.curriculum_data`, `seeding.loaders`
- `backend/scripts/seeding/loaders.py`: imports `app.models`, `seeding.curriculum_data`
- `backend/scripts/seeding/curriculum_data.py`: imports none (leaf module)
- `backend/alembic/env.py`: imports `alembic`, `app.database`, `app.models`
- `backend/alembic/versions/0001_baseline.py`: imports none (leaf module)
- `backend/alembic/versions/0002_add_full_text_search.py`: imports `alembic`, `app.models`
- `backend/alembic/versions/0003_page_number_nullable.py`: imports `alembic`, `sqlalchemy`
- `backend/scripts/tools/dump_pdf_markdown.py`: imports none (leaf module)
- `backend/tests/test_browser_automation.py`: imports `app.browser_agent`, `app.main`

---

### 5.2 Frontend TypeScript / React Modules (`frontend/src/`)
- `frontend/src/App.tsx`: imports `components/chat-window`, `components/layout`, `pages/Login`, `pages/Profile`, `pages/Register`
- `frontend/src/components/app-sidebar.tsx`: imports `lib/authContext`, `components/ui/avatar`, `components/ui/sidebar`
- `frontend/src/components/chat-header.tsx`: imports `components/ui/button`, `components/ui/separator`, `components/ui/sidebar`
- `frontend/src/components/chat-input.tsx`: imports `components/ui/button`, `components/ui/textarea`
- `frontend/src/components/chat-window.tsx`: imports `lib/authContext`, `components/chat-header`, `components/chat-input`, `components/message-scroller`
- `frontend/src/components/layout.tsx`: imports `components/app-sidebar`, `components/ui/sidebar`
- `frontend/src/components/message-scroller.tsx`: imports none (leaf UI component)
- `frontend/src/components/ui/attachment.tsx`: imports `components/ui/button`
- `frontend/src/components/ui/field.tsx`: imports `components/ui/label`, `components/ui/separator`
- `frontend/src/components/ui/message-scroller.tsx`: imports `components/ui/button`
- `frontend/src/components/ui/sheet.tsx`: imports `components/ui/button`
- `frontend/src/components/ui/sidebar.tsx`: imports `components/ui/button`, `components/ui/input`, `components/ui/separator`, `components/ui/sheet`, `components/ui/skeleton`, `components/ui/tooltip`, `hooks/use-mobile`
- `frontend/src/components/ui/*` *(21 UI primitive files: avatar, breadcrumb, bubble, button, card, collapsible, dropdown-menu, input, label, marker, message, navigation-menu, separator, skeleton, textarea, tooltip)*: imports none / leaf UI components
- `frontend/src/hooks/use-mobile.ts`: imports none (leaf hook)
- `frontend/src/lib/authContext.tsx`: imports none (leaf context)
- `frontend/src/lib/utils.ts`: imports none (leaf utility)
- `frontend/src/main.tsx`: imports `App`, `lib/authContext`
- `frontend/src/pages/Login.tsx`: imports `components/ui/button`, `components/ui/card`, `components/ui/field`, `components/ui/input`, `lib/authContext`
- `frontend/src/pages/Profile.tsx`: imports `components/ui/button`, `components/ui/card`, `lib/authContext`
- `frontend/src/pages/Register.tsx`: imports `components/ui/button`, `components/ui/card`, `components/ui/field`, `components/ui/input`
