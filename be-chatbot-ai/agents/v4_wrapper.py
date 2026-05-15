"""AgentHITL — Human-in-the-Loop adaptado para REST.

El agente v4 original usa input() bloqueante para revisar ambigüedades con el
analista. Eso es incompatible con HTTP. Esta clase expone dos métodos que
mapean a dos endpoints separados:

    analyze()                  → POST /agent-hitl/ambiguities
    process_with_resolutions() → POST /agent-hitl/refine

El frontend es quien "hace de HITL": recibe las ambigüedades del step 1,
las presenta al analista, y envía las resoluciones en el step 2.
El servidor no guarda estado entre los dos calls — diseño stateless.
"""

import json
import uuid
from pathlib import Path

import chromadb
from groq import Groq
from pydantic import ValidationError
from sentence_transformers import SentenceTransformer

# Path e imports de qualityai-modulo1 ya están resueltos por main.py
from src.ambiguity_detector import AmbiguityDetector, Ambiguity
from src.contract_a import (
    AcceptanceCriterion,
    AmbiguityResolution,
    RefinedRequirements,
    UserStory,
    Priority,
    StoryType,
)

_MODULO1 = Path(__file__).parent.parent.parent / "qualityai-modulo1"

_SYSTEM_PROMPT = """Eres un Analista de Requerimientos Senior de Katary Software (CMMI-DEV L3, 19 años).
Transforma requerimientos ambiguos en historias de usuario estructuradas (IEEE 830 / ISO 25010).

{kb_context}

## FORMATO JSON OBLIGATORIO
Responde SOLO con JSON válido, sin texto ni markdown. Estructura:
{{"project_context": "resumen", "user_stories": [
  {{"id": "US-001", "title": "mín 10 chars", "story_type": "functional|non_functional|technical",
    "priority": "critical|high|medium|low", "as_a": "rol", "i_want": "acción", "so_that": "beneficio",
    "acceptance_criteria": [
      {{"id": "AC-001", "description": "mín 20 chars", "given": "precondición concreta",
        "when": "acción específica", "then": "resultado verificable con tiempos",
        "test_data_examples": [{{"campo": "val", "expected": "resultado"}}],
        "is_negative_case": false, "boundary_values": ["mín", "máx"]}}],
    "business_rules": [], "dependencies": [], "ui_elements": [], "api_endpoints": [],
    "ambiguities_resolved": [
      {{"original_text": "texto ambiguo", "issue": "por qué",
        "resolution": "valores concretos", "assumption_made": false}}]
  }}]}}

## REGLAS
1. IDs: US-001, AC-001 (3 dígitos). ACs secuenciales globales
2. Cada criterio: given/when/then con datos concretos, mín 2 test_data_examples
3. Por cada caso positivo, incluir 1 criterio negativo (is_negative_case: true)
4. Usar las DECISIONES DEL ANALISTA como hechos, NO suposiciones (assumption_made: false)
5. Responde SOLO JSON"""


