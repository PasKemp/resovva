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
    from langchain_openai import ChatOpenAI

    kwargs = {}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key

    return ChatOpenAI(model="gpt-4o", temperature=0, timeout=60, **kwargs)


def get_embeddings(
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment: Optional[str] = None,
):
    """
    Liefert das Embeddings-Modell für RAG (US-3.1).

    - Azure konfiguriert → AzureOpenAIEmbeddings (Production, DSGVO).
    - Nur OPENAI_API_KEY → OpenAIEmbeddings (DEV).
    - Keines → None (RAG deaktiviert, kein Fehler).
    """
    settings = get_settings()

    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        from langchain_openai import AzureOpenAIEmbeddings

        ep = (endpoint or settings.azure_openai_endpoint or "").rstrip("/")
        return AzureOpenAIEmbeddings(
            azure_endpoint=ep,
            api_key=api_key or settings.azure_openai_api_key,
            azure_deployment=deployment or settings.embedding_deployment or "text-embedding-3-small",
            openai_api_version=settings.openai_api_version,
        )

    # Kein Azure → Standard OpenAI. api_key weglassen wenn None,
    # damit das SDK auf OPENAI_API_KEY im Environment zurückfällt.
    from langchain_openai import OpenAIEmbeddings

    kwargs = {}
    if settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key

    # Kein Key und kein Env-Var → None (RAG deaktiviert, kein Fehler)
    try:
        return OpenAIEmbeddings(
            model=settings.embedding_model or "text-embedding-3-small",
            **kwargs,
        )
    except Exception:
        return None


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Texte zu Embeddings-Vektoren (US-3.1).

    Returns:
        Leere Liste wenn kein Embeddings-Modell konfiguriert.
    """
    embeddings = get_embeddings()
    if embeddings is None:
        return []
    return embeddings.embed_documents(texts)
