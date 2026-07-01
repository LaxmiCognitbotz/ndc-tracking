* [ ] F&F (Full & Final) Management — KPI Logic & Schema Plan

## Overview

This document defines the complete technical plan for implementing the F&F (Full & Final Settlement) management module, including KPI counting logic, DMS Linkage Portal integration, TAT calculation, and the required database schema changes.

---

## Business Logic — Explained Step by Step

### Step 1 — Who is Eligible for F&F?

An employee record becomes eligible for the F&F workflow when **both** of the following NDC stages are completed:

| Condition                                | Description                                                 |
| ---------------------------------------- | ----------------------------------------------------------- |
| `ndc_stage = "NDC Completed"`          | The NDC stage has been cleared (all departments signed off) |
| `gcc_hr_approval_status = "Completed"` | The GCC HR stage approval is also completed                 |

> [!IMPORTANT]
> Both conditions must be true simultaneously. An employee with NDC Completed but GCC HR still pending is **NOT** eligible for F&F processing.

---

### Step 2 — KPI Definitions

#### `Total F&F In Process`

- **Definition:** Count of all employees where both NDC stage AND GCC HR stage are completed.
- **Logic:** `ndc_stage == "NDC Completed"` AND `gcc_hr_approval_status == "Completed"`
- **Current frontend key:** `fnfStats.total`
- **This is also the pool for `F&F Open`**

---

#### `F&F Open`

- **Definition:** Employees eligible for F&F (both stages completed) but whose F&F document has **NOT yet been confirmed** in the DMS Linkage Portal.
- **Logic:** Eligible employees where `is_fnf_completed = false` AND `fnf_document` is blank/null
- **Meaning:** HR still needs to search the DMS portal for their F&F document.
- **Current frontend key:** `fnfStats.open`

---

#### `F&F Completed`

- **Definition:** Count of employees where the HR user has **manually confirmed** that an F&F document exists in the DMS Linkage Portal.
- **Logic:** Eligible employees where `is_fnf_completed = true` (toggled by user action)
- **Source:** Action list — user manually searches DMS portal → finds document → clicks "Completed"
- **Current frontend key:** `fnfStats.done`

---

#### `F&F Revision Required`

- **Definition:** Count of employees where **multiple F&F documents** were found in the DMS Linkage Portal (indicating a revision scenario).
- **Logic:** Eligible employees where `is_fnf_revision = true` (toggled when multiple docs found)
- **Source:** When user searches DMS and finds >1 F&F document → system flags `is_fnf_revision = true`
- **Current frontend key:** `fnfStats.revision`

---

#### `F&F TAT (Turnaround Time)`

- **Definition:** Average number of days from the GCC HR stage initiation date to the F&F completion date.
- **Formula:** `F&F TAT = fnf_completed_date − gcc_initiate_date`
- **Unit:** Days
- **Current frontend key:** `fnfStats.avgTAT`

> [!NOTE]
> `gcc_initiate_date` maps to `stage_started_at` in the `ndc_approvals` table where `stage_name = "GCC HR"`.

---

### Step 3 — Action Flow (User-Triggered)

```
[Eligible Employee Pool]
         ↓
HR User opens F&F Management page
         ↓
HR searches DMS Linkage Portal by Employee ID
         ↓
    ┌──────────────┐
    │ Doc Found?   │
    └──────┬───────┘
           │
    ┌──────┴─────────────────┐
    │                        │
  1 doc found           Multiple docs found
    ↓                        ↓
  Click "Completed"      Click "Revision Required"
  is_fnf_completed=true  is_fnf_revision=true
  fnf_completed_date=today
```

---

### Step 4 — Department Date Propagation (AI Boolean Trigger)

When `is_fnf_completed` is set to `true` for a record, the system should:

1. **Check** each department approval stage (RM, IT, ABEX, Telecom, Store, Safety, Administration, Security, HR, GCC HR, Final ABEX).
2. For any department where:
   - `status` is blank/null, **AND**
   - `stage_completed_at` date is blank/null
3. **Auto-update** that department's `stage_completed_at` to the same date as the F&F completion date (`fnf_completed_date`).

