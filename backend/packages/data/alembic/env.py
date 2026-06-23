import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from lang3s.core import config as app_config
from lang3s.data.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
db_url = app_config.DB_URL
if "postgresql+psycopg:" not in db_url:
    db_url = re.sub(r"^postgresql(\+[^:]+)?:", "postgresql+psycopg:", db_url)
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def include_name(name, type_, parent_names):
    import re

    if type_ == "table":
        # Ignore any table that ends with '_part_' followed by a number
        # Adjust this regex/logic to match your partition naming scheme

        if name and re.search(r"_part_\d+$", name):
            return False
    # For indexes on partitions, Alembic usually names them with the table name
    if type_ == "index":
        if name and re.search(r"_part_\d+", name):
            return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
