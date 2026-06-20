# API Documentation & Response Structure

This document outlines the input parameters, headers, and JSON body structures for all endpoints in the NDC/GCC Workflow Tracking API.

---

## 1. Unified Response Structure

To make frontend consumption predictable and clean, the API wraps all standard JSON responses in a unified response envelope. **All response keys are serialized in standard `snake_case` matching the Python backend codebase.**

### Success Response Envelope

Standard success responses use the following envelope (with boolean status):

```json
{
  "status": true,
  "data": {
    /* Application-specific payload */
  },
  "message": null
}
```

### List / Pagination Success Envelope

When list operations are requested, the response data contains a JSON array, accompanied by pagination metrics in a `meta` block:

```json
{
  "status": true,
  "data": [
    {
      /* Array item 1 */
    },
    {
      /* Array item 2 */
    }
  ],
  "message": null,
  "meta": {
    "total": 120,      // Total records matching filter
    "page": 1,         // Current page number
    "page_size": 10,   // Number of records per page
    "pages": 12        // Total pages available
  }
}
```

### Error Response Envelope

If an exception or validation check fails, the API returns semantic HTTP codes (e.g., `400`, `401`, `403`, `422`, `500`) and the following standardized body (with boolean status):

```json
{
  "status": false,
  "data": null,
  "message": "Error description message"
}
```

### Form Validation Error Envelope (HTTP 422)

If a client request fails Pydantic schema validation, the fields are normalized in `snake_case` and returned under `data.errors`:

```json
{
  "status": false,
  "data": {
    "errors": [
      {
        "field": "person_number",
        "message": "field required"
      }
    ]
  },
  "message": "Validation failed"
}
```

---

## 2. API Endpoints

### 2.1 Auth & Health Checks

#### `POST /auth/dev-token`

* **Description**: Generates an admin JWT token for local/testing purposes.
* **Input**:
  - Query Parameter: `username` (string, defaults to `admin`).
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
      "token_type": "bearer"
    },
    "message": null
  }
  ```

#### `GET /health`

* **Description**: Simple ping to verify server status.
* **Input**: None.
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "status": "ok"
    },
    "message": null
  }
  ```

---

### 2.2 Ingest Service

#### `POST /ingest/upload-excel`

* **Description**: Ingests an Excel workflow tracking spreadsheet (`.xlsb`, `.xlsx`, `.xls`). Performs validation, maps statuses, calculates metrics, and updates records via upsert on `person_number`.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Body: Multipart Form Data containing `file` (Binary upload).
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "batch_id": 4,
      "records_processed": 40,
      "records_failed": 0,
      "status": "COMPLETED",
      "errors": []
    },
    "message": null
  }
  ```

#### `GET /ingest/batches`

* **Description**: Lists history of upload batches for audit trailing.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "id": 4,
        "file_name": "GCC_NDC_06_05.xlsb",
        "source_type": "EXCEL",
        "records_count": 40,
        "uploaded_by": "admin",
        "uploaded_at": "2026-06-05T09:47:00Z",
        "status": "COMPLETED",
        "error_message": null
      }
    ],
    "message": null
  }
  ```

---

### 2.3 NDC Records

#### `GET /ndc/records`

* **Description**: Returns a paginated, filterable list of active employee NDC clearance records.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (all optional):
    - `page` (int, default: `1`)
    - `page_size` (int, default: `20`)
    - `sort_by` (string, sortable fields: `ndc_initiated_date`, `person_number`, `employee_name`, `ndc_stage`, `last_working_date`, `ndc_completed_date`, `business_unit`, `location_city`)
    - `sort_order` (string, `asc` or `desc`)
    - `ndc_stage` (string)
    - `business_unit` (string)
    - `legal_employer` (string)
    - `location` (string)
    - `location_city` (string)
    - `department_reporting_name` (string)
    - `person_number` (int)
    - `employee_name` (string, partial search)
    - `ndc_initiated_from` (date, YYYY-MM-DD)
    - `ndc_initiated_to` (date, YYYY-MM-DD)
    - `pending_days_min` (int)
    - `pending_days_max` (int)
    - `approval_stage` (string)
    - `approval_status` (string)
    - `approver_name` (string, partial search)
    - `has_gcc_pending` (boolean)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "id": 1,
        "person_number": 10098,
        "employee_name": "Alice Smith",
        "business_unit": "GCC HR",
        "legal_employer": "XYZ Employer",
        "location": "GCC Location",
        "location_city": "Los Angeles",
        "department": "Engineering",
        "department_reporting_name": "Eng-Dev",
        "ndc_stage": "Recovery Pending",
        "resignation_date": "2026-05-01",
        "last_working_date": "2026-06-15",
        "ndc_assigned_date": "2026-05-02",
        "ndc_initiated_date": "2026-05-02",
        "ndc_completed_date": null,
        "created_by": "system",
        "source_file": "GCC_NDC_06_05.xlsb",
        "batch_id": 4,
        "created_at": "2026-06-05T09:47:00Z",
        "updated_at": "2026-06-05T09:47:00Z",
        "pending_days": 34,
        "tat_days": null,
        "days_to_lwd": 10
      }
    ],
    "message": null,
    "meta": {
      "total": 1,
      "page": 1,
      "page_size": 20,
      "pages": 1
    }
  }
  ```

#### `GET /ndc/records/{person_number}`

* **Description**: Fetches detail status of a single employee's clearances, including status on all 13 stages.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Path Parameter: `person_number` (int)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "id": 1,
      "person_number": 10098,
      "employee_name": "Alice Smith",
      "business_unit": "GCC HR",
      "ndc_stage": "Recovery Pending",
      "approvals": [
        {
          "stage_name": "Resignation Submission",
          "approver_name": "System",
          "status": "CLEARED",
          "sequence_order": 1
        },
        {
          "stage_name": "Line Manager Clearance",
          "approver_name": "Bob Jones",
          "status": "CLEARED",
          "sequenceOrder": 2
        },
        {
          "stage_name": "GCC HR",
          "approver_name": "GCC HR Admin",
          "status": "PENDING",
          "sequence_order": 11
        }
      ]
    },
    "message": null
  }
  ```

