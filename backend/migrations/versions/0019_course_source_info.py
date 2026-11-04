"""Course source metadata only; no exam schedules."""
from alembic import op
import sqlalchemy as sa
revision='0019'
down_revision='0018'

def upgrade():
    op.add_column('course_catalog',sa.Column('source_info',sa.JSON(),nullable=False,server_default=sa.text("'{}'")))

def downgrade():
    op.drop_column('course_catalog','source_info')
