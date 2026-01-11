from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from .config import settings
from ..models.user import User
from ..db.session import get_async_session
from ..schemas.user import TokenData
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT authentication scheme
security = HTTPBearer()

# JWT token functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def authenticate_user(session: AsyncSession, email: str, password: str) -> Optional[User]:
    # Find user by email
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    user = result.first()

    if user is None:
        return None

    user = user[0]  # Get the User object from the tuple

    if not verify_password(password, user.password_hash):
        return None

    return user


async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_async_session)
) -> User:
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
    result = await session.execute(statement)
    user = result.first()

    if user is None:
        raise credentials_exception

    return user[0]  # Return the User object from the tuple