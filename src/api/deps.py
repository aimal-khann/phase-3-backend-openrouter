from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from src.core.security import verify_password, create_access_token
from src.db.session import get_session
from src.models.user import User
from src.schemas.user import TokenData
from src.core.config import settings
import jwt
from typing import Optional


security = HTTPBearer()


def get_current_user_sync(token: HTTPAuthorizationCredentials = Depends(security), session: Session = Depends(get_session)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except jwt.exceptions.PyJWTError:
        raise credentials_exception

    statement = select(User).where(User.email == token_data.username)
    user = session.exec(statement).first()

    if user is None:
        raise credentials_exception

    return user


# Alias for backward compatibility with existing code
get_current_user = get_current_user_sync