"""Reviewed assignment locks captured in generation snapshots."""
from alembic import op
import sqlalchemy as sa
revision='0014'
down_revision='0013'

def upgrade():
    op.create_table('assignment_lock',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('source_run_id',sa.String(36),sa.ForeignKey('schedule_run.id'),nullable=False),
        sa.Column('activity_id',sa.String(36),sa.ForeignKey('teaching_activity.id'),nullable=False),
        sa.Column('occurrence',sa.Integer(),nullable=False),
        sa.Column('instructor_id',sa.String(36),sa.ForeignKey('instructor.id'),nullable=True),
        sa.Column('room_id',sa.String(36),sa.ForeignKey('room.id'),nullable=True),
        sa.Column('day',sa.String(12),nullable=True),
        sa.Column('start_minute',sa.Integer(),nullable=True),
        sa.Column('status',sa.String(20),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('app_user.id'),nullable=False),
        sa.Column('approved_by',sa.String(36),sa.ForeignKey('app_user.id'),nullable=True),
        sa.Column('request_key',sa.String(36),nullable=False),
        sa.Column('request_payload',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint("status IN ('draft','approved')",name='assignment_lock_status'),
        sa.CheckConstraint('occurrence >= 0 AND occurrence < 10',name='assignment_lock_occurrence'),
        sa.CheckConstraint('(day IS NULL) = (start_minute IS NULL)',name='assignment_lock_time_pair'),
        sa.CheckConstraint('start_minute IS NULL OR (start_minute >= 0 AND start_minute < 1440)',name='assignment_lock_minute'),
        sa.CheckConstraint('instructor_id IS NOT NULL OR room_id IS NOT NULL OR day IS NOT NULL',name='assignment_lock_nonempty'))
    op.create_index('assignment_lock_request','assignment_lock',['created_by','request_key'],unique=True)

def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM assignment_lock')).scalar():
        raise RuntimeError('Remove saved locks explicitly before downgrading')
    op.drop_table('assignment_lock')
