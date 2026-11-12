"""Each course's exam plan: number of quizzes (default 3) and whether it has a second-chance midterm."""
from alembic import op
import sqlalchemy as sa
revision = '0032'
down_revision = '0031'

def upgrade():
    op.add_column('course_catalog', sa.Column('quiz_count', sa.SmallInteger(), nullable=False, server_default='3'))
    op.add_column('course_catalog', sa.Column('second_chance', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_check_constraint('course_quiz_count', 'course_catalog', 'quiz_count BETWEEN 0 AND 10')

def downgrade():
    op.drop_constraint('course_quiz_count', 'course_catalog')
    op.drop_column('course_catalog', 'second_chance')
    op.drop_column('course_catalog', 'quiz_count')
