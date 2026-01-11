import re
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlmodel import Session, select
from datetime import timedelta

from src.db.session import get_session
from src.models.user import User
from src.schemas.user import UserCreate, UserRead, UserLogin
from src.core.security import create_access_token, get_password_hash, verify_password
from ...deps import get_current_user_sync
from src.core.config import settings

router = APIRouter()

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_create: UserCreate, session: Session = Depends(get_session)):
    # Check if user exists
    user = session.exec(select(User).where(User.email == user_create.email)).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate that full_name is not an email address
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if user_create.full_name and email_pattern.match(user_create.full_name.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name cannot be an email address"
        )

    # Create new user
    db_user = User(
        email=user_create.email,
        password_hash=get_password_hash(user_create.password),
        full_name=user_create.full_name
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user

@router.post("/login")
def login(user_credentials: UserLogin, session: Session = Depends(get_session)) -> dict:
    # Find user by email
    statement = select(User).where(User.email == user_credentials.email)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
def get_current_user_profile(current_user: User = Depends(get_current_user_sync)):
    return current_user