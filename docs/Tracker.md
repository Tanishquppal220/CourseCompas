# RAG-Based Programme Personalization Chatbot

## Living Project Tracker

> **Purpose:** This document is the persistent project context and implementation tracker.
> After completing any feature, the coding agent must update the relevant status, implementation notes, decisions, files/components changed, and next steps.

---

# 1. Project Overview

The project is a **RAG-based Programme Personalization Chatbot**.

The chatbot combines:

* Structured academic programme data
* PostgreSQL relational queries
* RAG-based document retrieval
* pgvector embeddings
* Natural language interaction
* Programme benefit information
* Future personalized achievement and benefit evaluation

The system should answer questions about:

* Courses
* Programme curriculum
* Terms
* Prerequisites
* Electives
* Programme documentation
* Benefits
* External achievements such as NPTEL

---

# 2. Current Architecture

## Backend

**FastAPI**

Responsibilities:

* API endpoints
* Chat requests
* RAG orchestration
* Database interaction
* Retrieval pipeline
* Future tool execution

## Relational Database

**PostgreSQL**

Used for structured programme information.

## Vector Search

**pgvector**

Used for:

* Document embeddings
* Semantic search
* Retrieval of relevant textual content

---

# 3. Core Design Principle

The system uses two different data approaches.

## Structured Data → PostgreSQL

Use PostgreSQL for data requiring:

* Exact matching
* Filtering
* Joins
* Numeric values
* Relationships
* Prerequisites
* Curriculum structure

## Textual Knowledge → RAG + Embeddings

Use embeddings for:

* Programme documentation
* Benefits documentation
* Syllabus text
* Explanatory content
* Policies
* FAQs
* Other highly textual information

---

# 4. Current Programme Database Schema

## Status: IMPLEMENTED / DATA ADDED

### Programs

```text
ProgramID
ProgramCode
ProgramName
AdmissionYear
DurationYears
```

### Courses

```text
CourseCode
CourseTitle
L
T
P
Credit
ContactHours
CourseType
CourseNature
```

### Terms

```text
TermID
ProgramID
TermNumber
TermPath
```

### Term_Curriculum

```text
CurriculumID
TermID
CourseCode
PlaceholderName
```

### Elective_Baskets

```text
BasketID
BasketName
CourseCode
ElectiveArea
```

### Course_Prerequisites

```text
CourseCode
PrereqCode
```

---

# 5. Database Relationships

```text
Programs
   │
   └── Terms
         │
         └── Term_Curriculum
                  │
                  └── Courses
                         │
                         ├── Course_Prerequisites
                         │
                         └── Elective_Baskets
```

---

# 6. Implementation Status

| Component                | Status                | Notes                                              |
| ------------------------ | --------------------- | -------------------------------------------------- |
| FastAPI project          | Completed             | API endpoints, test client & dependency setup     |
| PostgreSQL               | Completed             | Docker container coursecompass_db running locally  |
| pgvector                 | Completed             | Extension active & HNSW vector index created       |
| Programme schema design  | Completed             | Relational schema defined                          |
| Programme data ingestion | Completed             | All tables populated (250 courses, 287 basket rows)|
| Course database          | Completed             | Programme course data stored                       |
| RAG pipeline             | In Progress           | Retrieval service & vector search functional       |
| Benefits ingestion       | Completed             | 128 chunks extracted, embedded & stored            |
| Benefits embeddings      | Completed             | sentence-transformers/all-MiniLM-L6-v2 (384 dim)   |
| Benefit rule engine      | Future Update         | Deferred                                           |
| Achievement evaluation   | Future Update         | Depends on rule engine                             |
| External achievements    | Future Update         | NPTEL and similar sources                          |


---

# 7. Completed Features

## Feature 1: Programme Schema Database

### Status

**Completed**

### Description

The academic programme structure has been modeled as relational PostgreSQL data.

### Includes

* Programme information
* Courses
* Terms
* Term curriculum
* Elective baskets
* Course prerequisites

### Expected Capabilities

The database should support exact queries such as:

