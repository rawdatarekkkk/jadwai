"""Half-hour rule times, every-day rules and limit rules with parameters."""
from alembic import op
import sqlalchemy as sa
revision = '0028'
down_revision = '0027'
TARGET = "((type IN ('unavailable','preferred_period') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type='room_unavailable' AND room_id IS NOT NULL AND instructor_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type IN ('group_unavailable','group_allowed') AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND activity_id IS NULL) OR (type='activity_allowed' AND activity_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL) OR (type='activity_room' AND activity_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL) OR (type='activities_not_same_day' AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type IN ('instructor_max_daily_hours','instructor_max_days') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type='group_max_daily_hours' AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND activity_id IS NULL))"
STRENGTH = "type IN ('unavailable','preferred_period','room_unavailable','group_unavailable','group_allowed','activity_allowed','activity_room','activities_not_same_day','instructor_max_daily_hours','group_max_daily_hours','instructor_max_days') AND ((type!='preferred_period' AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))"
HOURS = "(type IN ('activity_room','activities_not_same_day','instructor_max_daily_hours','group_max_daily_hours','instructor_max_days') AND start_hour IS NULL AND end_hour IS NULL AND day IS NULL) OR (type IN ('unavailable','preferred_period','room_unavailable','group_unavailable','group_allowed','activity_allowed') AND start_hour IS NOT NULL AND end_hour IS NOT NULL AND start_hour >= 0 AND end_hour <= 24 AND start_hour < end_hour AND start_hour * 2 = floor(start_hour * 2) AND end_hour * 2 = floor(end_hour * 2))"
OLD_TARGET = "((type IN ('unavailable','preferred_period') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type='room_unavailable' AND room_id IS NOT NULL AND instructor_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type IN ('group_unavailable','group_allowed') AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND activity_id IS NULL) OR (type='activity_allowed' AND activity_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL))"
OLD_STRENGTH = "type IN ('unavailable','preferred_period','room_unavailable','group_unavailable','group_allowed','activity_allowed') AND ((type!='preferred_period' AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))"

def upgrade():
    for key in ('rule_target', 'rule_strength', 'rule_hours'):
        op.drop_constraint(key, 'rule', type_='check')
    op.alter_column('rule', 'start_hour', type_=sa.Float(), nullable=True)
    op.alter_column('rule', 'end_hour', type_=sa.Float(), nullable=True)
    op.alter_column('rule', 'day', nullable=True)
    op.add_column('rule', sa.Column('params', sa.JSON(), nullable=False, server_default='{}'))
    op.create_check_constraint('rule_target', 'rule', TARGET)
    op.create_check_constraint('rule_strength', 'rule', STRENGTH)
    op.create_check_constraint('rule_hours', 'rule', HOURS)

def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM rule WHERE day IS NULL OR start_hour IS NULL OR start_hour <> floor(start_hour) OR end_hour <> floor(end_hour)")).scalar():
        raise RuntimeError('Remove limit, every-day and half-hour rules before downgrading')
    for key in ('rule_target', 'rule_strength', 'rule_hours'):
        op.drop_constraint(key, 'rule', type_='check')
    op.drop_column('rule', 'params')
    op.alter_column('rule', 'day', nullable=False)
    op.alter_column('rule', 'end_hour', type_=sa.Integer(), nullable=False, postgresql_using='end_hour::integer')
    op.alter_column('rule', 'start_hour', type_=sa.Integer(), nullable=False, postgresql_using='start_hour::integer')
    op.create_check_constraint('rule_target', 'rule', OLD_TARGET)
    op.create_check_constraint('rule_strength', 'rule', OLD_STRENGTH)
    op.create_check_constraint('rule_hours', 'rule', "start_hour >= 0 AND end_hour <= 24 AND start_hour < end_hour")
