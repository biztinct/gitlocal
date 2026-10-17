# PayAI Phase 2 — Implementation Plan

## Goal

Enhance PayAI with broader data coverage, a modern centered-modal chat UI matching the `health_development_ai` design, configurable AI icon, chart type switching, and chart drill-down.

---

## Proposed Changes

### Component 1: New Data Queries (Backend)

#### [MODIFY] [payroll_data_query.py](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/models/payroll_data_query.py)

Add 4 new query methods + keyword routes:

| Query | Keywords | Model | Returns |
|-------|----------|-------|---------|
| **Attendance** | `attendance, check in, check out, late, present` | `hr.attendance` (1,026 records) | Average hours/day by dept, late arrivals, attendance rate |
| **Leaves** | `leave, absence, time off, vacation, sick leave` | `hr.leave` (12 records) | Leave days by type, department, approval status |
| **Recruitment** | `recruit, applicant, hiring, candidate, vacancy, job opening` | `hr.applicant` (41 records) | Applicants by stage, department, source |
| **Timesheets** | `timesheet, hours logged, time spent, project hours` | `account.analytic.line` (via hr_timesheet) | Hours by project, employee, department |

> [!IMPORTANT]
> **Attendance data (1,026 records):** Will use date filtering (last 30 days default) + `read_group` aggregation to avoid sending raw records to GPT. Only summaries are sent.

#### [MODIFY] [__manifest__.py](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/__manifest__.py)

Add dependencies:
```python
'depends': [
    ...existing...,
    'hr_holidays',      # leaves
    'hr_attendance',    # attendance
    'hr_recruitment',   # recruitment
    'hr_timesheet',     # timesheets
],
```

---

### Component 2: Modernize Icons

#### [MODIFY] [ai_insight_chat.xml](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.xml)

Replace all emojis with FontAwesome icons:

| Current | Replace With | Where |
|---------|-------------|-------|
| `✨` pill icon | `<i class="fa fa-bolt"/>` | Floating pill |
| `🤖` header/avatar | `<img>` (configurable) or `<i class="fa fa-robot"/>` | Header, message avatars |
| `👤` user avatar | `<i class="fa fa-user"/>` | User messages |
| `🗑️` clear chat | `<i class="fa fa-trash-o"/>` | Header action |
| `✕` close | `<i class="fa fa-times"/>` | Header action |
| `💡` insights | `<i class="fa fa-lightbulb-o"/>` | Insight cards |
| `📌` pin | `<i class="fa fa-thumb-tack"/>` | Pin to dashboard |
| `➤` send | `<i class="fa fa-paper-plane"/>` | Send button |

#### [MODIFY] [payroll_ai_menus.xml](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/views/payroll_ai_menus.xml)

Remove emoji from menu names — Odoo 19 uses `web_icon` for the root menu and FA icons render poorly in menu labels:

```xml
<menuitem name="Chat with PayAI" .../>   <!-- was: 💬 Chat with PayAI -->
<menuitem name="Dashboard" .../>          <!-- was: 📊 Dashboard -->
<menuitem name="Chat History" .../>       <!-- was: 📋 Chat History -->
<menuitem name="Configuration" .../>      <!-- was: ⚙️ Configuration -->
```

---

### Component 3: Centered Modal Chat (CSS Redesign)

#### [MODIFY] [ai_insight_chat.scss](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.scss)

Redesign to match the `bfsi_ai_coach_panel.scss` pattern:

