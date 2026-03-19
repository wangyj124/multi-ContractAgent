import os
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

def get_llm(model_name: str, temperature: float = 0, timeout: int = 60) -> ChatOpenAI:
    """
    Returns a ChatOpenAI instance configured with environment variables.
    """
    # Check for LangChain Tracing (LangSmith)
    if os.environ.get("LANGCHAIN_TRACING_V2") == "true":
        logger.info("LangChain Tracing (LangSmith) is enabled.")
    
    # Use workspace rules provided values as defaults
    base_url = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:10081/v1")
    api_key = os.environ.get("OPENAI_API_KEY", "sk-6aP9xT2mQv1sRb8Zc4NyUe0Lf7Hk3Wd5")
    
    # Map generic roles to environment variables if applicable
    if model_name == "supervisor":
        model_name = os.environ.get("MODEL_SUPERVISOR", "qwen3-32B")
    elif model_name == "worker":
        model_name = os.environ.get("MODEL_WORKER", "qwen3-30B-A3B-Instruct")
    elif os.environ.get(f"MODEL_{model_name.upper()}"):
        model_name = os.environ.get(f"MODEL_{model_name.upper()}")
    
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        base_url=base_url,
        api_key=api_key,
        timeout=120, # Increased default timeout
        request_timeout=120
    )
