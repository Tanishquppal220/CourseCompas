import json
import re
from collections import defaultdict
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from sqlalchemy import text

from app.database import SessionLocal
from app.llm import get_llm_agent
from app.models import User
from app.retrieval import search_benefits, search_documents

# ==============================================================================
# 1. Define Tools for the Agent
# ==============================================================================


@tool
def retrieve_syllabus_documents(
    query: str, course_code: str | None = None, doc_type: str | None = None
) -> str:
    """
    Search the university course documents database.

    This database contains two document types per course:
    - "Syllabus": High-level course info — topics by unit, course outcomes (COs), textbooks, practicals.
    - "IP" (Instruction Plan): Detailed operational data — CA/MTE/ETE marks distribution,
      week-by-week lecture schedule, evaluation scheme, LTP hours breakdown.

    Use "Syllabus" when asked about: what a course covers, topics, units, COs, labs, textbooks.
    Use "IP" when asked about: marks distribution, exam weightages, weekly schedule, evaluation scheme.

    Args:
        query: The search query (e.g., "marks distribution", "unit 3 topics", "course outcomes")
        course_code: Optional course code filter (e.g., "CSE202")
        doc_type: Optional filter — "Syllabus" or "IP"
    """
    db = SessionLocal()
    try:
        doc_type_filter = [doc_type] if doc_type else None
        docs = search_documents(
            db,
            query,
            k=8,
            course_code=course_code,
            doc_types=doc_type_filter,
            prefer_doc_type=doc_type,
        )
        if not docs:
            return "No relevant syllabus documents found."

        result = []
        for d in docs:
            header = f"[{d['doc_type']}/{d['chunk_type']}] Source: {d['source']} (Course: {d['course_code']})"
            if d.get("section_title"):
                header += f" | Section: {d['section_title']}"
            result.append(f"{header}\n{d['content']}")
        return "\n\n---\n\n".join(result)
    finally:
        db.close()


@tool
def retrieve_policy_benefits(query: str) -> str:
    """
    Search the university's Academic Benefits policy under the LPU EduRevolution (EduRev) framework.

    This tool covers all 8 EduRevolution benefit policies:
    1. 10% Attendance Benefit (requires CGPA >= 7.5 and >= 60% raw attendance)
    2. Duty Leave (DL) under EDU Revolution (hackathons, competitive exams, approved events)
    3. Grade Upgradation (patents filed/published/granted, Scopus Q1-Q4 publications, hackathons)
    4. Internship beyond Curriculum (stipend range x duration matrix for CA/MTE waivers or Grade Up)
    5. NPTEL/Proctored MOOCs Equivalence (CGPA >= 7.0 for full course waiver; UGC 40% cap)
    6. Project-based benefits (Industry/Govt projects, incubation centre startups)
    7. RPL — Recognition of Prior Learning (certifications/work exp -> course waiver; needs B+ in RPL exam)
    8. SCRGM — Student-Centric Revenue Generation Model (earning while learning rewards)

    Args:
        query: The search query (e.g., "EduRevolution benefits", "internship grade boost", "Scopus paper grade up", "RPL eligibility")
    """
    db = SessionLocal()
    try:
        docs = search_benefits(db, query, k=5)
        if not docs:
            return "No relevant policy documents found."

        result = []
        for d in docs:
            header = f"[Benefits/{d['chunk_type']}] Source: {d['source']}"
            if d.get("section_title"):
                header += f" | Section: {d['section_title']}"
            result.append(f"{header}\n{d['content']}")
        return "\n\n---\n\n".join(result)
    finally:
        db.close()


@tool
def query_curriculum_database(sql_query: str) -> str:
    """
    Execute a read-only SQL query against the university program curriculum database to answer structural questions.

    Database Schema:
    - terms (id, number, variant, label)
    - courses (id, code, title, lecture_hours, tutorial_hours, practical_hours, credits, contact_hours)
    - course_types (code, description)
    - course_natures (code, description)
    - elective_areas (id, name)
    - elective_baskets (id, name, term_id)
    - basket_options (id, basket_id, course_id, elective_area_id, s_no)
    - term_slots (id, term_id, s_no, display_name, course_id, basket_id, course_type_code, course_nature_code)

    Args:
        sql_query: A raw PostgreSQL query. Example: "SELECT c.code, c.title FROM courses c JOIN term_slots ts ON ts.course_id = c.id WHERE ts.term_id = 5"
    """
    db = SessionLocal()
    try:
        # Security: Enforce read-only transaction at the PostgreSQL level
        db.execute(text("SET TRANSACTION READ ONLY;"))

        normalized = sql_query.strip().upper()
        if not normalized.startswith(("SELECT", "WITH")):
            return "Error: Only read-only SELECT or WITH queries are allowed on the curriculum database."

        if any(
            keyword in normalized
            for keyword in [
                "INSERT",
                "UPDATE",
                "DELETE",
                "DROP",
                "ALTER",
                "GRANT",
                "TRUNCATE",
                "EXEC",
            ]
        ):
            return "Error: Data mutation and administrative commands are strictly forbidden."

        result = db.execute(text(sql_query)).fetchall()
        if not result:
            return "Query executed successfully, but returned 0 rows."

        return json.dumps([dict(row._mapping) for row in result], default=str)
    except Exception as e:  # noqa: BLE001
        return f"Error executing SQL: {e!s}"
    finally:
        db.close()