- **Pill**: Dark indigo background (#2d2a6e) with pulse animation and avatar glow rings
- **Panel → Centered Modal**: `position: fixed; top: 50%; left: 50%` with `modalExpandFromPill` animation
- **Backdrop**: Blurred overlay (`backdrop-filter: blur(8px)`)
- **Chat area**: Animated mesh gradient background with dot pattern overlay
- **Messages**: Larger bubble radius (20px), slide-in animation, gradient backgrounds
- **Input**: Rounded 16px, focus glow, circular send button

#### [MODIFY] [ai_insight_chat.xml](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.xml)

Update template structure to support:
- Backdrop div when panel is open
- Avatar rings around icon in header
- Configurable AI icon (`<img>` for custom icon, `<i>` for fallback)

---

### Component 4: Configurable AI Icon

#### [MODIFY] [payroll_ai_config.py](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/models/payroll_ai_config.py)

Add Image field + RPC endpoint (same pattern as `hr.ai.provider.config`):

```python
ai_icon = fields.Image(
    string='AI Chat Avatar',
    help='Custom icon for the PayAI chat. 128×128 recommended.',
    max_width=256, max_height=256,
)

@api.model
def rpc_get_ai_icon_url(self):
    """Return icon as data URL for frontend."""
    config = self.get_active_config()
    if config and config.ai_icon:
        icon_b64 = config.ai_icon
        if isinstance(icon_b64, bytes):
            icon_b64 = icon_b64.decode('utf-8')
        return 'data:image/png;base64,' + icon_b64
    return False
```

#### [MODIFY] [payroll_ai_config_views.xml](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/views/payroll_ai_config_views.xml)

Add Image widget to the form view for uploading the avatar.

#### [MODIFY] [ai_insight_chat.js](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.js)

Load icon URL on mount and use it in template:
```javascript
onMounted(() => {
    this._loadHistory();
    this._loadAiIcon();
});
```

---

### Component 5: Chart Type Switcher

#### [MODIFY] [chart_renderer.js](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.js)

Add chart type switching:
- New prop `showToolbar` (boolean, default false)
- Toolbar with icon buttons for: **bar, line, pie, doughnut, radar, polarArea, scatter, bubble**
- `switchChartType(newType)` method that updates the internal chart config and re-renders
- Only show applicable types (e.g., hide scatter for categorical data)

#### [MODIFY] [chart_renderer.xml](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.xml)

Add toolbar above the canvas:
```xml
<div class="payai-chart-toolbar" t-if="props.showToolbar">
    <button t-foreach="chartTypes" t-as="ct" t-key="ct.type"
            t-att-class="'chart-type-btn ' + (currentType === ct.type ? 'active' : '')"
            t-on-click="() => switchChartType(ct.type)"
            t-att-title="ct.label">
        <i t-att-class="ct.icon"/>
    </button>
</div>
```

#### [MODIFY] [chart_renderer.scss](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.scss)

Style the compact toolbar with active state highlighting.

#### [MODIFY] [ai_dashboard.xml](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/ai_dashboard/ai_dashboard.xml)

Pass `showToolbar="true"` for dashboard widgets.

---

### Component 6: Chart Drill-Down to List/Pivot View

#### [MODIFY] [chart_renderer.js](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.js)

Add click handler on chart elements. When a user clicks a bar/slice:
- Read the label (e.g., "Ban hành chính" department)
- Emit an event or call `actionService` to open the Odoo list view filtered by that label
- Map query types to Odoo action targets:

| Query Type | Click Opens | Model |
|-----------|------------|-------|
| `salary_by_department` | Employee list filtered by department | `hr.employee` |
| `headcount_by_department` | Employee list filtered by department | `hr.employee` |
| `payroll_periods` | Payslip list filtered by date | `hr.payslip` |
| `attendance` | Attendance list filtered by department | `hr.attendance` |
| `leave_by_type` | Leave list filtered by type | `hr.leave` |
| `recruitment` | Applicant list filtered by stage | `hr.applicant` |

#### [MODIFY] [chart_renderer.js](file:///Users/adity/Documents/GitHub/gitlocal/pb_payroll_ai_insights/static/src/components/chart_renderer/chart_renderer.js)

New prop `drillDownConfig` with model name and filter field:
```javascript
static props = {
    chartConfig: { type: Object, optional: true },
    showToolbar: { type: Boolean, optional: true },
    drillDownConfig: { type: Object, optional: true },
    // drillDownConfig = { model: 'hr.employee', filterField: 'department_id.name' }
};
```

---

## Open Questions

> [!IMPORTANT]
> 1. **Timesheets dependency**: `hr_timesheet` requires `project` module. This is already installed — confirmed. Proceed?
> 2. **Chart drill-down scope**: Should clicking a chart element open the view in a **new tab**, or navigate in the **same window**? (Same window means user leaves the dashboard.)

## Verification Plan

### Automated Tests
1. Deploy module and restart server
2. Clear asset cache — `DELETE FROM ir_attachment WHERE url LIKE '%/web/assets/%'`
3. Test each new query via chat:
   - "Show attendance summary"
   - "Leave breakdown by type"
   - "Recruitment pipeline status"
   - "Timesheet hours by project"
4. Verify chart type switcher on dashboard widgets
5. Verify drill-down opens correct filtered view

### Manual Verification
- Hard-refresh browser to load new CSS
- Verify centered modal animation matches health_development_ai style
- Upload custom AI icon and verify it appears in chat pill/header/avatars
- Test on mobile viewport
