/** @odoo-module **/
/**
 * Deputy-style Shift Planning Grid — Enhanced
 * Features: search, filters, leave overlay, conflict warnings, copy week,
 * view toggle, open shifts, visual polish
 */

import { Component, useState, onMounted, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const SHIFT_COLORS = [
    '#95a5a6', '#e74c3c', '#2ecc71', '#3498db', '#9b59b6',
    '#f39c12', '#1abc9c', '#e67e22', '#e91e63', '#00bcd4', '#8bc34a',
];

function fmtH(h) {
    const hr = Math.floor(h);
    const mn = Math.round((h % 1) * 60);
    const ampm = hr >= 12 ? 'pm' : 'am';
    const h12 = hr > 12 ? hr - 12 : (hr === 0 ? 12 : hr);
    return mn ? `${h12}:${String(mn).padStart(2, '0')}${ampm}` : `${h12}${ampm}`;
}

class ShiftPlanningGrid extends Component {
    static template = xml`
    <div class="spg-container">
        <div class="wf-breadcrumb">
            <span class="wf-bc-home" t-on-click="goHome"><i class="fa fa-home"/></span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-link" t-on-click="goFlowDashboard">Flow Dashboard</span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-current">Shift Roster</span>
        </div>
        <!-- TOOLBAR ROW 1 -->
        <div class="spg-toolbar">
            <div class="spg-toolbar-left">
                <select class="spg-select" t-on-change="onDepartmentChange">
                    <option value="">All Departments</option>
                    <t t-foreach="state.departments" t-as="dept" t-key="dept.id">
                        <option t-att-value="dept.id" t-att-selected="state.departmentId === dept.id">
                            <t t-esc="dept.name"/>
                        </option>
                    </t>
                </select>
                <select class="spg-select" t-on-change="onJobChange">
                    <option value="">All Positions</option>
                    <t t-foreach="state.jobs" t-as="job" t-key="job.id">
                        <option t-att-value="job.id" t-att-selected="state.jobId === job.id">
                            <t t-esc="job.name"/>
                        </option>
                    </t>
                </select>
                <div class="spg-search-box">
                    <i class="fa fa-search"/>
                    <input type="text" placeholder="Search employee..."
                           t-model="state.searchQuery" t-on-input="onSearch"/>
                </div>
            </div>
            <div class="spg-toolbar-center">
                <button class="spg-nav-btn" t-on-click="prevWeek"><i class="fa fa-chevron-left"/></button>
                <button class="spg-today-btn" t-on-click="goToday">Today</button>
                <span class="spg-week-label" t-esc="weekLabel"/>
                <button class="spg-nav-btn" t-on-click="nextWeek"><i class="fa fa-chevron-right"/></button>
            </div>
            <div class="spg-toolbar-right">
                <div class="spg-view-toggle">
                    <button t-attf-class="spg-toggle-btn {{ state.numDays === 7 ? 'active' : '' }}"
                            t-on-click="() => this.setView(7)">Week</button>
                    <button t-attf-class="spg-toggle-btn {{ state.numDays === 14 ? 'active' : '' }}"
                            t-on-click="() => this.setView(14)">Fortnight</button>
                </div>
                <button class="spg-copy-btn" t-on-click="copyWeek" title="Copy shifts to next week">
                    <i class="fa fa-copy"/> Copy Week
                </button>
                <button class="spg-publish-btn" t-on-click="publishAll"
                        t-att-disabled="state.summary.draft === 0">
                    <i class="fa fa-send"/> Publish All
                    <span class="spg-badge" t-if="state.summary.draft > 0" t-esc="state.summary.draft"/>
                </button>
            </div>
        </div>

        <!-- SUMMARY BAR -->
        <div class="spg-summary-bar">
            <div class="spg-stat"><span class="spg-stat-dot spg-dot-total"/>
                <b t-esc="state.summary.total_shifts"/> Shifts</div>
            <div class="spg-stat"><span class="spg-stat-dot spg-dot-hours"/>
                <b t-esc="state.summary.total_hours"/> Hours</div>
            <div class="spg-stat"><span class="spg-stat-dot spg-dot-published"/>
                <t t-esc="state.summary.published"/> Published</div>
            <div class="spg-stat"><span class="spg-stat-dot spg-dot-draft"/>
                <t t-esc="state.summary.draft"/> Unpublished</div>
            <div class="spg-stat"><span class="spg-stat-dot spg-dot-completed"/>
                <t t-esc="state.summary.completed"/> Completed</div>
            <div class="spg-stat" t-if="state.summary.open_shifts > 0">
                <span class="spg-stat-dot spg-dot-open"/>
                <t t-esc="state.summary.open_shifts"/> Open</div>
            <div class="spg-stat" t-if="state.summary.warnings > 0">
                <span class="spg-stat-dot spg-dot-warn"/>
                <b t-esc="state.summary.warnings"/> Warnings</div>
            <div class="spg-stat" t-if="state.summary.leave_approved > 0">
                <span class="spg-stat-dot spg-dot-leave"/>
                <t t-esc="state.summary.leave_approved"/> On Leave</div>
            <div class="spg-stat" t-if="state.summary.leave_pending > 0">
                <span class="spg-stat-dot spg-dot-leave-pending"/>
                <t t-esc="state.summary.leave_pending"/> Leave Pending</div>
        </div>

        <!-- GRID -->
        <div class="spg-grid-wrapper">
            <table class="spg-grid">
                <thead>
                    <tr>
                        <th class="spg-emp-header">
                            <span>EMPLOYEE</span>
                            <span class="spg-emp-count" t-esc="filteredEmployees.length + ' people'"/>
                        </th>
                        <t t-foreach="state.days" t-as="day" t-key="day.date">
                            <th t-attf-class="spg-day-header {{ day.is_today ? 'spg-today-col' : '' }} {{ day.is_weekend ? 'spg-weekend-col' : '' }}">
                                <div class="spg-day-name" t-esc="day.label"/>
                                <div class="spg-day-date" t-esc="day.full_label"/>
                            </th>
                        </t>
                    </tr>
                </thead>
                <tbody>
                    <!-- Open Shifts Row -->
                    <tr class="spg-open-row">
                        <td class="spg-emp-cell spg-open-cell">
                            <div class="spg-emp-info">
                                <div class="spg-open-avatar"><i class="fa fa-users"/></div>
                                <div>
                                    <div class="spg-emp-name">Open Shifts</div>
                                    <div class="spg-emp-meta">Unassigned</div>
                                </div>
                            </div>
                        </td>
                        <t t-foreach="state.days" t-as="day" t-key="day.date">
                            <td t-attf-class="spg-cell spg-open-day {{ day.is_today ? 'spg-today-col' : '' }}"
                                t-on-click="() => this.onCellClick(false, day.date)">
                                <t t-if="state.open_shifts[day.date]">
                                    <t t-foreach="state.open_shifts[day.date]" t-as="os" t-key="os.id">
                                        <div class="spg-shift-card spg-shift-open"
                                             t-attf-style="border-left-color: {{ this.getColor(os.color) }}">
                                            <div class="spg-shift-time"><t t-esc="os.start"/> - <t t-esc="os.end"/></div>
                                            <div class="spg-shift-label"
                                                 t-attf-style="background: {{ this.getColor(os.color) }}20; color: {{ this.getColor(os.color) }}">
                                                <t t-esc="os.template_name"/>
                                            </div>
                                        </div>
                                    </t>
                                </t>
                                <div class="spg-cell-add"><i class="fa fa-plus"/></div>
                            </td>
                        </t>
                    </tr>
                    <!-- Employee Rows -->
                    <t t-foreach="filteredEmployees" t-as="emp" t-key="emp.id">
                        <tr class="spg-emp-row" t-att-data-empid="emp.id">
                            <td class="spg-emp-cell">
                                <div class="spg-emp-info">
                                    <img class="spg-emp-avatar" t-att-src="emp.avatar_url"
                                         t-att-alt="emp.name" loading="lazy"/>
                                    <div class="spg-emp-detail">
                                        <div class="spg-emp-name" t-esc="emp.name"/>
                                        <div class="spg-emp-meta" t-esc="emp.job_title"/>
                                        <div class="spg-emp-hours-bar">
                                            <div class="spg-hours-fill"
                                                 t-attf-style="width: {{ Math.min(100, (emp.total_hours / emp.contracted_hours) * 100) }}%"/>
                                        </div>
                                        <div class="spg-emp-hours-text">
                                            <i class="fa fa-clock-o"/>
                                            <t t-esc="emp.total_hours"/>/<t t-esc="emp.contracted_hours"/> hrs
                                        </div>
                                    </div>
                                </div>
                            </td>
                            <t t-foreach="state.days" t-as="day" t-key="day.date">
                                <td t-attf-class="spg-cell {{ day.is_today ? 'spg-today-col' : '' }} {{ day.is_weekend ? 'spg-weekend-col' : '' }} {{ emp.leaves[day.date] ? (emp.leaves[day.date].is_approved ? 'spg-leave-cell' : 'spg-leave-pending-cell') : '' }}"
                                    t-on-click="() => this.onCellClick(emp.id, day.date)">
                                    <!-- Leave indicator -->
                                    <t t-if="emp.leaves[day.date]">
                                        <div t-attf-class="spg-leave-badge {{ emp.leaves[day.date].is_approved ? 'spg-leave-approved' : 'spg-leave-pending' }}">
                                            <i t-att-class="emp.leaves[day.date].is_approved ? 'fa fa-umbrella-beach' : 'fa fa-hourglass-half'"/>
                                            <span t-esc="emp.leaves[day.date].type"/>
                                        </div>
                                    </t>
                                    <!-- Shifts -->
                                    <t t-if="emp.shifts[day.date]">
                                        <t t-foreach="emp.shifts[day.date]" t-as="shift" t-key="shift.id">
                                            <div t-attf-class="spg-shift-card spg-shift-{{ shift.state }} {{ this.hasConflict(emp.id, shift.id) ? 'spg-shift-conflict' : '' }}"
                                                 t-attf-style="border-left-color: {{ this.getColor(shift.color) }}"
                                                 t-on-click.stop="() => this.onShiftClick(shift)">
                                                <div class="spg-shift-time">
                                                    <t t-esc="shift.start"/> - <t t-esc="shift.end"/>
                                                </div>
                                                <div class="spg-shift-label"
                                                     t-attf-style="background: {{ this.getColor(shift.color) }}20; color: {{ this.getColor(shift.color) }}">
                                                    <t t-esc="shift.template_name"/>
                                                </div>
                                                <span class="spg-conflict-icon" t-if="this.hasConflict(emp.id, shift.id)"
                                                      title="Shift conflict detected">⚠️</span>
                                                <div class="spg-shift-actions">
                                                    <button class="spg-shift-del" t-if="shift.state === 'draft'"
                                                            t-on-click.stop="() => this.deleteShift(shift.id)"
                                                            title="Delete"><i class="fa fa-trash-o"/></button>
                                                </div>
                                            </div>
                                        </t>
                                    </t>
                                    <!-- Add hint (only if no leave) -->
                                    <div class="spg-cell-add" t-if="!emp.leaves[day.date]">
                                        <i class="fa fa-plus"/>
                                    </div>
                                </td>
                            </t>
                        </tr>
                    </t>
                    <!-- Empty state -->
                    <t t-if="filteredEmployees.length === 0">
                        <tr>
                            <td t-att-colspan="state.days.length + 1" class="spg-empty-state">
                                <div class="spg-empty-inner">
                                    <i class="fa fa-calendar-o fa-3x"/>
                                    <h3>No employees found</h3>
                                    <p>Try changing your filters or department selection.</p>
                                </div>
                            </td>
                        </tr>
                    </t>
                </tbody>
            </table>
        </div>

        <!-- QUICK CREATE MODAL -->
        <div t-if="state.showCreateModal" class="spg-modal-overlay" t-on-click.stop="closeModal">
            <div class="spg-modal" t-on-click.stop="() => {}">
                <div class="spg-modal-header">
                    <h3><i class="fa fa-plus-circle"/> Add Shift</h3>
                    <button class="spg-modal-close" t-on-click="closeModal"><i class="fa fa-times"/></button>
                </div>
                <div class="spg-modal-body">
                    <div class="spg-modal-info">
                        <div class="spg-modal-detail" t-if="state.createEmployeeName">
                            <i class="fa fa-user"/> <t t-esc="state.createEmployeeName"/>
                        </div>
                        <div class="spg-modal-detail" t-else="">
                            <i class="fa fa-users"/> Open Shift
                        </div>
                        <div class="spg-modal-detail">
                            <i class="fa fa-calendar"/> <t t-esc="state.createDateLabel"/>
                        </div>
                    </div>
                    <div class="spg-template-grid">
                        <t t-foreach="state.templates" t-as="tmpl" t-key="tmpl.id">
                            <div class="spg-template-option"
                                 t-attf-style="border-color: {{ this.getColor(tmpl.color) }}"
                                 t-on-click="() => this.createShift(tmpl.id)">
                                <div class="spg-template-color"
                                     t-attf-style="background: {{ this.getColor(tmpl.color) }}"/>
                                <div class="spg-template-name" t-esc="tmpl.name"/>
                                <div class="spg-template-time">
                                    <t t-esc="this.fmtHour(tmpl.start_hour)"/> – <t t-esc="this.fmtHour(tmpl.end_hour)"/>
                                </div>
                                <div class="spg-template-dur"><t t-esc="tmpl.duration"/> hrs</div>
                            </div>
                        </t>
                    </div>
                </div>
            </div>
        </div>

        <!-- COPY WEEK MODAL -->
        <div t-if="state.showCopyModal" class="spg-modal-overlay" t-on-click.stop="closeCopyModal">
            <div class="spg-modal spg-modal-sm" t-on-click.stop="() => {}">
                <div class="spg-modal-header">
                    <h3><i class="fa fa-copy"/> Copy Week</h3>
                    <button class="spg-modal-close" t-on-click="closeCopyModal"><i class="fa fa-times"/></button>
                </div>
                <div class="spg-modal-body">
                    <p class="spg-copy-desc">Copy all shifts from the current week to:</p>
                    <div class="spg-copy-target">
                        <b t-esc="nextWeekLabel"/>
                    </div>
                    <div class="spg-copy-actions">
                        <button class="spg-copy-confirm" t-on-click="doCopyWeek">
                            <i class="fa fa-check"/> Copy Shifts
                        </button>
                        <button class="spg-copy-cancel" t-on-click="closeCopyModal">Cancel</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- LOADING -->
        <div t-if="state.loading" class="spg-loading">
            <div class="spg-spinner"><i class="fa fa-circle-o-notch fa-spin fa-2x"/></div>
            <span>Loading shifts…</span>
        </div>
    </div>`;

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            days: [],
            employees: [],
            templates: [],
            departments: [],
            jobs: [],
            open_shifts: {},
            warnings: [],
            summary: {},
            weekStart: this._getMonday(new Date()).toISOString().slice(0, 10),
            departmentId: false,
            jobId: false,
            numDays: 7,
            searchQuery: '',
            showCreateModal: false,
            showCopyModal: false,
            createEmployeeId: false,
            createEmployeeName: '',
            createDate: '',
            createDateLabel: '',
        });

        onWillStart(async () => {
            await Promise.all([this.loadDepartments(), this.loadJobs()]);
        });
        onMounted(async () => {
            await this.loadGrid();
        });
    }

    _getMonday(d) {
        const dt = new Date(d);
        const day = dt.getDay();
        const diff = dt.getDate() - day + (day === 0 ? -6 : 1);
        return new Date(dt.setDate(diff));
    }

    get weekLabel() {
        const start = new Date(this.state.weekStart);
        const end = new Date(start);
        end.setDate(end.getDate() + this.state.numDays - 1);
        const opts = { day: 'numeric', month: 'short' };
        return `${start.toLocaleDateString('en-US', opts)} – ${end.toLocaleDateString('en-US', opts)}, ${end.getFullYear()}`;
    }

    get nextWeekLabel() {
        const start = new Date(this.state.weekStart);
        start.setDate(start.getDate() + 7);
        const end = new Date(start);
        end.setDate(end.getDate() + 6);
        const opts = { day: 'numeric', month: 'short' };
        return `${start.toLocaleDateString('en-US', opts)} – ${end.toLocaleDateString('en-US', opts)}, ${end.getFullYear()}`;
    }

    get filteredEmployees() {
        const q = (this.state.searchQuery || '').toLowerCase().trim();
        if (!q) return this.state.employees;
        return this.state.employees.filter(e =>
            e.name.toLowerCase().includes(q) ||
            (e.job_title || '').toLowerCase().includes(q) ||
            (e.department || '').toLowerCase().includes(q)
        );
    }

    getColor(idx) { return SHIFT_COLORS[idx % SHIFT_COLORS.length]; }
    fmtHour(h) { return fmtH(h); }

    hasConflict(empId, shiftId) {
        return this.state.warnings.some(w =>
            w.employee_id === empId && (w.shift_a_id === shiftId || w.shift_b_id === shiftId)
        );
    }

    // ── Data Loading ──
    async _rpc(method, args = []) {
        return rpc('/web/dataset/call_kw/hr.shift.planning.grid/' + method, {
            model: 'hr.shift.planning.grid', method, args, kwargs: {},
        });
    }

    async loadDepartments() {
        try { this.state.departments = await this._rpc('get_departments'); } catch (_) { }
    }
    async loadJobs() {
        try { this.state.jobs = await this._rpc('get_job_positions'); } catch (_) { }
    }

    async loadGrid() {
        this.state.loading = true;
        try {
            const data = await this._rpc('get_grid_data', [
                this.state.weekStart, this.state.departmentId || false,
                this.state.jobId || false, this.state.numDays,
            ]);
            Object.assign(this.state, {
                days: data.days,
                employees: data.employees,
                templates: data.templates,
                open_shifts: data.open_shifts || {},
                warnings: data.warnings || [],
                summary: data.summary,
            });
        } catch (e) {
            console.error('Grid load failed:', e);
            this.notification.add('Failed to load shift grid', { type: 'danger' });
        }
        this.state.loading = false;
    }

    // ── Navigation ──
    prevWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() - this.state.numDays);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.loadGrid();
    }
    nextWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() + this.state.numDays);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.loadGrid();
    }
    goToday() {
        this.state.weekStart = this._getMonday(new Date()).toISOString().slice(0, 10);
        this.loadGrid();
    }
    setView(days) {
        this.state.numDays = days;
        this.loadGrid();
    }

    // ── Filters ──
    onDepartmentChange(ev) {
        this.state.departmentId = ev.target.value ? parseInt(ev.target.value) : false;
        this.loadGrid();
    }
    onJobChange(ev) {
        this.state.jobId = ev.target.value ? parseInt(ev.target.value) : false;
        this.loadGrid();
    }
    onSearch() { /* client-side filtering via filteredEmployees getter */ }

    // ── Cell / Shift ──
    onCellClick(employeeId, dateStr) {
        const emp = employeeId ? this.state.employees.find(e => e.id === employeeId) : null;
        // Don't allow creating on leave days
        if (emp && emp.leaves[dateStr] && emp.leaves[dateStr].is_approved) {
            this.notification.add('Employee is on leave this day', { type: 'warning' });
            return;
        }
        const d = new Date(dateStr);
        this.state.createEmployeeId = employeeId;
        this.state.createEmployeeName = emp ? emp.name : '';
        this.state.createDate = dateStr;
        this.state.createDateLabel = d.toLocaleDateString('en-US', { weekday: 'long', day: 'numeric', month: 'long' });
        this.state.showCreateModal = true;
    }

    closeModal() { this.state.showCreateModal = false; }

    async createShift(templateId) {
        try {
            await this._rpc('quick_create_shift', [
                this.state.createEmployeeId || false, this.state.createDate, templateId,
            ]);
            this.state.showCreateModal = false;
            this.notification.add('Shift created', { type: 'success' });
            await this.loadGrid();
        } catch (e) {
            this.notification.add('Failed to create shift', { type: 'danger' });
        }
    }

    async deleteShift(shiftId) {
        try {
            await this._rpc('delete_shift', [shiftId]);
            this.notification.add('Shift deleted', { type: 'info' });
            await this.loadGrid();
        } catch (_) {
            this.notification.add('Cannot delete this shift', { type: 'warning' });
        }
    }

    onShiftClick(shift) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.shift.planning',
            res_id: shift.id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    // ── Publish ──
    async publishAll() {
        try {
            const count = await this._rpc('publish_shifts', [
                this.state.weekStart, this.state.departmentId || false, this.state.numDays,
            ]);
            this.notification.add(`${count} shifts published`, { type: 'success' });
            await this.loadGrid();
        } catch (_) {
            this.notification.add('Publish failed', { type: 'danger' });
        }
    }

    // ── Copy Week ──
    copyWeek() { this.state.showCopyModal = true; }
    closeCopyModal() { this.state.showCopyModal = false; }

    async doCopyWeek() {
        const target = new Date(this.state.weekStart);
        target.setDate(target.getDate() + 7);
        try {
            const count = await this._rpc('copy_week', [
                this.state.weekStart, target.toISOString().slice(0, 10),
                this.state.departmentId || false,
            ]);
            this.state.showCopyModal = false;
            this.notification.add(`${count} shifts copied to next week`, { type: 'success' });
        } catch (_) {
            this.notification.add('Copy failed', { type: 'danger' });
        }
    }

    goHome() { this.actionService.doAction('pb_hr_flow.action_hr_flow_wizard'); }
    goFlowDashboard() {
        this.actionService.doAction('pb_hr_flow.action_hr_flow_wizard');
    }
}

registry.category("actions").add("shift_planning_grid", ShiftPlanningGrid);
