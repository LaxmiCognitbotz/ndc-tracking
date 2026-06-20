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


async def get_status_pie_data(db: AsyncSession, filters) -> dict:
    """Get counts of NDC records grouped by status categories (Completed, Pending, In Progress)."""
    from app.routers.ndc import _build_filtered_query
    
    if filters.approval_stage and filters.approval_stage.upper() != 'ALL':
        import copy
        base_filters = copy.copy(filters)
        base_filters.approval_stage = None
        base_filters.approval_status = None
        base_filters.approver_name = None
        
        records_subq = _build_filtered_query(base_filters).subquery()
        
        query = select(
            func.sum(case((NdcApproval.status == 'COMPLETED', 1), else_=0)).label("completed"),
            func.sum(case((NdcApproval.status.in_(['PENDING', 'DEPENDENT']), 1), else_=0)).label("pending"),
            func.sum(case((NdcApproval.status == 'IN_PROGRESS', 1), else_=0)).label("in_progress"),
            func.count(NdcApproval.id).label("total")
        ).join(
            records_subq, NdcApproval.ndc_record_id == records_subq.c.id
        ).where(
            NdcApproval.stage_name == filters.approval_stage
        )
        
        result = await db.execute(query)
        row = result.one()
        
        return {
            "completed": int(row.completed) if row.completed is not None else 0,
            "pending": int(row.pending) if row.pending is not None else 0,
            "in_progress": int(row.in_progress) if row.in_progress is not None else 0,
            "total": int(row.total) if row.total is not None else 0,
        }
    else:
        subq = _build_filtered_query(filters).subquery()
        
        query = select(
            func.sum(case((subq.c.ndc_stage == 'NDC Completed', 1), else_=0)).label("completed"),
            func.sum(case((subq.c.ndc_stage == 'Recovery Pending', 1), else_=0)).label("pending"),
            func.sum(case((subq.c.ndc_stage == 'GCC Pending', 1), else_=0)).label("in_progress"),
            func.count(subq.c.id).label("total")
        )
        
        result = await db.execute(query)
        row = result.one()
        
        return {
            "completed": int(row.completed) if row.completed is not None else 0,
            "pending": int(row.pending) if row.pending is not None else 0,
            "in_progress": int(row.in_progress) if row.in_progress is not None else 0,
            "total": int(row.total) if row.total is not None else 0,
        }


async def get_ndc_analysis_data(db: AsyncSession, filters) -> dict:
    """Get counts of completed NDC records grouped by completion delay buckets (relative to LWD)."""
    from app.routers.ndc import _build_filtered_query
    
    if filters.approval_stage and filters.approval_stage.upper() != 'ALL':
        import copy
        base_filters = copy.copy(filters)
        base_filters.approval_stage = None
        base_filters.approval_status = None
        base_filters.approver_name = None
        
        records_subq = _build_filtered_query(base_filters).where(
            NdcRecord.ndc_stage == 'NDC Completed',
            NdcRecord.last_working_date.isnot(None),
            NdcRecord.ndc_completed_date.isnot(None)
        ).subquery()
        
        delay = records_subq.c.ndc_completed_date - records_subq.c.last_working_date
        
        query = select(
            func.sum(case((delay <= 0, 1), else_=0)).label("on_due_date"),
            func.sum(case(((delay >= 1) & (delay <= 2), 1), else_=0)).label("within_2_days"),
            func.sum(case(((delay >= 3) & (delay <= 7), 1), else_=0)).label("three_to_seven_days"),
            func.sum(case(((delay >= 8) & (delay <= 30), 1), else_=0)).label("seven_to_thirty_days"),
            func.sum(case((delay > 30, 1), else_=0)).label("more_than_thirty_days"),
            func.count(NdcApproval.id).label("total")
        ).join(
            records_subq, NdcApproval.ndc_record_id == records_subq.c.id
        ).where(
            NdcApproval.stage_name == filters.approval_stage,
            NdcApproval.status == 'COMPLETED'
        )
        
        result = await db.execute(query)
        row = result.one()
        
        return {
            "on_due_date": int(row.on_due_date) if row.on_due_date is not None else 0,
            "within_2_days": int(row.within_2_days) if row.within_2_days is not None else 0,
            "three_to_seven_days": int(row.three_to_seven_days) if row.three_to_seven_days is not None else 0,
            "seven_to_thirty_days": int(row.seven_to_thirty_days) if row.seven_to_thirty_days is not None else 0,
            "more_than_thirty_days": int(row.more_than_thirty_days) if row.more_than_thirty_days is not None else 0,
            "total": int(row.total) if row.total is not None else 0,
        }
    else:
        # Build subquery for completed records
        subq = _build_filtered_query(filters).where(
            NdcRecord.ndc_stage == 'NDC Completed',
            NdcRecord.last_working_date.isnot(None),
            NdcRecord.ndc_completed_date.isnot(None)
        ).subquery()
        delay = subq.c.ndc_completed_date - subq.c.last_working_date
        
        query = select(
            func.sum(case((delay <= 0, 1), else_=0)).label("on_due_date"),
            func.sum(case(((delay >= 1) & (delay <= 2), 1), else_=0)).label("within_2_days"),
            func.sum(case(((delay >= 3) & (delay <= 7), 1), else_=0)).label("three_to_seven_days"),
            func.sum(case(((delay >= 8) & (delay <= 30), 1), else_=0)).label("seven_to_thirty_days"),
            func.sum(case((delay > 30, 1), else_=0)).label("more_than_thirty_days"),
            func.count(subq.c.id).label("total")
        )
        
        result = await db.execute(query)
        row = result.one()
        
        return {
            "on_due_date": int(row.on_due_date) if row.on_due_date is not None else 0,
            "within_2_days": int(row.within_2_days) if row.within_2_days is not None else 0,
            "three_to_seven_days": int(row.three_to_seven_days) if row.three_to_seven_days is not None else 0,
            "seven_to_thirty_days": int(row.seven_to_thirty_days) if row.seven_to_thirty_days is not None else 0,
            "more_than_thirty_days": int(row.more_than_thirty_days) if row.more_than_thirty_days is not None else 0,
            "total": int(row.total) if row.total is not None else 0,
        }



