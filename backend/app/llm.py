from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

load_dotenv()


def generate_chat_response(messages):
    """
    Generate a response from the AI model based on the provided messages.

    Args:
        messages (list): A list of messages in the conversation.

    Returns:
        str: The AI-generated response.
    """
    llm = create_agent(
        model="bedrock_converse:openai.gpt-oss-120b-1:0",
        system_prompt=SystemMessage(
            content=(
                "You are a helpful assistant.\n"
                "FORMATTING RULES:\n"
                "- Respond with clean Markdown. Tables are allowed.\n"
                "- Do NOT use raw HTML tags such as <b>, <i>, <table>. "
                "Inside table cells, use only text; for line breaks within a cell use <br>.\n"
                "- Use standard Markdown: headers, bold (**text**), lists, and pipe tables."
            )
        ),
        tools=[],
    )

    langchain_messages = []
    for msg in messages:
        if msg.get("role") == "user":
            langchain_messages.append(HumanMessage(content=msg.get("content", "")))
        else:
            langchain_messages.append(AIMessage(content=msg.get("content", "")))

    result = llm.invoke({"messages": langchain_messages})

    last_message = result["messages"][-1]
    content = last_message.content

    if isinstance(content, list):
        text_parts = []
        for p in content:
            if isinstance(p, str):
                text_parts.append(p)
            elif isinstance(p, dict) and "text" in p:
                text_parts.append(p["text"])
        return "".join(text_parts) if text_parts else str(content)

    return str(content)
