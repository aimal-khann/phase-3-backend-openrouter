from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.v1.api import router as api_router
from .api.v1.endpoints.agent import router as agent_router
import os
from dotenv import load_dotenv
from sqlmodel import SQLModel
from .db.session import sync_engine
from .models.user import User
from .models.task import Task

# Load environment variables
load_dotenv()

# Create database tables on startup
def create_db_and_tables():
    SQLModel.metadata.create_all(sync_engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    create_db_and_tables()
    yield
    # Cleanup on shutdown if needed

app = FastAPI(
    title="Professional Todo Manager API",
    description="API for the Professional Todo Manager backend service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware to allow requests from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(agent_router, prefix="/api/v1", tags=["agent"])

@app.get("/")
def read_root():
    return {"message": "Professional Todo Manager API"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}