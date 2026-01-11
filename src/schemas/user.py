from sqlmodel import SQLModel
from typing import Optional
from datetime import datetime
import uuid


class UserBase(SQLModel):
    email: str
    full_name: str


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: uuid.UUID
    created_at: datetime


class UserUpdate(SQLModel):
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserLogin(SQLModel):
    email: str
    password: str


class Token(SQLModel):
    access_token: str
    token_type: str


class TokenData(SQLModel):
    username: Optional[str] = None