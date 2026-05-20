"""Contract D — Code Generation Result.

Extiende el pipeline Stage 1-2 (A→B) con generación y verificación de código:
  Stage 3 (V1): CodeGeneratorAgent     → generated_code + generated_tests
  Stage 4 (V2): StaticAnalysisAgent    → quality_report (CC, CogC, Bandit, ISO 25010)
  Stage 5 (V3): TraceabilityAgent      → traceability_matrix + coverage_report
  Stage 6 (V4): CodeReviewAgent        → review (HITL senior dev)

Basado en qualityai-modulo3/src/contract_c.py, adaptado al namespace del pipeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class MeasurementStatus(str, Enum):
    """Clasificación honesta de capacidad de medición por característica ISO."""
    MEASURED = "MEASURED"
    REQUIRES_HUMAN_JUDGMENT = "REQUIRES_HUMAN_JUDGMENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComplexityBand(str, Enum):
    """Bandas de complejidad ciclomática según radon (A = mejor, E = peor)."""
    A = "A"  # CC 1-5
    B = "B"  # CC 6-10
    C = "C"  # CC 11-15
    D = "D"  # CC 16-20
    E = "E"  # CC > 20


class TraceabilityStatus(str, Enum):
    COVERED = "COVERED"
    ORPHAN_FORWARD = "ORPHAN_FORWARD"    # Escenario sin test que lo cubra
    ORPHAN_BACKWARD = "ORPHAN_BACKWARD"  # Test sin escenario que lo justifique


class SecuritySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CodeReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_CHANGES = "needs_changes"


# ── V1: Generación de código ──────────────────────────────────────────────────

class GeneratedCodeModule(BaseModel):
    """Módulo Python generado a partir de un feature Gherkin."""
    filename: str = Field(..., description="Ej: auth_service.py")
    source_code: str
    description: str
    user_story_id: str = Field(..., description="ID de la historia de usuario origen")


class GeneratedTest(BaseModel):
    """Test Pytest generado para cubrir los escenarios Gherkin."""
    test_name: str = Field(..., description="Ej: test_auth_login_valido")
    source_code: str
    scenario_ids: list[str] = Field(
        default_factory=list,
        description="IDs de escenarios Gherkin cubiertos (para trazabilidad V3)",
    )
    target_module: str = Field(..., description="Módulo que este test verifica")


# ── V2: Análisis estático ─────────────────────────────────────────────────────

class FunctionMetrics(BaseModel):
    """Métricas por función extraídas de radon + complexipy."""
    function_name: str
    module: str
    cyclomatic_complexity: int = Field(ge=1)
    cognitive_complexity: int = Field(ge=0)
    cc_band: ComplexityBand = ComplexityBand.A
    nesting_depth: int = Field(default=0, ge=0)
    exceeds_threshold: bool = False  # CC ≥ 10 OR CogC ≥ 15


class SecurityFinding(BaseModel):
    """Hallazgo de seguridad reportado por Bandit."""
    test_id: str = Field(..., description="Ej: B602, B608")
    severity: SecuritySeverity
    module: str
    line_number: int
    description: str


class QualityCharacteristicResult(BaseModel):
    """Estado de medición de una característica ISO 25010 para el código generado."""
    characteristic: str  # nombre del enum QualityCharacteristic
    status: MeasurementStatus
    metrics_used: list[str] = Field(default_factory=list)
    verdict: str = ""


class QualityReport(BaseModel):
    """Reporte de calidad estática completo (resultado Stage 4)."""
    function_metrics: list[FunctionMetrics] = Field(default_factory=list)
    maintainability_index: Optional[float] = Field(
        default=None,
        description="Índice de mantenibilidad promedio (radon mi), 0-100, ≥20 es bueno",
    )
    security_findings: list[SecurityFinding] = Field(default_factory=list)
    iso_25010_coverage: list[QualityCharacteristicResult] = Field(default_factory=list)
    functions_exceeding_threshold: int = 0


# ── V3: Trazabilidad CMMI L3 + cobertura ──────────────────────────────────────

class ScenarioTraceability(BaseModel):
    """Nodo forward: escenario Gherkin → tests que lo cubren."""
    scenario_id: str
    scenario_name: str
    covering_tests: list[str] = Field(default_factory=list)
    status: TraceabilityStatus = TraceabilityStatus.ORPHAN_FORWARD


class TestTraceability(BaseModel):
    """Nodo backward: test → escenarios Gherkin que justifica."""
    test_name: str
    justifying_scenarios: list[str] = Field(default_factory=list)
    status: TraceabilityStatus = TraceabilityStatus.ORPHAN_BACKWARD


class TraceabilityMatrix(BaseModel):
    """Matriz de trazabilidad bidireccional CMMI L3."""
    forward: list[ScenarioTraceability] = Field(default_factory=list)
    backward: list[TestTraceability] = Field(default_factory=list)
    requirements_coverage_pct: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="% de escenarios cubiertos por al menos 1 test",
    )
    tests_justified_pct: float = Field(
        default=0.0, ge=0.0, le=100.0,
        description="% de tests que justifican al menos 1 escenario",
    )
    orphan_scenarios: list[str] = Field(default_factory=list)
    orphan_tests: list[str] = Field(default_factory=list)
    cmmi_l3_compliant: bool = False  # True iff len(orphans) == 0 en ambas direcciones


class CoverageReport(BaseModel):
    """Reporte de cobertura de ramas obtenido con pytest-cov."""
    branch_coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    line_coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    meets_threshold: bool = False  # branch_coverage_pct >= 80
    uncovered_modules: list[str] = Field(default_factory=list)


# ── V4: Revisión humana (HITL senior dev) ─────────────────────────────────────

class CodeReviewChange(BaseModel):
    """Registro auditable de cada decisión del revisor (CMMI L3)."""
    timestamp: datetime = Field(default_factory=datetime.now)
    reviewer: str
    action: str = Field(
        ...,
        description="approved | rejected | comment_added | smell_flagged",
    )
    target: str = Field(..., description="filename del módulo revisado")
    notes: Optional[str] = None


class CodeReviewMetadata(BaseModel):
    """Metadata completa de la revisión humana del código generado."""
    review_status: CodeReviewStatus = CodeReviewStatus.PENDING_REVIEW
    version: int = 1
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    reviewer_feedback: Optional[str] = None
    change_history: list[CodeReviewChange] = Field(default_factory=list)


# ── Contenedor raíz — Contract D ──────────────────────────────────────────────

class CodeGenerationResult(BaseModel):
    """Contract D: resultado completo del pipeline de generación de código (V1→V4).

    Se construye incrementalmente:
      - Stage 3 rellena generated_code, generated_tests
      - Stage 4 rellena quality_report
      - Stage 5 rellena traceability_matrix, coverage_report
      - Stage 6 actualiza review
    """
    pipeline_run_id: str = Field(
        default_factory=lambda: f"m3d-{uuid.uuid4().hex[:8]}",
    )
    agent_name: str = "code_generator_agent"
    agent_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.now)

    source_contract_b_id: str = Field(
        ..., description="pipeline_run_id del Contract B de origen",
    )

    generated_code: list[GeneratedCodeModule] = Field(default_factory=list)
    generated_tests: list[GeneratedTest] = Field(default_factory=list)

    quality_report: Optional[QualityReport] = None
    traceability_matrix: Optional[TraceabilityMatrix] = None
    coverage_report: Optional[CoverageReport] = None

    review: CodeReviewMetadata = Field(default_factory=CodeReviewMetadata)

    total_modules: int = 0
    total_tests: int = 0