@tool
def get_open_minors_and_electives(
    area_or_keyword: str | None = None,
    basket_type: str = "open_minor",
    limit: int = 15,
) -> str:
    """
    Look up official LPU Open Minors, Engineering Minors, and Elective Tracks from the curriculum database.

    MANDATORY: Use this tool WHENEVER a student asks about:
    - What Open Minors (OM) are available at LPU
    - Recommendations for non-technical or interdisciplinary minors (Design, Business, Management, Finance, Law, Psychology, etc.)
    - Engineering Minors (EM) or Pathway Electives
    - Real course codes, titles, and credit values in any minor or elective track

    CRITICAL: NEVER invent course codes or subject names. Always query this tool to get real, official offerings.

    Args:
        area_or_keyword: Optional filter for elective area or subject keyword (e.g. "Management", "Design", "Finance", "AI", "Cyber", "Psychology", "Law").
                         If None, returns a categorized summary of all available Open Minor areas with sample courses.
        basket_type: "open_minor" (default), "engineering_minor", or "pathway".
        limit: Max courses to return per area (default 15).
    """
    db = SessionLocal()
    try:
        basket_pattern = "%open minor%"
        if basket_type == "engineering_minor":
            basket_pattern = "%engineering minor%"
        elif basket_type == "pathway":
            basket_pattern = "%pathway%"

        if area_or_keyword:
            kw = area_or_keyword.strip()
            query = text("""
                SELECT ea.name as area_name, c.code, c.title, c.credits, c.lecture_hours, c.tutorial_hours, c.practical_hours
                FROM basket_options bo
                JOIN elective_baskets eb ON bo.basket_id = eb.id
                JOIN courses c ON bo.course_id = c.id
                JOIN elective_areas ea ON bo.elective_area_id = ea.id
                WHERE eb.name ILIKE :bpat
                  AND (ea.name ILIKE :kw OR c.title ILIKE :kw OR c.code ILIKE :kw)
                ORDER BY ea.name, c.code
                LIMIT :limit;
            """)
            rows = db.execute(query, {"bpat": basket_pattern, "kw": f"%{kw}%", "limit": limit}).fetchall()
            if not rows:
                return (
                    f"No courses found matching keyword '{kw}' in {basket_type}. "
                    "Call again with a broader keyword (e.g. 'Design', 'Management', 'Finance', 'AI') "
                    "or leave empty to list all available tracks."
                )

            by_area = defaultdict(list)
            for r in rows:
                ltp = f"{r.lecture_hours}:{r.tutorial_hours}:{r.practical_hours}"
                by_area[r.area_name].append(f"  * {r.code} - {r.title} | Credits: {r.credits} (LTP: {ltp})")

            out = [f"### Official LPU {basket_type.replace('_', ' ').title()} Offerings for '{kw}':\n"]
            for area, courses in by_area.items():
                out.append(f"**Track: {area}**")
                out.extend(courses)
                out.append("")
            return "\n".join(out)
        else:
            query = text("""
                SELECT ea.name as area_name, COUNT(c.id) as course_count, string_agg(c.code || ': ' || c.title, '; ') as sample_courses
                FROM basket_options bo
                JOIN elective_baskets eb ON bo.basket_id = eb.id
                JOIN courses c ON bo.course_id = c.id
                JOIN elective_areas ea ON bo.elective_area_id = ea.id
                WHERE eb.name ILIKE :bpat
                GROUP BY ea.name
                ORDER BY ea.name;
            """)
            rows = db.execute(query, {"bpat": basket_pattern}).fetchall()
            out = [f"### Available Official LPU {basket_type.replace('_', ' ').title()} Tracks ({len(rows)} Total Tracks):\n"]
            for r in rows:
                samples = "; ".join(r.sample_courses.split("; ")[:3])
                out.append(f"- **{r.area_name}** ({r.course_count} courses) -> e.g. {samples}")
            out.append("\nTo see the full course list for any track, call this tool again with `area_or_keyword='<Track Name>'`.")
            return "\n".join(out)
    finally:
        db.close()


