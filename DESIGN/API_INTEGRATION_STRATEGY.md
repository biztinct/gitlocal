# API Integration Strategy — Payobook Payroll System

## Executive Summary

This document defines the strategy for integrating external HRIS/payroll systems with the Payobook Odoo 19 payroll platform. The core pattern is **Pull → Store → Transform → Map → Compute**:

1. **Pull** data on demand from external HRIS APIs (Zoho, SAP, Workday, etc.)
2. **Store** the raw API response locally in the Odoo database as a persistent data cache
3. **Transform** derive new values from stored records (e.g., count dependents, calculate tenure from dates, aggregate attendance rows)
4. **Map** the stored + transformed data to salary components using field mappings tied to pay structures
5. **Compute** payslips using the existing formula engine

> **What this is NOT:** This is *not* a real-time synchronisation system. There are no webhooks, no push endpoints, and no outbound APIs for external consumers. Data is pulled when an operator decides to, stored locally, and then used for payroll processing at the operator's pace.

---

## 1. Current Architecture (As-Is)

### 1.1 Data Flow Today

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌─────────────────────────┐
│   External HRIS     │      │   Odoo Payroll Engine     │      │      Outputs            │
│  (Zoho, SAP, etc.)  │      │  pb_hr_payroll_formula    │      │                         │
│                     │      │                          │      │  • Payslips             │
│  Manual Excel       │─────►│  hr.payroll.import.batch  │─────►│  • Payslip Lines        │
│  Export/Download    │      │  hr.payroll.import.line   │      │  • Payroll Analytics     │
│                     │      │  hr.formula.config        │      │  • Reports               │
│                     │      │  hr.formula.rule          │      │  • Government Forms      │
└─────────────────────┘      └──────────────────────────┘      └─────────────────────────┘
```

### 1.2 Current Workflow Steps

1. **Manual Export**: HR exports employee + salary data from external HRIS as Excel/CSV file
2. **Upload to Odoo**: User uploads the file in `hr.payroll.import.batch`
3. **Data Load**: `action_load_file()` parses Excel → creates `hr.payroll.import.line` records
4. **Employee Match**: `action_match_employees()` matches rows to Odoo employees by code/email/name
5. **Validate**: `action_validate()` validates data integrity
6. **Process**: `action_process()` creates employees, contracts, and payslips with formula-computed lines
7. **Review & Approve**: 2-level approval workflow (HR → GM)

### 1.3 Key Models

| Model | Purpose | File |
|-------|---------|------|
| `hr.formula.config` | Salary structure configuration (rules, formulas, country) | `formula_config.py` |
| `hr.formula.rule` | Individual salary rule with Excel formula | `formula_rule.py` |
| `hr.payroll.import.batch` | Import batch — staging area for payroll data | `payroll_import_batch.py` |
| `hr.payroll.import.line` | Individual employee row in import batch | `payroll_import_line.py` |
| `hr.integration.connector` | External system connection settings | `integration_connector.py` |
| `hr.integration.field.mapping` | Maps external fields to formula rule inputs | `integration_field_mapping.py` |
| `hr.payslip` (extended) | Payslip with formula computation support | `hr_payslip_formula.py` |

### 1.4 Existing Integration Framework (Built but Not Yet Connected)

The codebase already has a robust integration framework:

- **`integrations/base_connector.py`** — Abstract base class with `authenticate()`, `test_connection()`, `fetch_employees()`, `fetch_payroll_data()`, `transform_data()`
- **`integrations/zoho_connector.py`** — Full OAuth 2.0 implementation for Zoho People
- **`integrations/excel_connector.py`** — Excel/CSV file parsing
- **`integrations/sap_connector.py`** — SAP SuccessFactors stub
- **`integrations/workday_connector.py`** — Workday stub
- **`integrations/oracle_connector.py`** — Oracle HCM stub

---

## 2. Proposed Architecture (To-Be)

### 2.1 Core Principle: Pull → Store → Transform → Map → Compute

The integration follows an **on-demand pull** model. No data flows in real-time. An operator (or scheduled cron) triggers a pull, the data is persisted locally, optionally transformed, and then used for payroll at any later point.

```
┌────────────────────────┐
│   External HRIS APIs   │
│  (Zoho, SAP, Workday)  │
└───────────┬────────────┘
            │  ① PULL (on demand / scheduled)
            │     Operator clicks "Pull Data"
            │     or cron job fires
            ▼
┌────────────────────────────────────────────────────────────────────┐
│                     LOCAL DATA STORE                               │
│                  hr.api.data.store  (new model)                    │
│                                                                    │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  RAW LAYER      │  │  EXTRACTED LAYER  │  │  VERSION/DIFF    │  │
│  │  raw_payload     │  │  extracted_data   │  │  previous_id     │  │
│  │  (JSONB)        │  │  (JSONB, flat)    │  │  change_summary  │  │
│  │  Immutable      │  │  Queryable        │  │  Auditable       │  │
│  └────────┬────────┘  └────────┬─────────┘  └──────────────────┘  │
│           │                    │                                    │
│           │  ② STORE           │                                    │
│           │  Complete API      │                                    │
│           │  response saved    │                                    │
└───────────┼────────────────────┼────────────────────────────────────┘
            │                    │
            │                    ▼
┌────────────────────────────────────────────────────────────────────┐
│              ③ TRANSFORM (hr.api.transformation.rule)              │
│                                                                    │
│  Derive new values that don't exist in any single API record:      │
│  • Aggregate:  COUNT dependent records → NUM_DEPENDENTS = 3        │
│  • Date calc:  join_date → TENURE_MONTHS = 25                      │
│  • Filter+Count: dependents WHERE age < 18 → MINOR_DEPS = 2       │
│  • Sum records: SUM attendance.working_days → WORK_DAYS = 22       │
│                                                                    │
│  Results written to computed_data (JSONB) on data store             │
└───────────────────────────┬────────────────────────────────────────┘
                            │
                            │  ④ MAP (field mapping)
                            │     hr.integration.field.mapping
                            │     maps extracted_data + computed_data
                            │     to formula rule input values
                            ▼
┌────────────────────────────────────────────────────────────────────┐
│                    EXISTING PAYROLL PIPELINE                       │
│                                                                    │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐  │
│  │ hr.payroll.       │──►│ hr.formula.config │──►│ hr.payslip   │  │
│  │ import.batch      │   │ + formula rules   │   │ + lines      │  │
│  │ (staging, as-is)  │   │ (calc engine)     │   │ (output)     │  │
│  └──────────────────┘   └──────────────────┘   └──────────────┘  │
│                                                                    │
│  ⑤ COMPUTE — formula engine evaluates rules, creates payslips     │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 What Changed vs. Previous Approach