This propagation is triggered **automatically** when the `is_fnf_completed` boolean flips to `true` — it acts like a database trigger driven by the AI/backend logic.

> [!IMPORTANT]
> This update only applies to departments where **both** status AND date are missing. It does not overwrite existing data.

---

## Schema Changes Required

### A. `ndc_records` Table — New Columns

The following columns need to be added to the `NdcRecord` SQLAlchemy model and the database:

| Column                 | Type        | Default   | Description                                   |
| ---------------------- | ----------- | --------- | --------------------------------------------- |
| `is_fnf_completed`   | `Boolean` | `false` | True when HR confirms F&F doc found in DMS    |
| `is_fnf_revision`    | `Boolean` | `false` | True when multiple F&F docs found in DMS      |
| `fnf_completed_date` | `Date`    | `null`  | Date when HR confirmed F&F completion         |
| `gcc_initiate_date`  | `Date`    | `null`  | GCC HR stage start date (for TAT calculation) |
| `fnf_document_count` | `Integer` | `0`     | Number of F&F documents found in DMS portal   |

> [!NOTE]
> `gcc_initiate_date` can be derived from `ndc_approvals.stage_started_at` where `stage_name = "GCC HR"`, but storing it as a denormalized field on the record makes KPI queries simpler and faster.

---

### B. `CommonNDCRecord` Pydantic Schema — New Fields

**File:** `server/app/schemas/common.py`

```Python
is_fnf_completed: bool = False
is_fnf_revision: bool = False
fnf_completed_date: str = ""
gcc_initiate_date: str = ""
fnf_document_count: int = 0
```

---

### C. `NdcRecord` SQLAlchemy Model — New Columns

**File:** `server/app/models/ndc_record.py`

```python
from sqlalchemy import Boolean

is_fnf_completed  = Column(Boolean, default=False, nullable=False, server_default="0")
is_fnf_revision   = Column(Boolean, default=False, nullable=False, server_default="0")
fnf_completed_date = Column(Date, nullable=True)
gcc_initiate_date  = Column(Date, nullable=True)
fnf_document_count = Column(Integer, default=0, nullable=False, server_default="0")
```

---

### D. TypeScript `NDCRecord` Interface — New Fields

**File:** `client/src/types/index.ts`

```typescript
isFnfCompleted: boolean;
isFnfRevision: boolean;
fnfCompletedDate: string;
gccInitiateDate: string;
fnfDocumentCount: number;
```

---

## KPI Query Logic Changes

### File: `server/app/services/analytics_service.py`

The `get_closed_ndc_breakdown()` function currently returns hardcoded zeroes for F&F fields. It needs to be rewritten to query real data:

```python
# F&F Completed → is_fnf_completed = true
ff_done = COUNT(ndc_records WHERE ndc_stage="NDC Completed" AND is_fnf_completed=true)

# F&F Open → eligible but not yet confirmed
ff_open = COUNT(ndc_records WHERE ndc_stage="NDC Completed" AND is_fnf_completed=false AND is_fnf_revision=false)

# F&F Revision Required → multiple docs found
ff_revision = COUNT(ndc_records WHERE is_fnf_revision=true)
```

### TAT Calculation

```python
# F&F TAT = fnf_completed_date - gcc_initiate_date
avg_tat = AVG(fnf_completed_date - gcc_initiate_date)
         WHERE is_fnf_completed = true
         AND fnf_completed_date IS NOT NULL
         AND gcc_initiate_date IS NOT NULL
```

---

## API Endpoint Changes

### File: `server/app/routers/common_api.py`

The `PUT /api/v1/ndc-records/{id}` endpoint needs to handle:

1. **Update `is_fnf_completed`** → when set to `true`, also set `fnf_completed_date = today`
2. **Update `is_fnf_revision`** → when set to `true`
3. **Update `fnf_document_count`** → count of docs found in DMS
4. **Trigger department date propagation** → auto-fill blank department dates on `is_fnf_completed = true`

---

## Frontend KPI Calculation Changes

### File: `client/src/features/fnf/FNFManagement.tsx`

The `fnfStats` `useMemo` needs to be updated:

