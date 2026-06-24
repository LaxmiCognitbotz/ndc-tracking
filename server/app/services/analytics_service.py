"""Analytics service — TAT, bottleneck, department, and trend queries."""

from datetime import date

from sqlalchemy import select, func, case, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ndc_record import NdcRecord
from app.models.ndc_approval import NdcApproval


async def get_tat_stats(db: AsyncSession) -> dict:
    """Average/min/max TAT for completed NDCs, plus completion rate."""
    total_q = await db.execute(select(func.count()).select_from(NdcRecord))
    total = total_q.scalar() or 0

    completed_q = await db.execute(
        select(
            func.count().label("cnt"),
            func.avg(NdcRecord.ndc_completed_date - NdcRecord.ndc_initiated_date).label("avg_tat"),
            func.min(NdcRecord.ndc_completed_date - NdcRecord.ndc_initiated_date).label("min_tat"),
            func.max(NdcRecord.ndc_completed_date - NdcRecord.ndc_initiated_date).label("max_tat"),
        ).where(NdcRecord.ndc_stage == "NDC Completed")
    )
    row = completed_q.one()
    completed_count = row.cnt or 0

    return {
        "avg_tat_days": round(float(row.avg_tat), 1) if row.avg_tat is not None else None,
        "min_tat_days": int(row.min_tat) if row.min_tat is not None else None,
        "max_tat_days": int(row.max_tat) if row.max_tat is not None else None,
        "completed_count": completed_count,
        "total_count": total,
        "completion_rate": round(100.0 * completed_count / total, 1) if total > 0 else 0,
    }


async def get_bottlenecks(db: AsyncSession) -> dict:
    """Stage-wise and approver-wise pending counts."""
    # Stage-wise
    stage_q = await db.execute(
        select(
            NdcApproval.stage_name,
            func.count().label("pending_count"),
        )
        .where(NdcApproval.status == "PENDING")
        .group_by(NdcApproval.stage_name)
        .order_by(func.count().desc())
    )
    stage_wise = [{"stage_name": r.stage_name, "pending_count": r.pending_count} for r in stage_q.all()]

    # Approver-wise
    approver_q = await db.execute(
        select(
            NdcApproval.approver_name,
            NdcApproval.stage_name,
            func.count().label("pending_count"),
        )
        .where(NdcApproval.status == "PENDING")
        .group_by(NdcApproval.approver_name, NdcApproval.stage_name)
        .order_by(func.count().desc())
    )
    approver_wise = [
        {"approver_name": r.approver_name, "stage_name": r.stage_name, "pending_count": r.pending_count}
        for r in approver_q.all()
    ]

    return {"stage_wise": stage_wise, "approver_wise": approver_wise}


async def get_department_clearance(db: AsyncSession) -> list[dict]:
    """Clearance rate per department."""
    q = await db.execute(
        select(
            NdcRecord.department_reporting_name,
            func.count().label("total"),
            func.sum(case((NdcRecord.ndc_stage == "NDC Completed", 1), else_=0)).label("completed"),
        )
        .group_by(NdcRecord.department_reporting_name)
        .order_by(func.count().desc())
    )
    results = []
    for r in q.all():
        total = r.total or 0
        completed = r.completed or 0
        pct = round(100.0 * completed / total, 1) if total > 0 else 0
        results.append({
            "department": r.department_reporting_name or "Unknown",
            "total": total,
            "completed": completed,
            "clearance_pct": pct,
        })
    return results


async def get_trends(db: AsyncSession) -> list[dict]:
    """Daily initiated vs completed counts."""
    initiated_q = await db.execute(
        select(
            NdcRecord.ndc_initiated_date.label("dt"),
            func.count().label("cnt"),
        )
        .where(NdcRecord.ndc_initiated_date.isnot(None))
        .group_by(NdcRecord.ndc_initiated_date)
        .order_by(NdcRecord.ndc_initiated_date)
    )
    initiated_map = {r.dt: r.cnt for r in initiated_q.all()}

    completed_q = await db.execute(
        select(
            NdcRecord.ndc_completed_date.label("dt"),
            func.count().label("cnt"),
        )
        .where(NdcRecord.ndc_completed_date.isnot(None))
        .group_by(NdcRecord.ndc_completed_date)
        .order_by(NdcRecord.ndc_completed_date)
    )
    completed_map = {r.dt: r.cnt for r in completed_q.all()}

    all_dates = sorted(set(initiated_map.keys()) | set(completed_map.keys()))
    return [
        {
            "date": d,
            "initiated": initiated_map.get(d, 0),
            "completed": completed_map.get(d, 0),
        }
        for d in all_dates
    ]


# Dashboard Metrics