| Aspect | Previous Strategy | Revised Strategy |
|--------|-------------------|-------------------|
| **Data direction** | Bi-directional (pull + push + webhooks) | **Inbound pull only** |
| **Timing** | Real-time + scheduled | **On demand + optional cron** |
| **External API exposure** | REST endpoints for payslip retrieval, config, etc. | **None — no outbound APIs** |
| **Storage** | Transient (data flows straight through to import lines) | **Persistent local cache** with versioning |
| **When data is used** | Immediately upon receipt | **When operator chooses** to create an import batch |

---

## 3. Data Storage Deep-Dive: Why JSONB and the Three-Layer Model

### 3.1 The Core Problem

Different HRIS systems return wildly different data shapes:

```
Zoho People:      { "BasicSalary": 15000000, "HRA": 3000000, "Employeestatus": "Active" }
SAP SuccessFactors: { "compensation": { "basePay": 15000000 }, "employment": { "status": "A" } }
Workday:          { "Worker": { "Compensation": [{ "amount": 15000000, "type": "BASE" }] } }
Custom HRIS:      { "base_salary": 15000000, "housing": 3000000, "status": 1 }
```

A rigid relational model (one column per field) would require different tables or massive column sets for each system. The schema would break every time a new field is added upstream.

### 3.2 Storage Format Analysis

| Option | How it Works | Pros | Cons | Verdict |
|--------|-------------|------|------|---------|
| **`fields.Text` (JSON string)** | Store `json.dumps()` in a text column | Simple, Odoo-native | No DB-level querying, no indexing, requires `json.loads()` on every access, no partial updates | ❌ Current approach on `import.line`, adequate but not optimal |
| **`fields.Json` (PostgreSQL JSONB)** | Odoo 16+ field type → JSONB column | **Indexable** (GIN), **queryable** at DB level (`->>`), binary format is faster, partial key access, containment operators (`@>`) | Slightly more storage than text | ✅ **Recommended** |
| **Relational columns (normalized)** | Dedicated fields: `basic_salary = fields.Float` | Type safety, standard Odoo reporting | Rigid schema, migration for every new field, doesn't handle varying API structures | ❌ Too rigid for multi-system integration |
| **EAV (Entity-Attribute-Value)** | `(employee, field_name, field_value)` rows | Infinitely flexible | Terrible query performance, complex joins, anti-pattern | ❌ Anti-pattern |
| **Binary/File attachment** | Store as attachment | Handles any format | Not queryable, requires deserialization | ❌ Not suitable |

### 3.3 Why `fields.Json` (JSONB) is the Right Choice

PostgreSQL JSONB, exposed via Odoo's `fields.Json`, is the industry standard for this exact problem. Here's why:

**1. Queryable at the Database Level**
```sql
-- Find all stored records where basic salary exceeds 20M
SELECT id, extracted_data->>'BASIC' as basic
FROM hr_api_data_store
WHERE (extracted_data->>'BASIC')::numeric > 20000000;
```

**2. Indexable with GIN Indexes**
```sql
-- GIN index for containment queries
CREATE INDEX idx_api_store_extracted ON hr_api_data_store USING GIN (extracted_data);
-- Now this is fast:
SELECT * FROM hr_api_data_store WHERE extracted_data @> '{"BASIC": 15000000}';
```

**3. No `json.loads()` Overhead**
Unlike the current `fields.Text` + `json.dumps/loads` pattern on `hr.payroll.import.line`, JSONB is parsed once on write and returned as a native Python dict on read — no deserialization needed.

**4. Partial Key Access**
```python
# In Odoo Python code, fields.Json returns a dict directly
basic = record.extracted_data.get('BASIC', 0)
# vs. with fields.Text:
data = json.loads(record.raw_data_json)  # parse every time
basic = data.get('BASIC', 0)
```

**5. Schema Flexibility**
A Zoho pull stores `{"BasicSalary": 15000000, "HRA": 3000000}`. An SAP pull stores `{"basePay": 15000000, "housingAllowance": 3000000}`. Same column, different shapes — the field mappings translate them.

### 3.4 Industry Precedent

| System | How They Store External API Data |
|--------|----------------------------------|
| **Odoo's own Amazon connector** | `sale.amazon.order` stores full Amazon API response as JSON, then extracts into order lines |
| **Stripe/Payment gateways** | Raw webhook payload → JSONB, extract key fields into columns for indexing |
| **Workday Integration Cloud** | Staging area with flexible JSON payloads → mapping definitions → target models |
| **SAP Cloud Integration (CPI)** | Message store with JSON/XML → mapping rules → target IDocs |
| **Fivetran / Airbyte (modern ELT)** | Raw JSON → JSONB in PostgreSQL → transformation layer → analytics tables |
| **Salesforce Platform Events** | Raw event payload → persisted → consumed by subscribers at their own pace |

All of these follow the same pattern: **store raw, extract later, map when needed**.

### 3.5 The Three-Layer Architecture

Our implementation decomposes storage into three logical layers within the same model:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    hr.api.data.store — Single Record                       │
│                                                                             │
│  LAYER 1: RAW PAYLOAD              LAYER 2: EXTRACTED DATA                 │
│  ─────────────────────              ──────────────────────                  │
│  raw_payload (fields.Json)          extracted_data (fields.Json)            │
│                                                                             │
│  • Complete API response            • Flattened, cleaned key-value pairs    │
│  • Never modified after write       • Dot-notation paths resolved          │
│  • Audit trail / source of truth    • Ready for field mapping              │
│  • Debug / re-process if needed     • Queryable / filterable               │
│                                                                             │
│  Example (Zoho):                    Example (after extraction):            │
│  {                                  {                                      │
│    "response": {                      "BasicSalary": 15000000,             │
│      "result": [{                     "HRA": 3000000,                      │
│        "BasicSalary": 15000000,       "EmployeeID": "EMP001",             │
│        "HRA": 3000000,                "FirstName": "Nguyen",              │
│        ...                            "LastName": "Van A",                 │
│      }]                               "Department": "Engineering",         │
│    }                                  "Status": "Active"                   │
│  }                                  }                                      │
│                                                                             │
│  LAYER 3: VERSION & DIFF                                                   │
│  ────────────────────────                                                  │
│  version (Integer)                  Enables:                               │
│  previous_version_id (M2O → self)   • "What changed since last pull?"      │
│  change_summary (fields.Json)       • Salary change detection              │
│                                     • Retro-adjustment triggers            │
│  Example:                                                                  │
│  { "BASIC": {"old": 14000000, "new": 15000000},                           │
│    "HRA":   {"old": 2500000,  "new": 3000000} }                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.6 Why Three Layers, Not One?

