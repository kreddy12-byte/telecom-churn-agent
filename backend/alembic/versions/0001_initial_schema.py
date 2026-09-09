"""Initial production schema: customers, predictions, actions, app_users.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("gender", sa.String(length=16), nullable=True),
        sa.Column("senior_citizen", sa.Integer(), nullable=True),
        sa.Column("partner", sa.String(length=8), nullable=True),
        sa.Column("dependents", sa.String(length=8), nullable=True),
        sa.Column("tenure", sa.Integer(), nullable=True),
        sa.Column("contract", sa.String(length=32), nullable=True),
        sa.Column("paperless_billing", sa.String(length=8), nullable=True),
        sa.Column("payment_method", sa.String(length=64), nullable=True),
        sa.Column("phone_service", sa.String(length=8), nullable=True),
        sa.Column("multiple_lines", sa.String(length=32), nullable=True),
        sa.Column("internet_service", sa.String(length=32), nullable=True),
        sa.Column("online_security", sa.String(length=32), nullable=True),
        sa.Column("online_backup", sa.String(length=32), nullable=True),
        sa.Column("device_protection", sa.String(length=32), nullable=True),
        sa.Column("tech_support", sa.String(length=32), nullable=True),
        sa.Column("streaming_tv", sa.String(length=32), nullable=True),
        sa.Column("streaming_movies", sa.String(length=32), nullable=True),
        sa.Column("monthly_charges", sa.Float(), nullable=True),
        sa.Column("total_charges", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("customer_id"),
    )

    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("auth0_sub", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("picture_url", sa.String(length=512), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_users_auth0_sub", "app_users", ["auth0_sub"], unique=True)

    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("churn_probability", sa.Float(), nullable=False),
        sa.Column("risk_level", sa.String(length=16), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "risk_level IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_predictions_risk_level",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.customer_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_predictions_customer_created",
        "predictions",
        ["customer_id", "created_at"],
    )
    op.create_index(
        "ix_predictions_customer_id",
        "predictions",
        ["customer_id", "id"],
    )

    op.create_table(
        "actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.String(length=32), nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_sub", sa.String(length=128), nullable=True),
        sa.Column("reviewed_by_email", sa.String(length=255), nullable=True),
        sa.Column("reviewed_by_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'MODIFIED', 'REJECTED')",
            name="ck_actions_status",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.customer_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_actions_customer_status",
        "actions",
        ["customer_id", "status"],
    )
    op.create_index("ix_actions_status", "actions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_actions_status", table_name="actions")
    op.drop_index("ix_actions_customer_status", table_name="actions")
    op.drop_table("actions")
    op.drop_index("ix_predictions_customer_id", table_name="predictions")
    op.drop_index("ix_predictions_customer_created", table_name="predictions")
    op.drop_table("predictions")
    op.drop_index("ix_app_users_auth0_sub", table_name="app_users")
    op.drop_table("app_users")
    op.drop_table("customers")
