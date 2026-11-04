"""Year → major → group classification, preserving group/activity identifiers."""
from uuid import uuid4
import sqlalchemy as sa
from alembic import op
revision='0008'
down_revision='0007'


def upgrade():
    op.add_column('student_group',sa.Column('year',sa.Integer(),nullable=True))
    op.add_column('student_group',sa.Column('major',sa.String(100),nullable=True))
    op.create_check_constraint('group_year','student_group','year IS NULL OR year BETWEEN 1 AND 12')
    op.create_check_constraint('group_major','student_group',"major IS NULL OR length(trim(major)) > 0")
    # Only recover explicit year labels; unknown institutional majors stay null.
    op.execute("""UPDATE student_group g SET year = substring(r.name from '(?i)year[[:space:]]+([0-9]{1,2})([^0-9]|$)')::integer FROM record r
        WHERE r.id=g.id AND substring(r.name from '(?i)year[[:space:]]+([0-9]{1,2})([^0-9]|$)')::integer BETWEEN 1 AND 12""")
    # This mapping applies solely to our explicitly labelled synthetic batch.
    op.execute("""UPDATE student_group g SET major = CASE ((right(r.code,2)::integer-1)%6)/2
        WHEN 0 THEN 'Computer Science' WHEN 1 THEN 'Software Engineering' ELSE 'Information Systems' END
        FROM record r WHERE r.id=g.id AND r.code ~ '^LOAD-G(0[1-9]|1[0-8])$' AND r.name LIKE '[Demo]%'""")
    op.execute('UPDATE workspace SET version=version+1 WHERE EXISTS (SELECT 1 FROM student_group WHERE year IS NOT NULL OR major IS NOT NULL)')
    op.get_bind().execute(sa.text("""INSERT INTO audit(id,action,actor,action_code,params,created_at,input_version)
        SELECT :id,'Added year and major classification for student groups','System','groups.hierarchy_added','{}',CURRENT_TIMESTAMP,version FROM workspace WHERE id=1 AND EXISTS (SELECT 1 FROM student_group WHERE year IS NOT NULL OR major IS NOT NULL)"""),{'id':str(uuid4())})


def downgrade():
    op.drop_constraint('group_major','student_group',type_='check')
    op.drop_constraint('group_year','student_group',type_='check')
    op.drop_column('student_group','major')
    op.drop_column('student_group','year')
