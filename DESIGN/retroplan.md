# Implementation Plan: Mid-Cycle Payroll, Retroactive Adjustments & Mid-Month Promotions

## Executive Summary

Design and implement enterprise-grade payroll features for the Odoo 16 formula-based system:

1. **Mid-Cycle & End-Cycle Payroll** - Split monthly payments with automatic advance tracking and settlement
2. **Retroactive Adjustments** - Backdated salary/component changes with full audit trail
3. **Mid-Month Promotions** - Pro-rated salary calculations for mid-month changes

**Key Design Principles**:
- Leverage existing formula engine and contract component tracking
- Maintain 2-level approval workflow (HR → GM)
- Full audit compliance with who/when/why tracking
- Production-ready with comprehensive edge case handling

---

## User Requirements Summary

### Mid-Cycle & End-Cycle
- **Calculation**: Configurable percentage of monthly salary (e.g., 40% on 15th)
- **Periods**: Configurable dates (e.g., 1st-15th mid, 16th-31st end)
- **Settlement**: End-cycle automatically deducts mid-cycle advance as line item
- **Tracking**: System remembers mid-cycle payments per employee/period

### Retroactive Adjustments
- **Scenarios**: Salary increases, allowance changes, bonuses, tax adjustments, arrears (all backdated)
- **Calculation**: Delta (new - old) × affected months
- **Payment**: Add as line items in next regular payslip
- **Approval**: Same 2-level workflow as regular payroll

### Mid-Month Promotions
- **Changes**: Basic salary, grade, allowances, tax components
- **Calculation**: Pro-rated by days at old/new rates
- **Method**: Daily rate = Monthly / Calendar Days (or Working Days - configurable)
- **Timing**: Immediate with pro-rating OR next full month (configurable)

---

## Architecture Overview

### New Models (6 total)

#### 1. `hr.payroll.cycle.config` - Cycle Configuration
**Location**: `pb_hr_payroll_formula/models/payroll_cycle_config.py`

Controls mid/end-cycle split rules:
- Mid-cycle percentage (e.g., 40%)
- Period date ranges (configurable)
- Calculation method (percentage/fixed/formula)
- Auto-deduction settings

#### 2. `hr.payslip.cycle.advance` - Mid-Cycle Tracking
**Location**: `pb_hr_payroll_formula/models/payslip_cycle_advance.py`

Tracks each mid-cycle advance and settlement:
- Employee, period (e.g., "2026-01")
- Advance amount paid
- Deducted amount in end-cycle
- State: draft → paid → settled
- Links to both mid-cycle and end-cycle payslips

**Constraint**: `unique(employee_id, period_key)` - one advance per employee per month

#### 3. `hr.payroll.retro.adjustment` - Retro Tracking
**Location**: `pb_hr_payroll_formula/models/payroll_retro_adjustment.py`

Manages retroactive adjustments with approval workflow:
- Effective date (backdated)
- Affected period range (from/to dates)
- Old amount, new amount, delta
- Calculated total: delta × affected months
- State: draft → level1 → level2 → approved → paid
- HR/GM approval tracking

#### 4. `hr.payslip.retro.line` - Retro Payslip Links
**Location**: `pb_hr_payroll_formula/models/payslip_retro_line.py`

Links retro adjustments to payslip lines:
- Payslip ID, retro adjustment ID
- Created payslip line ID
- Displays: "Retro: Salary Increase (Oct 2025 - Dec 2025): 60,000"

#### 5. `hr.contract.promotion` - Promotion Tracking
**Location**: `pb_hr_payroll_formula/models/contract_promotion.py`

Tracks promotions with pro-rated calculations:
- Effective date, old/new wage, old/new job
- Pro-ration method (immediate/next_month)
- Daily rate method (calendar_days/working_days)
- Days at old/new rate (computed)
- Amount at old/new rate (computed)
- State: draft → level1 → level2 → approved → applied

#### 6. `hr.contract.promotion.component` - Component Changes
**Location**: Same file as promotion

Tracks allowance changes during promotion:
- Advantage template, old/new amounts
- Pro-rate flag per component
- Computed amounts if prorated

---

### Model Extensions

#### Extend `hr.payslip`
**File**: `pb_hr_payroll_formula/models/hr_payslip_formula.py` (after line 73)

