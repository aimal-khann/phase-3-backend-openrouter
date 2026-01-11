from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List
from datetime import datetime, timedelta, timezone
import uuid

from src.db.session import get_session
from src.models.user import User
from src.models.task import Task, TaskStatus
from src.schemas.task import TaskCreate, TaskRead, TaskUpdate, DashboardStats
from src.api.deps import get_current_user

router = APIRouter()

# --- NEW STATS ENDPOINT ---
@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Get current time once to avoid time drift during execution
    # Using timezone-aware datetime for proper comparison
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_later = now + timedelta(days=7)

    # Execute multiple efficient queries in parallel
    total_tasks = session.exec(
        select(func.count(Task.id)).where(Task.user_id == current_user.id)
    ).one()

    completed_tasks = session.exec(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == TaskStatus.completed
        )
    ).one()

    completed_today = session.exec(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == TaskStatus.completed,
            Task.updated_at >= today_start
        )
    ).one()

    # Fixed: Compare only date parts for due soon calculation to handle timezone issues
    # Also ensure due date is not in the past
    tasks_due_soon = session.exec(
        select(func.count(Task.id)).where(
            Task.user_id == current_user.id,
            Task.status == TaskStatus.pending,
            Task.due_date != None,
            Task.due_date >= now,  # Due date should not be in the past
            Task.due_date <= seven_days_later  # Due date should be within 7 days
        )
    ).one()

    # Calculate productivity score
    productivity_score = 0
    if total_tasks > 0:
        productivity_score = round((completed_tasks / total_tasks) * 100)

    return DashboardStats(
        tasks_due_soon=tasks_due_soon,
        completed_today=completed_today,
        productivity_score=productivity_score,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks
    )
# --------------------------

@router.get("/", response_model=List[TaskRead])
def list_user_tasks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    tasks = session.exec(select(Task).where(Task.user_id == current_user.id)).all()
    return tasks

@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    task_create: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    db_task = Task(
        user_id=current_user.id,
        title=task_create.title,
        description=task_create.description,
        status=task_create.status,
        priority=task_create.priority,
        due_date=task_create.due_date,
        tags=task_create.tags,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task

@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return task

@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: uuid.UUID,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    task_data = task_update.dict(exclude_unset=True)
    for key, value in task_data.items():
        setattr(task, key, value)

    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@router.delete("/{task_id}")
def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    session.delete(task)
    session.commit()
    return {"ok": True}