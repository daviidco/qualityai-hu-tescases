"""AbstractBaseAgent — SOLID base para todos los agentes del pipeline.

SOLID compliance:
  S: Los agentes orquestan el pipeline de su dominio; no hacen llamadas LLM
     directas, retrieval ni reranking — eso es responsabilidad de las
     dependencias inyectadas.
  O: Nuevos agentes extienden este base sin modificarlo.
  L: Cualquier agente concreto es sustituible donde se use AbstractBaseAgent.
  D: Constructor recibe ILLMProvider, IRetriever, IReranker — no clases concretas.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from ..config import Settings
from ..llm.interfaces import ILLMProvider
from ..rag.interfaces import IReranker, IRetriever

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class AbstractBaseAgent(ABC, Generic[InputT, OutputT]):
    """Base genérica para agentes del pipeline de calidad."""

    name: str = "abstract_agent"
    version: str = "0.0.0"

    def __init__(
        self,
        llm: ILLMProvider,
        retriever: IRetriever,
        reranker: IReranker,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._retriever = retriever
        self._reranker = reranker
        self._settings = settings

        # Métricas internas para Contract C
        self._llm_calls: int = 0
        self._rag_retrievals: int = 0

    @abstractmethod
    def process(self, input_data: InputT, **kwargs: Any) -> OutputT:
        """Ejecuta el pipeline del agente. Debe devolver un modelo Pydantic validado."""
        ...

    def _retrieve_and_rerank(
        self,
        query: str,
        metadata_filter: dict | None = None,
        expand_for: str = "stories",
    ) -> list[dict[str, Any]]:
        """Template method: pipeline RAG completo usado por todos los agentes concretos."""
        candidates = self._retriever.retrieve(
            query=query,
            top_k=self._settings.rag_bm25_top_k,
            metadata_filter=metadata_filter,
            expand_for=expand_for,
        )
        self._rag_retrievals += 1
        reranked = self._reranker.rerank(
            query=query,
            candidates=candidates,
            top_n=self._settings.rag_reranker_top_n,
        )
        return reranked

    def _build_rag_context_stories(self, candidates: list[dict[str, Any]]) -> str:
        """Formatea candidatos de historias para inyectar en el system prompt."""
        if not candidates:
            return ""
        lines = ["\n## HISTORIAS DE REFERENCIA (base de conocimiento Katary)\n"]
        lines.append("Usa estas historias como referencia de calidad. No copies — adapta:\n")
        for i, c in enumerate(candidates, 1):
            score = c.get("rerank_score", c.get("rrf_score", 0.0))
            meta = c.get("metadata", {})
            lines.append(
                f"### Referencia {i} | Dominio: {meta.get('dominio', 'N/A')} "
                f"| Relevancia: {score:.3f}\n"
                f"{c['document']}\n"
            )
        return "\n".join(lines)

    def _build_rag_context_patterns(self, candidates: list[dict[str, Any]]) -> str:
        """Formatea candidatos de patrones de testing para inyectar en el system prompt."""
        if not candidates:
            return ""
        lines = ["\n## PATRONES DE TESTING (19 años Katary Software)\n"]
        lines.append("Aplica estas técnicas y lecciones aprendidas:\n")
        for i, c in enumerate(candidates, 1):
            score = c.get("rerank_score", c.get("rrf_score", 0.0))
            meta = c.get("metadata", {})
            lines.append(
                f"### Patrón {i} | Dominio: {meta.get('domain', 'N/A')} "
                f"| Técnicas: {meta.get('techniques', 'N/A')} "
                f"| Relevancia: {score:.3f}\n"
                f"{c['document']}\n"
            )
        return "\n".join(lines)

    @staticmethod
    def _generate_run_id(prefix: str = "m3") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    @property
    def metrics(self) -> dict[str, int]:
        return {"llm_calls": self._llm_calls, "rag_retrievals": self._rag_retrievals}
