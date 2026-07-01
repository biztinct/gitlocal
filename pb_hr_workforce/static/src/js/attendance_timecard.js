/** @odoo-module **/
/**
 * Rippling-style Timecard View — Visual Gantt Timeline
 * Differentiates regular hours vs overtime by type (weekday, weekend, holiday, night)
 */

import { Component, useState, onMounted, onWillStart, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

class AttendanceTimecard extends Component {
    static props = { action: { type: Object, optional: true }, "*": true };
    static template = xml`
    <div class="tc-container">
        <div class="wf-breadcrumb">
            <span class="wf-bc-home" t-on-click="goHome"><i class="fa fa-home"/></span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-link" t-on-click="goFlowDashboard">Dashboard</span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-current">Timecards</span>
        </div>
        <!-- Toolbar -->
        <div class="tc-toolbar">
            <div class="tc-toolbar-left">
                <div class="tc-title"><i class="fa fa-clock-o"/> Timecards</div>
                <select class="tc-select" t-on-change="onDepartmentChange">
                    <option value="">All Departments</option>
                    <t t-foreach="state.departments" t-as="dept" t-key="dept.id">
                        <option t-att-value="dept.id"><t t-esc="dept.name"/></option>
                    </t>
                </select>
                <div class="tc-search">
                    <i class="fa fa-search"/>
                    <input type="text" placeholder="Search employee..." t-model="state.searchQuery"/>
                </div>
            </div>
            <div class="tc-toolbar-center">
                <button class="tc-nav-btn" t-on-click="prevWeek"><i class="fa fa-chevron-left"/></button>
                <button class="tc-today-btn" t-on-click="goToday">Today</button>
                <span class="tc-week-label" t-esc="weekLabel"/>
                <button class="tc-nav-btn" t-on-click="nextWeek"><i class="fa fa-chevron-right"/></button>
            </div>
            <div class="tc-toolbar-right">
                <label class="tc-toggle">
                    <input type="checkbox" t-att-checked="state.showOnlyWithHours"
                           t-on-change="toggleShowOnly"/>
                    <span>With hours only</span>
                </label>
                <button class="tc-refresh-btn" t-on-click="refresh"><i class="fa fa-refresh"/></button>
            </div>
        </div>

        <!-- OT Legend Bar -->
        <div class="tc-legend-bar" t-if="state.otLegend.length > 0">
            <div class="tc-legend-title">Hours Legend:</div>
            <div class="tc-legend-item">
                <span class="tc-legend-swatch tc-swatch-regular"/>
                <span>Regular</span>
            </div>
            <t t-foreach="state.otLegend" t-as="rule" t-key="rule_index">
                <div class="tc-legend-item">
                    <span t-attf-class="tc-legend-swatch tc-swatch-{{ rule.type }}"/>
                    <span><t t-esc="rule.name"/> (<t t-esc="rule.rate"/>)</span>
                </div>
            </t>
        </div>

        <!-- Scrollable body -->
        <div class="tc-body" t-if="!state.loading">
            <t t-foreach="filteredEmployees" t-as="emp" t-key="emp.id">
                <div class="tc-employee-card">
                    <!-- Employee Header -->
                    <div class="tc-emp-header" t-on-click="() => this.openEmployee(emp.id)">
                        <img class="tc-avatar" t-att-src="emp.avatar_url" t-att-alt="emp.name" loading="lazy"/>
                        <div class="tc-emp-info">
                            <div class="tc-emp-name" t-esc="emp.name"/>
                            <div class="tc-emp-meta" t-esc="emp.job_title"/>
                        </div>
                        <!-- OT breakdown chips -->
                        <div class="tc-emp-ot-chips" t-if="emp.ot_breakdown and emp.ot_breakdown.length > 0">
                            <t t-foreach="emp.ot_breakdown" t-as="ot" t-key="ot_index">
                                <span t-attf-class="tc-ot-chip tc-ot-{{ ot.type }}">
                                    <t t-esc="ot.label"/>: <t t-esc="ot.hours"/>h
                                </span>
                            </t>
                        </div>
                        <div class="tc-emp-total-group">
                            <div class="tc-emp-total">
                                <span class="tc-total-hrs" t-esc="emp.total_regular"/>
                                <span class="tc-total-label">reg</span>
                            </div>
                            <div class="tc-emp-total tc-ot-total" t-if="emp.total_ot > 0">
                                <span class="tc-total-hrs tc-ot-hrs" t-esc="emp.total_ot"/>
                                <span class="tc-total-label">OT</span>
                            </div>
                            <div class="tc-emp-total-all">
                                <span class="tc-total-hrs-all" t-esc="emp.total_hours"/>
                                <span class="tc-total-label">hrs</span>
                            </div>
                        </div>
                    </div>

                    <!-- Hour axis header -->
                    <div class="tc-hour-row">
                        <div class="tc-day-label-col"/>
                        <div class="tc-hour-axis">
                            <t t-foreach="state.hourLabels" t-as="hr" t-key="hr_index">
                                <div class="tc-hour-mark"><t t-esc="hr"/></div>
                            </t>
                        </div>
                        <div class="tc-dur-col tc-dur-header">Duration</div>
                    </div>

                    <!-- Day rows -->
                    <t t-foreach="state.days" t-as="day" t-key="day.date">
                        <div t-attf-class="tc-day-row {{ day.is_today ? 'tc-today' : '' }} {{ day.is_weekend ? 'tc-weekend' : '' }}">
                            <div class="tc-day-label-col">
                                <div class="tc-day-name" t-esc="day.label"/>
                                <div class="tc-day-date" t-esc="day.full_label"/>
                            </div>
                            <div class="tc-hour-axis tc-bar-area">
                                <!-- Hour gridlines -->
                                <t t-foreach="state.hourLabels" t-as="ghr" t-key="ghr_index">
                                    <div class="tc-gridline"/>
                                </t>
                                <!-- Attendance bars -->
                                <t t-set="dayData" t-value="this.getDayData(emp, day.date)"/>
                                <t t-foreach="dayData.entries" t-as="entry" t-key="entry.id">
                                    <div t-attf-class="tc-bar tc-bar-{{ entry.bar_type }} {{ entry.is_active ? 'tc-bar-active' : '' }}"
                                         t-attf-style="left: {{ entry.bar_left }}%; width: {{ entry.bar_width }}%"
                                         t-att-title="entry.label">
                                        <img class="tc-bar-avatar" t-att-src="emp.avatar_url" t-if="entry.check_in" loading="lazy"/>
                                        <span class="tc-bar-text" t-if="entry.check_in">
                                            <t t-esc="entry.check_in"/> - <t t-esc="entry.check_out"/>
                                        </span>
                                        <span class="tc-bar-text" t-if="!entry.check_in">
                                            OT <t t-esc="entry.worked"/>h
                                        </span>
                                    </div>
                                </t>
                            </div>
                            <div class="tc-dur-col">
                                <t t-if="dayData.total > 0">
                                    <span class="tc-dur-regular"><t t-esc="dayData.total"/>h</span>
                                    <span class="tc-dur-ot" t-if="dayData.overtime > 0">
                                        (<t t-esc="dayData.overtime"/>h OT)
                                    </span>
                                </t>
                            </div>
                        </div>
                    </t>
                </div>
            </t>

            <div class="tc-empty" t-if="filteredEmployees.length === 0">
                <i class="fa fa-clock-o fa-3x"/>
                <h3>No timecard data</h3>
                <p t-if="state.showOnlyWithHours">No employees with attendance hours this week. Uncheck _t("With hours only") to see all.</p>
                <p t-if="!state.showOnlyWithHours">No employees found.</p>
            </div>
        </div>

        <div t-if="state.loading" class="tc-loading">
            <i class="fa fa-circle-o-notch fa-spin fa-2x"/>
            <span>Loading timecards…</span>
        </div>
    </div>`;

    setup() {
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            departments: [],
            departmentId: false,
            searchQuery: '',
            showOnlyWithHours: true,
            weekStart: this._getMonday(new Date()).toISOString().slice(0, 10),
            days: [],
            employees: [],
            hourLabels: [],
            otLegend: [],
        });

        onWillStart(async () => {
            await this.loadDepartments();
        });
        onMounted(async () => {
            await this.loadData();
        });
    }

    /** Helper to safely get day data for an employee */
    getDayData(emp, dateStr) {
        if (emp.days && emp.days[dateStr]) {
            return emp.days[dateStr];
        }
        return { entries: [], regular: 0, overtime: 0, total: 0 };
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

    get filteredEmployees() {
        const q = (this.state.searchQuery || '').toLowerCase().trim();
        if (!q) return this.state.employees;
        return this.state.employees.filter(e =>
            e.name.toLowerCase().includes(q) ||
            (e.job_title || '').toLowerCase().includes(q) ||
            (e.department || '').toLowerCase().includes(q)
        );
    }

    async _rpc(method, args = []) {
        return rpc('/web/dataset/call_kw/hr.attendance.timecard/' + method, {
            model: 'hr.attendance.timecard', method, args, kwargs: {},
        });
    }

    async loadDepartments() {
        try { this.state.departments = await this._rpc('get_departments'); } catch (_) { }
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this._rpc('get_timecard_data', [
                false, this.state.weekStart,
                this.state.departmentId || false,
                this.state.showOnlyWithHours,
            ]);
            Object.assign(this.state, {
                days: data.days,
                employees: data.employees,
                hourLabels: data.hour_labels,
                otLegend: data.ot_legend || [],
            });
        } catch (e) {
            console.error('Timecard load failed:', e);
        }
        this.state.loading = false;
    }

    prevWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() - 7);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.loadData();
    }
    nextWeek() {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() + 7);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.loadData();
    }
    goToday() {
        this.state.weekStart = this._getMonday(new Date()).toISOString().slice(0, 10);
        this.loadData();
    }
    onDepartmentChange(ev) {
        this.state.departmentId = ev.target.value ? parseInt(ev.target.value) : false;
        this.loadData();
    }
    toggleShowOnly() {
        this.state.showOnlyWithHours = !this.state.showOnlyWithHours;
        this.loadData();
    }
    refresh() { this.loadData(); }
    openEmployee(empId) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            res_id: empId,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    goHome() { this.actionService.doAction('pb_dashboard.action_pb_dashboard'); }
    goFlowDashboard() {
        this.actionService.doAction('pb_dashboard.action_pb_dashboard');
    }
}

registry.category("actions").add("attendance_timecard", AttendanceTimecard);
