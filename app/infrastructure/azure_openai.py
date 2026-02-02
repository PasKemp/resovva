"""
LLM Wrapper – Azure OpenAI (DSGVO: Azure Germany).

Chat/Completion und Embeddings.
"""

from typing import List, Optional

# from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings


def get_llm(
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    deployment: str = "gpt-4o",
):
    """
    Azure OpenAI Chat-Modell für LangChain/LangGraph.
    TODO: Aus app.core.config.get_settings() befüllen.
    """
    # return AzureChatOpenAI(
    #     azure_endpoint=endpoint,
    #     api_key=api_key,
    #     azure_deployment=deployment,
    #     api_version="2024-02-15-preview",
    # )
    return None


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
