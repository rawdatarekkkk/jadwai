"""Account lifecycle, persisted throttling, structured append-only audit."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"


def upgrade():
    op.add_column(
        "app_user",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "app_user",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "audit",
        sa.Column(
            "action_code", sa.String(60), nullable=False, server_default="legacy"
        ),
    )
    op.add_column(
        "audit", sa.Column("params", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_table(
        "password_reset",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("app_user.id"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_reset_user_id", "password_reset", ["user_id"])
    op.create_table(
        "login_bucket",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    # Translate historical system messages without changing original record text.
    prefixes = {
        "Added ": "record.created",
        "Updated ": "record.updated",
        "Removed rule: ": "rule.deleted",
        "Removed ": "record.deleted",
        "Created rule: ": "rule.created",
        "Approve rule: ": "rule.approved",
        "Revoke rule: ": "rule.revoked",
    }
    for prefix, code in prefixes.items():
        op.execute(
            sa.text(
                "UPDATE audit SET action_code=:code,params=json_build_object('target',substring(action from :start)) WHERE action_code='legacy' AND left(action,:length)=:prefix"
            ).bindparams(
                code=code, start=len(prefix) + 1, length=len(prefix), prefix=prefix
            )
        )
    op.execute(
        "UPDATE audit SET action_code='workspace.created' WHERE action='Created workspace with synthetic starter data'"
    )
    op.execute(
        """CREATE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'audit_is_append_only' USING ERRCODE='42501'; END $$"""
    )
    op.execute(
        "CREATE TRIGGER audit_no_changes BEFORE UPDATE OR DELETE ON audit FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation()"
    )
    op.execute(
        "CREATE TRIGGER audit_no_truncate BEFORE TRUNCATE ON audit FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_mutation()"
    )


def downgrade():
    op.execute("DROP TRIGGER audit_no_truncate ON audit")
    op.execute("DROP TRIGGER audit_no_changes ON audit")
    op.execute("DROP FUNCTION reject_audit_mutation()")
    op.drop_table("login_bucket")
    op.drop_table("password_reset")
    op.drop_column("audit", "params")
    op.drop_column("audit", "action_code")
    op.drop_column("app_user", "version")
    op.drop_column("app_user", "active")
