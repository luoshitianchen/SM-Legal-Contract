"""法务合同域路由：合同起草/审批/归档、模板管理。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.legal import (
    ApprovalCreate,
    ArchiveCreate,
    ContractCreate,
    ContractSubmit,
    TemplateCreate,
)
from app.services.legal import ContractService, TemplateService

router = APIRouter(prefix="/api/legal", tags=["legal-contract"])


# ── 合同 ──
@router.get("/contracts")
async def list_contracts(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ContractService.list_contracts(session, limit, offset, status_filter, keyword)


@router.post("/contracts", status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: ContractCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ContractService.create_contract(session, payload, request)


@router.get("/contracts/{contract_id}")
async def get_contract(
    contract_id: str, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ContractService.get_contract(session, contract_id)


@router.post("/contracts/{contract_id}/submit")
async def submit_contract(
    contract_id: str, payload: ContractSubmit, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ContractService.submit_for_review(session, contract_id, request)


@router.post("/contracts/{contract_id}/decide", status_code=status.HTTP_200_OK)
async def decide_contract(
    contract_id: str, payload: ApprovalCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ContractService.decide(session, contract_id, payload, request)


@router.post("/contracts/{contract_id}/archive", status_code=status.HTTP_201_CREATED)
async def archive_contract(
    contract_id: str, payload: ArchiveCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await ContractService.archive(session, contract_id, payload, request)


# ── 模板 ──
@router.get("/templates")
async def list_templates(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    keyword: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TemplateService.list_templates(session, limit, offset, keyword)


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: TemplateCreate, request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await TemplateService.create_template(session, payload, request)
