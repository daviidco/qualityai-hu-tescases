"""Extracción de texto desde archivos de requerimientos (.txt, .pdf, .docx)."""

from __future__ import annotations

import io
from pathlib import Path


ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def validate_extension(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Formato '{suffix}' no soportado. Solo se aceptan: .txt, .pdf, .docx"
        )


def extract_text(file_bytes: bytes, filename: str) -> str:
    validate_extension(filename)
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        return _from_txt(file_bytes)
    if suffix == ".pdf":
        return _from_pdf(file_bytes)
    return _from_docx(file_bytes)


def _from_txt(data: bytes) -> str:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return data.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace").strip()


def _from_pdf(data: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    if not pages:
        raise ValueError(
            "No se pudo extraer texto del PDF. "
            "El archivo puede estar escaneado o protegido."
        )
    return "\n\n".join(pages)


def _from_docx(data: bytes) -> str:
    import docx

    doc = docx.Document(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        raise ValueError("El archivo .docx no contiene párrafos de texto.")
    return "\n\n".join(paragraphs)