**New Fields**:
```python
# Cycle fields
is_mid_cycle = fields.Boolean()
is_end_cycle = fields.Boolean()
cycle_advance_id = fields.Many2one('hr.payslip.cycle.advance')
mid_cycle_deduction = fields.Monetary()

# Retro fields
retro_line_ids = fields.One2many('hr.payslip.retro.line', 'payslip_id')
total_retro_amount = fields.Monetary(compute='_compute_total_retro')
has_retro_adjustments = fields.Boolean(compute='_compute_total_retro')

# Promotion fields
promotion_id = fields.Many2one('hr.contract.promotion')
is_prorated = fields.Boolean()
proration_details = fields.Text()  # JSON breakdown
```

**New Methods**:
- `action_include_pending_retro_adjustments()` - Find and add approved retro to payslip
- Override `action_payslip_done()` - Update advance/retro states when approved

#### Extend `hr.payroll.import.batch`
**File**: `pb_hr_payroll_formula/models/payroll_import_batch.py`

**Note**: `payroll_period` field ALREADY exists with 'mid_cycle' and 'end_cycle' options (line 78-84)

**New Fields**:
```python
cycle_config_id = fields.Many2one('hr.payroll.cycle.config')
auto_apply_retro_adjustments = fields.Boolean(default=True)
```

**Enhanced Methods**:
- `_create_payslip()` (line 1128) - Add cycle/retro logic
- `_process_mid_cycle_advance()` - NEW: Create advance tracking
- `_process_end_cycle_settlement()` - NEW: Deduct advance
- `_create_mid_cycle_deduction_line()` - NEW: Add deduction line

#### Extend `hr.contract`
**File**: `pb_hr_payroll_formula/models/hr_contract.py`

**New Fields**:
```python
promotion_count = fields.Integer(compute='_compute_promotion_count')
last_promotion_date = fields.Date(compute='_compute_last_promotion')
```

**New Methods**:
- `action_view_promotions()` - Show promotion history

---

## Critical Implementation Details

### 1. Mid-Cycle Advance Flow

**When `payroll_period = 'mid_cycle'`**:

1. Import batch processes employee data (days 1-15)
2. Calculate advance: `contract.wage × config.mid_cycle_percentage / 100`
3. Create `hr.payslip.cycle.advance` record:
   - employee_id, period_key = "2026-01"
   - advance_amount = 40,000
   - state = 'draft'
4. Create mid-cycle payslip with advance amount
5. On payslip approval → advance.state = 'paid'

**Formula Variables Available**:
```python
IS_MID_CYCLE = 1.0
# Formula: =IF(IS_MID_CYCLE=1, BASIC*0.4, 0)
```

### 2. End-Cycle Settlement Flow

**When `payroll_period = 'end_cycle'`**:

1. Import batch processes full month data
2. Find mid-cycle advance: `search([('employee_id', '=', emp), ('period_key', '=', '2026-01'), ('state', '=', 'paid')])`
3. Create end-cycle payslip with full month calculation
4. Add deduction line:
   - name: "Mid-Cycle Advance Deduction (15-Jan)"
   - code: 'MID_CYCLE_DED'
   - amount: **-40,000** (negative)
5. Link payslip to advance
6. On approval → advance.state = 'settled'

**Result**:
```
GROSS SALARY:           100,000
- TAX:                  -10,000
- INSURANCE:             -5,000
- MID-CYCLE DEDUCTION:  -40,000  ← Added automatically
= NET PAY:               45,000

Total Paid: 40,000 (mid) + 45,000 (end) = 85,000 net
```

### 3. Retroactive Adjustment Flow

**Creation**:
1. User creates `hr.payroll.retro.adjustment`:
   - Effective date: 2025-10-01
   - Period: Oct 2025 - Dec 2025 (3 months)
   - Old amount: 80,000, New: 100,000
   - Delta: 20,000
   - Total: 60,000 (20k × 3 months)

**Approval**:
2. Submit → HR Approve → GM Approve
3. State: approved (is_paid = False)

**Payment**:
4. Next payslip creation (Jan 2026):
   - Calls `action_include_pending_retro_adjustments()`
   - Finds approved retro for employee
   - Creates `hr.payslip.retro.line` link
   - Creates payslip line:
     - name: "Retro: Salary Increase (Oct 2025 - Dec 2025)"
     - code: RETRO_123
     - amount: 60,000

5. On payslip approval → retro.state = 'paid'

**Formula Variables**:
```python
RETRO_TOTAL = 60,000
# Formula: NETPAY = GROSS - DEDUCTIONS + RETRO_TOTAL
```

### 4. Pro-Rated Promotion Flow

