"""TestArchitectAgent v4 — Generación de casos de test con Gemini + RAG mejorado.

Mejoras sobre M2-v3:
  - LLM: Groq/Llama → GeminiProvider (ILLMProvider inyectado)
  - RAG: coseno single-stage → HyDE + BM25 + Dense + RRF + CrossEncoder
  - JSON mode: elimina _extract_json hacks
  - Contract B: propio con rag_pattern_ids en GherkinScenario
  - Pre-filtro de domain en metadata antes de búsqueda densa
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from .base import AbstractBaseAgent
from ..contracts.contract_a import AcceptanceCriterion, RefinedRequirements, UserStory
from ..contracts.contract_b import (
    CoverageMatrix,
    GherkinFeature,
    GherkinScenario,
    GherkinStep,
    GherkinTestSuite,
    QualityCharacteristic,
    ReviewMetadata,
    ScenarioType,
)


_SYSTEM_PROMPT_TEMPLATE = """Eres un Arquitecto QA Senior de Katary Software (CMMI-DEV L3, 19 años de experiencia).
Tu misión: generar escenarios de test Gherkin exhaustivos para criterios de aceptación.

{rag_context}

## HEURÍSTICAS DE TESTING OBLIGATORIAS

### Equivalencia de Particiones (EP)
- Identifica clases válidas e inválidas para cada campo
- Genera UN escenario por clase de equivalencia
- Documenta el tag @ep en los escenarios EP

### Análisis de Valores Frontera (BVA)
- Si el AC tiene rangos (min, max, límites): genera escenarios en min-1, min, min+1, max-1, max, max+1
- Tag: @bva

### Tablas de Decisión (DT)
- Si el AC combina múltiples condiciones: genera UN escenario por combinación relevante
- Tag: @dt

### Mínimo requerido por AC:
- ≥ 1 escenario positivo (happy path)
- ≥ 1 escenario negativo (input inválido, violación de regla)
- ≥ 1 escenario de frontera (si hay rangos)
- ≥ 1 escenario de error handling (si hay estados de error)

## CLASIFICACIÓN ISO 25010 (por escenario)

Decide caso a caso. NO asignes functional_suitability por defecto:
- functional_suitability: valida lógica de negocio, reglas, cálculos
- security: autenticación, autorización, bloqueo, cifrado, inyección SQL/XSS
- performance_efficiency: tiempo de respuesta, carga concurrente, throughput
- usability: mensajes de error, accesibilidad, navegación, consistencia UI
- reliability: recuperación de fallos, timeout, consistencia de datos
- compatibility: multi-browser/OS, formatos de archivo
- maintainability / portability: raramente aplica a escenarios BDD

## FORMATO JSON OBLIGATORIO (responde SOLO con JSON):

