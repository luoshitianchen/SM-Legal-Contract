"""法务合同域 Pydantic 模型。"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ContractCreate(BaseModel):
    contract_no: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(default="general", max_length=32)
    party_a: str = Field(default="", max_length=128)
    party_b: str = Field(default="", max_length=128)
    amount: float = Field(ge=0)
    sign_date: date | None = None
    effective_date: date | None = None
    expiry_date: date | None = None
    created_by: str = Field(default="", max_length=64)


class ContractSubmit(BaseModel):
    """提交审批动作（无附加字段，仅触发状态迁移）。"""


class ApprovalCreate(BaseModel):
    approver_id: str = Field(min_length=1, max_length=64)
    decision: Literal["approve", "reject"]
    comment: str = Field(default="", max_length=512)


class ArchiveCreate(BaseModel):
    file_ref: str = Field(min_length=1, max_length=256)
    location: str = Field(default="", max_length=128)
    archived_by: str = Field(default="", max_length=64)


class TemplateCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=128)
    category: str = Field(default="general", max_length=32)
    content: str = Field(default="", max_length=10000)
