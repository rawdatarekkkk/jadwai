"""Store source room identities before capacity/type confirmation."""
from alembic import op
import sqlalchemy as sa
revision='0020'
down_revision='0019'

def upgrade():
    op.add_column('room',sa.Column('source_info',sa.JSON(),nullable=False,server_default=sa.text("'{}'")))
    op.alter_column('room','capacity',nullable=True)
    op.alter_column('room','room_type',nullable=True)
    op.drop_constraint('room_types_valid','room',type_='check')
    op.create_check_constraint('room_types_valid','room',"cardinality(room_types) BETWEEN 0 AND 4 AND room_types <@ ARRAY['lecture','lab','flexible','exam_hall']::varchar[] AND array_position(room_types, NULL) IS NULL")

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM room WHERE capacity IS NULL OR room_type IS NULL OR cardinality(room_types)=0')).scalar():raise RuntimeError('Complete source room setup before downgrading')
    op.drop_constraint('room_types_valid','room',type_='check')
    op.create_check_constraint('room_types_valid','room',"cardinality(room_types) BETWEEN 1 AND 4 AND room_types <@ ARRAY['lecture','lab','flexible','exam_hall']::varchar[] AND array_position(room_types, NULL) IS NULL")
    op.alter_column('room','capacity',nullable=False)
    op.alter_column('room','room_type',nullable=False)
    op.drop_column('room','source_info')