@tool
def maximize_academic_benefits(achievements: str, courses: str) -> str:
    """
    Formulates an optimal EduRevolution benefit stacking strategy when a student has multiple achievements
    (e.g., internships, hackathon wins, research papers, certifications, revenue) across their enrolled courses.

    LPU Stacking Constraints:
    - Exactly ONE mapped benefit per course per term.
    - 10% Attendance Benefit is university-wide ONLY when the achievement/benefit explicitly grants attendance
      relaxation (competitive-exam attendance category, SCRGM revenue tiers). It applies across ALL courses only
      then, and only if CGPA >= 7.5 and raw attendance >= 60%. Do NOT assume it in every stacking plan.
    - Duty Leave (DL) applies for all approved event dates without taking a course benefit slot.
    - High-credit courses (3 or 4 credits) should be prioritized for maximum SGPA gain.

    Args:
        achievements: Summary of achievements and CGPA (e.g. "3-month startup internship at 8k/mo, Scopus Q1 paper, CGPA 7.8")
        courses: Enrolled semester courses (e.g. "CSE202 (4 cr), CSE205 (4 cr), INT306 (3 cr)")
    """
    db = SessionLocal()
    try:
        benefit_records = search_benefits(db, achievements, k=6)
        summary = ["### Retrieved Policy Criteria for Stacking Analysis:\n"]
        for b in benefit_records:
            summary.append(
                f"- **{b.get('section_title', 'Policy')}** [{b.get('chunk_type', '')}]: {b.get('content', '')[:180]}..."
            )

        summary.append("\n### Stacking & Optimization Rules to Apply:")
        summary.append(
            "1. Assign each achievement to a separate course (LPU strictly enforces 1 benefit per course per term)."
        )
        summary.append(
            "2. Allocate high-value waivers (Full CA + MTE or Grade Jump to O) to the highest-credit courses for maximum SGPA boost."
        )
        summary.append(
            "3. ONLY mention the 10% Attendance Benefit if the student's achievement explicitly grants attendance "
            "relaxation (competitive-exam attendance category, SCRGM revenue tiers). State it at most once, as "
            "conditional (CGPA >= 7.5 AND >= 60% raw attendance, subject to Standing Committee approval) and as part "
            "of the benefit itself - never as an extra bonus in unrelated stacking plans."
        )
        summary.append(
            "4. Remind student to submit a distinct nomination on UMS for each course via 'Placement Services / Academic Services >>> Special Academic Benefit'."
        )
        return "\n".join(summary)
    finally:
        db.close()


@tool
def check_academic_eligibility(benefit_type: str, cgpa: float) -> str:
    """
    Evaluates a student's eligibility for specific academic benefits based on their CGPA and the hardcoded university rules.
    Args:
        benefit_type: The type of benefit (e.g., "attendance", "internship", "grade_upgradation").
        cgpa: The student's current CGPA (float).
    """
    benefit_type = benefit_type.lower()
    if "attendance" in benefit_type:
        if cgpa >= 7.5:
            return "Eligible: Student satisfies the 7.5 CGPA requirement for the 10% Attendance Benefit."
        else:
            return f"Not Eligible: Student's CGPA ({cgpa}) is below the mandatory 7.5 threshold for attendance benefits."
    elif "internship" in benefit_type:
        if cgpa >= 6.0:
            return "Eligible: Student satisfies the 6.0 CGPA requirement for internship course integration."
        else:
            return f"Not Eligible: Student's CGPA ({cgpa}) is below the mandatory 6.0 threshold for internships."
    elif any(x in benefit_type for x in ["grade", "publish", "patent"]):
        return "Eligible: Grade upgradation (e.g. Scopus Q1 paper) has no minimum CGPA requirement."

    return "Unknown benefit type. Please consult the manual policies."


# ==============================================================================
# 2. Main Execution Function
# ==============================================================================