| KPI          | Old Logic                               | New Logic                                                                               |
| ------------ | --------------------------------------- | --------------------------------------------------------------------------------------- |
| `total`    | All records with non-empty`fnfStatus` | Records where`ndcStage == "NDC Completed"` AND `gccHrApprovalStatus == "Completed"` |
| `done`     | `fnfStatus == "Done" \| "Completed"`   | `isFnfCompleted == true`                                                              |
| `open`     | `fnfStatus == "Open"`                 | `isFnfCompleted == false` AND `isFnfRevision == false`                              |
| `revision` | `fnfStatus == "Revision Required"`    | `isFnfRevision == true`                                                               |
| `avgTAT`   | `ndcCompletedDate - lastWorkingDate`  | `fnfCompletedDate - gccInitiateDate`                                                  |

---

## Department Date Propagation Logic (Backend)

**Trigger:** When `is_fnf_completed` is set to `true`
**Location:** `server/app/routers/common_api.py` (in the PUT handler) or a dedicated service function

```python
async def propagate_department_dates(record_id: int, fnf_completed_date: date, db: AsyncSession):
    """
    For all department approvals on this record where status AND date are both blank,
    auto-fill the stage_completed_at with the fnf_completed_date.
    """
    approvals = await db.execute(
        select(NdcApproval)
        .where(NdcApproval.ndc_record_id == record_id)
        .where(
            (NdcApproval.status == None) | (NdcApproval.status == "")
        )
        .where(NdcApproval.stage_completed_at == None)
    )
    for approval in approvals.scalars().all():
        approval.stage_completed_at = fnf_completed_date
    await db.commit()
```

---

## File-by-File Change Summary

| File                                          | Change Type | Description                                                                                                                        |
| --------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `server/app/models/ndc_record.py`           | MODIFY      | Add 5 new columns:`is_fnf_completed`, `is_fnf_revision`, `fnf_completed_date`, `gcc_initiate_date`, `fnf_document_count` |
| `server/app/schemas/common.py`              | MODIFY      | Add 5 new fields to`CommonNDCRecord` schema                                                                                      |
| `server/app/schemas/ndc.py`                 | MODIFY      | Update`ClosedNdcBreakdown` schema to include proper F&F TAT field                                                                |
| `server/app/services/analytics_service.py`  | MODIFY      | Fix`get_closed_ndc_breakdown()` and `get_delayed_cases_breakdown()` with real F&F queries                                      |
| `server/app/routers/common_api.py`          | MODIFY      | Add PUT endpoint for F&F status update + department date propagation logic                                                         |
| `client/src/types/index.ts`                 | MODIFY      | Add 5 new TypeScript fields to`NDCRecord` interface                                                                              |
| `client/src/features/fnf/FNFManagement.tsx` | MODIFY      | Fix KPI`fnfStats` logic and `handleAction` to use new boolean fields                                                           |
| `server/init_db.py`                         | MODIFY      | Add`ALTER TABLE` migrations for new columns (or note for fresh DB init)                                                          |

---

## Open Questions

> [!IMPORTANT]
> **Q1: DMS Linkage Portal Integration**
> Is the DMS Linkage Portal an internal API that the backend can call, or is the F&F document search always done **manually** by the HR user outside the system? If it is manual, the backend only needs to accept the user's input (document count, completion flag) and does not need to make any outbound API calls.

> [!IMPORTANT]
> **Q2: GCC Initiate Date Source**
> Should `gcc_initiate_date` be copied from `ndc_approvals.stage_started_at` (where `stage_name = "GCC HR"`) at the time the record becomes eligible, or should it always be looked up dynamically from the approvals table at query time?

> [!IMPORTANT]
> **Q3: Database Migration Strategy**
> The project currently uses SQLite (`ndc_tracking.db`). Should we run raw `ALTER TABLE` SQL to add the new columns to the existing database, or should we drop and re-create the DB (acceptable only if test data)?

> [!NOTE]
> **Q4: `fnfStatus` Field Deprecation**
> The existing `fnf_status: str` field in `CommonNDCRecord` and `NDCRecord` currently drives the entire F&F display. After this change, `is_fnf_completed` and `is_fnf_revision` booleans will be the source of truth. The old `fnf_status` string field can be kept for backward compatibility or removed.
