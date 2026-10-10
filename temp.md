Yes — the project already supports this cleanly. The connection string is resolved in `backend/app/database.py`:

```python
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("LOCAL_DATABASE_URL")
```

with `load_dotenv()` reading a `backend/.env` file (`.env` is gitignored). So:

**1. Run a local Postgres with pgvector**
This project needs the `vector` extension (embeddings are `vector(384)` + HNSW indexes). On Linux e.g.:

```bash
apt install postgresql-16-pgvector   # or postgresql-<ver>-pgvector
systemctl start postgresql
sudo -u postgres createdb coursecompass
```

**2. Point the app at it in `backend/.env`**

```bash
# backend/.env
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/coursecompass
```

- `DATABASE_URL` **wins** over `LOCAL_DATABASE_URL`, so this overrides whatever hosted DB the `.env` currently points at. Use the SQLAlchemy drive prefix the project pins in `backend/pyproject.toml` (likely psycopg2 or psycopg) — adjust user/pass/dbname to your local setup.
- If you'd rather keep the hosted `DATABASE_URL` around, set only `LOCAL_DATABASE_URL` instead... but note `DATABASE_URL` takes precedence, so if it's already set in `.env` you must change that value.

**3. Bootstrap the schema (automatic or manual)**

```bash
cd backend
uv run alembic current                      # check current revision
uv run python scripts/ingest.py --benefits-only   # runs upgrade_schema() on first ingest
```

`upgrade_schema()` (in `app/database.py`) creates the `vector` extension, the ORM tables, and applies Alembic migrations to head (`0003`) — every ingest and seed run does this automatically. You can also do it explicitly:

```bash
uv run alembic upgrade head
```

**4. Load data**

```bash
uv run python scripts/seed.py              # curriculum (terms, courses, baskets)
uv run python scripts/ingest.py            # PDF chunks + benefits (or --force-rebuild)
```

Then verify with `uv run alembic current` → `0003_page_number_nullable` and a quick `psql -c '\dt'`.

