"""Reporte ejecutivo nativo — diseño profesional, datos completos."""

import base64
from datetime import datetime

import streamlit as st

# ── Paleta dark (coherente con el tema oscuro de la app) ──────────────────────
_C_CARD      = "#1a1f2e"
_C_CARD_BDR  = "#21262d"
_C_NAVY      = "#00bcd4"
_C_BLUE      = "#3b82f6"
_C_TEXT      = "#e2e8f0"
_C_MUTED     = "#94a3b8"
_C_LIGHT     = "#0f172a"

_PRIORITY_META = {
    "critical": ("CRÍTICA",  "#dc2626"),
    "high":     ("ALTA",     "#d97706"),
    "medium":   ("MEDIA",    "#2563eb"),
    "low":      ("BAJA",     "#6b7280"),
}
_TYPE_META = {
    "positive":       ("Positivo",     "#16a34a"),
    "negative":       ("Negativo",     "#dc2626"),
    "boundary":       ("Frontera",     "#d97706"),
    "edge_case":      ("Caso Borde",   "#7c3aed"),
    "error_handling": ("Manejo Error", "#0891b2"),
}
_ISO_LABELS = {
    "functional_suitability": "Funcionalidad",
    "security":               "Seguridad",
    "performance_efficiency": "Rendimiento",
    "usability":              "Usabilidad",
    "reliability":            "Confiabilidad",
    "compatibility":          "Compatibilidad",
    "maintainability":        "Mantenibilidad",
    "portability":            "Portabilidad",
}
_ISO_COLORS = {
    "functional_suitability": "#2563eb",
    "security":               "#dc2626",
    "performance_efficiency": "#d97706",
    "usability":              "#7c3aed",
    "reliability":            "#0891b2",
    "compatibility":          "#059669",
    "maintainability":        "#6b7280",
    "portability":            "#92400e",
}
_RISK_META = {
    "security":               ("CRÍTICO", "#f87171", "#450a0a", "OWASP ZAP, Burp Suite, Nessus"),
    "performance_efficiency": ("ALTO",    "#fbbf24", "#451a03", "JMeter, k6, Locust"),
    "reliability":            ("ALTO",    "#fbbf24", "#451a03", "Chaos Engineering, Toxiproxy"),
    "compatibility":          ("MEDIO",   "#60a5fa", "#172554", "BrowserStack, Sauce Labs"),
    "usability":              ("MEDIO",   "#60a5fa", "#172554", "Axe, Lighthouse, SUS survey"),
    "maintainability":        ("BAJO",    "#94a3b8", "#1e293b", "SonarQube, CodeClimate"),
    "portability":            ("BAJO",    "#94a3b8", "#1e293b", "Docker, CI multi-OS"),
}
_STATUS_META = {
    "approved":       ("Aprobada",              "#4ade80", "#052e16"),
    "rejected":       ("Rechazada",             "#f87171", "#450a0a"),
    "needs_changes":  ("Con observaciones",     "#fbbf24", "#451a03"),
    "pending_review": ("Pendiente de revisión", "#60a5fa", "#172554"),
}
_ACTION_META = {
    "accepted":     ("Aceptado",      "#4ade80", "#052e16"),
    "reclassified": ("Reclasificado", "#fbbf24", "#451a03"),
    "commented":    ("Comentado",     "#60a5fa", "#172554"),
}
_ALL_ISO = [
    "functional_suitability", "security", "performance_efficiency",
    "usability", "reliability", "compatibility", "maintainability", "portability",
]


def _card(content: str, border_left: str = "", extra: str = "") -> None:
    b = f"border-left:4px solid {border_left};" if border_left else ""
    st.markdown(
        f'<div style="background:{_C_CARD};border:1px solid {_C_CARD_BDR};border-radius:8px;'
        f'padding:1rem 1.25rem;margin-bottom:.6rem;{b}{extra}">{content}</div>',
        unsafe_allow_html=True,
    )


