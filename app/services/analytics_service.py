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
