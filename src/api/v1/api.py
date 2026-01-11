from fastapi import APIRouter
from .endpoints import auth, tasks, agent

router = APIRouter()

# Include all API endpoints
router.include_router(auth.router, prefix="/auth", tags=["authentication"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(agent.router, prefix="", tags=["agent"])