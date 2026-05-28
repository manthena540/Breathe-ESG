# Data Model

## Overview

The model is built around four core concerns:
1. **Multi-tenancy** — every row belongs to an Organization
2. **Source provenance** — every normalized record traces back to the exact file that produced it
3. **Scope classification** — every record carries a GHG Protocol scope and category
4. **Audit trail** — every analyst decision is recorded immutably

---

## Entities

### Organization
The tenant root. All other entities foreign-key to Organization. A single database instance serves multiple clients; queries always filter by `organization_id`.

```
Organization
├── id (PK)
├── name
├── slug (unique — used in URLs and API keys)
└── created_at
```

**Why slug?** Clients are identified by a stable human-readable identifier, not just an integer, so API paths like `/org/acme-corp/records/` are self-documenting.

---

### IngestionJob
Tracks a single file upload. This is the source-of-truth anchor: if you want to know where a record came from, you look at its `ingestion_job`.

```
IngestionJob
├── id (PK)
├── organization → Organization
├── source_type  ENUM(sap | utility | travel)
├── uploaded_file  (FileField, path on disk/S3)
├── original_filename
├── status  ENUM(pending | processing | completed | failed)
├── uploaded_by → User
├── created_at
├── completed_at
├── row_count
├── error_count
└── error_log  (JSON array of parse error strings)
```

**Why keep the original file?** A real audit requires the ability to re-derive any normalized number from its source bytes. Storing the file means we can re-run the parser if emission factors are updated.

**Why error_log on the job, not per-row?** Parse errors are structural (malformed date, unknown unit) — they prevent row creation entirely. Row-level issues that don't block creation are stored as `flags` on `EmissionRecord`.

---

### EmissionRecord
The normalized emission data point. One row in the source file produces one `EmissionRecord` (or zero, if it fails to parse).

```
EmissionRecord
├── id (PK)
├── organization → Organization       [tenant]
├── ingestion_job → IngestionJob      [provenance]
├── source_row_id                     [original identifier in source system]
│
├── scope  ENUM(1 | 2 | 3)           [GHG Protocol scope]
├── category  ENUM(                  [GHG Protocol category]
│     stationary_combustion,
│     mobile_combustion,
│     purchased_electricity,
│     business_travel,
│     purchased_goods)
├── activity_type                     [granular: diesel, natural_gas, flight_economy, hotel_stay…]
│
├── period_start  DATE               [billing period — NOT calendar month]
├── period_end    DATE               [bills frequently span month boundaries]
│
├── quantity      DECIMAL(18,4)      [raw quantity in source unit]
├── unit                             [source unit: liters, kWh, km, nights…]
├── quantity_normalized DECIMAL(18,4) [converted to standard unit for category]
├── normalized_unit                  [standard unit: liters for fuel, kWh for electricity]
├── co2e_kg       DECIMAL(18,4)      [calculated kg CO2e — null if factor unavailable]
│
├── facility                         [plant code, site name, or hotel name]
├── country
│
├── raw_data      JSON               [original row verbatim — never discarded]
│
├── status  ENUM(pending_review | approved | rejected | flagged)
├── review_notes
├── reviewed_by → User
├── reviewed_at
│
├── flags  JSON[]                    [suspicious conditions flagged at parse time]
├── is_locked  BOOL                  [true after audit sign-off — no further edits]
│
├── created_at
└── updated_at
```

#### Why `raw_data JSON`?
The original row is preserved verbatim. This means:
- An auditor can verify any normalized value against the source
- If the emission factor changes, we can recalculate without re-uploading
- Nothing is ever silently discarded

#### Why `period_start` / `period_end` instead of `month`?
Utility bills don't align with calendar months. A "January bill" covers Dec 15 – Jan 14. Forcing this into a `month` field loses information and introduces systematic error in period-over-period comparisons. Analysts can still filter by date range.

#### Why DECIMAL(18,4)?
Fuel quantities can be fractional liters (4 decimal places). CO2e sums across an enterprise can reach millions of kg (18 significant digits total). FLOAT would introduce rounding errors in financial audit contexts.

#### Why separate `quantity` / `quantity_normalized` / `co2e_kg`?
Three distinct concerns:
- `quantity` + `unit` — what the source said, exactly
- `quantity_normalized` + `normalized_unit` — converted to a standard unit for the category (kWh for electricity, liters for liquid fuels) for cross-site comparison
- `co2e_kg` — the final emissions number, using published emission factors

Keeping them separate means a changed emission factor doesn't require re-parsing the file.

#### Scope classification
| source_type | Scope | Category |
|-------------|-------|----------|
| SAP — diesel/petrol | 1 | mobile_combustion |
| SAP — natural gas | 1 | stationary_combustion |
| SAP — procurement | 3 | purchased_goods |
| Utility — electricity | 2 | purchased_electricity |
| Travel — flights | 3 | business_travel |
| Travel — hotels | 3 | business_travel |
| Travel — ground | 3 | business_travel |

---

### AuditLog
Immutable record of every analyst action on an EmissionRecord. Written at creation, never updated or deleted.

```
AuditLog
├── id (PK)
├── organization → Organization
├── record → EmissionRecord
├── action  ENUM(approved | rejected | flagged | edited | locked)
├── actor → User
├── before_state  JSON             [snapshot of record state before action]
├── after_state   JSON             [snapshot after action]
├── notes
└── timestamp  (auto_now_add)
```

**Why snapshot both states?** An auditor needs to be able to reconstruct the full history of a record without chasing foreign keys. Storing before/after as JSON means the audit is self-contained even if the record is later modified.

**Why a separate table instead of soft deletes / versioning on EmissionRecord?** A versioning approach on the main table makes queries complex and risks accidentally mutating history. A separate immutable log table is simpler and harder to corrupt accidentally.

---

## Multi-tenancy

All queries in the API filter by `organization`. A user belongs to one or more organizations via `OrganizationMembership`. In this prototype, the organization is selected at the UI level (dropdown). In production this would be derived from the authenticated user's session.

There is no row-level security at the database level (this is a prototype). In production, a PostgreSQL RLS policy or application-layer guard on every queryset would be required.

---

## Indexes (implied, not explicitly declared in prototype)

For a production deployment, the following indexes are needed:
- `EmissionRecord(organization_id, status)` — analyst filter queries
- `EmissionRecord(organization_id, scope, period_start)` — scope reporting queries
- `EmissionRecord(ingestion_job_id)` — job detail view
- `AuditLog(record_id)` — record history view

---

## What this model does NOT handle (see TRADEOFFS.md)
- Emission factor versioning (factors are hardcoded in parsers)
- Currency normalization (amounts stored in source currency)
- Parent/child company hierarchies
- Real-time API pull ingestion (file upload only)
