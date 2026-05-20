"""RequirementsAgent v5 — Refinamiento de requerimientos con HITL + Gemini + RAG mejorado.

Mejoras sobre M1-v4:
  - LLM: Groq/Llama → GeminiProvider (ILLMProvider inyectado)
  - RAG: coseno single-stage → HyDE + BM25 + Dense + RRF + CrossEncoder
  - JSON mode: elimina _extract_json hacks
  - AmbiguityDetector: propio de M3 con suggest_metric()
  - Contract A: propio con rag_sources y confidence_score
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from .base import AbstractBaseAgent
from ..analysis.ambiguity_detector import Ambiguity, AmbiguityDetector
from ..contracts.contract_a import (
    AcceptanceCriterion,
    AmbiguityResolution,
    Priority,
    RefinedRequirements,
    StoryType,
    UserStory,
)


_ECO_CONSTRAINTS = """\
## ⚡ MODO ECO ACTIVO — Minimiza el uso de tokens

REGLAS ESTRICTAS (no negociables):
1. Genera MÁXIMO 3 historias de usuario (las de prioridad critical/high primero).
2. Cada historia tendrá EXACTAMENTE 2 criterios de aceptación: 1 positivo + 1 negativo.
3. Mantén todos los campos obligatorios del JSON pero con valores concisos.
4. Si el requerimiento genera más de 3 historias naturalmente, consolida en 3.
"""


_SYSTEM_PROMPT_TEMPLATE = """Eres un Analista de Requerimientos Senior de Katary Software (CMMI-DEV L3, 19 años de experiencia).
Tu misión: transformar requerimientos ambiguos en historias de usuario estructuradas (IEEE 830 / ISO 25010).

{rag_context}

{eco_section}{ambiguity_section}

## INSTRUCCIONES OBLIGATORIAS

1. NUNCA hagas suposiciones — si algo es ambiguo y no fue resuelto, anótalo en coverage_notes
2. Genera MÁXIMO 5 historias de usuario (las más importantes; consolida si hay más)
3. Cada historia tendrá entre 2 y 3 criterios de aceptación (1 positivo + 1 negativo es suficiente)
4. Los IDs siguen el patrón US-001, US-002... y AC-001, AC-002... (contador global)
5. Los criterios deben tener valores concretos y verificables (números, tiempos, límites)
6. Descripciones CONCISAS — una oración por campo, sin repetir información

## FORMATO JSON OBLIGATORIO (responde SOLO con JSON válido):

