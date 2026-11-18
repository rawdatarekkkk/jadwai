"""Ask JAI chats: each admin's conversations, their messages, and what the chat remembers."""
from alembic import op
import sqlalchemy as sa
revision = '0033'
down_revision = '0032'

def upgrade():
    op.create_table('assistant_chat',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('app_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('state', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('assistant_chat_user_updated', 'assistant_chat', ['user_id', 'updated_at'])
    op.create_table('assistant_message',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chat_id', sa.String(36), sa.ForeignKey('assistant_chat.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(10), nullable=False),
        sa.Column('body', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('you', 'jai')", name='assistant_message_role'))
    op.create_index('assistant_message_chat_created', 'assistant_message', ['chat_id', 'created_at'])
    # The app's restricted role (made by app.provision) needs these too, on databases provisioned earlier.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'jadwai_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON assistant_chat, assistant_message TO jadwai_app;
        END IF; END $$""")

def downgrade():
    op.drop_index('assistant_message_chat_created', table_name='assistant_message')
    op.drop_table('assistant_message')
    op.drop_index('assistant_chat_user_updated', table_name='assistant_chat')
    op.drop_table('assistant_chat')
