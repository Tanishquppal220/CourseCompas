"""Alembic environment for CourseCompass.

The connection URL is taken from ``app.database`` (which reads ``DATABASE_URL``
from the environment / ``.env``), so migrations always point at the same
database the application uses.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.database import DATABASE_URL
from app.models import Base

# Alembic Config object (gives access to alembic.ini values).
config = context.config

# Configure Python logging from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for 'autogenerate' support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
