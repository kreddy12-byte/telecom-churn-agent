"""ORM models.

# ============================================================
# 4. MODELS
# ============================================================

Importing this package registers every table on ``Base.metadata``, which
Alembic (production) and ``create_all`` (development/tests) both rely on.
"""

from app.db.base import Base
from app.db.models.action import (
    ACTION_STATUSES,
    ALLOWED_TRANSITIONS,
    STATUS_APPROVED,
    STATUS_MODIFIED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUSES_REQUIRING_NOTE,
    Action,
)
from app.db.models.customer import FEATURE_COLUMN_MAP, ID_DATASET_COLUMN, Customer
from app.db.models.prediction import Prediction
from app.db.models.user import AppUser

__all__ = [
    "ACTION_STATUSES",
    "ALLOWED_TRANSITIONS",
    "Action",
    "AppUser",
    "Base",
    "Customer",
    "FEATURE_COLUMN_MAP",
    "ID_DATASET_COLUMN",
    "Prediction",
    "STATUSES_REQUIRING_NOTE",
    "STATUS_APPROVED",
    "STATUS_MODIFIED",
    "STATUS_PENDING",
    "STATUS_REJECTED",
]
