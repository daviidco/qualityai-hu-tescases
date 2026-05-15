"""AmbiguityDetector — IEEE 830 / ISO 25010.

Implementación propia de Module 3, independiente de Module 1.
Mejoras sobre M1-v4:
- suggest_metric(): propone métricas ISO 25010 concretas por categoría
- Severidad dinámica basada en densidad de ambigüedades en el texto
- build_resolved_prompt_section() incluye confidence_score
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Ambiguity:
    word: str
    category: str
    ieee_830_violation: str
    iso_25010_category: str
    suggestion: str
    context: str
    severity: str  # "alta" | "media" | "baja"


_AMBIGUOUS_WORDS: dict[str, dict] = {
    # ── Adjetivos vagos ──────────────────────────────────────────────────────
    "rápido": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define tiempo máximo de respuesta (ej. < 2 s en p95)",
        "severity": "alta",
        "metric_hint": "< 2 s p95 bajo carga normal",
    },
    "rápida": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define tiempo máximo de respuesta (ej. < 2 s en p95)",
        "severity": "alta",
        "metric_hint": "< 2 s p95 bajo carga normal",
    },
    "seguro": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "seguridad",
        "suggestion": "Especifica controles: autenticación, autorización, cifrado TLS, OWASP Top 10",
        "severity": "alta",
        "metric_hint": "TLS 1.2+, MFA, OWASP Top 10 mitigado",
    },
    "segura": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "seguridad",
        "suggestion": "Especifica controles: autenticación, autorización, cifrado TLS, OWASP Top 10",
        "severity": "alta",
        "metric_hint": "TLS 1.2+, MFA, OWASP Top 10 mitigado",
    },
    "fácil": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "usabilidad",
        "suggestion": "Define métrica de usabilidad: tiempo en tarea < X min, SUS score ≥ 80",
        "severity": "media",
        "metric_hint": "SUS score ≥ 80, tiempo en tarea ≤ 3 min para usuario nuevo",
    },
    "fácilmente": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "usabilidad",
        "suggestion": "Define métrica de usabilidad: tiempo en tarea < X min",
        "severity": "media",
        "metric_hint": "SUS score ≥ 80",
    },
    "eficiente": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Especifica métrica: throughput ≥ N req/s, CPU ≤ X%, memoria ≤ Y MB",
        "severity": "media",
        "metric_hint": "throughput ≥ 100 req/s, CPU ≤ 70%",
    },
    "robusto": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "confiabilidad",
        "suggestion": "Define disponibilidad (ej. 99.9% uptime) y MTTR",
        "severity": "media",
        "metric_hint": "disponibilidad 99.9%, MTTR < 1 h",
    },
    "robusta": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "confiabilidad",
        "suggestion": "Define disponibilidad y MTTR",
        "severity": "media",
        "metric_hint": "disponibilidad 99.9%, MTTR < 1 h",
    },
    "intuitivo": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "usabilidad",
        "suggestion": "Define: usuario novato completa tarea en < X min sin ayuda",
        "severity": "media",
        "metric_hint": "usuario novato completa flujo principal en < 5 min",
    },
    "intuitiva": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "usabilidad",
        "suggestion": "Define: usuario novato completa tarea en < X min sin ayuda",
        "severity": "media",
        "metric_hint": "usuario novato completa flujo principal en < 5 min",
    },
    "escalable": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Especifica: soportar N usuarios concurrentes con degradación ≤ X%",
        "severity": "media",
        "metric_hint": "1000 usuarios concurrentes, latencia ≤ 3 s",
    },
    "flexible": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "mantenibilidad",
        "suggestion": "Describe qué debe poder cambiarse sin modificar otros módulos",
        "severity": "baja",
        "metric_hint": "cambio de configuración sin recompilación",
    },
    "confiable": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "confiabilidad",
        "suggestion": "Especifica disponibilidad y tolerancia a fallos: 99.9% uptime, failover < 30 s",
        "severity": "media",
        "metric_hint": "99.9% uptime, failover automático < 30 s",
    },
    "óptimo": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define qué es óptimo en este contexto con métricas medibles",
        "severity": "alta",
        "metric_hint": "especificar KPI concreto",
    },
    "moderno": {
        "category": "adjetivo_vago",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "usabilidad",
        "suggestion": "Describe las características concretas de la UI/UX esperadas",
        "severity": "baja",
        "metric_hint": "cumple WCAG 2.1 AA, diseño responsivo",
    },
    # ── Verbos imprecisos ────────────────────────────────────────────────────
    "gestionar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Descomponer en operaciones CRUD: crear, leer, actualizar, eliminar, listar, buscar",
        "severity": "alta",
        "metric_hint": "definir cada operación con precondición y postcondición",
    },
    "administrar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Descomponer en operaciones CRUD específicas",
        "severity": "alta",
        "metric_hint": "definir cada operación con precondición y postcondición",
    },
    "manejar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Descomponer en operaciones específicas",
        "severity": "alta",
        "metric_hint": "definir cada operación con precondición y postcondición",
    },
    "procesar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Define qué datos entran, cómo se transforman y qué sale",
        "severity": "alta",
        "metric_hint": "input → transformación → output con tipos de datos",
    },
    "controlar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Especifica qué acciones de control: pausar, cancelar, reintentar, monitorear",
        "severity": "media",
        "metric_hint": "listar acciones posibles con estados resultantes",
    },
    "optimizar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define métrica de optimización: reducir latencia en X%, aumentar throughput a Y req/s",
        "severity": "alta",
        "metric_hint": "baseline medible + objetivo concreto",
    },
    "mejorar": {
        "category": "verbo_impreciso",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define la métrica y el valor objetivo de mejora",
        "severity": "alta",
        "metric_hint": "valor actual vs valor objetivo medible",
    },
    # ── Cuantificadores vagos ────────────────────────────────────────────────
    "varios": {
        "category": "cuantificador_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Especifica cantidad exacta o rango: 3 elementos, entre 5 y 10",
        "severity": "media",
        "metric_hint": "cantidad exacta o rango [min, max]",
    },
    "algunos": {
        "category": "cuantificador_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Especifica cantidad exacta o rango",
        "severity": "media",
        "metric_hint": "cantidad exacta o rango [min, max]",
    },
    "muchos": {
        "category": "cuantificador_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define el número exacto o rango con unidad",
        "severity": "media",
        "metric_hint": "N usuarios / N registros (valor concreto)",
    },
    "pocos": {
        "category": "cuantificador_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Especifica cantidad exacta",
        "severity": "baja",
        "metric_hint": "cantidad exacta",
    },
    "suficiente": {
        "category": "cuantificador_vago",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Define qué es suficiente con métricas concretas",
        "severity": "media",
        "metric_hint": "valor mínimo aceptable medible",
    },
    # ── Roles indefinidos ────────────────────────────────────────────────────
    "usuario": {
        "category": "rol_indefinido",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Especifica el rol exacto: administrador, cliente, analista QA, auditor",
        "severity": "alta",
        "metric_hint": "rol con permisos y responsabilidades definidas",
    },
    "usuarios": {
        "category": "rol_indefinido",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Especifica los roles exactos con permisos diferenciados",
        "severity": "alta",
        "metric_hint": "roles con permisos y responsabilidades definidas",
    },
    # ── Temporalidad vaga ────────────────────────────────────────────────────
    "periódicamente": {
        "category": "temporalidad_vaga",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define la frecuencia exacta: cada 5 minutos, diariamente a las 02:00",
        "severity": "alta",
        "metric_hint": "cron expression o intervalo concreto",
    },
    "regularmente": {
        "category": "temporalidad_vaga",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define la frecuencia exacta",
        "severity": "alta",
        "metric_hint": "cron expression o intervalo concreto",
    },
    "en tiempo real": {
        "category": "temporalidad_vaga",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define latencia máxima: < 500 ms, < 1 s, streaming con delay < 100 ms",
        "severity": "alta",
        "metric_hint": "latencia máxima en ms",
    },
    "inmediatamente": {
        "category": "temporalidad_vaga",
        "ieee_830_violation": "verificable",
        "iso_25010_category": "rendimiento",
        "suggestion": "Define tiempo máximo: < 500 ms, < 1 s, < 3 s",
        "severity": "alta",
        "metric_hint": "tiempo máximo en ms",
    },
    # ── Alcance indefinido ───────────────────────────────────────────────────
    "etc": {
        "category": "alcance_indefinido",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Enumera explícitamente todos los elementos sin usar 'etc'",
        "severity": "alta",
        "metric_hint": "lista exhaustiva de elementos",
    },
    "entre otros": {
        "category": "alcance_indefinido",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Enumera todos los elementos explícitamente",
        "severity": "alta",
        "metric_hint": "lista exhaustiva de elementos",
    },
    "y demás": {
        "category": "alcance_indefinido",
        "ieee_830_violation": "completo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Enumera explícitamente todos los elementos",
        "severity": "alta",
        "metric_hint": "lista exhaustiva de elementos",
    },
    "similar": {
        "category": "alcance_indefinido",
        "ieee_830_violation": "no_ambiguo",
        "iso_25010_category": "funcionalidad",
        "suggestion": "Define exactamente a qué se refiere 'similar': mismo formato, mismo flujo, etc.",
        "severity": "media",
        "metric_hint": "criterio de similitud explícito",
    },
}

_IEEE_830_DESCRIPTIONS: dict[str, str] = {
    "no_ambiguo": "Cada requerimiento debe tener una única interpretación posible",
    "completo": "Debe cubrir todos los casos sin dejar requerimientos implícitos",
    "verificable": "Debe poder probarse con métricas concretas y medibles",
    "trazable": "Debe poder rastrearse hasta la fuente que lo origina",
}


class AmbiguityDetector:
    """Detecta ambigüedades en texto de requerimientos usando IEEE 830 / ISO 25010.

    Mejoras sobre M1-v4:
    - suggest_metric(): propone métricas ISO 25010 concretas por palabra
    - Severidad dinámica según densidad (palabras ambiguas / total palabras)
    - build_resolved_prompt_section() incluye confidence_score
    """

    def analyze(self, requirement_text: str) -> list[Ambiguity]:
        found: list[Ambiguity] = []
        seen_words: set[str] = set()
        text_lower = requirement_text.lower()
        total_words = len(requirement_text.split())

        for word, info in _AMBIGUOUS_WORDS.items():
            pattern = rf"\b{re.escape(word)}\b"
            match = re.search(pattern, text_lower)
            if match and word not in seen_words:
                seen_words.add(word)
                start = max(0, match.start() - 30)
                end = min(len(requirement_text), match.end() + 30)
                context = requirement_text[start:end].strip()

                severity = self._dynamic_severity(info["severity"], total_words, len(found))
                found.append(
                    Ambiguity(
                        word=word,
                        category=info["category"],
                        ieee_830_violation=info["ieee_830_violation"],
                        iso_25010_category=info["iso_25010_category"],
                        suggestion=info["suggestion"],
                        context=f"...{context}...",
                        severity=severity,
                    )
                )

        return sorted(found, key=lambda a: {"alta": 0, "media": 1, "baja": 2}[a.severity])

    def suggest_metric(self, word: str) -> str:
        """Devuelve una métrica ISO 25010 concreta sugerida para la palabra ambigua."""
        info = _AMBIGUOUS_WORDS.get(word.lower())
        if info:
            return info.get("metric_hint", info["suggestion"])
        return "Especificar valor concreto y medible"

    def build_prompt_section(self, ambiguities: list[Ambiguity]) -> str:
        if not ambiguities:
            return ""
        lines = ["## AMBIGÜEDADES DETECTADAS (IEEE 830 / ISO 25010)\n"]
        lines.append("Resuelve TODAS las ambigüedades con valores concretos y medibles:\n")
        for i, a in enumerate(ambiguities, 1):
            ieee_desc = _IEEE_830_DESCRIPTIONS.get(a.ieee_830_violation, a.ieee_830_violation)
            lines.append(
                f"{i}. **'{a.word}'** [{a.severity.upper()}]\n"
                f"   - Categoría: {a.category} | ISO 25010: {a.iso_25010_category}\n"
                f"   - Violación IEEE 830: {ieee_desc}\n"
                f"   - Contexto: {a.context}\n"
                f"   - Sugerencia: {a.suggestion}\n"
                f"   - Métrica sugerida: {self.suggest_metric(a.word)}\n"
            )
        return "\n".join(lines)

    def build_resolved_prompt_section(self, resolutions: list[dict]) -> str:
        """Formatea las decisiones del analista como HECHOS (no supuestos).

        resolutions: list de dicts con keys:
            word, category, analyst_resolution, status, confidence_score
        """
        if not resolutions:
            return ""
        lines = ["## DECISIONES DEL ANALISTA QA (HECHOS VERIFICADOS)\n"]
        lines.append(
            "Las siguientes ambigüedades fueron revisadas por el analista. "
            "Úsalas como HECHOS — no hagas suposiciones sobre ellas:\n"
        )
        for r in resolutions:
            confidence = r.get("confidence_score", 1.0)
            assumption_flag = "HECHO VERIFICADO" if confidence >= 1.0 else f"ASUMIDO (confianza: {confidence:.0%})"
            lines.append(
                f"- **'{r['word']}'** → {r['analyst_resolution']} [{assumption_flag}]\n"
            )
        return "\n".join(lines)

    def generate_report(self, requirement_text: str) -> str:
        ambiguities = self.analyze(requirement_text)
        if not ambiguities:
            return "✅ No se detectaron ambigüedades en el texto analizado."
        counts = {"alta": 0, "media": 0, "baja": 0}
        for a in ambiguities:
            counts[a.severity] += 1
        lines = [
            f"📊 REPORTE DE AMBIGÜEDADES — {len(ambiguities)} detectadas",
            f"   Alta: {counts['alta']} | Media: {counts['media']} | Baja: {counts['baja']}",
            "",
        ]
        for a in ambiguities:
            lines.append(
                f"  [{a.severity.upper()}] '{a.word}' ({a.category})\n"
                f"    IEEE 830: {a.ieee_830_violation} | ISO 25010: {a.iso_25010_category}\n"
                f"    → {a.suggestion}"
            )
        return "\n".join(lines)

    def _dynamic_severity(self, base_severity: str, total_words: int, found_count: int) -> str:
        """Eleva la severidad si la densidad de ambigüedades es alta."""
        if total_words == 0:
            return base_severity
        density = (found_count + 1) / total_words
        if density > 0.05 and base_severity == "baja":
            return "media"
        if density > 0.10 and base_severity == "media":
            return "alta"
        return base_severity
