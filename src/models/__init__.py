# This file ensures both models are loaded together to resolve circular references
from .user import User
from .task import Task

__all__ = ["User", "Task"]