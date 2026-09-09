"""Customer table — the persisted form of the Telco customer record.

Every column here is a feature the trained model actually consumes (plus the
identifier and audit timestamps). Nothing extra is invented: a column the model
never sees would be dead weight that still has to be seeded, validated, and
migrated.

Column names are snake_case to match SQL convention, while the model expects the
dataset's original names (``MonthlyCharges``, ``tenure``, ...). That translation
happens in exactly one place — :data:`FEATURE_COLUMN_MAP` below — so the seed
script, the prediction service, the explanation service, and the what-if service
all speak to the model through the same mapping.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# =========================================================
# 1. DB COLUMN  <->  MODEL FEATURE MAPPING
# =========================================================

# (ORM attribute, dataset/model column). The model's feature names are fixed by
# the artifacts trained in Step 2, so this table adapts to them — never the
# other way round.
FEATURE_COLUMN_MAP: tuple[tuple[str, str], ...] = (
    ("gender", "gender"),
    ("senior_citizen", "SeniorCitizen"),
    ("partner", "Partner"),
    ("dependents", "Dependents"),
    ("tenure", "tenure"),
    ("phone_service", "PhoneService"),
    ("multiple_lines", "MultipleLines"),
    ("internet_service", "InternetService"),
    ("online_security", "OnlineSecurity"),
    ("online_backup", "OnlineBackup"),
    ("device_protection", "DeviceProtection"),
    ("tech_support", "TechSupport"),
    ("streaming_tv", "StreamingTV"),
    ("streaming_movies", "StreamingMovies"),
    ("contract", "Contract"),
    ("paperless_billing", "PaperlessBilling"),
    ("payment_method", "PaymentMethod"),
    ("monthly_charges", "MonthlyCharges"),
    ("total_charges", "TotalCharges"),
)

ID_DATASET_COLUMN = "customerID"


# =========================================================
# 2. CUSTOMER TABLE
# =========================================================


class Customer(Base):
    """A telecom customer, stored in the schema the churn model was trained on."""

    __tablename__ = "customers"

    # The dataset's own identifier is the natural key. Using it as the primary
    # key is what makes the seed idempotent without a lookup table.
    customer_id: Mapped[str] = mapped_column(String(32), primary_key=True)

    # --- Demographics ---
    gender: Mapped[str | None] = mapped_column(String(16))
    senior_citizen: Mapped[int | None] = mapped_column(Integer)
    partner: Mapped[str | None] = mapped_column(String(8))
    dependents: Mapped[str | None] = mapped_column(String(8))

    # --- Account ---
    tenure: Mapped[int | None] = mapped_column(Integer)
    contract: Mapped[str | None] = mapped_column(String(32))
    paperless_billing: Mapped[str | None] = mapped_column(String(8))
    payment_method: Mapped[str | None] = mapped_column(String(64))

    # --- Services ---
    phone_service: Mapped[str | None] = mapped_column(String(8))
    multiple_lines: Mapped[str | None] = mapped_column(String(32))
    internet_service: Mapped[str | None] = mapped_column(String(32))
    online_security: Mapped[str | None] = mapped_column(String(32))
    online_backup: Mapped[str | None] = mapped_column(String(32))
    device_protection: Mapped[str | None] = mapped_column(String(32))
    tech_support: Mapped[str | None] = mapped_column(String(32))
    streaming_tv: Mapped[str | None] = mapped_column(String(32))
    streaming_movies: Mapped[str | None] = mapped_column(String(32))

    # --- Charges ---
    # TotalCharges is blank for 11 customers in the raw dataset (new accounts),
    # so it is nullable; the ML pipeline already imputes missing values.
    monthly_charges: Mapped[float | None] = mapped_column(Float)
    total_charges: Mapped[float | None] = mapped_column(Float)

    # --- Audit ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Default lazy loading: list endpoints fetch the latest prediction with a
    # dedicated query rather than hydrating every historical row.
    predictions: Mapped[list["Prediction"]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )
    actions: Mapped[list["Action"]] = relationship(  # noqa: F821
        back_populates="customer", cascade="all, delete-orphan"
    )

    # =========================================================
    # 3. TRANSLATION TO / FROM THE MODEL'S FEATURE SCHEMA
    # =========================================================

    def to_model_record(self) -> dict[str, Any]:
        """Project this row into the record shape the ML pipeline expects.

        The identifier is included because the SHAP explainer echoes it back as
        ``customer_id``; the predictor ignores non-feature columns.
        """
        record: dict[str, Any] = {ID_DATASET_COLUMN: self.customer_id}
        for attribute, dataset_column in FEATURE_COLUMN_MAP:
            record[dataset_column] = getattr(self, attribute)
        return record

    @classmethod
    def field_values_from_dataset_record(
        cls, record: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Map a raw dataset row onto ORM attribute values (no instance created).

        Returned separately from :meth:`from_dataset_record` so the seed can use
        it to *update* an existing row without constructing a throwaway object.
        """
        return {
            attribute: record.get(dataset_column)
            for attribute, dataset_column in FEATURE_COLUMN_MAP
        }

    @classmethod
    def from_dataset_record(cls, record: Mapping[str, Any]) -> "Customer":
        """Build a Customer from a raw dataset row."""
        customer_id = str(record[ID_DATASET_COLUMN]).strip()
        return cls(customer_id=customer_id, **cls.field_values_from_dataset_record(record))
