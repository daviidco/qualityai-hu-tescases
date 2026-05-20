"""QualityPipeline — pipeline secuencial de calidad.

Pipeline fijo: RequirementsAgent → TestArchitectAgent → Reporter.
No enruta dinámicamente ni coordina agentes en paralelo — eso sería
un orquestador. Este módulo simplemente secuencia etapas en orden fijo
y transfiere el estado entre ellas (Contract A → Contract B → Contract C).

Responsabilidades (SOLID-S):
  - Secuenciar etapas
  - Transferir estado entre agentes (Contract A → Contract B)
  - Medir tiempos y construir Contract C (ExecutiveReport)
  - Persistir artefactos en disco

NO hace:
  - Llamadas LLM directas
  - Retrieval o reranking
  - Generación HTML
  - Parsing JSON
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from typing import TYPE_CHECKING, Optional

from .agents.requirements_agent import RequirementsAgent
from .agents.test_architect_agent import TestArchitectAgent
from .config import Settings
from .contracts.contract_a import RefinedRequirements
from .contracts.contract_b import (
    GherkinTestSuite,
    QualityCharacteristic,
    ReviewChange,
    ReviewStatus,
)
from .contracts.contract_c import (
    CodeGenerationSummary,
    ExecutiveReport,
    PipelineStageRecord,
    PipelineStageStatus,
    QualityInsight,
    RAGMetrics,
    RequirementsExecutiveSummary,
    TestSuiteExecutiveSummary,
)
from .contracts.contract_d import CodeGenerationResult, SecuritySeverity
from .reporting.interfaces import IReportGenerator

if TYPE_CHECKING:
    from .agents.code_generator_agent import CodeGeneratorAgent
    from .agents.static_analysis_agent import StaticAnalysisAgent
    from .agents.traceability_agent import TraceabilityAgent
    from .agents.code_review_agent import CodeReviewAgent


class QualityPipeline:
    """Pipeline secuencial de calidad. Solo secuencia etapas y gestiona estado (SOLID-S)."""

    def __init__(
        self,
        requirements_agent: RequirementsAgent,
        test_agent: TestArchitectAgent,
        reporter: IReportGenerator,
        settings: Settings,
        code_agent: Optional["CodeGeneratorAgent"] = None,
        static_agent: Optional["StaticAnalysisAgent"] = None,
        traceability_agent: Optional["TraceabilityAgent"] = None,
        review_agent: Optional["CodeReviewAgent"] = None,
    ) -> None:
        self._req_agent = requirements_agent
        self._test_agent = test_agent
        self._reporter = reporter
        self._settings = settings
        self._code_agent = code_agent
        self._static_agent = static_agent
        self._traceability_agent = traceability_agent
        self._review_agent = review_agent

    def swap_llm(self, new_settings: "Settings") -> None:
        """Reemplaza el proveedor LLM sin reconstruir la RAG stack (ChromaDB/CrossEncoder)."""
        from .llm.factory import create_llm
        new_llm = create_llm(new_settings)
        self.swap_llm_provider(new_llm, new_settings)

    def swap_llm_provider(
        self,
        provider: "ILLMProvider",
        settings: "Settings | None" = None,
    ) -> None:
        """Hot-swap directo de un ILLMProvider (p.ej. FallbackLLMProvider desde MongoDB)."""
        from .llm.interfaces import ILLMProvider  # import local para evitar circular
        self._req_agent._llm = provider
        self._test_agent._llm = provider
        self._req_agent._retriever._expander._llm = provider
        self._test_agent._retriever._expander._llm = provider
        if self._code_agent is not None:
            self._code_agent._llm = provider
            self._code_agent._retriever._expander._llm = provider
        if settings is not None:
            self._req_agent._settings = settings
            self._test_agent._settings = settings
            if self._code_agent is not None:
                self._code_agent._settings = settings
            self._settings = settings

    def run(
        self,
        requirement: str,
        interactive: bool = True,
        reviewer_name: str = "",
    ) -> dict[str, str]:
        """Ejecuta el pipeline completo. Devuelve paths de todos los artefactos."""
        output_dir = Path(self._settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stages: list[PipelineStageRecord] = []
        pipeline_start = datetime.now()

        # ── Etapa 1: Refinamiento de requerimientos ──────────────────────────
        print("\n" + "=" * 60)
        print("🔬 ETAPA 1: Refinamiento de Requerimientos")
        print("=" * 60)
        stage1 = PipelineStageRecord(stage_name="requirements_refinement")
        t0 = datetime.now()
        try:
            contract_a = self._req_agent.process(requirement, interactive=interactive)
            stage1.status = PipelineStageStatus.SUCCESS
            stage1.llm_calls = self._req_agent.metrics["llm_calls"]
            stage1.rag_retrievals = self._req_agent.metrics["rag_retrievals"]
        except Exception as exc:
            stage1.status = PipelineStageStatus.FAILED
            stage1.errors.append(str(exc))
            stage1.completed_at = datetime.now()
            stage1.duration_seconds = (stage1.completed_at - t0).total_seconds()
            stages.append(stage1)
            raise
        stage1.completed_at = datetime.now()
        stage1.duration_seconds = (stage1.completed_at - t0).total_seconds()
        stages.append(stage1)

        contract_a_path = output_dir / f"contract_a_{contract_a.pipeline_run_id}.json"
        self._save_model(contract_a, contract_a_path)
        print(f"  ✅ Contract A guardado: {contract_a_path.name}")

        # ── Etapa 2: Generación de casos de test ─────────────────────────────
        print("\n" + "=" * 60)
        print("🧪 ETAPA 2: Generación de Casos de Test")
        print("=" * 60)
        stage2 = PipelineStageRecord(stage_name="test_generation")
        t0 = datetime.now()
        try:
            contract_b = self._test_agent.process(contract_a)
            stage2.status = PipelineStageStatus.SUCCESS
            stage2.llm_calls = self._test_agent.metrics["llm_calls"]
            stage2.rag_retrievals = self._test_agent.metrics["rag_retrievals"]
        except Exception as exc:
            stage2.status = PipelineStageStatus.FAILED
            stage2.errors.append(str(exc))
            stage2.completed_at = datetime.now()
            stage2.duration_seconds = (stage2.completed_at - t0).total_seconds()
            stages.append(stage2)
            raise
        stage2.completed_at = datetime.now()
        stage2.duration_seconds = (stage2.completed_at - t0).total_seconds()
        stages.append(stage2)

        if interactive:
            contract_b = self._review_contract_b(contract_b, reviewer_name)

        contract_b_path = output_dir / f"contract_b_{contract_b.pipeline_run_id}.json"
        self._save_model(contract_b, contract_b_path)
        print(f"  ✅ Contract B guardado: {contract_b_path.name}")

        # ── Etapa 3: Generación de código (CodeGeneratorAgent) ───────────────
        contract_d: CodeGenerationResult | None = None
        if self._code_agent is not None:
            print("\n" + "=" * 60)
            print("🤖 ETAPA 3: Generación de Código Python")
            print("=" * 60)
            stage3 = PipelineStageRecord(stage_name="code_generation")
            t0 = datetime.now()
            try:
                contract_d = self._code_agent.process(contract_b)
                stage3.status = PipelineStageStatus.SUCCESS
                stage3.llm_calls = self._code_agent.metrics["llm_calls"]
                stage3.rag_retrievals = self._code_agent.metrics["rag_retrievals"]
            except Exception as exc:  # noqa: BLE001
                stage3.status = PipelineStageStatus.FAILED
                stage3.errors.append(str(exc))
                print(f"  ⚠️  Stage 3 falló: {exc}")
            stage3.completed_at = datetime.now()
            stage3.duration_seconds = (stage3.completed_at - t0).total_seconds()
            stages.append(stage3)
        else:
            stages.append(PipelineStageRecord(
                stage_name="code_generation", status=PipelineStageStatus.SKIPPED,
            ))

        # ── Etapa 4: Análisis estático (StaticAnalysisAgent) ─────────────────
        if contract_d is not None and self._static_agent is not None:
            print("\n" + "=" * 60)
            print("🔬 ETAPA 4: Análisis Estático de Código")
            print("=" * 60)
            stage4 = PipelineStageRecord(stage_name="static_analysis")
            t0 = datetime.now()
            try:
                contract_d = self._static_agent.analyze(contract_d)
                stage4.status = PipelineStageStatus.SUCCESS
            except Exception as exc:  # noqa: BLE001
                stage4.status = PipelineStageStatus.FAILED
                stage4.errors.append(str(exc))
                print(f"  ⚠️  Stage 4 falló: {exc}")
            stage4.completed_at = datetime.now()
            stage4.duration_seconds = (stage4.completed_at - t0).total_seconds()
            stages.append(stage4)
        else:
            stages.append(PipelineStageRecord(
                stage_name="static_analysis", status=PipelineStageStatus.SKIPPED,
            ))

        # ── Etapa 5: Trazabilidad CMMI L3 + cobertura (TraceabilityAgent) ────
        if contract_d is not None and self._traceability_agent is not None:
            print("\n" + "=" * 60)
            print("🗺  ETAPA 5: Trazabilidad CMMI L3 + Branch Coverage")
            print("=" * 60)
            stage5 = PipelineStageRecord(stage_name="traceability")
            t0 = datetime.now()
            try:
                contract_d = self._traceability_agent.trace(contract_d, contract_b)
                stage5.status = PipelineStageStatus.SUCCESS
            except Exception as exc:  # noqa: BLE001
                stage5.status = PipelineStageStatus.FAILED
                stage5.errors.append(str(exc))
                print(f"  ⚠️  Stage 5 falló: {exc}")
            stage5.completed_at = datetime.now()
            stage5.duration_seconds = (stage5.completed_at - t0).total_seconds()
            stages.append(stage5)
        else:
            stages.append(PipelineStageRecord(
                stage_name="traceability", status=PipelineStageStatus.SKIPPED,
            ))

        # ── Etapa 6: Revisión HITL senior developer (solo interactive) ───────
        if contract_d is not None and self._review_agent is not None and interactive:
            print("\n" + "=" * 60)
            print("👨‍💻 ETAPA 6: Revisión de Código (Senior Developer)")
            print("=" * 60)
            stage6 = PipelineStageRecord(stage_name="code_review")
            t0 = datetime.now()
            try:
                contract_d = self._review_agent.review(contract_d, reviewer_name)
                stage6.status = PipelineStageStatus.SUCCESS
            except Exception as exc:  # noqa: BLE001
                stage6.status = PipelineStageStatus.FAILED
                stage6.errors.append(str(exc))
                print(f"  ⚠️  Stage 6 falló: {exc}")
            stage6.completed_at = datetime.now()
            stage6.duration_seconds = (stage6.completed_at - t0).total_seconds()
            stages.append(stage6)
        else:
            stages.append(PipelineStageRecord(
                stage_name="code_review", status=PipelineStageStatus.SKIPPED,
            ))

        # Persistir Contract D si fue generado
        contract_d_path = None
        if contract_d is not None:
            contract_d_path = output_dir / f"contract_d_{contract_d.pipeline_run_id}.json"
            self._save_model(contract_d, contract_d_path)
            print(f"\n  ✅ Contract D guardado: {contract_d_path.name}")

        # ── Etapa 7: Construir Contract C + reporte HTML ──────────────────────
        print("\n" + "=" * 60)
        print("📊 ETAPA 7: Generación de Reporte Ejecutivo")
        print("=" * 60)
        total_duration = (datetime.now() - pipeline_start).total_seconds()
        contract_c = self._build_contract_c(
            contract_a=contract_a,
            contract_b=contract_b,
            stages=stages,
            total_duration=total_duration,
            contract_a_path=str(contract_a_path),
            contract_b_path=str(contract_b_path),
            contract_d=contract_d,
        )
        contract_c_path = output_dir / f"contract_c_{contract_c.pipeline_run_id}.json"
        self._save_model(contract_c, contract_c_path)
        print(f"  ✅ Contract C guardado: {contract_c_path.name}")

        report_path = output_dir / f"report_{contract_c.pipeline_run_id}.html"
        self._reporter.generate(contract_a, contract_b, contract_c, report_path)

        print("\n" + "=" * 60)
        print(f"🎉 Pipeline completado en {total_duration:.1f}s")
        print("=" * 60)

        total_acs = sum(len(s.acceptance_criteria) for s in contract_a.user_stories)
        html_content = report_path.read_text(encoding="utf-8")
        return {
            "pipeline_run_id": contract_c.pipeline_run_id,
            "contract_a": str(contract_a_path),
            "contract_b": str(contract_b_path),
            "contract_c": str(contract_c_path),
            "report_html": str(report_path),
            "html_content": html_content,
            "report_data": self._build_report_data(contract_a, contract_b, contract_c, self._settings.eco_mode),
            "summary": {
                "total_stories": len(contract_a.user_stories),
                "total_acceptance_criteria": total_acs,
                "total_scenarios": contract_b.total_scenarios,
                "coverage_pct": int(contract_c.requirements_to_test_coverage_ratio * 100),
                "total_ambiguities": contract_a.total_ambiguities_found,
                "duration_seconds": round(total_duration, 1),
                "llm_provider": contract_c.llm_provider,
                "created_at": contract_c.created_at.isoformat(),
            },
        }

    # ── Métodos para HITL web (3 fases separadas) ────────────────────────────

    def generate_code_from_features(self, features: list[dict]) -> dict:
        """Reconstruye GherkinTestSuite a partir de features serializadas y genera código."""
        from .contracts.contract_b import (
            GherkinFeature, GherkinScenario, GherkinStep,
            GherkinTestSuite, ScenarioType, QualityCharacteristic,
        )

        if self._code_agent is None:
            raise RuntimeError("CodeGeneratorAgent no disponible en este pipeline")

        reconstructed: list[GherkinFeature] = []
        for f in features:
            uid = f.get("user_story_id", "")
            raw_scenarios = f.get("scenarios") or []
            scenarios: list[GherkinScenario] = []
            for sc in raw_scenarios:
                steps_raw = sc.get("steps") or []
                steps = [
                    GherkinStep(keyword=s.get("keyword", "Given"), text=s.get("text", "the action is performed"))
                    for s in steps_raw
                ]
                while len(steps) < 3:
                    steps.append(GherkinStep(keyword="And", text="the system responds correctly"))
                name = sc.get("name", "Scenario")
                if len(name) < 10:
                    name = f"{name} (escenario)"
                try:
                    stype = ScenarioType(sc.get("scenario_type", "positive"))
                except ValueError:
                    stype = ScenarioType.POSITIVE
                try:
                    qchar = QualityCharacteristic(sc.get("quality_characteristic", "functional_suitability"))
                except ValueError:
                    qchar = QualityCharacteristic.FUNCTIONAL_SUITABILITY
                scenarios.append(GherkinScenario(
                    name=name,
                    scenario_type=stype,
                    quality_characteristic=qchar,
                    tags=sc.get("tags") or [],
                    steps=steps,
                    acceptance_criterion_id=sc.get("acceptance_criterion_id", ""),
                    user_story_id=uid,
                    heuristic_applied=sc.get("heuristic_applied", "general"),
                ))
            if not scenarios:
                continue
            reconstructed.append(GherkinFeature(
                name=f.get("name", "Feature"),
                description=f.get("description", ""),
                scenarios=scenarios,
                user_story_id=uid,
            ))

        if not reconstructed:
            raise ValueError("No se pudieron reconstruir features para generar código")

        suite = GherkinTestSuite(features=reconstructed)
        contract_d = self._code_agent.process(suite)

        return {
            "generated_code": [
                {
                    "filename": m.filename,
                    "source_code": m.source_code,
                    "description": m.description,
                    "user_story_id": m.user_story_id,
                }
                for m in contract_d.generated_code
            ],
            "generated_tests": [
                {
                    "test_name": t.test_name,
                    "source_code": t.source_code,
                    "scenario_ids": t.scenario_ids,
                    "target_module": t.target_module,
                }
                for t in contract_d.generated_tests
            ],
            "total_modules": contract_d.total_modules,
            "total_tests": contract_d.total_tests,
        }

    def detect_ambiguities(self, requirement: str) -> list[dict]:
        """Fase 1-a web: solo detección. Sin llamada al LLM."""
        ambiguities = self._req_agent.detect_ambiguities(requirement)
        return [
            {
                "word": a.word,
                "category": a.category,
                "ieee_830_violation": a.ieee_830_violation,
                "iso_25010_category": a.iso_25010_category,
                "suggestion": a.suggestion,
                "context": a.context,
                "severity": a.severity,
            }
            for a in ambiguities
        ]

    def run_stages_1_2(
        self,
        requirement: str,
        analyst_resolutions: list[dict],
    ) -> tuple[RefinedRequirements, GherkinTestSuite]:
        """Fases 1-b y 2 web: genera Contract A con resoluciones del analista,
        luego genera Contract B. Sin HITL interactivo de CLI."""
        output_dir = Path(self._settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        print("[run_stages_1_2] Iniciando process_with_resolutions...")
        import traceback
        try:
            contract_a = self._req_agent.process_with_resolutions(requirement, analyst_resolutions)
        except Exception as exc:
            print(f"[run_stages_1_2] process_with_resolutions falló: {exc}")
            traceback.print_exc()
            raise
        contract_a_path = output_dir / f"contract_a_{contract_a.pipeline_run_id}.json"
        self._save_model(contract_a, contract_a_path)

        contract_b = self._test_agent.process(contract_a)
        contract_b_path = output_dir / f"contract_b_{contract_b.pipeline_run_id}.json"
        self._save_model(contract_b, contract_b_path)

        return contract_a, contract_b

    def finalize_with_decisions(
        self,
        contract_a: RefinedRequirements,
        contract_b: GherkinTestSuite,
        reviewer_name: str,
        global_decision: str,
        analyst_feedback: str,
        scenario_decisions: list[dict],
    ) -> dict[str, str]:
        """Fase 3 web: aplica las decisiones del analista a contract_b,
        construye contract_c y genera el reporte HTML.

        scenario_decisions: list de {feature_id, scenario_name, action, notes, new_iso?}
        global_decision: 'approved' | 'rejected' | 'needs_changes'
        """
        from datetime import datetime as _dt
        from .contracts.contract_b import ReviewChange, ReviewStatus

        output_dir = Path(self._settings.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # ── Aplicar decisiones por escenario ─────────────────────────────────
        changes: list[ReviewChange] = []
        for dec in scenario_decisions:
            action = dec.get("action", "accepted")
            notes = dec.get("notes", "")
            new_iso = dec.get("new_iso")
            if new_iso:
                from .contracts.contract_b import QualityCharacteristic
                for feature in contract_b.features:
                    for scenario in feature.scenarios:
                        if scenario.name == dec.get("scenario_name") and feature.user_story_id == dec.get("feature_id"):
                            try:
                                scenario.quality_characteristic = QualityCharacteristic(new_iso)
                            except ValueError:
                                pass
            changes.append(ReviewChange(
                reviewer=reviewer_name,
                action=action,
                notes=notes,
                scenario_name=dec.get("scenario_name") or None,
            ))

        # Recalcular coverage_by_characteristic si hubo reclasificaciones
        if any(d.get("new_iso") for d in scenario_decisions):
            new_cov: dict[str, int] = {}
            for feature in contract_b.features:
                for scenario in feature.scenarios:
                    key = scenario.quality_characteristic.value
                    new_cov[key] = new_cov.get(key, 0) + 1
            contract_b.coverage_by_characteristic = new_cov

        # ── Actualizar ReviewMetadata ─────────────────────────────────────────
        _status_map = {
            "approved": ReviewStatus.APPROVED,
            "rejected": ReviewStatus.REJECTED,
            "needs_changes": ReviewStatus.NEEDS_CHANGES,
        }
        final_status = _status_map.get(global_decision, ReviewStatus.APPROVED)
        contract_b.review.review_status = final_status
        contract_b.review.approved_by = reviewer_name if final_status == ReviewStatus.APPROVED else None
        contract_b.review.approved_at = _dt.now() if final_status == ReviewStatus.APPROVED else None
        contract_b.review.analyst_feedback = analyst_feedback or None
        contract_b.review.change_history = changes

        contract_b_path = output_dir / f"contract_b_{contract_b.pipeline_run_id}.json"
        self._save_model(contract_b, contract_b_path)

        # ── Contract C + reporte ──────────────────────────────────────────────
        pipeline_start = _dt.now()
        stages: list[PipelineStageRecord] = [
            PipelineStageRecord(stage_name="requirements_refinement"),
            PipelineStageRecord(stage_name="test_generation"),
        ]
        total_duration = (pipeline_start - pipeline_start).total_seconds()

        contract_c = self._build_contract_c(
            contract_a=contract_a,
            contract_b=contract_b,
            stages=stages,
            total_duration=total_duration,
            contract_a_path=str(output_dir / f"contract_a_{contract_a.pipeline_run_id}.json"),
            contract_b_path=str(contract_b_path),
        )
        contract_c_path = output_dir / f"contract_c_{contract_c.pipeline_run_id}.json"
        self._save_model(contract_c, contract_c_path)

        report_path = output_dir / f"report_{contract_c.pipeline_run_id}.html"
        self._reporter.generate(contract_a, contract_b, contract_c, report_path)

        total_acs = sum(len(s.acceptance_criteria) for s in contract_a.user_stories)
        html_content = report_path.read_text(encoding="utf-8")
        return {
            "pipeline_run_id": contract_c.pipeline_run_id,
            "contract_a": str(output_dir / f"contract_a_{contract_a.pipeline_run_id}.json"),
            "contract_b": str(contract_b_path),
            "contract_c": str(contract_c_path),
            "report_html": str(report_path),
            "html_content": html_content,
            "report_data": self._build_report_data(contract_a, contract_b, contract_c, self._settings.eco_mode),
            "summary": {
                "total_stories": len(contract_a.user_stories),
                "total_acceptance_criteria": total_acs,
                "total_scenarios": contract_b.total_scenarios,
                "coverage_pct": int(contract_c.requirements_to_test_coverage_ratio * 100),
                "total_ambiguities": contract_a.total_ambiguities_found,
                "duration_seconds": 0.0,
                "llm_provider": contract_c.llm_provider,
                "created_at": contract_c.created_at.isoformat(),
            },
        }

    def _review_contract_b(
        self,
        contract_b: GherkinTestSuite,
        reviewer_name: str,
    ) -> GherkinTestSuite:
        """HITL: revisión interactiva de la suite de tests por el analista."""
        all_scenarios: list[tuple] = [
            (feature, scenario)
            for feature in contract_b.features
            for scenario in feature.scenarios
        ]
        total = len(all_scenarios)
        changes: list[ReviewChange] = []
        iso_options = list(QualityCharacteristic)

        print("\n" + "=" * 60)
        print("🔍 REVISIÓN INTERACTIVA DE CASOS DE TEST")
        print(f"   {total} escenarios  |  Revisor: {reviewer_name or 'sin nombre'}")
        print("=" * 60)
        print("   [a] aceptar  [r] reclasificar ISO  [c] comentar  [s] saltar  [q] terminar")

        quit_review = False
        for idx, (feature, scenario) in enumerate(all_scenarios, 1):
            if quit_review:
                break

            print(f"\n[{idx}/{total}]  Feature: {feature.name}")
            print(f"   Escenario : {scenario.name}")
            print(f"   Tipo      : {scenario.scenario_type.value}  |  ISO: {scenario.quality_characteristic.value}")
            if scenario.tags:
                print(f"   Tags      : {', '.join(scenario.tags)}")
            print("   Pasos:")
            for step in scenario.steps[:5]:
                print(f"     {step.keyword} {step.text}")
            if len(scenario.steps) > 5:
                print(f"     … ({len(scenario.steps) - 5} pasos más)")

            while True:
                try:
                    choice = input("\n   Acción [a/r/c/s/q]: ").strip().lower() or "a"
                except EOFError:
                    choice = "s"

                if choice == "a":
                    changes.append(ReviewChange(
                        reviewer=reviewer_name,
                        action="accepted",
                        notes=f"Escenario '{scenario.name}' aceptado sin cambios",
                    ))
                    break

                elif choice == "r":
                    print("\n   Características ISO 25010:")
                    for i, qc in enumerate(iso_options, 1):
                        marker = "→" if qc == scenario.quality_characteristic else " "
                        print(f"   {marker} {i}. {qc.value}")
                    while True:
                        try:
                            sel = input(f"   Selecciona [1-{len(iso_options)}]: ").strip()
                        except EOFError:
                            sel = "0"
                        if sel.isdigit() and 1 <= int(sel) <= len(iso_options):
                            break
                        print(f"   ⚠  Ingresa un número entre 1 y {len(iso_options)}")
                    try:
                        justification = input("   Justificación (Enter para omitir): ").strip()
                    except EOFError:
                        justification = ""
                    old_char = scenario.quality_characteristic
                    new_char = iso_options[int(sel) - 1]
                    scenario.quality_characteristic = new_char
                    note = f"'{scenario.name}': {old_char.value} → {new_char.value}"
                    if justification:
                        note += f". {justification}"
                    changes.append(ReviewChange(reviewer=reviewer_name, action="reclassified", notes=note))
                    print(f"   ✅ Reclasificado: {old_char.value} → {new_char.value}")
                    break

                elif choice == "c":
                    try:
                        comment = input("   Comentario: ").strip()
                    except EOFError:
                        comment = ""
                    changes.append(ReviewChange(
                        reviewer=reviewer_name,
                        action="commented",
                        notes=f"'{scenario.name}': {comment}",
                    ))
                    print("   ✅ Comentario registrado")
                    break

                elif choice == "s":
                    break

                elif choice == "q":
                    print("\n   ⚠  Revisión interrumpida — se guardan los cambios realizados hasta aquí.")
                    quit_review = True
                    break

                else:
                    print("   ⚠  Opción no válida. Usa: a / r / c / s / q")

        # ── Decisión global ──────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("📊 DECISIÓN GLOBAL")
        reclassified = sum(1 for c in changes if c.action == "reclassified")
        print(f"   Escenarios revisados : {len(changes)}  |  Reclasificados: {reclassified}")
        print()
        print("   [1] Aprobar suite de tests")
        print("   [2] Rechazar — requiere regeneración")
        print("   [3] Aprobar con cambios — hay observaciones pendientes")
        status_map = {
            "1": ReviewStatus.APPROVED,
            "2": ReviewStatus.REJECTED,
            "3": ReviewStatus.NEEDS_CHANGES,
        }
        while True:
            try:
                decision = input("\n   Decisión [1/2/3]: ").strip()
            except EOFError:
                decision = "1"
            if decision in status_map:
                final_status = status_map[decision]
                break
            print("   ⚠  Ingresa 1, 2 o 3")
        try:
            feedback = input("   Feedback general (Enter para omitir): ").strip()
        except EOFError:
            feedback = ""

        # ── Actualizar ReviewMetadata ────────────────────────────────────────
        contract_b.review.review_status = final_status
        contract_b.review.approved_by = reviewer_name if final_status == ReviewStatus.APPROVED else None
        contract_b.review.approved_at = datetime.now() if final_status == ReviewStatus.APPROVED else None
        contract_b.review.analyst_feedback = feedback or None
        contract_b.review.change_history = changes

        # ── Recalcular coverage_by_characteristic tras reclasificaciones ─────
        if reclassified > 0:
            new_coverage: dict[str, int] = {}
            for feature in contract_b.features:
                for scenario in feature.scenarios:
                    key = scenario.quality_characteristic.value
                    new_coverage[key] = new_coverage.get(key, 0) + 1
            contract_b.coverage_by_characteristic = new_coverage

        labels = {
            ReviewStatus.APPROVED: "✅ APROBADA",
            ReviewStatus.REJECTED: "❌ RECHAZADA",
            ReviewStatus.NEEDS_CHANGES: "⚠  APROBADA CON CAMBIOS",
        }
        print(f"\n   Suite de tests: {labels[final_status]}")
        return contract_b

    def _build_contract_c(
        self,
        contract_a: RefinedRequirements,
        contract_b: GherkinTestSuite,
        stages: list[PipelineStageRecord],
        total_duration: float,
        contract_a_path: str,
        contract_b_path: str,
        contract_d: "CodeGenerationResult | None" = None,
    ) -> ExecutiveReport:
        total_acs = sum(len(s.acceptance_criteria) for s in contract_a.user_stories)
        covered_acs = len([cm for cm in contract_b.coverage_matrix if cm.scenario_names])
        coverage_ratio = covered_acs / total_acs if total_acs > 0 else 0.0

        all_chars = list(QualityCharacteristic)
        zero_coverage = [
            qc.value for qc in all_chars
            if contract_b.coverage_by_characteristic.get(qc.value, 0) == 0
        ]

        total_llm = sum(s.llm_calls for s in stages)
        total_rag = sum(s.rag_retrievals for s in stages)

        rag_metrics = RAGMetrics(
            hyde_expansions=total_rag,
            bm25_candidates_total=total_rag * self._settings.rag_bm25_top_k,
            dense_candidates_total=total_rag * self._settings.rag_dense_top_k,
            rrf_merges=total_rag,
            reranker_calls=total_rag,
        )

        story_types: dict[str, int] = {}
        priorities: dict[str, int] = {}
        for story in contract_a.user_stories:
            story_types[story.story_type.value] = story_types.get(story.story_type.value, 0) + 1
            priorities[story.priority.value] = priorities.get(story.priority.value, 0) + 1

        req_summary = RequirementsExecutiveSummary(
            total_user_stories=len(contract_a.user_stories),
            total_acceptance_criteria=total_acs,
            total_ambiguities_detected=contract_a.total_ambiguities_found,
            total_assumptions_made=contract_a.total_assumptions_made,
            hitl_reviewed=True,
            story_types_breakdown=story_types,
            priority_breakdown=priorities,
        )

        test_summary = TestSuiteExecutiveSummary(
            total_scenarios=contract_b.total_scenarios,
            total_features=len(contract_b.features),
            positive_scenarios=contract_b.total_positive,
            negative_scenarios=contract_b.total_negative,
            boundary_scenarios=contract_b.total_boundary,
            coverage_by_characteristic=contract_b.coverage_by_characteristic,
            uncovered_criteria=contract_b.uncovered_criteria,
            review_status=contract_b.review.review_status.value,
            approved_by=contract_b.review.approved_by,
        )

        insights = self._generate_insights(contract_a, contract_b, coverage_ratio, zero_coverage)

        _model_map = {
            "groq": self._settings.groq_model,
            "deepseek": self._settings.deepseek_model,
            "cerebras": self._settings.cerebras_model,
        }
        llm_model = _model_map.get(
            self._settings.llm_provider,
            self._settings.gemini_generation_model,
        )

        return ExecutiveReport(
            contract_a_run_id=contract_a.pipeline_run_id,
            contract_b_run_id=contract_b.pipeline_run_id,
            contract_a_path=contract_a_path,
            contract_b_path=contract_b_path,
            requirements_summary=req_summary,
            test_suite_summary=test_summary,
            llm_provider=self._settings.llm_provider,
            llm_model=llm_model,
            pipeline_stages=stages,
            rag_metrics=rag_metrics,
            total_llm_calls=total_llm,
            total_duration_seconds=total_duration,
            quality_insights=insights,
            requirements_to_test_coverage_ratio=coverage_ratio,
            iso_characteristics_with_zero_coverage=zero_coverage,
            code_generation=self._build_code_generation_summary(contract_d),
        )

    def _build_code_generation_summary(
        self,
        contract_d: "CodeGenerationResult | None",
    ) -> "CodeGenerationSummary | None":
        """Construye el resumen de generación de código para el ExecutiveReport."""
        if contract_d is None:
            return None
        qr = contract_d.quality_report
        tm = contract_d.traceability_matrix
        cr = contract_d.coverage_report
        n_high = (
            sum(1 for f in qr.security_findings if f.severity == SecuritySeverity.HIGH)
            if qr else 0
        )
        return CodeGenerationSummary(
            total_modules=contract_d.total_modules,
            total_tests=contract_d.total_tests,
            functions_exceeding_threshold=qr.functions_exceeding_threshold if qr else 0,
            security_findings_high=n_high,
            cmmi_l3_compliant=tm.cmmi_l3_compliant if tm else None,
            branch_coverage_pct=cr.branch_coverage_pct if cr else None,
            code_review_status=contract_d.review.review_status.value,
            contract_d_run_id=contract_d.pipeline_run_id,
        )

    def _generate_insights(
        self,
        a: RefinedRequirements,
        b: GherkinTestSuite,
        coverage_ratio: float,
        zero_coverage: list[str],
    ) -> list[QualityInsight]:
        insights: list[QualityInsight] = []

        if coverage_ratio < 1.0:
            uncovered_count = len(b.uncovered_criteria)
            insights.append(QualityInsight(
                severity="warning" if uncovered_count <= 2 else "critical",
                category="coverage_gap",
                title=f"{uncovered_count} criterios de aceptación sin cobertura de test",
                description=(
                    f"Los criterios {', '.join(b.uncovered_criteria)} no tienen escenarios Gherkin asociados. "
                    f"Esto deja funcionalidad sin verificar."
                ),
                recommendation="Regenerar la suite de test o agregar escenarios manualmente para estos ACs.",
                affected_items=b.uncovered_criteria,
            ))

        if a.total_assumptions_made > 0:
            affected = [
                f"{us.id}: {res.original_text}"
                for us in a.user_stories
                for res in us.ambiguities_resolved
                if res.assumption_made
            ]
            insights.append(QualityInsight(
                severity="warning",
                category="assumption_risk",
                title=f"{a.total_assumptions_made} supuestos del LLM en requerimientos",
                description=(
                    "El LLM realizó suposiciones sobre términos ambiguos sin confirmación del analista. "
                    "Esto puede provocar que los tests no reflejen el comportamiento real esperado."
                ),
                recommendation="Revisar los campos ambiguities_resolved con assumption_made=True y validar con el cliente.",
                affected_items=affected[:5],
            ))

        security_count = b.coverage_by_characteristic.get("security", 0)
        if security_count == 0 and any(
            "segur" in us.title.lower() or "auth" in us.title.lower() or "login" in us.title.lower()
            for us in a.user_stories
        ):
            insights.append(QualityInsight(
                severity="critical",
                category="security_concern",
                title="Historias de seguridad sin escenarios de test de seguridad",
                description=(
                    "Se detectaron historias relacionadas con autenticación/seguridad pero ningún escenario "
                    "fue clasificado como security en ISO 25010."
                ),
                recommendation="Agregar escenarios @iso-security: inyección SQL, fuerza bruta, escalada de privilegios.",
                affected_items=[us.id for us in a.user_stories if "segur" in us.title.lower()],
            ))

        if zero_coverage:
            high_risk = {"security", "reliability", "performance_efficiency"}
            risky_uncovered = [qc for qc in zero_coverage if qc in high_risk]
            if risky_uncovered:
                insights.append(QualityInsight(
                    severity="warning",
                    category="iso_gap",
                    title=f"Sin cobertura en características ISO de alto riesgo: {', '.join(risky_uncovered)}",
                    description="Características ISO 25010 de alto riesgo sin ningún escenario de test.",
                    recommendation="Agregar escenarios específicos o usar herramientas especializadas (OWASP ZAP, JMeter, Chaos).",
                    affected_items=risky_uncovered,
                ))

        return insights

    def _build_report_data(
        self,
        contract_a: RefinedRequirements,
        contract_b: GherkinTestSuite,
        contract_c: ExecutiveReport,
        eco_mode: bool = False,
    ) -> dict:
        """Serializes contracts A/B/C into a flat dict for frontend rendering."""
        total_acs = sum(len(s.acceptance_criteria) for s in contract_a.user_stories)

        ambiguities = [
            {
                "story_id": story.id,
                "story_title": story.title,
                "original_text": res.original_text,
                "issue": res.issue,
                "resolution": res.resolution,
                "assumption_made": res.assumption_made,
                "confidence_score": res.confidence_score,
            }
            for story in contract_a.user_stories
            for res in story.ambiguities_resolved
        ]

        user_stories = [
            {
                "id": s.id,
                "title": s.title,
                "as_a": s.as_a,
                "i_want": s.i_want,
                "so_that": s.so_that,
                "priority": s.priority.value,
                "story_type": s.story_type.value,
                "business_rules": s.business_rules,
                "acceptance_criteria": [
                    {
                        "id": ac.id,
                        "description": ac.description,
                        "given": ac.given,
                        "when": ac.when,
                        "then": ac.then,
                        "is_negative_case": ac.is_negative_case,
                        "boundary_values": ac.boundary_values,
                    }
                    for ac in s.acceptance_criteria
                ],
            }
            for s in contract_a.user_stories
        ]

        features = [
            {
                "user_story_id": f.user_story_id,
                "name": f.name,
                "description": f.description,
                "scenarios": [
                    {
                        "name": sc.name,
                        "scenario_type": sc.scenario_type.value,
                        "quality_characteristic": sc.quality_characteristic.value,
                        "tags": sc.tags,
                        "steps": [{"keyword": s.keyword, "text": s.text} for s in sc.steps],
                        "acceptance_criterion_id": sc.acceptance_criterion_id,
                        "heuristic_applied": sc.heuristic_applied,
                    }
                    for sc in f.scenarios
                ],
            }
            for f in contract_b.features
        ]

        review = contract_b.review
        actions_breakdown: dict[str, int] = {}
        for ch in review.change_history:
            actions_breakdown[ch.action] = actions_breakdown.get(ch.action, 0) + 1

        reviewer = review.approved_by or (review.change_history[0].reviewer if review.change_history else "")
        if review.approved_at:
            reviewed_at = review.approved_at.isoformat()
        elif review.change_history:
            reviewed_at = review.change_history[-1].timestamp.isoformat()
        else:
            reviewed_at = ""

        hitl = {
            "reviewer": reviewer,
            "review_status": review.review_status.value,
            "reviewed_at": reviewed_at,
            "analyst_feedback": review.analyst_feedback,
            "changes_count": len(review.change_history),
            "actions_breakdown": actions_breakdown,
            "changes": [
                {
                    "action": ch.action,
                    "notes": ch.notes or "",
                    "scenario_name": ch.scenario_name or "",
                    "timestamp": ch.timestamp.isoformat(),
                }
                for ch in review.change_history
            ],
            "ambiguities_resolved": [
                {
                    "story_id": story.id,
                    "original_text": res.original_text,
                    "resolution": res.resolution,
                    "assumption_made": res.assumption_made,
                }
                for story in contract_a.user_stories
                for res in story.ambiguities_resolved
            ],
        }

        return {
            "pipeline_run_id": contract_c.pipeline_run_id,
            "created_at": contract_c.created_at.isoformat(),
            "module_version": contract_c.module_version,
            "llm_provider": contract_c.llm_provider,
            "llm_model": contract_c.llm_model,
            "total_duration_seconds": contract_c.total_duration_seconds or 0.0,
            "total_stories": len(contract_a.user_stories),
            "total_acceptance_criteria": total_acs,
            "total_scenarios": contract_b.total_scenarios,
            "coverage_pct": int(contract_c.requirements_to_test_coverage_ratio * 100),
            "total_ambiguities": contract_a.total_ambiguities_found,
            "original_requirement": contract_a.original_requirements_text,
            "project_context": contract_a.project_context,
            "ambiguities": ambiguities,
            "user_stories": user_stories,
            "features": features,
            "hitl": hitl,
            "iso_coverage": contract_b.coverage_by_characteristic,
            "uncovered_criteria": contract_b.uncovered_criteria,
            "coverage_matrix": [
                {
                    "user_story_id": cm.user_story_id,
                    "quality_characteristics_covered": [qc.value for qc in cm.quality_characteristics_covered],
                }
                for cm in contract_b.coverage_matrix
            ],
            "quality_insights": [
                {
                    "severity": ins.severity,
                    "category": ins.category,
                    "title": ins.title,
                    "description": ins.description,
                    "recommendation": ins.recommendation,
                    "affected_items": ins.affected_items,
                }
                for ins in contract_c.quality_insights
            ],
            "eco_mode": eco_mode,
        }

    @staticmethod
    def _save_model(model, path: Path) -> None:
        path.write_text(
            model.model_dump_json(indent=2),
            encoding="utf-8",
        )
