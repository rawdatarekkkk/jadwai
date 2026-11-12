"""Special rooms: who may use a room (programmes and/or catalogue courses); empty means everyone."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
revision = '0031'
down_revision = '0030'

def upgrade():
    op.add_column('room', sa.Column('reserved_majors', ARRAY(sa.String(100)), nullable=False, server_default='{}'))
    op.add_column('room', sa.Column('reserved_course_ids', ARRAY(sa.String(36)), nullable=False, server_default='{}'))

def downgrade():
    op.drop_column('room', 'reserved_course_ids')
    op.drop_column('room', 'reserved_majors')
