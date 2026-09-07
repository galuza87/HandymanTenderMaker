from langchain_openai import ChatOpenAI
from backend.config import LM_STUDIO_URL, LM_STUDIO_API_KEY
from typing import Optional

def get_llm(model_name: Optional[str] = "gpt-4o", temperature: float = 0.7) -> ChatOpenAI:
    """Returns the configured ChatOpenAI instance pointing to LM Studio.
    Supports model overrides for different versions."""
    return ChatOpenAI(
        base_url=LM_STUDIO_URL,
        api_key=LM_STUDIO_API_KEY,
        model_name=model_name,
        temperature=temperature
    )
