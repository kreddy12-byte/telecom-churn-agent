"""Telecom Churn Agent backend application.

The backend imports the repository's sibling packages — ``ml`` (prediction and
SHAP) and ``agent`` (retention strategies and the what-if simulator) — which
live one directory above ``backend/``. Since the process runs with ``backend/``
as its working directory, the repository root is put on the import path here, at
the package boundary, so every entrypoint (uvicorn, the CLIs, pytest) gets it
without repeating the setup. Where ``PYTHONPATH`` already covers it, as in the
Docker image, this is a no-op.
"""

from app.core.project_path import ensure_project_root_on_path

ensure_project_root_on_path()
