"""法务合同域仓储：合同/审批/模板/归档异步数据访问。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.legal import Contract, ContractApproval, ContractArchive, ContractTemplate


# ── 合同 ──
async def get_contract(session: AsyncSession, contract_id: str) -> Contract | None:
    result = await session.execute(select(Contract).where(Contract.id == contract_id))
    return result.scalar_one_or_none()


async def get_contract_by_no(session: AsyncSession, contract_no: str) -> Contract | None:
    result = await session.execute(select(Contract).where(Contract.contract_no == contract_no))
    return result.scalar_one_or_none()


async def list_contracts(session: AsyncSession, limit: int, offset: int,
                        status: str | None = None, keyword: str | None = None) -> list[Contract]:
    stmt = select(Contract).order_by(Contract.created_at.desc()).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Contract.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Contract.title.like(like), Contract.contract_no.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_contracts(session: AsyncSession, status: str | None = None,
                          keyword: str | None = None) -> int:
    stmt = select(func.count(Contract.id))
    if status:
        stmt = stmt.where(Contract.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(Contract.title.like(like), Contract.contract_no.like(like)))
    return int((await session.execute(stmt)).scalar_one())


async def create_contract(session: AsyncSession, c: Contract) -> Contract:
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return c


async def update_contract(session: AsyncSession, c: Contract) -> Contract:
    await session.commit()
    await session.refresh(c)
    return c


# ── 审批 ──
async def list_approvals(session: AsyncSession, contract_id: str) -> list[ContractApproval]:
    result = await session.execute(
        select(ContractApproval).where(ContractApproval.contract_id == contract_id)
        .order_by(ContractApproval.decided_at)
    )
    return list(result.scalars().all())


async def approval_exists(session: AsyncSession, contract_id: str,
                          approver_id: str) -> bool:
    result = await session.execute(
        select(func.count(ContractApproval.id)).where(
            ContractApproval.contract_id == contract_id,
            ContractApproval.approver_id == approver_id,
        )
    )
    return int(result.scalar_one()) > 0


async def create_approval(session: AsyncSession, a: ContractApproval) -> ContractApproval:
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


# ── 模板 ──
async def get_template(session: AsyncSession, template_id: str) -> ContractTemplate | None:
    result = await session.execute(select(ContractTemplate).where(ContractTemplate.id == template_id))
    return result.scalar_one_or_none()


async def get_template_by_code(session: AsyncSession, code: str) -> ContractTemplate | None:
    result = await session.execute(select(ContractTemplate).where(ContractTemplate.code == code))
    return result.scalar_one_or_none()


async def list_templates(session: AsyncSession, limit: int, offset: int,
                         keyword: str | None = None) -> list[ContractTemplate]:
    stmt = select(ContractTemplate).order_by(ContractTemplate.created_at.desc()).limit(limit).offset(offset)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(ContractTemplate.name.like(like), ContractTemplate.code.like(like)))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_templates(session: AsyncSession, keyword: str | None = None) -> int:
    stmt = select(func.count(ContractTemplate.id))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(or_(ContractTemplate.name.like(like), ContractTemplate.code.like(like)))
    return int((await session.execute(stmt)).scalar_one())


async def create_template(session: AsyncSession, t: ContractTemplate) -> ContractTemplate:
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


# ── 归档 ──
async def get_archive_by_contract(session: AsyncSession, contract_id: str) -> ContractArchive | None:
    result = await session.execute(
        select(ContractArchive).where(ContractArchive.contract_id == contract_id)
    )
    return result.scalar_one_or_none()


async def create_archive(session: AsyncSession, a: ContractArchive) -> ContractArchive:
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a
