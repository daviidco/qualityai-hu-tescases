"""Interfaces RAG — Interface Segregation (SOLID-I).

Cuatro interfaces mínimas y focalizadas:
  IEmbedder       — solo embedea texto
  IKnowledgeRepository — solo almacena/recupera vectores
  IRetriever      — solo recupera candidatos
  IReranker       — solo reordena candidatos

Ningún cliente depende de métodos que no usa (ISP).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IEmbedder(ABC):

    @abstractmethod
    def embed(self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
        """Embedea un batch de textos. Devuelve lista de vectores."""
        ...

    @abstractmethod
    def embed_single(self, text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
        """Embedea un solo texto. Devuelve un vector."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Dimensión del embedding (768 para text-embedding-004)."""
        ...


class IKnowledgeRepository(ABC):

    @abstractmethod
    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """Indexa chunks: [{id, text, metadata}]. Embeddings generados internamente."""
        ...

    @abstractmethod
    def query_dense(
        self,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Búsqueda coseno en ChromaDB con pre-filtro de metadata opcional."""
        ...

    @abstractmethod
    def get_all_documents(self) -> list[dict[str, Any]]:
        """Devuelve todos los documentos para construir el índice BM25."""
        ...

    @abstractmethod
    def count(self) -> int:
        """Número de chunks indexados."""
        ...


class IRetriever(ABC):

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: dict[str, str] | None = None,
        expand_for: str = "stories",
    ) -> list[dict[str, Any]]:
        """Recupera top_k candidatos para el query.

        Devuelve lista de dicts con keys: id, document, metadata, score.
        """
        ...


class IReranker(ABC):

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """Reordena candidatos con cross-encoder. Devuelve top_n sorted por score."""
        ...
