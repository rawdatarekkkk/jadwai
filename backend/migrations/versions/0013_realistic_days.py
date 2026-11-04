"""Versioned daily scheduling policy; no institutional defaults applied."""
from alembic import op
import sqlalchemy as sa
revision='0013'
down_revision='0012'
def upgrade():
    op.add_column('workspace',sa.Column('realism_policy',sa.JSON(),nullable=False,server_default='{}'))
def downgrade():
    for policy in op.get_bind().execute(sa.text('SELECT realism_policy FROM workspace')).scalars():
        if policy and any(v is not None and v is not False for v in policy.values()):
            raise RuntimeError('Clear the scheduling policy explicitly before downgrading')
    op.drop_column('workspace','realism_policy')