**Promotion Creation**:
1. Create promotion effective Jan 16, 2026
2. Old wage: 60,000, New: 80,000
3. Calculate pro-ration:
   - January: 31 days
   - Days at old: 15 (Jan 1-15)
   - Days at new: 16 (Jan 16-31)
   - Daily rate old: 60,000 / 31 = 1,935.48
   - Daily rate new: 80,000 / 31 = 2,580.65
   - Amount at old: 29,032.26
   - Amount at new: 41,290.32
   - **Total: 70,322.58**

**Approval & Application**:
4. Submit → HR Approve → GM Approve → Apply
5. On apply:
   - Close old contract (date_end = Jan 15)
   - Create new contract (date_start = Jan 16, wage = 80k)
   - State: applied

**Payslip Integration**:
6. January payslip creation:
   - Detect promotion in effective month
   - Override: `input_values['BASIC'] = 70,322.58`
   - Set: `is_prorated = True`
   - Store breakdown in `proration_details`

**Display on Payslip**:
```
Pro-Rated Salary
Promotion effective: Jan 16, 2026
15 days @ 60,000 = 29,032.26
16 days @ 80,000 = 41,290.32
────────────────────────────
Total: 70,322.58
```

---

## Formula System Integration

### New Formula Variables

Add to `_get_formula_input_values()` in `hr_payslip_formula.py`:

```python
values.update({
    'IS_MID_CYCLE': 1.0 if self.is_mid_cycle else 0.0,
    'IS_END_CYCLE': 1.0 if self.is_end_cycle else 0.0,
    'MID_CYCLE_DEDUCTION': self.mid_cycle_deduction or 0.0,
    'IS_PRORATED': 1.0 if self.is_prorated else 0.0,
    'RETRO_TOTAL': self.total_retro_amount or 0.0,
})
```

### Example Formulas

**Mid-Cycle Advance**:
```
Code: MID_CYCLE_ADVANCE
Formula: =IF(IS_MID_CYCLE=1, BASIC*0.4, 0)
```

**Net Pay (End-Cycle)**:
```
Code: NETPAY
Formula: =GROSS - TOTAL_DEDUCTIONS - MID_CYCLE_DEDUCTION + RETRO_TOTAL
```

**Pro-Ration Note**:
```
Code: PRORATION_NOTE
Formula: =IF(IS_PRORATED=1, "Salary pro-rated", "")
```

---

## User Interface

### Menus

```
Payroll
├── Payslips
├── Payslip Batches
├── Advanced Payroll (NEW)
│   ├── Mid-Cycle Advances
│   ├── Retroactive Adjustments
│   └── Promotions & Changes
├── Configuration
│   ├── Formula Configurations
│   ├── Cycle Configuration (NEW)
│   └── Salary Structures
```

### Key Forms

#### 1. Payroll Cycle Configuration
- Path: Payroll → Configuration → Cycle Configuration
- Settings: Mid-cycle %, period dates, calculation method
- Auto-deduction checkbox

#### 2. Retroactive Adjustment Form
- Path: Payroll → Advanced Payroll → Retroactive Adjustments
- Status bar: Draft | Level1 | Level2 | Approved | Paid
- Fields: Employee, effective date, period range, old/new amounts
- Auto-calculated: Delta, total adjustment
- Required: Reason text field

#### 3. Promotion Wizard
- Path: Employees → [Employee] → Actions → Create Promotion
- Multi-step wizard:
  - Step 1: Basic info (type, date, reason)
  - Step 2: Salary change (old/new, auto-calc increase %)
  - Step 3: Position change
  - Step 4: Pro-ration options (immediate/next month)
  - Step 5: Preview calculation breakdown
- Final: Create draft or submit for approval

#### 4. Enhanced Payslip Form
- New sections (conditionally visible):
  - **Cycle Information**: Shows mid/end-cycle details, deduction
  - **Retroactive Adjustments**: Lists retro lines with total
  - **Pro-Rated Salary**: Shows promotion breakdown

---

## Approval Workflows

### Retroactive Adjustments
```
Draft → Level1 (HR) → Level2 (GM) → Approved → Paid
```

- **Access Control**:
  - Draft/Submit: `group_payroll_base_officer`
  - Level1: `group_payroll_base_manager`
  - Level2: `group_payroll_super_admin`

### Promotions
```
Draft → Level1 (HR) → Level2 (GM) → Approved → Applied
```

- **Apply Action**: Creates new contract, closes old one
- **Auto-Applied**: When creating payslip in effective month

### Mid-Cycle Advances
```
Draft → Paid → Settled
```

- **Automatic**: No manual workflow
- **Transitions**: Triggered by payslip approval

---

## Edge Cases Handled