class AgentHITL:
    """Agente v4 HITL adaptado para REST — stateless, thread-safe."""

    def __init__(
        self,
        groq_api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        embedding_model: str = "all-MiniLM-L6-v2",
        max_retries: int = 3,
        temperature: float = 0.3,
    ):
        self.groq_client = Groq(api_key=groq_api_key)
        self.model_name = model_name
        self.max_retries = max_retries
        self.temperature = temperature

        kb_path = _MODULO1 / "knowledge_base_data"
        stories_path = _MODULO1 / "examples" / "knowledge_base" / "katary_stories.json"

        print(f"   ⏳ [v4] Loading embeddings: {embedding_model}")
        self.embedder = SentenceTransformer(embedding_model)
        self.ambiguity_detector = AmbiguityDetector()

        client = chromadb.PersistentClient(path=str(kb_path))
        self.collection = client.get_or_create_collection(
            name="katary_sgc",
            metadata={"hnsw:space": "cosine"},
        )

        if self.collection.count() == 0:
            self._load_stories(stories_path)
        else:
            print(f"   ✅ [v4] KB ready — {self.collection.count()} stories")

    def _load_stories(self, stories_path: Path) -> None:
        print("   📚 [v4] Indexing stories into ChromaDB...")
        with open(stories_path, "r", encoding="utf-8") as f:
            stories = json.load(f)
        textos = [s["texto"] for s in stories]
        self.collection.add(
            ids=[s["id"] for s in stories],
            embeddings=self.embedder.encode(textos).tolist(),
            documents=textos,
            metadatas=[
                {"dominio": s.get("dominio", "general"), "criterios": s.get("criterios", "")}
                for s in stories
            ],
        )
        print(f"   ✅ [v4] {self.collection.count()} stories indexed")

    # ── Step 1 ───────────────────────────────────────────────────────────────
    def analyze(self, requirement: str) -> list[Ambiguity]:
        """Detecta ambigüedades en el requerimiento. Sin LLM — respuesta rápida."""
        return self.ambiguity_detector.analyze(requirement)

    # ── Step 2 ───────────────────────────────────────────────────────────────
    def process_with_resolutions(
        self,
        requirement: str,
        resolutions: list[dict],
        top_k: int = 3,
    ) -> RefinedRequirements:
        """Refina el requerimiento usando las resoluciones confirmadas por el analista.

        Args:
            requirement:  texto original del requerimiento
            resolutions:  lista de dicts {word, status, analyst_resolution}
                          status: "resolved" | "dismissed"
            top_k:        historias similares a recuperar de ChromaDB
        """
        run_id = f"run-{uuid.uuid4().hex[:8]}"

        # Enriquecer el requerimiento con aclaraciones del analista
        clarifications = [
            f"- \"{r['word']}\": {r['analyst_resolution']}"
            for r in resolutions
            if r.get("status") == "resolved" and r.get("analyst_resolution")
        ]
        requirement_enriched = (
            requirement + "\n\nACLARACIONES DEL ANALISTA:\n" + "\n".join(clarifications)
            if clarifications else requirement
        )

        # Sección del prompt con CERTEZAS del analista (assumption_made: false)
        ambiguity_section = (
            self.ambiguity_detector.build_resolved_prompt_section(resolutions)
            if resolutions else ""
        )

        # RAG — buscar historias similares
        query_emb = self.embedder.encode([requirement]).tolist()
        results = self.collection.query(
            query_embeddings=query_emb,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        historias = [
            {
                "id": results["ids"][0][i],
                "texto": results["documents"][0][i],
                "criterios": results["metadatas"][0][i].get("criterios", ""),
                "dominio": results["metadatas"][0][i].get("dominio", ""),
                "similitud": 1 - results["distances"][0][i],
            }
            for i in range(len(results["ids"][0]))
        ]

        # Construir contexto del prompt
        contexto = "## HISTORIAS DE REFERENCIA DEL SGC DE KATARY\n"
        contexto += "Usa estas historias como modelo de calidad y profundidad:\n\n"
        for i, h in enumerate(historias, 1):
            contexto += f"### Referencia {i} [{h['id']}] (similitud: {h['similitud']:.2f})\n"
            contexto += f"**Historia:** {h['texto']}\n"
            contexto += f"**Criterios:** {h['criterios']}\n"
            contexto += f"**Dominio:** {h['dominio']}\n\n"
        if ambiguity_section:
            contexto += "\n" + ambiguity_section

        system_prompt = _SYSTEM_PROMPT.format(kb_context=contexto)
        user_message = (
            f"Analiza el siguiente requerimiento y transfórmalo en historias "
            f"de usuario con el nivel de calidad de las referencias del SGC de Katary.\n\n"
            f"REQUERIMIENTO:\n{requirement_enriched}"
        )

        # Generar + validar (con reintentos)
        last_errors: list[str] = []
        for attempt in range(1, self.max_retries + 1):
            try:
                raw = (
                    self._call_llm(system_prompt, user_message)
                    if attempt == 1
                    else self._call_llm_with_retry(system_prompt, user_message, last_errors)
                )
                return self._validate_contract_a(self._extract_json(raw), requirement, run_id)
            except json.JSONDecodeError as exc:
                last_errors = [f"JSON inválido: {exc}"]
            except ValidationError as exc:
                last_errors = [e["msg"] for e in exc.errors()]
            except ValueError as exc:
                last_errors = [str(exc)]

        raise RuntimeError(
            f"El LLM no generó JSON válido en {self.max_retries} intentos. "
            f"Errores: {last_errors}"
        )

    # ── Helpers internos ─────────────────────────────────────────────────────
    def _call_llm(self, system_prompt: str, user_message: str) -> str:
        resp = self.groq_client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=self.temperature,
            max_tokens=4000,
        )
        return resp.choices[0].message.content

    def _call_llm_with_retry(self, system_prompt: str, user_message: str, errors: list[str]) -> str:
        retry = (
            f"{user_message}\n\n## CORRECCIONES REQUERIDAS\n"
            + "\n".join(f"{i}. {e}" for i, e in enumerate(errors, 1))
            + "\nCorrige TODOS los errores. SOLO JSON."
        )
        return self._call_llm(system_prompt, retry)

    def _extract_json(self, raw: str) -> dict:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].rsplit("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].rsplit("```", 1)[0]
        start, end = text.find("{"), text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No se encontró JSON válido en la respuesta del LLM")
        return json.loads(text[start:end])

    def _validate_contract_a(
        self, raw_json: dict, original_text: str, run_id: str
    ) -> RefinedRequirements:
        user_stories: list[UserStory] = []
        ac_counter = 0

        for story_data in raw_json.get("user_stories", []):
            criteria: list[AcceptanceCriterion] = []
            for ac_data in story_data.get("acceptance_criteria", []):
                ac_counter += 1
                criteria.append(AcceptanceCriterion(
                    id=ac_data.get("id", f"AC-{ac_counter:03d}"),
                    description=ac_data.get("description", ""),
                    given=ac_data.get("given", ""),
                    when=ac_data.get("when", ""),
                    then=ac_data.get("then", ""),
                    test_data_examples=ac_data.get("test_data_examples", []),
                    is_negative_case=ac_data.get("is_negative_case", False),
                    boundary_values=ac_data.get("boundary_values", []),
                ))

            ambiguities = [
                AmbiguityResolution(
                    original_text=a.get("original_text", ""),
                    issue=a.get("issue", ""),
                    resolution=a.get("resolution", ""),
                    assumption_made=a.get("assumption_made", False),
                )
                for a in story_data.get("ambiguities_resolved", [])
            ]

            try:
                story_type = StoryType(story_data.get("story_type", "functional"))
            except ValueError:
                story_type = StoryType.FUNCTIONAL
            try:
                priority = Priority(story_data.get("priority", "medium"))
            except ValueError:
                priority = Priority.MEDIUM

            user_stories.append(UserStory(
                id=story_data.get("id", f"US-{len(user_stories) + 1:03d}"),
                title=story_data.get("title", "Sin título"),
                story_type=story_type,
                priority=priority,
                as_a=story_data.get("as_a", ""),
                i_want=story_data.get("i_want", ""),
                so_that=story_data.get("so_that", ""),
                acceptance_criteria=criteria,
                business_rules=story_data.get("business_rules", []),
                dependencies=story_data.get("dependencies", []),
                ui_elements=story_data.get("ui_elements", []),
                api_endpoints=story_data.get("api_endpoints", []),
                ambiguities_resolved=ambiguities,
            ))

        if not user_stories:
            raise ValueError("El LLM no generó ninguna historia de usuario")

        total_amb = sum(len(s.ambiguities_resolved) for s in user_stories)
        total_ass = sum(
            sum(1 for a in s.ambiguities_resolved if a.assumption_made)
            for s in user_stories
        )
        return RefinedRequirements(
            pipeline_run_id=run_id,
            agent_version="4.0.0",
            original_requirements_text=original_text,
            project_context=raw_json.get("project_context", ""),
            user_stories=user_stories,
            total_ambiguities_found=total_amb,
            total_assumptions_made=total_ass,
            coverage_notes=raw_json.get("coverage_notes"),
        )
