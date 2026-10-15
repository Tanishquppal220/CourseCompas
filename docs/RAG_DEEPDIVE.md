# Deep-Dive Technical Architecture: CourseCompass RAG & Agent Pipeline

This document provides a comprehensive technical audit of the Retrieval-Augmented Generation (RAG) system, database indexing strategies, semantic chunking pipelines, and agentic ReAct loop implemented in **CourseCompass**.

---

## 1. Embedding Model, Dimensions & pgvector Configuration

### 1.1 Embedding Model & Dimension
- **Model Name**: `BAAI/bge-small-en-v1.5`
- **Execution Library**: `sentence-transformers` via PyTorch (`SentenceTransformer(MODEL_NAME, trust_remote_code=True)`)
- **Output Vector Dimension**: `384`
- **Normalization**: `normalize_embeddings=True` (all generated vectors are $L_2$-normalized to unit sphere length)
- **Source Reference**: `backend/app/embeddings.py` (Lines 9–10) & `backend/app/models.py` (Line 20)
- *(Note on historical comment: the old `backend/scripts/ingest.py` retained a docstring reference to `Qwen3-Embedding-0.6B`, but the active codebase strictly instantiates and executes `BAAI/bge-small-en-v1.5` across all ingestion and runtime queries. The stale comment was removed when `ingest.py` became a thin CLI over `backend/scripts/ingestion/`).*

### 1.2 pgvector Schema Setup
Vector storage is defined across two primary chunking tables in PostgreSQL using SQLAlchemy's `Vector` type from `pgvector.sqlalchemy`:
1. `course_doc_chunks`: Stores chunks extracted from Course Syllabus and Instruction Plan (IP) documents.
2. `benefit_chunks`: Stores chunks extracted from the LPU EduRevolution academic benefits policy.

In `backend/app/models.py`:
```python
EMBEDDING_DIM = 384

# Shared by both chunk tables and by the Alembic migration that adds the
# column to existing databases.
FTS_EXPRESSION = (
    "to_tsvector('english', "
    "coalesce(section_title, '') || ' ' || coalesce(content, ''))"
)

class CourseDocumentChunk(Base):
    __tablename__ = "course_doc_chunks"
    ...
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    fts = Column(TSVECTOR, Computed(FTS_EXPRESSION, persisted=True))
    __table_args__ = (
        Index("ix_course_doc_chunks_fts", "fts", postgresql_using="gin"),
    )

class BenefitChunk(Base):
    __tablename__ = "benefit_chunks"
    ...
    embedding = Column(Vector(EMBEDDING_DIM), nullable=False)
    fts = Column(TSVECTOR, Computed(FTS_EXPRESSION, persisted=True))
    __table_args__ = (
        Index("ix_benefit_chunks_fts", "fts", postgresql_using="gin"),
    )
```

### 1.3 Indexing Strategy & DDL
- **Index Type**: **HNSW** (Hierarchical Navigable Small World)
- **Distance Operator**: **`vector_cosine_ops`** (calculates Cosine Distance using the `<=>` operator)
- **Database Extension**: `CREATE EXTENSION IF NOT EXISTS vector`
- **Index DDL** (defined in `backend/scripts/ingestion/database.py`):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Course document chunks HNSW vector index
CREATE INDEX IF NOT EXISTS ix_course_doc_chunks_embedding 
ON course_doc_chunks 
USING hnsw (embedding vector_cosine_ops);

-- Academic benefit chunks HNSW vector index
CREATE INDEX IF NOT EXISTS ix_benefit_chunks_embedding 
ON benefit_chunks 
USING hnsw (embedding vector_cosine_ops);
```

---

## 2. Hybrid Scoring SQL & Logic

CourseCompass combines dense vector semantic search with sparse lexical full-text search (FTS) using PostgreSQL's native `tsvector` engine and `websearch_to_tsquery`.

### 2.1 Full-Text Search Schema & GIN Index
Full-text indexing is implemented as a generated stored column that concatenates `section_title` and `content`, backed by a PostgreSQL GIN index. The expression lives once in `FTS_EXPRESSION` (`backend/app/models.py`) and is applied by the Alembic migration `backend/alembic/versions/0002_add_full_text_search.py` (via `scripts/add_fts.py` or `alembic upgrade`):

```sql
-- Course doc chunks FTS column & GIN index
ALTER TABLE course_doc_chunks 
ADD COLUMN IF NOT EXISTS fts tsvector 
GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(section_title, '') || ' ' || coalesce(content, ''))
) STORED;