#### `GET /ndc/summary`

* **Description**: Returns quick overall dashboard counts.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "total_records": 105,
      "stage_counts": [
        {
          "stage": "Recovery Pending",
          "count": 45
        },
        {
          "stage": "NDC Completed",
          "count": 60
        }
      ],
      "total_pending": 45,
      "gcc_pending_count": 12
    },
    "message": null
  }
  ```

#### `GET /ndc/pending-bottlenecks`

* **Description**: Lists active bottlenecks ranked by stage pending volume.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "stage_name": "GCC HR",
        "pending_count": 12
      },
      {
        "stage_name": "Assets Recovery",
        "pending_count": 9
      }
    ],
    "message": null
  }
  ```

---

### 2.4 Analytics Service

#### `GET /analytics/tat`

* **Description**: Returns overall TAT statistics for completed clearances.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "avg_tat_days": 12.5,
      "min_tat_days": 3,
      "max_tat_days": 45,
      "completed_count": 60,
      "total_count": 105,
      "completion_rate": 57.14
    },
    "message": null
  }
  ```

#### `GET /analytics/bottlenecks`

* **Description**: Details bottleneck counts aggregated by both stage and individual approver.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "stage_wise": [
        {
          "stage_name": "GCC HR",
          "pending_count": 12
        }
      ],
      "approver_wise": [
        {
          "approver_name": "Bob Jones",
          "stage_name": "GCC HR",
          "pending_count": 5
        }
      ]
    },
    "message": null
  }
  ```

#### `GET /analytics/department-wise`

* **Description**: Returns clearance statistics aggregated by business divisions / departments.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "department": "Engineering",
        "total": 35,
        "completed": 20,
        "clearance_pct": 57.14
      }
    ],
    "message": null
  }
  ```

#### `GET /analytics/trends`

* **Description**: Captures a month-over-month history of initiated and completed clearance workflows.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "date": "2026-05-01",
        "initiated": 40,
        "completed": 25
      }
    ],
    "message": null
  }
  ```

#### `GET /analytics/status-pie`

* **Description**: Returns status counts (completed, pending, in progress) for the dashboard status pie/donut chart. If `approval_stage` is specified (e.g. `'RM'`), counts are grouped by the statuses of that specific approval stage.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (matching `NdcFilterParams`):
    - `approval_stage` (string, e.g. `'RM'`, `'IT'`, `'All'`)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "completed": 88,
      "pending": 91,
      "in_progress": 28,
      "total": 207
    },
    "message": null
  }
  ```

#### `GET /analytics/ndc-analysis`

* **Description**: Returns counts of completed NDC records grouped by completion delay buckets (relative to LWD). If `approval_stage` is specified (e.g. `'RM'`), completion delay is calculated using the completed date of that department's approval.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (matching `NdcFilterParams`):
    - `approval_stage` (string, e.g. `'RM'`, `'IT'`, `'All'`)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "on_due_date": 3,
      "within_2_days": 2,
      "three_to_seven_days": 8,
      "seven_to_thirty_days": 22,
      "more_than_thirty_days": 46,
      "total": 81
    },
    "message": null
  }
  ```

#### `GET /analytics/approval-departments`