One caveat: the current `.env` points at a remote/dev Postgres (that's the DB my verification runs wrote to). As soon as you switch `DATABASE_URL` to local, ingest/seed will operate on the local DB instead — schema, chunks, and curriculum all included, no other config needed.


## Output
uv run python scripts/ingest.py --force --workers 2
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_baseline, Baseline: schema as it existed before Alembic was adopted.
INFO  [alembic.runtime.migration] Running upgrade 0001_baseline -> 0002_add_full_text_search, Add full-text search (generated tsvector + GIN) to the chunk tables.
INFO  [alembic.runtime.migration] Running upgrade 0002_add_full_text_search -> 0003_page_number_nullable, Make chunk page_number nullable.
targeting 38 courses; 74 doc(s) need work
  parsing 74 docs across 2 processes
rapidocr_api using backend: rapidocr

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
Loading weights: 100%|████████████████████████████████████████████████████████████| 199/199 [00:00<00:00, 13215.74it/s]
/home/tanishq/Projects/CourseCompass/backend/app/embeddings.py:24: FutureWarning: The `get_sentence_embedding_dimension` method has been renamed to `get_embedding_dimension`.
  model_dim = embedder.get_sentence_embedding_dimension()
  CHE110 Syllabus: 1 chunks in 9s
rapidocr_api using backend: rapidocr

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CHE110 IP: 56 chunks in 4s
  CSE101 Syllabus: 19 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE101 IP: 65 chunks in 6s
  CSE111 Syllabus: 9 chunks in 4s
  CSE111 IP: 40 chunks in 5s
  CSE121 Syllabus: 8 chunks in 5s
/home/tanishq/Projects/CourseCompass/backend/.venv/lib/python3.13/site-packages/pymupdf4llm/ocr/compute_ocr_features.py:236: RuntimeWarning: Mean of empty slice
  fft_ratio = magnitude[magnitude > magnitude.mean()].mean() / (
/home/tanishq/Projects/CourseCompass/backend/.venv/lib/python3.13/site-packages/numpy/_core/_methods.py:142: RuntimeWarning: invalid value encountered in scalar divide
  ret = ret.dtype.type(ret / rcount)
The text detection result is empty

=== Document parser messages ===
Using RapidOCR for OCR processing.
The text detection result is empty

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE121 IP: 49 chunks in 4s
  CSE202 Syllabus: 22 chunks in 3s
The text detection result is empty
The text detection result is empty
The text detection result is empty

=== Document parser messages ===
Using RapidOCR for OCR processing.
The text detection result is empty

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
OCR on page.number=1/2.
OCR on page.number=5/6.
OCR on page.number=6/7.
OCR on page.number=8/9.
OCR on page.number=11/12.
OCR on page.number=13/14.

=== Document parser messages ===
Using RapidOCR for OCR processing.
OCR on page.number=1/2.
OCR on page.number=5/6.
OCR on page.number=6/7.
OCR on page.number=8/9.
OCR on page.number=11/12.
OCR on page.number=13/14.
  CSE202 IP: 57 chunks in 5s
  CSE205 Syllabus: 36 chunks in 4s
  CSE205 IP: 60 chunks in 4s
  CSE211 Syllabus: 7 chunks in 4s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE211 IP: 57 chunks in 4s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE273 Syllabus: 24 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE273 IP: 41 chunks in 5s
  CSE274 Syllabus: 3 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE274 IP: 41 chunks in 3s
  CSE306 Syllabus: 18 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE306 IP: 64 chunks in 9s
  CSE307 Syllabus: 8 chunks in 3s
  CSE307 IP: 6 chunks in 2s
  CSE310 Syllabus: 32 chunks in 7s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE310 IP: 54 chunks in 5s
  CSE316 Syllabus: 9 chunks in 5s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE316 IP: 58 chunks in 5s
  CSE320 Syllabus: 9 chunks in 4s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE320 IP: 57 chunks in 5s
  CSE325 Syllabus: 8 chunks in 3s
  CSE325 IP: 6 chunks in 3s
  CSE326 Syllabus: 8 chunks in 4s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE326 IP: 49 chunks in 4s
  CSE329 Syllabus: 26 chunks in 8s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE329 IP: 35 chunks in 4s
  CSE330 Syllabus: 31 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE330 IP: 40 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE408 Syllabus: 32 chunks in 4s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE408 IP: 59 chunks in 5s
  CSE443 IP: no chunks, skipped
  CSE471 Syllabus: 24 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE471 IP: 39 chunks in 3s
  CSE472 Syllabus: 25 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  CSE472 IP: 51 chunks in 5s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  ECE249 Syllabus: 14 chunks in 3s
  ECE249 IP: 53 chunks in 3s
  ECE279 Syllabus: 8 chunks in 3s
  ECE279 IP: 6 chunks in 3s
  GEN231 IP: no chunks, skipped
  INT108 Syllabus: 28 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  INT108 IP: 66 chunks in 6s
  INT306 Syllabus: 94 chunks in 8s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  INT306 IP: 89 chunks in 11s
  INT373 Syllabus: 28 chunks in 3s
  INT373 IP: 43 chunks in 4s
  INT428 Syllabus: 25 chunks in 4s
  INT428 IP: 66 chunks in 6s
  MEC136 Syllabus: 9 chunks in 4s
  MEC136 IP: 46 chunks in 3s
  MTH174 Syllabus: 1 chunks in 1s
  MTH174 IP: 52 chunks in 5s
  MTH302 Syllabus: 7 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  MTH302 IP: 62 chunks in 5s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  MTH401 Syllabus: 10 chunks in 3s
  MTH401 IP: 54 chunks in 4s
  PEA307 Syllabus: 20 chunks in 3s
  PEA307 IP: 43 chunks in 3s
  PEL125 Syllabus: 30 chunks in 4s

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.

=== Document parser messages ===
Using RapidOCR for OCR processing.
  PEL125 IP: 1 chunks in 2s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  PEL134 Syllabus: 8 chunks in 4s
  PEL134 IP: 17 chunks in 3s
  PES318 Syllabus: 9 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  PES318 IP: 24 chunks in 4s
  PHY110 Syllabus: 6 chunks in 3s

=== Document parser messages ===
Using RapidOCR for OCR processing.
  PHY110 IP: 56 chunks in 2s
  benefits: already present, skipping
  hnsw index ready on course_doc_chunks
  hnsw index ready on benefit_chunks
course_doc_chunks: total rows = 2318
benefit_chunks: total rows = 110
total time: 846s
                       