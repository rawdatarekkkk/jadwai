"""Typed room and group unavailability rules."""
from alembic import op
import sqlalchemy as sa
revision='0011'
down_revision='0010'

def upgrade():
    op.alter_column('rule','instructor_id',nullable=True)
    op.add_column('rule',sa.Column('room_id',sa.String(36),sa.ForeignKey('room.id'),nullable=True))
    op.add_column('rule',sa.Column('group_id',sa.String(36),sa.ForeignKey('student_group.id'),nullable=True))
    op.drop_constraint('rule_strength','rule',type_='check')
    op.create_check_constraint('rule_strength','rule',"type IN ('unavailable','preferred_period','room_unavailable','group_unavailable') AND ((type IN ('unavailable','room_unavailable','group_unavailable') AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))")
    op.create_check_constraint('rule_target','rule',"((type IN ('unavailable','preferred_period') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL) OR (type='room_unavailable' AND room_id IS NOT NULL AND instructor_id IS NULL AND group_id IS NULL) OR (type='group_unavailable' AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL))")

def downgrade():
    # Refuse a lossy downgrade; never discard newly created academic rules.
    if op.get_bind().execute(sa.text("SELECT count(*) FROM rule WHERE type IN ('room_unavailable','group_unavailable')")).scalar():
        raise RuntimeError('Remove room/group rules explicitly before downgrading')
    op.drop_constraint('rule_target','rule',type_='check')
    op.drop_constraint('rule_strength','rule',type_='check')
    op.drop_column('rule','group_id')
    op.drop_column('rule','room_id')
    op.alter_column('rule','instructor_id',nullable=False)
    op.create_check_constraint('rule_strength','rule',"type IN ('unavailable','preferred_period') AND ((type='unavailable' AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))")
