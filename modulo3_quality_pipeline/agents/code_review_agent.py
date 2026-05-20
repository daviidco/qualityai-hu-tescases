"""CodeReviewAgent v4 — HITL: revisión de código por senior developer.

No extiende AbstractBaseAgent (sin LLM ni RAG).
Implementa el flujo interactivo de revisión de código generado (Stage 6).
Solo se ejecuta en modo interactive=True. En modo --auto se salta.

Pipeline de Stage 6:
  1. Muestra resumen del CodeGenerationResult (módulos, métricas, cobertura)
  2. Para cada GeneratedCodeModule: presenta source_code y pide acción
     [a]probar | [c]omentar (code smell) | [s]altar
  3. Registra cada decisión en CodeReviewMetadata.change_history (audit trail CMMI L3)
  4. Pide veredicto final: aprobar | rechazar | cambios
  5. Aplica veredicto → CodeReviewStatus
"""
from __future__ import annotations

from datetime import datetime

from ..contracts.contract_d import (
    CodeGenerationResult,
    CodeReviewChange,
    CodeReviewMetadata,
    CodeReviewStatus,
)

_ACTIONS = {
    "a": "approved",
    "c": "comment_added",
    "s": None,  # skip — no registra
}

_VERDICTS = {
    "aprobar": CodeReviewStatus.APPROVED,
    "rechazar": CodeReviewStatus.REJECTED,
    "cambios": CodeReviewStatus.NEEDS_CHANGES,
}


class CodeReviewAgent:
    """Stage 6 (HITL): senior developer revisa el código generado de forma interactiva."""

    def review(
        self,
        result: CodeGenerationResult,
        reviewer_name: str,
        auto: bool = False,
    ) -> CodeGenerationResult:
        """Conduce la revisión interactiva y actualiza el CodeReviewMetadata.

        Args:
            result: CodeGenerationResult con el código generado.
            reviewer_name: Nombre del revisor humano.
            auto: Si True, auto-aprueba sin interacción (modo headless/web).
        """
        if not result.generated_code:
            print("  [CodeReviewAgent] Sin módulos que revisar.")
            return result

        if auto:
            return self._auto_review(result, reviewer_name)

        print("\n" + "=" * 60)
        print("👨‍💻 STAGE 6: Revisión de Código — Senior Developer")
        print("=" * 60)
        self._mostrar_resumen(result)

        changes: list[CodeReviewChange] = []

        for i, module in enumerate(result.generated_code, 1):
            print(f"\n── Módulo {i}/{len(result.generated_code)}: {module.filename} ──")
            print(f"  Descripción: {module.description}")
            print(f"  Historia: {module.user_story_id}")
            print("\n--- SOURCE CODE ---")
            print(module.source_code)
            print("-------------------")

            # Buscar test asociado
            test = next(
                (t for t in result.generated_tests if t.target_module == module.filename),
                None,
            )
            if test:
                print(f"\n--- TEST: {test.test_name} ---")
                print(test.source_code)
                print("-" * 25)

            action = self._prompt_action(module.filename)
            if action is None:  # skip
                continue

            notes = ""
            if action == "comment_added":
                smell = self._prompt_smell()
                notes = smell

            changes.append(
                CodeReviewChange(
                    reviewer=reviewer_name,
                    action=action,
                    target=module.filename,
                    notes=notes or None,
                )
            )

        # Veredicto final
        verdict_status, feedback = self._prompt_verdict()

        review = CodeReviewMetadata(
            review_status=verdict_status,
            version=1,
            approved_by=reviewer_name if verdict_status == CodeReviewStatus.APPROVED else None,
            approved_at=datetime.now() if verdict_status == CodeReviewStatus.APPROVED else None,
            reviewer_feedback=feedback or None,
            change_history=changes,
        )
        if verdict_status == CodeReviewStatus.NEEDS_CHANGES:
            review.version = 2

        result.review = review
        print(f"\n  ✅ Revisión registrada: {verdict_status.value} por {reviewer_name}")
        return result

    def _auto_review(
        self,
        result: CodeGenerationResult,
        reviewer_name: str,
    ) -> CodeGenerationResult:
        """Auto-aprueba todos los módulos sin interacción (modo web/headless)."""
        changes: list[CodeReviewChange] = []
        for module in result.generated_code:
            changes.append(
                CodeReviewChange(
                    reviewer=reviewer_name,
                    action="approved",
                    target=module.filename,
                    notes="Auto-aprobado (modo web)",
                )
            )

        result.review = CodeReviewMetadata(
            review_status=CodeReviewStatus.APPROVED,
            version=1,
            approved_by=reviewer_name,
            approved_at=datetime.now(),
            reviewer_feedback="Auto-aprobado — pendiente de revisión HITL en frontend.",
            change_history=changes,
        )
        print(f"  ✅ Revisión auto-aprobada ({len(changes)} módulos) por {reviewer_name}")
        return result

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _mostrar_resumen(self, result: CodeGenerationResult) -> None:
        print(f"\n  Módulos generados : {result.total_modules}")
        print(f"  Tests generados   : {result.total_tests}")
        if result.quality_report:
            qr = result.quality_report
            print(f"  Funciones > umbral: {qr.functions_exceeding_threshold}")
            print(f"  Hallazgos seguridad: {len(qr.security_findings)}")
            if qr.maintainability_index is not None:
                print(f"  Índice MI         : {qr.maintainability_index:.1f}/100")
        if result.traceability_matrix:
            tm = result.traceability_matrix
            print(f"  Cobertura reqs    : {tm.requirements_coverage_pct:.0f}%")
            print(f"  CMMI L3           : {'✓' if tm.cmmi_l3_compliant else '✗'}")
        if result.coverage_report:
            cr = result.coverage_report
            print(f"  Branch coverage   : {cr.branch_coverage_pct:.0f}%")

    def _prompt_action(self, filename: str) -> str | None:
        while True:
            try:
                raw = input(
                    f"\n  [{filename}] Acción: [a]probar | [c]omentar (smell) | [s]altar → "
                ).strip().lower()
            except EOFError:
                return "approved"
            if raw in _ACTIONS:
                return _ACTIONS[raw]
            print("  Opción inválida. Usa: a, c o s")

    def _prompt_smell(self) -> str:
        print("  Tipos de smell: naming | design_intent | coupling | abstraction | correctness")
        try:
            smell_type = input("  Tipo de smell → ").strip() or "general"
            notes = input("  Nota del revisor → ").strip()
        except EOFError:
            return ""
        return f"[{smell_type}] {notes}".strip()

    def _prompt_verdict(self) -> tuple[CodeReviewStatus, str]:
        print("\n" + "─" * 40)
        while True:
            try:
                raw = input(
                    "  Veredicto final [aprobar | rechazar | cambios] → "
                ).strip().lower()
            except EOFError:
                raw = "aprobar"
            if raw in _VERDICTS:
                break
            print("  Opciones válidas: aprobar, rechazar, cambios")

        try:
            feedback = input("  Feedback general (opcional, Enter para omitir) → ").strip()
        except EOFError:
            feedback = ""

        return _VERDICTS[raw], feedback
