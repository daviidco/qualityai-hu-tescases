"""Integración con Jira: crea Epic → Story → Sub-task desde report_data del pipeline."""
from __future__ import annotations

import os
import re
from typing import Any

from jira import JIRA, JIRAError


def _get_client() -> JIRA:
    url = os.environ.get("JIRA_URL", "")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_TOKEN", "")
    if not url or not email or not token:
        raise RuntimeError("Jira no configurado: verifica JIRA_URL, JIRA_EMAIL y JIRA_API_TOKEN en el .env")
    if "tu-empresa" in url or url == "https://your-company.atlassian.net":
        raise RuntimeError(
            f"Jira no configurado: la URL '{url}' es el valor de ejemplo. "
            "Edita JIRA_URL en el .env con tu subdominio real de Atlassian."
        )
    try:
        return JIRA(server=url, basic_auth=(email, token))
    except JIRAError as exc:
        raise RuntimeError(f"No se pudo conectar a Jira ({url}): {exc.text}") from exc
    except Exception as exc:
        raise RuntimeError(f"No se pudo conectar a Jira ({url}): {exc}") from exc


def _issue_type(env_var: str, default: str) -> str:
    return os.environ.get(env_var, default)


def _generate_project_key(project_name: str) -> str:
    """AIQ + siglas del nombre, máx 10 chars."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", "", project_name).upper()
    words = clean.split()
    abbrev = "".join(w[0] for w in words if w)[:7] or "PRJ"
    return f"AIQ{abbrev}"[:10]


def _resolve_account_id(jira: JIRA, email: str) -> str | None:
    """Busca accountId de un usuario por email. None si no existe."""
    try:
        users = jira.search_users(query=email, maxResults=1)
        if users and hasattr(users[0], 'accountId') and users[0].accountId:
            return users[0].accountId
    except Exception:  # noqa: BLE001
        pass
    return None


def create_jira_project(
    project_name: str,
    project_key: str,
    lead_email: str,
) -> dict[str, str]:
    """Crea proyecto Jira Software. Retorna {key, name, url}.
    Si lead_email no existe en Jira, crea sin lead."""
    jira = _get_client()
    # Prefer the resolved email; fall back to the authenticated API user
    account_id = _resolve_account_id(jira, lead_email)
    if not account_id:
        try:
            account_id = jira.myself().get("accountId")
        except Exception:
            account_id = None
    base_url = os.environ["JIRA_URL"].rstrip("/")

    # Use REST API directly — jira.create_project() omits required Cloud fields
    payload: dict[str, Any] = {
        "key": project_key,
        "name": project_name,
        "projectTypeKey": os.environ.get("JIRA_PROJECT_TYPE", "software"),
        "projectTemplateKey": os.environ.get(
            "JIRA_PROJECT_TEMPLATE",
            "com.pyxis.greenhopper.jira:gh-scrum-template",
        ),
    }
    if account_id:
        payload["leadAccountId"] = account_id

    try:
        response = jira._session.post(
            f"{base_url}/rest/api/2/project",
            json=payload,
        )
        if not response.ok:
            try:
                err = response.json()
                msgs = err.get("errorMessages") or []
                errs = err.get("errors") or {}
                body = "; ".join(msgs) + (" — " + str(errs) if errs else "") if msgs or errs else response.text
            except Exception:
                body = response.text
            raise RuntimeError(f"Error creando proyecto Jira '{project_key}' ({response.status_code}): {body}")
        data = response.json()
        return {
            "key": data["key"],
            "name": project_name,
            "url": f"{base_url}/browse/{data['key']}",
        }
    except RuntimeError:
        raise
    except JIRAError as exc:
        raise RuntimeError(f"Error creando proyecto Jira '{project_key}': {exc.text}") from exc
    except Exception as exc:
        raise RuntimeError(f"Error creando proyecto Jira '{project_key}': {exc}") from exc


def _resolve_reporter(jira: JIRA, email: str) -> dict[str, Any]:
    """Retorna dict reporter compatible con Jira Cloud/Server.
    Si el email no existe en Jira devuelve dict vacío — Jira asigna reporter por defecto
    (el usuario autenticado / service account)."""
    try:
        users = jira.search_users(query=email, maxResults=1)
        if not users:
            return {}
        if hasattr(users[0], 'accountId') and users[0].accountId:
            return {"reporter": {"id": users[0].accountId}}
        return {"reporter": {"name": email}}
    except Exception:  # noqa: BLE001
        return {}


def create_tickets(
    project_key: str,
    report_data: dict,
    run_id: str,
    reporter_email: str,
) -> dict[str, Any]:
    """
    Crea la jerarquía de tickets en Jira a partir de report_data.

    Retorna un dict con las URLs creadas:
    {
        "epic": {"key": "PROJ-1", "url": "..."},
        "stories": [{"key": "PROJ-2", "user_story_id": "US-001", "url": "..."}],
        "subtasks": [{"key": "PROJ-3", "criterion_id": "AC-001", "url": "..."}],
        "total_created": N,
    }
    """
    jira = _get_client()
    project = project_key
    reporter = _resolve_reporter(jira, reporter_email)

    requirement = " ".join(report_data.get("original_requirement", "").split())[:100] or f"Pipeline {run_id[:8]}"
    user_stories = report_data.get("user_stories", [])

    epic_type = _issue_type("JIRA_EPIC_TYPE", "Epic")
    story_type = _issue_type("JIRA_STORY_TYPE", "Story")
    subtask_type = _issue_type("JIRA_SUBTASK_TYPE", "Sub-task")

    result: dict[str, Any] = {"epic": None, "stories": [], "subtasks": [], "total_created": 0}

    # ── 1. Crear Epic ─────────────────────────────────────────────────────────
    epic_fields: dict[str, Any] = {
        "project": {"key": project},
        "summary": f"[QualityAI] {requirement}",
        "description": _epic_description(report_data),
        "issuetype": {"name": epic_type},
        "labels": ["qualityai", "auto-generated"],
        **reporter,
    }
    epic_name_field = os.environ.get("JIRA_EPIC_NAME_FIELD", "customfield_10011")
    epic_fields[epic_name_field] = requirement[:255]

    try:
        epic = jira.create_issue(fields=epic_fields)
    except JIRAError as exc:
        raise RuntimeError(f"Error creando Epic en Jira: {exc.text or exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Error creando Epic en Jira: {exc}") from exc

    base_url = os.environ["JIRA_URL"].rstrip("/")
    result["epic"] = {"key": epic.key, "url": f"{base_url}/browse/{epic.key}"}
    result["total_created"] += 1

    # ── 2. Crear Story + Sub-tasks por Historia de Usuario ───────────────────
    for story in user_stories:
        story_fields: dict[str, Any] = {
            "project": {"key": project},
            "summary": f"[{story['id']}] {story['title']}",
            "description": _story_description(story),
            "issuetype": {"name": story_type},
            "labels": ["qualityai", story.get("priority", "medium"), story.get("story_type", "functional")],
            **reporter,
        }

        epic_link_field = os.environ.get("JIRA_EPIC_LINK_FIELD", "customfield_10014")
        story_fields[epic_link_field] = epic.key

        try:
            jira_story = jira.create_issue(fields=story_fields)
        except JIRAError as exc:
            raise RuntimeError(f"Error creando Story {story['id']}: {exc.text}") from exc

        result["stories"].append({
            "key": jira_story.key,
            "user_story_id": story["id"],
            "url": f"{base_url}/browse/{jira_story.key}",
        })
        result["total_created"] += 1

        # ── 3. Sub-task por Criterio de Aceptación ────────────────────────────
        for ac in story.get("acceptance_criteria", []):
            subtask_fields: dict[str, Any] = {
                "project": {"key": project},
                "parent": {"key": jira_story.key},
                "summary": f"[{ac['id']}] {ac['description'][:100]}",
                "description": _subtask_description(ac),
                "issuetype": {"name": subtask_type},
                "labels": ["qualityai", "acceptance-criteria"],
                **reporter,
            }
            try:
                subtask = jira.create_issue(fields=subtask_fields)
            except JIRAError as exc:
                raise RuntimeError(f"Error creando Sub-task {ac['id']}: {exc.text}") from exc

            result["subtasks"].append({
                "key": subtask.key,
                "criterion_id": ac["id"],
                "url": f"{base_url}/browse/{subtask.key}",
            })
            result["total_created"] += 1

    return result


def _epic_description(report_data: dict) -> str:
    req = report_data.get("original_requirement", "")
    ctx = report_data.get("project_context", "")
    n_stories = report_data.get("total_stories", 0)
    n_scenarios = report_data.get("total_scenarios", 0)
    coverage = report_data.get("coverage_pct", 0)

    lines = [
        "h2. Requerimiento Original",
        "{noformat}",
        req,
        "{noformat}",
        "",
        "h2. Contexto del Proyecto",
        ctx or "_Sin contexto adicional._",
        "",
        "h2. Métricas del Pipeline",
        f"* Historias de Usuario: {n_stories}",
        f"* Escenarios de Test: {n_scenarios}",
        f"* Cobertura AC: {coverage}%",
        "",
        "_Generado automáticamente por QualityAI · Módulo 3_",
    ]
    return "\n".join(lines)


def _story_description(story: dict) -> str:
    lines = [
        "h2. Historia de Usuario",
        f"*Como* {story.get('as_a', '')},",
        f"*quiero* {story.get('i_want', '')},",
        f"*para que* {story.get('so_that', '')}.",
        "",
        f"*Prioridad:* {story.get('priority', '').upper()}",
        f"*Tipo:* {story.get('story_type', '')}",
    ]

    rules = story.get("business_rules", [])
    if rules:
        lines += ["", "h3. Reglas de Negocio"]
        lines += [f"* {r}" for r in rules]

    acs = story.get("acceptance_criteria", [])
    if acs:
        lines += ["", "h3. Criterios de Aceptación"]
        for ac in acs:
            neg = " _(caso negativo)_" if ac.get("is_negative_case") else ""
            lines.append(f"* *{ac['id']}*{neg}: {ac['description']}")

    lines += ["", "_Generado automáticamente por QualityAI · Módulo 3_"]
    return "\n".join(lines)


def _subtask_description(ac: dict) -> str:
    bv = ac.get("boundary_values", [])
    boundary = "\n".join(f"* {v}" for v in bv) if bv else "_Sin valores de frontera_"
    neg = "Sí" if ac.get("is_negative_case") else "No"

    return "\n".join([
        "h2. Criterio de Aceptación",
        f"*{ac.get('id', '')}*: {ac.get('description', '')}",
        "",
        "h3. Escenario (Given / When / Then)",
        f"*Dado que:* {ac.get('given', '')}",
        f"*Cuando:* {ac.get('when', '')}",
        f"*Entonces:* {ac.get('then', '')}",
        "",
        f"*Caso negativo:* {neg}",
        "",
        "h3. Valores de Frontera",
        boundary,
        "",
        "_Generado automáticamente por QualityAI · Módulo 3_",
    ])
