from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


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
    project_draft_id: Optional[str] = None  # proyecto al que pertenece el análisis
    req_id: Optional[str] = None            # requerimiento específico dentro del proyecto


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


# ── Auth / Usuarios ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    role: str


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2)
    password: str = Field(..., min_length=8)
    role: Literal["admin", "analyst", "scrum_leader", "developer"] = "analyst"
    developer_type: Optional[Literal["backend", "frontend", "devops"]] = None


class UserOut(BaseModel):
    email: str
    name: str = ""
    role: str
    developer_type: Optional[str] = None
    is_active: bool
    created_at: str


# ── Miembros de proyecto ──────────────────────────────────────────────────────

# ── Proyectos (pre-pipeline) ──────────────────────────────────────────────────

class ProjectCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=2)
    description: Optional[str] = None
    client_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    requirement: Optional[str] = Field(None, min_length=20)  # opcional al crear


class ProjectUpdateRequest(BaseModel):
    project_name: Optional[str] = Field(None, min_length=2)
    description: Optional[str] = None
    client_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    requirement: Optional[str] = Field(None, min_length=20)


class ProjectDraftOut(BaseModel):
    run_id: str
    project_name: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    req_preview: str
    status: str
    created_by: str
    created_at: str
    assigned_analysts: list[str] = Field(default_factory=list)
    review_status: Optional[str] = None
    total_stories: int = 0
    total_scenarios: int = 0
    logo_url: Optional[str] = None
    req_count: int = 0
    req_analyzed: int = 0

# ── Requerimientos de proyecto ────────────────────────────────────────────────

class RequirementCreate(BaseModel):
    title: str = Field(..., min_length=3)
    content: str = Field(..., min_length=20)
    attachment_name: Optional[str] = None


class RefinementOut(BaseModel):
    run_id: str
    created_at: str
    created_by: str
    review_status: str
    summary: Optional[dict] = None


class RequirementOut(BaseModel):
    req_id: str
    title: str
    content: str
    created_at: str
    created_by: str
    status: str
    attachment_name: Optional[str] = None
    refinements: list[RefinementOut] = Field(default_factory=list)


class AssignAnalystRequest(BaseModel):
    analyst_email: EmailStr

class StoryAssignRequest(BaseModel):
    developer_email: EmailStr

class StoryAssignmentOut(BaseModel):
    story_id: str
    developer_email: str
    developer_type: Optional[str] = None
    assigned_by: str
    assigned_at: str

class ProjectMemberAdd(BaseModel):
    email: EmailStr


class ProjectMemberOut(BaseModel):
    email: str
    developer_type: str
    assigned_at: str
    assigned_by: str


class ProjectMembersResponse(BaseModel):
    run_id: str
    members: list[ProjectMemberOut]


# ── LLM Config (admin) ───────────────────────────────────────────────────────

class LLMKeyPreview(BaseModel):
    index: int
    preview: str   # "AIza…ef56"


class LLMProviderV2Out(BaseModel):
    keys: list[LLMKeyPreview]
    model: str


class LLMConfigV2Out(BaseModel):
    provider_order: list[str]
    providers: dict[str, LLMProviderV2Out]


class LLMProviderV2Update(BaseModel):
    model: str
    add_keys: list[str] = []
    remove_indices: list[int] = []


class LLMConfigV2Update(BaseModel):
    provider_order: list[str]
    providers: dict[str, LLMProviderV2Update]


# ── Jira export ───────────────────────────────────────────────────────────────

class JiraTicketRef(BaseModel):
    key: str
    url: str


class JiraStoryRef(JiraTicketRef):
    user_story_id: str


class JiraSubtaskRef(JiraTicketRef):
    criterion_id: str


class JiraExportResponse(BaseModel):
    run_id: str
    epic_key: str
    epic_url: str
    total_created: int
    stories: list[JiraStoryRef]
    subtasks: list[JiraSubtaskRef]
