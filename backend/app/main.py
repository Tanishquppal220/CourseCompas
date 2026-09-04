from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import re

from .database import SessionLocal
from .llm import generate_chat_response
from .retrieval import search_documents

## CORS Middleware add

COURSE_CODE_RE = re.compile(r"(?i)\b([A-Z]{3}\d{3})\b")
SYLLABUS_SIGNALS = ("syllabus", "course outcomes", "unit", "textbook", "reference", "credit")
IP_SIGNALS = (
    "week",
    "lecture",
    "tutorial",
    "practical",
    "evaluation",
    "scheme",
    "exam",
    "session plan",
    "readings",
    "spill over",
    "mid term",
    "end term",
)


def detect_course_intent(query: str):
    match = COURSE_CODE_RE.search(query)
    course_code = match.group(1).upper() if match else None
    lowered = query.lower()

    has_syllabus_signal = any(s in lowered for s in SYLLABUS_SIGNALS)
    has_ip_signal = any(s in lowered for s in IP_SIGNALS)

    if has_syllabus_signal and not has_ip_signal:
        prefer_doc_type = "Syllabus"
    elif has_ip_signal and not has_syllabus_signal:
        prefer_doc_type = "IP"
    else:
        prefer_doc_type = None

    return course_code, prefer_doc_type


def build_grounded_prompt(results, question: str) -> str:
    context = "\n\n---\n\n".join(
        f"Source: {r['source']}\n{r['content']}" for r in results
    )
    return (
        "Answer the user's question using ONLY the following document excerpts. "
        "If the answer is not in the excerpts, say you could not find it. "
        "Do not invent information.\n\n"
        f"=== DOCUMENTS ===\n{context}\n\n"
        f"=== QUESTION ===\n{question}"
    )


class ChatRequest(BaseModel):
    messages: list


class RagQuery(BaseModel):
    query: str
    k: int = 5
    course_code: str | None = None

app = FastAPI(
    title="CourseCompass API",
    description="Academic Programme Personalization & Benefits RAG API",
    version="0.3.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Health Check ───────────────────────────────────────────────────────────


@app.get("/api/status")
async def read_root():
    return {
        "status": "ok",
        "service": "CourseCompass Academic & Benefits Assistant",
        "version": "0.3.0",
    }


# ─── Chat Routes ────────────────────────────────────────────────────────────


@app.post("/api/chat")
def chat_endpoint(request: ChatRequest):
    last_user = next(
        (m for m in reversed(request.messages) if m.get("role") == "user"),
        None,
    )
    if not last_user:
        return {"response": "No user message found.", "sources": []}

    course_code, prefer_doc_type = detect_course_intent(last_user["content"])

    db = SessionLocal()
    try:
        results = search_documents(
            db,
            last_user["content"],
            k=5,
            course_code=course_code,
            prefer_doc_type=prefer_doc_type,
        )
    finally:
        db.close()

    sources = [
        {"source": r["source"], "course_code": r["course_code"], "score": r["score"]}
        for r in results
    ]

    if not results:
        return {
            "response": "I could not find any relevant documents for this query.",
            "sources": sources,
        }

    messages = [{"role": m["role"], "content": m["content"]} for m in request.messages]
    messages[-1]["content"] = build_grounded_prompt(results, last_user["content"])

    response_text = generate_chat_response(messages)

    return {"response": response_text, "sources": sources}


# ─── RAG Routes ──────────────────────────────────────────────────────────────


@app.post("/api/rag")
def rag_endpoint(request: RagQuery):
    if not request.query.strip():
        return {"answer": "Please provide a query.", "sources": []}

    course_code, prefer_doc_type = detect_course_intent(request.query)

    db = SessionLocal()
    try:
        results = search_documents(
            db,
            request.query,
            k=request.k,
            course_code=course_code or request.course_code,
            prefer_doc_type=prefer_doc_type,
        )
    finally:
        db.close()

    if not results:
        return {"answer": "No relevant documents found for this query.", "sources": []}

    answer = generate_chat_response(
        [{"role": "user", "content": build_grounded_prompt(results, request.query)}]
    )

    return {
        "answer": answer,
        "sources": [
            {"source": r["source"], "course_code": r["course_code"], "score": r["score"]}
            for r in results
        ],
    }
