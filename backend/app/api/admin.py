from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import case, desc, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis_record import AnalysisRun
from app.models.audit_log import AuditLog
from app.models.document_record import DocumentRecord
from app.models.user import User
from app.services.audit_service import log_event
from app.utils.auth import get_current_admin_user

router = APIRouter()


class AdminOverview(BaseModel):
    users_count: int
    documents_count: int
    analysis_runs_count: int
    audit_logs_count: int
    active_users_24h: int
    uploads_24h: int
    analyses_24h: int
    check_documents_count: int
    training_documents_count: int


class AuditLogItem(BaseModel):
    id: int
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    metadata: dict
    ip_address: Optional[str] = None
    created_at: str


class UserSummaryItem(BaseModel):
    user_id: str
    email: str
    username: str
    is_active: bool
    is_admin: bool
    role: str
    documents_count: int
    check_documents_count: int
    training_documents_count: int
    analyses_count: int
    created_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    last_login_at: Optional[str] = None


class UserStatusUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="true - active, false - blocked")


@router.get("/admin/overview", response_model=AdminOverview)
async def get_admin_overview(
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    users_count = await db.scalar(select(func.count(User.id)))
    documents_count = await db.scalar(select(func.count(DocumentRecord.id)))
    analysis_runs_count = await db.scalar(select(func.count(AnalysisRun.id)))
    audit_logs_count = await db.scalar(select(func.count(AuditLog.id)))
    active_users_24h = await db.scalar(
        select(func.count(distinct(AuditLog.user_id))).where(
            AuditLog.user_id.isnot(None),
            AuditLog.created_at >= since,
        )
    )
    uploads_24h = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "document_upload",
            AuditLog.created_at >= since,
        )
    )
    analyses_24h = await db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "analysis_run",
            AuditLog.created_at >= since,
        )
    )
    check_documents_count = await db.scalar(
        select(func.count(DocumentRecord.id)).where(DocumentRecord.purpose == "check")
    )
    training_documents_count = await db.scalar(
        select(func.count(DocumentRecord.id)).where(DocumentRecord.purpose == "training")
    )

    return AdminOverview(
        users_count=int(users_count or 0),
        documents_count=int(documents_count or 0),
        analysis_runs_count=int(analysis_runs_count or 0),
        audit_logs_count=int(audit_logs_count or 0),
        active_users_24h=int(active_users_24h or 0),
        uploads_24h=int(uploads_24h or 0),
        analyses_24h=int(analyses_24h or 0),
        check_documents_count=int(check_documents_count or 0),
        training_documents_count=int(training_documents_count or 0),
    )


@router.get("/admin/audit-logs", response_model=List[AuditLogItem])
async def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    action: Optional[str] = Query(default=None),
    user_id: Optional[str] = Query(default=None),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(desc(AuditLog.id))
        .limit(limit)
        .offset(offset)
    )
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)

    rows = (await db.execute(query)).all()
    return [
        AuditLogItem(
            id=log.id,
            user_id=str(log.user_id) if log.user_id else None,
            user_email=str(email) if email else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            metadata=log.metadata_json or {},
            ip_address=log.ip_address,
            created_at=log.created_at.isoformat(),
        )
        for log, email in rows
    ]


@router.get("/admin/users-summary", response_model=List[UserSummaryItem])
async def get_users_summary(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="last_login", pattern="^(last_login|account_age)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    only_blocked: bool = Query(default=False),
    _: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    max_audit_created = func.max(AuditLog.created_at)
    if sort_by == "account_age":
        order_expr = User.created_at.asc() if sort_order == "asc" else User.created_at.desc()
    else:
        order_expr = User.last_login_at.asc().nulls_last() if sort_order == "asc" else User.last_login_at.desc().nulls_last()

    query = (
        select(
            User.id,
            User.email,
            User.username,
            User.is_active,
            User.is_admin,
            User.role,
            User.created_at,
            User.last_login_at,
            func.count(distinct(DocumentRecord.id)).label("documents_count"),
            func.count(
                distinct(case((DocumentRecord.purpose == "check", DocumentRecord.id)))
            ).label("check_documents_count"),
            func.count(
                distinct(case((DocumentRecord.purpose == "training", DocumentRecord.id)))
            ).label("training_documents_count"),
            func.count(distinct(AnalysisRun.id)).label("analyses_count"),
            max_audit_created.label("last_activity_at"),
        )
        .select_from(User)
        .outerjoin(DocumentRecord, DocumentRecord.owner_id == User.id)
        .outerjoin(AnalysisRun, AnalysisRun.user_id == User.id)
        .outerjoin(AuditLog, AuditLog.user_id == User.id)
        .group_by(
            User.id,
            User.email,
            User.username,
            User.is_active,
            User.is_admin,
            User.role,
            User.created_at,
            User.last_login_at,
        )
        .limit(limit)
        .offset(offset)
    )
    if only_blocked:
        query = query.where(User.is_active.is_(False))
    query = query.order_by(order_expr, desc(max_audit_created))

    rows = (await db.execute(query)).all()
    return [
        UserSummaryItem(
            user_id=str(user_id),
            email=str(email),
            username=str(username),
            is_active=bool(is_active),
            is_admin=bool(is_admin),
            role=str(role or "user"),
            documents_count=int(documents_count or 0),
            check_documents_count=int(check_documents_count or 0),
            training_documents_count=int(training_documents_count or 0),
            analyses_count=int(analyses_count or 0),
            created_at=created_at.isoformat() if created_at else None,
            last_activity_at=last_activity_at.isoformat() if last_activity_at else None,
            last_login_at=last_login_at.isoformat() if last_login_at else None,
        )
        for (
            user_id,
            email,
            username,
            is_active,
            is_admin,
            role,
            created_at,
            last_login_at,
            documents_count,
            check_documents_count,
            training_documents_count,
            analyses_count,
            last_activity_at,
        ) in rows
    ]


@router.patch("/admin/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdateRequest,
    admin_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        return {"ok": False, "message": "User not found"}

    # Safety: don't allow disabling the last active admin (basic protection).
    if user.is_admin and not payload.is_active:
        active_admins = await db.scalar(
            select(func.count(User.id)).where(User.is_admin.is_(True), User.is_active.is_(True))
        )
        if int(active_admins or 0) <= 1:
            return {"ok": False, "message": "Cannot block the last active admin"}

    user.is_active = payload.is_active
    await log_event(
        db,
        action="user_status_update",
        user_id=admin_user.id,
        resource_type="user",
        resource_id=str(user.id),
        metadata={
            "target_email": user.email,
            "new_is_active": payload.is_active,
        },
    )
    await db.commit()
    return {"ok": True, "user_id": str(user.id), "is_active": user.is_active}
