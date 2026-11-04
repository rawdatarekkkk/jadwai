"""Multiple room uses, preserving each existing room's type."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '0016'
down_revision = '0015'

def upgrade():
    op.add_column('room', sa.Column('room_types', postgresql.ARRAY(sa.String(20)), nullable=True))
    op.execute('UPDATE room SET room_types = ARRAY[room_type]')
    op.execute('SET CONSTRAINTS ALL IMMEDIATE')
    op.alter_column('room', 'room_types', nullable=False)
    op.drop_constraint('room_room_type_check', 'room', type_='check')
    op.create_check_constraint('room_type', 'room', "room_type IN ('lecture','lab','flexible','exam_hall')")
    op.create_check_constraint('room_types_valid', 'room', "cardinality(room_types) BETWEEN 1 AND 4 AND room_types <@ ARRAY['lecture','lab','flexible','exam_hall']::varchar[] AND array_position(room_types, NULL) IS NULL")

def downgrade():
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM room WHERE cardinality(room_types) != 1 OR room_types[1] = 'exam_hall'")).scalar()
    if count:
        raise RuntimeError('Remove multiple/exam-hall room uses before downgrading')
    op.drop_constraint('room_types_valid', 'room', type_='check')
    op.drop_constraint('room_type', 'room', type_='check')
    op.drop_column('room', 'room_types')
    op.create_check_constraint('room_room_type_check', 'room', "room_type IN ('lecture','lab','flexible')")
