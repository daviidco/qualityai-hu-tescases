"""HtmlReporter — Reporte ejecutivo orientado al usuario final.

Estructura narrativa:
  1. Requerimiento original
  2. Ambigüedades detectadas y resueltas
  3. Historias de usuario con criterios de aceptación
  4. Casos de prueba (Gherkin por historia)
  5. Riesgos y recomendaciones
"""
from __future__ import annotations

import webbrowser
from pathlib import Path

from .interfaces import IReportGenerator
from ..contracts.contract_a import RefinedRequirements, UserStory
from ..contracts.contract_b import GherkinTestSuite, GherkinFeature
from ..contracts.contract_c import ExecutiveReport

_PRIORITY_META = {
    "critical": ("CRÍTICA",  "#dc2626", "#fee2e2"),
    "high":     ("ALTA",     "#d97706", "#fef3c7"),
    "medium":   ("MEDIA",    "#2563eb", "#dbeafe"),
    "low":      ("BAJA",     "#6b7280", "#f1f5f9"),
}
_TYPE_META = {
    "positive":       ("Positivo",       "#16a34a"),
    "negative":       ("Negativo",       "#dc2626"),
    "boundary":       ("Frontera",       "#d97706"),
    "edge_case":      ("Caso Borde",     "#7c3aed"),
    "error_handling": ("Manejo Error",   "#0891b2"),
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
_ISO_DESC = {
    "functional_suitability": "El sistema hace lo que el usuario necesita: completitud, corrección y pertinencia funcional.",
    "security":               "Protección de datos e información: confidencialidad, integridad, autenticación y no repudio.",
    "performance_efficiency": "Rendimiento en relación a los recursos: tiempo de respuesta, uso de CPU/memoria y capacidad.",
    "usability":              "Facilidad de uso: aprendizaje, operabilidad, protección contra errores y estética.",
    "reliability":            "El sistema funciona correctamente bajo condiciones definidas: disponibilidad, tolerancia a fallos y recuperabilidad.",
    "compatibility":          "Coexistencia e interoperabilidad con otros sistemas, navegadores o plataformas.",
    "maintainability":        "Facilidad de modificación: modularidad, reusabilidad, analizabilidad y capacidad de prueba.",
    "portability":            "Capacidad de trasladar el sistema a otros entornos: adaptabilidad, instalabilidad y reemplazabilidad.",
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
    "security":               ("CRÍTICO", "#dc2626", "#fee2e2", "OWASP ZAP, Burp Suite, Nessus"),
    "performance_efficiency": ("ALTO",    "#d97706", "#fef3c7", "JMeter, k6, Locust"),
    "reliability":            ("ALTO",    "#d97706", "#fef3c7", "Chaos Engineering, Toxiproxy"),
    "compatibility":          ("MEDIO",   "#2563eb", "#dbeafe", "BrowserStack, Sauce Labs"),
    "usability":              ("MEDIO",   "#2563eb", "#dbeafe", "Axe, Lighthouse, SUS survey"),
    "maintainability":        ("BAJO",    "#6b7280", "#f1f5f9", "SonarQube, CodeClimate"),
    "portability":            ("BAJO",    "#6b7280", "#f1f5f9", "Docker, CI multi-OS"),
}


class HtmlReporter(IReportGenerator):

    def generate(
        self,
        contract_a: RefinedRequirements,
        contract_b: GherkinTestSuite,
        contract_c: ExecutiveReport,
        output_path: Path,
    ) -> Path:
        html = self._assemble(contract_a, contract_b, contract_c)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        print(f"\n📄 Reporte generado: {output_path}")
        webbrowser.open(str(output_path))
        return output_path

    def _assemble(self, a: RefinedRequirements, b: GherkinTestSuite, c: ExecutiveReport) -> str:
        total_acs = sum(len(s.acceptance_criteria) for s in a.user_stories)
        all_ambiguities = [
            (story.id, story.title, res)
            for story in a.user_stories
            for res in story.ambiguities_resolved
        ]
        features_by_story = {f.user_story_id: f for f in b.features}

        sections = "\n".join([
            self._sec_header(a, b, c, total_acs),
            self._sec_nav(),
            self._sec_requirement(a),
            self._sec_ambiguities(all_ambiguities, a.total_ambiguities_found),
            self._sec_user_stories(a.user_stories),
            self._sec_test_cases(a.user_stories, features_by_story),
            self._sec_hitl_review(a, b, c),
            self._sec_iso_coverage(b),
            self._sec_risks(b, c),
            self._sec_footer(c),
        ])

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reporte de Calidad — {c.created_at.strftime("%Y-%m-%d")}</title>
  {self._css()}
</head>
<body>
{sections}
{self._js()}
</body>
</html>"""

    # ──────────────────────────────────────────────────────────────────────────
    # Secciones
    # ──────────────────────────────────────────────────────────────────────────

    def _sec_header(self, a, b, c, total_acs: int) -> str:
        created = c.created_at.strftime("%d/%m/%Y %H:%M")
        coverage_pct = int(c.requirements_to_test_coverage_ratio * 100)
        return f"""<header class="hero">
  <div class="hero-inner">
    <div class="hero-title">
      <span class="hero-badge">QualityAI · Módulo 3</span>
      <h1>Reporte de Calidad</h1>
      <p class="hero-sub">Generado el {created} · Pipeline #{c.pipeline_run_id[:8]}</p>
    </div>
    <div class="kpi-strip">
      <div class="kpi"><span class="kn">{len(a.user_stories)}</span><span class="kl">Historias</span></div>
      <div class="kpi"><span class="kn">{total_acs}</span><span class="kl">Criterios</span></div>
      <div class="kpi"><span class="kn">{b.total_scenarios}</span><span class="kl">Tests</span></div>
      <div class="kpi"><span class="kn">{coverage_pct}%</span><span class="kl">Cobertura</span></div>
      <div class="kpi"><span class="kn">{a.total_ambiguities_found}</span><span class="kl">Ambigüedades</span></div>
    </div>
  </div>
</header>"""

    def _sec_nav(self) -> str:
        return """<nav class="sidenav" id="sidenav">
  <a href="#req">📄 Requerimiento</a>
  <a href="#ambig">🔍 Ambigüedades</a>
  <a href="#stories">📝 Historias</a>
  <a href="#tests">🧪 Test Cases</a>
  <a href="#hitl">👤 Revisión HITL</a>
  <a href="#iso">🎯 ISO 25010</a>
  <a href="#risks">⚠️ Riesgos</a>
</nav>
<div class="main-wrap">"""

    def _sec_requirement(self, a: RefinedRequirements) -> str:
        raw = a.original_requirements_text.replace("\n", "<br>")
        context = a.project_context.replace("\n", "<br>") if a.project_context else ""
        context_block = f"""<div class="callout callout-info">
  <strong>Contexto inferido:</strong><br>{context}
</div>""" if context else ""
        return f"""<section id="req" class="section">
  <div class="section-label">01</div>
  <h2>Requerimiento Original</h2>
  <p class="section-desc">El texto ingresado tal como fue recibido, sin modificaciones.</p>
  <div class="raw-box">{raw}</div>
  {context_block}
</section>"""

    def _sec_ambiguities(self, all_ambiguities: list, total_found: int) -> str:
        if not all_ambiguities:
            return f"""<section id="ambig" class="section">
  <div class="section-label">02</div>
  <h2>Ambigüedades Detectadas</h2>
  <div class="callout callout-ok">✅ No se detectaron ambigüedades en el requerimiento.</div>
</section>"""

        assumed = [(sid, stitle, r) for sid, stitle, r in all_ambiguities if r.assumption_made]
        resolved = [(sid, stitle, r) for sid, stitle, r in all_ambiguities if not r.assumption_made]

        cards = []
        for sid, stitle, r in all_ambiguities:
            if r.assumption_made:
                badge = '<span class="abadge abadge-warn">⚠ Supuesto del LLM</span>'
                conf = f'<span class="conf">Confianza: {int(r.confidence_score * 100)}%</span>'
            else:
                badge = '<span class="abadge abadge-ok">✓ Validado por analista</span>'
                conf = ""
            cards.append(f"""<div class="ambig-card {'ambig-assumed' if r.assumption_made else ''}">
  <div class="ambig-header">
    <span class="ambig-story">{sid} — {stitle}</span>
    {badge}{conf}
  </div>
  <div class="ambig-row">
    <div class="ambig-col">
      <div class="ambig-field-label">Texto ambiguo encontrado</div>
      <div class="ambig-text">"{r.original_text}"</div>
      <div class="ambig-field-label" style="margin-top:.5rem">Problema detectado</div>
      <div class="ambig-issue">{r.issue}</div>
    </div>
    <div class="ambig-arrow">→</div>
    <div class="ambig-col">
      <div class="ambig-field-label">Resolución aplicada</div>
      <div class="ambig-resolution">{r.resolution}</div>
    </div>
  </div>
</div>""")

        summary = ""
        if assumed:
            summary = f"""<div class="callout callout-warn">
  ⚠️ <strong>{len(assumed)} supuesto(s) realizados por el LLM</strong> sin confirmación del analista.
  Revisarlos antes de comenzar el desarrollo — pueden no reflejar el comportamiento real esperado.
</div>"""

        return f"""<section id="ambig" class="section">
  <div class="section-label">02</div>
  <h2>Ambigüedades Detectadas</h2>
  <p class="section-desc">
    Se encontraron <strong>{total_found}</strong> ambigüedades en el requerimiento.
    <span class="pill pill-ok">{len(resolved)} validadas por el analista</span>
    <span class="pill pill-warn">{len(assumed)} asumidas por el LLM</span>
  </p>
  {summary}
  <div class="ambig-list">{"".join(cards)}</div>
</section>"""

    def _sec_user_stories(self, stories: list[UserStory]) -> str:
        cards = []
        for story in stories:
            p_label, p_color, p_bg = _PRIORITY_META.get(story.priority.value, ("—", "#6b7280", "#f1f5f9"))
            ac_rows = []
            for ac in story.acceptance_criteria:
                neg_badge = '<span class="neg-badge">Caso negativo</span>' if ac.is_negative_case else ""
                bv = ""
                if ac.boundary_values:
                    bv = f'<div class="bv">Valores frontera: {", ".join(ac.boundary_values)}</div>'
                ac_rows.append(f"""<div class="ac-card">
  <div class="ac-id">{ac.id} {neg_badge}</div>
  <div class="ac-desc">{ac.description}</div>
  <div class="gwt">
    <div class="gwt-row"><span class="gwt-kw">Dado que</span>{ac.given}</div>
    <div class="gwt-row"><span class="gwt-kw">Cuando</span>{ac.when}</div>
    <div class="gwt-row"><span class="gwt-kw">Entonces</span>{ac.then}</div>
  </div>
  {bv}
</div>""")

            rules_html = ""
            if story.business_rules:
                rules_items = "".join(f"<li>{r}</li>" for r in story.business_rules)
                rules_html = f'<div class="story-section-title">Reglas de negocio</div><ul class="rules-list">{rules_items}</ul>'

            cards.append(f"""<div class="story-card">
  <div class="story-header" onclick="toggle(this)">
    <div class="story-header-left">
      <span class="story-id">{story.id}</span>
      <span class="story-title">{story.title}</span>
    </div>
    <div class="story-header-right">
      <span class="priority-badge" style="background:{p_bg};color:{p_color};border:1px solid {p_color}">{p_label}</span>
      <span class="ac-count">{len(story.acceptance_criteria)} criterios</span>
      <span class="chevron">▼</span>
    </div>
  </div>
  <div class="story-body">
    <div class="story-narrative">
      <span class="narrative-kw">Como</span> {story.as_a},
      <span class="narrative-kw">quiero</span> {story.i_want},
      <span class="narrative-kw">para</span> {story.so_that}.
    </div>
    {rules_html}
    <div class="story-section-title">Criterios de Aceptación</div>
    {"".join(ac_rows)}
  </div>
</div>""")

        return f"""<section id="stories" class="section">
  <div class="section-label">03</div>
  <h2>Historias de Usuario</h2>
  <p class="section-desc">Haz clic en cada historia para ver sus criterios de aceptación detallados.</p>
  <div class="story-list">{"".join(cards)}</div>
</section>"""

    def _sec_test_cases(self, stories: list[UserStory], features_by_story: dict) -> str:
        blocks = []
        for story in stories:
            feature: GherkinFeature | None = features_by_story.get(story.id)
            if not feature:
                continue
            scenario_cards = []
            for sc in feature.scenarios:
                type_label, type_color = _TYPE_META.get(sc.scenario_type.value, (sc.scenario_type.value, "#6b7280"))
                iso_label = _ISO_LABELS.get(sc.quality_characteristic.value, sc.quality_characteristic.value)
                tags = " ".join(f"<span class='tag'>@{t}</span>" for t in sc.tags)
                steps = "".join(
                    f"<div class='step'><span class='step-kw'>{s.keyword}</span>{s.text}</div>"
                    for s in sc.steps
                )
                scenario_cards.append(f"""<div class="scenario-card" style="border-left:3px solid {type_color}">
  <div class="scenario-header">
    <div>
      <span class="scenario-type-badge" style="background:{type_color}">{type_label}</span>
      <span class="scenario-name">{sc.name}</span>
    </div>
    <span class="iso-chip">{iso_label}</span>
  </div>
  <div class="tags">{tags}</div>
  <div class="steps">{steps}</div>
  <div class="scenario-footer">AC: {sc.acceptance_criterion_id} · Técnica: {sc.heuristic_applied.upper()}</div>
</div>""")

            blocks.append(f"""<div class="feature-block">
  <div class="feature-title">
    <span class="feature-id">{story.id}</span>
    <span>{feature.name}</span>
    <span class="feature-count">{len(feature.scenarios)} escenarios</span>
  </div>
  <div class="feature-desc">{feature.description}</div>
  {"".join(scenario_cards)}
</div>""")

        return f"""<section id="tests" class="section">
  <div class="section-label">04</div>
  <h2>Casos de Prueba</h2>
  <p class="section-desc">Escenarios Gherkin generados para cada historia de usuario, listos para ejecutar en Cucumber / Behave.</p>
  {"".join(blocks)}
</section>"""

    def _sec_hitl_review(self, a: RefinedRequirements, b: GherkinTestSuite, c: ExecutiveReport) -> str:
        review = b.review
        _STATUS_META = {
            "approved":       ("✅ Aprobada",            "#166534", "#dcfce7"),
            "rejected":       ("❌ Rechazada",           "#991b1b", "#fee2e2"),
            "needs_changes":  ("⚠ Aprobada con cambios", "#92400e", "#fef3c7"),
            "pending_review": ("⏳ Pendiente de revisión","#1e40af", "#dbeafe"),
        }
        _ACTION_META = {
            "accepted":     ("Aceptado",       "#166534", "#dcfce7"),
            "reclassified": ("Reclasificado",  "#92400e", "#fef3c7"),
            "commented":    ("Comentado",      "#1e40af", "#dbeafe"),
        }

        status_key = review.review_status.value
        status_label, status_color, status_bg = _STATUS_META.get(
            status_key, ("—", "#6b7280", "#f1f5f9")
        )

        reviewer = review.approved_by or (
            review.change_history[0].reviewer if review.change_history else "—"
        )
        # Fecha: aprobación si existe, si no el timestamp del último cambio
        if review.approved_at:
            reviewed_at = review.approved_at.strftime("%d/%m/%Y %H:%M")
        elif review.change_history:
            reviewed_at = review.change_history[-1].timestamp.strftime("%d/%m/%Y %H:%M")
        else:
            reviewed_at = "—"
        feedback_block = ""
        if review.analyst_feedback:
            feedback_block = f"""<div class="callout callout-info" style="margin-top:1rem">
  💬 <strong>Feedback del revisor:</strong> {review.analyst_feedback}
</div>"""

        # Contadores de acciones
        actions_count: dict[str, int] = {}
        for ch in review.change_history:
            actions_count[ch.action] = actions_count.get(ch.action, 0) + 1
        pills = "".join(
            f'<span class="pill" style="background:{_ACTION_META.get(k,("","#6b7280","#f1f5f9"))[2]};'
            f'color:{_ACTION_META.get(k,("","#6b7280","#f1f5f9"))[1]}">'
            f'{_ACTION_META.get(k,(k,"",""))[0]}: {v}</span>'
            for k, v in actions_count.items()
        )

        # Tabla de decisiones por escenario
        rows_html = ""
        if review.change_history:
            rows = []
            for ch in review.change_history:
                a_label, a_color, a_bg = _ACTION_META.get(ch.action, (ch.action, "#6b7280", "#f1f5f9"))
                notes = ch.notes or "—"
                rows.append(f"""<tr>
  <td><span class="action-badge" style="background:{a_bg};color:{a_color}">{a_label}</span></td>
  <td class="notes-cell">{notes}</td>
  <td class="ts-cell">{ch.timestamp.strftime("%H:%M")}</td>
</tr>""")
            rows_html = f"""<h3 class="sub-h" style="margin-top:1.25rem">Detalle de decisiones por escenario</h3>
<div class="table-wrap">
<table class="review-table">
  <thead><tr><th>Acción</th><th>Notas</th><th>Hora</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
</div>"""

        # Revisión de ambigüedades (datos de contract_a)
        ambig_resolved = [(s.id, r) for s in a.user_stories for r in s.ambiguities_resolved]
        ambig_block = ""
        if ambig_resolved:
            ambig_rows = []
            for story_id, r in ambig_resolved:
                if r.assumption_made:
                    badge = '<span class="action-badge" style="background:#fef3c7;color:#92400e">⚠ Supuesto LLM</span>'
                else:
                    badge = '<span class="action-badge" style="background:#dcfce7;color:#166534">✓ Analista</span>'
                ambig_rows.append(f"""<tr>
  <td>{story_id}</td>
  <td class="notes-cell" style="font-style:italic;color:#dc2626">"{r.original_text}"</td>
  <td class="notes-cell">{r.resolution}</td>
  <td>{badge}</td>
</tr>""")
            ambig_block = f"""<h3 class="sub-h" style="margin-top:1.75rem">Resolución de ambigüedades</h3>
<div class="table-wrap">
<table class="review-table">
  <thead><tr><th>Historia</th><th>Texto ambiguo</th><th>Resolución aplicada</th><th>Origen</th></tr></thead>
  <tbody>{"".join(ambig_rows)}</tbody>
</table>
</div>"""

        return f"""<section id="hitl" class="section">
  <div class="section-label">05</div>
  <h2>Revisión HITL</h2>
  <p class="section-desc">Decisiones tomadas por el analista durante la revisión humana del pipeline.</p>
  <div class="hitl-summary">
    <div class="hitl-card">
      <div class="hitl-card-label">Revisor</div>
      <div class="hitl-card-value">👤 {reviewer}</div>
    </div>
    <div class="hitl-card">
      <div class="hitl-card-label">Decisión final</div>
      <div class="hitl-card-value">
        <span class="action-badge" style="background:{status_bg};color:{status_color};font-size:.85rem;padding:.3rem .8rem">{status_label}</span>
      </div>
    </div>
    <div class="hitl-card">
      <div class="hitl-card-label">Fecha de revisión</div>
      <div class="hitl-card-value">🕐 {reviewed_at}</div>
    </div>
    <div class="hitl-card">
      <div class="hitl-card-label">Escenarios revisados</div>
      <div class="hitl-card-value">🧪 {len(review.change_history)}</div>
    </div>
    <div class="hitl-card">
      <div class="hitl-card-label">Proveedor LLM</div>
      <div class="hitl-card-value">🤖 {c.llm_provider}</div>
    </div>
    <div class="hitl-card">
      <div class="hitl-card-label">Modelo</div>
      <div class="hitl-card-value" style="font-size:.82rem;word-break:break-all">{c.llm_model}</div>
    </div>
  </div>
  <div style="margin-top:.75rem">{pills}</div>
  {feedback_block}
  {rows_html}
  {ambig_block}
</section>"""

    def _sec_iso_coverage(self, b: GherkinTestSuite) -> str:
        cov = b.coverage_by_characteristic
        total_scenarios = sum(cov.values()) or 1

        # Orden fijo ISO 25010
        all_chars = [
            "functional_suitability", "security", "performance_efficiency",
            "usability", "reliability", "compatibility", "maintainability", "portability",
        ]

        # Barras de cobertura
        bar_rows = []
        for char in all_chars:
            count = cov.get(char, 0)
            pct = count / total_scenarios * 100
            color = _ISO_COLORS.get(char, "#6b7280")
            label = _ISO_LABELS.get(char, char)
            desc = _ISO_DESC.get(char, "")
            if count == 0:
                bar_fill = f'<div class="iso-bar-empty">Sin cobertura</div>'
                count_display = '<span class="iso-zero">0</span>'
            else:
                bar_fill = f'<div class="iso-bar-fill" style="width:{max(pct,2):.1f}%;background:{color}"></div>'
                count_display = f'<span class="iso-cnt" style="color:{color}">{count}</span>'

            bar_rows.append(f"""<div class="iso-row" title="{desc}">
  <div class="iso-lbl">
    <span class="iso-dot" style="background:{color}"></span>
    <span class="iso-name">{label}</span>
  </div>
  <div class="iso-bar-track">{bar_fill}</div>
  <div class="iso-meta">{count_display} <span class="iso-pct">{pct:.0f}%</span></div>
</div>""")

        # Tarjetas de detalle por característica
        detail_cards = []
        for char in all_chars:
            count = cov.get(char, 0)
            color = _ISO_COLORS.get(char, "#6b7280")
            label = _ISO_LABELS.get(char, char)
            desc = _ISO_DESC.get(char, "")
            pct = count / total_scenarios * 100

            # Historias que tienen escenarios de esta característica
            stories_covered: list[str] = []
            for cm in b.coverage_matrix:
                if any(qc.value == char for qc in cm.quality_characteristics_covered):
                    if cm.user_story_id not in stories_covered:
                        stories_covered.append(cm.user_story_id)

            if count == 0:
                status_chip = '<span class="iso-chip-gap">⚠ Sin cobertura</span>'
                card_border = "border: 2px dashed #fcd34d;"
                card_bg = "background:#fffbeb;"
            else:
                status_chip = f'<span class="iso-chip-ok">{count} escenarios · {pct:.0f}%</span>'
                card_border = f"border-left: 4px solid {color};"
                card_bg = ""

            stories_html = ""
            if stories_covered:
                stories_html = " ".join(
                    f'<span class="iso-story-tag">{sid}</span>' for sid in stories_covered
                )
                stories_html = f'<div class="iso-stories">Historias cubiertas: {stories_html}</div>'

            detail_cards.append(f"""<div class="iso-detail-card" style="{card_border}{card_bg}">
  <div class="iso-detail-header">
    <span class="iso-dot-lg" style="background:{color}"></span>
    <div>
      <div class="iso-detail-name">{label}</div>
      <div class="iso-detail-desc">{desc}</div>
    </div>
    {status_chip}
  </div>
  {stories_html}
</div>""")

        # Gaps detectados
        gaps = [char for char in all_chars if cov.get(char, 0) == 0]
        gap_block = ""
        if gaps:
            gap_names = ", ".join(_ISO_LABELS.get(g, g) for g in gaps)
            gap_block = f"""<div class="callout callout-warn" style="margin-bottom:1.5rem">
  ⚠️ <strong>Características ISO sin ningún escenario de test:</strong> {gap_names}.<br>
  Considera si el sistema tiene requisitos en estas áreas y agrega escenarios específicos.
</div>"""

        covered_count = sum(1 for c in all_chars if cov.get(c, 0) > 0)
        return f"""<section id="iso" class="section">
  <div class="section-label">06</div>
  <h2>Cobertura ISO 25010</h2>
  <p class="section-desc">
    ISO 25010 define 8 características de calidad del software. Se cubren
    <strong>{covered_count} de 8</strong> con escenarios de test.
  </p>
  {gap_block}
  <div class="iso-bars-wrap">{"".join(bar_rows)}</div>
  <h3 class="sub-h" style="margin-top:1.75rem">Detalle por característica</h3>
  <div class="iso-detail-grid">{"".join(detail_cards)}</div>
</section>"""

    def _sec_risks(self, b: GherkinTestSuite, c: ExecutiveReport) -> str:
        # Riesgos ISO
        risk_rows = []
        for char, count in sorted(b.coverage_by_characteristic.items(), key=lambda x: -x[1]):
            if char == "functional_suitability" or char not in _RISK_META:
                continue
            r_level, r_color, r_bg, r_tool = _RISK_META[char]
            risk_rows.append(f"""<tr>
  <td><strong>{_ISO_LABELS.get(char, char)}</strong></td>
  <td><span class="risk-badge" style="background:{r_bg};color:{r_color};border:1px solid {r_color}">{r_level}</span></td>
  <td class="tc">{count}</td>
  <td class="tool-cell">{r_tool}</td>
</tr>""")

        risk_table = ""
        if risk_rows:
            risk_table = f"""<h3 class="sub-h">Matriz de riesgo por característica ISO 25010</h3>
<div class="table-wrap">
<table class="risk-table">
  <thead><tr><th>Característica</th><th>Nivel de Riesgo</th><th>Escenarios</th><th>Herramienta recomendada</th></tr></thead>
  <tbody>{"".join(risk_rows)}</tbody>
</table>
</div>"""

        # Insights
        insight_cards = []
        for ins in c.quality_insights:
            if ins.severity == "critical":
                icon, color, bg = "🔴", "#dc2626", "#fee2e2"
            elif ins.severity == "warning":
                icon, color, bg = "🟡", "#d97706", "#fef3c7"
            else:
                icon, color, bg = "🔵", "#2563eb", "#dbeafe"
            affected = ""
            if ins.affected_items:
                items = " ".join(f"<code>{i}</code>" for i in ins.affected_items)
                affected = f'<div class="ins-affected">Afecta: {items}</div>'
            insight_cards.append(f"""<div class="insight" style="border-left:4px solid {color};background:{bg}">
  <div class="ins-title">{icon} {ins.title}</div>
  <p class="ins-desc">{ins.description}</p>
  <div class="ins-rec">💡 <strong>Recomendación:</strong> {ins.recommendation}</div>
  {affected}
</div>""")

        insights_block = ""
        if insight_cards:
            insights_block = f"""<h3 class="sub-h" style="margin-top:2rem">Alertas de calidad detectadas</h3>
{"".join(insight_cards)}"""

        uncovered_block = ""
        if b.uncovered_criteria:
            items = " ".join(f"<code>{c}</code>" for c in b.uncovered_criteria)
            uncovered_block = f"""<div class="callout callout-warn" style="margin-top:1.5rem">
  ⚠️ <strong>Criterios sin cobertura de test:</strong> {items}<br>
  Considera regenerar la suite o agregar escenarios manualmente.
</div>"""

        return f"""<section id="risks" class="section">
  <div class="section-label">07</div>
  <h2>Riesgos y Recomendaciones</h2>
  <p class="section-desc">Riesgos identificados según ISO 25010. Los tests no funcionales requieren herramientas especializadas.</p>
  {risk_table}
  {uncovered_block}
  {insights_block}
</section>
</div>"""  # cierre de .main-wrap

    def _sec_footer(self, c: ExecutiveReport) -> str:
        duration = f"{c.total_duration_seconds:.1f}s"
        return f"""<footer class="footer">
  QualityAI Módulo 3 · v{c.module_version} · Pipeline completado en {duration} ·
  Run ID: {c.pipeline_run_id}
</footer>"""

    # ──────────────────────────────────────────────────────────────────────────
    # CSS & JS
    # ──────────────────────────────────────────────────────────────────────────

    def _css(self) -> str:
        return """<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #f0f4f8; color: #1a202c; line-height: 1.6; }

/* Hero */
.hero { background: linear-gradient(135deg, #1e3a8a 0%, #5b21b6 100%); color: #fff; padding: 2.5rem 2rem 2rem; }
.hero-inner { max-width: 1100px; margin: 0 auto; }
.hero-badge { background: rgba(255,255,255,.15); border-radius: 20px; padding: .2rem .8rem; font-size: .75rem; letter-spacing: .05em; }
.hero h1 { font-size: 2rem; font-weight: 700; margin: .5rem 0 .25rem; }
.hero-sub { opacity: .75; font-size: .9rem; margin-bottom: 1.5rem; }
.kpi-strip { display: flex; gap: 1rem; flex-wrap: wrap; }
.kpi { background: rgba(255,255,255,.12); border-radius: 10px; padding: .75rem 1.25rem; min-width: 90px; text-align: center; }
.kn { display: block; font-size: 1.75rem; font-weight: 700; }
.kl { font-size: .7rem; opacity: .8; text-transform: uppercase; letter-spacing: .05em; }

/* Layout */
.sidenav { position: fixed; top: 50%; left: 0; transform: translateY(-50%);
           background: #fff; border-radius: 0 12px 12px 0; padding: .75rem .5rem;
           box-shadow: 2px 0 12px rgba(0,0,0,.1); display: flex; flex-direction: column; gap: .25rem; z-index: 100; }
.sidenav a { display: block; padding: .4rem .75rem; border-radius: 8px; font-size: .8rem;
             color: #475569; text-decoration: none; white-space: nowrap; }
.sidenav a:hover { background: #f1f5f9; color: #1e3a8a; }
.main-wrap { margin-left: 140px; max-width: 960px; padding: 1.5rem 1.5rem 1.5rem 1rem; }
@media(max-width:768px){ .sidenav{display:none;} .main-wrap{margin-left:0;} }

/* Sections */
.section { background: #fff; border-radius: 14px; padding: 2rem; margin-bottom: 1.5rem;
           box-shadow: 0 1px 4px rgba(0,0,0,.06); position: relative; overflow: hidden; }
.section-label { position: absolute; top: 1.25rem; right: 1.5rem; font-size: 3rem; font-weight: 900;
                 color: #f1f5f9; line-height: 1; user-select: none; }
.section h2 { font-size: 1.25rem; color: #1e3a8a; margin-bottom: .35rem; }
.section-desc { color: #64748b; font-size: .9rem; margin-bottom: 1.25rem; }
.sub-h { font-size: 1rem; color: #374151; margin-bottom: .75rem; font-weight: 600; }

/* Raw requirement */
.raw-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
           padding: 1.25rem; font-size: .9rem; color: #334155; white-space: pre-wrap; line-height: 1.7;
           margin-bottom: 1rem; }

/* Callouts */
.callout { border-radius: 8px; padding: .9rem 1rem; margin-bottom: 1rem; font-size: .9rem; }
.callout-info { background: #eff6ff; border: 1px solid #bfdbfe; color: #1e40af; }
.callout-ok   { background: #f0fdf4; border: 1px solid #86efac; color: #166534; }
.callout-warn { background: #fef3c7; border: 1px solid #fcd34d; color: #92400e; }

/* Pills */
.pill { display: inline-block; border-radius: 20px; padding: .15rem .65rem; font-size: .78rem;
        font-weight: 600; margin-left: .4rem; }
.pill-ok   { background: #dcfce7; color: #166534; }
.pill-warn { background: #fef3c7; color: #92400e; }

/* Ambiguities */
.ambig-list { display: flex; flex-direction: column; gap: .9rem; }
.ambig-card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 1rem; }
.ambig-assumed { border-color: #fcd34d; background: #fffbeb; }
.ambig-header { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: .75rem; }
.ambig-story { font-weight: 600; font-size: .9rem; }
.abadge { border-radius: 20px; padding: .15rem .65rem; font-size: .75rem; font-weight: 600; }
.abadge-ok   { background: #dcfce7; color: #166534; }
.abadge-warn { background: #fef3c7; color: #92400e; }
.conf { font-size: .78rem; color: #6b7280; margin-left: auto; }
.ambig-row { display: grid; grid-template-columns: 1fr 30px 1fr; gap: .5rem; align-items: start; }
.ambig-arrow { font-size: 1.4rem; color: #94a3b8; text-align: center; padding-top: 1.5rem; }
.ambig-field-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: #94a3b8; font-weight: 600; margin-bottom: .25rem; }
.ambig-text { font-style: italic; color: #dc2626; font-size: .88rem; }
.ambig-issue { font-size: .85rem; color: #475569; }
.ambig-resolution { font-size: .88rem; color: #166534; font-weight: 500; }

/* User Stories */
.story-list { display: flex; flex-direction: column; gap: .75rem; }
.story-card { border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.story-header { display: flex; justify-content: space-between; align-items: center; padding: .9rem 1rem;
                cursor: pointer; background: #f8fafc; gap: .5rem; }
.story-header:hover { background: #f1f5f9; }
.story-header-left { display: flex; align-items: center; gap: .75rem; }
.story-id { font-size: .75rem; font-weight: 700; color: #64748b; background: #e2e8f0;
            padding: .15rem .5rem; border-radius: 4px; }
.story-title { font-weight: 600; font-size: .95rem; }
.story-header-right { display: flex; align-items: center; gap: .5rem; flex-shrink: 0; }
.priority-badge { font-size: .72rem; font-weight: 700; padding: .2rem .6rem; border-radius: 20px; }
.ac-count { font-size: .78rem; color: #6b7280; }
.chevron { color: #94a3b8; font-size: .8rem; transition: transform .2s; }
.chevron.open { transform: rotate(180deg); }
.story-body { padding: 1.25rem; display: none; border-top: 1px solid #e2e8f0; }
.story-body.open { display: block; }
.story-narrative { background: #eff6ff; border-radius: 8px; padding: .9rem; font-size: .92rem;
                   color: #1e3a8a; margin-bottom: 1rem; line-height: 1.7; }
.narrative-kw { font-weight: 700; }
.story-section-title { font-size: .78rem; text-transform: uppercase; letter-spacing: .06em;
                       color: #94a3b8; font-weight: 700; margin: 1rem 0 .5rem; }
.rules-list { list-style: none; display: flex; flex-direction: column; gap: .35rem; margin-bottom: .75rem; }
.rules-list li::before { content: "▸ "; color: #7c3aed; }
.rules-list li { font-size: .88rem; color: #374151; }

/* Acceptance Criteria */
.ac-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: .9rem; margin-bottom: .6rem; }
.ac-id { font-size: .78rem; font-weight: 700; color: #64748b; margin-bottom: .3rem; }
.ac-desc { font-size: .88rem; color: #374151; margin-bottom: .6rem; }
.neg-badge { background: #fee2e2; color: #dc2626; border-radius: 4px; padding: .1em .4em; font-size: .7rem; margin-left: .4rem; }
.gwt { display: flex; flex-direction: column; gap: .25rem; }
.gwt-row { font-size: .85rem; }
.gwt-kw { display: inline-block; min-width: 72px; font-weight: 700; color: #7c3aed; }
.bv { margin-top: .5rem; font-size: .8rem; color: #6b7280; background: #f8fafc; padding: .3rem .5rem; border-radius: 4px; }

/* Test Cases */
.feature-block { margin-bottom: 1.75rem; }
.feature-title { display: flex; align-items: center; gap: .75rem; font-weight: 700; font-size: .95rem;
                 padding: .6rem 0; border-bottom: 2px solid #e2e8f0; margin-bottom: .75rem; color: #1e3a8a; }
.feature-id { font-size: .72rem; font-weight: 700; background: #dbeafe; color: #1e3a8a;
              padding: .15rem .5rem; border-radius: 4px; }
.feature-count { font-size: .78rem; color: #6b7280; margin-left: auto; }
.feature-desc { font-size: .85rem; color: #64748b; margin-bottom: .75rem; font-style: italic; }
.scenario-card { border-radius: 8px; background: #fafafa; padding: .9rem; margin-bottom: .6rem; }
.scenario-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: .4rem; gap: .5rem; flex-wrap: wrap; }
.scenario-type-badge { display: inline-block; color: #fff; font-size: .7rem; font-weight: 700;
                       padding: .15rem .5rem; border-radius: 4px; margin-right: .4rem; }
.scenario-name { font-weight: 600; font-size: .88rem; }
.iso-chip { font-size: .72rem; background: #f1f5f9; color: #475569; padding: .15rem .5rem;
            border-radius: 20px; white-space: nowrap; }
.tags { display: flex; flex-wrap: wrap; gap: .3rem; margin-bottom: .5rem; }
.tag { background: #e2e8f0; color: #475569; padding: .1em .45em; border-radius: 4px; font-size: .72rem; }
.steps { display: flex; flex-direction: column; gap: .2rem; }
.step { font-size: .84rem; }
.step-kw { display: inline-block; min-width: 58px; font-weight: 700; color: #7c3aed; }
.scenario-footer { font-size: .72rem; color: #94a3b8; margin-top: .5rem; padding-top: .4rem;
                   border-top: 1px dashed #e2e8f0; }

/* Risks */
.table-wrap { overflow-x: auto; margin-bottom: 1rem; }
.risk-table { width: 100%; border-collapse: collapse; font-size: .88rem; }
.risk-table th { background: #f8fafc; padding: .65rem .9rem; text-align: left; font-weight: 600;
                 color: #374151; border-bottom: 2px solid #e2e8f0; }
.risk-table td { padding: .65rem .9rem; border-bottom: 1px solid #f1f5f9; }
.risk-table tr:hover td { background: #f8fafc; }
.risk-badge { border-radius: 20px; padding: .15rem .65rem; font-size: .75rem; font-weight: 700; }
.tc { text-align: center; font-weight: 600; }
.tool-cell { font-size: .8rem; color: #475569; }
.insight { border-radius: 10px; padding: 1rem; margin-bottom: .9rem; }
.ins-title { font-weight: 700; font-size: .95rem; margin-bottom: .4rem; }
.ins-desc { font-size: .88rem; color: #374151; margin-bottom: .5rem; }
.ins-rec { font-size: .88rem; }
.ins-affected { margin-top: .5rem; font-size: .8rem; color: #6b7280; }
.ins-affected code { background: rgba(0,0,0,.07); padding: .1em .3em; border-radius: 3px; }

/* ISO 25010 coverage */
.iso-bars-wrap { display: flex; flex-direction: column; gap: .55rem; margin-bottom: .5rem; }
.iso-row { display: grid; grid-template-columns: 160px 1fr 80px; align-items: center; gap: .75rem; }
.iso-lbl { display: flex; align-items: center; gap: .5rem; }
.iso-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.iso-name { font-size: .85rem; font-weight: 500; }
.iso-bar-track { background: #e2e8f0; border-radius: 6px; height: 22px; overflow: hidden; position: relative; }
.iso-bar-fill { height: 22px; border-radius: 6px; transition: width .6s ease; }
.iso-bar-empty { height: 22px; display: flex; align-items: center; padding: 0 .5rem;
                 font-size: .72rem; color: #94a3b8; font-style: italic; }
.iso-meta { display: flex; flex-direction: column; align-items: flex-end; }
.iso-cnt { font-size: 1rem; font-weight: 700; }
.iso-zero { font-size: 1rem; font-weight: 700; color: #d1d5db; }
.iso-pct { font-size: .72rem; color: #94a3b8; }
.iso-detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: .75rem; }
.iso-detail-card { border-radius: 10px; padding: 1rem; border: 1px solid #e2e8f0; }
.iso-detail-header { display: flex; gap: .75rem; align-items: flex-start; margin-bottom: .6rem; }
.iso-dot-lg { width: 14px; height: 14px; border-radius: 50%; flex-shrink: 0; margin-top: .25rem; }
.iso-detail-name { font-weight: 700; font-size: .92rem; }
.iso-detail-desc { font-size: .78rem; color: #64748b; margin-top: .2rem; line-height: 1.4; }
.iso-chip-ok { background: #dcfce7; color: #166534; border-radius: 20px; padding: .15rem .65rem;
               font-size: .72rem; font-weight: 700; white-space: nowrap; margin-left: auto; flex-shrink: 0; }
.iso-chip-gap { background: #fef3c7; color: #92400e; border-radius: 20px; padding: .15rem .65rem;
                font-size: .72rem; font-weight: 700; white-space: nowrap; margin-left: auto; flex-shrink: 0; }
.iso-stories { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .4rem; }
.iso-story-tag { background: #f1f5f9; color: #475569; border-radius: 4px; padding: .1em .45em;
                 font-size: .72rem; font-weight: 600; }

/* HITL Review */
.hitl-summary { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: .75rem; margin-bottom: .75rem; }
.hitl-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: .9rem 1rem; }
.hitl-card-label { font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; color: #94a3b8; font-weight: 600; margin-bottom: .35rem; }
.hitl-card-value { font-size: .92rem; font-weight: 600; color: #1a202c; }
.action-badge { display: inline-block; border-radius: 20px; padding: .15rem .65rem; font-size: .75rem; font-weight: 700; }
.review-table { width: 100%; border-collapse: collapse; font-size: .85rem; }
.review-table th { background: #f8fafc; padding: .55rem .9rem; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #e2e8f0; }
.review-table td { padding: .55rem .9rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
.review-table tr:hover td { background: #f8fafc; }
.notes-cell { color: #374151; font-size: .83rem; }
.ts-cell { color: #94a3b8; font-size: .78rem; white-space: nowrap; }

/* Footer */
.footer { text-align: center; color: #94a3b8; font-size: .78rem; padding: 1.5rem; margin-left: 140px; }
@media(max-width:768px){ .footer{margin-left:0;} }
</style>"""

    def _js(self) -> str:
        return """<script>
function toggle(header) {
  const body = header.nextElementSibling;
  const chevron = header.querySelector('.chevron');
  const open = body.classList.toggle('open');
  chevron.classList.toggle('open', open);
}
// Highlight active nav link on scroll
const sections = document.querySelectorAll('section[id]');
const navLinks = document.querySelectorAll('.sidenav a');
window.addEventListener('scroll', () => {
  let current = '';
  sections.forEach(s => { if (window.scrollY >= s.offsetTop - 100) current = s.id; });
  navLinks.forEach(a => {
    a.style.background = a.getAttribute('href') === '#' + current ? '#eff6ff' : '';
    a.style.color = a.getAttribute('href') === '#' + current ? '#1e3a8a' : '';
    a.style.fontWeight = a.getAttribute('href') === '#' + current ? '600' : '';
  });
});
</script>"""
