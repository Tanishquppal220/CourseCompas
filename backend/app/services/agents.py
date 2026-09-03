from pathlib import Path
from langchain.agents import create_agent

def load_prompt(filename: str) -> str:
    path = Path(__file__).parent.parent / "prompts" / filename
    return path.read_text(encoding="utf-8")

def create_course_advisor(llm, tools):
    system_prompt = load_prompt("course_advisor_prompt.md")
    return create_agent(llm, tools, system_prompt=system_prompt)

def create_rpl_advisor(llm, tools):
    system_prompt = load_prompt("rpl_advisor_prompt.md")
    return create_agent(llm, tools, system_prompt=system_prompt)

def create_benefits_expert(llm, tools):
    system_prompt = load_prompt("benefits_expert_prompt.md")
    return create_agent(llm, tools, system_prompt=system_prompt)
