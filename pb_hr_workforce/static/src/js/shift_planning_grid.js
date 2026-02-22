/** @odoo-module **/
/**
 * Deputy-style Shift Planning Grid — Odoo 19 OWL Client Action
 *
 * A visual weekly grid with:
 * - Sticky left sidebar: employee avatars, names, total hours
 * - Day columns: Mon–Sun
 * - Shift cards: color-coded by template, showing time range
 * - Toolbar: week navigation, department filter, publish button
 * - Summary footer: shift counts by status
 */

import { Component, useState, onMounted, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const SHIFT_COLORS = [
    '#95a5a6', '#e74c3c', '#2ecc71', '#3498db', '#9b59b6',
    '#f39c12', '#1abc9c', '#e67e22', '#e91e63', '#00bcd4',
    '#8bc34a',
];

function formatHour(h) {
    const hr = Math.floor(h);
    const mn = Math.round((h % 1) * 60);
    const ampm = hr >= 12 ? 'pm' : 'am';
    const h12 = hr > 12 ? hr - 12 : (hr === 0 ? 12 : hr);
    return mn ? `${h12}:${String(mn).padStart(2, '0')}${ampm}` : `${h12}${ampm}`;
}

class ShiftPlanningGrid extends Component {
    static template = xml`
    <div class="spg-container">
        <!-- TOOLBAR -->
        <div class="spg-toolbar">
            <div class="spg-toolbar-left">
                <select class="spg-dept-select" t-on-change="onDepartmentChange">
                    <option value="">All Departments</option>
                    <t t-foreach="state.departments" t-as="dept" t-key="dept.id">
                        <option t-att-value="dept.id"
                                t-att-selected="state.departmentId === dept.id">
                            <t t-esc="dept.name"/>
                        </option>
                    </t>
                </select>
            </div>
            <div class="spg-toolbar-center">
                <button class="spg-nav-btn" t-on-click="prevWeek">
                    <i class="fa fa-chevron-left"/>
                </button>
                <button class="spg-today-btn" t-on-click="goToday">Today</button>
                <span class="spg-week-label" t-esc="weekLabel"/>
                <button class="spg-nav-btn" t-on-click="nextWeek">
                    <i class="fa fa-chevron-right"/>
                </button>
            </div>
            <div class="spg-toolbar-right">
                <button class="spg-publish-btn" t-on-click="publishAll"
                        t-att-disabled="state.summary.draft === 0">
                    <i class="fa fa-send"/> Publish All
                    <span class="spg-badge" t-if="state.summary.draft > 0"
                          t-esc="state.summary.draft"/>
                </button>
            </div>
        </div>

        <!-- SUMMARY BAR -->
        <div class="spg-summary-bar">
            <div class="spg-stat">
                <span class="spg-stat-dot spg-dot-total"/>
                <span t-esc="state.summary.total_shifts"/> Shifts
            </div>
            <div class="spg-stat">
                <span class="spg-stat-dot spg-dot-hours"/>
                <span t-esc="state.summary.total_hours"/> Hours
            </div>
            <div class="spg-stat">
                <span class="spg-stat-dot spg-dot-published"/>
                <span t-esc="state.summary.published"/> Published
            </div>
            <div class="spg-stat">
                <span class="spg-stat-dot spg-dot-draft"/>
                <span t-esc="state.summary.draft"/> Unpublished
            </div>
            <div class="spg-stat">
                <span class="spg-stat-dot spg-dot-completed"/>
                <span t-esc="state.summary.completed"/> Completed
            </div>
        </div>

        <!-- GRID -->
        <div class="spg-grid-wrapper">
            <table class="spg-grid">
                <thead>
                    <tr>
                        <th class="spg-emp-header">Employee</th>
                        <t t-foreach="state.days" t-as="day" t-key="day.date">
                            <th t-attf-class="spg-day-header {{ day.is_today ? 'spg-today-col' : '' }} {{ day.is_weekend ? 'spg-weekend-col' : '' }}">
                                <div class="spg-day-name" t-esc="day.label"/>
                                <div class="spg-day-date" t-esc="day.full_label"/>
                            </th>
                        </t>
                    </tr>
                </thead>
                <tbody>
                    <!-- Open/Unassigned row -->
                    <tr class="spg-open-row">
                        <td class="spg-emp-cell spg-open-cell">
                            <div class="spg-emp-info">
                                <div class="spg-emp-avatar spg-open-avatar">
                                    <i class="fa fa-plus-circle"/>
                                </div>
                                <div>
                                    <div class="spg-emp-name">Open Shifts</div>
                                    <div class="spg-emp-meta">Click any cell to add</div>
                                </div>
                            </div>
                        </td>
                        <t t-foreach="state.days" t-as="day" t-key="day.date">
                            <td t-attf-class="spg-cell spg-empty-cell {{ day.is_today ? 'spg-today-col' : '' }} {{ day.is_weekend ? 'spg-weekend-col' : '' }}"
                                t-on-click="() => this.onCellClick(false, day.date)">
                                <div class="spg-cell-add-hint">
                                    <i class="fa fa-plus"/>
                                </div>
                            </td>
                        </t>
                    </tr>
                    <!-- Employee rows -->
                    <t t-foreach="state.employees" t-as="emp" t-key="emp.id">
                        <tr class="spg-emp-row">
                            <td class="spg-emp-cell">
                                <div class="spg-emp-info">
                                    <img class="spg-emp-avatar"
                                         t-att-src="emp.avatar_url"
                                         t-att-alt="emp.name"
                                         loading="lazy"/>
                                    <div>
                                        <div class="spg-emp-name" t-esc="emp.name"/>
                                        <div class="spg-emp-meta">
                                            <span t-esc="emp.job_title"/>
                                        </div>
                                        <div class="spg-emp-hours">
                                            <i class="fa fa-clock-o"/>
                                            <span t-esc="emp.total_hours"/> hrs
                                        </div>
                                    </div>
                                </div>
                            </td>
                            <t t-foreach="state.days" t-as="day" t-key="day.date">
                                <td t-attf-class="spg-cell {{ day.is_today ? 'spg-today-col' : '' }} {{ day.is_weekend ? 'spg-weekend-col' : '' }}"
                                    t-on-click="() => this.onCellClick(emp.id, day.date)">
                                    <t t-if="emp.shifts[day.date]">
                                        <t t-foreach="emp.shifts[day.date]" t-as="shift" t-key="shift.id">
                                            <div t-attf-class="spg-shift-card spg-shift-{{ shift.state }}"
                                                 t-attf-style="border-left-color: {{ this.getShiftColor(shift.color) }}"
                                                 t-on-click.stop="() => this.onShiftClick(shift)">
                                                <div class="spg-shift-time">
                                                    <t t-esc="shift.start"/> - <t t-esc="shift.end"/>
                                                </div>
                                                <div class="spg-shift-label"
                                                     t-attf-style="background: {{ this.getShiftColor(shift.color) }}20; color: {{ this.getShiftColor(shift.color) }}">
                                                    <t t-esc="shift.template_name"/>
                                                </div>
                                                <div class="spg-shift-actions">
                                                    <button class="spg-shift-del"
                                                            t-if="shift.state === 'draft'"
                                                            t-on-click.stop="() => this.deleteShift(shift.id)">
                                                        <i class="fa fa-trash-o"/>
                                                    </button>
                                                </div>
                                            </div>
                                        </t>
                                    </t>
                                    <t t-else="">
                                        <div class="spg-cell-add-hint">
                                            <i class="fa fa-plus"/>
                                        </div>
                                    </t>
                                </td>
                            </t>
                        </tr>
                    </t>
                </tbody>
            </table>
        </div>

        <!-- QUICK CREATE MODAL -->
        <div t-if="state.showCreateModal" class="spg-modal-overlay" t-on-click.stop="closeModal">
            <div class="spg-modal" t-on-click.stop="() => {}">
                <div class="spg-modal-header">
                    <h3>Add Shift</h3>
                    <button class="spg-modal-close" t-on-click="closeModal">
                        <i class="fa fa-times"/>
                    </button>
                </div>
                <div class="spg-modal-body">
                    <div class="spg-modal-info">
                        <div t-if="state.createEmployeeName" class="spg-modal-employee">
                            <i class="fa fa-user"/> <t t-esc="state.createEmployeeName"/>
                        </div>
                        <div class="spg-modal-date">
                            <i class="fa fa-calendar"/> <t t-esc="state.createDate"/>
                        </div>
                    </div>
                    <div class="spg-template-grid">
                        <t t-foreach="state.templates" t-as="tmpl" t-key="tmpl.id">
                            <div class="spg-template-option"
                                 t-attf-style="border-color: {{ this.getShiftColor(tmpl.color) }}"
                                 t-on-click="() => this.createShift(tmpl.id)">
                                <div class="spg-template-name" t-esc="tmpl.name"/>
                                <div class="spg-template-time">
                                    <t t-esc="this.fmtHour(tmpl.start_hour)"/> – <t t-esc="this.fmtHour(tmpl.end_hour)"/>
                                </div>
                                <div class="spg-template-dur">
                                    <t t-esc="tmpl.duration"/> hrs
                                </div>
                            </div>
                        </t>
                    </div>
                </div>
            </div>
        </div>

        <!-- LOADING -->
        <div t-if="state.loading" class="spg-loading">
            <i class="fa fa-spinner fa-spin fa-2x"/>
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
            summary: { total_shifts: 0, published: 0, draft: 0, completed: 0, total_hours: 0 },
            weekStart: this._getMonday(new Date()).toISOString().slice(0, 10),
            departmentId: false,
            showCreateModal: false,
            createEmployeeId: false,
            createEmployeeName: '',
            createDate: '',
        });

        onWillStart(async () => {
            await this.loadDepartments();
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
        end.setDate(end.getDate() + 6);
        const opts = { day: 'numeric', month: 'short' };
        return `${start.toLocaleDateString('en-US', opts)} – ${end.toLocaleDateString('en-US', opts)}, ${end.getFullYear()}`;
    }

    getShiftColor(idx) {
        return SHIFT_COLORS[idx % SHIFT_COLORS.length];
    }

    fmtHour(h) {
        return formatHour(h);
    }

    async loadDepartments() {
        try {
            this.state.departments = await rpc(
                '/web/dataset/call_kw/hr.shift.planning.grid/get_departments',
                { model: 'hr.shift.planning.grid', method: 'get_departments', args: [], kwargs: {} }
            );
        } catch (e) {
            console.error('Grid: failed to load departments', e);
        }
    }

    async loadGrid() {
        this.state.loading = true;
        try {
            const data = await rpc(
                '/web/dataset/call_kw/hr.shift.planning.grid/get_grid_data',
                {
                    model: 'hr.shift.planning.grid',
                    method: 'get_grid_data',
                    args: [this.state.weekStart, this.state.departmentId || false],
                    kwargs: {},
                }
            );
            this.state.days = data.days;
            this.state.employees = data.employees;
            this.state.templates = data.templates;
            this.state.summary = data.summary;
        } catch (e) {
            console.error('Grid: failed to load', e);
            this.notification.add('Failed to load shift grid', { type: 'danger' });
        }
        this.state.loading = false;
    }

    prevWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() - 7);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.loadGrid();
    }

    nextWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() + 7);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.loadGrid();
    }

    goToday() {
        this.state.weekStart = this._getMonday(new Date()).toISOString().slice(0, 10);
        this.loadGrid();
    }

    onDepartmentChange(ev) {
        const val = ev.target.value;
        this.state.departmentId = val ? parseInt(val) : false;
        this.loadGrid();
    }

    onCellClick(employeeId, dateStr) {
        if (!employeeId) {
            // Open shifts row — ignore for now (no unassigned shifts)
            return;
        }
        const emp = this.state.employees.find(e => e.id === employeeId);
        this.state.createEmployeeId = employeeId;
        this.state.createEmployeeName = emp ? emp.name : '';
        this.state.createDate = dateStr;
        this.state.showCreateModal = true;
    }

    closeModal() {
        this.state.showCreateModal = false;
    }

    async createShift(templateId) {
        try {
            await rpc(
                '/web/dataset/call_kw/hr.shift.planning.grid/quick_create_shift',
                {
                    model: 'hr.shift.planning.grid',
                    method: 'quick_create_shift',
                    args: [this.state.createEmployeeId, this.state.createDate, templateId],
                    kwargs: {},
                }
            );
            this.state.showCreateModal = false;
            this.notification.add('Shift created', { type: 'success' });
            await this.loadGrid();
        } catch (e) {
            console.error('Grid: create failed', e);
            this.notification.add('Failed to create shift', { type: 'danger' });
        }
    }

    async deleteShift(shiftId) {
        try {
            await rpc(
                '/web/dataset/call_kw/hr.shift.planning.grid/delete_shift',
                {
                    model: 'hr.shift.planning.grid',
                    method: 'delete_shift',
                    args: [shiftId],
                    kwargs: {},
                }
            );
            this.notification.add('Shift deleted', { type: 'info' });
            await this.loadGrid();
        } catch (e) {
            this.notification.add('Cannot delete this shift', { type: 'warning' });
        }
    }

    async publishAll() {
        try {
            const count = await rpc(
                '/web/dataset/call_kw/hr.shift.planning.grid/publish_shifts',
                {
                    model: 'hr.shift.planning.grid',
                    method: 'publish_shifts',
                    args: [this.state.weekStart, this.state.departmentId || false],
                    kwargs: {},
                }
            );
            this.notification.add(`${count} shifts published`, { type: 'success' });
            await this.loadGrid();
        } catch (e) {
            this.notification.add('Publish failed', { type: 'danger' });
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
}

registry.category("actions").add("shift_planning_grid", ShiftPlanningGrid);