* What courses are in a particular term?
* What are the prerequisites of a course?
* How many credits does a course have?
* Which courses belong to an elective basket?
* What courses belong to a programme?

### Coding Agent Update Requirement

When modifying this feature, update:

```text
Status:
Database migrations changed:
Tables changed:
Data ingestion changes:
Validation completed:
Known issues:
```

---

# 8. Current Feature: Benefits Knowledge Base

## Status

**COMPLETED**


### Initial Approach

Benefits information will initially be treated as highly textual content.

The initial implementation will:

```text
Benefits Documents
        ↓
Document Extraction
        ↓
Chunking
        ↓
Embedding Generation
        ↓
pgvector Storage
        ↓
Semantic Retrieval
        ↓
LLM Response
```

### Example Questions

* What benefits are available?
* Explain this benefit.
* What benefits are associated with this programme?
* What does this achievement benefit mean?
* Tell me about available achievement benefits.

### Important Decision

For the current version:

> **Benefits will primarily be handled through RAG embeddings.**

Structured extraction of complex benefit rules is deferred to a future update.

---

# 9. RAG Pipeline

## Status

**NOT STARTED**

### Target Flow

```text
User Question
      ↓
Query Processing
      ↓
Determine Query Type
      ↓
────────────────────────────
│                          │
Structured Query       Textual Query
│                          │
PostgreSQL             Vector Search
│                          │
Exact Data             Relevant Chunks
│                          │
────────────────────────────
           ↓
          LLM
           ↓
    Final Response
```

---

# 10. Feature: Course Information Retrieval

## Status

**PLANNED**

### Data Sources

* PostgreSQL `Courses`
* Course prerequisites
* Term curriculum
* Future syllabus documents
* Future course embeddings

### Example Questions

* Tell me about course X.
* What are the prerequisites?
* Which term contains this course?
* What is the credit structure?
* Which courses are related to this course?

### Implementation Requirements

* SQL lookup for structured facts
* RAG retrieval for detailed textual explanations
* Combine results when necessary

---

# 11. Feature: Benefits RAG

## Status

**NEXT**

### Objective

Allow users to ask natural-language questions about programme benefits.

### Initial Architecture

```text
Benefits Source
      ↓
Text Extraction
      ↓
Chunking
      ↓
Embeddings
      ↓
pgvector
      ↓
Similarity Search
      ↓
Relevant Context
      ↓
LLM Answer
```

### Acceptance Criteria

* Benefits documents can be ingested.
* Documents are chunked successfully.
* Embeddings are generated.
* Embeddings are stored in pgvector.
* Relevant chunks can be retrieved.
* Chatbot responses use retrieved context.

---

# 12. Future Feature: Structured Benefit Rules

## Status

**FUTURE UPDATE — NOT CURRENTLY IMPLEMENTED**

This feature will be implemented when deterministic benefit evaluation becomes necessary.

### Future Flow

```text
Achievement
      ↓
Identify Category
      ↓
Evaluate Rules
      ↓
Determine Tier
      ↓
Determine Benefit
      ↓
Map Benefit to Course
      ↓
Personalized Response
```

### Possible Future Tables

```text
benefit_rules
benefits
achievement_types
benefit_course_mapping
```

### Reason for Deferral

The current priority is to establish the RAG pipeline and ingest highly textual benefits documentation first.

Structured rule extraction will be added later if requirements include:

* Numeric thresholds
* Score evaluation
* Rank evaluation
* Tier determination
* Exact eligibility decisions

---

# 13. Future Feature: Feature F

## Status

**FUTURE UPDATE**

### Objective

Map:

```text
Achievement
→ Benefit
→ Potential Tier
→ Course Mapping
```

The exact architecture will be finalized when the benefit rule system is implemented.

---

# 14. Future Feature: External Achievements

## Status

**FUTURE UPDATE**

Examples:

* NPTEL courses
* External certifications
* Other recognized achievements

### Requirements

External content may need:

* Separate sourcing
* Separate ingestion
* Metadata tracking
* Future benefit mapping

