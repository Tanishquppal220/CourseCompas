from app.database import SessionLocal
from app.services.retrieval import search_benefits
from langchain_core.tools import tool


@tool
def search_academic_benefits(query: str, section_filter: str = None) -> str:
    """
    Search the academic benefits database for policies on Attendance, Grade Upgradation, Internships, NPTEL, RPL, etc.
    Always use this tool when the user asks about benefits, relaxations, stipends, or eligibility criteria.
    """
    db = SessionLocal()
    try:
        # Retrieve the top 4 most relevant chunks
        results = search_benefits(db=db, query=query, limit=4, section_filter=section_filter)
        if not results:
            return "No specific benefits found for this query."
        
        # Format results into a concise string for the LLM context
        formatted = []
        for r in results:
            formatted.append(f"Section: {r['section_title']}\nDetails:\n{r['content']}")
        
        return "\n\n---\n\n".join(formatted)
    finally:
        db.close()


@tool
def search_course_info(course_code: str, query: str) -> str:
    """
    Search the syllabus or instruction plan (IP) for a specific course (e.g. CSE101).
    ALWAYS use this tool when the user asks about a course's syllabus, topics, outcomes, evaluation scheme, or credits.
    """
    from app.services.retrieval import search_course_docs
    db = SessionLocal()
    try:
        results = search_course_docs(db, query, course_code=course_code, limit=4)
        if not results:
            return f"No detailed syllabus/IP found for {course_code} matching your query."
            
        formatted = [f"Source: {r['course_code']} ({r['doc_type']})\n{r['content']}" for r in results]
        return "\n\n---\n\n".join(formatted)
    except Exception as e:
        return f"Error during course info retrieval: {str(e)}"
