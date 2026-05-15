"""Generador de reporte ejecutivo en PDF usando fpdf2.

Produce un documento de 2 páginas A4, fondo blanco, apto para imprimir.
Usa DejaVu Sans (Unicode) para soporte completo de caracteres UTF-8.
"""
from __future__ import annotations

import os
from datetime import datetime

from fpdf import FPDF

# ── Paleta corporativa ─────────────────────────────────────────────────────────
_NAVY       = (30,  58, 138)
_BLUE       = (37, 99,  235)
_LIGHT_BLUE = (219, 234, 254)
_DARK       = (17,  24,  39)
_GRAY       = (75,  85,  99)
_LIGHT_GRAY = (243, 244, 246)
_MID_GRAY   = (209, 213, 219)
_WHITE      = (255, 255, 255)
_GREEN      = (22, 163,  74)
_GREEN_BG   = (220, 252, 231)
_ORANGE     = (217, 119,   6)
_ORANGE_BG  = (254, 243, 199)
_RED        = (220,  38,  38)
_RED_BG     = (254, 226, 226)

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
_RISK_META = {
    "security":               ("CRITICO", _RED,    _RED_BG),
    "performance_efficiency": ("ALTO",    _ORANGE, _ORANGE_BG),
    "reliability":            ("ALTO",    _ORANGE, _ORANGE_BG),
    "compatibility":          ("MEDIO",   _BLUE,   _LIGHT_BLUE),
    "usability":              ("MEDIO",   _BLUE,   _LIGHT_BLUE),
    "maintainability":        ("BAJO",    _GRAY,   _LIGHT_GRAY),
    "portability":            ("BAJO",    _GRAY,   _LIGHT_GRAY),
}
_PRIORITY_ES = {
    "critical": "CRITICA",
    "high":     "ALTA",
    "medium":   "MEDIA",
    "low":      "BAJA",
}
_STATUS_ES = {
    "approved":       "APROBADA",
    "rejected":       "RECHAZADA",
    "needs_changes":  "CON OBSERVACIONES",
    "pending_review": "PENDIENTE",
}

# DejaVu font paths (installed via fonts-dejavu-core in Dockerfile)
_DEJAVU_DIR = "/usr/share/fonts/truetype/dejavu"
_FONT_REGULAR = os.path.join(_DEJAVU_DIR, "DejaVuSans.ttf")
_FONT_BOLD    = os.path.join(_DEJAVU_DIR, "DejaVuSans-Bold.ttf")
_FONT_ITALIC  = os.path.join(_DEJAVU_DIR, "DejaVuSans-Oblique.ttf")
_USE_DEJAVU   = all(os.path.exists(p) for p in [_FONT_REGULAR, _FONT_BOLD, _FONT_ITALIC])
_FONT         = "DejaVu" if _USE_DEJAVU else "Helvetica"


