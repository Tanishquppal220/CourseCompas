import os

from app.schemas import ChatMessage
from app.services.tools import search_academic_benefits, search_course_info
from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import create_engine


def generate_chat_response(messages: list[ChatMessage], current_user=None) -> str:
    # llm = ChatGoogleGenerativeAI(
    #     model="gemini-3.6-flash",
    #     google_api_key=os.getenv("GOOGLE_API_KEY"),
    # )
    llm = ChatBedrockConverse(
        model_id="openai.gpt-oss-120b-1:0",
        region_name=os.getenv("AWS_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    
    db_url = os.getenv("READONLY_DATABASE_URL", os.getenv("DATABASE_URL"))
    engine = create_engine(db_url)
    db = SQLDatabase(
        engine, 
        include_tables=["courses", "programs", "terms", "term_curriculum", "elective_baskets", "course_prerequisites"]
    )
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    
    tools = [search_academic_benefits, search_course_info] + toolkit.get_tools()
    
    from app.services.multi_agent import create_multi_agent_app
    app = create_multi_agent_app(llm, tools)
    
    # Build student context from user profile
    langchain_messages = []
    if current_user:
        student_context = f"""CURRENT STUDENT CONTEXT:
- Name: {current_user.full_name or 'Unknown'}
- Registration Number: {current_user.registration_number}
- Program: {current_user.program_name or 'Unknown'}
- Current Term: {current_user.current_term or 'Unknown'}
- Current CGPA: {float(current_user.current_cgpa) if current_user.current_cgpa else 'Unknown'}
- Admission Year: {current_user.admission_year or 'Unknown'}

Use this information to personalize your responses. For example, if the student asks about their current term courses, use their term number. If they ask about benefits eligibility, check against their CGPA.

FORMATTING RULES:
- Do NOT greet the student by name at the start of every message. Only greet on the very first message of a conversation.
- NEVER use HTML tags like <br>, <b>, <i>, <table>, etc. Use ONLY standard Markdown formatting (headers, bold, lists, tables with pipes).
- For line breaks inside table cells, use separate rows instead.

CRITICAL — NO HALLUCINATION:
- NEVER invent, guess, or make up course codes, course names, prerequisites, or any academic data.
- You MUST ALWAYS query the database using your SQL tools or search tools BEFORE mentioning any course.
- If a tool returns no results, say "I could not find that information in the database" — do NOT fill in the gap with made-up data.
- This applies to RPL advice too: do NOT suggest specific courses for RPL unless you have verified they exist in the database."""
        langchain_messages.append(SystemMessage(content=student_context))
    
    for msg in messages:
        if msg.role == "user":
            langchain_messages.append(HumanMessage(content=msg.content))
        else:
            langchain_messages.append(AIMessage(content=msg.content))
            
    response = app.invoke({"messages": langchain_messages})
    
    last_message = response["messages"][-1]
    content = last_message.content
    
    if isinstance(content, list):
        text_parts = []
        for p in content:
            if isinstance(p, dict):
                if "text" in p:
                    text_parts.append(p["text"])
                elif p.get("type") == "text":
                    text_parts.append(p.get("text", ""))
        
        if text_parts:
            return "".join(text_parts)
            
        # Fallback if no text parts were found
        return "The AI generated a response, but it could not be parsed."
        
    return str(content)
