import base64
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

# Volumen donde se persisten los reportes HTML por proyecto
_REPORTS_DIR = Path("/app/storage/reports")

import mongo_store
from dependencies import get_current_user
from executive_pdf import generate_executive_pdf
from schemas import (
    AnalyzeRequest, AnalyzeResponse, AmbiguityItem,
    GenerateTestsRequest, GenerateTestsResponse,
    FeatureOut, ScenarioOut, GherkinStepOut,
    AcceptanceCriterionOut, UserStoryOut,
    FinalizeRequest, FinalizeResponse, PipelineSummary,
    ProjectListResponse, ProjectDetailResponse, ProjectMeta,
    GenerateCodeRequest, AcceptCodeRequest,
)

router = APIRouter(tags=["Pipeline HITL"])


def _raise_http(exc: Exception) -> None:
    """Convierte excepciones del pipeline en HTTP errors apropiados."""
    detail = str(exc)
    logger.exception("❌ Pipeline error: %s", detail)
    if "RATE_LIMIT" in detail:
        raise HTTPException(status_code=429, detail=detail.replace("RATE_LIMIT: ", ""))
    raise HTTPException(status_code=500, detail=detail)


def _get_llm(request: Request):
    """Obtiene el FallbackLLMProvider del pipeline (o None si no está disponible)."""
    pipeline = getattr(request.app.state, "pipeline", None)
    req_agent = getattr(pipeline, "_req_agent", None)
    return getattr(req_agent, "_llm", None)


# ── Estado del LLM en tiempo real ────────────────────────────────────────────

