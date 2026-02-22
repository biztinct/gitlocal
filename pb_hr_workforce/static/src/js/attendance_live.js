/** @odoo-module **/
/**
 * Deputy-style Live Attendance Feed — Odoo 19 OWL Client Action
 * Real-time Kanban with status columns: On Shift | Checked Out | Not Started | On Leave
 */

import { Component, useState, onMounted, onWillStart, onWillUnmount, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

class AttendanceLive extends Component {
    static template = xml`
    <div class="atl-container">
        <!-- Toolbar -->
        <div class="atl-toolbar">
            <div class="atl-toolbar-left">
                <div class="atl-title">
                    <i class="fa fa-dot-circle-o atl-pulse"/> Live Attendance
                </div>
                <select class="atl-select" t-on-change="onDepartmentChange">
                    <option value="">All Departments</option>
                    <t t-foreach="state.departments" t-as="dept" t-key="dept.id">
                        <option t-att-value="dept.id"><t t-esc="dept.name"/></option>
                    </t>
                </select>
                <div class="atl-search">
                    <i class="fa fa-search"/>
                    <input type="text" placeholder="Search employee..."
                           t-model="state.searchQuery"/>
                </div>
            </div>
            <div class="atl-toolbar-right">
                <div class="atl-timestamp">
                    <i class="fa fa-refresh atl-spin" t-if="state.loading"/>
                    Updated <t t-esc="state.timestamp"/>
                </div>
                <button class="atl-refresh-btn" t-on-click="refresh">
                    <i class="fa fa-refresh"/> Refresh
                </button>
            </div>
        </div>

        <!-- Summary -->
        <div class="atl-summary">
            <div class="atl-sum-card atl-sum-total">
                <div class="atl-sum-num" t-esc="state.summary.total"/>
                <div class="atl-sum-label">Total</div>
            </div>
            <div class="atl-sum-card atl-sum-active">
                <div class="atl-sum-num" t-esc="state.summary.on_shift"/>
                <div class="atl-sum-label">On Shift</div>
            </div>
            <div class="atl-sum-card atl-sum-done">
                <div class="atl-sum-num" t-esc="state.summary.checked_out"/>
                <div class="atl-sum-label">Checked Out</div>
            </div>
            <div class="atl-sum-card atl-sum-pending">
                <div class="atl-sum-num" t-esc="state.summary.not_started"/>
                <div class="atl-sum-label">Not Started</div>
            </div>
            <div class="atl-sum-card atl-sum-leave">
                <div class="atl-sum-num" t-esc="state.summary.on_leave"/>
                <div class="atl-sum-label">On Leave</div>
            </div>
            <div class="atl-sum-card atl-sum-late" t-if="state.summary.late > 0">
                <div class="atl-sum-num" t-esc="state.summary.late"/>
                <div class="atl-sum-label">Late</div>
            </div>
        </div>

        <!-- Columns -->
        <div class="atl-columns">
            <!-- On Shift -->
            <div class="atl-column atl-col-active">
                <div class="atl-col-header atl-header-active">
                    <i class="fa fa-check-circle"/>
                    On Shift
                    <span class="atl-col-count" t-esc="filteredOnShift.length"/>
                </div>
                <div class="atl-col-body">
                    <t t-foreach="filteredOnShift" t-as="card" t-key="card.id">
                        <div class="atl-card atl-card-active" t-on-click="() => this.openEmployee(card.id)">
                            <div class="atl-card-top">
                                <img class="atl-avatar" t-att-src="card.avatar_url" t-att-alt="card.name" loading="lazy"/>
                                <div class="atl-card-info">
                                    <div class="atl-card-name" t-esc="card.name"/>
                                    <div class="atl-card-meta" t-esc="card.job_title"/>
                                </div>
                                <span class="atl-late-badge" t-if="card.is_late">LATE</span>
                            </div>
                            <div class="atl-card-details">
                                <div class="atl-detail">
                                    <i class="fa fa-sign-in"/> <t t-esc="card.check_in"/>
                                </div>
                                <div class="atl-detail atl-duration">
                                    <i class="fa fa-clock-o"/> <t t-esc="card.duration"/> hrs
                                </div>
                            </div>
                            <div class="atl-card-shift" t-if="card.shift and card.shift.template">
                                <span class="atl-shift-tag"><t t-esc="card.shift.template"/>
                                    <t t-esc="card.shift.start"/> - <t t-esc="card.shift.end"/></span>
                            </div>
                        </div>
                    </t>
                    <div class="atl-empty" t-if="filteredOnShift.length === 0">
                        <i class="fa fa-user-times"/> No one on shift
                    </div>
                </div>
            </div>

            <!-- Checked Out -->
            <div class="atl-column atl-col-done">
                <div class="atl-col-header atl-header-done">
                    <i class="fa fa-sign-out"/>
                    Checked Out
                    <span class="atl-col-count" t-esc="filteredCheckedOut.length"/>
                </div>
                <div class="atl-col-body">
                    <t t-foreach="filteredCheckedOut" t-as="card" t-key="card.id">
                        <div class="atl-card atl-card-done" t-on-click="() => this.openEmployee(card.id)">
                            <div class="atl-card-top">
                                <img class="atl-avatar" t-att-src="card.avatar_url" t-att-alt="card.name" loading="lazy"/>
                                <div class="atl-card-info">
                                    <div class="atl-card-name" t-esc="card.name"/>
                                    <div class="atl-card-meta" t-esc="card.job_title"/>
                                </div>
                            </div>
                            <div class="atl-card-details">
                                <div class="atl-detail"><i class="fa fa-sign-in"/> <t t-esc="card.check_in"/></div>
                                <div class="atl-detail"><i class="fa fa-sign-out"/> <t t-esc="card.check_out"/></div>
                                <div class="atl-detail atl-duration"><i class="fa fa-clock-o"/> <t t-esc="card.duration"/> hrs</div>
                            </div>
                        </div>
                    </t>
                    <div class="atl-empty" t-if="filteredCheckedOut.length === 0">
                        <i class="fa fa-check"/> No checkouts yet
                    </div>
                </div>
            </div>

            <!-- Not Started -->
            <div class="atl-column atl-col-pending">
                <div class="atl-col-header atl-header-pending">
                    <i class="fa fa-hourglass-start"/>
                    Not Started
                    <span class="atl-col-count" t-esc="filteredNotStarted.length"/>
                </div>
                <div class="atl-col-body">
                    <t t-foreach="filteredNotStarted" t-as="card" t-key="card.id">
                        <div class="atl-card atl-card-pending" t-on-click="() => this.openEmployee(card.id)">
                            <div class="atl-card-top">
                                <img class="atl-avatar" t-att-src="card.avatar_url" t-att-alt="card.name" loading="lazy"/>
                                <div class="atl-card-info">
                                    <div class="atl-card-name" t-esc="card.name"/>
                                    <div class="atl-card-meta" t-esc="card.job_title"/>
                                </div>
                                <span class="atl-late-badge" t-if="card.is_late">LATE</span>
                            </div>
                            <div class="atl-card-shift" t-if="card.shift and card.shift.template">
                                <span class="atl-shift-tag"><t t-esc="card.shift.template"/>
                                    <t t-esc="card.shift.start"/> - <t t-esc="card.shift.end"/></span>
                            </div>
                        </div>
                    </t>
                    <div class="atl-empty" t-if="filteredNotStarted.length === 0">
                        <i class="fa fa-thumbs-up"/> Everyone accounted for
                    </div>
                </div>
            </div>

            <!-- On Leave -->
            <div class="atl-column atl-col-leave">
                <div class="atl-col-header atl-header-leave">
                    <i class="fa fa-plane"/>
                    On Leave
                    <span class="atl-col-count" t-esc="filteredOnLeave.length"/>
                </div>
                <div class="atl-col-body">
                    <t t-foreach="filteredOnLeave" t-as="card" t-key="card.id">
                        <div class="atl-card atl-card-leave" t-on-click="() => this.openEmployee(card.id)">
                            <div class="atl-card-top">
                                <img class="atl-avatar" t-att-src="card.avatar_url" t-att-alt="card.name" loading="lazy"/>
                                <div class="atl-card-info">
                                    <div class="atl-card-name" t-esc="card.name"/>
                                    <div class="atl-card-meta" t-esc="card.job_title"/>
                                </div>
                            </div>
                            <div class="atl-card-details">
                                <span class="atl-leave-type"><i class="fa fa-tag"/> <t t-esc="card.leave_type"/></span>
                            </div>
                        </div>
                    </t>
                    <div class="atl-empty" t-if="filteredOnLeave.length === 0">
                        <i class="fa fa-calendar-check-o"/> No one on leave
                    </div>
                </div>
            </div>
        </div>

        <!-- Loading overlay -->
        <div t-if="state.loading and !state.timestamp" class="atl-loading">
            <i class="fa fa-circle-o-notch fa-spin fa-2x"/>
            <span>Loading attendance…</span>
        </div>
    </div>`;

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this._refreshInterval = null;

        this.state = useState({
            loading: true,
            departments: [],
            departmentId: false,
            searchQuery: '',
            on_shift: [],
            checked_out: [],
            not_started: [],
            on_leave: [],
            summary: { total: 0, on_shift: 0, checked_out: 0, not_started: 0, on_leave: 0, late: 0 },
            timestamp: '',
        });

        onWillStart(async () => {
            await this.loadDepartments();
        });
        onMounted(async () => {
            await this.loadData();
            this._refreshInterval = setInterval(() => this.loadData(), 30000);
        });
        onWillUnmount(() => {
            if (this._refreshInterval) clearInterval(this._refreshInterval);
        });
    }

    _filter(list) {
        const q = (this.state.searchQuery || '').toLowerCase().trim();
        if (!q) return list;
        return list.filter(c =>
            c.name.toLowerCase().includes(q) ||
            (c.job_title || '').toLowerCase().includes(q) ||
            (c.department || '').toLowerCase().includes(q)
        );
    }

    get filteredOnShift() { return this._filter(this.state.on_shift); }
    get filteredCheckedOut() { return this._filter(this.state.checked_out); }
    get filteredNotStarted() { return this._filter(this.state.not_started); }
    get filteredOnLeave() { return this._filter(this.state.on_leave); }

    async _rpc(method, args = []) {
        return rpc('/web/dataset/call_kw/hr.attendance.live/' + method, {
            model: 'hr.attendance.live', method, args, kwargs: {},
        });
    }

    async loadDepartments() {
        try { this.state.departments = await this._rpc('get_departments'); } catch (_) { }
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this._rpc('get_live_data', [this.state.departmentId || false]);
            Object.assign(this.state, {
                on_shift: data.on_shift,
                checked_out: data.checked_out,
                not_started: data.not_started,
                on_leave: data.on_leave,
                summary: data.summary,
                timestamp: data.timestamp,
            });
        } catch (e) {
            console.error('Attendance load failed:', e);
        }
        this.state.loading = false;
    }

    async refresh() {
        await this.loadData();
        this.notification.add('Attendance data refreshed', { type: 'info' });
    }

    onDepartmentChange(ev) {
        this.state.departmentId = ev.target.value ? parseInt(ev.target.value) : false;
        this.loadData();
    }

    openEmployee(empId) {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'hr.employee',
            res_id: empId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
}

registry.category("actions").add("attendance_live", AttendanceLive);