async def get_approval_analysis_data(db: AsyncSession, filters) -> list[dict]:
    """Get counts of completed and pending approvals grouped by approval stage/department."""
    from app.routers.ndc import _build_filtered_query
    
    import copy
    base_filters = copy.copy(filters)
    base_filters.approval_stage = None
    
    # 1. Build the filtered subquery for NdcRecord ids matching the filters
    record_subq = _build_filtered_query(base_filters).subquery()
    
    # 2. Query the NdcApproval table, joining on the filtered record subquery
    query = (
        select(
            NdcApproval.stage_name,
            func.sum(case((NdcApproval.status == 'COMPLETED', 1), else_=0)).label("completed"),
            func.sum(case((NdcApproval.status == 'PENDING', 1), else_=0)).label("pending")
        )
        .join(record_subq, NdcApproval.ndc_record_id == record_subq.c.id)
    )
    
    if filters.approval_stage and filters.approval_stage.upper() != 'ALL':
        query = query.where(NdcApproval.stage_name == filters.approval_stage)
        
    query = query.group_by(NdcApproval.stage_name)

    
    result = await db.execute(query)
    rows = result.all()
    
    # Map stage_name to its sequence order from status_mapper
    from app.utils.status_mapper import APPROVAL_STAGES
    stage_order = {stage[0]: stage[3] for stage in APPROVAL_STAGES}
    
    # Map raw rows to a list of dicts
    data = []
    for r in rows:
        stage_name = r.stage_name
        data.append({
            "stage_name": stage_name,
            "completed": int(r.completed) if r.completed is not None else 0,
            "pending": int(r.pending) if r.pending is not None else 0,
            "sequence_order": stage_order.get(stage_name, 99)
        })
    
    # Sort by sequence_order so the frontend receives them in sequence order
    data.sort(key=lambda x: x["sequence_order"])
    return data


async def get_monthly_trend_data(db: AsyncSession, filters) -> list[dict]:
    """Get monthly trend of initiated vs completed clearance requests."""
    from app.routers.ndc import _build_filtered_query
    
    # 1. Get the filtered records query
    query = _build_filtered_query(filters)
    
    # Execute and get all records matching the filters
    result = await db.execute(query)
    records = result.scalars().all()
    
    total_records = len(records)
    if total_records == 0:
        return []
        
    # Group initiated and completed by month
    from collections import defaultdict
    # Represent months as (year, month) to sort them easily
    initiated_counts = defaultdict(int)
    completed_counts = defaultdict(int)
    
    all_months = set()
    
    for r in records:
        if r.ndc_initiated_date:
            y_m = (r.ndc_initiated_date.year, r.ndc_initiated_date.month)
            initiated_counts[y_m] += 1
            all_months.add(y_m)
        if r.ndc_completed_date:
            y_m = (r.ndc_completed_date.year, r.ndc_completed_date.month)
            completed_counts[y_m] += 1
            all_months.add(y_m)
            
    if not all_months:
        return []
        
    # Sort the months chronologically
    sorted_months = sorted(list(all_months))
    
    # Generate the result list
    month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 
                   7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
                   
    data = []
    for y_m in sorted_months:
        year, month = y_m
        month_label = f"{month_names[month]} {year}"
        
        init_count = initiated_counts[y_m]
        comp_count = completed_counts[y_m]
        
        init_pct = round((init_count / total_records) * 100, 1) if total_records > 0 else 0.0
        comp_pct = round((comp_count / total_records) * 100, 1) if total_records > 0 else 0.0
        
        data.append({
            "month": month_label,
            "initiated": init_count,
            "completed": comp_count,
            "initiated_pct": init_pct,
            "completed_pct": comp_pct
        })
        
    return data


