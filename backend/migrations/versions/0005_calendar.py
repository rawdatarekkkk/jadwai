"""Versioned institutional semester/calendar configuration."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"


def upgrade():
    for column in [
        sa.Column(
            "timezone", sa.String(100), nullable=False, server_default="Africa/Cairo"
        ),
        sa.Column(
            "days",
            sa.JSON(),
            nullable=False,
            server_default='["Sunday","Monday","Tuesday","Wednesday","Thursday"]',
        ),
        sa.Column("start_hour", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("end_hour", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("period_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
    ]:
        op.add_column("workspace", column)
    op.create_check_constraint(
        "calendar_hours",
        "workspace",
        "start_hour >= 0 AND end_hour <= 24 AND start_hour < end_hour",
    )
    op.create_check_constraint(
        "calendar_period", "workspace", "period_minutes IN (30,60)"
    )
    op.create_check_constraint(
        "calendar_dates",
        "workspace",
        "start_date IS NULL OR end_date IS NULL OR start_date <= end_date",
    )


def downgrade():
    for name in ["calendar_dates", "calendar_period", "calendar_hours"]:
        op.drop_constraint(name, "workspace", type_="check")
    for name in [
        "end_date",
        "start_date",
        "period_minutes",
        "end_hour",
        "start_hour",
        "days",
        "timezone",
    ]:
        op.drop_column("workspace", name)