@router.get("/pipeline/status")
async def pipeline_status(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Devuelve el proveedor LLM activo y la cadena completa para el frontend."""
    llm = _get_llm(request)
    return {
        "current_label": getattr(llm, "current_label", "—"),
        "chain_meta": getattr(llm, "chain_meta", []),
        "skip_count": getattr(llm, "_skip_count", 0),
    }


@router.post("/pipeline/skip-provider")
async def skip_provider(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Avanza el puntero de la cadena al siguiente proveedor/key."""
    llm = _get_llm(request)
    if llm is None or not hasattr(llm, "skip_current"):
        return {"ok": False, "reason": "FallbackLLMProvider no disponible"}
    llm.skip_current()
    return {
        "ok": True,
        "skip_count": getattr(llm, "_skip_count", 0),
        "current_label": getattr(llm, "current_label", "—"),
    }


# ── Fase 1-a: Detectar ambigüedades ──────────────────────────────────────────

@router.post("/pipeline/analyze", response_model=AnalyzeResponse)
async def analyze(
    req: AnalyzeRequest,
    request: Request,
    _user: dict = Depends(get_current_user),
) -> AnalyzeResponse:
    """Detecta ambigüedades en el requerimiento. Crea sesión para los pasos siguientes."""
    try:
        raw = await run_in_threadpool(
            request.app.state.pipeline.detect_ambiguities,
            req.requirement,
        )
    except Exception as exc:
        _raise_http(exc)

    session_id = str(uuid.uuid4())
    request.app.state.sessions[session_id] = {
        "requirement": req.requirement,
        "contract_a": None,
        "contract_b": None,
    }

    return AnalyzeResponse(
        session_id=session_id,
        requirement=req.requirement,
        has_ambiguities=bool(raw),
        ambiguities=[AmbiguityItem(**a) for a in raw],
    )


# ── Fase 1-b + 2: Generar HU y Test Cases ────────────────────────────────────

@router.post("/pipeline/generate-tests", response_model=GenerateTestsResponse)
async def generate_tests(
    req: GenerateTestsRequest,
    request: Request,
    _user: dict = Depends(get_current_user),
) -> GenerateTestsResponse:
    """Genera Contract A con las resoluciones del analista y luego Contract B (test cases)."""
    session = request.app.state.sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada.")

    resolutions = [r.model_dump() for r in req.resolutions]
    try:
        contract_a, contract_b = await run_in_threadpool(
            request.app.state.pipeline.run_stages_1_2,
            session["requirement"],
            resolutions,
        )
    except Exception as exc:
        _raise_http(exc)

    session["contract_a"] = contract_a
    session["contract_b"] = contract_b

    features_out = [
        FeatureOut(
            user_story_id=f.user_story_id,
            name=f.name,
            description=f.description,
            scenarios=[
                ScenarioOut(
                    name=sc.name,
                    scenario_type=sc.scenario_type.value,
                    quality_characteristic=sc.quality_characteristic.value,
                    tags=sc.tags,
                    steps=[GherkinStepOut(keyword=s.keyword, text=s.text) for s in sc.steps],
                    acceptance_criterion_id=sc.acceptance_criterion_id,
                )
                for sc in f.scenarios
            ],
        )
        for f in contract_b.features
    ]

    stories_out = [
        UserStoryOut(
            id=s.id,
            title=s.title,
            as_a=s.as_a,
            i_want=s.i_want,
            so_that=s.so_that,
            priority=s.priority.value,
            story_type=s.story_type.value,
            business_rules=s.business_rules,
            acceptance_criteria=[
                AcceptanceCriterionOut(
                    id=ac.id,
                    description=ac.description,
                    given=ac.given,
                    when=ac.when,
                    then=ac.then,
                    is_negative_case=ac.is_negative_case,
                )
                for ac in s.acceptance_criteria
            ],
        )
        for s in contract_a.user_stories
    ]

    return GenerateTestsResponse(
        session_id=req.session_id,
        total_scenarios=contract_b.total_scenarios,
        features=features_out,
        user_stories=stories_out,
    )


# ── Fase 3: Finalizar con decisiones del analista ─────────────────────────────

@router.post("/pipeline/finalize", response_model=FinalizeResponse)
async def finalize(
    req: FinalizeRequest,
    request: Request,
    _user: dict = Depends(get_current_user),
) -> FinalizeResponse:
    """Aplica decisiones de revisión a Contract B y genera el reporte HTML final."""
    session = request.app.state.sessions.get(req.session_id)
    if not session or not session.get("contract_a") or not session.get("contract_b"):
        raise HTTPException(status_code=404, detail="Sesión incompleta — ejecuta /analyze y /generate-tests primero.")

    decisions = [d.model_dump() for d in req.scenario_decisions]
    try:
        result = await run_in_threadpool(
            request.app.state.pipeline.finalize_with_decisions,
            session["contract_a"],
            session["contract_b"],
            req.reviewer_name,
            req.global_decision,
            req.analyst_feedback,
            decisions,
        )
    except Exception as exc:
        _raise_http(exc)

    # Limpia la sesión para liberar memoria
    del request.app.state.sessions[req.session_id]

    summary_data = result["summary"]
    try:
        pdf_bytes = generate_executive_pdf(result["report_data"])
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception as pdf_exc:
        logger.exception("PDF generation failed: %s", pdf_exc)
        pdf_b64 = ""

    run_id = result["pipeline_run_id"]
    req_preview = result["report_data"].get("original_requirement", "")[:200]

    pipeline_data = {
        "run_id":       run_id,
        "timestamp":    summary_data.get("created_at", ""),
        "req_preview":  req_preview,
        "summary":      summary_data,
        "report_data":  result["report_data"],
        "html_content": result["html_content"],
        "pdf_base64":   pdf_b64,
    }

    # Persist to MongoDB
    try:
        await mongo_store.save(run_id, pipeline_data)
    except Exception as store_exc:
        logger.exception("MongoDB store save failed: %s", store_exc)

    # Link pipeline result to the project draft (and specific requirement) if provided
    if req.project_draft_id:
        try:
            await mongo_store.link_pipeline(req.project_draft_id, pipeline_data, req.req_id)
        except Exception as link_exc:
            logger.exception("link_pipeline failed for draft %s: %s", req.project_draft_id, link_exc)

        # Persist HTML report to project_assets volume for long-term file access
        try:
            report_path = _REPORTS_DIR / req.project_draft_id / f"{run_id}.html"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(result["html_content"], encoding="utf-8")
        except Exception as file_exc:
            logger.exception("HTML report file write failed: %s", file_exc)

    return FinalizeResponse(
        pipeline_run_id=run_id,
        html_content=result["html_content"],
        report_data=result["report_data"],
        pdf_base64=pdf_b64,
        summary=PipelineSummary(**summary_data),
    )


# ── Generación de código ─────────────────────────────────────────────────────

@router.post("/pipeline/generate-code")
async def generate_code(
    req: GenerateCodeRequest,
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Genera módulos Python + tests Pytest desde las features de un refinamiento."""
    doc = await mongo_store.get(req.run_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Refinamiento no encontrado.")

    features = (doc.get("report_data") or {}).get("features") or []
    if not features:
        raise HTTPException(status_code=400, detail="No hay features disponibles para generar código.")

    try:
        result = await run_in_threadpool(
            request.app.state.pipeline.generate_code_from_features,
            features,
        )
    except Exception as exc:
        _raise_http(exc)

    try:
        await mongo_store.save_generated_code(req.run_id, result)
    except Exception as save_exc:
        logger.exception("save_generated_code failed: %s", save_exc)

    return result


@router.post("/pipeline/accept-code")
async def accept_code(
    req: AcceptCodeRequest,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Guarda las decisiones HITL (aceptar/cambios) sobre el código generado."""
    decisions = [d.model_dump() for d in req.decisions]
    try:
        await mongo_store.save_code_decisions(
            run_id=req.run_id,
            decisions=decisions,
            global_decision=req.global_decision,
            reviewer=req.reviewer or _user.get("email", ""),
        )
    except Exception as exc:
        logger.exception("save_code_decisions failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"ok": True, "run_id": req.run_id, "global_decision": req.global_decision}


# ── Historial de proyectos ────────────────────────────────────────────────────

@router.get("/pipeline/projects", response_model=ProjectListResponse)
async def list_projects(_user: dict = Depends(get_current_user)) -> ProjectListResponse:
    """Lista todos los proyectos almacenados, ordenados por fecha descendente."""
    items = await mongo_store.list_all()
    return ProjectListResponse(
        projects=[ProjectMeta(**p) for p in items]
    )


@router.get("/pipeline/projects/{run_id}", response_model=ProjectDetailResponse)
async def get_project(run_id: str, _user: dict = Depends(get_current_user)) -> ProjectDetailResponse:
    """Retorna el reporte completo de un proyecto."""
    data = await mongo_store.get(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return ProjectDetailResponse(**data)