| Layer | Purpose | Mutability | Retention |
|-------|---------|------------|-----------|
| **Raw Payload** | Audit trail, debugging, re-processing | **Immutable** — never written after initial save | Keep for 12 months, then archive |
| **Extracted Data** | Field mapping input, querying, UI display | **Write-once** — generated from raw on store | Keep with raw payload |
| **Version/Diff** | Change detection, retro-adjustment triggers | **Write-once** — computed at pull time | Keep with raw payload |

Separating raw from extracted means:
- If a field mapping is wrong, you can re-extract from raw without pulling again
- If the extraction logic changes, you re-run extraction, not re-pull from API
- The raw payload is a forensic-grade audit trail that proves what the external system returned

---

## 4. New Model: `hr.api.data.store`

### 4.1 Model Definition

```python
class HrApiDataStore(models.Model):
    _name = 'hr.api.data.store'
    _description = 'API Data Store — Local Cache of External HRIS Data'
    _order = 'pull_date desc, id desc'
    _rec_name = 'display_name'

    # ==========================================
    # IDENTITY
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector', string='Source Connector',
        required=True, ondelete='cascade', index=True,
    )
    data_type = fields.Selection([
        ('employee', 'Employee Master Data'),
        ('salary', 'Salary / Compensation'),
        ('attendance', 'Attendance'),
        ('leave', 'Leave / Time-Off'),
        ('dependent', 'Dependents / Family'),
        ('benefit', 'Benefits'),
        ('tax', 'Tax Information'),
        ('custom', 'Custom / Other'),
    ], string='Data Type', required=True, index=True)

    employee_external_id = fields.Char(
        string='External Employee ID', index=True,
        help="Employee ID in the source HRIS system",
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Matched Employee',
        help="Odoo employee this data belongs to (matched after pull)",
    )

    # ==========================================
    # PERIOD
    # ==========================================
    period_from = fields.Date(string='Period From')
    period_to = fields.Date(string='Period To')
    period_label = fields.Char(
        string='Period', compute='_compute_period_label', store=True,
    )

    # ==========================================
    # LAYER 1: RAW PAYLOAD (immutable after write)
    # ==========================================
    raw_payload = fields.Json(
        string='Raw API Response',
        help="Complete, unmodified API response. Never edited after initial write.",
    )

    # ==========================================
    # LAYER 2: EXTRACTED DATA (flattened for mapping)
    # ==========================================
    extracted_data = fields.Json(
        string='Extracted Data',
        help="Flattened key-value pairs extracted from raw payload, ready for field mapping.",
    )

    # ==========================================
    # LAYER 2b: COMPUTED DATA (from transformation rules)
    # ==========================================
    computed_data = fields.Json(
        string='Computed Data',
        help="Derived values produced by transformation rules (e.g., dependent count, tenure). "
             "Merged with extracted_data at mapping time.",
    )

    # ==========================================
    # LAYER 3: VERSIONING & CHANGE DETECTION
    # ==========================================
    version = fields.Integer(
        string='Version', default=1,
        help="Increments with each pull for the same employee+data_type+period",
    )
    previous_version_id = fields.Many2one(
        'hr.api.data.store', string='Previous Version',
        help="Link to previous pull for change detection",
    )
    change_summary = fields.Json(
        string='Changes from Previous',
        help="Diff: {field: {old: x, new: y}} — auto-computed on pull",
    )
    has_changes = fields.Boolean(
        string='Has Changes', compute='_compute_has_changes', store=True,
    )

    # ==========================================
    # METADATA
    # ==========================================
    pull_date = fields.Datetime(
        string='Pull Date', default=fields.Datetime.now, required=True,
    )
    pull_duration_ms = fields.Integer(
        string='Pull Duration (ms)',
        help="How long the API call took",
    )
    pull_triggered_by = fields.Selection([
        ('manual', 'Manual (Button Click)'),
        ('cron', 'Scheduled (Cron Job)'),
    ], string='Triggered By', default='manual')

    state = fields.Selection([
        ('raw', 'Raw (Just Pulled)'),
        ('extracted', 'Extracted (Ready for Mapping)'),
        ('consumed', 'Consumed (Used in Import Batch)'),
        ('archived', 'Archived'),
        ('error', 'Error'),
    ], string='Status', default='raw', index=True)

    error_message = fields.Text(string='Error Message')

    # Traceability: which import batch consumed this data
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch', string='Used in Import Batch',
        readonly=True,
    )

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ==========================================
    # COMPUTED
    # ==========================================
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('employee_external_id', 'data_type', 'pull_date')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.employee_external_id or '?', rec.data_type or '?']
            if rec.pull_date:
                parts.append(rec.pull_date.strftime('%Y-%m-%d %H:%M'))
            rec.display_name = ' / '.join(parts)

    @api.depends('period_from', 'period_to')
    def _compute_period_label(self):
        for rec in self:
            if rec.period_from and rec.period_to:
                rec.period_label = f"{rec.period_from} → {rec.period_to}"
            else:
                rec.period_label = False

    @api.depends('change_summary')
    def _compute_has_changes(self):
        for rec in self:
            rec.has_changes = bool(rec.change_summary)
```

### 4.2 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **`fields.Json` not `fields.Text`** | JSONB is natively queryable, indexable (GIN), and returns Python dicts without `json.loads()` overhead. Our existing `raw_data_json = fields.Text` on import lines requires manual serialization/deserialization on every access. |
| **Raw + Extracted as separate fields** | Raw is the audit trail (never touch it). Extracted is the working copy (re-generable). If extraction logic improves, re-extract from raw without re-pulling from API. |
| **Versioning with `previous_version_id`** | Enables diff computation across pulls. Critical for retro-adjustment detection: "This employee's basic salary changed from 14M to 15M since last pull." |
| **One record per employee per data_type per pull** | Granular — can track salary changes independently from attendance changes. Don't mix concerns. |
| **`state = 'consumed'`** | Traceability — once data is used in an import batch, it's marked consumed. Prevents accidental re-use and provides a clear audit trail. |
| **No cascade delete from connector** | If a connector is archived, stored data is preserved for audit purposes. |

---

## 5. Pull Workflow — Step by Step

### 5.1 On-Demand Pull (Operator-Triggered)

