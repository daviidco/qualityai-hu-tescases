"""CRUD de proyectos sobre la colección MongoDB 'projects'."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from db import get_db

_LISTING_PROJECTION = {
    "_id": 0,
    "run_id": 1,
    "timestamp": 1,
    "req_preview": 1,
    "review_status": 1,
    "reviewer": 1,
    "llm_provider": 1,
    "summary": 1,
}

_FULL_PROJECTION = {"_id": 0}


async def save(run_id: str, data: dict) -> None:
    """Inserta o reemplaza el documento del proyecto."""
    db = get_db()
    doc = {**data, "run_id": run_id}
    # Extraer campos de primer nivel para indexar/filtrar rápido
    hitl = data.get("report_data", {}).get("hitl", {})
    doc["review_status"] = hitl.get("review_status", "pending_review")
    doc["reviewer"] = hitl.get("reviewer") or None
    reviewed_at = hitl.get("reviewed_at")
    doc["reviewed_at"] = datetime.fromisoformat(reviewed_at) if reviewed_at else None
    doc["llm_provider"] = data.get("report_data", {}).get("llm_provider", "")
    await db.projects.replace_one({"run_id": run_id}, doc, upsert=True)


async def list_all() -> list[dict]:
    """Devuelve metadata ligera de todos los proyectos, del más reciente al más antiguo."""
    db = get_db()
    cursor = db.projects.find({}, _LISTING_PROJECTION).sort("created_at", -1)
    return await cursor.to_list(length=None)


async def list_by_status(status: str) -> list[dict]:
    """Devuelve proyectos filtrados por review_status."""
    db = get_db()
    cursor = db.projects.find({"review_status": status}, _LISTING_PROJECTION).sort("created_at", -1)
    return await cursor.to_list(length=None)


async def get(run_id: str) -> dict | None:
    """Devuelve el documento completo de un proyecto, o None si no existe."""
    db = get_db()
    return await db.projects.find_one({"run_id": run_id}, _FULL_PROJECTION)


async def delete(run_id: str) -> bool:
    """Elimina un proyecto. Devuelve True si existía."""
    db = get_db()
    result = await db.projects.delete_one({"run_id": run_id})
    return result.deleted_count > 0


# ── Proyectos pre-pipeline (drafts) ──────────────────────────────────────────

async def create_draft(
    project_name: str,
    created_by: str,
    requirement: str | None = None,
    client_name: str | None = None,
    contact_name: str | None = None,
    contact_email: str | None = None,
    description: str | None = None,
) -> str:
    """Crea un proyecto draft. El requerimiento inicial es opcional."""
    run_id = str(uuid.uuid4())
    db = get_db()

    # Si se proporciona requerimiento inicial, lo guardamos en el array
    initial_reqs = []
    if requirement and requirement.strip():
        initial_reqs.append({
            "req_id": str(uuid.uuid4()),
            "title": "Requerimiento inicial",
            "content": requirement.strip(),
            "created_at": datetime.now(timezone.utc),
            "created_by": created_by,
            "status": "created",
            "refinements": [],
        })

    await db.projects.insert_one({
        "run_id": run_id,
        "project_name": project_name,
        "description": description or None,
        "client_name": client_name or None,
        "contact_name": contact_name or None,
        "contact_email": contact_email or None,
        "req_preview": (requirement or "")[:200],
        "status": "created",
        "created_by": created_by,
        "created_at": datetime.now(timezone.utc),
        "assigned_analysts": [],
        "assigned_members": [],
        "story_assignments": [],
        "requirements": initial_reqs,
        "review_status": None,
        "report_data": None,
        "html_content": None,
        "pdf_base64": None,
        "summary": None,
        "jira_export": None,
    })
    return run_id


async def add_requirement(
    run_id: str, title: str, content: str, created_by: str,
    attachment_name: str | None = None,
) -> str:
    """Agrega un nuevo requerimiento al proyecto. Devuelve el req_id."""
    req_id = str(uuid.uuid4())
    db = get_db()
    req_doc = {
        "req_id": req_id,
        "title": title,
        "content": content,
        "created_at": datetime.now(timezone.utc),
        "created_by": created_by,
        "status": "created",
        "attachment_name": attachment_name or None,
        "refinements": [],
    }
    await db.projects.update_one(
        {"run_id": run_id},
        {
            "$push": {"requirements": req_doc},
            "$set": {"req_preview": content[:200]},
        },
    )
    return req_id


async def update_requirement(
    run_id: str, req_id: str, title: str | None, content: str | None,
    attachment_name: str | None = None,
) -> bool:
    """Actualiza título, contenido y/o adjunto de un requerimiento."""
    db = get_db()
    set_fields: dict = {}
    if title is not None:
        set_fields["requirements.$.title"] = title
    if content is not None:
        set_fields["requirements.$.content"] = content
    if attachment_name is not None:
        set_fields["requirements.$.attachment_name"] = attachment_name
    if not set_fields:
        return False
    result = await db.projects.update_one(
        {"run_id": run_id, "requirements.req_id": req_id},
        {"$set": set_fields},
    )
    return result.modified_count > 0


async def set_requirement_status(run_id: str, req_id: str, status: str) -> None:
    db = get_db()
    await db.projects.update_one(
        {"run_id": run_id, "requirements.req_id": req_id},
        {"$set": {"requirements.$.status": status}},
    )


async def list_projects_for_user(email: str, role: str) -> list[dict]:
    """Lista proyectos filtrados por rol del usuario."""
    db = get_db()
    if role == "admin":
        query: dict = {}
    elif role == "scrum_leader":
        query = {"created_by": email}
    elif role == "analyst":
        query = {"assigned_analysts": email}
    else:
        return []

    projection = {
        "_id": 0, "run_id": 1, "project_name": 1, "description": 1,
        "client_name": 1, "contact_name": 1, "contact_email": 1, "req_preview": 1,
        "status": 1, "created_by": 1, "created_at": 1,
        "assigned_analysts": 1, "review_status": 1, "summary": 1,
        "logo_path": 1, "requirements": 1,
    }
    cursor = db.projects.find(query, projection).sort("created_at", -1)
    return await cursor.to_list(length=None)


async def update_project(run_id: str, fields: dict) -> bool:
    """Actualiza campos editables de un proyecto draft."""
    db = get_db()
    set_doc: dict = {}
    if "project_name" in fields and fields["project_name"]:
        set_doc["project_name"] = fields["project_name"]
    if "description" in fields:
        set_doc["description"] = fields["description"] or None
    if "client_name" in fields:
        set_doc["client_name"] = fields["client_name"] or None
    if "contact_name" in fields:
        set_doc["contact_name"] = fields["contact_name"] or None
    if "contact_email" in fields:
        set_doc["contact_email"] = fields["contact_email"] or None
    if not set_doc:
        return False
    result = await db.projects.update_one({"run_id": run_id}, {"$set": set_doc})
    return result.modified_count > 0


async def assign_analyst(run_id: str, analyst_email: str) -> bool:
    db = get_db()
    result = await db.projects.update_one(
        {"run_id": run_id, "assigned_analysts": {"$ne": analyst_email}},
        {"$push": {"assigned_analysts": analyst_email}},
    )
    return result.modified_count > 0


async def update_status(run_id: str, status: str) -> None:
    db = get_db()
    await db.projects.update_one({"run_id": run_id}, {"$set": {"status": status}})


async def update_logo_path(run_id: str, path: str) -> None:
    db = get_db()
    await db.projects.update_one({"run_id": run_id}, {"$set": {"logo_path": path}})


async def link_pipeline(
    draft_id: str, pipeline_data: dict, req_id: str | None = None
) -> bool:
    """Vincula el resultado del pipeline a un proyecto (y a un requerimiento específico)."""
    db = get_db()
    report_data = pipeline_data.get("report_data") or {}
    hitl = report_data.get("hitl", {})
    summary = pipeline_data.get("summary", {})
    run_id = pipeline_data.get("run_id", "")

    # Actualizar campos raíz del proyecto
    result = await db.projects.update_one(
        {"run_id": draft_id},
        {"$set": {
            "status": "completed",
            "review_status": hitl.get("review_status", "pending_review"),
            "reviewer": hitl.get("reviewer"),
            "summary": summary,
            "report_data": report_data,
            "user_stories": report_data.get("user_stories") or [],
            "test_cases": report_data.get("features") or [],
            "html_content": pipeline_data.get("html_content"),
            "pdf_base64": pipeline_data.get("pdf_base64"),
            "llm_provider": report_data.get("llm_provider", ""),
            "last_analyzed_at": datetime.now(timezone.utc),
        }},
    )

    # Agregar refinamiento al requerimiento específico
    if req_id and run_id:
        refinement = {
            "run_id": run_id,
            "created_at": datetime.now(timezone.utc),
            "created_by": hitl.get("reviewer") or "",
            "review_status": hitl.get("review_status", "pending_review"),
            "summary": summary,
        }
        await db.projects.update_one(
            {"run_id": draft_id, "requirements.req_id": req_id},
            {
                "$push": {"requirements.$.refinements": refinement},
                "$set": {"requirements.$.status": "completed"},
            },
        )

    return result.modified_count > 0


async def save_generated_code(run_id: str, code_data: dict) -> None:
    """Guarda el código generado + análisis V2/V3/V4 en el documento del refinamiento."""
    db = get_db()
    update: dict = {
        "generated_code": code_data.get("generated_code", []),
        "generated_tests": code_data.get("generated_tests", []),
        "code_generation_status": "generated",
        "code_generated_at": datetime.now(timezone.utc),
    }

    # V2: Análisis estático (radon, complexipy, bandit)
    if "quality_report" in code_data:
        update["quality_report"] = code_data["quality_report"]
    if "quality_summary" in code_data:
        update["quality_summary"] = code_data["quality_summary"]

    # V3: Trazabilidad CMMI L3 + cobertura
    if "traceability_matrix" in code_data:
        update["traceability_matrix"] = code_data["traceability_matrix"]
    if "coverage_report" in code_data:
        update["coverage_report"] = code_data["coverage_report"]
    if "cmmi_l3_compliant" in code_data:
        update["cmmi_l3_compliant"] = code_data["cmmi_l3_compliant"]
    if "requirements_coverage_pct" in code_data:
        update["requirements_coverage_pct"] = code_data["requirements_coverage_pct"]
    if "branch_coverage_pct" in code_data:
        update["branch_coverage_pct"] = code_data["branch_coverage_pct"]
    if "line_coverage_pct" in code_data:
        update["line_coverage_pct"] = code_data["line_coverage_pct"]

    # V4: Revisión de código
    if "code_review" in code_data:
        update["code_review"] = code_data["code_review"]

    await db.projects.update_one(
        {"run_id": run_id},
        {"$set": update},
    )


async def save_code_decisions(
    run_id: str, decisions: list[dict], global_decision: str, reviewer: str
) -> None:
    """Guarda las decisiones HITL sobre el código generado."""
    db = get_db()
    await db.projects.update_one(
        {"run_id": run_id},
        {"$set": {
            "code_review_status": global_decision,
            "code_reviewer": reviewer,
            "code_decisions": decisions,
            "code_reviewed_at": datetime.now(timezone.utc),
        }},
    )


async def assign_story(
    run_id: str, story_id: str, dev_email: str, assigned_by: str
) -> None:
    db = get_db()
    await db.projects.update_one(
        {"run_id": run_id},
        {"$pull": {"story_assignments": {"story_id": story_id}}},
    )
    await db.projects.update_one(
        {"run_id": run_id},
        {"$push": {"story_assignments": {
            "story_id": story_id,
            "developer_email": dev_email,
            "assigned_by": assigned_by,
            "assigned_at": datetime.now(timezone.utc).isoformat(),
        }}},
    )


async def unassign_story(run_id: str, story_id: str) -> bool:
    """Elimina la asignación de un desarrollador a una historia."""
    db = get_db()
    result = await db.projects.update_one(
        {"run_id": run_id},
        {"$pull": {"story_assignments": {"story_id": story_id}}},
    )
    return result.modified_count > 0


async def get_story_assignments(run_id: str) -> list[dict]:
    db = get_db()
    doc = await db.projects.find_one(
        {"run_id": run_id},
        {"_id": 0, "story_assignments": 1},
    )
    return (doc or {}).get("story_assignments") or []
