"""Preserve extraction inputs and administrator review decisions separately."""
from alembic import op
import sqlalchemy as sa
revision = '0025'
down_revision = '0024'


def upgrade():
    op.create_table('extraction_proposal',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('request_key', sa.String(36), unique=True, nullable=False),
        sa.Column('submitted_by', sa.String(36), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('input_version', sa.Integer(), nullable=False),
        sa.Column('input_sha256', sa.String(64), nullable=False),
        sa.Column('record', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('extraction_proposal_review',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('proposal_id', sa.String(36), sa.ForeignKey('extraction_proposal.id'), unique=True, nullable=False),
        sa.Column('request_key', sa.String(36), unique=True, nullable=False),
        sa.Column('submitted_by', sa.String(36), sa.ForeignKey('app_user.id'), nullable=False),
        sa.Column('input_sha256', sa.String(64), nullable=False),
        sa.Column('record', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    for table in ('extraction_proposal', 'extraction_proposal_review'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION reject_evaluation_review_mutation()')


def downgrade():
    for table in ('extraction_proposal_review', 'extraction_proposal'):
        if op.get_bind().execute(sa.text(f'SELECT count(*) FROM {table}')).scalar():
            raise RuntimeError('Preserve proposal evidence before downgrading')
    op.drop_table('extraction_proposal_review')
    op.drop_table('extraction_proposal')
