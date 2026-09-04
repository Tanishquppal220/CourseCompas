from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.concurrency import asynccontextmanager
from sqlalchemy.orm import Session

from .schemas import (
    ChatRequest,
    ChatResponse,
)
from .services.llm import generate_chat_response
from .services.retrieval import search_benefits
from .database import get_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print("Shutting down RAG background workers...")
    try:
        from joblib import externals
        externals.loky.get_reusable_executor().shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(
    title="CourseCompass API",
    description="Academic Programme Personalization & Benefits RAG API",
    version="0.3.0",
    lifespan=lifespan,
)


# ─── Health Check ───────────────────────────────────────────────────────────

@app.get("/")
async def read_root():
    return {
        "status": "online",
        "service": "CourseCompass Academic & Benefits Assistant",
        "version": "0.3.0",
    }


# ─── Benefits Search ───────────────────────────────────────────────────────

@app.get("/api/benefits/search")
def search_benefits_api(
    query: str = Query(..., description="User query about academic benefits"),
    limit: int = Query(5, ge=1, le=20, description="Number of results to retrieve"),
    section: str | None = Query(None, description="Optional section filter"),
    db: Session = Depends(get_db),
):
    results = search_benefits(db=db, query=query, limit=limit, section_filter=section)
    return {
        "query": query,
        "section_filter": section,
        "total_results": len(results),
        "results": results,
    }


# ─── Chat Routes ────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(
    request: ChatRequest,
):
    # Generate AI response
    response_text = generate_chat_response(request.messages)

    return ChatResponse(response=response_text)
