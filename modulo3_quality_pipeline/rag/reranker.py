"""CrossEncoderReranker — reranking con cross-encoder.

Por qué cross-encoder en vez de bi-encoder para reranking:
- Bi-encoder (usado en retrieval): query y doc se embedean por separado,
  similitud = coseno. Rápido pero menos preciso.
- Cross-encoder: query y doc procesados JUNTOS por el modelo → un score
  de relevancia único. Mucho más preciso pero más lento.

Patrón dos etapas (industria):
  recuperar 20 candidatos barato (bi-encoder) →
  reordenar top 5 caro (cross-encoder)

Modelo: cross-encoder/ms-marco-MiniLM-L-6-v2
  - 22M parámetros, ~100ms para 20 candidatos en CPU
  - Entrenado en MS MARCO (QA), generaliza bien a español
"""
from __future__ import annotations

from typing import Any

from sentence_transformers import CrossEncoder

from .interfaces import IReranker


class CrossEncoderReranker(IReranker):
    """Reranker con cross-encoder. Responsabilidad única: reordenar (SOLID-S)."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None:
        self._model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Puntúa todos los pares (query, candidate) y devuelve top_n."""
        if not candidates:
            return []

        pairs = [(query, c["document"]) for c in candidates]
        scores = self._model.predict(pairs)

        reranked = []
        for i, candidate in enumerate(candidates):
            c = dict(candidate)
            c["rerank_score"] = float(scores[i])
            reranked.append(c)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_n]