CREATE INDEX IF NOT EXISTS ix_course_doc_chunks_fts 
ON course_doc_chunks 
USING GIN (fts);

-- Benefit chunks FTS column & GIN index
ALTER TABLE benefit_chunks 
ADD COLUMN IF NOT EXISTS fts tsvector 
GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(section_title, '') || ' ' || coalesce(content, ''))
) STORED;

CREATE INDEX IF NOT EXISTS ix_benefit_chunks_fts 
ON benefit_chunks 
USING GIN (fts);
```

### 2.2 Exact Hybrid Scoring SQL Formula & Query Cleaning
Implemented in `backend/app/retrieval.py`:

```python
# 1. Distill natural language query into keywords and extract course code (e.g., CSE205)
cleaned_text, detected_code = clean_query_for_fts(query_text)
tsquery = func.websearch_to_tsquery("english", cleaned_text)

# 2. Vector distance (cosine distance between query vector and chunk embedding)
distance = CourseDocumentChunk.embedding.cosine_distance(query_vector)

# 3. Hybrid score combining cosine similarity and Cover Density ts_rank (HYBRID_ALPHA = 1.2)
hybrid_score = (1.0 - distance) + (
    func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery), 0.0)
    * 1.2
)
```

Equivalent raw SQL fragment:
```sql
SELECT 
    *,
    ((1.0 - (course_doc_chunks.embedding <=> :query_vector)) + 
     (COALESCE(ts_rank_cd(course_doc_chunks.fts, websearch_to_tsquery('english', :cleaned_text)), 0.0) * 1.2)) AS score
FROM course_doc_chunks
WHERE ...
ORDER BY score DESC
LIMIT :k;
```

#### Mathematical Formulation
$$\text{HybridScore} = (1.0 - d_{\text{cosine}}) + 1.2 \times \text{ts\_rank\_cd}(\text{fts}, \text{cleaned\_tsquery})$$
- Cosine distance $d_{\text{cosine}} \in [0, 2]$. Because embeddings are unit-normalized, $(1.0 - d_{\text{cosine}})$ maps to the cosine similarity $[-1, 1]$.
- `ts_rank_cd` evaluates cover density: how close query terms appear to one another within the passage. A calibrated multiplier $\alpha = 1.2$ gives sufficient weight to exact keyword and phrase matches (e.g., assessment rubrics, course codes) without overpowering the semantic dense vector base.

### 2.3 The OR-Filter Condition (Relevance Gating)
In standard RAG systems, querying for $k$ items always returns $k$ candidates, even if all $k$ items are completely irrelevant. To eliminate this failure mode, CourseCompass applies an explicit OR-filter gate (`backend/app/retrieval.py` Line 62 & Line 100):

```python
q = q.filter(or_(distance < 0.6, CourseDocumentChunk.fts.op("@@")(tsquery)))
```

Equivalent SQL condition:
```sql
WHERE ((course_doc_chunks.embedding <=> :query_vector) < 0.6 
       OR course_doc_chunks.fts @@ websearch_to_tsquery('english', :query_text))
