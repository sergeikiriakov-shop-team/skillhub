"""Pydantic schemas for platform identity: user/admin API DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str
    role: str = "contributor"


class RoleUpdate(BaseModel):
    role: str


class ReviewerUpdate(BaseModel):
    is_reviewer: bool


class UserOut(BaseModel):
    id: int
    name: str
    role: str
    is_reviewer: bool = False
    created_at: datetime


class UserCreated(UserOut):
    token: str = Field(description="Shown once — store it now; only its hash is kept.")
