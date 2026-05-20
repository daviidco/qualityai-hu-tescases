"""Panel del Analista: proyectos asignados e inicio de pipeline por requerimiento."""
from __future__ import annotations

import streamlit as st

import api
from config import BACKEND
from handlers import handle_analyze
from ui.icons import icon

_B = 'padding:.15rem .6rem;border-radius:10px;font-size:.75rem;'
_STATUS_BADGE = {
    "created":   f'<span style="background:#1e3a5f;color:#93c5fd;{_B}">{icon("clock",12,"#93c5fd")} Sin analizar</span>',
    "analyzing": f'<span style="background:#1c3a2a;color:#6ee7b7;{_B}">{icon("rocket",12,"#6ee7b7")} Analizando</span>',
    "completed": f'<span style="background:#14532d;color:#86efac;{_B}">{icon("check-circle",12,"#86efac")} Completado</span>',
}
_BS = 'padding:.1rem .45rem;border-radius:8px;font-size:.72rem;'
_REQ_STATUS_BADGE = {
    "created":   f'<span style="background:#1e3a5f;color:#93c5fd;{_BS}">{icon("clock",11,"#93c5fd")} Pendiente</span>',
    "analyzing": f'<span style="background:#1c3a2a;color:#6ee7b7;{_BS}">{icon("rocket",11,"#6ee7b7")} Analizando</span>',
    "completed": f'<span style="background:#14532d;color:#86efac;{_BS}">{icon("check-circle",11,"#86efac")} Completado</span>',
}
_BR = 'padding:.1rem .5rem;border-radius:10px;font-size:.72rem;'
_REVIEW_BADGE = {
    "pending_review": f'<span style="background:#422006;color:#fed7aa;{_BR}">{icon("clock",11,"#fed7aa")} Pendiente revisión</span>',
    "approved":       f'<span style="background:#14532d;color:#86efac;{_BR}">{icon("check-circle",11,"#86efac")} Aprobado</span>',
    "rejected":       f'<span style="background:#450a0a;color:#fca5a5;{_BR}">{icon("x-circle",11,"#fca5a5")} Rechazado</span>',
    "needs_changes":  f'<span style="background:#3b2007;color:#fcd34d;{_BR}">{icon("warning",11,"#fcd34d")} Requiere cambios</span>',
}


def render_analyst_panel() -> None:
    if st.session_state.get("analyst_selected_project"):
        _render_project_detail(st.session_state.analyst_selected_project)
        return
    _render_project_list()


def _render_project_list() -> None:
    st.markdown(
        '<h2 style="color:#e2e8f0;margin-bottom:1.25rem;">Mis Proyectos Asignados</h2>',
        unsafe_allow_html=True,
    )

    projects = api.get(f"{BACKEND}/projects") or []

    if not projects:
        st.info("No tienes proyectos asignados. El Scrum Leader te asignará proyectos.")
        return

    st.markdown(f"**{len(projects)} proyecto(s) asignado(s)**")
    st.markdown("")

    for p in projects:
        _project_card(p)


def _project_card(p: dict) -> None:
    status = p.get("status", "created")
    badge = _STATUS_BADGE.get(status, "")
    has_req = bool(p.get("req_preview", "").strip())

    with st.container(border=True):
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            client = p.get("client_name", "")
            client_str = f" · {client}" if client else ""
            st.markdown(
                f"**{p.get('project_name', 'Sin nombre')}**{client_str} &nbsp; {badge}",
                unsafe_allow_html=True,
            )
            if not has_req:
                st.markdown(
                    f'<span style="color:#f97316;font-size:.8rem;">'
                    f'{icon("warning",12,"#f97316")} Sin requerimientos — puedes agregar uno desde el detalle</span>',
                    unsafe_allow_html=True,
                )
            else:
                preview = p.get("req_preview", "")[:100]
                st.markdown(
                    f'<span style="color:#8b949e;font-size:.85rem;">{preview}…</span>',
                    unsafe_allow_html=True,
                )
            if p.get("total_stories", 0):
                st.caption(
                    f"{p['total_stories']} HU · {p.get('total_scenarios', 0)} test cases"
                )
        with col_btn:
            if st.button("Ver", key=f"analyst_proj_{p['run_id']}", use_container_width=True):
                st.session_state.analyst_selected_project = p["run_id"]
                st.rerun()


