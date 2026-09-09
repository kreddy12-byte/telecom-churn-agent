"""Make the sibling ``ml`` and ``agent`` packages importable from the backend.

The intelligence layers are top-level packages at the repository root, while the
backend runs with ``backend/`` as its working directory. Rather than mutating
``sys.path`` as an invisible import side effect, this exposes one explicit
function that the process entrypoints call — ``app.main`` for the API and each
CLI for scripts — so the behaviour is greppable and testable.

Setting ``PYTHONPATH`` to the repository root (as the Docker image does) makes
this a no-op.
"""

from __future__ import annotations

import sys
from pathlib import Path

# backend/app/core/project_path.py -> repository root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]


def ensure_project_root_on_path() -> Path:
    """Put the repository root on ``sys.path`` if it is not already there.

    Returns the resolved repository root, which callers use to locate shared
    assets such as the ML artifact directory.
    """
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT
