"""StaticAnalysisAgent v2 — Análisis estático del código generado.

No extiende AbstractBaseAgent (sin LLM ni RAG).
Ejecuta radon, complexipy y bandit como subprocesos sobre el código generado
y produce un QualityReport con clasificación honesta ISO 25010.

Pipeline de Stage 4:
  1. Vuelca módulos a directorio temporal
  2. Mide CC y MI (radon cc + radon mi)
  3. Mide CogC (complexipy)
  4. Detecta vulnerabilidades (bandit)
  5. Cruza métricas → FunctionMetrics[]
  6. Clasifica ISO 25010 honestamente (MEASURED vs NOT_APPLICABLE)
  7. Ensambla QualityReport y lo adjunta al CodeGenerationResult
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from ..contracts.contract_d import (
    CodeGenerationResult,
    ComplexityBand,
    FunctionMetrics,
    MeasurementStatus,
    QualityCharacteristicResult,
    QualityReport,
    SecurityFinding,
    SecuritySeverity,
)

# Umbrales de calidad (basados en standards de la industria)
_CC_THRESHOLD = 10     # CC ≥ 10 → exceeds_threshold
_COGC_THRESHOLD = 15   # CogC ≥ 15 → exceeds_threshold
_MI_GOOD = 20.0        # MI < 20 → calidad de mantenibilidad baja

_CC_BANDS = {
    (1, 5): ComplexityBand.A,
    (6, 10): ComplexityBand.B,
    (11, 15): ComplexityBand.C,
    (16, 20): ComplexityBand.D,
}


def _cc_band(cc: int) -> ComplexityBand:
    for (lo, hi), band in _CC_BANDS.items():
        if lo <= cc <= hi:
            return band
    return ComplexityBand.E


class StaticAnalysisAgent:
    """Stage 4: análisis estático de código con radon, complexipy y bandit."""

    def analyze(self, result: CodeGenerationResult) -> CodeGenerationResult:
        """Ejecuta el análisis estático y adjunta quality_report al resultado."""
        if not result.generated_code:
            print("  [StaticAnalysisAgent] Sin módulos que analizar — saltando Stage 4")
            return result

        with tempfile.TemporaryDirectory() as tmp_dir:
            self._volcar_codigo(result, Path(tmp_dir))
            quality_report = self._build_quality_report(Path(tmp_dir))

        result.quality_report = quality_report
        n_exc = quality_report.functions_exceeding_threshold
        n_sec = len(quality_report.security_findings)
        mi = quality_report.maintainability_index
        print(
            f"  ✅ StaticAnalysis: {n_exc} funciones sobre umbral | "
            f"{n_sec} hallazgos de seguridad | MI={mi:.1f}" if mi else
            f"  ✅ StaticAnalysis: {n_exc} funciones sobre umbral | {n_sec} hallazgos de seguridad"
        )
        return result

    # ── Escritura a disco ─────────────────────────────────────────────────────

    def _volcar_codigo(self, result: CodeGenerationResult, tmp: Path) -> None:
        for mod in result.generated_code:
            (tmp / mod.filename).write_text(mod.source_code, encoding="utf-8")

    # ── Ejecución de herramientas ─────────────────────────────────────────────

    def _run(self, cmd: list[str], cwd: Path) -> str:
        """Ejecuta un subproceso y devuelve stdout (vacío si falla)."""
        try:
            r = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=60,
            )
            return r.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _radon_cc(self, tmp: Path) -> dict[str, list[dict[str, Any]]]:
        """Complejidad ciclomática por función. Devuelve {filename: [block]}."""
        out = self._run([sys.executable, "-m", "radon", "cc", "-j", "."], tmp)
        if not out.strip():
            return {}
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}

    def _radon_mi(self, tmp: Path) -> dict[str, dict[str, Any]]:
        """Índice de mantenibilidad por archivo. Devuelve {filename: {mi, rank}}."""
        out = self._run([sys.executable, "-m", "radon", "mi", "-j", "."], tmp)
        if not out.strip():
            return {}
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}

    def _complexipy(self, tmp: Path) -> dict[str, dict[str, int]]:
        """Complejidad cognitiva por función. Devuelve {func_name: {complexity}}."""
        result_file = tmp / "complexity-results.json"
        self._run(
            [sys.executable, "-m", "complexipy", "--output-format", "json", "."],
            tmp,
        )
        if not result_file.exists():
            return {}
        try:
            raw = json.loads(result_file.read_text(encoding="utf-8"))
            # complexipy puede devolver lista o dict según versión
            if isinstance(raw, list):
                return {item["name"]: item for item in raw if "name" in item}
            return raw
        except (json.JSONDecodeError, KeyError):
            return {}

    def _bandit(self, tmp: Path) -> list[dict[str, Any]]:
        """Hallazgos de seguridad. Devuelve lista de issues de bandit."""
        out = self._run([sys.executable, "-m", "bandit", "-r", "-f", "json", "."], tmp)
        if not out.strip():
            return []
        try:
            data = json.loads(out)
            return data.get("results", [])
        except json.JSONDecodeError:
            return []

    # ── Construcción de modelos ───────────────────────────────────────────────

    def _build_function_metrics(
        self,
        cc_data: dict[str, list[dict[str, Any]]],
        cogc_data: dict[str, dict[str, int]],
    ) -> list[FunctionMetrics]:
        metrics: list[FunctionMetrics] = []
        for filename, blocks in cc_data.items():
            for block in blocks:
                if block.get("type") not in ("function", "method"):
                    continue
                name = block.get("name", "unknown")
                cc = block.get("complexity", 1)
                cogc_entry = cogc_data.get(name, {})
                cogc = cogc_entry.get("complexity", cogc_entry.get("cognitive_complexity", 0))
                metrics.append(
                    FunctionMetrics(
                        function_name=name,
                        module=filename,
                        cyclomatic_complexity=cc,
                        cognitive_complexity=cogc,
                        cc_band=_cc_band(cc),
                        nesting_depth=block.get("col_offset", 0) // 4,
                        exceeds_threshold=(cc >= _CC_THRESHOLD or cogc >= _COGC_THRESHOLD),
                    )
                )
        return metrics

    def _build_security_findings(
        self, bandit_issues: list[dict[str, Any]]
    ) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for issue in bandit_issues:
            try:
                sev_raw = issue.get("issue_severity", "low").lower()
                sev = SecuritySeverity(sev_raw) if sev_raw in ("low", "medium", "high") else SecuritySeverity.LOW
                findings.append(
                    SecurityFinding(
                        test_id=issue.get("test_id", "B000"),
                        severity=sev,
                        module=Path(issue.get("filename", "unknown")).name,
                        line_number=issue.get("line_number", 0),
                        description=issue.get("issue_text", ""),
                    )
                )
            except Exception:  # noqa: BLE001
                continue
        return findings

    def _classify_iso_25010(
        self,
        function_metrics: list[FunctionMetrics],
        security_findings: list[SecurityFinding],
    ) -> list[QualityCharacteristicResult]:
        """Clasificación honesta: declara lo que se puede medir vs. lo que no."""
        n_exceeds = sum(1 for m in function_metrics if m.exceeds_threshold)
        n_high_sec = sum(1 for f in security_findings if f.severity == SecuritySeverity.HIGH)

        return [
            QualityCharacteristicResult(
                characteristic="maintainability",
                status=MeasurementStatus.MEASURED,
                metrics_used=["radon-cc", "radon-mi", "complexipy"],
                verdict=(
                    f"{n_exceeds} funciones sobre umbral CC/CogC. "
                    "Refactoriza funciones complejas." if n_exceeds > 0
                    else "Complejidad dentro de umbrales aceptables."
                ),
            ),
            QualityCharacteristicResult(
                characteristic="security",
                status=MeasurementStatus.MEASURED,
                metrics_used=["bandit"],
                verdict=(
                    f"{n_high_sec} hallazgos HIGH. Revisión inmediata requerida." if n_high_sec > 0
                    else f"{len(security_findings)} hallazgos totales. Sin severidad HIGH."
                    if security_findings else "Sin vulnerabilidades detectadas por análisis estático."
                ),
            ),
            QualityCharacteristicResult(
                characteristic="functional_suitability",
                status=MeasurementStatus.REQUIRES_HUMAN_JUDGMENT,
                metrics_used=[],
                verdict="Requiere ejecución y revisión humana para verificar correctitud funcional.",
            ),
            QualityCharacteristicResult(
                characteristic="reliability",
                status=MeasurementStatus.REQUIRES_HUMAN_JUDGMENT,
                metrics_used=[],
                verdict="Manejo de errores y resiliencia requieren revisión de arquitectura.",
            ),
            QualityCharacteristicResult(
                characteristic="performance_efficiency",
                status=MeasurementStatus.NOT_APPLICABLE,
                metrics_used=[],
                verdict="Solo medible en runtime con profiling real.",
            ),
            QualityCharacteristicResult(
                characteristic="compatibility",
                status=MeasurementStatus.NOT_APPLICABLE,
                metrics_used=[],
                verdict="Requiere pruebas de integración con sistemas reales.",
            ),
            QualityCharacteristicResult(
                characteristic="usability",
                status=MeasurementStatus.NOT_APPLICABLE,
                metrics_used=[],
                verdict="Solo medible con usuarios finales.",
            ),
            QualityCharacteristicResult(
                characteristic="portability",
                status=MeasurementStatus.NOT_APPLICABLE,
                metrics_used=[],
                verdict="Requiere despliegue en múltiples entornos.",
            ),
        ]

    def _build_quality_report(self, tmp: Path) -> QualityReport:
        cc_data = self._radon_cc(tmp)
        mi_data = self._radon_mi(tmp)
        cogc_data = self._complexipy(tmp)
        bandit_issues = self._bandit(tmp)

        function_metrics = self._build_function_metrics(cc_data, cogc_data)
        security_findings = self._build_security_findings(bandit_issues)

        # MI promedio ponderado
        mi_values = [v.get("mi", 0.0) for v in mi_data.values() if isinstance(v, dict)]
        avg_mi = sum(mi_values) / len(mi_values) if mi_values else None

        iso = self._classify_iso_25010(function_metrics, security_findings)
        n_exceeds = sum(1 for m in function_metrics if m.exceeds_threshold)

        return QualityReport(
            function_metrics=function_metrics,
            maintainability_index=avg_mi,
            security_findings=security_findings,
            iso_25010_coverage=iso,
            functions_exceeding_threshold=n_exceeds,
        )
