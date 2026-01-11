from logging.config import fileConfig
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Force load the .env file
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import Connection

from alembic import context

# IMPORT MODELS SO ALEMBIC SEES THEM - import from models package to resolve circular references
from src import models
from sqlmodel import SQLModel

config = context.config

# 2. OVERRIDE URL with .env variable - use sync version for migrations
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Convert async database URL to sync for migrations
    sync_database_url = database_url.replace("+aiosqlite", "").replace("+asyncpg", "")
    config.set_main_option("sqlalchemy.url", sync_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()