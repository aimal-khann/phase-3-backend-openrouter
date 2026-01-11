from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import datetime
import os
import json
from sqlmodel import Session, select, desc
from openai import OpenAI

# Internal Imports
from src.db.session import sync_engine
from src.models.chat import Conversation, ChatMessage
from src.mcp.tools import (
    add_task, 
    list_tasks, 
    delete_task, 
    get_analytics, 
    delete_all_tasks, 
    complete_all_tasks, 
    mark_all_tasks_incomplete,
    update_task_by_title
)

router = APIRouter()

# --- OPENROUTER CONFIGURATION ---
# 1. Get the OpenRouter Key from .env
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# 2. Set Default Model (Switched to Llama 3.3 70B which is robust and free)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

# 3. Configure Client for OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": "http://localhost:3000", # Required by OpenRouter
        "X-Title": "Aurora Task Agent", # Optional
    }
)

# --- REQUEST/RESPONSE MODELS ---
class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    user_id: str
    tool_calls_executed: bool
    original_request: Dict[str, Any]

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are Aurora, an intelligent Task Orchestrator.
Your goal is to ensure the user stays organized and productive.
Today's date is: {current_date}

BEHAVIORAL GUIDELINES:
1. **Direct & Action-Oriented**: Do not explain what you are doing, just do it.
2. **Smart Parsing**: If the user provides a relative date like "next friday", calculate the specific date.
3. **Data Integrity**: Always ensure dates are formatted as YYYY-MM-DD before saving.
4. **Duplicate Handling**: If you find multiple tasks with the same name when deleting, ask the user for clarification using the task IDs provided in the error message.
"""

# --- TOOLS SCHEMA (Cleaned for compatibility) ---
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "add_task",
            "description": "Add a new task",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Task priority"},
                    "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                    "tags": {"type": "string", "description": "Comma-separated tags"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update an existing task. Identify the task by its CURRENT title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "current_title": {"type": "string", "description": "The exact title of the task to update"},
                    "new_title": {"type": "string", "description": "The new title (if renaming)"},
                    "description": {"type": "string", "description": "New description"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "status": {"type": "string", "enum": ["pending", "completed"]},
                    "due_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "tags": {"type": "string"}
                },
                "required": ["current_title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks for the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["all", "pending", "completed", "archived"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task. Handles duplicates: if multiple tasks have the same title, use task_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_title": {"type": "string", "description": "Title of the task to delete (if unique)"},
                    "task_id": {"type": "string", "description": "The specific UUID of the task (use this to resolve duplicates)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_all_tasks",
            "description": "Delete all tasks for the user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_all_tasks",
            "description": "Mark all tasks as completed for the user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_analytics",
            "description": "Get analytics data for the user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mark_all_tasks_incomplete",
            "description": "Mark all tasks as incomplete for the user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

# --- CHAT ENDPOINT ---
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Handles user chat, saves to DB, calls OpenAI with tools, returns response.
    """
    if not request.user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    # A. Setup Database Session & User
    with Session(sync_engine) as session:
        try:
            user_uuid = uuid.UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user_id format")

        # B. Get or Create Conversation
        conv_id = None
        if request.conversation_id:
            try:
                conv_id = uuid.UUID(request.conversation_id)
                conversation = session.get(Conversation, conv_id)
                if not conversation:
                    conv_id = None
            except ValueError:
                conv_id = None

        if not conv_id:
            title_text = request.message[:30] + "..." if len(request.message) > 30 else request.message
            new_conv = Conversation(
                user_id=user_uuid,
                title=title_text or "New Chat"
            )
            session.add(new_conv)
            session.commit()
            session.refresh(new_conv)
            conv_id = new_conv.id

        # C. Save USER Message to DB
        user_msg_db = ChatMessage(
            conversation_id=conv_id,
            role="user",
            content=request.message,
            created_at=datetime.datetime.utcnow()
        )
        session.add(user_msg_db)
        session.commit()

        # D. Build Context
        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(current_date=today_str)}]

        # Load history - FIX: Load newest 10, then reverse for chronological order
        history = session.exec(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv_id)
            .order_by(desc(ChatMessage.timestamp)) # Newest first
            .limit(10)
        ).all()
        
        # Reverse to chronological order (Old -> New)
        history = history[::-1]

        for h in history:
            if h.role in ["user", "assistant"]:
                messages.append({"role": h.role, "content": h.content})

        # E. Call OpenAI (via OpenRouter)
        tool_calls_executed = False
        try:
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto"
            )
            ai_msg = completion.choices[0].message
            final_resp = ""

            # F. Handle Tool Calls
            if ai_msg.tool_calls:
                messages.append(ai_msg)
                tool_calls_executed = True

                for tool_call in ai_msg.tool_calls:
                    fname = tool_call.function.name
                    args = json.loads(tool_call.function.arguments)
                    args['user_id'] = request.user_id # Inject user_id securely here

                    # Call the appropriate tool
                    if fname == "add_task":
                        result = add_task(**args)
                    elif fname == "update_task":
                        result = update_task_by_title(**args)
                    elif fname == "list_tasks":
                        result = list_tasks(**args)
                    elif fname == "delete_task":
                        result = delete_task(**args)
                    elif fname == "delete_all_tasks":
                        result = delete_all_tasks(**args)
                    elif fname == "complete_all_tasks":
                        result = complete_all_tasks(**args)
                    elif fname == "mark_all_tasks_incomplete":
                        result = mark_all_tasks_incomplete(**args)
                    elif fname == "get_analytics":
                        result = get_analytics(**args)
                    else:
                        result = {"status": "error", "message": f"Tool {fname} not found"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })

                # Get final response
                final_completion = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages
                )
                final_resp = final_completion.choices[0].message.content
            else:
                final_resp = ai_msg.content or "Okay."

        except Exception as e:
            # Print error to console for debugging
            print(f"OpenRouter Error: {str(e)}")
            final_resp = f"I encountered an error processing your request: {str(e)}"
            tool_calls_executed = False

        # G. Save ASSISTANT Message
        ai_msg_db = ChatMessage(
            conversation_id=conv_id,
            role="assistant",
            content=final_resp or "Processed.",
            created_at=datetime.datetime.utcnow()
        )
        session.add(ai_msg_db)
        session.commit()

        # H. Return Response
        return ChatResponse(
            response=final_resp or "Done.",
            conversation_id=str(conv_id),
            user_id=request.user_id,
            tool_calls_executed=tool_calls_executed,
            original_request={"message": request.message}
        )

