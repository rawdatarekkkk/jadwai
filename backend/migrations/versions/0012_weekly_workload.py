"""Configurable weekly instructor maxima in exact teaching minutes."""
from alembic import op
import sqlalchemy as sa
revision='0012'
down_revision='0011'

def upgrade():
    op.add_column('instructor',sa.Column('max_weekly_minutes',sa.Integer(),nullable=True))
    op.create_check_constraint('weekly_limit_minutes','instructor','max_weekly_minutes IS NULL OR (max_weekly_minutes BETWEEN 0 AND 10080 AND max_weekly_minutes % 30 = 0)')

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM instructor WHERE max_weekly_minutes IS NOT NULL')).scalar():
        raise RuntimeError('Clear weekly maxima explicitly before downgrading')
    op.drop_constraint('weekly_limit_minutes','instructor',type_='check')
    op.drop_column('instructor','max_weekly_minutes')
