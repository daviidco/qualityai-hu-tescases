"""HybridRetriever — BM25 + Dense + RRF.

Pipeline de recuperación de 3 etapas:
  1. HyDE: expande el query en un documento hipotético → mejor vector
  2. Recuperación paralela: BM25 sparse (top-20) + Dense coseno (top-20)
  3. Reciprocal Rank Fusion (RRF, k=60): merge normalizado → top-K unificado

Referencia RRF: Cormack et al. 2009 — "Reciprocal Rank Fusion outperforms
Condorcet and individual Rank Learning Methods".
"""
from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi

from .interfaces import IEmbedder, IKnowledgeRepository, IRetriever
from .query_expander import HyDEQueryExpander


class HybridRetriever(IRetriever):
    """Retriever híbrido: HyDE + BM25 + Dense + RRF.

    Responsabilidad única: recuperar y fusionar candidatos (SOLID-S).
    No reordena (eso es IReranker) ni hace LLM calls directos (SOLID-S).
    """

    def __init__(
        self,
        repository: IKnowledgeRepository,
        embedder: IEmbedder,
        query_expander: HyDEQueryExpander,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_k: int = 60,
    ) -> None:
        self._repo = repository
        self._embedder = embedder
        self._expander = query_expander
        self._bm25_top_k = bm25_top_k
        self._dense_top_k = dense_top_k
        self._rrf_k = rrf_k

        self._bm25_index: BM25Okapi | None = None
        self._bm25_corpus: list[dict[str, Any]] | None = None

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, str] | None = None,
        expand_for: str = "stories",
    ) -> list[dict[str, Any]]:
        """Pipeline completo: HyDE → BM25 + Dense → RRF → top_k candidatos."""

        # Etapa 1: HyDE — expandir query en documento hipotético
        if expand_for == "patterns":
            expanded_query = self._expander.expand_for_patterns(query)
        else:
            expanded_query = self._expander.expand_for_stories(query)

        # Etapa 2a: Dense retrieval con query expandido
        query_embedding = self._embedder.embed_single(
            expanded_query, task_type="RETRIEVAL_QUERY"
        )
        dense_results = self._repo.query_dense(
            embedding=query_embedding,
            top_k=self._dense_top_k,
            where=metadata_filter,
        )
        dense_ranked = [(r["id"], r["score"]) for r in dense_results]
        doc_lookup = {r["id"]: r for r in dense_results}

        # Etapa 2b: BM25 sparse retrieval sobre query original (no expandido)
        bm25_ranked = self._bm25_search(query, self._bm25_top_k)

        # Completar doc_lookup con resultados BM25 que no estén en dense
        all_docs = self._bm25_corpus or []
        bm25_doc_lookup = {d["id"]: d for d in all_docs}
        for doc_id, _ in bm25_ranked:
            if doc_id not in doc_lookup and doc_id in bm25_doc_lookup:
                bm25_raw = bm25_doc_lookup[doc_id]
                doc_lookup[doc_id] = {
                    "id": doc_id,
                    "document": bm25_raw["text"],
                    "metadata": bm25_raw.get("metadata", {}),
                    "score": 0.0,
                }

        # Etapa 3: RRF Merge
        merged = self._rrf_merge(bm25_ranked, dense_ranked)

        # Resolver IDs a documentos
        candidates = []
        for doc_id, rrf_score in merged[:top_k]:
            if doc_id in doc_lookup:
                candidate = dict(doc_lookup[doc_id])
                candidate["rrf_score"] = rrf_score
                candidates.append(candidate)

        return candidates

    def _build_bm25_index(self) -> None:
        """Construye el índice BM25 de forma lazy la primera vez que se necesita."""
        docs = self._repo.get_all_documents()
        self._bm25_corpus = docs
        tokenized = [d["text"].lower().split() for d in docs]
        self._bm25_index = BM25Okapi(tokenized)

    def _bm25_search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """Devuelve [(doc_id, bm25_score), ...] ordenado descendente."""
        if self._bm25_index is None:
            self._build_bm25_index()

        assert self._bm25_index is not None
        assert self._bm25_corpus is not None

        scores = self._bm25_index.get_scores(query.lower().split())
        ranked = sorted(
            [
                (self._bm25_corpus[i]["id"], float(scores[i]))
                for i in range(len(scores))
                if scores[i] > 0
            ],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def _rrf_merge(
        self,
        bm25_ranked: list[tuple[str, float]],
        dense_ranked: list[tuple[str, float]],
    ) -> list[tuple[str, float]]:
        """Reciprocal Rank Fusion.

        RRF_score(d) = Σ 1 / (k + rank(d))
        k=60 según el paper original de Cormack et al. 2009.
        No requiere normalización de scores — trabaja con los rangos.
        """
        scores: dict[str, float] = {}
        for rank, (doc_id, _) in enumerate(bm25_ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
        for rank, (doc_id, _) in enumerate(dense_ranked):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (self._rrf_k + rank + 1)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def invalidate_bm25_cache(self) -> None:
        """Invalida el índice BM25 cuando el KB cambia (lazy rebuild en próximo retrieve)."""
        self._bm25_index = None
        self._bm25_corpus = None