```
HR Operator clicks "Pull Data" on connector form
    │
    ▼
hr.integration.connector.action_pull_data()
    │
    ├─► Select data types to pull (employee, salary, attendance, etc.)
    ├─► Select period (current month / custom dates)
    │
    ▼
Connector authenticates with external HRIS
    │  (OAuth 2.0 / API Key / Bearer Token)
    ▼
Connector calls external API
    │  e.g., Zoho: GET /api/forms/P_Employee/records
    │        Zoho: GET /api/forms/P_Salary/records
    ▼
Raw API response received
    │
    ▼
For each employee in response:
    │
    ├─► Create hr.api.data.store record
    │     • raw_payload = complete API response (JSONB, immutable)
    │     • state = 'raw'
    │
    ├─► Extract & flatten the raw payload
    │     • Resolve nested paths (e.g., response.result[0].BasicSalary → "BasicSalary")
    │     • Store in extracted_data (JSONB)
    │     • state = 'extracted'
    │
    ├─► Find previous version for same employee + data_type
    │     • Compute change_summary diff
    │     • Link previous_version_id
    │     • Increment version number
    │
    └─► Try to match to existing Odoo employee
          • By employee code (external_id)
          • By email
          • Store in employee_id (nullable)

    ▼
Notify operator: "Pulled 150 employee records from Zoho. 3 have salary changes."
```

### 5.2 Scheduled Pull (Cron Job)

Same flow as above, but triggered by `ir.cron`:

```xml
<record id="cron_pull_zoho_data" model="ir.cron">
    <field name="name">Pull Zoho People Data</field>
    <field name="model_id" ref="model_hr_integration_connector"/>
    <field name="state">code</field>
    <field name="code">model.search([('connector_type','=','zoho'),('active','=',True)]).action_pull_data()</field>
    <field name="interval_number">1</field>
    <field name="interval_type">months</field>
    <field name="numbercall">-1</field>
    <field name="nextcall">2026-03-01 00:00:00</field>
</record>
```

### 5.3 Using Stored Data for Payroll

```
HR Operator opens hr.payroll.import.batch (existing model)
    │
    ├─► source_type = 'api_data_store' (new option, alongside 'excel' and 'connector')
    │
    ├─► Select connector + period
    │
    ▼
System loads hr.api.data.store records
    │  WHERE connector_id = X AND period = Y AND state = 'extracted'
    │
    ▼
For each stored record:
    │
    ├─► Apply field mappings (hr.integration.field.mapping)
    │     • source_field: "BasicSalary" (key in extracted_data)
    │     • target_rule_id: BASIC (formula rule)
    │     • transformation: direct / multiply / python
    │
    ├─► Create hr.payroll.import.line
    │     • raw_data_json = extracted_data (already flat+clean)
    │     • employee_code, employee_name, employee_email populated
    │
    └─► Mark data store records as state = 'consumed'
          • Link import_batch_id for traceability

    ▼
Normal payroll pipeline continues:
    action_match_employees() → action_validate() → action_process()
```

---

## 6. Field Mapping Architecture

### 6.1 How Field Mapping Works

The existing `hr.integration.field.mapping` model maps source fields to formula rule input columns. With the data store, the source is now the `extracted_data` JSONB field instead of a live API call:

```
Stored Data (extracted_data JSONB)     →  Transformation  →  Formula Rule
────────────────────────────────────   ──────────────────  ──────────────
extracted_data["BasicSalary"]           direct              BASIC
extracted_data["HRA"]                   direct              ALLOWANCE_HOUSING
extracted_data["OvertimeHours"]         multiply × rate     OVERTIME_PAY
extracted_data["AnnualBonus"]           divide ÷ 12         MONTHLY_BONUS
extracted_data["TaxableAmount"]         python expression   TAXABLE_INCOME
```

### 6.2 Field Mapping Transforms (Single-Field, at Mapping Time)

These are **simple, single-field** transforms already implemented on `hr.integration.field.mapping`. They operate on one source value at a time, at the moment the field is mapped to a pay component:

| Type | Description | Example |
|------|-------------|---------|
| `direct` | Direct value copy | `salary` → `BASIC` |
| `multiply` | Multiply by factor | `hourly_rate * 176` → `MONTHLY_BASIC` |
| `divide` | Divide by factor | `annual_salary / 12` → `MONTHLY_SALARY` |
| `round` | Round to N decimals | `12345.6789` → `12345.68` |
| `python` | Custom Python expression | `value * 1.1 if value > 10000000 else value` |

> **Important distinction:** These transforms operate on a **single value from a single record**. They cannot count across multiple records, check dates, or combine fields. For that, see **Section 7: Transformation Layer** below.

### 6.3 How extracted_data and computed_data Merge

At mapping time, the system merges `extracted_data` (from the API) with `computed_data` (from transformation rules) into a single flat dict. Field mapping doesn't need to know where a value came from:

```python
# At import batch creation time:
mappable_data = {**record.extracted_data, **record.computed_data}
# computed_data keys override extracted_data if same name (intentional)

# Field mapping works on the merged dict:
# mapping.source_field = "NUM_DEPENDENTS"  → found in computed_data
# mapping.source_field = "BasicSalary"     → found in extracted_data
# Both work identically from the mapping's perspective
```

### 6.4 Auto-Mapping (Already Implemented)

The `action_auto_map()` method on `hr.integration.field.mapping` uses field name similarity to suggest mappings automatically. When stored data has keys matching formula rule codes (e.g., `BASIC`, `GROSS`, `NET`), they map with zero configuration. This also works for computed_data keys.

### 6.5 Mapping Lifecycle

```
① Connector created
     │
     ▼
② First pull — system discovers available fields
     │  (from raw_payload keys or via connector.get_available_fields())
     │
     ▼
③ Configure transformation rules (Section 7)
     │  Define aggregations, date calculations, etc.
     │  These produce computed_data keys (e.g., NUM_DEPENDENTS)
     │
     ▼
④ Auto-map creates tentative mappings
     │  BasicSalary → BASIC (auto-matched, from extracted_data)
     │  HRA → ALLOWANCE_HOUSING (auto-matched, from extracted_data)
     │  NUM_DEPENDENTS → DEPENDENT_COUNT (from computed_data)
     │  CustomField123 → ??? (unmapped, needs manual config)
     │
     ▼
⑤ Operator reviews & adjusts mappings in UI
     │  • Confirm auto-mappings
     │  • Map remaining fields manually
     │  • Configure single-field transforms (multiply, python, etc.)
     │  • Test with sample values
     │
     ▼
⑥ Subsequent pulls — transformation rules + mappings applied automatically
     │  Stored data → transform → merged data → field mappings → import lines → payroll
```

---

## 7. Transformation Layer — Deriving Values from Stored Records

### 7.1 The Problem This Solves

The API stores data **exactly as the external system returns it**. But payroll often needs values that **don't exist in any single API record** — they must be derived from the stored data set. For example:

