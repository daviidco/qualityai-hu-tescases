"""AgentRAG — wraps agente_v1_rag functional code into a reusable class.

v1 is not OOP; we encapsulate its logic here so the lifespan can initialize
it once and keep the KB + embedder in memory across requests.
"""

import json
from pathlib import Path

import chromadb
from groq import Groq
from sentence_transformers import SentenceTransformer

_MODULO1 = Path(__file__).parent.parent.parent / "qualityai-modulo1"

_SYSTEM_PROMPT = """Eres un Analista de Requerimientos Senior de Katary Software,
empresa colombiana con 19 años de experiencia y certificación CMMI-DEV Nivel 3.
Tu trabajo es transformar requerimientos ambiguos en historias de usuario profesionales
con criterios de aceptación Given/When/Then verificables.

REGLAS:
1. Formato: "Como [rol], quiero [acción], para que [beneficio]"
2. Criterios de aceptación en formato Given/When/Then con validaciones específicas
3. Incluir validaciones de datos (longitudes, formatos, rangos)
4. Incluir tiempos de respuesta esperados
5. Incluir manejo de errores y casos límite
6. Incluir al menos un caso negativo por cada caso positivo
7. Detectar y resolver ambigüedades con valores concretos

{kb_context}"""


class AgentRAG:
    """Agente v1: RAG básico con salida en texto libre."""

    def __init__(
        self,
        groq_api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        self.groq_client = Groq(api_key=groq_api_key)
        self.model_name = model_name

        kb_path = _MODULO1 / "knowledge_base_data"
        stories_path = _MODULO1 / "examples" / "knowledge_base" / "katary_stories.json"

        print(f"   ⏳ [v1] Loading embeddings: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)

        client = chromadb.PersistentClient(path=str(kb_path))
        self.collection = client.get_or_create_collection(
            name="katary_sgc",
            metadata={"hnsw:space": "cosine"},
        )

        if self.collection.count() == 0:
            self._load_stories(stories_path)
        else:
            print(f"   ✅ [v1] KB ready — {self.collection.count()} stories")

    def _load_stories(self, stories_path: Path) -> None:
        print("   📚 [v1] Indexing stories into ChromaDB...")
        with open(stories_path, "r", encoding="utf-8") as f:
            stories = json.load(f)

        textos = [s["texto"] for s in stories]
        embeddings = self.embedder.encode(textos).tolist()
        self.collection.add(
            ids=[s["id"] for s in stories],
            embeddings=embeddings,
            documents=textos,
            metadatas=[
                {"dominio": s.get("dominio", "general"), "criterios": s.get("criterios", "")}
                for s in stories
            ],
        )
        print(f"   ✅ [v1] {self.collection.count()} stories indexed")

    def process(self, requirement: str, top_k: int = 3) -> str:
        query_emb = self.embedder.encode([requirement]).tolist()
        results = self.collection.query(
            query_embeddings=query_emb,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        historias = []
        for i in range(len(results["ids"][0])):
            sim = 1 - results["distances"][0][i]
            historias.append({
                "id": results["ids"][0][i],
                "texto": results["documents"][0][i],
                "criterios": results["metadatas"][0][i].get("criterios", ""),
                "dominio": results["metadatas"][0][i].get("dominio", ""),
                "similitud": sim,
            })

        contexto_kb = "## HISTORIAS DE REFERENCIA DEL SGC DE KATARY\n"
        contexto_kb += "Usa estas historias como modelo de calidad y profundidad:\n\n"
        for i, h in enumerate(historias, 1):
            contexto_kb += f"### Referencia {i} [{h['id']}] (similitud: {h['similitud']:.2f})\n"
            contexto_kb += f"**Historia:** {h['texto']}\n"
            contexto_kb += f"**Criterios:** {h['criterios']}\n"
            contexto_kb += f"**Dominio:** {h['dominio']}\n\n"

        system_prompt = _SYSTEM_PROMPT.format(kb_context=contexto_kb)
        user_message = (
            f"Transforma el siguiente requerimiento en historias de usuario "
            f"con el mismo nivel de calidad que las referencias del SGC de Katary.\n\n"
            f"REQUERIMIENTO:\n{requirement}"
        )

        response = self.groq_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        return response.choices[0].message.content
