"""Constructores de HTML para mostrar resultados de los agentes."""


def render_rag_result(data: dict) -> str:
    result = data.get("result", "")
    return (
        '<div class="result-card">'
        '<div class="story-header">Análisis Completado — RAG Texto Libre</div>'
        f'<div style="color:#c9d1d9;font-size:0.9rem;white-space:pre-wrap;">{result}</div>'
        "</div>"
    )


def render_contract_a(data: dict) -> str:
    stories   = data.get("user_stories", [])
    agent_ver = data.get("agent_version", "?")
    total_amb = data.get("total_ambiguities_found", 0)
    total_ass = data.get("total_assumptions_made", 0)
    run_id    = data.get("pipeline_run_id", "")

    html = (
        f'<div class="story-header">Análisis Completado · {agent_ver} · {run_id}</div>'
        f'<div style="color:#8b949e;font-size:0.8rem;margin-bottom:0.75rem;">'
        f'{data.get("project_context", "")}</div>'
    )

    priority_labels = {
        "critical": "CRÍTICA", "high": "ALTA", "medium": "MEDIA", "low": "BAJA",
    }
    priority_colors = {
        "critical": "#ef4444", "high": "#f97316",
        "medium": "#eab308", "low": "#22c55e",
    }
    type_labels = {
        "functional": "FUNCIONAL",
        "non_functional": "NO FUNCIONAL",
        "technical": "TÉCNICA",
    }

    for story in stories:
        prio  = story.get("priority", "medium")
        stype = story.get("story_type", "functional")
        color = priority_colors.get(prio, "#eab308")

        html += '<div class="result-card" style="margin-bottom:0.75rem;">'
        html += (
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem;">'
            f'<span class="story-header">{story.get("id", "US-?")} · {type_labels.get(stype, stype.upper())}</span>'
            f'<span style="font-size:0.75rem;color:{color};font-weight:600;">'
            f'{priority_labels.get(prio, prio.upper())}</span>'
            f"</div>"
        )
        html += f'<div class="story-title">{story.get("title", "")}</div>'
        html += (
            f'<div class="story-narrative">'
            f'Como <b>{story.get("as_a", "")}</b>, '
            f'quiero {story.get("i_want", "")}, '
            f'para que {story.get("so_that", "")}'
            f"</div>"
        )

        acs = story.get("acceptance_criteria", [])
        if acs:
            html += '<div style="font-size:0.78rem;color:#8b949e;margin-bottom:0.4rem;">CRITERIOS DE ACEPTACIÓN</div>'
            for ac in acs:
                ac_icon = (
                    '<span class="ac-neg">neg</span>'
                    if ac.get("is_negative_case")
                    else '<span class="ac-check">ok</span>'
                )
                html += f'<div class="ac-item">{ac_icon}<span>{ac.get("description", "")}</span></div>'

        ambs = story.get("ambiguities_resolved", [])
        if ambs:
            html += '<div style="margin-top:0.6rem;">'
            for a in ambs:
                tag = " [LLM]" if a.get("assumption_made") else " [OK]"
                html += f'<span class="amb-tag">{a.get("original_text", "")}{tag}</span>'
            html += "</div>"

        html += "</div>"

    html += (
        f'<div class="metric-row">'
        f'<div class="metric-item"><div class="metric-label">Historias</div>'
        f'<div class="metric-value">{len(stories)}</div></div>'
        f'<div class="metric-item"><div class="metric-label">Ambigüedades</div>'
        f'<div class="metric-value">{total_amb}</div></div>'
        f'<div class="metric-item"><div class="metric-label">Suposiciones</div>'
        f'<div class="metric-value">{total_ass}</div></div>'
        f"</div>"
    )
    return html
