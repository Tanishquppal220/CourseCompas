from typing import TypedDict, Annotated, Sequence, Literal
import operator
import os
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.services.agents import create_course_advisor, create_rpl_advisor, create_benefits_expert, load_prompt

# 1. State Definition
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str

# 2. Router Model
class RouterOutput(BaseModel):
    next: Literal["RPL_Advisor", "Course_Advisor", "Benefits_Expert", "FINISH"] = Field(
        description="The name of the next agent to route to, or FINISH if the user's request is complete."
    )

def create_multi_agent_app(llm, tools):
    # Initialize agents
    course_agent = create_course_advisor(llm, tools)
    rpl_agent = create_rpl_advisor(llm, tools)
    benefits_agent = create_benefits_expert(llm, tools)
    
    # 3. Node Functions
    def supervisor_node(state: AgentState):
        members = ["RPL_Advisor", "Course_Advisor", "Benefits_Expert"]
        prompt_text = load_prompt("supervisor_prompt.md")
        system_msg = SystemMessage(content=prompt_text.replace("{members}", ", ".join(members)))
        
        # Ask LLM to output structured routing response
        messages = [system_msg] + list(state["messages"])
        structured_llm = llm.with_structured_output(RouterOutput)
        try:
            response = structured_llm.invoke(messages)
            if response and hasattr(response, 'next'):
                return {"next": response.next}
        except Exception as e:
            print(f"Supervisor routing failed: {e}")
            
        # Fallback to FINISH if structured output fails
        return {"next": "FINISH"}

    def rpl_node(state: AgentState):
        result = rpl_agent.invoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}

    def course_node(state: AgentState):
        result = course_agent.invoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}

    def benefits_node(state: AgentState):
        result = benefits_agent.invoke({"messages": state["messages"]})
        return {"messages": [result["messages"][-1]]}

    # 4. Build Graph
    workflow = StateGraph(AgentState)
    
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("RPL_Advisor", rpl_node)
    workflow.add_node("Course_Advisor", course_node)
    workflow.add_node("Benefits_Expert", benefits_node)
    
    workflow.add_conditional_edges(
        "Supervisor",
        lambda x: x["next"],
        {
            "RPL_Advisor": "RPL_Advisor",
            "Course_Advisor": "Course_Advisor",
            "Benefits_Expert": "Benefits_Expert",
            "FINISH": END
        }
    )
    
    workflow.add_edge("RPL_Advisor", END)
    workflow.add_edge("Course_Advisor", END)
    workflow.add_edge("Benefits_Expert", END)
    
    workflow.set_entry_point("Supervisor")
    return workflow.compile()
