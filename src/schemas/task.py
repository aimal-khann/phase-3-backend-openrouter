from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime
import uuid
from enum import Enum
from ..models.task import TaskStatus, TaskPriority

class TaskBase(SQLModel):
    title: str
    description: Optional[str] = None
    status: Optional[TaskStatus] = TaskStatus.pending
    priority: Optional[TaskPriority] = TaskPriority.medium
    due_date: Optional[datetime] = None
    tags: Optional[str] = None

class TaskCreate(TaskBase):
    title: str

class TaskRead(TaskBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

class TaskUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    tags: Optional[str] = None

# --- NEW STATS SCHEMA ---
class DashboardStats(SQLModel):
    tasks_due_soon: int
    completed_today: int
    productivity_score: int
    total_tasks: int
    completed_tasks: int