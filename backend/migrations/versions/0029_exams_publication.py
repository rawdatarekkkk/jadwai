"""Exam halls inputs, configurable cohort lists, scenario names and publication."""
from alembic import op
import sqlalchemy as sa
revision = '0029'
down_revision = '0028'

def upgrade():
    op.add_column('course_catalog', sa.Column('expected_students', sa.Integer(), nullable=True))
    op.create_check_constraint('course_expected_students', 'course_catalog', 'expected_students IS NULL OR expected_students BETWEEN 1 AND 5000')
    op.add_column('workspace', sa.Column('exam_cohort_rules', sa.JSON(), nullable=True))
    for table in ('schedule_run', 'exam_run'):
        op.add_column(table, sa.Column('name', sa.String(100), nullable=True))
        op.add_column(table, sa.Column('parent_run_id', sa.String(36), sa.ForeignKey(table + '.id'), nullable=True))
        op.add_column(table, sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))
        # At most one published timetable of each kind.
        op.create_index(table + '_one_published', table, [sa.text('(published_at IS NOT NULL)')], unique=True, postgresql_where=sa.text('published_at IS NOT NULL'))

def downgrade():
    for table in ('schedule_run', 'exam_run'):
        op.drop_index(table + '_one_published', table_name=table)
        for column in ('published_at', 'parent_run_id', 'name'):
            op.drop_column(table, column)
    op.drop_column('workspace', 'exam_cohort_rules')
    op.drop_constraint('course_expected_students', 'course_catalog', type_='check')
    op.drop_column('course_catalog', 'expected_students')
