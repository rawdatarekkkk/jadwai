"""Shared parent courses and teaching-component eligibility."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa
revision = '0018'
down_revision = '0017'

def upgrade():
    table = op.create_table('course_catalog',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('eligibility', sa.JSON(), nullable=False),
        sa.Column('group_ids', sa.JSON(), nullable=False))
    op.create_index('course_catalog_code_ci', 'course_catalog', [sa.text('lower(code)')], unique=True)
    op.add_column('teaching_activity', sa.Column('course_id', sa.String(36), sa.ForeignKey('course_catalog.id'), nullable=True))
    conn = op.get_bind()
    records = conn.execute(sa.text("SELECT r.id, r.name, r.code, a.activity_type FROM record r JOIN teaching_activity a ON a.id=r.id ORDER BY r.id")).mappings().all()
    courses = {}
    for row in records:
        key = row['name'].strip().casefold()
        course = courses.setdefault(key, dict(id=str(uuid4()), name=row['name'], code=row['code'], eligibility={'lecture': [], 'tutorial': [], 'lab': []}, group_ids=[], activities=[]))
        teachers = conn.execute(sa.text('SELECT instructor_id FROM activity_instructor WHERE activity_id=:id'), {'id': row['id']}).scalars().all()
        groups = conn.execute(sa.text('SELECT group_id FROM activity_group WHERE activity_id=:id'), {'id': row['id']}).scalars().all()
        course['eligibility'][row['activity_type']] = sorted(set(course['eligibility'][row['activity_type']] + teachers))
        course['group_ids'] = sorted(set(course['group_ids'] + groups))
        course['activities'].append(row['id'])
    for course in courses.values():
        activities = course.pop('activities')
        conn.execute(table.insert().values(**course))
        for ident in activities:
            conn.execute(sa.text('UPDATE teaching_activity SET course_id=:course WHERE id=:id'), {'course':course['id'], 'id':ident})
    op.execute('SET CONSTRAINTS ALL IMMEDIATE')

def downgrade():
    op.drop_column('teaching_activity', 'course_id')
    op.drop_table('course_catalog')