* **Description**: Returns a sorted list of all unique approval departments/stages available in the database, prepended with `'All'`.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      "All",
      "RM",
      "IT",
      "Abex",
      "Telecom",
      "Store",
      "Safety",
      "Administration",
      "Security",
      "HR",
      "GCC HR",
      "Business Specific",
      "Final Abex",
      "Legatrix"
    ],
    "message": null
  }
  ```

#### `GET /analytics/approval-analysis`

* **Description**: Returns counts of completed and pending clearances grouped by approval stage/department (e.g., RM, IT, HR, Security, Administration, Safety). If `approval_stage` is specified (and is not `'All'`), the returned list is filtered to contain only the counts for that specific stage.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (all optional, matching `NdcFilterParams`):
    - `ndc_stage` (string)
    - `business_unit` (string)
    - `legal_employer` (string)
    - `location` (string)
    - `location_city` (string)
    - `department_reporting_name` (string)
    - `approval_stage` (string)
    - `approval_status` (string)
    - `approver_name` (string)
    - `person_number` (int)
    - `employee_name` (string)
    - `has_gcc_pending` (boolean)
    - `pending_days_min` (int)
    - `pending_days_max` (int)
    - `ndc_initiated_from` (date)
    - `ndc_initiated_to` (date)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "stage_name": "RM",
        "completed": 13,
        "pending": 3
      },
      {
        "stage_name": "IT",
        "completed": 11,
        "pending": 5
      }
    ],
    "message": null
  }
  ```

#### `GET /analytics/monthly-trend`

* **Description**: Returns monthly trends of initiated vs completed clearance requests along with percentage representation.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (all optional, matching `NdcFilterParams`):
    - `ndc_stage` (string)
    - `business_unit` (string)
    - `legal_employer` (string)
    - `location` (string)
    - `location_city` (string)
    - `department_reporting_name` (string)
    - `approval_stage` (string)
    - `approval_status` (string)
    - `approver_name` (string)
    - `person_number` (int)
    - `employee_name` (string)
    - `has_gcc_pending` (boolean)
    - `pending_days_min` (int)
    - `pending_days_max` (int)
    - `ndc_initiated_from` (date)
    - `ndc_initiated_to` (date)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "month": "Feb 2026",
        "initiated": 2,
        "completed": 0,
        "initiated_pct": 9.1,
        "completed_pct": 0.0
      },
      {
        "month": "Mar 2026",
        "initiated": 5,
        "completed": 1,
        "initiated_pct": 22.7,
        "completed_pct": 4.5
      }
    ],
    "message": null
  }
  ```

#### `GET /analytics/closed-tat-analysis`

* **Description**: Returns counts of completed NDC records grouped by Turnaround Time (TAT) duration buckets (completed date minus initiated date).
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (all optional, matching `NdcFilterParams`):
    - `ndc_stage` (string)
    - `business_unit` (string)
    - `legal_employer` (string)
    - `location` (string)
    - `location_city` (string)
    - `department_reporting_name` (string)
    - `approval_stage` (string)
    - `approval_status` (string)
    - `approver_name` (string)
    - `person_number` (int)
    - `employee_name` (string)
    - `has_gcc_pending` (boolean)
    - `pending_days_min` (int)
    - `pending_days_max` (int)
    - `ndc_initiated_from` (date)
    - `ndc_initiated_to` (date)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": {
      "within_7_days": 2,
      "within_15_days": 8,
      "within_30_days": 12,
      "more_than_30_days": 59,
      "total": 88
    },
    "message": null
  }
  ```

#### `GET /analytics/top-delayed-cases`

* **Description**: Returns top delayed pending cases grouped by NDC and F&F categories.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
  - Query Parameters (all optional):
    - `category` (string, options: `'All'`, `'NDC'`, `'F&F'`. Default: `'All'`)
    - `limit` (int, default: 10)
    - All optional filters matching `NdcFilterParams`:
      - `business_unit` (string)
      - `legal_employer` (string)
      - `location` (string)
      - `location_city` (string)
      - `department_reporting_name` (string)
      - `ndc_initiated_from` (date)
      - `ndc_initiated_to` (date)
* **Success Response (200 OK)**:
  ```json
  {
    "status": true,
    "data": [
      {
        "person_number": 30144128,
        "employee_name": "Prasad Babu Galla",
        "department": "Projects",
        "last_working_date": "2025-11-12",
        "category": "NDC Pending",
        "delay_days": 220
      },
      {
        "person_number": 30144128,
        "employee_name": "Prasad Babu Galla",
        "department": "Projects",
        "last_working_date": "2025-11-12",
        "category": "F&F Pending",
        "delay_days": 220
      }
    ],
    "message": null
  }
  ```

---

### 2.5 MIS Exporter

#### `GET /export/mis-excel`

* **Description**: Downloads a custom styled multi-sheet Excel file (`NDC_MIS_Report.xlsx`) including active records, TAT summaries, bottlenecks, and division metrics.
* **Input**:
  - Header: `Authorization: Bearer <JWT_TOKEN>`
* **Response Output**:
  - Binary Stream (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
  - **Note**: This endpoint skips JSON wrapping to return the raw binary stream directly.