| What Payroll Needs | What the API Returns | The Gap |
|--------------------|----------------------|---------|
| `NUM_DEPENDENTS = 3` | 3 separate dependent records (one per child) | Need to **count** records |
| `MINOR_DEPENDENTS = 2` | Dependent records with `date_of_birth` field | Need to **count with a date filter** (age < 18) |
| `WORKING_DAYS = 22` | 22 attendance records for the month | Need to **count** attendance records with `status = 'present'` |
| `TOTAL_LEAVE_DAYS = 3` | 3 leave records with `days` field | Need to **sum** the `days` field across records |
| `TENURE_MONTHS = 25` | Employee record with `date_of_joining = "2024-01-15"` | Need to **calculate** months between join date and period end |
| `IS_PROBATION = true` | Employee record with `join_date` and `probation_months = 6` | Need to **check** if current date is within probation period |

**None of these can be done by field mapping** (single-field transforms) or by the **formula engine** (which only receives the values that have already been mapped as inputs). The transformation layer fills this gap.

### 7.2 Where It Sits in the Pipeline

```
① PULL    →  Raw API records stored (multiple per employee: salary, dependents, attendance, etc.)
② STORE   →  extracted_data populated per record
③ TRANSFORM →  Transformation rules run across stored records → computed_data written
④ MAP     →  Field mapping reads from extracted_data + computed_data → creates import lines
⑤ COMPUTE →  Formula engine evaluates pay structure rules → payslips
```

**Key insight:** The transformation layer operates on **sets of stored records** (e.g., all dependent records for employee X), whereas field mapping operates on **individual values**. They are complementary, not competing.

### 7.3 Transformation Rule Model: `hr.api.transformation.rule`

```python
class HrApiTransformationRule(models.Model):
    _name = 'hr.api.transformation.rule'
    _description = 'API Data Transformation Rule'
    _order = 'sequence, id'

    # ==========================================
    # IDENTITY
    # ==========================================
    connector_id = fields.Many2one(
        'hr.integration.connector', string='Connector',
        required=True, ondelete='cascade',
    )
    name = fields.Char(string='Rule Name', required=True,
        help="e.g., 'Count Dependents', 'Calculate Tenure'",
    )
    output_key = fields.Char(string='Output Key', required=True,
        help="Key name written to computed_data, e.g., 'NUM_DEPENDENTS'. "
             "This becomes available for field mapping.",
    )
    description = fields.Text(string='Description',
        help="Explain what this rule computes and why.",
    )

    # ==========================================
    # RULE TYPE
    # ==========================================
    rule_type = fields.Selection([
        ('count', 'Count Records'),
        ('sum', 'Sum Field Across Records'),
        ('avg', 'Average Field Across Records'),
        ('min', 'Minimum Field Across Records'),
        ('max', 'Maximum Field Across Records'),
        ('date_diff', 'Date Difference Calculation'),
        ('date_check', 'Date Condition Check'),
        ('python', 'Python Expression (Advanced)'),
    ], string='Rule Type', required=True, default='count')

    # ==========================================
    # SOURCE: Which stored records to operate on
    # ==========================================
    source_data_type = fields.Selection([
        ('employee', 'Employee Master Data'),
        ('salary', 'Salary / Compensation'),
        ('attendance', 'Attendance'),
        ('leave', 'Leave / Time-Off'),
        ('dependent', 'Dependents / Family'),
        ('benefit', 'Benefits'),
        ('tax', 'Tax Information'),
        ('custom', 'Custom / Other'),
    ], string='Source Data Type', required=True,
        help="Which data_type records to operate on. "
             "e.g., 'dependent' to count dependent records.",
    )

    # ==========================================
    # AGGREGATE SETTINGS (count, sum, avg, min, max)
    # ==========================================
    aggregate_field = fields.Char(
        string='Field to Aggregate',
        help="For sum/avg/min/max: which key in extracted_data to aggregate. "
             "Leave empty for count (counts records, not a field).",
    )
    filter_expression = fields.Char(
        string='Filter Expression',
        help="Optional Python expression to filter records before aggregating. "
             "Available: `rec` (the extracted_data dict), `env` (Odoo env). "
             "Examples:\n"
             "  rec.get('status') == 'Active'\n"
             "  rec.get('relationship') == 'Child'\n"
             "  rec.get('age', 0) < 18",
    )

    # ==========================================
    # DATE SETTINGS (date_diff, date_check)
    # ==========================================
    date_source_field = fields.Char(
        string='Date Source Field',
        help="Key in extracted_data containing the date, e.g., 'date_of_joining'",
    )
    date_compare_to = fields.Selection([
        ('period_start', 'Period Start Date'),
        ('period_end', 'Period End Date'),
        ('today', 'Today'),
        ('fixed', 'Fixed Date'),
    ], string='Compare To', default='period_end')
    date_fixed_value = fields.Date(string='Fixed Date')
    date_unit = fields.Selection([
        ('days', 'Days'),
        ('months', 'Months'),
        ('years', 'Years'),
    ], string='Result Unit', default='months',
        help="For date_diff: return difference in days, months, or years.",
    )
    date_check_operator = fields.Selection([
        ('before', 'Is Before'),
        ('after', 'Is After'),
        ('within', 'Is Within N months'),
    ], string='Check Operator')
    date_check_value = fields.Integer(
        string='Check Value (months)',
        help="For 'within' operator: number of months to check.",
    )

    # ==========================================
    # PYTHON (advanced, full flexibility)
    # ==========================================
    python_code = fields.Text(
        string='Python Expression',
        help="Advanced: Full Python code. Available variables:\n"
             "  `records` — list of extracted_data dicts for this data_type\n"
             "  `employee_data` — the employee's own extracted_data dict\n"
             "  `all_records` — dict of {data_type: [records]} for all types\n"
             "  `period_start`, `period_end` — batch period dates\n"
             "  `env` — Odoo environment\n"
             "  `employee` — hr.employee record (if matched)\n\n"
             "Must set `result = <value>` as the output.\n\n"
             "Example:\n"
             "  children = [r for r in records if r.get('relationship') == 'Child']\n"
             "  minors = [c for c in children if c.get('age', 0) < 18]\n"
             "  result = len(minors)",
    )

    # ==========================================
    # SETTINGS
    # ==========================================
    default_value = fields.Float(
        string='Default Value', default=0,
        help="Value to use if no matching records found or rule errors.",
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
```

### 7.4 Concrete Examples

#### Example 1: Count All Dependents

```
Rule Name:        Count Dependents
Output Key:       NUM_DEPENDENTS
Rule Type:        count
Source Data Type:  dependent
Filter:           (empty — count all)
Default Value:    0
```

**What happens:** System finds all `hr.api.data.store` records where `employee_external_id = 'EMP001'` AND `data_type = 'dependent'`. Counts them. Writes `computed_data = {"NUM_DEPENDENTS": 3}` on the employee's salary record.