```

#### Why This Condition Matters:
1. **Semantic Gating**: Requires a cosine distance strictly $< 0.6$ (equivalent to cosine similarity $> 0.40$). Chunks located farther in vector space are discarded unless they have explicit keyword matches.
2. **Exact Acronym/Code Preservation**: If a user asks for an exact course code (e.g., `CSE316`) or niche policy acronym (`SCRGM`, `RPL`), dense embeddings might place them near unrelated computer science courses. The lexical branch `fts @@ tsquery` guarantees that chunks containing the exact token pass through to the candidate pool regardless of semantic distance.
3. **Suppression of Out-of-Distribution Hallucinations**: Prevents low-scoring noise from entering the reranking stage.

---

## 3. Chunking Strategy & Taxonomy

Rather than relying on arbitrary sliding token windows (e.g. `chunk_size = 500`, `chunk_overlap = 50`), CourseCompass implements **document-aware semantic and structural chunking** in `backend/scripts/ingestion/chunking/` (one module per document type).

### 3.1 Token/Character Split Sizes & Overlap
- **Sliding-window `chunk_size`**: **None / Not used**
- **Sliding-window `chunk_overlap`**: **None / Not used**
- **Chunking Philosophy**: Deterministic domain partitioning. Documents are parsed according to their structural boundaries (syllabus units, course outcomes, table rows, and policy criteria clauses).

### 3.2 Strategy Per Document Type

#### A. Syllabus PDFs (`chunk_syllabus` in `chunking/syllabus.py`)
1. **Course Overview**: Extracts course title, course code, LTP hours (`Lecture-Tutorial-Practical`), and credit distributions.
2. **Course Outcomes (COs)**: Parsed via regex `CO(\d+)\s*::\s*(.+?)(?=CO\d+\s*::|$)` into isolated outcome chunks (e.g., `CO1 :: explain the types of data...`).
3. **Unit Sections**: Triggered by Roman numeral markers `Unit\s+([IVX]+)`. Topic titles and sub-bullet bodies are parsed via `TOPIC_SPLIT_RE = ^([A-Za-z0-9 ...]{2,90}?)[:：](.+)$`.
4. **Practicals**: Extracted using regex `^\d{2}\.[^\d]` or `^•\s*\d{2}\.` into distinct lab exercise chunks.
5. **References**: Textbooks, author names, publishers, and reference links consolidated into reference chunks.

#### B. Instruction Plan (IP) PDFs (`chunk_ip` in `chunking/instruction_plan.py`)
1. **Weightage Table**: Detects evaluation matrices (`Course Weightage: ATT: 5, CA: 25, MTT: 20, ETT: 50`) and parses them into overview chunks.
2. **Textbook Tables**: Identifies tables with `[TR]-\d+` codes, mapping rows into structured references with author, title, and publisher metadata.
3. **Lecture-by-Lecture Plan**: Iterates over multi-column pedagogical tables using `classify_lecture_cells`:
   - Categorizes cells into `week`, `lecture`, `topic`, `refs`, `desc`, `outcomes`, and `pedagog` (pedagogical tools).
   - Reconstructs continuation rows and handles merged table cells.
   - Outputs a unified, self-contained chunk per lecture.
4. **LTP Week Distribution**: Extracts calendar structures and spillover lecture allocations into table row chunks.

#### C. Academic Benefits Markdown (`chunk_benefits` in `chunking/benefits.py`)
1. **Policy Overview & Eligibility**: Parses introductory text blocks and preamble definitions for each of the 8 EduRevolution benefit schemes.
2. **Criteria Rows with Bi-Directional Cell Fill**:
   - Parses markdown table rows.
   - Performs **forward and backward fill** across columns (`stipend`, `duration`, `category`, `types`, `achievement`) to resolve merged table spans.
   - Enriches each row with parent section titles and general eligibility requirements.
3. **Special Notes**: Captures footers, RMS ticket procedures, and administrative guidelines into dedicated advisory chunks.

### 3.3 Complete `chunk_type` Taxonomy
The codebase enforces an 11-member `chunk_type` taxonomy across the vector tables:

| `chunk_type` | Document Kind | Content Representation |
| :--- | :--- | :--- |
| `course_overview` | Syllabus, IP | Course metadata, code, LTP hours, credit weightages |
| `course_outcome` | Syllabus, IP | Individual course outcome statements (CO1 through CO6) |
| `unit` | Syllabus | Unit number (I–VI), unit topic name, detailed theoretical curriculum |
| `lecture` | IP | Single lecture plan: week number, lecture number, topic, readings, pedagogical tool, and outcomes |
| `practical` | Syllabus, IP | Lab exercise description and numbered practical objectives |
| `reference` | IP | Single textbook or reference book row (`T-1`, `R-1`) with author and publisher |
| `references` | Syllabus | Consolidated list of textbooks, references, and external URLs |
| `table_row` | IP | LTP week distribution, examination spillover schedules, and structural matrices |
| `policy_overview` | Benefits | Scheme overview, general eligibility rules, and preamble descriptions |
| `criteria_row` | Benefits | Tabular matrix row (e.g. stipend bracket $\times$ duration $\rightarrow$ grade benefit) |
| `special_note` | Benefits | Administrative notices, RMS ticket routes, and physical room guidelines |

---

## 4. Cross-Encoder Reranker & Candidate Rescoring

### 4.1 Reranker Model
- **Model**: **`BAAI/bge-reranker-base`**
- **Execution Class**: `sentence_transformers.CrossEncoder`
- **CPU Threading**: `torch.set_num_threads(max(1, os.cpu_count() or 1))`
- **Source Reference**: `backend/app/reranker.py` (Lines 13–20)

### 4.2 Candidate Pool Size & Rescoring Logic
In `backend/app/retrieval.py` (Line 132 & Line 201), the candidate budget before reranking is calculated as:

```python
candidate_k = max(15, k * 3) if rerank else k
```

- For the standard default user retrieval budget of $k = 5$:
  $$\text{candidate\_k} = \max(15, 5 \times 3) = 15 \text{ candidates}$$
- If $k = 10$, $\text{candidate\_k} = 30$ candidates.

### 4.3 Rescoring Workflow
1. **Candidate Retrieval**: The database runs hybrid scoring (vector cosine similarity + FTS `ts_rank_cd`) and filters via `or_(distance < 0.6, fts @@ tsquery)`. The top 15 candidate rows are returned.
2. **Cross-Encoder Scoring**:
   ```python
   pairs = [[query, doc.get("content", "")] for doc in documents]
   scores = reranker.predict(pairs)
   for doc, score in zip(documents, scores, strict=False):
       doc["rerank_score"] = round(float(score), 4)
   ```
3. **Reranking & Truncation**: Documents are re-sorted descending by `rerank_score`, and the top $k$ (default 5) are returned to the caller.
4. **Resilience Fallback**: If cross-encoder inference encounters an exception (e.g. OOM or tensor dimension error), the error is logged as a warning, and the system smoothly falls back to the initial hybrid order without failing the request (`backend/app/reranker.py` Lines 47–51).

---

## 5. LangChain Agent Toolset

The agent is equipped with 6 specialized tools registered via `@tool` in `backend/app/agent.py`.

```
                                  ┌─────────────────────────────┐
                                  │      LangChain ReAct        │
                                  │      Reasoning Agent        │
                                  └──────────────┬──────────────┘
                                                 │
         ┌──────────────────┬────────────────────┼───────────────────┬──────────────────┐
         │                  │                    │                   │                  │
         ▼                  ▼                    ▼                   ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌──────────────────────┐ ┌──────────────┐ ┌────────────────┐
