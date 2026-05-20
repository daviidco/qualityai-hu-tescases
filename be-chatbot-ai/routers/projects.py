"""Endpoints de gestión de proyectos, asignación de miembros y exportación a Jira."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

import mongo_store
from db import get_db
from dependencies import get_current_user, require_analyst_or_leader, require_scrum_or_admin
from schemas import (
    AssignAnalystRequest,
    JiraExportResponse,
    ProjectCreateRequest,
    ProjectDraftOut,
    ProjectMemberAdd,
    ProjectMemberOut,
    ProjectMembersResponse,
    ProjectUpdateRequest,
    RequirementCreate,
    RequirementOut,
    RefinementOut,
    StoryAssignRequest,
    StoryAssignmentOut,
)

router = APIRouter(tags=["Projects"])


# ── Proyectos CRUD ────────────────────────────────────────────────────────────

@router.post("/projects", response_model=ProjectDraftOut, status_code=201)
async def create_project(
    req: ProjectCreateRequest,
    current_user: dict = Depends(require_scrum_or_admin),
) -> ProjectDraftOut:
    """Crea un proyecto draft (pre-pipeline). El requerimiento es opcional al crear."""
    existing = await get_db().projects.find_one({"project_name": req.project_name})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un proyecto con el nombre '{req.project_name}'",
        )
    run_id = await mongo_store.create_draft(
        project_name=req.project_name,
        created_by=current_user["email"],
        requirement=req.requirement,
        client_name=req.client_name,
        contact_name=req.contact_name,
        contact_email=str(req.contact_email) if req.contact_email else None,
        description=req.description,
    )
    project = await mongo_store.get(run_id)
    return _to_draft_out(project)


@router.patch("/projects/{run_id}", response_model=ProjectDraftOut)
async def update_project(
    run_id: str,
    req: ProjectUpdateRequest,
    current_user: dict = Depends(require_scrum_or_admin),
) -> ProjectDraftOut:
    """Actualiza datos del proyecto (nombre, cliente, contacto, requerimiento)."""
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if current_user["role"] == "scrum_leader" and project.get("created_by") != current_user["email"]:
        raise HTTPException(status_code=403, detail="No tienes permisos sobre este proyecto")

    await mongo_store.update_project(run_id, req.model_dump(exclude_none=True))
    updated = await mongo_store.get(run_id)
    return _to_draft_out(updated)


@router.delete("/projects/{run_id}", status_code=204)
async def delete_project(
    run_id: str,
    current_user: dict = Depends(require_scrum_or_admin),
) -> None:
    """Elimina un proyecto, su logo y todos sus datos asociados."""
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    if current_user["role"] == "scrum_leader" and project.get("created_by") != current_user["email"]:
        raise HTTPException(status_code=403, detail="No tienes permisos sobre este proyecto")

    if logo_path := project.get("logo_path"):
        try:
            Path(logo_path).unlink(missing_ok=True)
        except Exception:
            pass

    await mongo_store.delete(run_id)


@router.get("/projects", response_model=list[ProjectDraftOut])
async def list_projects(
    current_user: dict = Depends(get_current_user),
) -> list[ProjectDraftOut]:
    """Lista proyectos filtrados por rol del usuario."""
    items = await mongo_store.list_projects_for_user(
        current_user["email"], current_user["role"]
    )
    return [_to_draft_out(p) for p in items]


@router.get("/projects/{run_id}/detail", response_model=dict)
async def get_project_detail(
    run_id: str,
    _user: dict = Depends(get_current_user),
) -> dict:
    """Retorna el documento completo de un proyecto."""
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    # Convertir datetime a ISO para serialización JSON
    if isinstance(project.get("created_at"), datetime):
        project["created_at"] = project["created_at"].isoformat()
    if isinstance(project.get("reviewed_at"), datetime):
        project["reviewed_at"] = project["reviewed_at"].isoformat()
    return project


@router.patch("/projects/{run_id}/status", status_code=200)
async def update_project_status(
    run_id: str,
    body: dict,
    _user: dict = Depends(require_analyst_or_leader),
) -> dict:
    """Actualiza el status del proyecto (created → analyzing → completed)."""
    new_status = body.get("status")
    allowed = {"created", "analyzing", "completed"}
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status debe ser uno de: {allowed}")
    await mongo_store.update_status(run_id, new_status)
    return {"run_id": run_id, "status": new_status}


# ── Requerimientos ───────────────────────────────────────────────────────────

@router.post("/projects/{run_id}/requirements", response_model=RequirementOut, status_code=201)
async def add_requirement(
    run_id: str,
    req: RequirementCreate,
    current_user: dict = Depends(require_analyst_or_leader),
) -> RequirementOut:
    """Agrega un requerimiento al proyecto."""
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    req_id = await mongo_store.add_requirement(
        run_id, req.title, req.content, current_user["email"], req.attachment_name
    )
    return RequirementOut(
        req_id=req_id,
        title=req.title,
        content=req.content,
        created_at=datetime.now(timezone.utc).isoformat(),
        created_by=current_user["email"],
        status="created",
        attachment_name=req.attachment_name,
        refinements=[],
    )


@router.get("/projects/{run_id}/requirements", response_model=list[RequirementOut])
async def list_requirements(
    run_id: str,
    _user: dict = Depends(get_current_user),
) -> list[RequirementOut]:
    """Lista los requerimientos del proyecto."""
    doc = await mongo_store.get(run_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return [_to_req_out(r) for r in (doc.get("requirements") or [])]


@router.patch("/projects/{run_id}/requirements/{req_id}", response_model=RequirementOut)
async def update_requirement(
    run_id: str,
    req_id: str,
    body: RequirementCreate,
    _user: dict = Depends(require_analyst_or_leader),
) -> RequirementOut:
    """Actualiza título y contenido de un requerimiento."""
    await mongo_store.update_requirement(run_id, req_id, body.title, body.content)
    doc = await mongo_store.get(run_id)
    reqs = doc.get("requirements") or [] if doc else []
    r = next((r for r in reqs if r["req_id"] == req_id), None)
    if not r:
        raise HTTPException(status_code=404, detail="Requerimiento no encontrado")
    return _to_req_out(r)


# ── Asignación de analistas ───────────────────────────────────────────────────

@router.post("/projects/{run_id}/assign-analyst", status_code=200)
async def assign_analyst_to_project(
    run_id: str,
    req: AssignAnalystRequest,
    current_user: dict = Depends(require_scrum_or_admin),
) -> dict:
    """Asigna un analista a un proyecto."""
    db = get_db()
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    if current_user["role"] == "scrum_leader" and project.get("created_by") != current_user["email"]:
        raise HTTPException(status_code=403, detail="No tienes permisos sobre este proyecto")

    user = await db.users.find_one({"email": req.analyst_email, "is_active": True})
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {req.analyst_email} no encontrado")

    assigned = await mongo_store.assign_analyst(run_id, req.analyst_email)
    return {"assigned": assigned, "analyst_email": req.analyst_email}


# ── Asignación de historias a desarrolladores ─────────────────────────────────

@router.post(
    "/projects/{run_id}/stories/{story_id}/assign",
    response_model=StoryAssignmentOut,
)
async def assign_story(
    run_id: str,
    story_id: str,
    req: StoryAssignRequest,
    current_user: dict = Depends(require_scrum_or_admin),
) -> StoryAssignmentOut:
    """Asigna una historia de usuario a un developer."""
    db = get_db()
    user = await db.users.find_one({"email": req.developer_email, "is_active": True})
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {req.developer_email} no encontrado")
    if user["role"] != "developer":
        raise HTTPException(status_code=400, detail="Solo se pueden asignar usuarios con rol developer")

    await mongo_store.assign_story(run_id, story_id, req.developer_email, current_user["email"])
    return StoryAssignmentOut(
        story_id=story_id,
        developer_email=req.developer_email,
        developer_type=user.get("developer_type"),
        assigned_by=current_user["email"],
        assigned_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/projects/{run_id}/assignments", response_model=list[StoryAssignmentOut])
async def get_story_assignments(
    run_id: str,
    _user: dict = Depends(get_current_user),
) -> list[StoryAssignmentOut]:
    """Retorna las asignaciones de historias del proyecto."""
    db = get_db()
    assignments = await mongo_store.get_story_assignments(run_id)
    result = []
    for a in assignments:
        dev = await db.users.find_one({"email": a["developer_email"]}, {"developer_type": 1})
        result.append(StoryAssignmentOut(
            story_id=a["story_id"],
            developer_email=a["developer_email"],
            developer_type=(dev or {}).get("developer_type"),
            assigned_by=a["assigned_by"],
            assigned_at=a["assigned_at"],
        ))
    return result


# ── Asignación de miembros (developers) ──────────────────────────────────────

@router.post("/projects/{run_id}/members", response_model=ProjectMemberOut, status_code=201)
async def add_member(
    run_id: str,
    req: ProjectMemberAdd,
    current_user: dict = Depends(require_analyst_or_leader),
) -> ProjectMemberOut:
    """Asigna un desarrollador a un proyecto."""
    db = get_db()
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    user = await db.users.find_one({"email": req.email, "is_active": True})
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {req.email} no encontrado")
    if user["role"] != "developer":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden asignar usuarios con rol developer",
        )

    member_doc = {
        "email": req.email,
        "developer_type": user.get("developer_type", "backend"),
        "assigned_at": datetime.now(timezone.utc).isoformat(),
        "assigned_by": current_user["email"],
    }
    result = await db.projects.update_one(
        {"run_id": run_id, "assigned_members.email": {"$ne": req.email}},
        {"$push": {"assigned_members": member_doc}},
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{req.email} ya está asignado a este proyecto",
        )
    return ProjectMemberOut(**member_doc)


@router.delete("/projects/{run_id}/team/{email}", status_code=200)
async def remove_team_member(
    run_id: str,
    email: str,
    current_user: dict = Depends(require_scrum_or_admin),
) -> dict:
    """Quita un miembro del equipo asignado (assigned_analysts)."""
    result = await get_db().projects.update_one(
        {"run_id": run_id},
        {"$pull": {"assigned_analysts": email}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return {"removed": email}


@router.delete("/projects/{run_id}/members/{email}", status_code=204)
async def remove_member(
    run_id: str,
    email: str,
    _user: dict = Depends(require_analyst_or_leader),
) -> None:
    db = get_db()
    result = await db.projects.update_one(
        {"run_id": run_id},
        {"$pull": {"assigned_members": {"email": email}}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")


@router.get("/projects/{run_id}/members", response_model=ProjectMembersResponse)
async def list_members(
    run_id: str,
    _user: dict = Depends(get_current_user),
) -> ProjectMembersResponse:
    db = get_db()
    doc = await db.projects.find_one(
        {"run_id": run_id},
        {"_id": 0, "assigned_members": 1},
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    members = doc.get("assigned_members") or []
    return ProjectMembersResponse(
        run_id=run_id,
        members=[ProjectMemberOut(**m) for m in members],
    )


# ── Logo del proyecto ─────────────────────────────────────────────────────────

_LOGO_DIR = Path("/app/storage/logos")
_ALLOWED_LOGO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/projects/{run_id}/logo", status_code=200)
async def upload_logo(
    run_id: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(require_scrum_or_admin),
) -> dict:
    """Sube el logo del proyecto y guarda el path en MongoDB."""
    if file.content_type not in _ALLOWED_LOGO_TYPES:
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes JPG, PNG, WEBP o GIF.")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo supera 5 MB.")

    _LOGO_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "logo.jpg").suffix or ".jpg"
    dest = _LOGO_DIR / f"{run_id}{ext}"
    dest.write_bytes(content)

    await mongo_store.update_logo_path(run_id, str(dest))
    return {"logo_url": f"/projects/{run_id}/logo"}


@router.get("/projects/{run_id}/logo")
async def get_logo(
    run_id: str,
    _user: dict = Depends(get_current_user),
) -> FileResponse:
    """Retorna el archivo de logo del proyecto."""
    project = await mongo_store.get(run_id)
    if not project or not project.get("logo_path"):
        raise HTTPException(status_code=404, detail="Logo no encontrado.")
    path = Path(project["logo_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo de logo no encontrado.")
    return FileResponse(str(path))


# ── Exportación a Jira ────────────────────────────────────────────────────────

@router.post("/projects/{run_id}/jira", response_model=JiraExportResponse)
async def export_to_jira(
    run_id: str,
    current_user: dict = Depends(require_scrum_or_admin),
) -> JiraExportResponse:
    """Crea la jerarquía Epic → Story → Sub-task en Jira."""
    project = await mongo_store.get(run_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    report_data = project.get("report_data")
    if not report_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El proyecto no tiene report_data — completa el pipeline primero",
        )

    from jira_client import create_tickets
    try:
        tickets = await run_in_threadpool(create_tickets, report_data, run_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    db = get_db()
    await db.projects.update_one(
        {"run_id": run_id},
        {"$set": {
            "jira_export": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "exported_by": current_user["email"],
                **tickets,
            }
        }},
    )

    return JiraExportResponse(
        run_id=run_id,
        epic_key=tickets["epic"]["key"],
        epic_url=tickets["epic"]["url"],
        total_created=tickets["total_created"],
        stories=tickets["stories"],
        subtasks=tickets["subtasks"],
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _to_req_out(r: dict) -> RequirementOut:
    created_at = r.get("created_at", "")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    refinements = []
    for ref in r.get("refinements") or []:
        ref_at = ref.get("created_at", "")
        if isinstance(ref_at, datetime):
            ref_at = ref_at.isoformat()
        refinements.append(RefinementOut(
            run_id=ref.get("run_id", ""),
            created_at=str(ref_at),
            created_by=ref.get("created_by", ""),
            review_status=ref.get("review_status", "pending_review"),
            summary=ref.get("summary"),
        ))
    return RequirementOut(
        req_id=r["req_id"],
        title=r.get("title", ""),
        content=r.get("content", ""),
        created_at=str(created_at),
        created_by=r.get("created_by", ""),
        status=r.get("status", "created"),
        attachment_name=r.get("attachment_name"),
        refinements=refinements,
    )


def _to_draft_out(p: dict) -> ProjectDraftOut:
    summary = p.get("summary") or {}
    created_at = p.get("created_at", "")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    reqs = p.get("requirements") or []
    req_preview = p.get("req_preview", "")
    if not req_preview and reqs:
        req_preview = reqs[0].get("content", "")[:200]
    logo_url = f"/projects/{p['run_id']}/logo" if p.get("logo_path") else None
    req_count    = len(reqs)
    req_analyzed = sum(1 for r in reqs if r.get("status") == "completed")
    return ProjectDraftOut(
        run_id=p["run_id"],
        project_name=p.get("project_name", ""),
        description=p.get("description"),
        client_name=p.get("client_name"),
        contact_name=p.get("contact_name"),
        contact_email=p.get("contact_email"),
        req_preview=req_preview,
        status=p.get("status", "created"),
        created_by=p.get("created_by", ""),
        created_at=str(created_at),
        assigned_analysts=p.get("assigned_analysts") or [],
        review_status=p.get("review_status"),
        total_stories=summary.get("total_stories", 0),
        total_scenarios=summary.get("total_scenarios", 0),
        logo_url=logo_url,
        req_count=req_count,
        req_analyzed=req_analyzed,
    )