#### Example 2: Count Minor Dependents (Under 18)

```
Rule Name:        Count Minor Dependents
Output Key:       MINOR_DEPENDENTS
Rule Type:        count
Source Data Type:  dependent
Filter:           rec.get('age', 0) < 18
Default Value:    0
```

**What happens:** Same as above, but filters to only dependents where `age < 18`. If 2 of 3 children are under 18, writes `computed_data = {"MINOR_DEPENDENTS": 2}`.

#### Example 3: Sum Leave Days Taken

```
Rule Name:        Total Leave Days
Output Key:       LEAVE_DAYS_TAKEN
Rule Type:        sum
Source Data Type:  leave
Aggregate Field:  days
Filter:           rec.get('status') == 'Approved'
Default Value:    0
```

**What happens:** Finds all leave records for the employee in the period. Sums the `days` field from each. Writes `computed_data = {"LEAVE_DAYS_TAKEN": 5}`.

#### Example 4: Count Working Days from Attendance

```
Rule Name:        Working Days Present
Output Key:       WORKING_DAYS
Rule Type:        count
Source Data Type:  attendance
Filter:           rec.get('status') in ('Present', 'present', 'P')
Default Value:    0
```

#### Example 5: Calculate Tenure in Months

```
Rule Name:        Employee Tenure
Output Key:       TENURE_MONTHS
Rule Type:        date_diff
Source Data Type:  employee
Date Source Field: date_of_joining
Compare To:       period_end
Result Unit:      months
Default Value:    0
```

**What happens:** Reads `date_of_joining` from the employee's extracted_data. Calculates the difference in months from that date to the batch period end. Writes `computed_data = {"TENURE_MONTHS": 25}`.

#### Example 6: Check if Employee is in Probation

```
Rule Name:        Probation Status
Output Key:       IS_PROBATION
Rule Type:        date_check
Source Data Type:  employee
Date Source Field: date_of_joining
Compare To:       period_end
Check Operator:   within
Check Value:      6
Default Value:    0
```

**What happens:** Checks if `date_of_joining` is within 6 months of the period end date. Writes `computed_data = {"IS_PROBATION": 1}` (true) or `{"IS_PROBATION": 0}` (false).

#### Example 7: Complex Custom Logic (Python)

```
Rule Name:        Dependent Tax Deduction Eligibility
Output Key:       ELIGIBLE_DEPENDENT_COUNT
Rule Type:        python
Source Data Type:  dependent
Python Code:
    from datetime import date
    cutoff = period_end.replace(year=period_end.year - 18)
    eligible = []
    for dep in records:
        dob = dep.get('date_of_birth', '')
        if dob:
            dob_date = date.fromisoformat(dob)
            if dob_date > cutoff:  # under 18
                eligible.append(dep)
        elif dep.get('relationship') in ('Spouse', 'Parent'):
            eligible.append(dep)  # spouse/parent always eligible
    result = len(eligible)
```

### 7.5 When Transformation Rules Execute

Transformation rules run **after pull + extraction, before mapping**. They can be triggered:

1. **Automatically after pull** — when `action_pull_data()` completes, run all active rules for the connector
2. **Manually by operator** — "Recompute Transformations" button on the data store view
3. **At import batch creation** — just before field mappings are applied

The computed_data is **cached** on the data store record. It is not recomputed on every access — only when explicitly triggered. This means:
- If a transformation rule is added or changed, the operator clicks "Recompute" to update computed_data
- The cached result is what gets mapped to pay components

### 7.6 Transformation vs. Formula Engine — Clear Responsibilities

| Concern | Handled By | Example |
|---------|-----------|---------|
| Counting/aggregating API records | **Transformation Layer** | Count 3 dependents → `NUM_DEPENDENTS = 3` |
| Date calculations from API data | **Transformation Layer** | Join date → `TENURE_MONTHS = 25` |
| Summing across API record sets | **Transformation Layer** | Sum leave days → `LEAVE_DAYS_TAKEN = 5` |
| Adding two pay components | **Formula Engine** | `=BASIC + ALLOWANCE` → `GROSS` |
| Tax bracket calculation | **Formula Engine** | `=IF(GROSS>10000000, GROSS*0.1, 0)` |
| Statutory deduction formulas | **Formula Engine** | `=BASIC * 0.08` → SHUI employee |
| Simple field-level multiply/divide | **Field Mapping** | API annual salary ÷ 12 → monthly |

**Rule of thumb:**
- If it needs **multiple API records** → Transformation Layer
- If it needs **date arithmetic on API data** → Transformation Layer
- If it **combines pay components** → Formula Engine
- If it **converts a single value** → Field Mapping

---

## 8. Authentication & Security

### 8.1 Outbound Authentication (Odoo → External HRIS)

Since we are only **pulling** data, authentication is always outbound — Odoo authenticates against the external system:

| Method | Use Case | Implementation |
|--------|----------|----------------|
| **OAuth 2.0** | Zoho, Workday, modern APIs | Client credentials + refresh token (already implemented in `ZohoConnector`) |
| **API Key** | Custom HRIS, simpler APIs | Stored on `hr.integration.connector.api_key` |
| **Basic Auth** | Legacy systems, on-premise SAP | Username/password on connector record |
| **Bearer Token** | Pre-shared token setups | Stored on connector, refreshed manually |

### 8.2 Security Measures

- **Credentials encrypted at rest**: Stored with `groups="base.group_system"` (already implemented)
- **Token auto-refresh**: OAuth connectors refresh tokens before expiry (implemented in `ZohoConnector._refresh_access_token()`)
- **Connection test**: `action_test_connection()` validates credentials without pulling data
- **Audit trail**: Every pull is recorded with timestamp, duration, record count, and who triggered it
- **Company isolation**: `hr.api.data.store` has `company_id` — multi-company safe

> **Note:** No inbound authentication is needed since we are not exposing any APIs externally. External systems cannot call into our Odoo instance.

---

## 9. Data Flow — Detailed Scenario

### 9.1 Complete Monthly Payroll Cycle (Zoho People Example)

