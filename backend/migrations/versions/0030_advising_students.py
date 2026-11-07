"""Advising (irregular) students: personal course changes against their home group."""
from alembic import op
import sqlalchemy as sa
revision = '0030'
down_revision = '0029'

def upgrade():
    op.create_table('advising_student',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('code', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('group_id', sa.String(36), sa.ForeignKey('student_group.id', ondelete='SET NULL'), nullable=True))
    op.create_index('advising_student_code_ci', 'advising_student', [sa.text('lower(code)')], unique=True)
    op.create_table('advising_change',
        sa.Column('student_id', sa.String(36), sa.ForeignKey('advising_student.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('course_id', sa.String(36), sa.ForeignKey('course_catalog.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('action', sa.String(10), primary_key=True),
        sa.Column('group_id', sa.String(36), sa.ForeignKey('student_group.id', ondelete='CASCADE'), nullable=True),
        sa.CheckConstraint("(action = 'drop' AND group_id IS NULL) OR (action = 'add' AND group_id IS NOT NULL)", name='advising_change_shape'))
    op.add_column('app_user', sa.Column('advising_student_id', sa.String(36), sa.ForeignKey('advising_student.id', ondelete='SET NULL'), nullable=True))

def downgrade():
    op.drop_column('app_user', 'advising_student_id')
    op.drop_table('advising_change')
    op.drop_index('advising_student_code_ci', table_name='advising_student')
    op.drop_table('advising_student')
