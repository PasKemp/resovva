"""
LLM Wrapper – Azure OpenAI (Production) oder Standard OpenAI (DEV).

Chat/Completion und Embeddings. Für DEV: OPENAI_API_KEY (platform.openai.com).
Für Production: Azure-Variablen (DSGVO: Azure Germany).
"""

from typing import List, Optional

from app.core.config import get_settings


def get_llm():
    """
    Liefert das Chat-Modell für LangChain/LangGraph.

    - Azure konfiguriert (Endpoint + Key) → AzureChatOpenAI (Production).
    - Nur OPENAI_API_KEY gesetzt → ChatOpenAI (DEV, platform.openai.com, Pay-per-Use).
    """
    settings = get_settings()

    # Production: Azure OpenAI (DSGVO)
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from langchain_openai import AzureChatOpenAI

        endpoint = (settings.azure_openai_endpoint or "").rstrip("/")
        return AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=settings.azure_openai_api_key,
            azure_deployment=settings.azure_openai_deployment,
            openai_api_version=settings.openai_api_version,
            temperature=0,
            timeout=60,
        )

    # DEV: Standard OpenAI (platform.openai.com, z.B. 5€ Guthaben)
    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model="gpt-4o",
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=60,
        )

    raise ValueError(
        "Kein LLM konfiguriert. "
        "DEV: Setze OPENAI_API_KEY in .env (platform.openai.com, Pay-per-Use). "
        "Production: Setze AZURE_OPENAI_ENDPOINT und AZURE_OPENAI_API_KEY."
    )


def get_embeddings(
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment: Optional[str] = None,
):
    """Azure OpenAI Embeddings für RAG."""
    # return AzureOpenAIEmbeddings(
    #     azure_endpoint=endpoint,
    #     api_key=api_key,
    #     azure_deployment=deployment or "text-embedding-3-small",
    # )
    return None


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Texte zu Vektoren embedden."""
    # TODO: get_embeddings().embed_documents(texts)
    return []
