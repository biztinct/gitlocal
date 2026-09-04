# Workday Complete Feature Implementation Plan (v2)

## Decisions Made

| Question | Decision |
|----------|----------|
| Phase order | **Sequential: C → D → E → F → G → H** |
| Position Management | **Use pb_hr_payroll_demand as data source** (see analysis below) |
| Skills module | **hr_skills installed** ✅ — Phase G4 is unblocked |
| Payroll data for Budget vs Actual | **7 confirmed payslips** in hr_payslip with real Vietnamese salary components |
| Multi-currency | **Deferred** to future expansion — removed from Phase H |

---

## Key Discovery: pb_hr_payroll_demand Module

### What It Does
This is a **strategic workforce demand planning** module with 3 core models:

| Model | Purpose | Key Fields |
|-------|---------|------------|
| pb.workforce.capability | Organizational capabilities (Primary/Secondary/Enabler) with maturity levels | name, capability_type, maturity, skill_ids, role_ids |
| pb.workforce.role | Role profiles with skills, KPIs, criticality/scarcity segmentation | name, capability_id, skill_ids, segmentation_criticality |
| pb.workforce.demand.plan | Monthly headcount/FTE/cost demand plans per role with budget tracking | role_id, year, monthly_line_ids, planned_budget |

### Recommendation: Use as Soft Dependency — Do NOT install separately

> [!IMPORTANT]
> pb_hr_payroll_demand is currently **uninstalled** and its JS dashboard is **disabled** (incompatible with Odoo 19). Rather than installing it as a separate app, we should:
> 1. **Add it as a soft dependency** of pb_hr_workforce_planning (via try/except imports)
> 2. **Leverage its role/capability data** for Phase G (Position Management, Skills Gap)
> 3. **Bridge its demand data** into our unified WFP dashboard instead of maintaining two separate dashboards

This means Phase G gets simplified — instead of building wfp.position from scratch, we bridge pb.workforce.role + pb.workforce.demand.plan into WFP dashboard.

---

## Key Discovery: hr_recruitment Data

### Available Data
- **41 applicants** across 7 recruitment stages
- Pipeline: New (8) → Qualification (7) → First Interview (9) → Second Interview (6) → Contract Proposal (6) → Signed (2)
- Model: hr.applicant with stage_id, job_id, department_id

### Integration Plan
Phase G will connect recruitment pipelines to WFP:
- Show **hiring pipeline funnel** in dashboard
- Link hr.applicant to wfp.headcount.change
- Track **time-to-fill** and **cost-per-hire** metrics

---

## Key Discovery: Payroll Data for Budget vs. Actual

### Available Data
- **7 confirmed payslips** (state=done) + 14 draft payslips
- Real Vietnamese salary components: Ngach luong (base), PC tham nien (seniority), BHXH (social insurance), etc.
- Total confirmed payroll: ~224M VND across 7 employees

### Budget vs. Actual Approach
- **Forecast**: From wfp.monthly.projection
- **Actual**: From hr.payslip_line where slip_id.state = done grouped by month
- **Matching**: Map component codes between formula engine and payslip lines

---

## UI/UX Design Philosophy — World-Class Charts

### Design Principles
1. **Data-to-Ink Ratio**: Minimize chart chrome, let data speak
2. **Consistent Color Palette**: All charts share 6-color palette from CSS variables
3. **Storytelling Layout**: Charts in narrative flow (KPIs → trends → breakdowns → details)
4. **Micro-interactions**: Every chart element responds to hover with smooth transitions
5. **Responsive Containers**: Charts resize fluidly within bento grid cells

### Chart Library: Chart.js 4.x (Already Integrated)

| Chart Type | Used For | Premium Touches |
|------------|----------|-----------------|
| **Bar + Line Combo** | Weekly hours, Budget vs Actual | Gradient fills, dashed target line, rounded corners |
| **Horizontal Bar** | Dept utilization, Component breakdown | Animated entry, sorted by value, inline labels |
| **Doughnut** | Cost distribution, Total Rewards | Center stat, legend below, segment hover grow |
| **Scatter/Bubble** | Compa-ratio × Performance | Color by dept, size by salary, hover card |
| **Stacked Area** | Labor cost forecast | Gradient with transparency, confidence bands |
| **Waterfall** | Component cost changes | Green=decrease, Red=increase, connecting stems |
| **Heatmap** | Utilization × Employee × Day | Pure CSS grid with HSL color interpolation |
| **Funnel** | Recruitment pipeline | CSS-only with gradient steps |
| **Gauge/Radial** | Budget utilization % | SVG arc with animated fill |
| **Treemap** | Department cost allocation | CSS grid proportional sizing |

### Color System
```
--chart-blue:    hsl(220, 90%, 56%)   /* Primary metric */
--chart-emerald: hsl(155, 70%, 45%)   /* Positive/target */
--chart-amber:   hsl(35, 92%, 52%)    /* Warning/caution */
--chart-rose:    hsl(350, 80%, 55%)   /* Negative/over */
--chart-violet:  hsl(265, 75%, 55%)   /* Secondary/accent */
--chart-cyan:    hsl(190, 80%, 45%)   /* Tertiary */
```

### Tooltip Design
- Frosted glass background (backdrop-filter: blur(12px))
- Rounded corners, subtle shadow
- Bold value, muted label, mini trend sparkline

### Animation Strategy
- **Entry**: Charts animate with easeOutCubic (bars grow, lines draw, donuts fill)
- **Update**: Smooth transitions on data change (300ms ease)
- **Hover**: Scale up hovered element, dim others
- **Scroll**: IntersectionObserver triggers animation when visible

---

## Phase C: Budget vs. Actual Tracking & Scenario Comparison

