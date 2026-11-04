"""Student accounts linked to a group."""
from alembic import op
import sqlalchemy as sa
revision = "0010"
down_revision = "0009"
def upgrade():
    op.drop_constraint("valid_user_role", "app_user", type_="check")
    op.create_check_constraint("valid_user_role", "app_user", "role IN ('administrator', 'viewer', 'student')")
    op.add_column("app_user", sa.Column("group_id", sa.String(36), sa.ForeignKey("record.id"), nullable=True))
def downgrade():
    op.execute("UPDATE app_user SET role='viewer' WHERE role='student'")
    op.drop_column("app_user", "group_id")
    op.drop_constraint("valid_user_role", "app_user", type_="check")
    op.create_check_constraint("valid_user_role", "app_user", "role IN ('administrator', 'viewer')")