### Mid-Cycle
- ✅ Employee joins mid-month (no advance for first month)
- ✅ Employee leaves after mid-cycle paid (deduct from final settlement)
- ✅ Duplicate prevention (unique constraint on period_key)
- ✅ Mid-cycle cancelled after payment (reversal mechanism)
- ✅ No end-cycle created (advance stays in 'paid' state, manual settlement)

### Retroactive
- ✅ Overlapping adjustments (both allowed, cumulative)
- ✅ Retro for past tax year (flag: requires_tax_review)
- ✅ Employee terminated before retro paid (manual payment option)
- ✅ Negative retro (overpayment recovery, spread over months)
- ✅ Duplicate payment prevention (check is_paid flag)

### Promotions
- ✅ Multiple promotions same month (3-period pro-ration)
- ✅ Promotion on last day (user chooses immediate vs. next month)
- ✅ Promotion with contract gap (validation error, must fix)
- ✅ Demotion (salary decrease, same logic, negative delta)
- ✅ Component removed (track as old=amount, new=0)

---

## Implementation Sequence

### Phase 1: Foundation (Week 1)
- Create 6 new models with fields, relationships, constraints
- Add fields to existing models (hr.payslip, hr.contract, hr.payroll.import.batch)
- Create basic views (tree/form) for all models
- Set up security rules (ir.model.access.csv)

### Phase 2: Mid-Cycle Processing (Week 2)
- Implement `_process_mid_cycle_advance()` in payroll_import_batch.py
- Create advance on payslip approval (override action_payslip_done)
- Add formula variable IS_MID_CYCLE
- Test: Import → Create → Approve → Verify state='paid'

### Phase 3: End-Cycle Settlement (Week 3)
- Implement `_process_end_cycle_settlement()`
- Implement `_create_mid_cycle_deduction_line()`
- Add deduction to payslip lines
- Update advance to 'settled'
- Test: End-cycle → Find advance → Deduct → Verify total paid

### Phase 4: Retroactive Adjustments (Week 4)
- Create retro adjustment model with approval workflow
- Implement `action_include_pending_retro_adjustments()` in payslip
- Create approval buttons (submit, HR approve, GM approve)
- Add retro line creation logic
- Test: Create → Approve → Include in payslip → Mark paid

### Phase 5: Promotions (Week 5)
- Create promotion models with pro-ration calculation
- Implement `calculate_prorated_salary()` method
- Create promotion wizard with multi-step flow
- Implement `action_apply_promotion()` for contract creation
- Test: Create → Calculate → Apply → Verify payslip pro-ration

### Phase 6: Integration & Testing (Week 6)
- Full integration: mid-cycle + retro in same payslip
- Edge case testing (all scenarios above)
- Performance testing (large batches)
- Security testing (approval workflows)

### Phase 7: UI & Reports (Week 7)
- Settlement reports (mid-cycle advances)
- Retro adjustment reports (audit trail)
- Enhanced payslip report template (cycle/retro details)
- Demo data for testing

### Phase 8: Documentation (Week 8)
- User manual (how to use each feature)
- Technical documentation (for developers)
- Training materials

---

## Critical Files Reference

### Files to Create (6 new models)

1. `pb_hr_payroll_formula/models/payroll_cycle_config.py`
2. `pb_hr_payroll_formula/models/payslip_cycle_advance.py`
3. `pb_hr_payroll_formula/models/payroll_retro_adjustment.py`
4. `pb_hr_payroll_formula/models/payslip_retro_line.py`
5. `pb_hr_payroll_formula/models/contract_promotion.py`
6. `pb_hr_payroll_formula/models/contract_promotion_component.py` (can be in same file)

### Files to Modify (3 existing files)

1. **`pb_hr_payroll_formula/models/payroll_import_batch.py`**
   - **Line 1128**: Enhance `_create_payslip()` method
   - **Add**: `_process_mid_cycle_advance()`, `_process_end_cycle_settlement()`, `_create_mid_cycle_deduction_line()`

2. **`pb_hr_payroll_formula/models/hr_payslip_formula.py`**
   - **After line 73**: Add new fields (is_mid_cycle, retro_line_ids, promotion_id, etc.)
   - **Add**: `action_include_pending_retro_adjustments()` method
   - **Override**: `action_payslip_done()` to update advance/retro states
   - **Add**: New formula variables in `_get_formula_input_values()`

3. **`pb_hr_payroll_formula/models/hr_contract.py`**
   - **Add**: promotion_count, last_promotion_date fields
   - **Add**: `action_view_promotions()` method

### View Files to Create