{{
  "project_context": "descripción breve del proyecto",
  "user_stories": [
    {{
      "id": "US-001",
      "title": "título descriptivo",
      "story_type": "functional | non_functional | technical",
      "priority": "critical | high | medium | low",
      "as_a": "rol del usuario",
      "i_want": "acción concreta",
      "so_that": "beneficio verificable",
      "acceptance_criteria": [
        {{
          "id": "AC-001",
          "description": "descripción concisa",
          "given": "precondición",
          "when": "acción",
          "then": "resultado con métrica concreta",
          "is_negative_case": false,
          "boundary_values": []
        }}
      ],
      "business_rules": ["regla concreta"],
      "ambiguities_resolved": [
        {{
          "original_text": "texto ambiguo",
          "issue": "razón de ambigüedad",
          "resolution": "resolución con valores concretos",
          "assumption_made": false,
          "confidence_score": 1.0
        }}
      ],
      "rag_sources": ["SGC-US-001"]
    }}
  ],
  "coverage_notes": null
}}"""


class RequirementsAgent(AbstractBaseAgent):
    """v5 del agente de refinamiento de requerimientos. Completamente independiente de M1."""

    name = "requirements_agent"
    version = "5.0.0"

    def __init__(self, llm, retriever, reranker, settings) -> None:
        super().__init__(llm, retriever, reranker, settings)
        self._ambiguity_detector = AmbiguityDetector()

    def process(
        self,
        requirement: str,
        interactive: bool = True,
    ) -> RefinedRequirements:
        """Pipeline completo: detectar ambigüedades → HITL → RAG → Gemini → Contract A."""
        run_id = self._generate_run_id("m3-req")

        # Paso 1: Detectar ambigüedades
        ambiguities = self._ambiguity_detector.analyze(requirement)
        if ambiguities:
            print(f"\n📊 {len(ambiguities)} ambigüedades detectadas en el requerimiento.")

        # Paso 2: HITL — revisión del analista
        resolved_section = ""
        resolutions: list[dict] = []
        if ambiguities and interactive:
            resolutions = self._review_ambiguities_with_analyst(ambiguities)
            resolved_section = self._ambiguity_detector.build_resolved_prompt_section(resolutions)
        elif ambiguities and not interactive:
            # Modo automático: LLM resuelve, se marca assumption_made=True
            resolved_section = self._ambiguity_detector.build_prompt_section(ambiguities)

        # Paso 3: RAG — recuperar historias similares
        candidates = self._retrieve_and_rerank(requirement, expand_for="stories")

        # Paso 4: Construir prompt e invocar Gemini
        rag_context = self._build_rag_context_stories(candidates)
        eco_section = _ECO_CONSTRAINTS if self._settings.eco_mode else ""
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            rag_context=rag_context,
            eco_section=eco_section,
            ambiguity_section=resolved_section or "## SIN AMBIGÜEDADES DETECTADAS\nProcede con la refinación directa.",
        )

        # Paso 5-6: Llamar LLM y validar con reintentos
        contract_a = self._call_with_retry(
            system_prompt=system_prompt,
            user_message=requirement,
            original_text=requirement,
            run_id=run_id,
            ambiguities=ambiguities,
        )
        return contract_a

    def detect_ambiguities(self, requirement: str) -> list[Ambiguity]:
        """Solo detecta ambigüedades, sin llamar al LLM. Para el paso 1 del HITL web."""
        return self._ambiguity_detector.analyze(requirement)

    def process_with_resolutions(
        self,
        requirement: str,
        analyst_resolutions: list[dict],
    ) -> RefinedRequirements:
        """HITL web: mismo flujo que process(interactive=True) pero las resoluciones
        provienen del frontend en vez de input() en CLI.

        analyst_resolutions: list de dicts {word, category, analyst_resolution, status}
        """
        # Reset provider chain so each web request starts from the highest-priority provider.
        if hasattr(self._llm, "reset_skip"):
            self._llm.reset_skip()

        run_id = self._generate_run_id("m3-req")
        ambiguities = self._ambiguity_detector.analyze(requirement)

        if analyst_resolutions:
            resolved_section = self._ambiguity_detector.build_resolved_prompt_section(
                analyst_resolutions
            )
        elif ambiguities:
            resolved_section = self._ambiguity_detector.build_prompt_section(ambiguities)
        else:
            resolved_section = ""

        candidates = self._retrieve_and_rerank(requirement, expand_for="stories")
        rag_context = self._build_rag_context_stories(candidates)
        eco_section = _ECO_CONSTRAINTS if self._settings.eco_mode else ""
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            rag_context=rag_context,
            eco_section=eco_section,
            ambiguity_section=resolved_section or "## SIN AMBIGÜEDADES DETECTADAS\nProcede con la refinación directa.",
        )
        return self._call_with_retry(
            system_prompt=system_prompt,
            user_message=requirement,
            original_text=requirement,
            run_id=run_id,
            ambiguities=ambiguities,
        )

    def _review_ambiguities_with_analyst(self, ambiguities: list[Ambiguity]) -> list[dict]:
        """HITL: presenta ambigüedades al analista con 3 opciones."""
        resolutions = []
        print("\n" + "=" * 60)
        print("🔍 REVISIÓN DE AMBIGÜEDADES — Analista QA")
        print("=" * 60)

        for i, ambiguity in enumerate(ambiguities, 1):
            print(f"\n[{i}/{len(ambiguities)}] Ambigüedad DETECTADA:")
            print(f"  Palabra:    '{ambiguity.word}' [{ambiguity.severity.upper()}]")
            print(f"  Categoría:  {ambiguity.category}")
            print(f"  IEEE 830:   {ambiguity.ieee_830_violation}")
            print(f"  ISO 25010:  {ambiguity.iso_25010_category}")
            print(f"  Contexto:   {ambiguity.context}")
            print(f"  Sugerencia: {ambiguity.suggestion}")
            print(f"  Métrica:    {self._ambiguity_detector.suggest_metric(ambiguity.word)}")
            print("\n  Opciones:")
            print(f"  [1] Aceptar resolución sugerida: \"{ambiguity.suggestion}\"")
            print("  [2] Ingresar resolución personalizada")
            print("  [3] Descartar (no es ambigua en este contexto)")

            while True:
                choice = input("\n  Selecciona [1/2/3]: ").strip()
                if choice == "1":
                    resolutions.append({
                        "word": ambiguity.word,
                        "category": ambiguity.category,
                        "analyst_resolution": ambiguity.suggestion,
                        "status": "accepted",
                        "confidence_score": 1.0,
                    })
                    print(f"  ✅ Resolución aceptada: {ambiguity.suggestion}")
                    break
                elif choice == "2":
                    custom = input("  Ingresa tu resolución: ").strip()
                    if custom:
                        resolutions.append({
                            "word": ambiguity.word,
                            "category": ambiguity.category,
                            "analyst_resolution": custom,
                            "status": "custom",
                            "confidence_score": 1.0,
                        })
                        print(f"  ✅ Resolución personalizada: {custom}")
                    break
                elif choice == "3":
                    print(f"  ⏭️  Descartada — '{ambiguity.word}' no es ambigua en este contexto")
                    break
                else:
                    print("  ❌ Opción inválida. Ingresa 1, 2 o 3.")

        return resolutions

    def _call_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        original_text: str,
        run_id: str,
        ambiguities: list[Ambiguity],
    ) -> RefinedRequirements:
        """Llama al LLM con reintentos en caso de error de validación Pydantic."""
        last_error: str = ""
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                if attempt > 1:
                    retry_prompt = (
                        system_prompt
                        + f"\n\n## ERROR EN INTENTO ANTERIOR — CORRIGE:\n{last_error}"
                    )
                else:
                    retry_prompt = system_prompt

                raw_json = self._llm.generate_json(retry_prompt, user_message)
                self._llm_calls += 1
                return self._parse_contract_a(raw_json, original_text, run_id, len(ambiguities))

            except (ValidationError, ValueError, KeyError) as e:
                last_error = str(e)
                print(f"  ⚠️  Intento {attempt}/{self._settings.max_retries} fallido: {last_error[:100]}")
                # Advance to the next provider in the chain so the next retry uses a
                # different LLM — the current one returned structurally valid but
                # semantically incomplete JSON (e.g. acceptance_criteria: []).
                if hasattr(self._llm, "skip_current"):
                    self._llm.skip_current()

        raise RuntimeError(
            f"No se pudo generar Contract A válido tras {self._settings.max_retries} intentos. "
            f"Último error: {last_error}"
        )

    def _parse_contract_a(
        self,
        raw_json: dict[str, Any],
        original_text: str,
        run_id: str,
        total_ambiguities: int,
    ) -> RefinedRequirements:
        """Construye RefinedRequirements desde el dict JSON del LLM.

        Robusto ante JSON truncado: omite historias/criterios incompletos en lugar
        de fallar toda la operación. Solo lanza ValueError si no hay ninguna historia.
        """
        stories: list[UserStory] = []
        total_assumptions = 0

        for us_data in raw_json.get("user_stories", []):
            us_id = us_data.get("id", "").strip()
            if not us_id:
                continue  # historia truncada sin ID — omitir

            try:
                criteria = []
                for ac_data in us_data.get("acceptance_criteria", []):
                    ac_id = ac_data.get("id", "").strip()
                    if not ac_id:
                        continue
                    try:
                        criteria.append(AcceptanceCriterion(
                            id=ac_id,
                            description=ac_data.get("description", ""),
                            given=ac_data.get("given", ""),
                            when=ac_data.get("when", ""),
                            then=ac_data.get("then", ""),
                            test_data_examples=ac_data.get("test_data_examples", []),
                            is_negative_case=ac_data.get("is_negative_case", False),
                            boundary_values=ac_data.get("boundary_values", []),
                        ))
                    except Exception:
                        continue  # criterio malformado — omitir

                # Skip stories whose criteria were all filtered out — creating
                # UserStory with acceptance_criteria=[] would fail Pydantic validation.
                if not criteria:
                    print(f"  ⚠️  Historia {us_id} omitida: sin criterios de aceptación válidos")
                    continue

                resolutions = []
                for r_data in us_data.get("ambiguities_resolved", []):
                    try:
                        assumption = r_data.get("assumption_made", False)
                        if assumption:
                            total_assumptions += 1
                        resolutions.append(AmbiguityResolution(
                            original_text=r_data.get("original_text", ""),
                            issue=r_data.get("issue", ""),
                            resolution=r_data.get("resolution", ""),
                            assumption_made=assumption,
                            confidence_score=float(
                                r_data.get("confidence_score", 0.5 if assumption else 1.0)
                            ),
                        ))
                    except Exception:
                        continue

                stories.append(UserStory(
                    id=us_id,
                    title=us_data.get("title", us_id),
                    story_type=StoryType(us_data.get("story_type", "functional")),
                    priority=Priority(us_data.get("priority", "medium")),
                    as_a=us_data.get("as_a", "usuario"),
                    i_want=us_data.get("i_want", ""),
                    so_that=us_data.get("so_that", ""),
                    acceptance_criteria=criteria,
                    business_rules=us_data.get("business_rules", []),
                    dependencies=us_data.get("dependencies", []),
                    ui_elements=us_data.get("ui_elements", []),
                    api_endpoints=us_data.get("api_endpoints", []),
                    ambiguities_resolved=resolutions,
                    rag_sources=us_data.get("rag_sources", []),
                ))
            except Exception as exc:
                print(f"  ⚠️  Historia {us_id} omitida por datos incompletos: {exc}")
                continue

        if not stories:
            raise ValueError(
                "El LLM no generó ninguna historia de usuario válida. "
                "El JSON puede estar completamente truncado."
            )

        return RefinedRequirements(
            pipeline_run_id=run_id,
            agent_name=self.name,
            agent_version=self.version,
            original_requirements_text=original_text,
            project_context=raw_json.get("project_context", ""),
            user_stories=stories,
            total_ambiguities_found=total_ambiguities,
            total_assumptions_made=total_assumptions,
            coverage_notes=raw_json.get("coverage_notes"),
        )