---

# 15. Development Roadmap

## Phase 1 — Foundation
 
### Status: Completed
 
* [x] Define project architecture
* [x] Design Programme Schema
* [x] Create PostgreSQL structure
* [x] Add Programme Schema data
* [x] Complete backend infrastructure validation (Docker coursecompass_db)
* [x] Confirm pgvector configuration
 
---
 
## Phase 2 — Benefits Knowledge Ingestion
 
### Status: Completed
 
* [x] Identify benefits source documents (Academic Benefits.pdf)
* [x] Extract textual content & tabular rules (12 pages)
* [x] Clean documents & contextual chunking (128 chunks)
* [x] Define chunking strategy (Policy conditions + tabular criteria)
* [x] Generate embeddings (all-MiniLM-L6-v2, 384 dimensions)
* [x] Store embeddings in pgvector (benefit_chunks table + HNSW index)
* [x] Add metadata (sections, page numbers, row fields)
* [x] Test semantic retrieval (Validated via pgvector cosine similarity)
 
---
 
## Phase 3 — RAG Chatbot
 
### Status: In Progress
 
* [x] Create retrieval service (`app.services.retrieval.search_benefits`)
* [x] Implement similarity search (`<=>` cosine distance with HNSW)
* [x] Retrieve relevant chunks (`GET /api/benefits/search`)
* [ ] Pass context to LLM
* [ ] Generate grounded responses
* [ ] Add source attribution
* [ ] Test hallucination resistance


---

## Phase 4 — Hybrid Query System

### Status: NOT STARTED

Implement query routing.

```text
User Query
     ↓
Query Classification
     │
     ├── Structured → PostgreSQL
     │
     ├── Textual → RAG
     │
     └── Hybrid → PostgreSQL + RAG
```

---

## Phase 5 — Benefit Rules

### Status: FUTURE

* [ ] Analyze benefit rule matrix
* [ ] Extract deterministic rules
* [ ] Design `benefit_rules`
* [ ] Implement strict rule lookup
* [ ] Test threshold evaluation

---

## Phase 6 — Personalization

### Status: FUTURE

* [ ] Achievement processing
* [ ] Benefit eligibility
* [ ] Tier evaluation
* [ ] Benefit mapping
* [ ] Course mapping
* [ ] Personalized responses

---

## Phase 7 — External Achievements

### Status: FUTURE

* [ ] Identify external sources
* [ ] NPTEL integration strategy
* [ ] External content ingestion
* [ ] Achievement metadata
* [ ] Benefit integration

---

# 16. Current Priority

## Immediate Next Task

> **Build the benefits ingestion and RAG pipeline.**

Recommended implementation order:

```text
1. Obtain benefits documents
2. Extract text
3. Clean and normalize content
4. Create chunks
5. Generate embeddings
6. Store in pgvector
7. Implement similarity search
8. Test retrieval
9. Connect retrieval to chatbot
```

---

# 17. Coding Agent Update Protocol

After completing any feature or task, the coding agent must update this tracker using the following format.

## Feature Update Template

```text
### Feature:
<Name>

### Status:
Not Started / In Progress / Completed / Blocked

### Date Updated:
<date>

### What Was Implemented:
- Item 1
- Item 2

### Files Added:
- path/file.py

### Files Modified:
- path/file.py

### Database Changes:
- Migration details
- Tables added or modified

### API Changes:
- Endpoint details

### Tests:
- Tests added
- Results

### Known Issues:
- Issue 1

### Important Technical Decisions:
- Decision and reasoning

### Next Step:
- Next implementation task
```

---

# 18. Agent Rules

The coding agent should:

1. Read this tracker before starting work.
2. Identify the current priority.
3. Update the tracker after implementation.
4. Never mark a feature as completed without verification.
5. Record important architectural decisions.
6. Record database changes.
7. Record new dependencies.
8. Record known bugs or limitations.
9. Update the roadmap when priorities change.
10. Preserve previous implementation history.

---

# 19. Current Project State Snapshot

