"""法务合同域模型：合同、审批记录、合同模板、归档记录。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class Contract(Base):
    """合同主表：一份合同对应唯一编号，全生命周期状态机管理。"""

    __tablename__ = "lc_contracts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_no: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="general")
    party_a: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    party_b: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 状态机：draft 草稿 / in_review 审批中 / approved 已审批 / rejected 已驳回 / archived 已归档
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", index=True)
    created_by: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ContractApproval(Base):
    """合同审批记录：每次审批动作留痕。"""

    __tablename__ = "lc_contract_approvals"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("lc_contracts.id"), nullable=False, index=True
    )
    approver_id: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # approve / reject
    comment: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContractTemplate(Base):
    """合同模板：供起草合同时引用。"""

    __tablename__ = "lc_contract_templates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="general")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContractArchive(Base):
    """合同归档记录：审批通过后归档到档案库。"""

    __tablename__ = "lc_contract_archives"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    contract_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("lc_contracts.id"), nullable=False, unique=True, index=True
    )
    file_ref: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(128), default="")
    archived_by: Mapped[str] = mapped_column(String(64), default="")
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
