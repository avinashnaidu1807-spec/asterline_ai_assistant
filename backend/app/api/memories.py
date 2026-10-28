"""Memory management API endpoints with per-user scoping and allowlisted operations."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.memory.service import memory_service
from app.schemas.memory import MemoryCategory, MemoryCreate, MemoryRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memories", tags=["memories"])


class MemoryCreateReq(BaseModel):
    user_id: str
    category: MemoryCategory
    content: str = Field(..., min_length=1, max_length=5000)


class MemoryUpdateReq(BaseModel):
    user_id: str
    content: str = Field(..., min_length=1, max_length=5000)


@router.get("", response_model=List[MemoryRead])
def list_memories(
    user_id: str = Query(...),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    memories = memory_service.get_all(db, user_id=user_id, category=category, status="active")
    return memories


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
def create_memory(
    req: MemoryCreateReq,
    db: Session = Depends(get_db),
):
    res = memory_service.create(
        session=db,
        user_id=req.user_id,
        category=req.category.value,
        content=req.content,
    )
    if not res.success or not res.memory:
        raise HTTPException(status_code=400, detail=res.reason)
    db.commit()
    return res.memory


@router.put("/{memory_id}", response_model=MemoryRead)
def update_memory(
    memory_id: str,
    req: MemoryUpdateReq,
    db: Session = Depends(get_db),
):
    res = memory_service.update(
        session=db,
        memory_id=memory_id,
        user_id=req.user_id,
        content=req.content,
    )
    if not res.success or not res.memory:
        raise HTTPException(status_code=400, detail=res.reason)
    db.commit()
    return res.memory


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: str,
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    res = memory_service.delete(session=db, memory_id=memory_id, user_id=user_id)
    if not res.success:
        raise HTTPException(status_code=404, detail=res.reason)
    db.commit()
    return None


@router.delete("", status_code=status.HTTP_200_OK)
def delete_all_memories(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    res = memory_service.delete_all(session=db, user_id=user_id)
    db.commit()
    return {"deleted_count": res.count, "user_id": user_id}

