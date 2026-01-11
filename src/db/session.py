from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.orm import sessionmaker
from ..core.config import settings
import os

# Helper function to ensure URL format is correct
def get_db_url():
    url = settings.DATABASE_URL
    if not url:
        return "sqlite:///todo.db"
    return url

db_url = get_db_url()

# --- CONFIGURATION FOR SQLITE ---
if db_url.startswith("sqlite"):
    # SQLite only supports Sync engine easily
    sync_engine = create_engine(
        db_url,
        echo=True,
        connect_args={"check_same_thread": False}
    )

    def get_session():
        with Session(sync_engine) as session:
            yield session

# --- CONFIGURATION FOR POSTGRESQL (NEON) ---
else:
    # 1. SETUP SYNC ENGINE (Required for creating tables on startup)
    # Ensure URL starts with postgresql:// and does NOT use async driver
    sync_url = db_url.replace("postgres://", "postgresql://")
    if "+asyncpg" in sync_url:
        sync_url = sync_url.replace("+asyncpg", "")
    
    # Create the Sync Engine (uses psycopg2-binary)
    sync_engine = create_engine(
        sync_url,
        echo=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )

    # 2. SETUP ASYNC ENGINE (For async endpoints)
    # Ensure URL uses the async driver
    async_url = sync_url.replace("postgresql://", "postgresql+asyncpg://")

    async_engine = create_async_engine(
        async_url,
        echo=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    # Async Session Factory
    AsyncSessionLocal = sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Dependency: Get Sync Session (This is what your current API uses)
    def get_session():
        with Session(sync_engine) as session:
            yield session

    # Dependency: Get Async Session (Available for future use)
    async def get_async_session():
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()