```text
PROJECT:
RAG-Based Programme Personalization Chatbot

CURRENT DATABASE:
PostgreSQL 16 in Docker (coursecompass_db) with pgvector active

PROGRAMME DATA:
Added (250 courses, 10 terms, 60 curriculum entries, 287 basket mappings)

CURRENT STRUCTURED DATA:
- Programs
- Courses
- Terms
- Term_Curriculum
- Elective_Baskets
- Course_Prerequisites

BENEFITS DATA SOURCE:
Academic Benefits.pdf (12 pages, 128 chunks embedded and stored in pgvector)

RETRIEVAL SYSTEM:
HNSW cosine similarity search implemented and tested via FastAPI endpoint (/api/benefits/search)

NEXT IMPLEMENTATION:
Connect retrieved context to LLM response generator (Chatbot / RAG answer synthesis)

CURRENT PRIORITY:
Build LLM response orchestration for student questions
```

---

# 20. Persistent Context Summary

The system has completed **Phase 1 (Relational Programme Foundation)** and **Phase 2 (Academic Benefits Ingestion & Semantic Vector Retrieval)**.

Local PostgreSQL with `pgvector` contains both structured degree data and 128 vectorized chunks from `Academic Benefits.pdf`. The semantic retrieval engine is tested and exposes `/api/benefits/search`.

The next development milestone is:

> **Phase 3 (RAG Chatbot): Connect user queries and retrieved context to an LLM to generate natural, grounded responses with source attribution.**

---

# 21. Completed Feature Logs

### Feature:
Academic Benefits Knowledge Base & Semantic Retrieval (Phase 2 & Phase 3 Retrieval)

### Status:
Completed

### Date Updated:
2026-09-03

### What Was Implemented:
- Ingestion pipeline extracting both policy conditions and tabular criteria from `Academic Benefits.pdf` (12 pages).
- Local embedding generation using Hugging Face `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors).
- Local PostgreSQL table `benefit_chunks` with `pgvector` type and HNSW cosine index (`vector_cosine_ops`).
- Semantic search module `backend/app/services/retrieval.py` performing vector distance search (`<=>`).
- FastAPI endpoint `GET /api/benefits/search` with filtering support.

### Files Added:
- `backend/scripts/ingest_benefits.py`
- `backend/app/services/retrieval.py`

### Files Modified:
- `backend/app/models.py` (added `BenefitChunk` model)
- `backend/app/database.py` (added dotenv support)
- `backend/app/main.py` (added search endpoint and dependency injection)
- `backend/.env` (configured local Docker PostgreSQL connection)
- `backend/pyproject.toml` (added `sentence-transformers`, `python-dotenv`)
- `Tracker.md` (updated status and roadmap)

### Database Changes:
- Enabled `vector` extension in PostgreSQL `coursecompass` database.
- Created `benefit_chunks` table with columns: `id`, `document_name`, `section_title`, `page_number`, `chunk_type`, `content`, `metadata`, `embedding`.
- Created HNSW index `idx_benefit_chunks_embedding_hnsw` on `benefit_chunks(embedding vector_cosine_ops)`.
- Ingested 128 chunks.

### API Changes:
- `GET /api/benefits/search?query=...&limit=5&section=...`: Returns top-k matching chunks with similarity scores, page numbers, and section references.

### Tests:
- Tested queries: 10% Attendance Benefit, Duty Leave rules, NPTEL course equivalence, Grade Upgradation requirements.
- Tested via FastAPI `TestClient` — returned 200 OK with correct relevant policy chunks.

### Important Technical Decisions:
- Selected lightweight local embedding model `all-MiniLM-L6-v2` running on CPU: fast execution (<2s for full PDF ingestion, <15ms per search query) without external API costs or rate limits.
- Extracted both general rules and structured table rows as distinct chunks to preserve exact eligibility criteria.

### Next Step:
- Phase 3 LLM Generation: Integrate LLM generation (e.g. Gemini / Ollama / OpenAI) with retrieved context to synthesize natural conversational answers.

