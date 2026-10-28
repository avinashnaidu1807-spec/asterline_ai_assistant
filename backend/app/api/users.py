"""Users API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import User
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


class UserCreateReq(BaseModel):
    username: str
    display_name: str = ""


@router.get("", response_model=List[UserRead])
def list_users(db: Session = Depends(get_db)):
    users = db.execute(select(User).where(User.is_active == True)).scalars().all()
    return list(users)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(req: UserCreateReq, db: Session = Depends(get_db)):
    existing = db.execute(select(User).where(User.username == req.username)).scalar_one_or_none()
    if existing:
        return existing

    user = User(
        id=str(uuid.uuid4()),
        username=req.username,
        display_name=req.display_name or req.username.replace("_", " ").title(),
        created_at=datetime.utcnow(),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: str, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

