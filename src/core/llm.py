import os
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

def get_llm(model_name: str, temperature: float = 0) -> ChatOpenAI:
    """
    Returns a ChatOpenAI instance configured with environment variables.
    
    Args:
        model_name: The name of the model to use.
        temperature: Sampling temperature (default 0 for deterministic output).
    """
    # Check for LangChain Tracing (LangSmith)
    if os.environ.get("LANGCHAIN_TRACING_V2") == "true":
        logger.info("LangChain Tracing (LangSmith) is enabled.")
    
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "sk-proj-...")
    
    # Map generic roles to environment variables if applicable
    # This allows flexibility even if caller passes a specific name
    if model_name == "supervisor":
        model_name = os.environ.get("MODEL_SUPERVISOR", "gpt-4o")
    elif model_name == "worker":
        model_name = os.environ.get("MODEL_WORKER", "qwen3-30B-A3B-Instruct")
    
    # Also allow overriding specific hardcoded models via env vars if they match known keys
    # But usually better to just use the specific env var in the caller.
    # Here we just ensure we use the passed model_name which might have been resolved above.
    
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        api_key=api_key,
    )