```
DAY 1 of month — Scheduled Pull
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cron triggers connector.action_pull_data()
    │
    ▼ ZohoConnector.authenticate() — OAuth 2.0 token refresh
    ▼ ZohoConnector.fetch_employees() — GET /api/forms/P_Employee/records
    ▼ ZohoConnector.fetch_payroll_data() — GET salary, attendance, leave
    │
    ▼ For each of 200 employees:
        ├── hr.api.data.store.create(raw_payload=<full API response>)
        ├── Extract & flatten → extracted_data
        ├── Compare with previous version → change_summary
        └── Match to Odoo employee → employee_id
    │
    ▼ Log: "Pulled 200 records. 5 salary changes detected."


DAY 20 — HR Reviews Stored Data
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HR operator opens Data Store dashboard
    │
    ├── Views 200 "extracted" records
    ├── Filters by has_changes=True → sees 5 salary updates
    ├── Reviews changes: "Employee EMP042: BASIC 14M → 15M"
    ├── Clicks "Re-pull" on specific employees if needed
    │
    ▼ Data is ready and validated by HR


DAY 22 — Create Import Batch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HR creates new hr.payroll.import.batch
    │
    ├── source_type = 'api_data_store'
    ├── connector_id = Zoho connector
    ├── period = Feb 2026
    │
    ▼ System loads 200 data store records for this period
    ▼ Applies field mappings → creates 200 import lines
    ▼ Marks store records as state='consumed'
    │
    ▼ action_match_employees() — matches 198, 2 new hires
    ▼ action_validate() — all pass
    ▼ action_process() — creates payslips with formula computation


DAY 25 — Review & Approve
━━━━━━━━━━━━━━━━━━━━━━━━━
Payslips reviewed via payroll analytics dashboard
Level 1 approval (HR) → Level 2 approval (GM)
Payslips confirmed → accounting entries generated
```

---

## 10. Country-Specific Considerations

### 10.1 Component Codes by Country

| Country | Key Components (Input Rules) |
|---------|------------------------------|
| **Vietnam (VN)** | `BASIC`, `ALLOWANCE_HOUSING`, `SHUI_*`, `TU_*`, `PIT_*`, `OVERTIME_*`, `13TH_MONTH` |
| **Indonesia (ID)** | `BASIC`, `BPJS_*`, `PPH21_*`, `THR`, `MEAL_ALLOWANCE`, `TRANSPORT_ALLOWANCE` |
| **India (IN)** | `BASIC`, `HRA`, `PF_*`, `ESI_*`, `TDS`, `LTA`, `MEDICAL_ALLOWANCE` |
| **Singapore (SG)** | `BASIC`, `CPF_*`, `SDL`, `FWL`, `AWS` |
| **Thailand (TH)** | `BASIC`, `SSF_*`, `PIT_*`, `PROVIDENT_FUND` |
| **Cambodia (KH)** | `BASIC`, `SENIORITY_*`, `NSSF_*` |
| **Malaysia (MY)** | `BASIC`, `EPF_*`, `SOCSO_*`, `EIS_*`, `PCB_*` |

### 10.2 Per-Country Behavior

The formula configuration (`hr.formula.config`) already selects the correct rules per country. The data store is country-agnostic — it stores whatever the API returns. The field mappings handle the translation from external field names to country-specific formula rule codes.

---

## 11. Error Handling Strategy

### 11.1 Pull Errors

| Error | Handling | Stored As |
|-------|----------|-----------|
| Authentication failure | Retry with token refresh; if still fails, mark connector as `error` | `connector.last_error` |
| API rate limit (429) | Exponential backoff with retry (max 3 attempts) | Pull log message |
| Partial response | Store what was received, flag records with errors | `data_store.state = 'error'` + `error_message` |
| Network timeout | Retry once, then abort and notify operator | `connector.last_error` |
| Invalid JSON response | Store raw response text for debugging, mark error | `data_store.error_message` |

### 11.2 Extraction Errors

| Error | Handling |
|-------|----------|
| Unexpected payload structure | Log warning, store raw but skip extraction, state = 'error' |
| Missing expected fields | Extract what's available, note missing fields in `error_message` |
| Data type mismatch | Coerce where possible (string "15000000" → float), flag if not |

### 11.3 Mapping Errors (at Import Batch time)

These are handled by the existing `hr.payroll.import.batch` pipeline — validation errors appear on import lines, same as with Excel imports.

---

## 12. Implementation Plan

### Phase 1: Data Store Model & Transformation Rules (Week 1)
**Create `hr.api.data.store` and `hr.api.transformation.rule` models**

| Task | Effort | Priority |
|------|--------|----------|
| Create `hr.api.data.store` model with JSONB fields | 1 day | HIGH |
| Implement extraction logic (raw → extracted) | 0.5 day | HIGH |
| Implement versioning & diff computation | 0.5 day | HIGH |
| Add `action_pull_data()` to `hr.integration.connector` | 1 day | HIGH |
| Wire up Zoho connector to create data store records | 1 day | HIGH |
| Create tree/form views for data store | 0.5 day | HIGH |
| Security rules (ir.model.access.csv) | 0.5 day | HIGH |

**Deliverables:**
- Working pull from Zoho → stored in database
- Data store browsable in Odoo UI
- Change detection across pulls

### Phase 1b: Transformation Engine (Week 1-2)
**Create `hr.api.transformation.rule` model and execution engine**

| Task | Effort | Priority |
|------|--------|----------|
| Create `hr.api.transformation.rule` model | 0.5 day | HIGH |
| Implement aggregate execution (count, sum, avg, min, max) | 1 day | HIGH |
| Implement filter expression evaluation | 0.5 day | HIGH |
| Implement date_diff and date_check rule types | 0.5 day | HIGH |
| Implement Python expression execution (sandboxed) | 0.5 day | HIGH |
| Write `computed_data` back to data store records | 0.5 day | HIGH |
| Create transformation rule views (form, tree) on connector | 0.5 day | HIGH |
| Add "Recompute Transformations" button | 0.5 day | MEDIUM |

**Deliverables:**
- Configurable transformation rules on each connector
- Dependent count, tenure calculation, attendance sum all working
- computed_data populated and visible in data store UI

### Phase 2: Import Batch Integration (Week 2)
**Connect data store to existing payroll pipeline**

| Task | Effort | Priority |
|------|--------|----------|
| Add `source_type = 'api_data_store'` to import batch | 0.5 day | HIGH |
| Implement "Load from Data Store" action on import batch | 1 day | HIGH |
| Wire field mappings to read from `extracted_data` + `computed_data` (merged) | 1 day | HIGH |
| Mark consumed records and link to import batch | 0.5 day | HIGH |
| Add auto-discover fields from stored data | 0.5 day | MEDIUM |
| Build field mapping wizard for first-time setup | 1 day | MEDIUM |

**Deliverables:**
- One-click "Load from API data" on import batch
- Field mappings transform stored data into formula inputs
- Traceability: data store ↔ import batch ↔ payslips

### Phase 3: Connector Activation (Week 3)
**Wire up additional connectors beyond Zoho**

| Task | Effort | Priority |
|------|--------|----------|
| Implement SAP connector pull (if client uses SAP) | 2 days | as needed |
| Implement Workday connector pull (if client uses Workday) | 2 days | as needed |
| Implement Oracle HCM connector pull (if client uses Oracle) | 2 days | as needed |
| Add scheduled cron for automatic monthly pulls | 0.5 day | MEDIUM |
| Implement re-pull for specific employees | 0.5 day | MEDIUM |

