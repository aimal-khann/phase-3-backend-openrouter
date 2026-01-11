from sqlmodel import Session, select, desc
from datetime import datetime
from typing import Optional, List
import datetime as dt
from uuid import UUID
import uuid

from ..models.task import Task
from ..models.user import User
from ..db.session import sync_engine

# --- 1. CORE TASK FUNCTIONS ---

def add_task(user_id: str, title: str, description: Optional[str] = None,
             priority: str = "medium", due_date: Optional[str] = None, tags: Optional[str] = None):
    with Session(sync_engine) as session:
        if not user_id: raise ValueError("user_id is required")
        
        parsed_date = None
        if due_date:
            try: parsed_date = dt.datetime.strptime(due_date, "%Y-%m-%d")
            except: pass
            
        task = Task(
            user_id=user_id, title=title, description=description, priority=priority, 
            due_date=parsed_date, tags=tags, status="pending"
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        
        return {
            "status": "success", 
            "message": f"Task '{title}' added.", 
            "task": {"id": str(task.id), "title": task.title}
        }

def list_tasks(user_id: str, status: Optional[str] = None):
    with Session(sync_engine) as session:
        if not user_id: raise ValueError("user_id is required")
        
        query = select(Task).where(Task.user_id == user_id)
        if status and status != "all": 
            query = query.where(Task.status == status)
        
        # FIX: Order by newest first so the list is stable
        tasks = session.exec(query.order_by(desc(Task.created_at))).all()
        
        task_list = []
        for t in tasks:
            task_list.append({
                "id": str(t.id),
                "title": t.title,
                "priority": t.priority,
                "status": t.status,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "created_at": t.created_at.isoformat() if t.created_at else None
            })
            
        return {"status": "success", "tasks": task_list}

# --- IMPROVED DELETE FUNCTION ---
def delete_task(user_id: str, task_title: Optional[str] = None, task_id: Optional[str] = None):
    """
    Delete a task. Handles duplicates by asking for clarification with a numbered list.
    """
    with Session(sync_engine) as session:
        if not user_id: raise ValueError("user_id is required")
        if not task_title and not task_id:
            return {"status": "error", "message": "Please provide either a task title or task ID."}

        # 1. Direct Delete by ID
        if task_id:
            try: task_uuid = uuid.UUID(task_id)
            except ValueError: return {"status": "error", "message": "Invalid ID format."}

            task = session.get(Task, task_uuid)
            if not task or str(task.user_id) != user_id:
                return {"status": "error", "message": f"Task ID {task_id} not found."}
            
            title_backup = task.title
            session.delete(task)
            session.commit()
            return {"status": "success", "message": f"Task '{title_backup}' deleted."}

        # 2. Delete by Title (Smart Duplicate Check)
        if task_title:
            # Sort by creation time so "first one" and "second one" always mean the same thing
            tasks = session.exec(
                select(Task)
                .where(Task.user_id == user_id)
                .where(Task.title == task_title)
                .order_by(Task.created_at)
            ).all()
            
            if not tasks:
                return {"status": "error", "message": f"Task '{task_title}' not found."}
            
            if len(tasks) == 1:
                session.delete(tasks[0])
                session.commit()
                return {"status": "success", "message": f"Task '{task_title}' deleted."}
            
            # Found duplicates: Return a Numbered List
            duplicates_info = []
            for i, t in enumerate(tasks, 1):
                # Show Seconds for precision
                created_date = t.created_at.strftime('%Y-%m-%d %H:%M:%S') if t.created_at else "Unknown"
                due_str = f" | Due: {t.due_date.date()}" if t.due_date else ""
                
                # Format: "1. [Low] Created: ... ID: ..."
                info = f"{i}. [{t.priority.upper()}] Created: {created_date}{due_str} (ID: {t.id})"
                duplicates_info.append(info)
            
            list_str = "\n".join(duplicates_info)
            
            return {
                "status": "error", 
                "message": f"I found multiple tasks named '{task_title}'. Which one?\n{list_str}\n\nYou can say 'Delete number 1' or 'Delete the high priority one'.",
                "requires_clarification": True
            }

def update_task_by_title(user_id: str, current_title: str, new_title: str = None, 
                         description: str = None, priority: str = None, status: str = None, 
                         due_date: str = None, tags: str = None):
    with Session(sync_engine) as session:
        if not user_id or not current_title: return {"status": "error", "message": "Missing fields"}
        
        # Check for multiple tasks with same title before updating
        tasks = session.exec(select(Task).where(Task.user_id == user_id, Task.title == current_title)).all()
        if not tasks: return {"status": "error", "message": "Task not found."}
        if len(tasks) > 1:
             return {"status": "error", "message": f"Found {len(tasks)} tasks named '{current_title}'. Please rename them via ID first or delete the duplicates."}

        task = tasks[0]
        
        if new_title: task.title = new_title
        if description: task.description = description
        if priority: task.priority = priority
        if status: task.status = status
        if tags: task.tags = tags
        if due_date: 
            try: task.due_date = dt.datetime.strptime(due_date, "%Y-%m-%d")
            except: pass
            
        task.updated_at = dt.datetime.utcnow()
        session.add(task)
        session.commit()
        return {"status": "success", "message": f"Task '{current_title}' updated.", "task": {"title": task.title}}

# --- 2. ANALYTICS ---

def get_analytics(user_id: str):
    with Session(sync_engine) as session:
        tasks = session.exec(select(Task).where(Task.user_id == user_id)).all()
        total = len(tasks)
        completed = len([t for t in tasks if t.status == "completed"])
        pending = len([t for t in tasks if t.status == "pending"])
        score = int((completed / total * 100) if total > 0 else 0)
        
        return {"status": "success", "analytics": {"tasks_total": total, "tasks_completed": completed, "tasks_pending": pending, "productivity_score": score}}

# --- 3. BULK ACTIONS ---

def delete_all_tasks(user_id: str):
    with Session(sync_engine) as session:
        tasks = session.exec(select(Task).where(Task.user_id == user_id)).all()
        for t in tasks: session.delete(t)
        session.commit()
        return {"status": "success", "message": f"Deleted {len(tasks)} tasks."}

def complete_all_tasks(user_id: str):
    with Session(sync_engine) as session:
        tasks = session.exec(select(Task).where(Task.user_id == user_id)).all()
        for t in tasks: 
            t.status = "completed"
            session.add(t)
        session.commit()
        return {"status": "success", "message": "All tasks marked completed."}

def mark_all_tasks_incomplete(user_id: str):
    with Session(sync_engine) as session:
        tasks = session.exec(select(Task).where(Task.user_id == user_id)).all()
        for t in tasks: 
            t.status = "pending"
            session.add(t)
        session.commit()
        return {"status": "success", "message": "All tasks marked pending."}