**Goal**: Close the planning loop — track actual payroll spend against forecasts.

### Component C1: Budget vs. Actual Model

#### [NEW] budget_tracking.py
New model wfp.budget.actual comparing forecast vs real payroll:
- scenario_id, period_month, department_id
- forecast_headcount, forecast_cost (from wfp.monthly.projection)
- actual_headcount, actual_cost (from hr.payslip_line)
- variance_amount, variance_pct (computed)

API: get_budget_vs_actual_data(scenario_id)
- Maps Vietnamese component codes to WFP categories
- Returns: { months: [{month, forecast, actual, variance}], by_department: [...] }

Dashboard Chart: Dual bar (forecast=blue, actual=green) with variance line

### Component C2: Scenario Comparison (Finish)
- Enhance get_comparison_data() with per-department deltas
- Wire comparison dropdown → grouped bar chart overlay
- Side-by-side KPI cards

### Component C3: Audit Trail
- New model wfp.scenario.approval for logging all state changes
- Fields: scenario_id, action, user_id, timestamp, comment, snapshot_data (JSON)

---

## Phase D: Advanced Analytics & Visualizations

### D1: Compa-Ratio Scatter Plot
- API: get_compa_ratio_data()
- Chart: Bubble chart (X=compa-ratio, Y=performance, size=salary)
- Quadrant lines at compa-ratio=1.0 and performance=3.0

### D2: Department Cost Heatmap
- API: get_dept_cost_heatmap()
- Chart: CSS grid with HSL-interpolated backgrounds

### D3: Component Waterfall Chart
- API: get_component_waterfall()
- Chart: Waterfall bars (green=decrease, red=increase)

### D4: Total Rewards Statement
- New transient model wfp.total.rewards
- PDF-printable statement with doughnut chart
- Pulls from contract + formula engine

---

## Phase E: Approval Workflows & Governance

### E1: Multi-Level Approval Chain
- New model wfp.approval.step (role-based: Manager → HR → Finance → VP)
- Notification via mail.activity

### E2: Budget Guardrails
- New model wfp.budget.guardrail
- Rules: max increase %, department budget cap, compa-ratio bounds
- Actions: warn (yellow badge) or block (prevent submission)

### E3: Manager Worksheet View
- Transient model wfp.manager.worksheet
- Shows only direct reports with budget progress bar
- Pre-populated merit matrix suggestions
- Guardrail violations inline

---

## Phase F: Advanced Labor Forecasting

### F1: Scheduled vs. Actual Hours
- Reads hr.shift.planning vs hr.attendance
- Dual-bar chart by day-of-week

### F2: OT Cost Breakdown by Type
- Categorizes from hr.overtime.request.overtime_type
- "What-if" slider for OT reduction simulation

### F3: Employee Utilization Heatmap
- Employee x Day matrix with HSL color scale
- Red (<6h underwork), Green (6-8h), Amber (8-10h), Red (>10h burnout)

### F4: Labor Cost Forecast (3/6/12 Month)
- New transient model wfp.labor.forecast
- Trailing 12-week average x hourly rate projected forward
- Stacked area chart with confidence bands

### F5: Absence Impact Analysis
- Reads hr.leave by type
- Donut showing leave distribution + cost impact bar

---

## Phase G: Position Management, Recruitment & Talent

### G1: Bridge pb_hr_payroll_demand into WFP
- Soft dependency via try/except
- API: get_demand_planning_data() reads pb.workforce.demand.plan + pb.workforce.role
- Dashboard: Role demand heatmap + FTE gap chart

### G2: Recruitment Pipeline Integration
- API: get_recruitment_pipeline() reads hr.applicant by stage
- Dashboard: Recruitment funnel chart
- Link hr.applicant to wfp.headcount.change

### G3: Attrition/Turnover Modeling
- Enhanced headcount_change.py with historical_turnover_rate
- Projected departures and replacement costs

### G4: Skills Gap Analysis
- New transient model wfp.skills.gap
- Uses hr.skill + hr.employee.skill (Odoo 19 built-in)
- Cross-references with pb.workforce.role.skill_ids
- Horizontal bar chart showing skill coverage %

---

## Phase H: Self-Service & Collaboration

### H1: Role-Based Dashboard Views
- Admin: full dashboard, all departments
- Manager: department-filtered, direct reports only
- User: read-only KPI summary

### H2: Collaborative Comments
- Collapsible Discussion panel using existing mail.thread

### H3: Plan Version Control
- New model wfp.scenario.version with JSON snapshots
- Save Version button + Compare Versions action

---

## New Models Summary (9 total)

| Model | Type | Phase |
|-------|------|-------|
| wfp.budget.actual | Stored | C |
| wfp.scenario.approval | Stored | C |
| wfp.total.rewards | Transient | D |
| wfp.approval.step | Stored | E |
| wfp.budget.guardrail | Stored | E |
| wfp.manager.worksheet | Transient | E |
| wfp.labor.forecast | Transient | F |
| wfp.skills.gap | Transient | G |
| wfp.scenario.version | Stored | H |

---

## Open Questions

> [!IMPORTANT]
> 1. **Install pb_hr_payroll_demand?** Recommend installing before Phase G so role/capability data is available. Its JS dashboard is disabled. Shall I install it?

> [!IMPORTANT]
> 2. **Performance ratings**: Compa-ratio scatter (Phase D1) needs employee performance scores. Is hr.appraisal installed? Or use a custom field?

> [!IMPORTANT]
> 3. **Dashboard tab structure**: With all phases, proposed layout:
>    - Compensation Planning (existing)
>    - Labor Analytics (existing)
>    - Budget & Actuals (Phase C)
>    - Workforce Demand (Phase G)
>    Or should some be chart panels within existing tabs?
