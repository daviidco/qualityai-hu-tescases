"""Contract C — Executive Report.

Meta-contrato nuevo de Module 3.
Envuelve Contract A + Contract B con métricas de pipeline, RAG y quality insights.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PipelineStageStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStageRecord(BaseModel):
    stage_name: str
    status: PipelineStageStatus = PipelineStageStatus.SUCCESS
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    llm_calls: int = 0
    rag_retrievals: int = 0
    errors: list[str] = Field(default_factory=list)


class RAGMetrics(BaseModel):
    """Métricas pedagógicas del pipeline RAG mejorado."""
    hyde_expansions: int = Field(default=0, description="Expansiones HyDE realizadas")
    bm25_candidates_total: int = 0
    dense_candidates_total: int = 0
    rrf_merges: int = 0
    reranker_calls: int = 0
    avg_reranker_top1_score: Optional[float] = None
    kb_stories_chunks: int = 0
    kb_patterns_chunks: int = 0


class RequirementsExecutiveSummary(BaseModel):
    total_user_stories: int
    total_acceptance_criteria: int
    total_ambiguities_detected: int
    total_assumptions_made: int
    hitl_reviewed: bool
    story_types_breakdown: dict[str, int] = Field(default_factory=dict)
    priority_breakdown: dict[str, int] = Field(default_factory=dict)


class TestSuiteExecutiveSummary(BaseModel):
    total_scenarios: int
    total_features: int
    positive_scenarios: int
    negative_scenarios: int
    boundary_scenarios: int
    coverage_by_characteristic: dict[str, int] = Field(default_factory=dict)
    uncovered_criteria: list[str] = Field(default_factory=list)
    review_status: str = "pending_review"
    approved_by: Optional[str] = None


class QualityInsight(BaseModel):
    """Insight de calidad generado automáticamente por el Reporter."""
    severity: str = Field(..., description="critical | warning | info")
    category: str = Field(
        ...,
        description="coverage_gap | assumption_risk | security_concern | iso_gap | etc.",
    )
    title: str
    description: str
    recommendation: str
    affected_items: list[str] = Field(default_factory=list)


class CodeGenerationSummary(BaseModel):
    """Resumen del pipeline de generación de código para el ExecutiveReport."""
    total_modules: int = 0
    total_tests: int = 0
    functions_exceeding_threshold: int = 0
    security_findings_high: int = 0
    cmmi_l3_compliant: Optional[bool] = None
    branch_coverage_pct: Optional[float] = None
    code_review_status: str = "pending_review"
    contract_d_run_id: Optional[str] = None


class ExecutiveReport(BaseModel):
    """Contract C: Reporte ejecutivo combinado producido por el Orquestador.

    No reemplaza A ni B — los envuelve con:
    - Auditoría de pipeline (CMMI-DEV L3)
    - Métricas RAG (pedagógico: muestra la mejora)
    - Resúmenes ejecutivos de requerimientos + tests
    - Quality insights cross-cutting generados automáticamente
    """
    pipeline_run_id: str = Field(default_factory=lambda: f"m3-{uuid.uuid4().hex[:8]}")
    module_version: str = "3.0.0"
    created_at: datetime = Field(default_factory=datetime.now)

    contract_a_run_id: str
    contract_b_run_id: str
    contract_a_path: Optional[str] = None
    contract_b_path: Optional[str] = None

    requirements_summary: RequirementsExecutiveSummary
    test_suite_summary: TestSuiteExecutiveSummary

    llm_provider: str = ""
    llm_model: str = ""

    pipeline_stages: list[PipelineStageRecord] = Field(default_factory=list)
    rag_metrics: RAGMetrics = Field(default_factory=RAGMetrics)
    total_llm_calls: int = 0
    total_duration_seconds: Optional[float] = None

    quality_insights: list[QualityInsight] = Field(default_factory=list)

    requirements_to_test_coverage_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fracción de ACs con al menos un escenario de test",
    )
    iso_characteristics_with_zero_coverage: list[str] = Field(default_factory=list)

    # Resumen del pipeline de generación de código (Stages 3-6, opcional)
    code_generation: Optional[CodeGenerationSummary] = None