def run_agent(
    query: str,
    user_reg_no: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> tuple[str, list]:
    """
    Runs the agent with full tool-calling and conversational memory support.
    """
    db = SessionLocal()
    profile = {}
    try:
        if user_reg_no:
            user_query = (
                db.query(User).filter(User.registration_number == user_reg_no).first()
            )
            if user_query:
                profile = {
                    "registration_number": user_query.registration_number,
                    "current_term": user_query.current_term,
                    "current_cgpa": float(user_query.cgpa) if user_query.cgpa else 0.0,
                    "program_name": user_query.program,
                }
    finally:
        db.close()

    # Define available tools
    tools = [
        get_open_minors_and_electives,
        retrieve_syllabus_documents,
        retrieve_policy_benefits,
        maximize_academic_benefits,
        query_curriculum_database,
        check_academic_eligibility,
    ]

    # Create the LLM Agent
    agent = get_llm_agent(tools=tools)

    # Convert past history into LangChain messages
    messages = []

    # Inject student profile as a system message
    system_ctx = (
        f"You are advising an LPU student (Reg No: {profile.get('registration_number', 'Guest')}).\n"
        f"Current Term: {profile.get('current_term', 'N/A')} | "
        f"Program: {profile.get('program_name', 'B.Tech CSE')} | "
        f"CGPA: {profile.get('current_cgpa', 'N/A')}\n\n"
        "Check CGPA thresholds ONLY if the student explicitly asks about the specific benefit. Do NOT proactively "
        "volunteer the 10% Attendance Benefit or any other threshold in unrelated conversations "
        "(e.g. SCRGM, internships, grade upgradation).\n"
        "- 10% Attendance Benefit (ONLY if asked): requires CGPA >= 7.5 and >= 60% raw attendance.\n"
        "- Internship course integration: standard requirement CGPA >= 6.0.\n"
        "- NPTEL Full Equivalence: requires CGPA >= 7.0.\n"
        "- RPL & Grade Upgradation: NO minimum CGPA required.\n\n"
        "CRITICAL INSTRUCTION: In LPU terminology, 'IP' stands for 'Instruction Plan' (course delivery plan "
        "and marks scheme). It NEVER refers to internet IP addresses.\n\n"
        "CURRICULUM GROUNDING & ANTI-HALLUCINATION RULES:\n"
        "- ZERO INVENTED CODES OR TITLES: You must NEVER invent or hallucinate course codes (e.g. BUSM101, CSE410) "
        "or course titles. Every course code, elective track, minor, and credit count MUST come from a tool call "
        "(`get_open_minors_and_electives`, `query_curriculum_database`, or `retrieve_syllabus_documents`). "
        "If a course is not in the database, it DOES NOT EXIST at LPU.\n"
        "- MANDATORY TOOL CALL FOR ELECTIVES & MINORS: Whenever a student asks about Open Minors, Engineering Minors, "
        "Elective Baskets, or course recommendations, you MUST call `get_open_minors_and_electives` to retrieve genuine LPU tracks "
        "and official course codes (e.g., UI/UX Design: IXD801, Product Design: PID801, Management: MKT202 / FIN212, "
        "AI & ML: CSE273 / CSE274 / CSE470 / CSE471 / CSE472 / CSE473).\n"
        "- ACCURATE CREDITS: Always quote the exact credit count returned by the database (typically 3.0 credits for Open Minor courses). "
        "Never guess or state that minors are 2 credits unless verified from the retrieved record.\n"
        "- NOT OFFERED HONESTY: If a student asks about a subject or code not offered at LPU, explicitly inform them that it is not in the curriculum.\n\n"
        "SYLLABUS GROUNDING INSTRUCTION:\n"
        "When asked about the syllabus, units, or topics of a course, always refer to the Course Overview chunk "
        "and use the EXACT official course title from that chunk (e.g. 'CSE408: DESIGN AND ANALYSIS OF ALGORITHMS') "
        "and its credit structure (L:T:P). NEVER substitute an informal or alternative course name. Enumerate only "
        "the genuine Units (Units I through VI) found in the retrieved Syllabus chunks without hallucinating, "
        "inventing missing units, or treating practical labs as units.\n\n"
        "CONVERSATIONAL ADVISING GUIDELINE:\n"
        "If the student's inquiry about a project, course, or internship lacks key details (stipend, duration, "
        "platform, proctored status, company tier), do NOT make assumptions or dump huge tables. "
        "Politely ask 2-4 numbered clarifying questions first to gather the exact facts."
    )
    messages.append(SystemMessage(content=system_ctx))

    # Append past history
    if chat_history:
        for msg in chat_history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            else:
                messages.append(AIMessage(content=msg.get("content", "")))

    # Append current query
    messages.append(HumanMessage(content=query))

    # Run the Agent
    result = agent.invoke({"messages": messages})

    last_message = result["messages"][-1]
    content = last_message.content

    # Stringify in case of block formatting, filtering out thinking/reasoning blocks
    if isinstance(content, list):
        text_parts = []
        for p in content:
            if isinstance(p, dict):
                if p.get("type") == "reasoning_content":
                    continue  # Skip internal thinking — never show to user
                if "text" in p:
                    text_parts.append(p["text"])
                    continue
            if isinstance(p, str):
                text_parts.append(p)
        response_text = "".join(text_parts)
    else:
        response_text = str(content)

    # Strip any text-level reasoning or think tags (e.g. <reasoning>...</reasoning>)
    response_text = re.sub(
        r"<(?:reasoning|think)>[\s\S]*?</(?:reasoning|think)>", "", response_text
    ).strip()

    # Extract source citations from any tool calls executed in this turn
    sources = []
    for msg in result.get("messages", []):
        content_text = ""
        if hasattr(msg, "content"):
            content_text = str(msg.content)
        for line in content_text.splitlines():
            if "Source:" in line:
                src = line.strip().lstrip("-").strip()
                if src and src not in sources:
                    sources.append(src)

    return response_text, sources
