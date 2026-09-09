"""SQLAlchemy declarative base.

Kept separate from :mod:`app.db.session` so ORM models can import ``Base``
without pulling in the engine — that is what lets the test suite bind the same
models to a different database.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""