# --- CONVERSATION HISTORY ENDPOINTS ---
class ConversationHistoryResponse(BaseModel):
    id: str
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

@router.get("/conversations", response_model=List[ConversationHistoryResponse])
def get_conversations(user_id: str):
    if not user_id: raise HTTPException(status_code=400, detail="user_id required")
    with Session(sync_engine) as session:
        user_uuid = uuid.UUID(user_id)
        conversations = session.exec(select(Conversation).where(Conversation.user_id == user_uuid).order_by(desc(Conversation.updated_at))).all()
        return [ConversationHistoryResponse(id=str(c.id), title=c.title, created_at=c.created_at, updated_at=c.updated_at) for c in conversations]

class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    messages: List[Dict[str, Any]]

@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_detail(conversation_id: str, user_id: str):
    if not user_id: raise HTTPException(status_code=400, detail="user_id required")
    with Session(sync_engine) as session:
        try:
            user_uuid = uuid.UUID(user_id)
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError: raise HTTPException(status_code=400, detail="Invalid ID")
        
        conversation = session.get(Conversation, conv_uuid)
        if not conversation or str(conversation.user_id) != user_id: raise HTTPException(status_code=404, detail="Not found")
        
        messages = session.exec(select(ChatMessage).where(ChatMessage.conversation_id == conv_uuid).order_by(ChatMessage.timestamp.asc())).all()
        return ConversationDetailResponse(
            id=str(conversation.id), title=conversation.title, created_at=conversation.created_at, updated_at=conversation.updated_at,
            messages=[{"id": str(m.id), "role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages]
        )

@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, user_id: str):
    if not user_id: raise HTTPException(status_code=400, detail="user_id required")
    with Session(sync_engine) as session:
        try:
            user_uuid = uuid.UUID(user_id)
            conv_uuid = uuid.UUID(conversation_id)
        except ValueError: raise HTTPException(status_code=400, detail="Invalid ID")
        
        conversation = session.get(Conversation, conv_uuid)
        if not conversation or str(conversation.user_id) != user_id: raise HTTPException(status_code=404, detail="Not found")
        
        messages = session.exec(select(ChatMessage).where(ChatMessage.conversation_id == conv_uuid)).all()
        for m in messages: session.delete(m)
        session.delete(conversation)
        session.commit()
        return {"message": "Deleted"}