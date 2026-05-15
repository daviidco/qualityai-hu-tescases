"""Panel HITL — Fase 2: revisión y aprobación de test cases."""

import streamlit as st

_ISO_OPTIONS = [
    "functional_suitability", "security", "performance_efficiency",
    "usability", "reliability", "compatibility", "maintainability", "portability",
]
_ISO_LABELS = {
    "functional_suitability": "Funcionalidad",
    "security": "Seguridad",
    "performance_efficiency": "Rendimiento",
    "usability": "Usabilidad",
    "reliability": "Confiabilidad",
    "compatibility": "Compatibilidad",
    "maintainability": "Mantenibilidad",
    "portability": "Portabilidad",
}
_TYPE_COLOR = {
    "positive": "#16a34a",
    "negative": "#dc2626",
    "boundary": "#d97706",
    "edge_case": "#7c3aed",
    "error_handling": "#0891b2",
}
_TYPE_LABEL = {
    "positive": "Positivo",
    "negative": "Negativo",
    "boundary": "Frontera",
    "edge_case": "Caso Borde",
    "error_handling": "Manejo Error",
}


def _render_reference_panel() -> None:
    """Panel de referencia: requerimiento + historias de usuario para consulta."""
    requirement: str = st.session_state.get("hitl_requirement", "")
    user_stories: list[dict] = st.session_state.get("hitl_user_stories", [])

    with st.expander("📋  Referencia — Requerimiento e Historias de Usuario", expanded=False):
        if requirement:
            st.markdown(
                '<div style="font-size:.92rem;text-transform:uppercase;letter-spacing:.06em;'
                'color:#475569;font-weight:700;margin-bottom:.35rem;">Requerimiento original</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="background:#0e1a2e;border:1px solid #0e4f6b;border-radius:8px;'
                f'padding:.8rem 1rem;font-size:1rem;color:#93c5fd;white-space:pre-wrap;'
                f'line-height:1.6;margin-bottom:1rem;">{requirement}</div>',
                unsafe_allow_html=True,
            )

        if user_stories:
            st.markdown(
                f'<div style="font-size:.92rem;text-transform:uppercase;letter-spacing:.06em;'
                f'color:#475569;font-weight:700;margin-bottom:.5rem;">'
                f'{len(user_stories)} Historias de Usuario generadas</div>',
                unsafe_allow_html=True,
            )
            _PRIO_COLOR = {
                "critical": "#dc2626", "high": "#d97706",
                "medium": "#2563eb",   "low": "#6b7280",
            }
            _PRIO_ES = {
                "critical": "CRÍTICA", "high": "ALTA",
                "medium": "MEDIA",     "low": "BAJA",
            }
            for story in user_stories:
                prio = story.get("priority", "medium")
                p_color = _PRIO_COLOR.get(prio, "#6b7280")
                p_label = _PRIO_ES.get(prio, prio.upper())
                n_ac = len(story.get("acceptance_criteria", []))
                with st.expander(
                    f"{story['id']} · {story['title']}",
                    expanded=False,
                ):
                    st.markdown(
                        f'<div style="display:flex;gap:.4rem;margin-bottom:.6rem;">'
                        f'<span style="background:#1e2d3d;color:{p_color};border:1px solid {p_color};'
                        f'border-radius:20px;padding:.1rem .55rem;font-size:.92rem;font-weight:700;">'
                        f'{p_label}</span>'
                        f'<span style="background:#1e2d3d;color:#475569;border-radius:20px;'
                        f'padding:.1rem .55rem;font-size:.92rem;">{n_ac} criterios AC</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div style="background:#0e1a2e;border:1px solid #0e4f6b;border-radius:6px;'
                        f'padding:.7rem .9rem;font-size:1rem;color:#93c5fd;line-height:1.65;'
                        f'margin-bottom:.6rem;">'
                        f'<b>Como</b> {story.get("as_a","")}, '
                        f'<b>quiero</b> {story.get("i_want","")}, '
                        f'<b>para que</b> {story.get("so_that","")}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    for ac in story.get("acceptance_criteria", []):
                        neg = (
                            '<span style="background:#fee2e2;color:#dc2626;border-radius:3px;'
                            'padding:.05rem .35rem;font-size:.9rem;margin-left:.3rem;">neg</span>'
                            if ac.get("is_negative_case") else ""
                        )
                        st.markdown(
                            f'<div style="border-left:2px solid #0e4f6b;padding:.3rem 0 .3rem .6rem;'
                            f'margin-bottom:.3rem;font-size:1rem;">'
                            f'<span style="color:#00bcd4;font-weight:700;">{ac.get("id","")}</span>'
                            f'{neg}'
                            f'<span style="color:#8b949e;"> — {ac.get("description","")}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )


def render_test_review(on_submit) -> None:
    """Renderiza el panel de revisión de test cases.

    on_submit(reviewer_name, global_decision, feedback) se llama al finalizar.
    """
    features: list[dict] = st.session_state.hitl_features
    total = st.session_state.hitl_total_scenarios
    decisions: dict = st.session_state.hitl_scenario_decisions

    st.markdown(
        '<h3 style="color:#e2e8f0;margin-bottom:0.25rem;">🧪 Revisión de Test Cases</h3>',
        unsafe_allow_html=True,
    )
    reviewed = sum(1 for d in decisions.values() if d.get("action") != "skipped")
    st.markdown(
        f'<div style="color:#64748b;font-size:1rem;margin-bottom:1rem;">'
        f'{total} escenarios generados · {reviewed} revisados</div>',
        unsafe_allow_html=True,
    )

    _render_reference_panel()

    # ── Escenarios por feature ────────────────────────────────────────────────
    for feature in features:
        fid = feature["user_story_id"]
        with st.expander(f"📋 {fid} — {feature['name']}  ({len(feature['scenarios'])} escenarios)", expanded=True):
            st.markdown(
                f'<div style="font-size:1rem;color:#64748b;font-style:italic;margin-bottom:.75rem;">'
                f'{feature["description"]}</div>',
                unsafe_allow_html=True,
            )
            for idx, sc in enumerate(feature["scenarios"]):
                _render_scenario(fid, sc, decisions, idx)

    st.divider()

    # ── Panel global de decisión ──────────────────────────────────────────────
    st.markdown("### Decisión global de la suite de tests")

    col_rev, col_dec = st.columns(2)
    with col_rev:
        reviewer_name = st.text_input(
            "Revisor / Aprobador",
            placeholder="Ej: ana.garcia",
            key="hitl_reviewer_name",
        )
    with col_dec:
        global_decision = st.selectbox(
            "Decisión",
            options=["approved", "needs_changes", "rejected"],
            format_func=lambda x: {
                "approved": "✅ Aprobar suite",
                "needs_changes": "⚠️ Aprobar con observaciones",
                "rejected": "❌ Rechazar — requiere regeneración",
            }[x],
            key="hitl_global_decision",
        )

    feedback = st.text_area(
        "Feedback general (opcional)",
        placeholder="Observaciones generales sobre la suite de tests…",
        key="hitl_feedback",
        height=80,
    )

    st.markdown("<div style='height:.5rem'></div>", unsafe_allow_html=True)

    if st.button(
        "Generar Reporte Final →",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get("is_running", False),
    ):
        on_submit(reviewer_name, global_decision, feedback)


def _render_scenario(feature_id: str, sc: dict, decisions: dict, idx: int) -> None:
    key = f"{feature_id}|{sc['name']}"
    wkey = f"{feature_id}|{idx}|{sc['acceptance_criterion_id']}"
    type_color = _TYPE_COLOR.get(sc["scenario_type"], "#6b7280")
    type_label = _TYPE_LABEL.get(sc["scenario_type"], sc["scenario_type"])
    iso_label = _ISO_LABELS.get(sc["quality_characteristic"], sc["quality_characteristic"])

    with st.container(border=True):
        col_name, col_iso = st.columns([4, 1])
        with col_name:
            st.markdown(
                f'<span style="background:{type_color};color:#fff;border-radius:4px;'
                f'padding:.15rem .5rem;font-size:.92rem;font-weight:700;margin-right:.5rem;">'
                f'{type_label}</span>'
                f'<span style="font-size:1.1rem;font-weight:600;color:#e2e8f0;">{sc["name"]}</span>',
                unsafe_allow_html=True,
            )
        with col_iso:
            st.markdown(
                f'<div style="text-align:right;font-size:.92rem;color:#94a3b8;">{iso_label}</div>',
                unsafe_allow_html=True,
            )

        # Tags
        if sc.get("tags"):
            tags_html = " ".join(
                f'<span style="background:#1e293b;color:#94a3b8;border-radius:4px;'
                f'padding:.1em .4em;font-size:.92rem;">@{t}</span>'
                for t in sc["tags"]
            )
            st.markdown(tags_html, unsafe_allow_html=True)

        # Pasos (primeros 5)
        steps_html = "".join(
            f'<div style="font-size:1rem;"><span style="color:#7c3aed;font-weight:700;'
            f'min-width:52px;display:inline-block;">{s["keyword"]}</span>{s["text"]}</div>'
            for s in sc["steps"][:5]
        )
        if len(sc["steps"]) > 5:
            steps_html += f'<div style="font-size:.95rem;color:#64748b;">… {len(sc["steps"]) - 5} pasos más</div>'
        st.markdown(
            f'<div style="background:#0f172a;border-radius:6px;padding:.6rem .8rem;'
            f'margin:.4rem 0;">{steps_html}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div style="font-size:.92rem;color:#64748b;">AC: {sc["acceptance_criterion_id"]}</div>',
            unsafe_allow_html=True,
        )

        # ── Controles de revisión ─────────────────────────────────────────────
        col_act, col_iso_new = st.columns([2, 2])
        with col_act:
            current_action = decisions.get(key, {}).get("action", "accepted")
            action = st.selectbox(
                "Acción",
                options=["accepted", "reclassified", "commented", "skipped"],
                format_func=lambda x: {
                    "accepted": "✓ Aceptar",
                    "reclassified": "↺ Reclasificar ISO",
                    "commented": "💬 Comentar",
                    "skipped": "→ Saltar",
                }[x],
                index=["accepted", "reclassified", "commented", "skipped"].index(current_action),
                key=f"action_{wkey}",
                label_visibility="collapsed",
            )

        with col_iso_new:
            if action == "reclassified":
                current_iso = decisions.get(key, {}).get("new_iso", sc["quality_characteristic"])
                new_iso = st.selectbox(
                    "Nueva ISO",
                    options=_ISO_OPTIONS,
                    format_func=lambda x: _ISO_LABELS.get(x, x),
                    index=_ISO_OPTIONS.index(current_iso) if current_iso in _ISO_OPTIONS else 0,
                    key=f"iso_{wkey}",
                    label_visibility="collapsed",
                )
            else:
                new_iso = None

        notes = ""
        if action in ("commented", "reclassified"):
            notes = st.text_input(
                "Nota / justificación",
                value=decisions.get(key, {}).get("notes", ""),
                placeholder="Agrega un comentario o justificación…",
                key=f"notes_{wkey}",
                label_visibility="collapsed",
            )

        # Persistir decisión en session_state
        decisions[key] = {
            "action": action,
            "notes": notes,
            "new_iso": new_iso if action == "reclassified" else None,
        }
        st.session_state.hitl_scenario_decisions = decisions
