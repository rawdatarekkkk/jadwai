"""Preserve imported teaching timetable blocks separately from validated activities."""
from alembic import op
import sqlalchemy as sa
revision='0022'
down_revision='0021'
def upgrade():
    op.create_table('source_timetable',sa.Column('id',sa.String(36),primary_key=True),sa.Column('source_sha256',sa.String(64),nullable=False,unique=True),sa.Column('source_document',sa.String(200),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM source_timetable')).scalar():raise RuntimeError('Preserve source timetables before downgrading')
    op.drop_table('source_timetable')
