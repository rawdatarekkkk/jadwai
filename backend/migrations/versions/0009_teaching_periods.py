"""Versioned named teaching periods, with breaks excluded from placement."""
import sqlalchemy as sa
from alembic import op
revision='0009'
down_revision='0008'

def upgrade():
    op.add_column('workspace',sa.Column('teaching_periods',sa.JSON(),nullable=False,server_default='[]'))

def downgrade():
    op.drop_column('workspace','teaching_periods')
