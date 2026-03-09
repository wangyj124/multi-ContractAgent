import os
from langchain_openai import ChatOpenAI

def get_llm(model_name: str, temperature: float = 0) -> ChatOpenAI:
    """
    Returns a ChatOpenAI instance configured with environment variables.
    
    Args:
        model_name: The name of the model to use.
        temperature: Sampling temperature (default 0 for deterministic output).
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "sk-proj-...")
    
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        api_key=api_key,
    )