│retrieve_syllabus│ │retrieve_     │ │maximize_academic_    │ │check_academic│ │auto_submit_    │
│_documents       │ │policy_       │ │benefits              │ │_eligibility  │ │academic_benefit│
│                 │ │benefits      │ │                      │ │              │ │_portal         │
└────────┬────────┘ └───────┬──────┘ └──────────┬───────────┘ └──────────────┘ └────────────────┘
         │                  │                   │
         └─────────┬────────┴───────────────────┘
                   ▼
       ┌────────────────────────┐
       │   query_curriculum_    │
       │   database (SQL)       │
       └────────────────────────┘
```

### Full Tool List & Signatures

#### 1. `retrieve_syllabus_documents`
- **Signature**:
  ```python
  retrieve_syllabus_documents(query: str, course_code: str | None = None, doc_type: str | None = None) -> str
  ```
- **One-Line Purpose**: Searches course syllabus and instruction plan (IP) chunks via hybrid search and cross-encoder reranking to return course outcomes, topics, practicals, textbook references, and exam weightages.

#### 2. `retrieve_policy_benefits`
- **Signature**:
  ```python
  retrieve_policy_benefits(query: str) -> str
  ```
- **One-Line Purpose**: Searches the university's Academic Benefits policy database via hybrid search and reranking to retrieve eligibility rules, criteria rows, and procedures across all 8 EduRevolution benefit pathways.

#### 3. `query_curriculum_database`
- **Signature**:
  ```python
  query_curriculum_database(sql_query: str) -> str
  ```
- **One-Line Purpose**: Executes read-only SQL queries (`SELECT` / `WITH`) against relational PostgreSQL curriculum schema tables (`terms`, `courses`, `term_slots`, `elective_baskets`) to answer structural program inquiries.

#### 4. `maximize_academic_benefits`
- **Signature**:
  ```python
  maximize_academic_benefits(achievements: str, courses: str) -> str
  ```
- **One-Line Purpose**: Retrieves relevant policy criteria and applies LPU stacking rules (1 benefit per course, attendance bonus stacking, credit prioritization) to optimize a student's SGPA across semester courses.

#### 5. `check_academic_eligibility`
- **Signature**:
  ```python
  check_academic_eligibility(benefit_type: str, cgpa: float) -> str
  ```
- **One-Line Purpose**: Evaluates a student's quantitative CGPA eligibility against hardcoded threshold rules for attendance benefits ($\ge 7.5$), internships ($\ge 6.0$), or research/RPL (no minimum).

#### 6. `auto_submit_academic_benefit_portal`
- **Signature**:
  ```python
  auto_submit_academic_benefit_portal(category: str, course_code: str, achievement_summary: str, student_name: str | None = None, student_reg_no: str | None = None, target_portal_url: str | None = None) -> str
  ```
- **One-Line Purpose**: Executes a resilient Playwright browser automation agent with Cloudflare/CAPTCHA detection, heuristic form filling, and human-in-the-loop escalation to submit benefit nominations on the university portal.

---

## 6. ReAct Loop & Agent Architecture

### 6.1 Agent Construction & Engine
- **Framework**: Modern LangChain Agent API via `langchain.agents.create_agent`
- **Foundational LLM**: AWS Bedrock Converse API executing `bedrock_converse:openai.gpt-oss-120b-1:0` (`backend/app/llm.py` Line 10)
- **Agent Type**: Tool-calling ReAct (Reasoning + Acting) loop that evaluates student queries, formulates intermediate tool-call arguments, consumes structured tool outputs, and iterates until emitting the final user-facing response.

### 6.2 Conversational Memory Architecture
- **State Persistence**: Conversational state is externalized and backed by PostgreSQL tables `chat_sessions` and `chat_messages` (`backend/app/models.py` Lines 36–51).
- **Message Reconstruction**: On each turn, previous dialogue history is loaded from the database and mapped into LangChain message objects:
  ```python
  messages = [SystemMessage(content=dynamic_system_ctx)]
  if chat_history:
      for msg in chat_history:
          if msg.get("role") == "user":
              messages.append(HumanMessage(content=msg.get("content", "")))
          else:
              messages.append(AIMessage(content=msg.get("content", "")))
  messages.append(HumanMessage(content=query))
  ```
- **Execution**: The compiled graph agent is invoked statelessly with `agent.invoke({"messages": messages})`.

### 6.3 Dual-Layer System Prompt Design

The agent's behavior is guided by two layered system prompts:

#### 1. Foundation Static Prompt (`backend/app/llm.py` Lines 12–120)
- **Role Persona**: CourseCompass, dedicated AI Academic Advisor for Lovely Professional University (LPU).
- **Domain Policies**: Relative grading system, 75% attendance rule, Week-1 Double Attendance incentive, and course-specific Continuous Assessment (CA) rules.
- **5 Pillars of EduRevolution**: Beyond the Classroom (Duty Leave), Research & Innovation (Grade Upgradation for Scopus papers/patents), Real-World Revenue (SCRGM), Startups & Incubation, Industry Certifications/RPL.
- **Document Routing Rules**: Explicitly instructs when to query "Syllabus" (course outcomes, unit topics) vs "IP" (marks distribution, exam weightages, weekly schedules).
- **Consultative Advisor Protocol**: Strict mandate to never assume missing parameters or dump raw policy tables. Enforces asking 2–4 targeted, numbered clarifying questions (e.g. stipend, duration, proctoring status) before rendering verdicts.
- **Benefit Stacking Rules**: Enforces exactly 1 mapped benefit per course, prioritizes 3–4 credit courses, and stacks the 10% Attendance Benefit universally if CGPA $\ge 7.5$.
- **Official Workflow Guidance**: 4-step UMS submission procedure, physical assistance office (Block 38 - Room 205B), and RMS ticket paths.

#### 2. Per-Turn Dynamic Context (`backend/app/agent.py` Lines 344–361)
Injected dynamically at the head of every session turn using the authenticated student's database profile:
```python
system_ctx = (
    f"You are advising an LPU student (Reg No: {profile.get('registration_number', 'Guest')}).\n"
    f"Current Term: {profile.get('current_term', 'N/A')} | "
    f"Program: {profile.get('program_name', 'B.Tech CSE')} | "
    f"CGPA: {profile.get('current_cgpa', 'N/A')}\n\n"
    "Proactively check this student's CGPA against LPU thresholds when they ask about:\n"
    "- 10% Attendance Benefit: requires CGPA >= 7.5 and >= 60% raw attendance.\n"
    "- Internship course integration: standard requirement CGPA >= 6.0.\n"
    "- NPTEL Full Equivalence: requires CGPA >= 7.0.\n"
    "- RPL & Grade Upgradation: NO minimum CGPA required.\n\n"
    "CRITICAL INSTRUCTION: In LPU terminology, 'IP' stands for 'Instruction Plan' (course delivery plan "
    "and marks scheme). It NEVER refers to internet IP addresses.\n\n"
    "CONVERSATIONAL ADVISING GUIDELINE:\n"
    "If the student's inquiry about a project, course, or internship lacks key details ... "
    "Politely ask 2-4 numbered clarifying questions first to gather the exact facts."
)
```

### 6.4 Output Sanitization & Citation Extraction
Before responses reach the client, `backend/app/agent.py` executes post-processing:
1. **Reasoning Block Stripping**: Filters out `reasoning_content` dictionaries and regex-strips `<think>...</think>` or `<reasoning>...</reasoning>` blocks generated by thinking models.
2. **Source Citation Extraction**: Scans intermediate tool execution messages for lines containing `Source:` and compiles an explicit, deduplicated list of source citations returned alongside the response payload.

---

## 7. Interview Talking Points

Here are 5 high-yield talking points connecting CourseCompass's implementation to standard RAG architecture interview questions:

1. **Chunking Trade-offs: Semantic/Structural Partitioning vs Sliding Token Windows**
   * *Interview Question*: *"How do you decide on chunk size and overlap for complex enterprise documents?"*
   * *Talking Point*: Sliding-window token splitting (e.g. 512 tokens with 50-token overlap) causes high semantic fragmentation in tabular, hierarchical documents. In CourseCompass, an instruction plan table or a syllabus unit split arbitrarily across a token boundary cuts off lecture outcomes from their pedagogical tools or breaks evaluation matrices. CourseCompass opts for **document-aware structural chunking**: using pymupdf4llm layout analysis and regex state machines to parse complete syllabus units, isolated course outcomes (`CO1..CO6`), and tabular criteria rows with bi-directional cell filling. The trade-off is higher upfront parser complexity in exchange for atomic, self-contained chunks that preserve 100% of tabular relationships without needing arbitrary overlap redundancy.

2. **Why Dense Vector Search Fails Alone: The Critical Value of Hybrid Search & OR-Gating**
   * *Interview Question*: *"Why isn't dense vector similarity search sufficient on its own, and how do you implement hybrid retrieval?"*
   * *Talking Point*: Pure dense embedding models compress documents into continuous semantic vectors, which frequently struggle with out-of-vocabulary course codes (`CSE316` vs `CSE320`), acronyms (`SCRGM`, `RPL`), or exact policy titles. CourseCompass implements hybrid retrieval in PostgreSQL by fusing pgvector cosine distance (`1.0 - distance`) with PostgreSQL's native cover density ranking (`ts_rank_cd(fts, tsquery) * 0.5`). Crucially, CourseCompass introduces an **OR-filter gate** (`distance < 0.6 OR fts @@ tsquery`). In standard vector retrieval, forcing a database to return top-$k$ candidates on an out-of-domain query returns the $k$ least-bad, completely irrelevant documents, leading to hallucination. The OR-gate acts as an relevance firewall: only documents with strong semantic proximity ($d < 0.6$) or exact keyword hits enter the candidate pool.

3. **Two-Stage Retrieval: Bi-Encoder Scalability vs Cross-Encoder Precision**
   * *Interview Question*: *"Why use a reranker instead of just retrieving the top chunks directly with your embedding model?"*
   * *Talking Point*: Bi-encoders (`bge-small-en-v1.5`) encode queries and passages independently, enabling fast Approximate Nearest Neighbor (ANN) search over millions of chunks via HNSW indexes. However, because query and document tokens never interact during encoding, bi-encoders miss subtle semantic interactions. CourseCompass adopts a **two-stage retrieval pipeline**: the bi-encoder + FTS stage casts a wider net to retrieve $\max(15, 3k)$ candidates, which are then passed to a cross-encoder (`BAAI/bge-reranker-base`). The cross-encoder performs full cross-attention over `[query, passage]` token pairs, re-scoring candidates with true interaction modeling. This achieves near-zero latency degradation ($< 40\text{ms}$ for 15 candidates on CPU) while significantly increasing Hit Rate @ 5 and Mean Reciprocal Rank (MRR).

4. **Grounding & Anti-Hallucination: Persona Constraints & Clarifying Interview Protocols**
   * *Interview Question*: *"How do you prevent an LLM agent from making up university policies or guessing student eligibility when facts are missing?"*
   * *Talking Point*: Guarding against hallucination requires architecture, not just system prompts. CourseCompass uses a three-tier grounding strategy:
     1. **Dynamic Per-Turn Context Injection**: The authenticated student's profile (CGPA, Term, Program) is injected directly from the relational database into the system prompt, preventing the LLM from hallucinating or asking the user for their own CGPA.
     2. **Consultative Cross-Examination Protocol**: The prompt explicitly forbids the agent from guessing missing parameters (e.g. stipend, duration, or whether an exam was proctored). If parameters are missing, the agent is constrained to ask 2–4 numbered clarifying questions before rendering an eligibility verdict.
     3. **Deterministic Tooling for Math & Rules**: Rather than letting the LLM calculate eligibility thresholds or solve multi-course benefit allocations, dedicated tools (`check_academic_eligibility` and `maximize_academic_benefits`) enforce hardcoded deterministic logic and university constraints (e.g., maximum 1 benefit per course).

5. **Retrieval Evaluation in Production: Moving Beyond Naive Benchmarks to Ragas**
   * *Interview Question*: *"How would you quantitatively evaluate and benchmark this RAG pipeline?"*
   * *Talking Point*: Evaluating a production RAG system requires decomposing the pipeline into two distinct components: **Retrieval Evaluation** and **Generation Evaluation** (using frameworks like Ragas or TruLens):
     - **Retrieval Metrics**:
       - *Context Precision / Hit Rate @ K*: Measures whether the cross-encoder placed the correct syllabus unit or benefit row within the top 5 chunks.
       - *Context Recall*: Measures whether the semantic chunker captured all prerequisite topics and evaluation criteria needed to answer the question.
     - **Generation Metrics**:
       - *Faithfulness / Groundedness*: Verifies that every assertion made by `gpt-oss-120b` is mathematically and factually supported by the retrieved chunk content, penalizing ungrounded claims.
       - *Answer Relevance*: Ensures the agent directly answers the student's specific academic dilemma without dumping irrelevant policy sections.
     - *Regression Testing*: Golden chunk-signature diffs of the ingestion chunkers (chunk content must stay byte-identical across refactors before a `--force-rebuild` re-ingest) and golden Q&A dataset regression runs ensure that prompt modifications, chunking changes, or embedding model upgrades do not degrade retrieval recall on edge-case course codes.