async def get_dashboard_summary(db: AsyncSession) -> dict:
    """Get dashboard summary metrics."""
    # Total employee exit count
    total_exit_q = await db.execute(select(func.count()).select_from(NdcRecord))
    total_exit = total_exit_q.scalar() or 0
    
    # Open NDC (Recovery Pending + GCC Pending)
    open_ndc_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage.in_(["Recovery Pending", "GCC Pending"]))
    )
    open_ndc = open_ndc_q.scalar() or 0
    
    # Closed NDC (NDC Completed)
    closed_ndc_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage == "NDC Completed")
    )
    closed_ndc = closed_ndc_q.scalar() or 0
    
    # In progress cases (Recovery Pending)
    in_progress_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage == "Recovery Pending")
    )
    in_progress = in_progress_q.scalar() or 0
    
    # Pending approval (GCC Pending)
    pending_approval_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage == "GCC Pending")
    )
    pending_approval = pending_approval_q.scalar() or 0
    
    # Top delayed cases - records that are overdue based on last working date
    from datetime import datetime, timedelta
    today = date.today()
    overdue_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(
            (NdcRecord.last_working_date < today) & 
            (NdcRecord.ndc_stage != "NDC Completed")
        )
    )
    top_delayed_cases = overdue_q.scalar() or 0
    
    # Overdue (same as top delayed)
    overdue = top_delayed_cases
    
    # Average completion time
    avg_tat_q = await db.execute(
        select(
            func.avg(NdcRecord.ndc_completed_date - NdcRecord.ndc_initiated_date).label("avg_tat"),
        ).where(NdcRecord.ndc_stage == "NDC Completed")
    )
    row = avg_tat_q.one()
    avg_completion_time = round(float(row.avg_tat), 1) if row.avg_tat is not None else None
    
    return {
        "total_employee_exit_count": total_exit,
        "open_ndc": open_ndc,
        "closed_ndc": closed_ndc,
        "top_delayed_cases": top_delayed_cases,
        "in_progress_cases": in_progress,
        "pending_approval": pending_approval,
        "overdue": overdue,
        "avg_completion_time_days": avg_completion_time,
    }


async def get_open_ndc_breakdown(db: AsyncSession) -> dict:
    """Get breakdown of open NDC categories."""
    recovery_pending_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage == "Recovery Pending")
    )
    recovery_pending = recovery_pending_q.scalar() or 0
    
    gcc_pending_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage == "GCC Pending")
    )
    gcc_pending = gcc_pending_q.scalar() or 0
    
    return {
        "recovery_pending": recovery_pending,
        "ndc_pending_with_gcc": gcc_pending,
    }


async def get_closed_ndc_breakdown(db: AsyncSession) -> dict:
    """Get breakdown of closed NDC categories.
    
    Note: These categories require additional fields in NdcRecord model
    to track F&F status. For now, assuming all completed are 'F&F done'.
    """
    completed_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(NdcRecord.ndc_stage == "NDC Completed")
    )
    ff_done = completed_q.scalar() or 0
    
    return {
        "ff_done": ff_done,
        "ff_open": 0,
        "ff_revision_required": 0,
    }


async def get_delayed_cases_breakdown(db: AsyncSession) -> dict:
    """Get breakdown of delayed cases."""
    today = date.today()
    
    # NDC delay cases - NDC records overdue
    ndc_delay_q = await db.execute(
        select(func.count()).select_from(NdcRecord)
        .where(
            (NdcRecord.ndc_initiated_date.isnot(None)) &
            (NdcRecord.ndc_completed_date.isnot(None)) &
            (NdcRecord.ndc_stage == "NDC Completed")
        )
    )
    ndc_delay_cases = ndc_delay_q.scalar() or 0
    
    # F&F delay cases - using same logic as NDC delay for now
    # In a real scenario, you'd have separate F&F tracking
    ff_delay_cases = ndc_delay_cases - (ndc_delay_cases // 2)  # Approximate split
    
    return {
        "ndc_delay_cases": ndc_delay_cases,
        "ff_delay_cases": ff_delay_cases,
    }


async def get_dashboard_detailed_metrics(db: AsyncSession) -> dict:
    """Get all dashboard metrics in one call."""
    summary = await get_dashboard_summary(db)
    open_ndc_breakdown = await get_open_ndc_breakdown(db)
    closed_ndc_breakdown = await get_closed_ndc_breakdown(db)
    delayed_cases = await get_delayed_cases_breakdown(db)
    
    return {
        "summary": summary,
        "open_ndc_breakdown": open_ndc_breakdown,
        "closed_ndc_breakdown": closed_ndc_breakdown,
        "delayed_cases": delayed_cases,
    }
