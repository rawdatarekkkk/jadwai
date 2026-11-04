import os

from alembic import context
from app.models import Base
from sqlalchemy import create_engine


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


provided = context.config.attributes.get("connection")
if provided is not None:
    run(provided)
else:
    engine = create_engine(
        os.environ.get("DATABASE_ADMIN_URL") or os.environ["DATABASE_URL"]
    )
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