def _section_header(num: str, title: str, desc: str = "") -> None:
    desc_html = (
        f'<div style="font-size:1.05rem;color:{_C_MUTED};margin-top:.1rem;">{desc}</div>'
        if desc else ""
    )
    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:.5rem;'
        f'margin:1.75rem 0 .65rem;padding-bottom:.4rem;'
        f'border-bottom:2px solid {_C_NAVY};">'
        f'<span style="font-size:2.8rem;font-weight:900;color:{_C_TEXT};line-height:1;">{num}</span>'
        f'<div><div style="font-size:1.4rem;font-weight:700;color:{_C_NAVY};">{title}</div>'
        f'{desc_html}</div></div>',
        unsafe_allow_html=True,
    )


def render_report_native(report_data: dict, html_content: str | None = None,
                         pdf_base64: str = "") -> None:
    """Renders the executive report natively with a professional document style."""

    created = report_data.get("created_at", "")
    try:
        created_fmt = datetime.fromisoformat(created).strftime("%d/%m/%Y %H:%M")
    except Exception:
        created_fmt = created[:16]
    run_id = report_data.get("pipeline_run_id", "")
    run_id_short = run_id[:8]
    is_eco = report_data.get("eco_mode", False)

    eco_badge = (
        '<span style="background:#065f46;color:#6ee7b7;border:1px solid #34d399;'
        'border-radius:20px;padding:.15rem .7rem;font-size:.9rem;font-weight:700;'
        'margin-left:.6rem;vertical-align:middle;">⚡ ECO</span>'
        if is_eco else ""
    )

    # ── Encabezado del documento ──────────────────────────────────────────────
    st.markdown(
        f'<div style="background:linear-gradient(135deg,{_C_NAVY},#3730a3);'
        f'border-radius:10px;padding:1.25rem 1.5rem;margin-bottom:1rem;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
        f'flex-wrap:wrap;gap:.5rem;">'
        f'<div>'
        f'<div style="font-size:1rem;color:rgba(255,255,255,.65);text-transform:uppercase;'
        f'letter-spacing:.1em;margin-bottom:.25rem;">QualityAI · Módulo 3 · v{report_data.get("module_version","3.0.0")}</div>'
        f'<div style="font-size:2rem;font-weight:700;color:#fff;">'
        f'Reporte Ejecutivo de Calidad{eco_badge}</div>'
        f'<div style="font-size:1rem;color:rgba(255,255,255,.65);margin-top:.2rem;">'
        f'Generado el {created_fmt} · Run #{run_id_short} · '
        f'{report_data.get("llm_provider","").upper()} / {report_data.get("llm_model","")}'
        f'</div></div></div></div>',
        unsafe_allow_html=True,
    )

    # ── Botón descarga PDF ────────────────────────────────────────────────────
    if pdf_base64:
        try:
            pdf_bytes = base64.b64decode(pdf_base64)
            st.download_button(
                label="⬇  Descargar Reporte PDF",
                data=pdf_bytes,
                file_name=f"reporte_ejecutivo_{run_id_short}.pdf",
                mime="application/pdf",
                use_container_width=False,
            )
        except Exception:
            st.markdown(
                '<span style="color:#94a3b8;font-size:1rem;">⚠ PDF no disponible para este reporte.</span>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<span style="color:#94a3b8;font-size:1rem;">⚠ PDF no disponible para este reporte.</span>',
            unsafe_allow_html=True,
        )

    # ── KPI strip ─────────────────────────────────────────────────────────────
    kpis = [
        ("Historias de Usuario", report_data.get("total_stories", 0),         _C_NAVY),
        ("Criterios AC",         report_data.get("total_acceptance_criteria", 0), "#3730a3"),
        ("Tests generados",      report_data.get("total_scenarios", 0),        "#0891b2"),
        ("Cobertura",            f"{report_data.get('coverage_pct', 0)}%",    "#059669"),
        ("Ambigüedades",         report_data.get("total_ambiguities", 0),      "#d97706"),
    ]
    kpi_cols = st.columns(len(kpis))
    for col, (label, value, color) in zip(kpi_cols, kpis):
        with col:
            st.markdown(
                f'<div style="background:{_C_CARD};border:1px solid {_C_CARD_BDR};'
                f'border-top:3px solid {color};border-radius:8px;padding:.85rem;text-align:center;">'
                f'<div style="font-size:2.6rem;font-weight:700;color:{color};">{value}</div>'
                f'<div style="font-size:1rem;color:{_C_MUTED};text-transform:uppercase;'
                f'letter-spacing:.05em;margin-top:.15rem;">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:.25rem'></div>", unsafe_allow_html=True)

    # ── 01: Requerimiento ─────────────────────────────────────────────────────
    _section_header("01", "Requerimiento Original",
                    "Texto ingresado sin modificaciones.")
    raw = report_data.get("original_requirement", "")
    _card(
        f'<div style="font-size:1.25rem;color:{_C_TEXT};white-space:pre-wrap;line-height:1.7;">'
        f'{raw}</div>'
    )
    ctx = report_data.get("project_context", "")
    if ctx:
        _card(
            f'<div style="font-size:1rem;color:{_C_MUTED};text-transform:uppercase;'
            f'letter-spacing:.06em;margin-bottom:.3rem;">Contexto inferido</div>'
            f'<div style="font-size:1.15rem;color:{_C_MUTED};">{ctx}</div>',
            border_left=_C_BLUE,
        )

    # ── 02: Ambigüedades ──────────────────────────────────────────────────────
    ambiguities = report_data.get("ambiguities", [])
    _section_header("02", "Ambigüedades Detectadas")
    if not ambiguities:
        _card(
            f'<span style="color:#16a34a;margin-right:.4rem;">✓</span>'
            f'<span style="color:{_C_MUTED};font-size:1.25rem;">No se detectaron ambigüedades.</span>',
            border_left="#16a34a",
        )
    else:
        assumed  = [a for a in ambiguities if a.get("assumption_made")]
        resolved = [a for a in ambiguities if not a.get("assumption_made")]
        total_found = report_data.get("total_ambiguities", len(ambiguities))
        st.markdown(
            f'<div style="font-size:1.15rem;color:{_C_MUTED};margin-bottom:.65rem;">'
            f'<strong style="color:{_C_TEXT};">{total_found}</strong> ambigüedades encontradas. '
            f'<span style="background:#052e16;color:#4ade80;border-radius:20px;'
            f'padding:.1rem .55rem;font-size:1rem;font-weight:600;">'
            f'{len(resolved)} validadas por el analista</span> '
            f'<span style="background:#451a03;color:#fbbf24;border-radius:20px;'
            f'padding:.1rem .55rem;font-size:1rem;font-weight:600;margin-left:.25rem;">'
            f'{len(assumed)} asumidas por el LLM</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if assumed:
            _card(
                f'<span style="color:#d97706;margin-right:.35rem;">⚠</span>'
                f'<strong style="color:#92400e;">{len(assumed)} supuesto(s) del LLM</strong>'
                f'<span style="color:{_C_MUTED};font-size:1.1rem;"> — validar con el cliente '
                f'antes de comenzar el desarrollo.</span>',
                border_left="#d97706",
            )
        for amb in ambiguities:
            is_assumed = amb.get("assumption_made", False)
            badge_style = (
                "background:#451a03;color:#fbbf24;" if is_assumed
                else "background:#052e16;color:#4ade80;"
            )
            badge_text = "⚠ Supuesto LLM" if is_assumed else "✓ Analista"
            conf = (
                f' <span style="font-size:1rem;color:{_C_MUTED};">'
                f'({int(amb.get("confidence_score", 1) * 100)}%)</span>'
                if is_assumed else ""
            )
            _card(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'margin-bottom:.5rem;flex-wrap:wrap;gap:.3rem;">'
                f'<span style="font-size:1.1rem;font-weight:600;color:{_C_NAVY};">'
                f'{amb.get("story_id","")} — {amb.get("story_title","")}</span>'
                f'<span style="border-radius:20px;padding:.1rem .55rem;font-size:1rem;'
                f'font-weight:600;{badge_style}">{badge_text}{conf}</span>'
                f'</div>'
                f'<div style="display:grid;grid-template-columns:1fr 22px 1fr;gap:.5rem;'
                f'align-items:start;">'
                f'<div>'
                f'<div style="font-size:1rem;color:{_C_MUTED};text-transform:uppercase;'
                f'letter-spacing:.05em;margin-bottom:.2rem;">Texto ambiguo</div>'
                f'<div style="font-style:italic;color:#dc2626;font-size:1.1rem;">'
                f'"{amb.get("original_text","")}"</div>'
                f'<div style="font-size:1rem;color:{_C_MUTED};text-transform:uppercase;'
                f'letter-spacing:.05em;margin:.4rem 0 .15rem;">Problema</div>'
                f'<div style="font-size:1.05rem;color:{_C_MUTED};">{amb.get("issue","")}</div>'
                f'</div>'
                f'<div style="text-align:center;color:{_C_MUTED};padding-top:1rem;">→</div>'
                f'<div>'
                f'<div style="font-size:1rem;color:{_C_MUTED};text-transform:uppercase;'
                f'letter-spacing:.05em;margin-bottom:.2rem;">Resolución</div>'
                f'<div style="font-size:1.1rem;color:#4ade80;font-weight:500;">'
                f'{amb.get("resolution","")}</div>'
                f'</div></div>',
                border_left="#d97706" if is_assumed else "#16a34a",
            )

    # ── 03: Historias de Usuario ───────────────────────────────────────────────
    user_stories = report_data.get("user_stories", [])
    _section_header("03", "Historias de Usuario",
                    "Expande cada historia para ver sus criterios de aceptación.")
    for story in user_stories:
        p_label, p_color = _PRIORITY_META.get(story.get("priority", ""), ("—", _C_MUTED))
        ac_count = len(story.get("acceptance_criteria", []))
        with st.expander(f"{story['id']} · {story['title']}", expanded=False):
            st.markdown(
                f'<div style="display:flex;gap:.4rem;margin-bottom:.65rem;flex-wrap:wrap;">'
                f'<span style="background:{p_color}20;color:{p_color};border:1px solid {p_color};'
                f'border-radius:20px;padding:.1rem .55rem;font-size:1rem;font-weight:700;">'
                f'{p_label}</span>'
                f'<span style="background:{_C_LIGHT};color:{_C_MUTED};border-radius:20px;'
                f'padding:.1rem .55rem;font-size:1rem;">{ac_count} criterios AC</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="background:{_C_LIGHT};border:1px solid {_C_CARD_BDR};border-radius:8px;'
                f'padding:.85rem 1rem;font-size:1.2rem;color:{_C_TEXT};margin-bottom:.75rem;'
                f'line-height:1.7;">'
                f'<strong style="color:{_C_NAVY};">Como</strong> {story.get("as_a","")}, '
                f'<strong style="color:{_C_NAVY};">quiero</strong> {story.get("i_want","")}, '
                f'<strong style="color:{_C_NAVY};">para que</strong> {story.get("so_that","")}'
                f'</div>',
                unsafe_allow_html=True,
            )
            if story.get("business_rules"):
                st.markdown(
                    f'<div style="font-size:1rem;text-transform:uppercase;letter-spacing:.06em;'
                    f'color:{_C_MUTED};font-weight:700;margin-bottom:.3rem;">Reglas de negocio</div>',
                    unsafe_allow_html=True,
                )
                for rule in story["business_rules"]:
                    st.markdown(
                        f'<div style="font-size:1.1rem;color:{_C_MUTED};padding:.15rem 0 .15rem .6rem;'
                        f'border-left:2px solid {_C_BLUE};margin-bottom:.2rem;">▸ {rule}</div>',
                        unsafe_allow_html=True,
                    )
            st.markdown(
                f'<div style="font-size:1rem;text-transform:uppercase;letter-spacing:.06em;'
                f'color:{_C_MUTED};font-weight:700;margin:.6rem 0 .35rem;">'
                f'Criterios de Aceptación</div>',
                unsafe_allow_html=True,
            )
            for ac in story.get("acceptance_criteria", []):
                neg_badge = (
                    f'<span style="background:#450a0a;color:#f87171;border-radius:4px;'
                    f'padding:.05em .35em;font-size:1rem;margin-left:.3rem;">negativo</span>'
                    if ac.get("is_negative_case") else ""
                )
                bv_html = ""
                if ac.get("boundary_values"):
                    bv_html = (
                        f'<div style="margin-top:.35rem;font-size:1rem;color:{_C_MUTED};">'
                        f'Valores frontera: {", ".join(ac["boundary_values"])}</div>'
                    )
                _card(
                    f'<div style="font-size:1rem;font-weight:700;color:{_C_MUTED};'
                    f'margin-bottom:.2rem;">{ac.get("id","")}{neg_badge}</div>'
                    f'<div style="font-size:1.1rem;color:{_C_TEXT};margin-bottom:.45rem;">'
                    f'{ac.get("description","")}</div>'
                    f'<div style="font-size:1.05rem;color:{_C_TEXT};">'
                    f'<span style="color:#7c3aed;font-weight:700;display:inline-block;'
                    f'min-width:70px;">Dado que</span>{ac.get("given","")}</div>'
                    f'<div style="font-size:1.05rem;color:{_C_TEXT};">'
                    f'<span style="color:#7c3aed;font-weight:700;display:inline-block;'
                    f'min-width:70px;">Cuando</span>{ac.get("when","")}</div>'
                    f'<div style="font-size:1.05rem;color:{_C_TEXT};">'
                    f'<span style="color:#7c3aed;font-weight:700;display:inline-block;'
                    f'min-width:70px;">Entonces</span>{ac.get("then","")}</div>'
                    f'{bv_html}',
                )

    # ── 04: Casos de prueba ────────────────────────────────────────────────────
    features = report_data.get("features", [])
    story_map = {s["id"]: s["title"] for s in user_stories}
    _section_header("04", "Casos de Prueba",
                    "Escenarios Gherkin generados, listos para Cucumber / Behave.")
    for feature in features:
        n_sc = len(feature.get("scenarios", []))
        with st.expander(
            f"{feature.get('user_story_id','')} · {feature.get('name','')}  [{n_sc} escenarios]",
            expanded=False,
        ):
            if feature.get("description"):
                st.markdown(
                    f'<div style="font-size:1.1rem;color:{_C_MUTED};font-style:italic;'
                    f'margin-bottom:.65rem;">{feature["description"]}</div>',
                    unsafe_allow_html=True,
                )
            for sc in feature.get("scenarios", []):
                t_label, t_color = _TYPE_META.get(
                    sc.get("scenario_type", ""), (sc.get("scenario_type", ""), _C_MUTED)
                )
                iso_key   = sc.get("quality_characteristic", "")
                iso_label = _ISO_LABELS.get(iso_key, iso_key)
                iso_color = _ISO_COLORS.get(iso_key, _C_MUTED)
                tags_html = "".join(
                    f'<span style="background:{_C_LIGHT};color:{_C_MUTED};padding:.1em .4em;'
                    f'border-radius:4px;font-size:1rem;margin-right:.25rem;'
                    f'border:1px solid {_C_CARD_BDR};">@{t}</span>'
                    for t in sc.get("tags", [])
                )
                steps_html = "".join(
                    f'<div style="font-size:1.05rem;color:{_C_TEXT};margin-bottom:.15rem;">'
                    f'<span style="color:#7c3aed;font-weight:700;display:inline-block;'
                    f'min-width:56px;">{s["keyword"]}</span>{s["text"]}</div>'
                    for s in sc.get("steps", [])
                )
                _card(
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
                    f'margin-bottom:.35rem;gap:.4rem;flex-wrap:wrap;">'
                    f'<div><span style="background:{t_color};color:#fff;font-size:1rem;'
                    f'font-weight:700;padding:.1rem .4rem;border-radius:4px;margin-right:.3rem;">'
                    f'{t_label}</span>'
                    f'<span style="font-size:1.15rem;font-weight:600;color:{_C_TEXT};">'
                    f'{sc.get("name","")}</span></div>'
                    f'<span style="background:{iso_color}18;color:{iso_color};font-size:1rem;'
                    f'padding:.1rem .45rem;border-radius:20px;white-space:nowrap;'
                    f'border:1px solid {iso_color};">{iso_label}</span>'
                    f'</div>'
                    f'<div style="margin-bottom:.4rem;">{tags_html}</div>'
                    f'<div style="background:{_C_LIGHT};border-radius:6px;padding:.55rem .75rem;'
                    f'margin-bottom:.35rem;">{steps_html}</div>'
                    f'<div style="font-size:1rem;color:{_C_MUTED};">'
                    f'AC: {sc.get("acceptance_criterion_id","")} · '
                    f'Técnica: {sc.get("heuristic_applied","").upper()}</div>',
                    border_left=t_color,
                )

    # ── 05: Revisión HITL ─────────────────────────────────────────────────────
    hitl = report_data.get("hitl", {})
    _section_header("05", "Revisión HITL",
                    "Decisiones del analista durante la revisión humana.")
    status_key = hitl.get("review_status", "pending_review")
    s_label, s_color, s_bg = _STATUS_META.get(status_key, ("—", _C_MUTED, _C_LIGHT))
    reviewed_at_raw = hitl.get("reviewed_at", "")
    try:
        reviewed_at_fmt = (
            datetime.fromisoformat(reviewed_at_raw).strftime("%d/%m/%Y %H:%M")
            if reviewed_at_raw else "—"
        )
    except Exception:
        reviewed_at_fmt = reviewed_at_raw[:16] if reviewed_at_raw else "—"

    hitl_kpis = [
        ("Revisor",        hitl.get("reviewer", "") or "—"),
        ("Decisión final", f'<span style="color:{s_color};font-weight:700;">{s_label}</span>'),
        ("Revisado el",    reviewed_at_fmt),
        ("Escenarios",     str(hitl.get("changes_count", 0))),
        ("Proveedor LLM",  report_data.get("llm_provider", "—").upper()),
    ]
    h_cols = st.columns(len(hitl_kpis))
    for col, (label, value) in zip(h_cols, hitl_kpis):
        with col:
            _card(
                f'<div style="font-size:1rem;text-transform:uppercase;letter-spacing:.06em;'
                f'color:{_C_MUTED};margin-bottom:.25rem;">{label}</div>'
                f'<div style="font-size:1.15rem;font-weight:600;color:{_C_TEXT};">{value}</div>'
            )

    if hitl.get("analyst_feedback"):
        _card(
            f'<span style="color:{_C_BLUE};margin-right:.35rem;">💬</span>'
            f'<strong style="color:{_C_NAVY};">Feedback del revisor:</strong> '
            f'<span style="color:{_C_MUTED};font-size:1.15rem;">{hitl["analyst_feedback"]}</span>',
            border_left=_C_BLUE,
        )

    ab = hitl.get("actions_breakdown", {})
    if ab:
        pills = "".join(
            f'<span style="border-radius:20px;padding:.12rem .6rem;font-size:1rem;'
            f'font-weight:600;background:{_ACTION_META.get(k,("",None,"#f1f5f9"))[2]};'
            f'color:{_ACTION_META.get(k,("",_C_MUTED,""))[1]};margin-right:.3rem;">'
            f'{_ACTION_META.get(k,(k,None,None))[0]}: {v}</span>'
            for k, v in ab.items()
        )
        st.markdown(f'<div style="margin-bottom:.6rem;">{pills}</div>', unsafe_allow_html=True)

    amb_resolved = hitl.get("ambiguities_resolved", [])
    if amb_resolved:
        _llm_badge = (
            '<span style="background:#451a03;color:#fbbf24;border-radius:20px;'
            'padding:.08rem .45rem;font-size:1rem;font-weight:600;">⚠ LLM</span>'
        )
        _ana_badge = (
            '<span style="background:#052e16;color:#4ade80;border-radius:20px;'
            'padding:.08rem .45rem;font-size:1rem;font-weight:600;">✓ Analista</span>'
        )
        rows_parts = []
        for r in amb_resolved:
            badge = _llm_badge if r.get("assumption_made") else _ana_badge
            rows_parts.append(
                f'<tr style="border-bottom:1px solid {_C_CARD_BDR};">'
                f'<td style="padding:.45rem .7rem;color:{_C_BLUE};font-size:1.05rem;font-weight:600;">'
                f'{r.get("story_id","")}</td>'
                f'<td style="padding:.45rem .7rem;color:#dc2626;font-style:italic;font-size:1.05rem;">'
                f'"{r.get("original_text","")}"</td>'
                f'<td style="padding:.45rem .7rem;color:#4ade80;font-size:1.05rem;">'
                f'{r.get("resolution","")}</td>'
                f'<td style="padding:.45rem .7rem;">{badge}</td></tr>'
            )
        rows_html = "".join(rows_parts)
        st.markdown(
            f'<div style="font-size:1.1rem;font-weight:600;color:{_C_TEXT};margin-bottom:.3rem;">'
            f'Resolución de ambigüedades</div>',
            unsafe_allow_html=True,
        )
        _card(
            f'<div style="overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="border-bottom:2px solid {_C_CARD_BDR};background:{_C_LIGHT};">'
            f'<th style="padding:.4rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Historia</th>'
            f'<th style="padding:.4rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Texto ambiguo</th>'
            f'<th style="padding:.4rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Resolución</th>'
            f'<th style="padding:.4rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Origen</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table></div>'
        )

    # ── 06: ISO 25010 ─────────────────────────────────────────────────────────
    iso_coverage = report_data.get("iso_coverage", {})
    _section_header("06", "Cobertura ISO 25010")
    total_sc = sum(iso_coverage.values()) or 1
    covered_count = sum(1 for c in _ALL_ISO if iso_coverage.get(c, 0) > 0)
    st.markdown(
        f'<div style="font-size:1.15rem;color:{_C_MUTED};margin-bottom:.6rem;">'
        f'ISO 25010 define 8 características de calidad. Se cubren '
        f'<strong style="color:{_C_TEXT};">{covered_count} de 8</strong> '
        f'con escenarios de test.</div>',
        unsafe_allow_html=True,
    )
    gaps = [c for c in _ALL_ISO if iso_coverage.get(c, 0) == 0]
    if gaps:
        gap_names = ", ".join(_ISO_LABELS.get(g, g) for g in gaps)
        _card(
            f'<span style="color:#d97706;margin-right:.35rem;">⚠</span>'
            f'<strong style="color:#92400e;">Sin cobertura:</strong> '
            f'<span style="color:{_C_MUTED};font-size:1.1rem;">{gap_names}</span>',
            border_left="#d97706",
        )
    bars_html = ""
    for char in _ALL_ISO:
        count = iso_coverage.get(char, 0)
        pct   = count / total_sc * 100
        color = _ISO_COLORS.get(char, _C_MUTED)
        label = _ISO_LABELS.get(char, char)
        if count == 0:
            fill = (
                f'<div style="background:{_C_LIGHT};border-radius:4px;height:16px;'
                f'display:flex;align-items:center;padding:0 .5rem;">'
                f'<span style="font-size:1rem;color:{_C_MUTED};font-style:italic;">Sin cobertura</span></div>'
            )
            cnt_disp = f'<span style="color:{_C_MUTED};font-weight:700;">0</span>'
        else:
            fill = (
                f'<div style="background:{color};border-radius:4px;height:16px;'
                f'width:{max(pct, 2):.1f}%;"></div>'
            )
            cnt_disp = f'<span style="color:{color};font-weight:700;">{count}</span>'
        bars_html += (
            f'<div style="display:grid;grid-template-columns:130px 1fr 60px;'
            f'align-items:center;gap:.5rem;margin-bottom:.35rem;">'
            f'<div style="display:flex;align-items:center;gap:.4rem;">'
            f'<div style="width:8px;height:8px;border-radius:50%;background:{color};'
            f'flex-shrink:0;"></div>'
            f'<span style="font-size:1.05rem;color:{_C_TEXT};font-weight:500;">{label}</span></div>'
            f'<div style="background:{_C_LIGHT};border-radius:4px;height:16px;overflow:hidden;'
            f'border:1px solid {_C_CARD_BDR};">{fill}</div>'
            f'<div style="text-align:right;">{cnt_disp} '
            f'<span style="font-size:1rem;color:{_C_MUTED};">{pct:.0f}%</span></div></div>'
        )
    _card(bars_html)

    # ── 07: Riesgos ───────────────────────────────────────────────────────────
    quality_insights = report_data.get("quality_insights", [])
    _section_header("07", "Riesgos y Recomendaciones")
    risk_rows = "".join(
        f'<tr style="border-bottom:1px solid {_C_CARD_BDR};">'
        f'<td style="padding:.5rem .7rem;font-size:1.1rem;color:{_C_TEXT};font-weight:500;">'
        f'{_ISO_LABELS.get(char, char)}</td>'
        f'<td style="padding:.5rem .7rem;">'
        f'<span style="background:{r_bg};color:{r_color};border:1px solid {r_color};'
        f'border-radius:20px;padding:.1rem .5rem;font-size:1rem;font-weight:700;">'
        f'{r_level}</span></td>'
        f'<td style="padding:.5rem .7rem;text-align:center;font-weight:600;color:{_C_TEXT};">'
        f'{count}</td>'
        f'<td style="padding:.5rem .7rem;font-size:1rem;color:{_C_MUTED};">{r_tool}</td>'
        f'</tr>'
        for char, count in sorted(iso_coverage.items(), key=lambda x: -x[1])
        if char != "functional_suitability" and char in _RISK_META
        for r_level, r_color, r_bg, r_tool in [_RISK_META[char]]
    )
    if risk_rows:
        st.markdown(
            f'<div style="font-size:1.15rem;font-weight:600;color:{_C_TEXT};margin-bottom:.3rem;">'
            f'Matriz de riesgo por característica ISO 25010</div>',
            unsafe_allow_html=True,
        )
        _card(
            f'<div style="overflow-x:auto;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr style="border-bottom:2px solid {_C_CARD_BDR};background:{_C_LIGHT};">'
            f'<th style="padding:.45rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Característica</th>'
            f'<th style="padding:.45rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Nivel</th>'
            f'<th style="padding:.45rem .7rem;text-align:center;font-size:1rem;color:{_C_MUTED};">Tests</th>'
            f'<th style="padding:.45rem .7rem;text-align:left;font-size:1rem;color:{_C_MUTED};">Herramienta recomendada</th>'
            f'</tr></thead><tbody>{risk_rows}</tbody></table></div>'
        )

    uncovered = report_data.get("uncovered_criteria", [])
    if uncovered:
        items_html = " ".join(
            f'<code style="background:{_C_LIGHT};color:{_C_NAVY};padding:.1em .35em;'
            f'border-radius:3px;font-size:1.05rem;border:1px solid {_C_CARD_BDR};">{c}</code>'
            for c in uncovered
        )
        _card(
            f'<span style="color:#d97706;margin-right:.35rem;">⚠</span>'
            f'<strong style="color:#92400e;">Criterios sin cobertura de test:</strong> {items_html}',
            border_left="#d97706",
        )

    if quality_insights:
        st.markdown(
            f'<div style="font-size:1.15rem;font-weight:600;color:{_C_TEXT};margin:.6rem 0 .3rem;">'
            f'Alertas de calidad detectadas</div>',
            unsafe_allow_html=True,
        )
        for ins in quality_insights:
            if ins.get("severity") == "critical":
                icon, i_color, i_bg = "🔴", "#dc2626", "#2d0a0a"
            elif ins.get("severity") == "warning":
                icon, i_color, i_bg = "🟡", "#d97706", "#2d1a03"
            else:
                icon, i_color, i_bg = "🔵", "#3b82f6", "#0d1a2d"
            affected_html = ""
            if ins.get("affected_items"):
                items_h = " ".join(
                    f'<code style="background:{_C_LIGHT};color:{_C_MUTED};padding:.1em .3em;'
                    f'border-radius:3px;font-size:1.05rem;border:1px solid {_C_CARD_BDR};">{i}</code>'
                    for i in ins["affected_items"]
                )
                affected_html = (
                    f'<div style="margin-top:.4rem;font-size:1.05rem;color:{_C_MUTED};">'
                    f'Afecta: {items_h}</div>'
                )
            _card(
                f'<div style="font-weight:700;font-size:1.3rem;color:{_C_TEXT};margin-bottom:.3rem;">'
                f'{icon} {ins.get("title","")}</div>'
                f'<div style="font-size:1.1rem;color:{_C_MUTED};margin-bottom:.35rem;">'
                f'{ins.get("description","")}</div>'
                f'<div style="font-size:1.1rem;">'
                f'<strong style="color:{_C_BLUE};">💡 Recomendación:</strong> '
                f'<span style="color:{_C_TEXT};">{ins.get("recommendation","")}</span></div>'
                f'{affected_html}',
                border_left=i_color,
                extra=f"background:{i_bg};",
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    duration = report_data.get("total_duration_seconds") or 0
    version  = report_data.get("module_version", "3.0.0")
    st.markdown(
        f'<div style="text-align:center;color:{_C_MUTED};font-size:1rem;'
        f'padding:1.25rem .5rem;border-top:1px solid {_C_CARD_BDR};margin-top:1rem;">'
        f'QualityAI Módulo 3 · v{version} · Pipeline completado en {duration:.1f}s · '
        f'Run ID: {run_id}'
        f'</div>',
        unsafe_allow_html=True,
    )
