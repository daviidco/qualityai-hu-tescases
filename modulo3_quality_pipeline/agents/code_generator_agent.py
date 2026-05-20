"""CodeGeneratorAgent v1 — Contract B (Gherkin) → Contract D (código Python + Pytest).

Extiende AbstractBaseAgent para usar el stack RAG avanzado del pipeline
(HyDE + BM25 + Dense + RRF + CrossEncoder) con la KB Katary de patrones de código,
en lugar del SentenceTransformer simple de la versión educativa.

Transformación:
  Por cada Feature en GherkinTestSuite:
    1. RAG sobre Katary KB → patrones de código relevantes al dominio
    2. LLM (JSON mode) → GeneratedCodeModule + GeneratedTest
  Resultado: CodeGenerationResult con generated_code[] + generated_tests[]
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from .base import AbstractBaseAgent
from ..contracts.contract_b import GherkinFeature, GherkinTestSuite
from ..contracts.contract_d import (
    CodeGenerationResult,
    GeneratedCodeModule,
    GeneratedTest,
)

_SYSTEM_PROMPT = """\
Eres un senior Python developer en Katary Software con 10+ años de experiencia.
Tu tarea es generar código Python limpio y tests Pytest a partir de escenarios Gherkin.

REGLAS OBLIGATORIAS:
1. Genera exactamente UN módulo Python y UN archivo de test por feature.
2. El código debe ser pythónico, con type hints, docstrings concisos y sin comentarios obvios.
3. Los tests deben incluir el decorador @pytest.mark.scenario("<scenario_id>") en cada función
   de test para mantener trazabilidad CMMI L3.
4. Usa nombres descriptivos que reflejen el dominio del negocio.
5. No dependencias externas más allá de la stdlib y pytest.
6. Umbrales de calidad: CC < 10 (funciones simples), sin lógica anidada innecesaria.

PATRONES DE CÓDIGO DE REFERENCIA (base de conocimiento Katary):
{rag_context}

Responde SOLO con JSON válido en este esquema exacto:
{{
  "filename": "nombre_del_modulo.py",
  "source_code": "código Python completo del módulo",
  "description": "descripción de 1-2 frases del módulo",
  "test_name": "test_nombre_del_modulo.py",
  "test_source_code": "código completo del archivo de tests Pytest",
  "scenario_ids": ["lista", "de", "scenario", "ids", "cubiertos"]
}}
"""

_ECO_SYSTEM_PROMPT = """\
Eres un senior Python developer. Genera código Python y tests Pytest mínimos
(función principal + 1 test positivo + 1 test negativo) para los escenarios Gherkin dados.

PATRONES DE REFERENCIA:
{rag_context}

