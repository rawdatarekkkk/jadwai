"""Append-only annotation-review records, separate from operational inputs."""
from alembic import op
import sqlalchemy as sa
revision='0023'
down_revision='0022'
def upgrade():
    op.create_table('evaluation_review',sa.Column('id',sa.String(36),primary_key=True),sa.Column('request_key',sa.String(36),unique=True,nullable=False),sa.Column('submitted_by',sa.String(36),sa.ForeignKey('app_user.id'),nullable=False),sa.Column('reviewer_id',sa.String(100),nullable=False),sa.Column('input_sha256',sa.String(64),nullable=False),sa.Column('record',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.execute("CREATE FUNCTION reject_evaluation_review_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Evaluation review records are append-only'; END $$")
    op.execute('CREATE TRIGGER evaluation_review_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON evaluation_review FOR EACH STATEMENT EXECUTE FUNCTION reject_evaluation_review_mutation()')
def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM evaluation_review')).scalar():raise RuntimeError('Preserve evaluation reviews before downgrading')
    op.drop_table('evaluation_review');op.execute('DROP FUNCTION reject_evaluation_review_mutation()')