def _t(text: str) -> str:
    """Make text safe for the active font encoding."""
    if _USE_DEJAVU:
        return str(text)
    # Latin-1 fallback: replace common non-Latin-1 chars
    return (
        str(text)
        .replace("→", "->")   # →
        .replace("…", "...")  # …
        .replace("•", "-")    # •
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


class _PDF(FPDF):
    def __init__(self, run_id: str, version: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._run_id  = run_id
        self._version = version
        if _USE_DEJAVU:
            self.add_font("DejaVu", "",  _FONT_REGULAR)
            self.add_font("DejaVu", "B", _FONT_BOLD)
            self.add_font("DejaVu", "I", _FONT_ITALIC)

    def footer(self):
        self.set_y(-12)
        self.set_font(_FONT, "I", 7)
        self.set_text_color(*_GRAY)
        left = _t(f"QualityAI Modulo 3 · v{self._version} · Run #{self._run_id}")
        self.cell(0, 5, left, 0, 0, "L")
        self.set_x(-30)
        self.cell(20, 5, _t(f"Pagina {self.page_no()}"), 0, 0, "R")


def _set_color(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_text_color(*rgb)


def _filled_rect(pdf: FPDF, x, y, w, h, fill_rgb, border_rgb=None) -> None:
    pdf.set_fill_color(*fill_rgb)
    if border_rgb:
        pdf.set_draw_color(*border_rgb)
        pdf.rect(x, y, w, h, "FD")
    else:
        pdf.set_draw_color(*fill_rgb)
        pdf.rect(x, y, w, h, "F")


def _section_title(pdf: FPDF, y: float, title: str) -> float:
    pdf.set_xy(15, y)
    pdf.set_font(_FONT, "B", 10)
    _set_color(pdf, _NAVY)
    pdf.cell(0, 6, _t(title.upper()), 0, 1)
    pdf.set_draw_color(*_NAVY)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)
    return pdf.get_y()


def generate_executive_pdf(report_data: dict) -> bytes:
    """Returns PDF bytes for the executive report."""

    run_id   = report_data.get("pipeline_run_id", "")[:8]
    version  = report_data.get("module_version", "3.0.0")
    created  = report_data.get("created_at", "")
    try:
        created_fmt = datetime.fromisoformat(created).strftime("%d/%m/%Y %H:%M")
    except Exception:
        created_fmt = created[:16]

    pdf = _PDF(run_id, version)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(15, 15, 15)

    # ═══════════════════════════════════════════════════════════════════════════
    # PÁGINA 1
    # ═══════════════════════════════════════════════════════════════════════════
    pdf.add_page()

    # ── Header bar ────────────────────────────────────────────────────────────
    _filled_rect(pdf, 0, 0, 210, 22, _NAVY)
    pdf.set_xy(15, 4)
    pdf.set_font(_FONT, "B", 13)
    pdf.set_text_color(*_WHITE)
    pdf.cell(120, 7, _t("REPORTE EJECUTIVO DE CALIDAD"), 0, 0)
    pdf.set_font(_FONT, "", 8)
    pdf.set_text_color(180, 200, 255)
    pdf.set_xy(15, 12)
    pdf.cell(120, 5, _t(f"QualityAI - Modulo 3 - v{version}"), 0, 0)
    pdf.set_xy(135, 4)
    pdf.set_text_color(*_WHITE)
    pdf.set_font(_FONT, "B", 9)
    pdf.cell(60, 5, _t(f"Run #{run_id}"), 0, 0, "R")
    pdf.set_xy(135, 10)
    pdf.set_font(_FONT, "", 8)
    pdf.set_text_color(180, 200, 255)
    pdf.cell(60, 5, _t(created_fmt), 0, 0, "R")
    pdf.ln(10)

    # ── Banner modo eco ───────────────────────────────────────────────────────
    if report_data.get("eco_mode"):
        _filled_rect(pdf, 0, pdf.get_y(), 210, 7, (6, 95, 70))
        pdf.set_xy(15, pdf.get_y() + 1)
        pdf.set_font(_FONT, "B", 8)
        pdf.set_text_color(110, 231, 183)
        pdf.cell(0, 5, _t("ECO MODE - Salida reducida para economizar tokens (max 3 HU, 2 AC, 2 escenarios/AC)"), 0, 0, "C")
        pdf.ln(8)

    # ── Requerimiento ─────────────────────────────────────────────────────────
    y = pdf.get_y() + 6
    _section_title(pdf, y, "01 - Requerimiento Analizado")
    req_text = report_data.get("original_requirement", "")
    if len(req_text) > 2000:
        req_text = req_text[:2000] + "..."
    pdf.set_x(15)
    pdf.set_font(_FONT, "", 8.5)
    _set_color(pdf, _DARK)
    pdf.multi_cell(180, 4.5, _t(req_text))
    pdf.ln(3)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    y = pdf.get_y()
    _section_title(pdf, y, "02 - Metricas Clave")
    kpis = [
        ("Historias",    str(report_data.get("total_stories", 0))),
        ("Criterios AC", str(report_data.get("total_acceptance_criteria", 0))),
        ("Tests",        str(report_data.get("total_scenarios", 0))),
        ("Cobertura",    f"{report_data.get('coverage_pct', 0)}%"),
        ("Ambiguedades", str(report_data.get("total_ambiguities", 0))),
    ]
    kpi_w = 34
    kpi_x = 15
    kpi_y = pdf.get_y()
    for label, value in kpis:
        _filled_rect(pdf, kpi_x, kpi_y, kpi_w, 18, _LIGHT_BLUE, _MID_GRAY)
        pdf.set_xy(kpi_x, kpi_y + 1.5)
        pdf.set_font(_FONT, "B", 16)
        _set_color(pdf, _NAVY)
        pdf.cell(kpi_w, 9, _t(value), 0, 0, "C")
        pdf.set_xy(kpi_x, kpi_y + 10)
        pdf.set_font(_FONT, "", 7)
        _set_color(pdf, _GRAY)
        pdf.cell(kpi_w, 5, _t(label.upper()), 0, 0, "C")
        kpi_x += kpi_w + 2
    pdf.ln(24)

    # ── Decisión HITL + Modelo ─────────────────────────────────────────────────
    y = pdf.get_y()
    _section_title(pdf, y, "03 - Estado de Revision")
    hitl = report_data.get("hitl", {})
    status_key = hitl.get("review_status", "pending_review")
    status_label = _STATUS_ES.get(status_key, status_key.upper())

    if status_key == "approved":
        s_fill, s_text = _GREEN_BG, _GREEN
    elif status_key == "rejected":
        s_fill, s_text = _RED_BG, _RED
    else:
        s_fill, s_text = _ORANGE_BG, _ORANGE

    rev_at = hitl.get("reviewed_at", "")
    try:
        rev_at_fmt = datetime.fromisoformat(rev_at).strftime("%d/%m/%Y %H:%M") if rev_at else "-"
    except Exception:
        rev_at_fmt = rev_at[:16] if rev_at else "-"

    row_y = pdf.get_y()
    _filled_rect(pdf, 15, row_y, 50, 14, s_fill, s_text)
    pdf.set_xy(15, row_y + 2)
    pdf.set_font(_FONT, "B", 9)
    _set_color(pdf, s_text)
    pdf.cell(50, 10, _t(status_label), 0, 0, "C")
    details = [
        ("Revisor",       hitl.get("reviewer", "-") or "-"),
        ("Fecha rev.",    rev_at_fmt),
        ("Proveedor LLM", report_data.get("llm_provider", "-").upper()),
        ("Modelo",        report_data.get("llm_model", "-")),
    ]
    dx = 70
    for lbl, val in details:
        pdf.set_xy(dx, row_y + 1)
        pdf.set_font(_FONT, "", 7)
        _set_color(pdf, _GRAY)
        pdf.cell(30, 4, _t(lbl.upper()))
        pdf.set_xy(dx, row_y + 5.5)
        pdf.set_font(_FONT, "B", 8)
        _set_color(pdf, _DARK)
        pdf.cell(30, 5, _t(str(val)[:30]))
        dx += 32
    pdf.ln(20)

    # ── ISO 25010 coverage ────────────────────────────────────────────────────
    y = pdf.get_y()
    _section_title(pdf, y, "04 - Cobertura ISO 25010")
    iso_cov = report_data.get("iso_coverage", {})
    total_sc = sum(iso_cov.values()) or 1
    all_iso = [
        "functional_suitability", "security", "performance_efficiency",
        "usability", "reliability", "compatibility", "maintainability", "portability",
    ]
    hdr_y = pdf.get_y()
    _filled_rect(pdf, 15, hdr_y, 180, 7, _NAVY)
    pdf.set_xy(15, hdr_y + 1)
    pdf.set_font(_FONT, "B", 7.5)
    _set_color(pdf, _WHITE)
    pdf.cell(70, 5, "Caracteristica ISO 25010", 0, 0)
    pdf.cell(30, 5, "Escenarios", 0, 0, "C")
    pdf.cell(30, 5, "Cobertura", 0, 0, "C")
    pdf.cell(50, 5, "Estado", 0, 0, "C")
    pdf.ln(8)
    row_fill = False
    for char in all_iso:
        count = iso_cov.get(char, 0)
        pct = count / total_sc * 100
        label = _ISO_LABELS.get(char, char)
        row_y2 = pdf.get_y()
        bg = _LIGHT_GRAY if row_fill else _WHITE
        _filled_rect(pdf, 15, row_y2, 180, 6.5, bg)
        pdf.set_xy(15, row_y2 + 1)
        pdf.set_font(_FONT, "", 8)
        _set_color(pdf, _DARK)
        pdf.cell(70, 5, _t(label))
        pdf.cell(30, 5, str(count), 0, 0, "C")
        pdf.cell(30, 5, f"{pct:.0f}%", 0, 0, "C")
        bar_x = 105 + 30
        bar_w = 45
        bar_y_pos = row_y2 + 2
        _filled_rect(pdf, bar_x, bar_y_pos, bar_w, 3, (229, 231, 235))
        if pct > 0:
            _filled_rect(pdf, bar_x, bar_y_pos, max(bar_w * pct / 100, 1), 3, _BLUE)
        pdf.ln(6.5)
        row_fill = not row_fill

    # ═══════════════════════════════════════════════════════════════════════════
    # PÁGINA 2
    # ═══════════════════════════════════════════════════════════════════════════
    pdf.add_page()

    _filled_rect(pdf, 0, 0, 210, 12, _NAVY)
    pdf.set_xy(15, 3)
    pdf.set_font(_FONT, "B", 9)
    _set_color(pdf, _WHITE)
    pdf.cell(120, 6, "REPORTE EJECUTIVO DE CALIDAD - continuacion")
    pdf.set_xy(135, 3)
    pdf.set_font(_FONT, "", 8)
    pdf.set_text_color(180, 200, 255)
    pdf.cell(60, 6, _t(f"Run #{run_id} - {created_fmt}"), 0, 0, "R")
    pdf.ln(16)

    # ── Matriz de riesgos ─────────────────────────────────────────────────────
    y = pdf.get_y()
    _section_title(pdf, y, "05 - Matriz de Riesgos")
    hdr_y = pdf.get_y()
    _filled_rect(pdf, 15, hdr_y, 180, 7, _NAVY)
    pdf.set_xy(15, hdr_y + 1)
    pdf.set_font(_FONT, "B", 7.5)
    _set_color(pdf, _WHITE)
    pdf.cell(65, 5, "Caracteristica")
    pdf.cell(30, 5, "Nivel Riesgo", 0, 0, "C")
    pdf.cell(20, 5, "Tests", 0, 0, "C")
    pdf.cell(65, 5, "Herramienta recomendada")
    pdf.ln(8)

    _RISK_TOOLS = {
        "security":               "OWASP ZAP, Burp Suite, Nessus",
        "performance_efficiency": "JMeter, k6, Locust",
        "reliability":            "Chaos Engineering, Toxiproxy",
        "compatibility":          "BrowserStack, Sauce Labs",
        "usability":              "Axe, Lighthouse, SUS survey",
        "maintainability":        "SonarQube, CodeClimate",
        "portability":            "Docker, CI multi-OS",
    }
    row_fill = False
    sorted_chars = sorted(
        [(c, v) for c, v in iso_cov.items() if c != "functional_suitability" and c in _RISK_META],
        key=lambda x: -x[1],
    )
    for char, count in sorted_chars:
        r_level, r_color, r_bg = _RISK_META[char]
        r_tool  = _RISK_TOOLS.get(char, "-")
        label   = _ISO_LABELS.get(char, char)
        row_y3  = pdf.get_y()
        bg = _LIGHT_GRAY if row_fill else _WHITE
        _filled_rect(pdf, 15, row_y3, 180, 6.5, bg)
        pdf.set_xy(15, row_y3 + 1)
        pdf.set_font(_FONT, "", 8)
        _set_color(pdf, _DARK)
        pdf.cell(65, 5, _t(label))
        _filled_rect(pdf, 80, row_y3 + 1, 26, 4.5, r_bg)
        pdf.set_xy(80, row_y3 + 1.5)
        pdf.set_font(_FONT, "B", 7)
        _set_color(pdf, r_color)
        pdf.cell(26, 4, _t(r_level), 0, 0, "C")
        pdf.set_xy(106, row_y3 + 1)
        pdf.set_font(_FONT, "", 8)
        _set_color(pdf, _DARK)
        pdf.cell(20, 5, str(count), 0, 0, "C")
        pdf.set_xy(126, row_y3 + 1)
        pdf.cell(65, 5, _t(r_tool[:35]))
        pdf.ln(6.5)
        row_fill = not row_fill
    pdf.ln(4)

    # ── Historias de usuario ───────────────────────────────────────────────────
    y = pdf.get_y()
    _section_title(pdf, y, "06 - Historias de Usuario")
    user_stories = report_data.get("user_stories", [])
    hdr_y = pdf.get_y()
    _filled_rect(pdf, 15, hdr_y, 180, 7, _NAVY)
    pdf.set_xy(15, hdr_y + 1)
    pdf.set_font(_FONT, "B", 7.5)
    _set_color(pdf, _WHITE)
    pdf.cell(18, 5, "ID")
    pdf.cell(95, 5, "Historia")
    pdf.cell(22, 5, "Prioridad", 0, 0, "C")
    pdf.cell(20, 5, "Criterios", 0, 0, "C")
    pdf.cell(25, 5, "Tests")
    pdf.ln(8)

    features = report_data.get("features", [])
    tests_by_story: dict[str, int] = {
        f["user_story_id"]: len(f.get("scenarios", []))
        for f in features
    }
    row_fill = False
    for story in user_stories:
        prio    = _PRIORITY_ES.get(story.get("priority", ""), "-")
        n_ac    = len(story.get("acceptance_criteria", []))
        n_tests = tests_by_story.get(story.get("id", ""), 0)
        row_y4  = pdf.get_y()
        bg = _LIGHT_GRAY if row_fill else _WHITE
        _filled_rect(pdf, 15, row_y4, 180, 6.5, bg)
        pdf.set_xy(15, row_y4 + 1)
        pdf.set_font(_FONT, "B", 7.5)
        _set_color(pdf, _BLUE)
        pdf.cell(18, 5, _t(story.get("id", "")))
        pdf.set_font(_FONT, "", 8)
        _set_color(pdf, _DARK)
        title = story.get("title", "")[:52]
        pdf.cell(95, 5, _t(title))
        pdf.cell(22, 5, _t(prio), 0, 0, "C")
        pdf.cell(20, 5, str(n_ac), 0, 0, "C")
        pdf.cell(25, 5, str(n_tests))
        pdf.ln(6.5)
        row_fill = not row_fill
    pdf.ln(4)

    # ── Quality Insights ──────────────────────────────────────────────────────
    quality_insights = report_data.get("quality_insights", [])
    if quality_insights:
        y = pdf.get_y()
        _section_title(pdf, y, "07 - Alertas de Calidad")
        for ins in quality_insights[:4]:
            sev = ins.get("severity", "info")
            if sev == "critical":
                fill, color = _RED_BG, _RED
                badge = "CRITICO"
            elif sev == "warning":
                fill, color = _ORANGE_BG, _ORANGE
                badge = "ATENCION"
            else:
                fill, color = _LIGHT_BLUE, _BLUE
                badge = "INFO"

            ins_y = pdf.get_y()
            _filled_rect(pdf, 15, ins_y, 180, 12, fill, color)
            _filled_rect(pdf, 15, ins_y, 22, 12, color)
            pdf.set_xy(15, ins_y + 3.5)
            pdf.set_font(_FONT, "B", 7)
            _set_color(pdf, _WHITE)
            pdf.cell(22, 5, badge, 0, 0, "C")
            pdf.set_xy(40, ins_y + 1.5)
            pdf.set_font(_FONT, "B", 8)
            _set_color(pdf, color)
            pdf.cell(150, 4.5, _t(ins.get("title", "")[:80]))
            pdf.set_xy(40, ins_y + 6.5)
            pdf.set_font(_FONT, "", 7.5)
            _set_color(pdf, _DARK)
            rec = ins.get("recommendation", "")[:95]
            pdf.cell(150, 4, _t(rec))
            pdf.ln(13)

    # ── Supuestos del LLM ─────────────────────────────────────────────────────
    ambiguities = report_data.get("ambiguities", [])
    assumed = [a for a in ambiguities if a.get("assumption_made")]
    if assumed:
        y = pdf.get_y()
        _section_title(pdf, y, "08 - Supuestos del LLM (requieren validacion)")
        for a in assumed[:6]:
            ins_y = pdf.get_y()
            _filled_rect(pdf, 15, ins_y, 180, 11, _ORANGE_BG, _ORANGE)
            pdf.set_xy(18, ins_y + 1.5)
            pdf.set_font(_FONT, "B", 7.5)
            _set_color(pdf, _ORANGE)
            pdf.cell(40, 4, _t(f"{a.get('story_id','')} - "))
            pdf.set_font(_FONT, "I", 7.5)
            _set_color(pdf, _RED)
            txt = f'"{a.get("original_text", "")[:40]}"'
            pdf.cell(80, 4, _t(txt))
            pdf.set_xy(18, ins_y + 6)
            pdf.set_font(_FONT, "", 7.5)
            _set_color(pdf, _DARK)
            res = f"-> {a.get('resolution', '')[:95]}"
            pdf.cell(170, 4, _t(res))
            pdf.ln(12)

    return bytes(pdf.output())
