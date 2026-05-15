"""GeminiEmbedder — usa text-embedding-004 (768-dim) via el nuevo SDK google-genai.

Ventajas sobre all-MiniLM-L6-v2 de M1/M2:
- 768 dims vs 384 dims → más capacidad representacional
- Soporte multilingüe superior para español
- task_type asymmetry: RETRIEVAL_DOCUMENT al indexar, RETRIEVAL_QUERY al buscar
- Sin descarga de modelo local — API cloud
"""
from __future__ import annotations

from google import genai
from google.genai import types

from .interfaces import IEmbedder


class GeminiEmbedder(IEmbedder):
    """Embedder con text-embedding-004 del nuevo SDK google-genai."""

    def __init__(self, model_name: str = "models/gemini-embedding-001", api_key: str = "") -> None:
        self._model_name = model_name
        self._dim = 3072
        self._api_key = api_key
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            import os
            key = self._api_key or os.environ.get("GEMINI_API_KEY", "")
            if not key:
                raise ValueError(
                    "GEMINI_API_KEY es requerida para embeddings (gemini-embedding-001).\n"
                    "  Agrégala en tu .env aunque uses LLM_PROVIDER=groq —\n"
                    "  los embeddings siempre usan la API de Gemini."
                )
            self._client = genai.Client(api_key=key)
        return self._client

    def set_client(self, client: genai.Client) -> None:
        """Inyecta el cliente compartido (preferir sobre el fallback)."""
        self._client = client

    def embed(
        self,
        texts: list[str],
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[list[float]]:
        """Embedea batch. task_type=RETRIEVAL_DOCUMENT para indexado KB."""
        if not texts:
            return []
        client = self._get_client()
        result = client.models.embed_content(
            model=self._model_name,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        # El nuevo SDK devuelve result.embeddings como lista de Embedding objects
        if hasattr(result, "embeddings"):
            return [e.values for e in result.embeddings]
        # Fallback para respuesta alternativa
        return []

    def embed_single(
        self,
        text: str,
        task_type: str = "RETRIEVAL_QUERY",
    ) -> list[float]:
        """Embedea un solo texto. task_type=RETRIEVAL_QUERY para búsquedas."""
        client = self._get_client()
        result = client.models.embed_content(
            model=self._model_name,
            contents=text,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        if hasattr(result, "embeddings") and result.embeddings:
            return result.embeddings[0].values
        return []

    @property
    def dimension(self) -> int:
        return self._dim
