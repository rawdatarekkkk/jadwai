"""Typed mandatory activity and group permitted windows."""
from alembic import op
import sqlalchemy as sa
revision='0015'
down_revision='0014'
TARGET="((type IN ('unavailable','preferred_period') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type='room_unavailable' AND room_id IS NOT NULL AND instructor_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type IN ('group_unavailable','group_allowed') AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND activity_id IS NULL) OR (type='activity_allowed' AND activity_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL))"
STRENGTH="type IN ('unavailable','preferred_period','room_unavailable','group_unavailable','group_allowed','activity_allowed') AND ((type!='preferred_period' AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))"

def upgrade():
    op.add_column('rule',sa.Column('activity_id',sa.String(36),sa.ForeignKey('teaching_activity.id'),nullable=True))
    for key in ('rule_target','rule_strength'):op.drop_constraint(key,'rule',type_='check')
    op.create_check_constraint('rule_target','rule',TARGET)
    op.create_check_constraint('rule_strength','rule',STRENGTH)

def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM rule WHERE type IN ('group_allowed','activity_allowed')")).scalar():raise RuntimeError('Remove permitted-window rules before downgrading')
    for key in ('rule_target','rule_strength'):op.drop_constraint(key,'rule',type_='check')
    op.drop_column('rule','activity_id')
    op.create_check_constraint('rule_target','rule',"((type IN ('unavailable','preferred_period') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL) OR (type='room_unavailable' AND room_id IS NOT NULL AND instructor_id IS NULL AND group_id IS NULL) OR (type='group_unavailable' AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL))")
    op.create_check_constraint('rule_strength','rule',"type IN ('unavailable','preferred_period','room_unavailable','group_unavailable') AND ((type!='preferred_period' AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))")
