"""TraceabilityAgent v3 — CMMI L3: matriz bidireccional + cobertura de ramas.

No extiende AbstractBaseAgent (sin LLM ni RAG).

Pipeline de Stage 5:
  1. Extrae todos los scenario_ids del Contract B (ground truth)
  2. Extrae markers @pytest.mark.scenario() de los tests generados (regex)
  3. Construye matriz bidireccional:
       Forward:  escenario → tests que lo cubren  (COVERED | ORPHAN_FORWARD)
       Backward: test → escenarios que justifica   (COVERED | ORPHAN_BACKWARD)
  4. Mide cobertura de ramas con pytest --cov-branch
  5. Adjunta traceability_matrix + coverage_report al CodeGenerationResult
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import json
from pathlib import Path

from ..contracts.contract_b import GherkinTestSuite
from ..contracts.contract_d import (
    CodeGenerationResult,
    CoverageReport,
    ScenarioTraceability,
    TestTraceability,
    TraceabilityMatrix,
    TraceabilityStatus,
)

# Regex que captura @pytest.mark.scenario("SCN-001") y variantes
_MARKER_RE = re.compile(
    r'@pytest\.mark\.scenario\(["\']([^"\']+)["\']\)',
)
# Patrón alternativo: scenario_ids en comentarios # scenario: SCN-001
_COMMENT_RE = re.compile(r'#\s*scenario[s]?:\s*([\w\-,\s]+)')

_BRANCH_THRESHOLD = 80.0  # % mínimo de cobertura de ramas para CMMI L3


class TraceabilityAgent:
    """Stage 5: trazabilidad CMMI L3 + medición de cobertura de ramas."""

    def trace(
        self,
        result: CodeGenerationResult,
        contract_b: GherkinTestSuite,
    ) -> CodeGenerationResult:
        """Construye la matriz de trazabilidad y mide cobertura."""
        if not result.generated_tests:
            print("  [TraceabilityAgent] Sin tests — saltando Stage 5")
            return result

        scenario_map = self._extract_scenario_ids(contract_b)
        test_markers = self._extract_markers(result)

        matrix = self._build_matrix(scenario_map, test_markers)
        coverage = self._measure_coverage(result)

        result.traceability_matrix = matrix
        result.coverage_report = coverage

        orphans = len(matrix.orphan_scenarios) + len(matrix.orphan_tests)
        print(
            f"  ✅ Trazabilidad: {matrix.requirements_coverage_pct:.0f}% escenarios cubiertos | "
            f"{matrix.tests_justified_pct:.0f}% tests justificados | "
            f"CMMI L3={'✓' if matrix.cmmi_l3_compliant else '✗'} | "
            f"Branch cov={coverage.branch_coverage_pct:.0f}%"
        )
        if orphans:
            print(f"  ⚠️  {len(matrix.orphan_scenarios)} escenarios huérfanos | "
                  f"{len(matrix.orphan_tests)} tests huérfanos")
        return result

    # ── Extracción de IDs ─────────────────────────────────────────────────────

    def _extract_scenario_ids(self, contract_b: GherkinTestSuite) -> dict[str, str]:
        """Devuelve {scenario_id: scenario_name} de todos los escenarios del Contract B."""
        ids: dict[str, str] = {}
        for feature in contract_b.features:
            for scenario in feature.scenarios:
                ids[scenario.acceptance_criterion_id] = scenario.name
                # También indexar por nombre de escenario limpio (por si el LLM lo usó)
                clean = scenario.name.lower().replace(" ", "_")
                ids[clean] = scenario.name
        return ids

    def _extract_markers(
        self, result: CodeGenerationResult
    ) -> dict[str, list[str]]:
        """Devuelve {test_name: [scenario_ids]} desde los campos scenario_ids y marcadores regex."""
        test_markers: dict[str, list[str]] = {}
        for test in result.generated_tests:
            ids: set[str] = set(test.scenario_ids)

            # También extraer con regex del source code (fuente de verdad para pytest)
            for match in _MARKER_RE.finditer(test.source_code):
                raw = match.group(1)
                # Limpiar notación [SCN-001] → SCN-001
                ids.add(raw.strip("[]"))

            # Fallback: comentarios # scenario: SCN-001, SCN-002
            for match in _COMMENT_RE.finditer(test.source_code):
                for sid in re.split(r'[,\s]+', match.group(1)):
                    sid = sid.strip()
                    if sid:
                        ids.add(sid)

            test_markers[test.test_name] = list(ids)
        return test_markers

    # ── Construcción de matriz ────────────────────────────────────────────────

    def _build_matrix(
        self,
        scenario_map: dict[str, str],
        test_markers: dict[str, list[str]],
    ) -> TraceabilityMatrix:
        # Forward: escenario → tests
        forward: list[ScenarioTraceability] = []
        for sid, sname in scenario_map.items():
            covering = [
                tname for tname, ids in test_markers.items()
                if sid in ids
            ]
            forward.append(
                ScenarioTraceability(
                    scenario_id=sid,
                    scenario_name=sname,
                    covering_tests=covering,
                    status=TraceabilityStatus.COVERED if covering else TraceabilityStatus.ORPHAN_FORWARD,
                )
            )

        # Backward: test → escenarios
        backward: list[TestTraceability] = []
        for tname, ids in test_markers.items():
            justifying = [sid for sid in ids if sid in scenario_map]
            backward.append(
                TestTraceability(
                    test_name=tname,
                    justifying_scenarios=justifying,
                    status=TraceabilityStatus.COVERED if justifying else TraceabilityStatus.ORPHAN_BACKWARD,
                )
            )

        orphan_scenarios = [f.scenario_id for f in forward if f.status == TraceabilityStatus.ORPHAN_FORWARD]
        orphan_tests = [b.test_name for b in backward if b.status == TraceabilityStatus.ORPHAN_BACKWARD]

        req_cov = (
            (len(forward) - len(orphan_scenarios)) / len(forward) * 100
            if forward else 0.0
        )
        test_just = (
            (len(backward) - len(orphan_tests)) / len(backward) * 100
            if backward else 0.0
        )

        return TraceabilityMatrix(
            forward=forward,
            backward=backward,
            requirements_coverage_pct=round(req_cov, 1),
            tests_justified_pct=round(test_just, 1),
            orphan_scenarios=orphan_scenarios,
            orphan_tests=orphan_tests,
            cmmi_l3_compliant=(not orphan_scenarios and not orphan_tests),
        )

    # ── Medición de cobertura ─────────────────────────────────────────────────

    def _measure_coverage(self, result: CodeGenerationResult) -> CoverageReport:
        """Escribe código + tests a tempdir, ejecuta pytest --cov-branch, parsea resultado."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            code_dir = tmp / "src"
            code_dir.mkdir()
            test_dir = tmp / "tests"
            test_dir.mkdir()

            # Volcar módulos
            for mod in result.generated_code:
                (code_dir / mod.filename).write_text(mod.source_code, encoding="utf-8")

            # conftest.py para registrar el marker personalizado
            (test_dir / "conftest.py").write_text(
                "import pytest\n\n"
                "def pytest_configure(config):\n"
                "    config.addinivalue_line('markers', 'scenario(id): CMMI L3 traceability')\n",
                encoding="utf-8",
            )

            # Volcar tests (ajustar imports para apuntar a src/)
            for test in result.generated_tests:
                src = test.source_code.replace(
                    "from src.", "from src."
                )
                (test_dir / test.test_name).write_text(src, encoding="utf-8")

            cov_json = tmp / "coverage.json"
            try:
                subprocess.run(
                    [
                        sys.executable, "-m", "pytest",
                        str(test_dir),
                        f"--cov={code_dir}",
                        "--cov-branch",
                        f"--cov-report=json:{cov_json}",
                        "-q", "--tb=no", "--no-header",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=str(tmp),
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return CoverageReport()

            if not cov_json.exists():
                return CoverageReport()

            return self._parse_coverage_json(cov_json, result)

    def _parse_coverage_json(
        self, cov_json: Path, result: CodeGenerationResult
    ) -> CoverageReport:
        try:
            data = json.loads(cov_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return CoverageReport()

        totals = data.get("totals", {})
        covered_branches = totals.get("covered_branches", 0)
        num_branches = totals.get("num_branches", 0)
        covered_lines = totals.get("covered_lines", 0)
        num_statements = totals.get("num_statements", 1)  # evitar /0

        branch_pct = (covered_branches / num_branches * 100) if num_branches else 0.0
        line_pct = (covered_lines / num_statements * 100) if num_statements else 0.0

        # Módulos sin cobertura
        generated_names = {m.filename for m in result.generated_code}
        uncovered = [
            Path(fname).name
            for fname, fdata in data.get("files", {}).items()
            if Path(fname).name in generated_names
            and fdata.get("summary", {}).get("percent_covered", 100) < 1.0
        ]

        return CoverageReport(
            branch_coverage_pct=round(branch_pct, 1),
            line_coverage_pct=round(line_pct, 1),
            meets_threshold=branch_pct >= _BRANCH_THRESHOLD,
            uncovered_modules=uncovered,
        )
