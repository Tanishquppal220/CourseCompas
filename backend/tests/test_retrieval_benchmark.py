"""Retrieval Benchmark Suite: Evaluates Baseline vs. Improved Retrieval Strategies.

Measures Hit Rate (Hit@1, Hit@3, Hit@5), Candidate Recall (Recall@15), Mean Reciprocal
Rank (MRR@5), and latency (ms) across curated query categories in the CourseCompass backend.

Supports side-by-side A/B evaluation:
    - Baseline Modes: dense, fts, baseline_hybrid, baseline_rerank (candidate_k=15)
    - Improved Sandbox Modes: improved_fts, improved_hybrid (alpha=1.2 + cleaned query),
                              improved_rerank (fast candidate_k=8), improved_rerank_depth (candidate_k=15)

Usage:
    # Run full A/B comparison across baseline and improved modes (fast, DB-only)
    uv run python tests/test_retrieval_benchmark.py --skip-rerank

    # Run full benchmark including cross-encoder reranking comparison
    uv run python tests/test_retrieval_benchmark.py

    # Filter to a specific query category
    uv run python tests/test_retrieval_benchmark.py --category "Course Codes"

    # Interactive inspection for a custom query
    uv run python tests/test_retrieval_benchmark.py --query "CSE205 Data Structures syllabus" --verbose

    # Export benchmark report to markdown
    uv run python tests/test_retrieval_benchmark.py --output results/retrieval_benchmark.md

    # Run as a pytest test
    uv run pytest tests/test_retrieval_benchmark.py
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any, Callable

# Ensure backend root is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.embeddings import embed_query
from app.models import BenefitChunk, CourseDocumentChunk
from app.reranker import rerank_documents


# ─── Data Structures ────────────────────────────────────────────────────────


@dataclass
class QueryTestCase:
    id: str
    query: str
    category: str
    domain: str  # "course" or "benefit"
    expected_course_code: str | None = None
    expected_section: str | None = None
    expected_doc_type: str | None = None
    expected_keywords: list[str] = field(default_factory=list)
    custom_validator: Callable[[dict[str, Any]], bool] | None = None

    def matches(self, chunk: dict[str, Any]) -> bool:
        if self.custom_validator is not None:
            return self.custom_validator(chunk)

        if self.expected_course_code and chunk.get("course_code") != self.expected_course_code:
            return False

        if self.expected_doc_type and chunk.get("doc_type") != self.expected_doc_type:
            return False

        if self.expected_section:
            sec = chunk.get("section_title") or ""
            if self.expected_section.lower() not in sec.lower():
                return False

        if self.expected_keywords:
            content = (chunk.get("content") or "").lower()
            sec = (chunk.get("section_title") or "").lower()
            combined = f"{sec} {content}"
            for kw in self.expected_keywords:
                if kw.lower() not in combined:
                    return False

        return True


@dataclass
class ModeMetricResult:
    mode_name: str
    hit_at_1: float = 0.0
    hit_at_3: float = 0.0
    hit_at_5: float = 0.0
    recall_at_15: float = 0.0
    mrr_at_5: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    total_queries: int = 0


# ─── Test Cases Dataset ─────────────────────────────────────────────────────

BENCHMARK_CASES: list[QueryTestCase] = [
    # ── Category 1: Exact Course Codes & Unit Lookups ───────────────────────
    QueryTestCase(
        id="C1_CSE205_SYLLABUS",
        query="What topics are covered in CSE205 Data Structures syllabus?",
        category="Course Codes",
        domain="course",
        expected_course_code="CSE205",
        expected_doc_type="Syllabus",
        expected_keywords=["data structures"],
    ),
    QueryTestCase(
        id="C1_INT108_PYTHON",
        query="INT108 Python programming unit topics",
        category="Course Codes",
        domain="course",
        expected_course_code="INT108",
        expected_keywords=["python"],
    ),
    QueryTestCase(
        id="C1_CSE316_OS",
        query="CSE316 Operating Systems CPU scheduling syllabus",
        category="Course Codes",
        domain="course",
        expected_course_code="CSE316",
        expected_keywords=["operating system"],
    ),
    QueryTestCase(
        id="C1_ECE249_BASIC",
        query="ECE249 basic electrical and electronics engineering",
        category="Course Codes",
        domain="course",
        expected_course_code="ECE249",
    ),
    QueryTestCase(
        id="C1_CSE274_ML",
        query="CSE274 applied machine learning clustering regression",
        category="Course Codes",
        domain="course",
        expected_course_code="CSE274",
        expected_keywords=["machine learning"],
    ),

    # ── Category 2: Academic Acronyms & Weightages ──────────────────────────
    QueryTestCase(
        id="C2_IP_PEL134_WEIGHTAGE",
        query="PEL134 Instruction Plan IP course weightage ATT CA",
        category="Academic Acronyms",
        domain="course",
        expected_course_code="PEL134",
        expected_doc_type="IP",
        expected_keywords=["weightage"],
    ),
    QueryTestCase(
        id="C2_CSE205_IP_LECTURE",
        query="CSE205 instruction plan lecture breakdown",
        category="Academic Acronyms",
        domain="course",
        expected_course_code="CSE205",
        expected_doc_type="IP",
    ),
    QueryTestCase(
        id="C2_RPL_POLICY",
        query="Recognition of Prior Learning RPL policy benefit",
        category="Academic Acronyms",
        domain="benefit",
        expected_section="Recognition of Prior Learning",
    ),
    QueryTestCase(
        id="C2_DUTY_LEAVE_DL",
        query="Duty Leave DL under EduRevolution guidelines",
        category="Academic Acronyms",
        domain="benefit",
        expected_section="Duty Leave",
    ),
    QueryTestCase(
        id="C2_SCRGM_MATRIX",
        query="SCRGM Student Centric Revenue Generation Criteria Sheet",
        category="Academic Acronyms",
        domain="benefit",
        expected_section="Student-Centric Revenue Generation",
    ),

    # ── Category 3: Tabular Policy Criteria & Numeric Thresholds ────────────
    QueryTestCase(
        id="C3_ATTENDANCE_7_5",
        query="10% attendance benefit 7.5 CGPA 60% requirement",
        category="Policy Criteria & Numbers",
        domain="benefit",
        expected_section="Attendance Benefit",
        expected_keywords=["7.5", "60%"],
    ),
    QueryTestCase(
        id="C3_GRADE_UPGRADATION_STIPEND",
        query="Grade Upgradation policy stipend greater than 25000",
        category="Policy Criteria & Numbers",
        domain="benefit",
        expected_section="Grade Upgradation",
        expected_keywords=["stipend"],
    ),
    QueryTestCase(
        id="C3_INTERNSHIP_DURATION",
        query="Internship beyond Curriculum duration and marks benefit",
        category="Policy Criteria & Numbers",
        domain="benefit",
        expected_section="Internship beyond Curriculum",
    ),
    QueryTestCase(
        id="C3_NPTEL_MOOCS",
        query="NPTEL Proctored MOOCs Certifications Criteria Sheet",
        category="Policy Criteria & Numbers",
        domain="benefit",
        expected_section="NPTEL",
    ),
    QueryTestCase(
        id="C3_ATTENDANCE_DOUBLE_WEEK1",
        query="Double attendance incentive first week of semester",
        category="Policy Criteria & Numbers",
        domain="benefit",
        expected_section="Attendance Benefit",
        expected_keywords=["attendance"],
    ),

    # ── Category 4: References & Proper Nouns ───────────────────────────────
    QueryTestCase(
        id="C4_OLIVER_THEOBALD",
        query="Oliver Theobald Machine Learning for Absolute Beginners",
        category="References & Authors",
        domain="course",
        expected_course_code="CSE274",
        expected_keywords=["oliver theobald"],
    ),
    QueryTestCase(
        id="C4_SRIDHAR_OXFORD",
        query="Sridhar Vijayalakshmi Oxford University Press Machine Learning",
        category="References & Authors",
        domain="course",
        expected_course_code="CSE274",
        expected_keywords=["sridhar"],
    ),
    QueryTestCase(
        id="C4_CO_COURSE_OUTCOMES",
        query="CSE205 Course Outcome CO1 time space complexity",
        category="References & Authors",
        domain="course",
        expected_course_code="CSE205",
        expected_keywords=["co1"],
    ),
    QueryTestCase(
        id="C4_PROJECT_BENEFITS",
        query="Project based benefits under EduRevolution incubation",
        category="References & Authors",
        domain="benefit",
        expected_section="Project",
    ),
    QueryTestCase(
        id="C4_RMS_GRIEVANCE",
        query="RMS ticket submission for Edu-Revolution benefits",
        category="References & Authors",
        domain="benefit",
        expected_keywords=["rms"],
    ),

    # ── Category 5: Conceptual & Paraphrased Queries ────────────────────────
    QueryTestCase(
        id="C5_HACKATHON_GRADE",
        query="How can participating in national hackathons help my grades?",
        category="Conceptual & Paraphrased",
        domain="benefit",
        expected_section="Grade Upgradation",
    ),
    QueryTestCase(
        id="C5_MISSED_EXAM_SPORTS",
        query="What happens if I miss my exam due to an approved sports event?",
        category="Conceptual & Paraphrased",
        domain="benefit",
        expected_section="Duty Leave",
    ),
    QueryTestCase(
        id="C5_OFF_CAMPUS_INTERNSHIP",
        query="Can an off campus internship waive any course evaluations?",
        category="Conceptual & Paraphrased",
        domain="benefit",
        expected_section="Internship beyond Curriculum",
    ),
    QueryTestCase(
        id="C5_SHORT_ATTENDANCE",
        query="How do I get extra attendance if I am below 75 percent?",
        category="Conceptual & Paraphrased",
        domain="benefit",
        expected_section="Attendance Benefit",
    ),
    QueryTestCase(
        id="C5_ML_REGRESSION",
        query="Linear regularized tree based regression models machine learning",
        category="Conceptual & Paraphrased",
        domain="course",
        expected_course_code="CSE274",
        expected_keywords=["regression"],
    ),
]


# ─── Query Preprocessing Helper for FTS ─────────────────────────────────────

FTS_STOP_PATTERNS = [
    r"\b(what\s+is|what\s+are|what\s+topics\s+are\s+covered\s+in|topics\s+covered\s+in|what\s+topics\s+are)\b",
    r"\b(can\s+you\s+show\s+me|show\s+me\s+the|tell\s+me\s+about|can\s+you\s+tell\s+me)\b",
    r"\b(how\s+does|how\s+can|how\s+do\s+i|what\s+happens\s+if\s+i|can\s+an)\b",
    r"\b(difference\s+between|list\s+of|breakdown\s+of|overview\s+of)\b",
    r"\b(topics|covered|syllabus|details|guidelines|requirement|requirements)\b",
]


def clean_query_for_fts(query: str) -> tuple[str, str | None]:
    """Distills conversational natural language queries into content keywords for FTS."""
    text_clean = query

    # Extract course code (e.g. CSE205, INT108)
    course_match = re.search(r"\b([A-Za-z]{3}\d{3})\b", text_clean)
    extracted_code = course_match.group(1).upper() if course_match else None

    # Remove conversational filler patterns
    for pat in FTS_STOP_PATTERNS:
        text_clean = re.sub(pat, " ", text_clean, flags=re.IGNORECASE)

    # Clean punctuation
    text_clean = re.sub(r"[?!.,;:\"'(){}\[\]]", " ", text_clean)

    tokens = [
        t for t in text_clean.split()
        if len(t) > 1 and t.lower() not in {
            "the", "in", "and", "or", "to", "for", "of", "on", "at", "by", "an", "is", "if", "my"
        }
    ]

    cleaned_query = " ".join(tokens)
    return (cleaned_query if cleaned_query else query), extracted_code


# ─── Baseline Retrieval Engines (Mirrors app/retrieval.py) ───────────────────


def execute_dense_search(
    db: Session,
    domain: str,
    query_vector: list[float],
    k: int = 15,
) -> list[dict[str, Any]]:
    """Baseline Mode 1: Pure Dense Vector Search (Cosine Similarity)."""
    if domain == "course":
        distance = CourseDocumentChunk.embedding.cosine_distance(query_vector)
        score = 1.0 - distance
        q = (
            db.query(CourseDocumentChunk, score.label("score"))
            .filter(distance < 0.6)
            .order_by(score.desc())
            .limit(k)
        )
        return [
            {
                "id": chunk.id,
                "course_code": chunk.course_code,
                "doc_type": chunk.doc_type,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in q.all()
        ]
    else:
        distance = BenefitChunk.embedding.cosine_distance(query_vector)
        score = 1.0 - distance
        q = (
            db.query(BenefitChunk, score.label("score"))
            .filter(distance < 0.6)
            .order_by(score.desc())
            .limit(k)
        )
        return [
            {
                "id": chunk.id,
                "course_code": None,
                "doc_type": "Benefits",
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in q.all()
        ]


def execute_fts_search(
    db: Session,
    domain: str,
    query_text: str,
    k: int = 15,
) -> list[dict[str, Any]]:
    """Baseline Mode 2: Raw PostgreSQL Full-Text Search (Cover Density Rank)."""
    tsquery = func.websearch_to_tsquery("english", query_text)
    if domain == "course":
        score = func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery), 0.0)
        q = (
            db.query(CourseDocumentChunk, score.label("score"))
            .filter(CourseDocumentChunk.fts.op("@@")(tsquery))
            .order_by(score.desc())
            .limit(k)
        )
        return [
            {
                "id": chunk.id,
                "course_code": chunk.course_code,
                "doc_type": chunk.doc_type,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in q.all()
        ]
    else:
        score = func.coalesce(func.ts_rank_cd(BenefitChunk.fts, tsquery), 0.0)
        q = (
            db.query(BenefitChunk, score.label("score"))
            .filter(BenefitChunk.fts.op("@@")(tsquery))
            .order_by(score.desc())
            .limit(k)
        )
        return [
            {
                "id": chunk.id,
                "course_code": None,
                "doc_type": "Benefits",
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in q.all()
        ]


def execute_hybrid_search(
    db: Session,
    domain: str,
    query_text: str,
    query_vector: list[float],
    k: int = 15,
    alpha: float = 0.5,
) -> list[dict[str, Any]]:
    """Baseline Mode 3: Current Production Hybrid Search (raw query, alpha=0.5)."""
    tsquery = func.websearch_to_tsquery("english", query_text)
    if domain == "course":
        distance = CourseDocumentChunk.embedding.cosine_distance(query_vector)
        hybrid_score = (1.0 - distance) + (
            func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery), 0.0) * alpha
        )
        q = (
            db.query(CourseDocumentChunk, hybrid_score.label("score"))
            .filter(or_(distance < 0.6, CourseDocumentChunk.fts.op("@@")(tsquery)))
            .order_by(hybrid_score.desc())
            .limit(k)
        )
        return [
            {
                "id": chunk.id,
                "course_code": chunk.course_code,
                "doc_type": chunk.doc_type,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in q.all()
        ]
    else:
        distance = BenefitChunk.embedding.cosine_distance(query_vector)
        hybrid_score = (1.0 - distance) + (
            func.coalesce(func.ts_rank_cd(BenefitChunk.fts, tsquery), 0.0) * alpha
        )
        q = (
            db.query(BenefitChunk, hybrid_score.label("score"))
            .filter(or_(distance < 0.6, BenefitChunk.fts.op("@@")(tsquery)))
            .order_by(hybrid_score.desc())
            .limit(k)
        )
        return [
            {
                "id": chunk.id,
                "course_code": None,
                "doc_type": "Benefits",
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in q.all()
        ]


def execute_hybrid_rerank_search(
    db: Session,
    domain: str,
    query_text: str,
    query_vector: list[float],
    candidate_k: int = 15,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Baseline Mode 4: Current Production Hybrid Search + Reranker (candidate_k=15)."""
    candidates = execute_hybrid_search(
        db, domain, query_text, query_vector, k=candidate_k, alpha=0.5
    )
    if not candidates:
        return []
    return rerank_documents(query_text, candidates, top_k=top_k)