Responde SOLO con JSON:
{{
  "filename": "modulo.py",
  "source_code": "código Python",
  "description": "descripción breve",
  "test_name": "test_modulo.py",
  "test_source_code": "tests Pytest con @pytest.mark.scenario",
  "scenario_ids": ["ids de escenarios cubiertos"]
}}
"""


class CodeGeneratorAgent(AbstractBaseAgent[GherkinTestSuite, CodeGenerationResult]):
    """Stage 3: genera módulos Python + tests Pytest a partir de Contract B."""

    name = "code_generator_agent"
    version = "1.0.0"

    def process(self, contract_b: GherkinTestSuite, **kwargs: Any) -> CodeGenerationResult:
        """Procesa cada feature del test suite y genera código + tests correspondientes."""
        features = contract_b.features
        if self._settings.eco_mode:
            features = features[:2]

        generated_code: list[GeneratedCodeModule] = []
        generated_tests: list[GeneratedTest] = []

        print(f"\n  [CodeGeneratorAgent] Procesando {len(features)} feature(s)...")

        for i, feature in enumerate(features, 1):
            print(f"    [{i}/{len(features)}] {feature.name[:60]}")
            try:
                module, test = self._generate_for_feature(feature)
                generated_code.append(module)
                generated_tests.append(test)
            except Exception as exc:  # noqa: BLE001
                print(f"    ⚠️  Error en feature '{feature.name}': {exc}")

        result = CodeGenerationResult(
            source_contract_b_id=contract_b.pipeline_run_id,
            generated_code=generated_code,
            generated_tests=generated_tests,
            total_modules=len(generated_code),
            total_tests=len(generated_tests),
        )
        print(f"  ✅ {result.total_modules} módulos + {result.total_tests} archivos de test generados")
        return result

    def _generate_for_feature(
        self, feature: GherkinFeature
    ) -> tuple[GeneratedCodeModule, GeneratedTest]:
        """RAG → LLM → parse para una feature Gherkin."""
        # Construir query a partir del nombre + descripción + primera historia
        query = f"{feature.name}. {feature.description}"
        if feature.scenarios:
            first = feature.scenarios[0]
            query += f" {' '.join(s.text for s in first.steps[:3])}"

        candidates = self._retrieve_and_rerank(query, expand_for="patterns")
        rag_context = self._build_rag_context_code_patterns(candidates)

        prompt = (_ECO_SYSTEM_PROMPT if self._settings.eco_mode else _SYSTEM_PROMPT)
        system = prompt.format(rag_context=rag_context)
        user_msg = self._build_user_message(feature)

        raw = self._llm.generate_json(system, user_msg)
        self._llm_calls += 1

        return self._parse_response(raw, feature)

    def _build_user_message(self, feature: GherkinFeature) -> str:
        """Serializa la feature Gherkin para el prompt del usuario."""
        lines = [f"Feature: {feature.name}", f"  {feature.description}", ""]
        for scenario in feature.scenarios:
            lines.append(f"  Scenario: {scenario.name}")
            lines.append(f"  # {scenario.quality_characteristic.value} | {scenario.heuristic_applied}")
            lines.append(f"  # ID: {scenario.acceptance_criterion_id}")
            for step in scenario.steps:
                lines.append(f"    {step.keyword} {step.text}")
            lines.append("")
        return "\n".join(lines)

    def _build_rag_context_code_patterns(self, candidates: list[dict[str, Any]]) -> str:
        """Formatea candidatos de la KB Katary de código para el system prompt."""
        if not candidates:
            return "Sin patrones de referencia disponibles."
        parts = []
        for i, c in enumerate(candidates, 1):
            score = c.get("rerank_score", c.get("rrf_score", 0.0))
            meta = c.get("metadata", {})
            parts.append(
                f"[Patrón {i} | Dominio: {meta.get('domain', 'N/A')} "
                f"| Relevancia: {score:.3f}]\n{c['document']}"
            )
        return "\n\n".join(parts)

    def _parse_response(
        self, raw: dict[str, Any], feature: GherkinFeature
    ) -> tuple[GeneratedCodeModule, GeneratedTest]:
        """Convierte la respuesta JSON del LLM en modelos Pydantic validados."""
        # Extraer scenario_ids de los escenarios de la feature si el LLM no los proporcionó
        default_ids = [s.acceptance_criterion_id for s in feature.scenarios]

        filename = raw.get("filename") or f"{feature.name.lower().replace(' ', '_')}.py"
        source_code = raw.get("source_code", "# código no generado")
        description = raw.get("description", feature.description[:100])
        test_name = raw.get("test_name") or f"test_{filename}"
        test_source = raw.get("test_source_code", "# tests no generados")
        scenario_ids = raw.get("scenario_ids") or default_ids

        if not filename.endswith(".py"):
            filename += ".py"
        if not test_name.endswith(".py"):
            test_name += ".py"

        module = GeneratedCodeModule(
            filename=filename,
            source_code=source_code,
            description=description,
            user_story_id=feature.user_story_id,
        )
        test = GeneratedTest(
            test_name=test_name,
            source_code=test_source,
            scenario_ids=list(scenario_ids),
            target_module=filename,
        )
        return module, test
