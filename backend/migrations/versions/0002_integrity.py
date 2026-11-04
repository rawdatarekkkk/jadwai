"""Database integrity for accounts, sessions and supported record kinds."""

from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_check_constraint(
        "valid_user_role", "app_user", "role IN ('administrator', 'viewer')"
    )
    op.create_check_constraint(
        "valid_record_kind",
        "record",
        "kind IN ('courses', 'instructors', 'rooms', 'groups')",
    )
    op.create_check_constraint(
        "valid_rule_status", "rule", "status IN ('draft', 'approved')"
    )
    op.create_foreign_key("session_user_fk", "session", "app_user", ["user_id"], ["id"])
    op.create_foreign_key(
        "rule_approver_fk", "rule", "app_user", ["approved_by"], ["id"]
    )


def downgrade():
    op.drop_constraint("rule_approver_fk", "rule", type_="foreignkey")
    op.drop_constraint("session_user_fk", "session", type_="foreignkey")
    op.drop_constraint("valid_rule_status", "rule", type_="check")
    op.drop_constraint("valid_record_kind", "record", type_="check")
    op.drop_constraint("valid_user_role", "app_user", type_="check")