{{
  "scenarios": [
    {{
      "name": "descripción del escenario de mínimo 10 caracteres",
      "scenario_type": "positive | negative | boundary | edge_case | error_handling",
      "quality_characteristic": "functional_suitability | security | performance_efficiency | usability | reliability | compatibility | maintainability | portability",
      "tags": ["@smoke", "@regression", "@iso-security", "@ep"],
      "heuristic_applied": "EP | BVA | DT | general",
      "steps": [
        {{"keyword": "Given", "text": "descripción de la precondición"}},
        {{"keyword": "When", "text": "descripción de la acción del usuario"}},
        {{"keyword": "Then", "text": "resultado esperado con valor concreto"}},
        {{"keyword": "And", "text": "condición adicional si aplica"}}
      ],
      "rag_pattern_ids": ["PTN-001"]
    }}
  ]
}}"""


_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "authentication": ["login", "autenticar", "contraseña", "password", "sesión", "logout", "bloqueo", "token", "jwt"],
    "form_validation": ["formulario", "campo", "validar", "formato", "requerido", "obligatorio", "correo", "email"],
    "search_filtering": ["buscar", "filtrar", "búsqueda", "filtro", "listar", "paginación", "ordenar"],
    "report_generation": ["reporte", "informe", "exportar", "pdf", "excel", "gráfica", "dashboard"],
    "file_management": ["archivo", "subir", "descargar", "upload", "download", "adjunto", "documento"],
    "notifications": ["notificación", "alerta", "email", "correo", "enviar", "avisar"],
    "user_management": ["usuario", "rol", "permiso", "perfil", "cuenta", "administrar", "admin"],
    "data_management": ["crear", "editar", "eliminar", "actualizar", "crud", "registro", "dato"],
}


class TestArchitectAgent(AbstractBaseAgent):
    """v4 del agente de arquitectura de tests. Completamente independiente de M2."""

    name = "test_architect_agent"
    version = "4.0.0"

    def process(
        self,
        contract_a: RefinedRequirements,
        **kwargs: Any,
    ) -> GherkinTestSuite:
        """Pipeline: Contract A → por-AC RAG → Gemini → Contract B."""
        features: list[GherkinFeature] = []
        coverage_matrix: list[CoverageMatrix] = []
        total_scenarios = 0
        total_positive = 0
        total_negative = 0
        total_boundary = 0
        coverage_by_char: dict[str, int] = {}
        uncovered: list[str] = []

        for story in contract_a.user_stories:
            story_scenarios: list[GherkinScenario] = []
            story_domain = self._infer_domain(story)

            for ac in story.acceptance_criteria:
                ac_scenarios = self._generate_scenarios_for_ac(ac, story, story_domain)

                if not ac_scenarios:
                    uncovered.append(ac.id)
                    continue

                story_scenarios.extend(ac_scenarios)

                # Actualizar contadores
                for s in ac_scenarios:
                    total_scenarios += 1
                    if s.scenario_type == ScenarioType.POSITIVE:
                        total_positive += 1
                    elif s.scenario_type == ScenarioType.NEGATIVE:
                        total_negative += 1
                    elif s.scenario_type == ScenarioType.BOUNDARY:
                        total_boundary += 1
                    char_key = s.quality_characteristic.value
                    coverage_by_char[char_key] = coverage_by_char.get(char_key, 0) + 1

                coverage_matrix.append(CoverageMatrix(
                    user_story_id=story.id,
                    criterion_id=ac.id,
                    scenario_names=[s.name for s in ac_scenarios],
                    coverage_type=[s.scenario_type for s in ac_scenarios],
                    quality_characteristics_covered=list({s.quality_characteristic for s in ac_scenarios}),
                ))

            if story_scenarios:
                features.append(GherkinFeature(
                    name=f"[{story.id}] {story.title}",
                    description=(
                        f"Como {story.as_a}, quiero {story.i_want}, "
                        f"para que {story.so_that}"
                    ),
                    tags=[f"@us-{story.id.lower()}", f"@{story.story_type.value}"],
                    scenarios=story_scenarios,
                    user_story_id=story.id,
                ))

        if not features:
            raise ValueError("No se generaron features. Verifica que Contract A tenga criterios válidos.")

        return GherkinTestSuite(
            pipeline_run_id=self._generate_run_id("m3-test"),
            agent_name=self.name,
            agent_version=self.version,
            features=features,
            coverage_matrix=coverage_matrix,
            review=ReviewMetadata(),
            total_scenarios=total_scenarios,
            total_positive=total_positive,
            total_negative=total_negative,
            total_boundary=total_boundary,
            uncovered_criteria=uncovered,
            coverage_by_characteristic=coverage_by_char,
        )

    def _generate_scenarios_for_ac(
        self,
        ac: AcceptanceCriterion,
        story: UserStory,
        domain: str,
    ) -> list[GherkinScenario]:
        """RAG por-AC → Gemini → escenarios Gherkin para un criterio de aceptación."""
        ac_query = f"{ac.description}. Given {ac.given}. When {ac.when}. Then {ac.then}"

        metadata_filter = {"domain": domain} if domain else None
        candidates = self._retrieve_and_rerank(
            query=ac_query,
            metadata_filter=metadata_filter,
            expand_for="patterns",
        )

        rag_context = self._build_rag_context_patterns(candidates)
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(rag_context=rag_context)
        user_message = self._build_ac_user_message(ac, story)

        pattern_ids = [
            c.get("metadata", {}).get("source_id", "")
            for c in candidates
            if c.get("metadata", {}).get("source_id")
        ]

        for attempt in range(1, self._settings.max_retries + 1):
            try:
                raw_json = self._llm.generate_json(system_prompt, user_message)
                self._llm_calls += 1
                return self._parse_scenarios(raw_json, ac, story, pattern_ids)
            except (ValidationError, ValueError, KeyError) as e:
                if attempt == self._settings.max_retries:
                    print(f"  ⚠️  No se pudieron generar escenarios para {ac.id}: {e}")
                    return []

        return []

    def _build_ac_user_message(self, ac: AcceptanceCriterion, story: UserStory) -> str:
        parts = [
            f"## Historia de Usuario: {story.id} — {story.title}",
            f"Como {story.as_a}, quiero {story.i_want}, para que {story.so_that}",
            "",
            f"## Criterio de Aceptación: {ac.id}",
            f"Descripción: {ac.description}",
            f"GIVEN: {ac.given}",
            f"WHEN: {ac.when}",
            f"THEN: {ac.then}",
        ]
        if ac.is_negative_case:
            parts.append("NOTA: Este criterio es un caso negativo/de error.")
        if ac.boundary_values:
            parts.append(f"Valores frontera: {', '.join(ac.boundary_values)}")
        if ac.test_data_examples:
            parts.append(f"Datos de prueba: {ac.test_data_examples}")
        if self._settings.eco_mode:
            parts.append(
                "\n⚡ MODO ECO: Genera EXACTAMENTE 2 escenarios: 1 positivo (happy path) + 1 negativo. "
                "No apliques BVA ni DT. Sin escenarios adicionales."
            )
        else:
            parts.append(
                "\nGenera TODOS los escenarios Gherkin necesarios aplicando EP, BVA y DT según corresponda."
            )
        return "\n".join(parts)

    def _parse_scenarios(
        self,
        raw_json: dict,
        ac: AcceptanceCriterion,
        story: UserStory,
        pattern_ids: list[str],
    ) -> list[GherkinScenario]:
        """Convierte el JSON del LLM en objetos GherkinScenario validados."""
        scenarios = []
        for s_data in raw_json.get("scenarios", []):
            if not isinstance(s_data, dict):
                continue
            steps = []
            for step_data in s_data.get("steps", []):
                if not isinstance(step_data, dict):
                    continue
                keyword = step_data.get("keyword", "Given")
                if keyword not in {"Given", "When", "Then", "And", "But"}:
                    keyword = "And"
                steps.append(GherkinStep(keyword=keyword, text=step_data.get("text", "")))

            if len(steps) < 3:
                continue  # Escenario inválido — mínimo Given/When/Then

            try:
                qc = QualityCharacteristic(s_data.get("quality_characteristic", "functional_suitability"))
            except ValueError:
                qc = QualityCharacteristic.FUNCTIONAL_SUITABILITY

            try:
                scenario_type = ScenarioType(s_data.get("scenario_type", "positive"))
            except ValueError:
                scenario_type = ScenarioType.POSITIVE

            heuristic = s_data.get("heuristic_applied", "general")
            tags = s_data.get("tags", [])
            # Agregar tag de heurística si no está
            heuristic_tag = f"@{heuristic.lower()}" if heuristic != "general" else None
            if heuristic_tag and heuristic_tag not in tags:
                tags.append(heuristic_tag)
            # Agregar tag ISO
            iso_tag = f"@iso-{qc.value.replace('_', '-')}"
            if iso_tag not in tags:
                tags.append(iso_tag)

            scenarios.append(GherkinScenario(
                name=s_data.get("name", f"Escenario {ac.id}"),
                scenario_type=scenario_type,
                quality_characteristic=qc,
                tags=tags,
                steps=steps,
                acceptance_criterion_id=ac.id,
                user_story_id=story.id,
                heuristic_applied=heuristic,
                rag_pattern_ids=pattern_ids,
            ))

        return scenarios

    def _infer_domain(self, story: UserStory) -> str:
        """Heurística: infiere el dominio de la historia para pre-filtrar el KB."""
        text = f"{story.title} {story.as_a} {story.i_want} {story.so_that}".lower()
        for domain, keywords in _DOMAIN_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return domain
        return ""