async def get_closed_tat_analysis_data(db: AsyncSession, filters) -> dict:
    """Get counts of completed NDC records grouped by TAT duration buckets (completed - initiated)."""
    from app.routers.ndc import _build_filtered_query
    
    # Build subquery for completed records matching the filters
    subq = _build_filtered_query(filters).where(NdcRecord.ndc_stage == 'NDC Completed').subquery()
    tat = subq.c.ndc_completed_date - subq.c.ndc_initiated_date
    
    query = select(
        func.sum(case(((tat >= 0) & (tat <= 7), 1), else_=0)).label("within_7_days"),
        func.sum(case(((tat >= 8) & (tat <= 15), 1), else_=0)).label("within_15_days"),
        func.sum(case(((tat >= 16) & (tat <= 30), 1), else_=0)).label("within_30_days"),
        func.sum(case((tat > 30, 1), else_=0)).label("more_than_30_days"),
        func.count(subq.c.id).label("total")
    )
    
    result = await db.execute(query)
    row = result.one()
    
    return {
        "within_7_days": int(row.within_7_days) if row.within_7_days is not None else 0,
        "within_15_days": int(row.within_15_days) if row.within_15_days is not None else 0,
        "within_30_days": int(row.within_30_days) if row.within_30_days is not None else 0,
        "more_than_30_days": int(row.more_than_30_days) if row.more_than_30_days is not None else 0,
        "total": int(row.total) if row.total is not None else 0,
    }


async def get_top_delayed_cases(db: AsyncSession, filters, category: str = "All", limit: int = 10) -> list[dict]:
    """Get the top delayed pending cases grouped by NDC and F&F categories."""
    from app.routers.ndc import _build_filtered_query
    
    # 1. Get filtered query for pending records with last_working_date
    query = _build_filtered_query(filters).where(
        NdcRecord.ndc_stage != 'NDC Completed',
        NdcRecord.last_working_date.isnot(None)
    ).order_by(NdcRecord.last_working_date.asc())
    
    # Execute query
    result = await db.execute(query)
    records = result.scalars().all()
    
    from datetime import date
    today = date.today()
    
    data = []
    for r in records:
        delay = (today - r.last_working_date).days
        # Only include positive delays (cases where last working date has passed)
        if delay <= 0:
            continue
            
        # Add NDC Pending row if requested
        if category in ("All", "NDC"):
            data.append({
                "person_number": r.person_number,
                "employee_name": r.employee_name,
                "department": r.department_reporting_name or r.department,
                "last_working_date": r.last_working_date,
                "category": "NDC Pending",
                "delay_days": delay
            })
            
        # Add F&F Pending row if requested
        if category in ("All", "F&F"):
            data.append({
                "person_number": r.person_number,
                "employee_name": r.employee_name,
                "department": r.department_reporting_name or r.department,
                "last_working_date": r.last_working_date,
                "category": "F&F Pending",
                "delay_days": delay
            })
            
    # Sort the final combined list by:
    # 1. delay_days descending
    # 2. category (NDC Pending before F&F Pending)
    # 3. employee_name alphabetically
    data.sort(key=lambda x: (-x["delay_days"], x["category"] == "F&F Pending", x["employee_name"]))
    
    # Apply limit
    return data[:limit]


async def get_approval_departments(db: AsyncSession) -> list[str]:
    """Get distinct approval stage names sorted by sequence order."""
    from sqlalchemy import distinct
    from app.models.ndc_approval import NdcApproval
    from app.utils.status_mapper import APPROVAL_STAGES
    
    result = await db.execute(select(distinct(NdcApproval.stage_name)))
    stages = result.scalars().all()
    
    # Sort them using the order defined in APPROVAL_STAGES
    stage_order = {s[0]: s[3] for s in APPROVAL_STAGES}
    stages_sorted = sorted(stages, key=lambda x: stage_order.get(x, 99))
    return ["All"] + stages_sorted







