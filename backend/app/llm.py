import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_aws import ChatBedrockConverse
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from sqlalchemy import create_engine

load_dotenv()


def generate_chat_response(messages):
    """
    Generate a response from the AI model based on the provided messages.

    Args:
        messages (list): A list of messages in the conversation.

    Returns:
        str: The AI-generated response.
    """
    llm = ChatBedrockConverse(
        model_id="google.gemma-3-4b-it",
        region_name=os.getenv("AWS_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    response = llm.invoke(messages)
    print(f"LLM response: {response}")
    return response.content
