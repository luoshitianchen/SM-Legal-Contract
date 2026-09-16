"""法务合同域服务：合同起草、审批、归档的业务规则与状态机。"""
from __future__ import annotations

import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError

from app.core.security import internal_write_allowed
from app.models.legal import Contract, ContractApproval, ContractArchive, ContractTemplate
from app.repositories import legal as repo
from app.schemas.legal import ApprovalCreate, ArchiveCreate, ContractCreate, TemplateCreate
from app.services.audit import record_audit

# 合同合法状态迁移
_CONTRACT_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"in_review"},
    "in_review": {"approved", "rejected"},
    "approved": {"archived"},
    "rejected": set(),
    "archived": set(),
}


def _contract_to_dict(c: Contract) -> dict:
    return {
        "id": c.id, "contract_no": c.contract_no, "title": c.title, "category": c.category,
        "party_a": c.party_a, "party_b": c.party_b, "amount": c.amount,
        "sign_date": c.sign_date.isoformat() if c.sign_date else None,
        "effective_date": c.effective_date.isoformat() if c.effective_date else None,
        "expiry_date": c.expiry_date.isoformat() if c.expiry_date else None,
        "status": c.status, "created_by": c.created_by,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "updated_at": c.updated_at.isoformat() if c.updated_at else "",
    }


def _approval_to_dict(a: ContractApproval) -> dict:
    return {
        "id": a.id, "contract_id": a.contract_id, "approver_id": a.approver_id,
        "decision": a.decision, "comment": a.comment,
        "decided_at": a.decided_at.isoformat() if a.decided_at else "",
    }


def _template_to_dict(t: ContractTemplate) -> dict:
    return {
        "id": t.id, "code": t.code, "name": t.name, "category": t.category,
        "content": t.content, "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else "",
    }


def _archive_to_dict(a: ContractArchive) -> dict:
    return {
        "id": a.id, "contract_id": a.contract_id, "file_ref": a.file_ref,
        "location": a.location, "archived_by": a.archived_by,
        "archived_at": a.archived_at.isoformat() if a.archived_at else "",
    }


class ContractService:
    @staticmethod
    async def list_contracts(session, limit, offset, status_filter, keyword):
        rows = await repo.list_contracts(session, limit, offset, status_filter, keyword)
        total = await repo.count_contracts(session, status_filter, keyword)
        return {"total": total, "items": [_contract_to_dict(c) for c in rows]}

    @staticmethod
    async def get_contract(session, contract_id):
        c = await repo.get_contract(session, contract_id)
        if not c:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        approvals = await repo.list_approvals(session, contract_id)
        result = _contract_to_dict(c)
        result["approvals"] = [_approval_to_dict(a) for a in approvals]
        return result

    @staticmethod
    async def create_contract(session, payload: ContractCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        # 业务规则：生效日期不得晚于到期日期
        if (
            payload.effective_date
            and payload.expiry_date
            and payload.effective_date > payload.expiry_date
        ):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "生效日期不能晚于到期日期")
        if await repo.get_contract_by_no(session, payload.contract_no):
            raise HTTPException(status.HTTP_409_CONFLICT, "合同编号已存在")
        c = Contract(
            id=str(uuid.uuid4()), contract_no=payload.contract_no, title=payload.title,
            category=payload.category, party_a=payload.party_a, party_b=payload.party_b,
            amount=payload.amount, sign_date=payload.sign_date,
            effective_date=payload.effective_date, expiry_date=payload.expiry_date,
            status="draft", created_by=payload.created_by,
        )
        try:
            c = await repo.create_contract(session, c)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "合同编号已存在") from exc
        await record_audit(session, "contract.created", "internal",
                           f"contract_id={c.id} no={payload.contract_no}", request)
        return _contract_to_dict(c)

    @staticmethod
    async def submit_for_review(session, contract_id, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        c = await repo.get_contract(session, contract_id)
        if not c:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        if "in_review" not in _CONTRACT_TRANSITIONS.get(c.status, set()):
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"合同状态 {c.status} 不可提交审批")
        c.status = "in_review"
        c = await repo.update_contract(session, c)
        await record_audit(session, "contract.submitted", "internal",
                           f"contract_id={contract_id}", request)
        return _contract_to_dict(c)

    @staticmethod
    async def decide(session, contract_id, payload: ApprovalCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        c = await repo.get_contract(session, contract_id)
        if not c:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        if c.status != "in_review":
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"合同当前状态 {c.status}，须为审批中")
        # 业务规则：同一审批人不可重复审批同一份合同
        if await repo.approval_exists(session, contract_id, payload.approver_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "该审批人已审批过此合同")
        decision = payload.decision
        a = ContractApproval(
            id=str(uuid.uuid4()), contract_id=contract_id,
            approver_id=payload.approver_id, decision=decision, comment=payload.comment,
        )
        await repo.create_approval(session, a)
        c.status = "approved" if decision == "approve" else "rejected"
        c = await repo.update_contract(session, c)
        await record_audit(session, f"contract.{decision}d", "internal",
                           f"contract_id={contract_id} approver={payload.approver_id}", request)
        return _contract_to_dict(c)

    @staticmethod
    async def archive(session, contract_id, payload: ArchiveCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        c = await repo.get_contract(session, contract_id)
        if not c:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "合同不存在")
        if c.status != "approved":
            raise HTTPException(status.HTTP_409_CONFLICT,
                               f"合同状态 {c.status}，须审批通过后方可归档")
        if await repo.get_archive_by_contract(session, contract_id):
            raise HTTPException(status.HTTP_409_CONFLICT, "合同已归档，不可重复归档")
        arch = ContractArchive(
            id=str(uuid.uuid4()), contract_id=contract_id, file_ref=payload.file_ref,
            location=payload.location, archived_by=payload.archived_by,
        )
        arch = await repo.create_archive(session, arch)
        c.status = "archived"
        await repo.update_contract(session, c)
        await record_audit(session, "contract.archived", "internal",
                           f"contract_id={contract_id}", request)
        return _archive_to_dict(arch)


class TemplateService:
    @staticmethod
    async def list_templates(session, limit, offset, keyword):
        rows = await repo.list_templates(session, limit, offset, keyword)
        total = await repo.count_templates(session, keyword)
        return {"total": total, "items": [_template_to_dict(t) for t in rows]}

    @staticmethod
    async def create_template(session, payload: TemplateCreate, request: Request):
        if not internal_write_allowed(request):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "内部写入令牌无效")
        if await repo.get_template_by_code(session, payload.code):
            raise HTTPException(status.HTTP_409_CONFLICT, "模板编码已存在")
        t = ContractTemplate(
            id=str(uuid.uuid4()), code=payload.code, name=payload.name,
            category=payload.category, content=payload.content, status="active",
        )
        try:
            t = await repo.create_template(session, t)
        except IntegrityError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "模板编码已存在") from exc
        await record_audit(session, "contract_template.created", "internal",
                           f"template_id={t.id} code={payload.code}", request)
        return _template_to_dict(t)
