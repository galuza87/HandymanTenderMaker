from langchain_openai import ChatOpenAI
from backend.config import LM_STUDIO_URL, LM_STUDIO_API_KEY

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=LM_STUDIO_URL,
        api_key=LM_STUDIO_API_KEY,
        model_name="gpt-4o", # Spoof model name to force Langchain to allow json_schema
        temperature=0.7
    )
