"""Reserve model request keys before external I/O."""
from alembic import op
import sqlalchemy as sa
revision='0026'
down_revision='0025'
def upgrade():
    op.create_table('extraction_job',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('request_key',sa.String(36),unique=True,nullable=False),
        sa.Column('submitted_by',sa.String(36),sa.ForeignKey('app_user.id'),nullable=False),
        sa.Column('input_sha256',sa.String(64),nullable=False),
        sa.Column('status',sa.String(30),nullable=False),
        sa.Column('proposal_id',sa.String(36),sa.ForeignKey('extraction_proposal.id'),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM extraction_job')).scalar():
        raise RuntimeError('Preserve model request history before downgrading')
    op.drop_table('extraction_job')
