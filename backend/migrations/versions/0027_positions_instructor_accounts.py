"""Doctor/TA positions and instructor accounts. Existing instructors remain unspecified."""
from alembic import op
import sqlalchemy as sa
revision = '0027'
down_revision = '0026'

def upgrade():
    op.add_column('instructor', sa.Column('position', sa.String(10), nullable=True))
    op.create_check_constraint('instructor_position', 'instructor', "position IS NULL OR position IN ('doctor','ta')")
    op.drop_constraint('valid_user_role', 'app_user', type_='check')
    op.create_check_constraint('valid_user_role', 'app_user', "role IN ('administrator', 'viewer', 'student', 'instructor')")
    op.add_column('app_user', sa.Column('instructor_id', sa.String(36), sa.ForeignKey('record.id'), nullable=True))

def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM app_user WHERE role='instructor'")).scalar():
        raise RuntimeError('Remove instructor accounts before downgrading')
    op.drop_column('app_user', 'instructor_id')
    op.drop_constraint('valid_user_role', 'app_user', type_='check')
    op.create_check_constraint('valid_user_role', 'app_user', "role IN ('administrator', 'viewer', 'student')")
    op.drop_constraint('instructor_position', 'instructor', type_='check')
    op.drop_column('instructor', 'position')