1. `pb_hr_payroll_formula/views/payroll_cycle_config_views.xml`
2. `pb_hr_payroll_formula/views/payslip_cycle_advance_views.xml`
3. `pb_hr_payroll_formula/views/payroll_retro_adjustment_views.xml`
4. `pb_hr_payroll_formula/views/contract_promotion_views.xml`
5. `pb_hr_payroll_formula/wizards/promotion_wizard_views.xml`

### Security Files to Update

1. `pb_hr_payroll_formula/security/ir.model.access.csv` - Add access rules for new models

### Menu Files to Update

1. `pb_hr_payroll_formula/views/payroll_menu_structure.xml` - Add "Advanced Payroll" menu

---

## Data Flow Summary

### Mid-Cycle to End-Cycle
```
Day 1-15: MID-CYCLE
├─ Import batch (period='mid_cycle')
├─ Calculate 40% advance = 40,000
├─ Create payslip + advance record (state='draft')
├─ Approve payslip
└─ Advance state → 'paid'

Day 16-31: END-CYCLE
├─ Import batch (period='end_cycle')
├─ Find advance for period "2026-01"
├─ Create payslip with full calculation
├─ Add deduction line: -40,000
├─ Link to advance
├─ Approve payslip
└─ Advance state → 'settled'

Result: Total paid = 40,000 + 65,000 = 105,000 net
```

### Retroactive Adjustment
```
Timeline:
├─ Oct-Dec 2025: Paid 80k/month (should be 100k)
├─ Jan 2026: Create retro adjustment
│   ├─ Delta: 20,000/month × 3 months = 60,000
│   ├─ Submit → HR Approve → GM Approve
│   └─ State: 'approved'
├─ Jan 2026 payslip:
│   ├─ Auto-include retro (60,000)
│   ├─ Payslip total: BASIC (100k) + RETRO (60k) = 160k gross
│   └─ Approve
└─ Retro state → 'paid'
```

### Mid-Month Promotion
```
Event: Promotion on Jan 16
├─ Create promotion record
├─ Calculate pro-ration:
│   ├─ 15 days @ 60,000 = 29,032.26
│   └─ 16 days @ 80,000 = 41,290.32
├─ Approve → Apply
│   ├─ Close old contract (Jan 15)
│   └─ Create new contract (Jan 16, 80k)
├─ January payslip:
│   ├─ Detect promotion
│   ├─ Override BASIC = 70,322.58 (pro-rated)
│   └─ Store breakdown
└─ February payslip: BASIC = 80,000 (full new rate)
```

---

## Success Criteria

✅ **Functionality**:
- Mid-cycle advances automatically deducted in end-cycle
- Retro adjustments correctly calculated and paid
- Promotions pro-rated by day with accurate daily rates

✅ **Audit Compliance**:
- Full who/when/why tracking on all changes
- Approval history preserved
- Payment trail complete

✅ **Performance**:
- Handle 1000+ employees in batch
- No performance degradation
- Optimized queries (indexed fields)

✅ **User Experience**:
- Intuitive wizards for promotions
- Clear approval workflows
- Helpful error messages

✅ **Edge Cases**:
- All scenarios handled gracefully
- No data corruption
- Reversible operations

---

## Technical Design Highlights

### Best Practices Applied

1. **SAP-style Retro Accounting**: Delta calculation with period tracking
2. **Workday Pro-Ration**: Daily rate methods (calendar/working days)
3. **ADP Advance System**: Automatic advance/deduction matching
4. **Oracle Audit Trail**: Full change history with approval chain
5. **Enterprise State Management**: Locked states, no reprocessing

### Database Design

- **Normalization**: Separate models for each concern
- **Constraints**: Unique constraints prevent duplicates
- **Indexing**: Key fields indexed (employee_id, period_key, state)
- **Cascading**: Proper ondelete rules

### Security

- **Access Control**: Role-based (Officer/Manager/Admin)
- **Approval Gates**: 2-level approval enforced
- **Audit Logging**: Auto-populated created_by, changed_by fields
- **Data Integrity**: Constraints, validations, checks

---

## End of Plan

This comprehensive plan provides a production-ready, enterprise-grade solution for mid-cycle payroll, retroactive adjustments, and mid-month promotions in your Odoo 16 formula-based payroll system.

**Key Strengths**:
- Leverages existing formula engine and contract tracking
- Handles all edge cases identified
- Full audit compliance
- Industry best practices (SAP, Workday, ADP, Oracle)
- Performance-optimized
- User-friendly workflows

**Ready for Implementation**: All models, fields, methods, and workflows fully specified with exact file paths and code integration points.
