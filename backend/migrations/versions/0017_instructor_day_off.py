"""Instructor weekly day off. Existing instructors remain unspecified."""
from alembic import op
import sqlalchemy as sa
revision = '0017'
down_revision = '0016'

def upgrade():
    op.add_column('instructor', sa.Column('day_off', sa.String(10), nullable=True))
    op.create_check_constraint('instructor_day_off', 'instructor', "day_off IS NULL OR day_off IN ('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')")

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM instructor WHERE day_off IS NOT NULL')).scalar():
        raise RuntimeError('Clear instructor days off before downgrading')
    op.drop_constraint('instructor_day_off', 'instructor', type_='check')
    op.drop_column('instructor', 'day_off')
