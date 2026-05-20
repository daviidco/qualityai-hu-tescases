"""KnowledgeRepository — ChromaDB con chunked indexing.

Mejoras sobre KnowledgeBase de M1/M2:
- Almacena CHUNKS, no documentos completos
  - Historias: 3 chunks (title_story / criteria / lessons)
  - Patrones: 2 chunks (context / lessons)
- Pre-filtro de metadata antes de búsqueda densa
- Dimensión explícita 768 para text-embedding-004
- get_all_documents() para BM25 index building
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb

from .interfaces import IEmbedder, IKnowledgeRepository


class KnowledgeRepository(IKnowledgeRepository):
    """Repositorio ChromaDB con indexado por chunks. Solo almacena/recupera."""

    def __init__(
        self,
        persist_dir: str,
        collection_name: str,
        embedder: IEmbedder,
    ) -> None:
        self._embedder = embedder
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """chunks: [{id, text, metadata}]. Embeddings computados aquí."""
        if not chunks:
            return
        texts = [c["text"] for c in chunks]
        embeddings = self._embedder.embed(texts, task_type="RETRIEVAL_DOCUMENT")
        self._collection.add(
            ids=[c["id"] for c in chunks],
            embeddings=embeddings,
            documents=texts,
            metadatas=[c.get("metadata", {}) for c in chunks],
        )

    def query_dense(
        self,
        embedding: list[float],
        top_k: int,
        where: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Búsqueda coseno con pre-filtro de metadata opcional."""
        kwargs: dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": min(top_k, self.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)
        output = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc_id, doc, meta, dist in zip(ids, docs, metas, dists):
            output.append({
                "id": doc_id,
                "document": doc,
                "metadata": meta,
                "score": 1.0 - dist,  # cosine distance → similarity
            })
        return output

    def get_all_documents(self) -> list[dict[str, Any]]:
        """Devuelve todos los chunks para construir el índice BM25."""
        if self.count() == 0:
            return []
        results = self._collection.get(include=["documents", "metadatas"])
        output = []
        for doc_id, doc, meta in zip(
            results.get("ids", []),
            results.get("documents", []),
            results.get("metadatas", []),
        ):
            output.append({"id": doc_id, "text": doc, "metadata": meta})
        return output

    def count(self) -> int:
        return self._collection.count()

    def load_stories_from_json(self, filepath: str) -> None:
        """Indexa el KB de historias con 3 chunks por historia."""
        path = Path(filepath)
        if not path.exists():
            print(f"  ⚠️  KB de historias no encontrado ({filepath}). El pipeline continuará sin RAG de historias.")
            return

        with open(path, encoding="utf-8") as f:
            stories = json.load(f)

        chunks: list[dict[str, Any]] = []
        for story in stories:
            sid = story["id"]
            dominio = story.get("dominio", "general")
            proyecto = story.get("proyecto", "")

            chunks.append({
                "id": f"{sid}_title",
                "text": story.get("texto", ""),
                "metadata": {
                    "source_id": sid,
                    "chunk_type": "title_story",
                    "dominio": dominio,
                    "proyecto": proyecto,
                },
            })
            criterios = story.get("criterios", "")
            if criterios:
                chunks.append({
                    "id": f"{sid}_criteria",
                    "text": criterios,
                    "metadata": {
                        "source_id": sid,
                        "chunk_type": "criteria",
                        "dominio": dominio,
                    },
                })
            lecciones = story.get("lecciones", "")
            if lecciones:
                chunks.append({
                    "id": f"{sid}_lessons",
                    "text": lecciones,
                    "metadata": {
                        "source_id": sid,
                        "chunk_type": "lessons",
                        "dominio": dominio,
                    },
                })

        if chunks:
            self.add_chunks(chunks)
            print(f"  [KnowledgeRepository] {len(stories)} historias → {len(chunks)} chunks indexados")

    def load_patterns_from_json(self, filepath: str) -> None:
        """Indexa el KB de patrones de testing con 2 chunks por patrón."""
        path = Path(filepath)
        if not path.exists():
            print(f"  ⚠️  KB de patrones no encontrado ({filepath}). El pipeline continuará sin RAG de patrones.")
            return

        with open(path, encoding="utf-8") as f:
            patterns = json.load(f)

        chunks: list[dict[str, Any]] = []
        for p in patterns:
            pid = p["id"]
            dominio = p.get("domain", "general")

            context_text = " ".join(filter(None, [
                p.get("domain", ""),
                p.get("ac_pattern_typical", ""),
                p.get("katary_context", ""),
            ]))
            chunks.append({
                "id": f"{pid}_context",
                "text": context_text,
                "metadata": {
                    "source_id": pid,
                    "chunk_type": "context",
                    "domain": dominio,
                    "techniques": ", ".join(p.get("techniques_used", [])),
                },
            })

            lessons_text = " ".join(filter(None, [
                p.get("lessons_learned_katary", ""),
                "Escenarios típicos: " + " | ".join(p.get("typical_scenarios", [])),
            ]))
            if lessons_text.strip():
                chunks.append({
                    "id": f"{pid}_lessons",
                    "text": lessons_text,
                    "metadata": {
                        "source_id": pid,
                        "chunk_type": "lessons",
                        "domain": dominio,
                    },
                })

        if chunks:
            self.add_chunks(chunks)
            print(f"  [KnowledgeRepository] {len(patterns)} patrones → {len(chunks)} chunks indexados")

    def load_code_patterns_from_json(self, filepath: str) -> None:
        """Indexa la KB Katary de patrones de código con 3 chunks por patrón.

        Chunks:
          - context: domain + katary_context + code_pattern_typical
          - quality:  quality_practices + typical_functions
          - lessons:  common_smells + lessons_learned_katary
        """
        path = Path(filepath)
        if not path.exists():
            print(f"  ⚠️  KB de patrones de código no encontrada ({filepath}). Stage 3 sin RAG.")
            return

        with open(path, encoding="utf-8") as f:
            patterns = json.load(f)

        chunks: list[dict[str, Any]] = []
        for p in patterns:
            pid = p["id"]
            domain = p.get("domain", "general")

            context_text = " ".join(filter(None, [
                domain,
                p.get("katary_context", ""),
                p.get("code_pattern_typical", ""),
            ]))
            chunks.append({
                "id": f"{pid}_context",
                "text": context_text,
                "metadata": {
                    "source_id": pid,
                    "chunk_type": "context",
                    "domain": domain,
                },
            })

            quality_text = " ".join([
                *p.get("quality_practices", []),
                *p.get("typical_functions", []),
            ])
            if quality_text.strip():
                chunks.append({
                    "id": f"{pid}_quality",
                    "text": quality_text,
                    "metadata": {
                        "source_id": pid,
                        "chunk_type": "quality",
                        "domain": domain,
                    },
                })

            lessons_text = " ".join(filter(None, [
                "Smells comunes: " + " | ".join(p.get("common_smells", [])),
                p.get("lessons_learned_katary", ""),
            ]))
            if lessons_text.strip():
                chunks.append({
                    "id": f"{pid}_lessons",
                    "text": lessons_text,
                    "metadata": {
                        "source_id": pid,
                        "chunk_type": "lessons",
                        "domain": domain,
                    },
                })

        if chunks:
            self.add_chunks(chunks)
            print(f"  [KnowledgeRepository] {len(patterns)} patrones Katary → {len(chunks)} chunks indexados")