def _render_project_detail(run_id: str) -> None:
    if st.button("Volver"):
        st.session_state.analyst_selected_project = None
        st.rerun()

    with st.spinner("Cargando proyecto…"):
        project = api.get(f"{BACKEND}/projects/{run_id}/detail")

    if not project:
        st.error("No se pudo cargar el proyecto.")
        return

    status = project.get("status", "created")
    badge = _STATUS_BADGE.get(status, "")

    st.markdown(
        f'<h2 style="color:#e2e8f0;">{project.get("project_name", "Proyecto")} &nbsp; {badge}</h2>',
        unsafe_allow_html=True,
    )

    # ── Datos del cliente ─────────────────────────────────────────────────────
    client = project.get("client_name", "")
    contact_name = project.get("contact_name", "")
    contact_email = project.get("contact_email", "")

    if client or contact_name or contact_email:
        col1, col2, col3 = st.columns(3)
        if client:
            col1.metric("Cliente", client)
        if contact_name:
            col2.metric("Contacto", contact_name)
        if contact_email:
            col3.markdown(
                f'<div style="margin-top:.5rem;">'
                f'<div style="font-size:.75rem;color:#8b949e;">Email contacto</div>'
                f'<div style="font-size:.9rem;color:#e2e8f0;">{contact_email}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("")

    st.divider()

    # ── Requerimientos ────────────────────────────────────────────────────────
    _section_requirements(run_id, project)


def _section_requirements(run_id: str, project: dict) -> None:
    st.markdown(
        '<h4 style="color:#00bcd4;">Requerimientos</h4>',
        unsafe_allow_html=True,
    )

    reqs = api.get(f"{BACKEND}/projects/{run_id}/requirements") or []

    if not reqs:
        st.warning(
            "Este proyecto no tiene requerimientos cargados aún. "
            "Puedes agregar uno a continuación."
        )
    else:
        for req in reqs:
            _req_card(run_id, req, project)

    # ── Agregar nuevo requerimiento ───────────────────────────────────────────
    with st.expander("Agregar requerimiento"):
        _req_add_form(run_id)


def _req_card(run_id: str, req: dict, project: dict) -> None:
    req_id = req["req_id"]
    title = req.get("title", req_id)
    req_status = req.get("status", "created")
    refinements = req.get("refinements") or []
    content = req.get("content", "")

    with st.container(border=True):
        col_title, col_badge = st.columns([4, 1])
        with col_title:
            st.markdown(f"**{title}**")
        with col_badge:
            st.markdown(_REQ_STATUS_BADGE.get(req_status, ""), unsafe_allow_html=True)

        with st.expander("Ver requerimiento"):
            st.text_area(
                "",
                value=content,
                height=130,
                disabled=True,
                label_visibility="collapsed",
                key=f"req_view_{req_id}",
            )

        # ── Refinamientos pasados ─────────────────────────────────────────────
        if refinements:
            with st.expander(f"Refinamientos anteriores ({len(refinements)})"):
                for ref in refinements:
                    rev_badge = _REVIEW_BADGE.get(ref.get("review_status") or "", "")
                    summary = ref.get("summary") or {}
                    stories = summary.get("total_stories", 0)
                    scenarios = summary.get("total_scenarios", 0)
                    meta = f"{stories} HU · {scenarios} tests" if stories else ""
                    ref_run_id = ref.get("run_id", "")
                    col_meta, col_view = st.columns([4, 1])
                    with col_meta:
                        st.markdown(
                            f'<div style="padding:.4rem 0;">'
                            f'{ref.get("created_at", "")[:16]} &nbsp; {rev_badge}'
                            f'{"&nbsp; <b>" + meta + "</b>" if meta else ""}'
                            f'<span style="color:#8b949e;font-size:.8rem;"> por {ref.get("created_by","")}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with col_view:
                        if ref_run_id and st.button(
                            "Ver", key=f"view_ref_{req_id}_{ref_run_id}"
                        ):
                            existing_ids = {p["run_id"] for p in st.session_state.projects}
                            if ref_run_id not in existing_ids:
                                st.session_state.projects.insert(0, {
                                    "run_id": ref_run_id,
                                    "req_preview": content[:200],
                                    "summary": summary,
                                })
                            st.session_state.active_project = ref_run_id
                            st.session_state.view = "report"
                            st.session_state.analyst_selected_project = None
                            st.rerun()

        # ── Botón de análisis ─────────────────────────────────────────────────
        if content.strip():
            if st.button(
                "Iniciar análisis",
                key=f"analyze_{req_id}",
                type="primary",
                use_container_width=True,
            ):
                st.session_state.current_project_draft_id = run_id
                st.session_state.current_project_name = project.get("project_name", "")
                st.session_state.current_req_id = req_id
                api.patch(f"{BACKEND}/projects/{run_id}/status", {"status": "analyzing"})
                st.session_state.analyst_selected_project = None
                handle_analyze(content)


def _req_add_form(run_id: str) -> None:
    with st.form(f"req_add_analyst_{run_id}", clear_on_submit=True):
        new_title = st.text_input(
            "Título del requerimiento *",
            placeholder="Ej: Módulo de pagos con tarjeta",
        )
        new_content = st.text_area(
            "Descripción / Requerimiento en bruto *",
            height=150,
            placeholder="Describe el requerimiento del sistema de forma libre…",
        )
        save = st.form_submit_button("Agregar requerimiento", type="primary")
    if save:
        errors = []
        if not new_title.strip():
            errors.append("El título es obligatorio.")
        if not new_content.strip() or len(new_content.strip()) < 20:
            errors.append("El contenido debe tener al menos 20 caracteres.")
        for e in errors:
            st.error(e)
        if errors:
            return
        result = api.post(
            f"{BACKEND}/projects/{run_id}/requirements",
            {"title": new_title.strip(), "content": new_content.strip()},
        )
        if result is not None:
            st.success(f"Requerimiento agregado.")
            st.rerun()
