from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from src.contract_a import RefinedRequirements  # qualityai-modulo1/src/contract_a.py
from schemas import (
    RefineRequest,
    AgentRagResponse,
    AnalyzeResponse,
    AmbiguityInfo,
    HITLRefineRequest,
)

router = APIRouter(tags=["Agents"])


@router.post(
    "/agent-rag/refine",
    response_model=AgentRagResponse,
    summary="Refinar requerimiento con RAG básico (texto libre)",
    description=(
        "Agente v1: busca historias similares en ChromaDB y genera historias "
        "de usuario en **texto libre** usando el contexto recuperado."
    ),
)
async def refine_agent_rag(req: RefineRequest, request: Request) -> AgentRagResponse:
    try:
        result: str = await run_in_threadpool(
            request.app.state.agent_rag.process,
            req.requirement,
            req.top_k,
        )
        return AgentRagResponse(
            requirement=req.requirement,
            agent_version="1.0.0",
            result=result,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/agent-json/refine",
    response_model=RefinedRequirements,
    summary="Refinar requerimiento con salida JSON estructurada (Contract A)",
    description=(
        "Agente v2: RAG + salida **JSON validada con Pydantic** (Contract A). "
        "Incluye reintentos automáticos si el LLM produce JSON inválido."
    ),
)
async def refine_agent_json(req: RefineRequest, request: Request) -> RefinedRequirements:
    try:
        return await run_in_threadpool(
            request.app.state.agent_json.process,
            req.requirement,
            req.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/agent-ambiguity/refine",
    response_model=RefinedRequirements,
    summary="Refinar requerimiento con detección de ambigüedades pre-LLM",
    description=(
        "Agente v3: detector determinístico de ambigüedades (IEEE 830 / ISO 25010) "
        "**antes** de llamar al LLM. Las ambigüedades detectadas se inyectan en el "
        "prompt para que el modelo las resuelva explícitamente."
    ),
)
async def refine_agent_ambiguity(req: RefineRequest, request: Request) -> RefinedRequirements:
    try:
        return await run_in_threadpool(
            request.app.state.agent_ambiguity.process,
            req.requirement,
            req.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Agent v4 HITL — Step 1 ───────────────────────────────────────────────────

@router.post(
    "/agent-hitl/ambiguities",
    response_model=AnalyzeResponse,
    summary="[HITL step 1] Detectar ambigüedades en el requerimiento",
    description=(
        "Agente v4 — paso 1 de 2. Analiza el requerimiento con el detector "
        "determinístico (IEEE 830 / ISO 25010) y devuelve la lista de ambigüedades "
        "para que el analista las revise en el frontend. **No llama al LLM.** "
        "Si `has_ambiguities` es `false`, puedes ir directo a `/agent-hitl/refine` "
        "con `resolutions: []`."
    ),
)
async def hitl_ambiguities(req: RefineRequest, request: Request) -> AnalyzeResponse:
    try:
        ambiguities = await run_in_threadpool(
            request.app.state.agent_hitl.analyze,
            req.requirement,
        )
        return AnalyzeResponse(
            requirement=req.requirement,
            has_ambiguities=bool(ambiguities),
            ambiguities=[
                AmbiguityInfo(
                    word=a.word,
                    category=a.category,
                    suggestion=a.suggestion,
                    context=a.context,
                    severity=a.severity,
                )
                for a in ambiguities
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ── Agent v4 HITL — Step 2 ───────────────────────────────────────────────────

@router.post(
    "/agent-hitl/refine",
    response_model=RefinedRequirements,
    summary="[HITL step 2] Refinar con las resoluciones del analista (Contract A)",
    description=(
        "Agente v4 — paso 2 de 2. Recibe las decisiones del analista sobre cada "
        "ambigüedad y genera las historias de usuario. Las resoluciones confirmadas "
        "se inyectan en el prompt como **hechos** (`assumption_made: false`), "
        "eliminando las suposiciones del LLM."
    ),
)
async def hitl_refine(req: HITLRefineRequest, request: Request) -> RefinedRequirements:
    try:
        resolutions = [r.model_dump() for r in req.resolutions]
        return await run_in_threadpool(
            request.app.state.agent_hitl.process_with_resolutions,
            req.requirement,
            resolutions,
            req.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
