import uuid
from datetime import datetime
from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship

# --- 1. CONVERSATION MODEL ---
class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"  # Explicit table name prevents naming conflicts
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(index=True)
    title: str = Field(default="New Chat", max_length=200)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationship: One Conversation has many Messages
    messages: List["ChatMessage"] = Relationship(back_populates="conversation")


# --- 2. CHAT MESSAGE MODEL ---
class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"  # Explicit table name
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", index=True)
    
    # FIX: Removed the 'check' constraint that was crashing the app
    role: str = Field(default="user") 
    
    content: str = Field(max_length=10000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_call_id: Optional[str] = Field(default=None)

    # Relationship: Many Messages belong to one Conversation
    conversation: Optional[Conversation] = Relationship(back_populates="messages")