"""Dated exam draft runs, separate from weekly teaching schedules."""
from alembic import op
import sqlalchemy as sa
revision='0021'
down_revision='0020'
def upgrade():
    op.create_table('exam_run',sa.Column('id',sa.String(36),primary_key=True),sa.Column('input_version',sa.Integer(),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),sa.Column('result',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM exam_run')).scalar():raise RuntimeError('Preserve exam drafts before downgrading')
    op.drop_table('exam_run')
