"""Persist immutable scheduling snapshots and recoverable worker jobs."""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


def upgrade():
    op.create_table("schedule_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspace.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("input_version", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(36), unique=True, nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('queued','running','completed','blocked','infeasible','unknown','failed','cancelled')", name="schedule_status"))
    op.create_index("one_active_schedule", "schedule_run", ["workspace_id"], unique=True, postgresql_where=sa.text("status IN ('queued','running')"))
    op.execute("""CREATE FUNCTION protect_schedule_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF NEW.snapshot::jsonb IS DISTINCT FROM OLD.snapshot::jsonb OR NEW.input_version <> OLD.input_version OR NEW.request_key <> OLD.request_key OR NEW.created_by <> OLD.created_by OR NEW.workspace_id <> OLD.workspace_id OR NEW.created_at <> OLD.created_at THEN
            RAISE EXCEPTION 'schedule snapshot is immutable';
        END IF; RETURN NEW; END $$""")
    op.execute("CREATE TRIGGER immutable_schedule_snapshot BEFORE UPDATE ON schedule_run FOR EACH ROW EXECUTE FUNCTION protect_schedule_snapshot()")


def downgrade():
    op.drop_table("schedule_run")
    op.execute("DROP FUNCTION protect_schedule_snapshot()")