# ─── Improved Experimental Sandbox Engines ──────────────────────────────────


def execute_improved_fts_search(
    db: Session,
    domain: str,
    query_text: str,
    k: int = 15,
) -> list[dict[str, Any]]:
    """Improved Mode: FTS with conversational query distillation and OR fallback."""
    cleaned_text, detected_code = clean_query_for_fts(query_text)
    tsquery = func.websearch_to_tsquery("english", cleaned_text)

    if domain == "course":
        score = func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery), 0.0)
        q = db.query(CourseDocumentChunk, score.label("score"))
        if detected_code:
            q = q.filter(CourseDocumentChunk.course_code == detected_code)
        q = q.filter(CourseDocumentChunk.fts.op("@@")(tsquery))
        rows = q.order_by(score.desc()).limit(k).all()

        # Fallback to OR-query if strict AND query returns 0 hits
        if not rows:
            tokens = cleaned_text.split()
            if len(tokens) > 1:
                or_query = " OR ".join(tokens)
                tsquery_or = func.websearch_to_tsquery("english", or_query)
                score_or = func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery_or), 0.0)
                q_or = db.query(CourseDocumentChunk, score_or.label("score"))
                if detected_code:
                    q_or = q_or.filter(CourseDocumentChunk.course_code == detected_code)
                q_or = q_or.filter(CourseDocumentChunk.fts.op("@@")(tsquery_or))
                rows = q_or.order_by(score_or.desc()).limit(k).all()

        return [
            {
                "id": chunk.id,
                "course_code": chunk.course_code,
                "doc_type": chunk.doc_type,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in rows
        ]
    else:
        score = func.coalesce(func.ts_rank_cd(BenefitChunk.fts, tsquery), 0.0)
        q = db.query(BenefitChunk, score.label("score")).filter(BenefitChunk.fts.op("@@")(tsquery))
        rows = q.order_by(score.desc()).limit(k).all()

        if not rows:
            tokens = cleaned_text.split()
            if len(tokens) > 1:
                or_query = " OR ".join(tokens)
                tsquery_or = func.websearch_to_tsquery("english", or_query)
                score_or = func.coalesce(func.ts_rank_cd(BenefitChunk.fts, tsquery_or), 0.0)
                rows = (
                    db.query(BenefitChunk, score_or.label("score"))
                    .filter(BenefitChunk.fts.op("@@")(tsquery_or))
                    .order_by(score_or.desc())
                    .limit(k)
                    .all()
                )

        return [
            {
                "id": chunk.id,
                "course_code": None,
                "doc_type": "Benefits",
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in rows
        ]


def execute_improved_hybrid_search(
    db: Session,
    domain: str,
    query_text: str,
    query_vector: list[float],
    k: int = 15,
    alpha: float = 1.2,
) -> list[dict[str, Any]]:
    """Improved Mode: Hybrid Search with distilled query, course extraction, and alpha=1.2."""
    cleaned_text, detected_code = clean_query_for_fts(query_text)
    tsquery = func.websearch_to_tsquery("english", cleaned_text)

    if domain == "course":
        distance = CourseDocumentChunk.embedding.cosine_distance(query_vector)
        fts_score = func.coalesce(func.ts_rank_cd(CourseDocumentChunk.fts, tsquery), 0.0)
        hybrid_score = (1.0 - distance) + (fts_score * alpha)

        q = db.query(CourseDocumentChunk, hybrid_score.label("score"))
        if detected_code:
            q = q.filter(CourseDocumentChunk.course_code == detected_code)

        q = q.filter(or_(distance < 0.6, CourseDocumentChunk.fts.op("@@")(tsquery)))
        rows = q.order_by(hybrid_score.desc()).limit(k).all()

        # If zero hits under course_code filter, relax filter to avoid empty result
        if not rows and detected_code:
            q_relaxed = db.query(CourseDocumentChunk, hybrid_score.label("score")).filter(
                or_(distance < 0.6, CourseDocumentChunk.fts.op("@@")(tsquery))
            )
            rows = q_relaxed.order_by(hybrid_score.desc()).limit(k).all()

        return [
            {
                "id": chunk.id,
                "course_code": chunk.course_code,
                "doc_type": chunk.doc_type,
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in rows
        ]
    else:
        distance = BenefitChunk.embedding.cosine_distance(query_vector)
        fts_score = func.coalesce(func.ts_rank_cd(BenefitChunk.fts, tsquery), 0.0)
        hybrid_score = (1.0 - distance) + (fts_score * alpha)

        q = db.query(BenefitChunk, hybrid_score.label("score")).filter(
            or_(distance < 0.6, BenefitChunk.fts.op("@@")(tsquery))
        )
        rows = q.order_by(hybrid_score.desc()).limit(k).all()
        return [
            {
                "id": chunk.id,
                "course_code": None,
                "doc_type": "Benefits",
                "chunk_type": chunk.chunk_type,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "score": float(sc),
            }
            for chunk, sc in rows
        ]


def execute_improved_rerank_search(
    db: Session,
    domain: str,
    query_text: str,
    query_vector: list[float],
    candidate_k: int = 8,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Improved Mode: Improved Hybrid + Fast Cross-Encoder Reranking (candidate_k=8)."""
    candidates = execute_improved_hybrid_search(
        db, domain, query_text, query_vector, k=candidate_k, alpha=1.2
    )
    if not candidates:
        return []
    return rerank_documents(query_text, candidates, top_k=top_k)


# ─── Benchmark Runner ────────────────────────────────────────────────────────


def evaluate_retrieval_modes(
    test_cases: list[QueryTestCase],
    modes_to_test: list[str],
    verbose: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Runs all test cases across selected retrieval modes and aggregates metrics."""
    db = SessionLocal()
    try:
        results_by_mode: dict[str, list[dict[str, Any]]] = {m: [] for m in modes_to_test}

        print(f"\n🚀 Running Retrieval Benchmark on {len(test_cases)} test queries...")
        print(f"Modes under test: {', '.join(modes_to_test)}\n")

        for idx, test_case in enumerate(test_cases, start=1):
            if verbose:
                print(f"\n[{idx}/{len(test_cases)}] ({test_case.category}) Query: \"{test_case.query}\"")

            # Pre-compute query vector once per query for fairness
            query_vector = embed_query(test_case.query)

            for mode in modes_to_test:
                t0 = time.perf_counter()
                if mode == "dense":
                    chunks = execute_dense_search(db, test_case.domain, query_vector, k=15)
                elif mode == "fts":
                    chunks = execute_fts_search(db, test_case.domain, test_case.query, k=15)
                elif mode == "baseline_hybrid":
                    chunks = execute_hybrid_search(
                        db, test_case.domain, test_case.query, query_vector, k=15, alpha=0.5
                    )
                elif mode == "baseline_rerank":
                    chunks = execute_hybrid_rerank_search(
                        db, test_case.domain, test_case.query, query_vector, candidate_k=15, top_k=5
                    )
                elif mode == "improved_fts":
                    chunks = execute_improved_fts_search(db, test_case.domain, test_case.query, k=15)
                elif mode == "improved_hybrid":
                    chunks = execute_improved_hybrid_search(
                        db, test_case.domain, test_case.query, query_vector, k=15, alpha=1.2
                    )
                elif mode == "improved_rerank":
                    chunks = execute_improved_rerank_search(
                        db, test_case.domain, test_case.query, query_vector, candidate_k=8, top_k=5
                    )
                elif mode == "improved_rerank_depth":
                    chunks = execute_improved_rerank_search(
                        db, test_case.domain, test_case.query, query_vector, candidate_k=15, top_k=5
                    )
                else:
                    raise ValueError(f"Unknown mode: {mode}")

                latency_ms = (time.perf_counter() - t0) * 1000

                # Determine match positions
                matches = [test_case.matches(c) for c in chunks]

                hit_at_1 = 1.0 if (len(matches) > 0 and matches[0]) else 0.0
                hit_at_3 = 1.0 if any(matches[:3]) else 0.0
                hit_at_5 = 1.0 if any(matches[:5]) else 0.0
                recall_at_15 = 1.0 if any(matches[:15]) else 0.0

                first_match_rank = next((i for i, m in enumerate(matches[:5]) if m), None)
                mrr_at_5 = (1.0 / (first_match_rank + 1)) if first_match_rank is not None else 0.0

                record = {
                    "query_id": test_case.id,
                    "category": test_case.category,
                    "query": test_case.query,
                    "hit_at_1": hit_at_1,
                    "hit_at_3": hit_at_3,
                    "hit_at_5": hit_at_5,
                    "recall_at_15": recall_at_15,
                    "mrr_at_5": mrr_at_5,
                    "latency_ms": latency_ms,
                    "total_returned": len(chunks),
                }
                results_by_mode[mode].append(record)

                if verbose:
                    status_sym = "✅" if hit_at_5 else "❌"
                    print(
                        f"  -> [{mode:<20}] {status_sym} Hit@1: {int(hit_at_1)} | "
                        f"Hit@5: {int(hit_at_5)} | Rec@15: {int(recall_at_15)} | "
                        f"MRR: {mrr_at_5:.2f} | Latency: {latency_ms:.1f}ms (returned {len(chunks)})"
                    )
                    if chunks:
                        top = chunks[0]
                        sec = top.get("section_title") or top.get("chunk_type") or "chunk"
                        print(f"      Top rank: [{top.get('course_code') or top.get('doc_type')}] {sec[:50]} (score={top.get('score'):.3f})")

        return results_by_mode
    finally:
        db.close()


def aggregate_metrics(
    results_by_mode: dict[str, list[dict[str, Any]]],
) -> dict[str, ModeMetricResult]:
    """Computes global metric averages and percentiles for each mode."""
    summaries: dict[str, ModeMetricResult] = {}
    for mode, records in results_by_mode.items():
        if not records:
            continue
        n = len(records)
        latencies = [r["latency_ms"] for r in records]
        latencies.sort()
        p95_idx = int(0.95 * len(latencies))
        p95 = latencies[min(p95_idx, len(latencies) - 1)]

        summaries[mode] = ModeMetricResult(
            mode_name=mode,
            hit_at_1=sum(r["hit_at_1"] for r in records) / n,
            hit_at_3=sum(r["hit_at_3"] for r in records) / n,
            hit_at_5=sum(r["hit_at_5"] for r in records) / n,
            recall_at_15=sum(r["recall_at_15"] for r in records) / n,
            mrr_at_5=sum(r["mrr_at_5"] for r in records) / n,
            avg_latency_ms=statistics.mean(latencies),
            p95_latency_ms=p95,
            total_queries=n,
        )
    return summaries


def format_markdown_report(
    summaries: dict[str, ModeMetricResult],
    results_by_mode: dict[str, list[dict[str, Any]]],
) -> str:
    """Renders a comprehensive markdown benchmark report."""
    md = [
        "# CourseCompass — Retrieval Benchmark Report (A/B Sandbox Evaluation)",
        "",
        f"**Benchmark Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 1. Global Performance Comparison",
        "",
        "| Mode | Hit@1 | Hit@3 | Hit@5 | Recall@15 (Pool) | MRR@5 | Avg Latency | p95 Latency |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for mode, s in summaries.items():
        md.append(
            f"| **{mode}** | {s.hit_at_1 * 100:.1f}% | {s.hit_at_3 * 100:.1f}% | "
            f"{s.hit_at_5 * 100:.1f}% | {s.recall_at_15 * 100:.1f}% | {s.mrr_at_5:.3f} | "
            f"{s.avg_latency_ms:.1f}ms | {s.p95_latency_ms:.1f}ms |"
        )

    md.extend([
        "",
        "---",
        "",
        "## 2. Category-by-Category Hit Rate @ 5",
        "",
    ])

    categories = sorted({r["category"] for r in next(iter(results_by_mode.values()))})
    header = "| Category | " + " | ".join(f"**{m}**" for m in summaries) + " |"
    divider = "| :--- | " + " | ".join(":---:" for _ in summaries) + " |"
    md.extend([header, divider])

    for cat in categories:
        row = [f"**{cat}**"]
        for mode in summaries:
            cat_records = [r for r in results_by_mode[mode] if r["category"] == cat]
            if cat_records:
                cat_hit5 = (sum(r["hit_at_5"] for r in cat_records) / len(cat_records)) * 100
                row.append(f"{cat_hit5:.1f}%")
            else:
                row.append("N/A")
        md.append("| " + " | ".join(row) + " |")

    md.extend([
        "",
        "---",
        "",
        "## 3. Analysis & Key Findings",
        "",
        "1. **Baseline vs Improved Hybrid**:",
        "   - `improved_hybrid` introduces conversational question distillation, OR fallback relaxation, and an alpha boost (1.2).",
        "2. **Averting Reranker Starvation with Fast Candidate Pool (k=8 vs k=15)**:",
        "   - Candidate budget tuning tests whether reranking 8 candidates preserves recall while halving CPU latency.",
        "",
    ])

    return "\n".join(md)


# ─── Pytest Compatibility ───────────────────────────────────────────────────


def test_retrieval_benchmark():
    """Automated pytest test: asserts improved hybrid retrieval outperforms or equals baseline."""
    modes = ["dense", "baseline_hybrid", "improved_hybrid"]
    cases = BENCHMARK_CASES[:10]  # First 10 cases for quick CI execution
    results = evaluate_retrieval_modes(cases, modes, verbose=False)
    metrics = aggregate_metrics(results)

    dense_hit5 = metrics["dense"].hit_at_5
    improved_hit5 = metrics["improved_hybrid"].hit_at_5

    assert improved_hit5 >= dense_hit5, (
        f"Improved Hybrid Hit@5 ({improved_hit5:.2f}) should be >= Dense Hit@5 ({dense_hit5:.2f})"
    )
    assert improved_hit5 >= 0.80, (
        f"Improved Hybrid Hit@5 ({improved_hit5:.2f}) should achieve at least 80% on core queries"
    )


# ─── CLI Entrypoint ─────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(description="CourseCompass Retrieval Benchmark Harness")
    parser.add_argument(
        "--mode",
        choices=[
            "all",
            "dense",
            "fts",
            "baseline_hybrid",
            "baseline_rerank",
            "improved_fts",
            "improved_hybrid",
            "improved_rerank",
            "improved_rerank_depth",
        ],
        default="all",
        help="Retrieval mode to evaluate (default: all)",
    )
    parser.add_argument(
        "--skip-rerank",
        action="store_true",
        help="Skip cross-encoder reranking mode for fast DB-only benchmark",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter benchmark to a specific category (e.g. 'Course Codes')",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Run a single one-off query test across modes",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to export the markdown benchmark report (e.g. results/retrieval_benchmark.md)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed per-query chunk rankings and scores",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Determine modes
    if args.mode == "all":
        if args.skip_rerank:
            modes = ["dense", "fts", "improved_fts", "baseline_hybrid", "improved_hybrid"]
        else:
            modes = [
                "dense",
                "fts",
                "improved_fts",
                "baseline_hybrid",
                "improved_hybrid",
                "baseline_rerank",
                "improved_rerank",
            ]
    else:
        modes = [args.mode]

    # Handle single query test
    if args.query:
        print(f"\n🔍 Testing Single Query: \"{args.query}\"")
        cases = [
            QueryTestCase(
                id="CUSTOM_QUERY",
                query=args.query,
                category="Custom Query",
                domain="course",
            )
        ]
        results = evaluate_retrieval_modes(cases, modes, verbose=True)
        return

    # Filter test cases
    cases = BENCHMARK_CASES
    if args.category:
        cases = [c for c in cases if args.category.lower() in c.category.lower()]
        if not cases:
            print(f"❌ No test cases found matching category '{args.category}'")
            return

    # Run benchmark
    results = evaluate_retrieval_modes(cases, modes, verbose=args.verbose)
    summaries = aggregate_metrics(results)

    # Print summary tables
    report_md = format_markdown_report(summaries, results)
    print("\n" + report_md)

    # Optional export
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report_md, encoding="utf-8")
        print(f"\n💾 Benchmark report saved to: {out_path.resolve()}")


if __name__ == "__main__":
    main()
