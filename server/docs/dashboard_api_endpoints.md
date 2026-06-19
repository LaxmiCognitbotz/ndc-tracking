# Dashboard API Endpoints

This document describes the new dashboard API endpoints created to support the NDC Tracking dashboard metrics.

## Overview

The dashboard provides comprehensive metrics for NDC (Notice of Deemed Compliance) tracking, including:

- Key performance indicators (KPIs)
- NDC stage breakdown
- Delayed case tracking
- Completion time analytics

## Base URL

All endpoints are prefixed with `/analytics/dashboard`

## Authentication

All endpoints require JWT authentication via the `Authorization` header:

```
Authorization: Bearer <token>
```

---

## Endpoints

### 1. Dashboard Summary

**Endpoint:** `GET /analytics/dashboard/summary`

**Description:** Get high-level dashboard metrics with all key KPIs.

**Response Model:**

```json
{
  "total_employee_exit_count": 16,
  "open_ndc": 11,
  "closed_ndc": 5,
  "top_delayed_cases": 10,
  "in_progress_cases": 1,
  "pending_approval": 10,
  "overdue": 10,
  "avg_completion_time_days": 3.0
}
```

**Field Descriptions:**

- `total_employee_exit_count`: Total number of NDC records in the system
- `open_ndc`: Count of records in "Recovery Pending" or "GCC Pending" stages
- `closed_ndc`: Count of records in "NDC Completed" stage
- `top_delayed_cases`: Count of records overdue past their last working date
- `in_progress_cases`: Count of records in "Recovery Pending" stage
- `pending_approval`: Count of records in "GCC Pending" stage awaiting GCC HR approval
- `overdue`: Count of records past their last working date (same as top_delayed_cases)
- `avg_completion_time_days`: Average turnaround time (TAT) in days for completed NDCs

---

### 2. Open NDC Categories

**Endpoint:** `GET /analytics/dashboard/open-ndc`

**Description:** Get breakdown of open NDC cases by category.

**Response Model:**

```json
{
  "recovery_pending": 9,
  "ndc_pending_with_gcc": 10
}
```

**Field Descriptions:**

- `recovery_pending`: NDCs in "Recovery Pending" stage (being recovered)
- `ndc_pending_with_gcc`: NDCs in "GCC Pending" stage (awaiting GCC HR approval)

---

### 3. Closed NDC Categories

**Endpoint:** `GET /analytics/dashboard/closed-ndc`

**Description:** Get breakdown of closed NDC cases by F&F (Final & Follow-up) status.

**Response Model:**

```json
{
  "ff_done": 5,
  "ff_open": 0,
  "ff_revision_required": 0
}
```

**Field Descriptions:**

- `ff_done`: F&F process completed
- `ff_open`: F&F process in progress
- `ff_revision_required`: F&F cases requiring revision

**Note:** Requires additional F&F status tracking fields in the database schema. Currently, all completed NDCs are counted as `ff_done`.

---

### 4. Delayed Cases

**Endpoint:** `GET /analytics/dashboard/delayed-cases`

**Description:** Get breakdown of delayed cases by type.

**Response Model:**

```json
{
  "ndc_delay_cases": 10,
  "ff_delay_cases": 9
}
```

**Field Descriptions:**

- `ndc_delay_cases`: NDC processing delayed past expected completion date
- `ff_delay_cases`: F&F processing delayed past expected completion date

---

### 5. Detailed Dashboard Metrics

**Endpoint:** `GET /analytics/dashboard/detailed`

**Description:** Get all dashboard metrics in a single call (combines summary, open NDC, closed NDC, and delayed cases).

**Response Model:**

```json
{
  "summary": {
    "total_employee_exit_count": 16,
    "open_ndc": 11,
    "closed_ndc": 5,
    "top_delayed_cases": 10,
    "in_progress_cases": 1,
    "pending_approval": 10,
    "overdue": 10,
    "avg_completion_time_days": 3.0
  },
  "open_ndc_breakdown": {
    "recovery_pending": 9,
    "ndc_pending_with_gcc": 10
  },
  "closed_ndc_breakdown": {
    "ff_done": 5,
    "ff_open": 0,
    "ff_revision_required": 0
  },
  "delayed_cases": {
    "ndc_delay_cases": 10,
    "ff_delay_cases": 9
  }
}
```

---

## Usage Examples

### Get Dashboard Summary

```bash
curl -X GET "http://localhost:8000/analytics/dashboard/summary" \
  -H "Authorization: Bearer your_token_here"
```

### Get Open NDC Breakdown

```bash
curl -X GET "http://localhost:8000/analytics/dashboard/open-ndc" \
  -H "Authorization: Bearer your_token_here"
```

### Get Detailed Metrics

```bash
curl -X GET "http://localhost:8000/analytics/dashboard/detailed" \
  -H "Authorization: Bearer your_token_here"
```

---

## Error Responses

All endpoints may return the following error responses:

### 401 Unauthorized

```json
{
  "detail": "Not authenticated"
}
```

**Cause:** Missing or invalid JWT token

### 422 Unprocessable Entity

```json
{
  "detail": "Validation error"
}
```

**Cause:** Invalid request parameters

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

**Cause:** Server-side error during metric calculation

---

## Implementation Details

### Service Layer

All metrics are calculated in `app/services/analytics_service.py`:

- `get_dashboard_summary()`: Main metrics calculation
- `get_open_ndc_breakdown()`: Open NDC category counts
- `get_closed_ndc_breakdown()`: Closed NDC category counts
- `get_delayed_cases_breakdown()`: Delayed case counts
- `get_dashboard_detailed_metrics()`: Combined metrics

### Database Queries

- All queries use `SQLAlchemy` ORM with async support
- Efficient grouping and aggregation using `func.count()`
- Filtered queries for specific NDC stages
- Date calculations for overdue detection

### Response Schemas

All response models are defined in `app/schemas/ndc.py`:

- `DashboardSummary`
- `OpenNdcBreakdown`
- `ClosedNdcBreakdown`
- `DelayedCasesBreakdown`
- `DashboardDetailedMetrics`

---

## Future Enhancements

1. **F&F Tracking**: Add separate F&F status field to `NdcRecord` model to properly track F&F workflow
2. **Date-based Filtering**: Add optional date range parameters to filter metrics by date range
3. **Department Filtering**: Add optional department parameter to filter metrics by department
4. **Cache**: Implement caching for frequently accessed metrics to reduce database load
5. **Historical Trends**: Add endpoints to track metric trends over time
6. **Export**: Add endpoints to export dashboard data in various formats (CSV, Excel)

---

## Project Structure

```
app/
├── routers/
│   └── analytics.py          # Dashboard endpoints
├── services/
│   └── analytics_service.py  # Dashboard metric calculations
├── schemas/
│   └── ndc.py               # Response schemas
└── models/
    ├── ndc_record.py        # NDC record model
    └── ndc_approval.py      # NDC approval model
docs/
└── dashboard_api_endpoints.md  # This file
```

---

## Database Schema References

### NdcRecord Table

- `id`: Primary key
- `person_number`: Employee person number
- `employee_name`: Employee name
- `ndc_stage`: Current NDC stage ('Recovery Pending', 'GCC Pending', 'NDC Completed')
- `ndc_initiated_date`: When NDC process started
- `ndc_completed_date`: When NDC process completed
- `last_working_date`: Employee's last working date (used for overdue detection)

### NdcApproval Table

- `id`: Primary key
- `ndc_record_id`: Foreign key to NdcRecord
- `stage_name`: Approval stage name
- `status`: Current status ('PENDING', 'APPROVED', 'REJECTED')
- `approver_name`: Name of the approver
