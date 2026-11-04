"""Immutable adjudication decisions preserve their source reviews."""
from alembic import op
import sqlalchemy as sa
revision='0024'
down_revision='0023'
def upgrade():
    op.create_table('evaluation_adjudication',sa.Column('id',sa.String(36),primary_key=True),sa.Column('request_key',sa.String(36),unique=True,nullable=False),sa.Column('submitted_by',sa.String(36),sa.ForeignKey('app_user.id'),nullable=False),sa.Column('first_review_id',sa.String(36),sa.ForeignKey('evaluation_review.id'),nullable=False),sa.Column('second_review_id',sa.String(36),sa.ForeignKey('evaluation_review.id'),nullable=False),sa.Column('adjudicator_id',sa.String(100),nullable=False),sa.Column('input_sha256',sa.String(64),nullable=False),sa.Column('record',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.execute('CREATE TRIGGER evaluation_adjudication_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON evaluation_adjudication FOR EACH STATEMENT EXECUTE FUNCTION reject_evaluation_review_mutation()')
def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM evaluation_adjudication')).scalar():raise RuntimeError('Preserve adjudications before downgrading')
    op.drop_table('evaluation_adjudication')
