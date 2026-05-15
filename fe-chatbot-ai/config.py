"""Constantes globales de la aplicación."""

import os

from dotenv import load_dotenv

load_dotenv()

BACKEND: str = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")
PIPELINE_ENDPOINT: str = f"{BACKEND}/pipeline/run"
