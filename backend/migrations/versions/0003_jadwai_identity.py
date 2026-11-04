"""Rename only the original synthetic administrator email for the JadwAI brand."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade():
    op.execute(
        sa.text(
            "UPDATE app_user SET email='admin@jadwai.local' WHERE email='admin@mizan.local' AND NOT EXISTS (SELECT 1 FROM app_user WHERE email='admin@jadwai.local')"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE app_user SET email='admin@mizan.local' WHERE email='admin@jadwai.local' AND NOT EXISTS (SELECT 1 FROM app_user WHERE email='admin@mizan.local')"
        )
    )