**Deliverables:**
- Multiple HRIS connectors pulling into the same data store
- Scheduled monthly pulls
- Selective re-pull capability

### Phase 4: Dashboard & Monitoring (Week 4)
**Visibility into integration health**

| Task | Effort | Priority |
|------|--------|----------|
| Data Store dashboard (summary stats, filters, actions) | 1 day | MEDIUM |
| Pull history log on connector form | 0.5 day | MEDIUM |
| Change detection alerts via web_notify | 0.5 day | MEDIUM |
| Data retention / archival policy (auto-archive after 12 months) | 0.5 day | LOW |

**Deliverables:**
- Dashboard showing pull history, change summary, data health
- Alerts when significant changes are detected
- Archival for old data

---

## 13. Module Structure

All new code lives within the existing `pb_hr_payroll_formula` module (no new module needed):

```
pb_hr_payroll_formula/
├── models/
│   ├── api_data_store.py              # NEW — hr.api.data.store model
│   ├── api_transformation_rule.py     # NEW — hr.api.transformation.rule model
│   ├── integration_connector.py       # EXTEND — add action_pull_data(), link to rules
│   ├── payroll_import_batch.py        # EXTEND — add source_type='api_data_store'
│   └── ... (existing files unchanged)
├── views/
│   ├── api_data_store_views.xml       # NEW — tree, form, search views
│   ├── api_transformation_rule_views.xml  # NEW — rule config views (on connector form)
│   ├── connector_views.xml            # EXTEND — add "Pull Data" + "Recompute" buttons
│   └── ... (existing files unchanged)
├── security/
│   └── ir.model.access.csv            # EXTEND — add data.store + transformation.rule access
├── data/
│   └── cron_data.xml                  # EXTEND — add scheduled pull crons
└── integrations/
    └── ... (existing connectors, extend to populate data store)
```

---

## 14. Migration Path from Excel to API

### 14.1 Gradual Migration Strategy

```
Month 1:  Excel imports continue as-is
          + Deploy data store model
          + Configure Zoho connector + field mappings
          + First test pull → verify stored data looks correct

Month 2:  Run both in parallel
          + Pull from API → create import batch from data store
          + Also import same month via Excel
          + Compare payslip results side-by-side

Month 3:  Switch primary source to API data store
          + Excel available as fallback
          + Monitor for discrepancies

Month 4:  API data store is primary
          + Excel used only for ad-hoc scenarios
          + Full monitoring in place
```

### 14.2 Backward Compatibility

The data store integration **does not break** the existing Excel workflow. Both methods feed into the same pipeline (`hr.payroll.import.batch` → `hr.formula.config` → `hr.payslip`). Users can freely switch between:
- `source_type = 'excel'` → upload spreadsheet (as today)
- `source_type = 'api_data_store'` → load from stored API data

---

## 15. Data Retention & Storage Estimates

### 15.1 Storage Sizing

| Metric | Estimate |
|--------|----------|
| Avg. raw payload per employee | ~2 KB (JSONB) |
| Avg. extracted data per employee | ~500 bytes (JSONB) |
| 500 employees × monthly pull | ~1.25 MB/month |
| 12 months retention | ~15 MB/year |
| With versioning (3 pulls/month) | ~45 MB/year |

This is negligible — even with 5,000 employees and daily pulls, annual storage would be under 500 MB.

### 15.2 Retention Policy

| Age | Action |
|-----|--------|
| 0–3 months | Active — fully queryable |
| 3–12 months | Retained — available for audit |
| 12+ months | Archived — `state = 'archived'`, excluded from default views |
| 24+ months | Eligible for deletion (configurable via system parameter) |

---

## 16. Decision Log

| Decision | Rationale |
|----------|-----------|
| **Pull-only, no push/webhooks** | Payroll is a monthly batch process. Real-time sync adds complexity without proportional value. Pull when needed, process when ready. |
| **No outbound APIs** | No external consumers for payslips or payroll data currently. Can be added later if needed, as a separate concern. |
| **`fields.Json` (JSONB) over `fields.Text` (JSON string)** | JSONB is indexable, queryable at DB level, and doesn't require `json.loads()` on every access. Industry standard for semi-structured data in PostgreSQL. |
| **Three-layer storage (raw + extracted + diff) + computed_data** | Separation of concerns: raw is audit trail (immutable), extracted is working copy (re-generable), diff enables change detection, computed_data holds transformation results. |
| **Separate transformation layer between storage and mapping** | The API returns multiple records per employee (dependents, attendance, leave). Payroll needs derived values (count, sum, date diff) that don't exist in any single record. Field mapping is one-to-one; transformation is many-to-one. They solve different problems. |
| **Transformation rules are configurable, not hardcoded** | Different clients have different HRIS structures and payroll needs. A Vietnamese company may need dependent counts for PIT deductions; an Indonesian one may need BPJS tier lookup. Rules must be per-connector. |
| **computed_data merges with extracted_data at mapping time** | Field mapping doesn't need to know whether a value came from the API or from a transformation rule. This keeps the mapping layer simple and uniform. |
| **One model, not multiple tables** | `hr.api.data.store` handles all data types via `data_type` selection. Simpler than separate models per data entity. JSONB handles the schema variance. |
| **Extend `pb_hr_payroll_formula`, not new module** | The data store is tightly coupled to the formula engine and import batch. A separate module would create unnecessary dependency management. |
| **Versioning with linked list (`previous_version_id`)** | Enables O(1) diff computation without scanning the full history. Also enables "show me the last 3 pulls for employee X" queries via simple traversal. |
| **Store first, transform, then map** | Decouples pull timing from payroll timing. HR can pull data on day 1, review changes on day 15, and create payslips on day 22 — at their own pace. |

---

## 17. Open Questions

1. **Which external HRIS systems are highest priority?** (Zoho connector is complete; SAP/Workday/Oracle are stubs)
2. **Pull frequency?** Monthly is default. Should we support more frequent pulls for attendance data?
3. **Data retention period?** 12 months proposed. Any compliance requirements for longer?
4. **Change notifications?** Should salary changes trigger Odoo activities/notifications, or just be visible in the UI?
5. **Re-extraction?** Should operators be able to re-extract from raw payload (e.g., after fixing a mapping)?
6. **Transformation rule templates?** Should we ship pre-built rules for common scenarios (dependent count, tenure calc) as demo data?

---

*Document Created: 15 February 2026*
*Last Updated: 15 February 2026*
*Author: Payobook Development Team*
