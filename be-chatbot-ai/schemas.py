from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Fase 1-a: Detectar ambigüedades ──────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    requirement: str = Field(..., description="Requerimiento en texto libre")


class AmbiguityItem(BaseModel):
    word: str
    category: str
    ieee_830_violation: str
    iso_25010_category: str
    suggestion: str
    context: str
    severity: str


class AnalyzeResponse(BaseModel):
    session_id: str
    requirement: str
    has_ambiguities: bool
    ambiguities: list[AmbiguityItem]


# ── Fase 1-b + 2: Generar HU + Test Cases ────────────────────────────────────

class AnalystResolution(BaseModel):
    word: str
    category: str
    analyst_resolution: str
    status: Literal["accepted", "custom", "dismissed"]


class GenerateTestsRequest(BaseModel):
    session_id: str
    resolutions: list[AnalystResolution] = Field(default_factory=list)


class GherkinStepOut(BaseModel):
    keyword: str
    text: str


class ScenarioOut(BaseModel):
    name: str
    scenario_type: str
    quality_characteristic: str
    tags: list[str]
    steps: list[GherkinStepOut]
    acceptance_criterion_id: str


class FeatureOut(BaseModel):
    user_story_id: str
    name: str
    description: str
    scenarios: list[ScenarioOut]


class AcceptanceCriterionOut(BaseModel):
    id: str
    description: str
    given: str
    when: str
    then: str
    is_negative_case: bool


class UserStoryOut(BaseModel):
    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    priority: str
    story_type: str
    business_rules: list[str]
    acceptance_criteria: list[AcceptanceCriterionOut]


class GenerateTestsResponse(BaseModel):
    session_id: str
    total_scenarios: int
    features: list[FeatureOut]
    user_stories: list[UserStoryOut]


# ── Fase 3: Finalizar con decisiones del analista ─────────────────────────────

class ScenarioDecision(BaseModel):
    feature_id: str
    scenario_name: str
    action: Literal["accepted", "reclassified", "commented", "skipped"]
    notes: str = ""
    new_iso: Optional[str] = None


class FinalizeRequest(BaseModel):
    session_id: str
    reviewer_name: str = ""
    global_decision: Literal["approved", "rejected", "needs_changes"] = "approved"
    analyst_feedback: str = ""
    scenario_decisions: list[ScenarioDecision] = Field(default_factory=list)


class PipelineSummary(BaseModel):
    total_stories: int
    total_acceptance_criteria: int
    total_scenarios: int
    coverage_pct: int
    total_ambiguities: int
    duration_seconds: float
    llm_provider: str
    created_at: str


class FinalizeResponse(BaseModel):
    pipeline_run_id: str
    html_content: str
    report_data: dict
    pdf_base64: str
    summary: PipelineSummary


# ── Historial de proyectos ────────────────────────────────────────────────────

class ProjectMeta(BaseModel):
    run_id: str
    timestamp: str
    req_preview: str
    summary: PipelineSummary


class ProjectListResponse(BaseModel):
    projects: list[ProjectMeta]


class ProjectDetailResponse(BaseModel):
    run_id: str
    timestamp: str
    req_preview: str
    summary: PipelineSummary
    report_data: dict
    html_content: str
    pdf_base64: str
