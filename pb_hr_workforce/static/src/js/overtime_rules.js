/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
/**
 * Deputy-Style Overtime Rules Dashboard
 * Visual card-based OT rules with inline premium edit/create modal
 */

import { Component, useState, onMounted, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";

const OT_TYPES = [
    { value: 'weekday', label: _t("Weekday"), icon: 'fa-briefcase', color: '#2563eb', desc: _t("Extra hours on regular work days") },
    { value: 'weekend', label: _t("Weekend"), icon: 'fa-calendar-o', color: '#7c3aed', desc: 'All hours on Saturday & Sunday' },
    { value: 'holiday', label: _t("Holiday"), icon: 'fa-star', color: '#ea580c', desc: _t("All hours on public holidays") },
    { value: 'night', label: _t("Night Shift"), icon: 'fa-moon-o', color: '#1e293b', desc: _t("Hours within night time window") },
    { value: 'extended', label: _t("Extended"), icon: 'fa-bolt', color: '#dc2626', desc: _t("OT exceeding daily max cap") },
];

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const DAY_FIELDS = ['apply_monday', 'apply_tuesday', 'apply_wednesday', 'apply_thursday', 'apply_friday', 'apply_saturday', 'apply_sunday'];

class OvertimeRulesDashboard extends Component {
    static props = { action: { type: Object, optional: true }, "*": true };
    static template = xml`
    <div class="otr-container">
        <div class="wf-breadcrumb">
            <span class="wf-bc-home" t-on-click="goHome"><i class="fa fa-home"/></span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-link" t-on-click="goFlowDashboard">Dashboard</span>
            <span class="wf-bc-sep"><i class="fa fa-chevron-right"/></span>
            <span class="wf-bc-current">Overtime Rules</span>
        </div>
        <!-- Header -->
        <div class="otr-header">
            <div class="otr-header-left">
                <div class="otr-title"><i class="fa fa-balance-scale"/> Overtime Rules</div>
                <div class="otr-subtitle">Configure how work hours are classified and compensated</div>
            </div>
            <div class="otr-header-right">
                <button class="otr-btn otr-btn-new" t-on-click="openCreate">
                    <i class="fa fa-plus"/> New Rule
                </button>
                <button class="otr-btn otr-btn-refresh" t-on-click="loadRules">
                    <i class="fa fa-refresh"/>
                </button>
            </div>
        </div>

        <!-- Stats strip -->
        <div class="otr-stats" t-if="!state.loading">
            <div class="otr-stat">
                <div class="otr-stat-num" t-esc="state.rules.length"/>
                <div class="otr-stat-label">Total Rules</div>
            </div>
            <t t-foreach="otTypeStats" t-as="st" t-key="st.value">
                <div t-attf-class="otr-stat otr-stat-{{ st.value }}">
                    <div class="otr-stat-num" t-esc="st.count"/>
                    <div class="otr-stat-label" t-esc="st.label"/>
                </div>
            </t>
        </div>

        <!-- Rules Grid -->
        <div class="otr-grid" t-if="!state.loading">
            <t t-foreach="state.rules" t-as="rule" t-key="rule.id">
                <div t-attf-class="otr-card otr-card-{{ rule.overtime_type }}"
                     t-on-click="() => this.openEdit(rule)">
                    <div class="otr-card-header">
                        <div t-attf-class="otr-type-badge otr-type-{{ rule.overtime_type }}">
                            <i t-attf-class="fa {{ this.typeIcon(rule.overtime_type) }}"/>
                            <span t-esc="this.typeLabel(rule.overtime_type)"/>
                        </div>
                        <div class="otr-rate-circle">
                            <span class="otr-rate-num" t-esc="rule.rate_display"/>
                        </div>
                    </div>
                    <div class="otr-card-title" t-esc="rule.name"/>
                    <div class="otr-card-country" t-if="rule.country_id">
                        <i class="fa fa-flag-o"/> <t t-esc="rule.country_name"/>
                    </div>
                    <div class="otr-day-pills">
                        <t t-foreach="this.dayLetters" t-as="d" t-key="d_index">
                            <span t-attf-class="otr-day-pill {{ this.isDayActive(rule, d_index) ? 'otr-day-active' : '' }}">
                                <t t-esc="d"/>
                            </span>
                        </t>
                    </div>
                    <div class="otr-time-section" t-if="rule.time_from || rule.time_to">
                        <div class="otr-time-label"><i class="fa fa-moon-o"/> Night Window</div>
                        <div class="otr-time-bar">
                            <div class="otr-time-fill" t-attf-style="left: {{ this.timeBarLeft(rule) }}%; width: {{ this.timeBarWidth(rule) }}%"/>
                        </div>
                        <div class="otr-time-labels">
                            <span>12AM</span><span>6AM</span><span>12PM</span><span>6PM</span><span>12AM</span>
                        </div>
                    </div>
                    <div class="otr-metrics">
                        <div class="otr-metric">
                            <div class="otr-metric-val"><t t-esc="rule.rate_multiplier"/>x</div>
                            <div class="otr-metric-label">Multiplier</div>
                        </div>
                        <div class="otr-metric">
                            <div class="otr-metric-val"><t t-esc="rule.threshold_hours"/>h</div>
                            <div class="otr-metric-label">OT After</div>
                        </div>
                        <div class="otr-metric">
                            <div class="otr-metric-val"><t t-esc="rule.max_hours_per_day"/>h</div>
                            <div class="otr-metric-label">Max/Day</div>
                        </div>
                        <div class="otr-metric">
                            <div class="otr-metric-val"><t t-esc="rule.max_hours_per_month"/>h</div>
                            <div class="otr-metric-label">Max/Month</div>
                        </div>
                    </div>
                    <div class="otr-card-footer">
                        <span class="otr-approval" t-if="rule.requires_approval">
                            <i class="fa fa-check-circle"/> Approval Required
                        </span>
                        <span class="otr-no-approval" t-if="!rule.requires_approval">
                            <i class="fa fa-bolt"/> Auto-approved
                        </span>
                        <span class="otr-edit-hint"><i class="fa fa-pencil"/> Edit</span>
                    </div>
                </div>
            </t>
        </div>

        <!-- Info Section -->
        <div class="otr-info-section" t-if="!state.loading and state.rules.length > 0">
            <div class="otr-info-header"><i class="fa fa-info-circle"/> How overtime classification works</div>
            <div class="otr-info-grid">
                <div class="otr-info-card otr-info-weekday">
                    <div class="otr-info-icon"><i class="fa fa-briefcase"/></div>
                    <div class="otr-info-title">Weekday OT</div>
                    <div class="otr-info-desc">Hours beyond threshold on Mon–Fri become overtime</div>
                </div>
                <div class="otr-info-card otr-info-weekend">
                    <div class="otr-info-icon"><i class="fa fa-calendar-o"/></div>
                    <div class="otr-info-title">Weekend OT</div>
                    <div class="otr-info-desc">ALL hours on Sat/Sun are overtime at this rate</div>
                </div>
                <div class="otr-info-card otr-info-holiday">
                    <div class="otr-info-icon"><i class="fa fa-star"/></div>
                    <div class="otr-info-title">Holiday OT</div>
                    <div class="otr-info-desc">ALL hours on public holidays earn the premium</div>
                </div>
                <div class="otr-info-card otr-info-night">
                    <div class="otr-info-icon"><i class="fa fa-moon-o"/></div>
                    <div class="otr-info-title">Night Premium</div>
                    <div class="otr-info-desc">Hours within the night window earn extra rate</div>
                </div>
            </div>
        </div>

        <!-- Empty -->
        <div class="otr-empty" t-if="!state.loading and state.rules.length === 0">
            <i class="fa fa-balance-scale fa-3x"/>
            <h3>No overtime rules configured</h3>
            <p>Create your first rule to define overtime classification.</p>
            <button class="otr-btn otr-btn-new" t-on-click="openCreate"><i class="fa fa-plus"/> Create First Rule</button>
        </div>

        <div class="otr-loading" t-if="state.loading">
            <i class="fa fa-circle-o-notch fa-spin fa-2x"/><span>Loading…</span>
        </div>

        <!-- ═══════ PREMIUM EDIT/CREATE MODAL ═══════ -->
        <div class="otr-modal-overlay" t-if="state.modalOpen" t-on-click.self="closeModal">
            <div class="otr-modal">
                <!-- Modal Header -->
                <div class="otr-modal-header">
                    <h2 class="otr-modal-title">
                        <i class="fa fa-balance-scale"/>
                        <t t-if="state.form.id">Edit Rule</t>
                        <t t-if="!state.form.id">New Overtime Rule</t>
                    </h2>
                    <button class="otr-modal-close" t-on-click="closeModal"><i class="fa fa-times"/></button>
                </div>

                <!-- Step 1: Rule Name -->
                <div class="otr-form-section">
                    <label class="otr-form-label">Rule Name</label>
                    <input type="text" class="otr-form-input otr-form-input-lg"
                           placeholder="e.g. Vietnam — Weekday Overtime"
                           t-att-value="state.form.name"
                           t-on-input="(ev) => this.state.form.name = ev.target.value"/>
                </div>

                <!-- Step 2: OT Type Selector — visual cards -->
                <div class="otr-form-section">
                    <label class="otr-form-label">Overtime Type</label>
                    <div class="otr-type-selector">
                        <t t-foreach="this.otTypes" t-as="ot" t-key="ot.value">
                            <div t-attf-class="otr-type-card {{ state.form.overtime_type === ot.value ? 'otr-type-card-active' : '' }}"
                                 t-on-click="() => this.selectType(ot.value)"
                                 t-attf-style="--type-color: {{ ot.color }}">
                                <i t-attf-class="fa {{ ot.icon }} otr-type-card-icon"/>
                                <div class="otr-type-card-label" t-esc="ot.label"/>
                                <div class="otr-type-card-desc" t-esc="ot.desc"/>
                            </div>
                        </t>
                    </div>
                </div>

                <!-- Step 3: Rate & Limits -->
                <div class="otr-form-section">
                    <label class="otr-form-label">Rate &amp; Limits</label>
                    <div class="otr-form-row">
                        <div class="otr-form-group">
                            <div class="otr-form-sublabel">Rate Multiplier</div>
                            <div class="otr-rate-input-wrap">
                                <input type="number" step="0.1" min="1.0"
                                       class="otr-form-input otr-rate-input"
                                       t-att-value="state.form.rate_multiplier"
                                       t-on-input="(ev) => this.state.form.rate_multiplier = parseFloat(ev.target.value) || 1.5"/>
                                <span class="otr-rate-preview" t-esc="ratePreview"/>
                            </div>
                        </div>
                        <div class="otr-form-group">
                            <div class="otr-form-sublabel">OT Begins After (hrs)</div>
                            <input type="number" step="0.5" min="0"
                                   class="otr-form-input"
                                   t-att-value="state.form.threshold_hours"
                                   t-on-input="(ev) => this.state.form.threshold_hours = parseFloat(ev.target.value) || 0"/>
                        </div>
                        <div class="otr-form-group">
                            <div class="otr-form-sublabel">Max OT/Day</div>
                            <input type="number" step="0.5" min="0"
                                   class="otr-form-input"
                                   t-att-value="state.form.max_hours_per_day"
                                   t-on-input="(ev) => this.state.form.max_hours_per_day = parseFloat(ev.target.value) || 4"/>
                        </div>
                        <div class="otr-form-group">
                            <div class="otr-form-sublabel">Max OT/Month</div>
                            <input type="number" step="1" min="0"
                                   class="otr-form-input"
                                   t-att-value="state.form.max_hours_per_month"
                                   t-on-input="(ev) => this.state.form.max_hours_per_month = parseFloat(ev.target.value) || 40"/>
                        </div>
                    </div>
                </div>

                <!-- Step 4: Day Toggles -->
                <div class="otr-form-section">
                    <label class="otr-form-label">Applicable Days</label>
                    <div class="otr-day-toggles">
                        <t t-foreach="this.dayNames" t-as="dayName" t-key="dayName_index">
                            <div t-attf-class="otr-day-toggle {{ state.form[this.dayFields[dayName_index]] ? 'otr-day-toggle-on' : '' }}"
                                 t-on-click="() => this.toggleDay(dayName_index)">
                                <div class="otr-day-toggle-letter" t-esc="dayName.charAt(0)"/>
                                <div class="otr-day-toggle-name" t-esc="dayName"/>
                            </div>
                        </t>
                    </div>
                    <div class="otr-day-summary" t-esc="daysSummary"/>
                </div>

                <!-- Step 5: Time Window (mainly for Night Shift) -->
                <div class="otr-form-section" t-if="state.form.overtime_type === 'night'">
                    <label class="otr-form-label"><i class="fa fa-moon-o"/> Night Shift Time Window</label>
                    <div class="otr-form-row">
                        <div class="otr-form-group">
                            <div class="otr-form-sublabel">From</div>
                            <input type="time" class="otr-form-input"
                                   t-att-value="this.floatToTime(state.form.time_from)"
                                   t-on-input="(ev) => this.state.form.time_from = this.timeToFloat(ev.target.value)"/>
                        </div>
                        <div class="otr-form-group">
                            <div class="otr-form-sublabel">To</div>
                            <input type="time" class="otr-form-input"
                                   t-att-value="this.floatToTime(state.form.time_to)"
                                   t-on-input="(ev) => this.state.form.time_to = this.timeToFloat(ev.target.value)"/>
                        </div>
                    </div>
                    <div class="otr-time-preview">
                        <div class="otr-time-bar-lg">
                            <div class="otr-time-fill-lg"
                                 t-attf-style="left: {{ this.timeBarLeft(state.form) }}%; width: {{ this.timeBarWidth(state.form) }}%"/>
                        </div>
                        <div class="otr-time-labels-lg">
                            <span>12AM</span><span>3AM</span><span>6AM</span><span>9AM</span>
                            <span>12PM</span><span>3PM</span><span>6PM</span><span>9PM</span><span>12AM</span>
                        </div>
                    </div>
                </div>

                <!-- Step 6: Options -->
                <div class="otr-form-section">
                    <div class="otr-form-row">
                        <label class="otr-checkbox-label">
                            <input type="checkbox"
                                   t-att-checked="state.form.requires_approval"
                                   t-on-change="() => this.state.form.requires_approval = !this.state.form.requires_approval"/>
                            <span class="otr-checkbox-text"><i class="fa fa-check-circle"/> Requires Manager Approval</span>
                        </label>
                    </div>
                </div>

                <!-- Description -->
                <div class="otr-form-section">
                    <label class="otr-form-label">Legal Reference / Notes</label>
                    <textarea class="otr-form-textarea"
                              placeholder="e.g. Vietnam Labor Code Art. 98: Weekday overtime paid at 150%..."
                              t-att-value="state.form.note"
                              t-on-input="(ev) => this.state.form.note = ev.target.value"/>
                </div>

                <!-- Footer -->
                <div class="otr-modal-footer">
                    <button class="otr-btn otr-btn-cancel" t-on-click="closeModal">Cancel</button>
                    <button class="otr-btn otr-btn-delete" t-if="state.form.id" t-on-click="deleteRule">
                        <i class="fa fa-trash"/> Delete
                    </button>
                    <button class="otr-btn otr-btn-save" t-on-click="saveRule" t-att-disabled="state.saving">
                        <i t-attf-class="fa {{ state.saving ? 'fa-spinner fa-spin' : 'fa-check' }}"/>
                        <t t-if="state.form.id">Save Changes</t>
                        <t t-if="!state.form.id">Create Rule</t>
                    </button>
                </div>
            </div>
        </div>
    </div>`;

    setup() {
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        this.otTypes = OT_TYPES;
        this.dayNames = DAYS;
        this.dayFields = DAY_FIELDS;
        this.dayLetters = DAYS.map(d => d.charAt(0));

        this.state = useState({
            loading: true,
            rules: [],
            modalOpen: false,
            saving: false,
            form: this._emptyForm(),
        });
        onMounted(() => this.loadRules());
    }

    _emptyForm() {
        return {
            id: false,
            name: '',
            overtime_type: 'weekday',
            rate_multiplier: 1.5,
            threshold_hours: 8.0,
            max_hours_per_day: 4.0,
            max_hours_per_month: 40.0,
            requires_approval: true,
            time_from: 0, time_to: 0,
            apply_monday: true, apply_tuesday: true, apply_wednesday: true,
            apply_thursday: true, apply_friday: true,
            apply_saturday: false, apply_sunday: false,
            note: '',
        };
    }

    async loadRules() {
        this.state.loading = true;
        try {
            const rules = await rpc('/web/dataset/call_kw/hr.overtime.config/search_read', {
                model: 'hr.overtime.config', method: 'search_read',
                args: [[['active', '=', true]]],
                kwargs: {
                    fields: [
                        'name', 'overtime_type', 'rate_multiplier', 'rate_display',
                        'max_hours_per_day', 'max_hours_per_month', 'requires_approval',
                        'country_id', 'time_from', 'time_to', 'threshold_hours',
                        'apply_monday', 'apply_tuesday', 'apply_wednesday',
                        'apply_thursday', 'apply_friday', 'apply_saturday', 'apply_sunday',
                        'applicable_days_display', 'time_display', 'note',
                    ],
                    order: 'country_id, sequence',
                },
            });
            this.state.rules = rules.map(r => ({
                ...r,
                country_name: r.country_id ? r.country_id[1] : '',
            }));
        } catch (e) { console.error('OT Rules load:', e); }
        this.state.loading = false;
    }

    get otTypeStats() {
        return OT_TYPES.map(t => ({
            ...t,
            count: this.state.rules.filter(r => r.overtime_type === t.value).length,
        }));
    }

    get ratePreview() {
        return Math.round((this.state.form.rate_multiplier || 1) * 100) + '%';
    }

    get daysSummary() {
        const active = DAY_FIELDS.map((f, i) => this.state.form[f] ? DAYS[i] : null).filter(Boolean);
        if (active.length === 7) return _t("Every day");
        if (active.length === 5 && !this.state.form.apply_saturday && !this.state.form.apply_sunday) return 'Weekdays (Mon–Fri)';
        if (active.length === 2 && this.state.form.apply_saturday && this.state.form.apply_sunday) return 'Weekends (Sat–Sun)';
        return active.join(', ') || _t("No days selected");
    }

    typeIcon(t) { return (OT_TYPES.find(o => o.value === t) || {}).icon || 'fa-clock-o'; }
    typeLabel(t) { return (OT_TYPES.find(o => o.value === t) || {}).label || t; }
    isDayActive(rule, idx) { return rule[DAY_FIELDS[idx]]; }
    timeBarLeft(r) { return (r.time_from / 24) * 100; }
    timeBarWidth(r) {
        if (!r.time_from && !r.time_to) return 0;
        if (r.time_to < r.time_from) return ((24 - r.time_from + r.time_to) / 24) * 100;
        return ((r.time_to - r.time_from) / 24) * 100;
    }

    floatToTime(f) {
        const h = Math.floor(f || 0);
        const m = Math.round(((f || 0) - h) * 60);
        return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    }
    timeToFloat(s) {
        if (!s) return 0;
        const [h, m] = s.split(':').map(Number);
        return h + m / 60;
    }

    // ── Modal actions ──
    openCreate() {
        this.state.form = this._emptyForm();
        this.state.modalOpen = true;
    }

    openEdit(rule) {
        this.state.form = {
            id: rule.id,
            name: rule.name || '',
            overtime_type: rule.overtime_type || 'weekday',
            rate_multiplier: rule.rate_multiplier || 1.5,
            threshold_hours: rule.threshold_hours || 0,
            max_hours_per_day: rule.max_hours_per_day || 4,
            max_hours_per_month: rule.max_hours_per_month || 40,
            requires_approval: rule.requires_approval,
            time_from: rule.time_from || 0,
            time_to: rule.time_to || 0,
            apply_monday: rule.apply_monday,
            apply_tuesday: rule.apply_tuesday,
            apply_wednesday: rule.apply_wednesday,
            apply_thursday: rule.apply_thursday,
            apply_friday: rule.apply_friday,
            apply_saturday: rule.apply_saturday,
            apply_sunday: rule.apply_sunday,
            note: rule.note || '',
        };
        this.state.modalOpen = true;
    }

    closeModal() { this.state.modalOpen = false; }

    selectType(type) {
        this.state.form.overtime_type = type;
        // Auto-set defaults like Deputy
        if (type === 'weekday') {
            Object.assign(this.state.form, {
                apply_monday: true, apply_tuesday: true, apply_wednesday: true,
                apply_thursday: true, apply_friday: true,
                apply_saturday: false, apply_sunday: false,
                threshold_hours: 8.0, time_from: 0, time_to: 0,
            });
        } else if (type === 'weekend') {
            Object.assign(this.state.form, {
                apply_monday: false, apply_tuesday: false, apply_wednesday: false,
                apply_thursday: false, apply_friday: false,
                apply_saturday: true, apply_sunday: true,
                threshold_hours: 0, time_from: 0, time_to: 0,
            });
        } else if (type === 'holiday') {
            Object.assign(this.state.form, {
                apply_monday: true, apply_tuesday: true, apply_wednesday: true,
                apply_thursday: true, apply_friday: true,
                apply_saturday: true, apply_sunday: true,
                threshold_hours: 0, time_from: 0, time_to: 0,
            });
        } else if (type === 'night') {
            Object.assign(this.state.form, {
                apply_monday: true, apply_tuesday: true, apply_wednesday: true,
                apply_thursday: true, apply_friday: true,
                apply_saturday: true, apply_sunday: true,
                threshold_hours: 0, time_from: 22, time_to: 6,
            });
        }
    }

    toggleDay(idx) {
        this.state.form[DAY_FIELDS[idx]] = !this.state.form[DAY_FIELDS[idx]];
    }

    async saveRule() {
        const f = this.state.form;
        if (!f.name) {
            this.notificationService.add(_t("Please enter a rule name"), { type: 'warning' });
            return;
        }
        this.state.saving = true;
        const vals = {
            name: f.name, overtime_type: f.overtime_type,
            rate_multiplier: f.rate_multiplier, threshold_hours: f.threshold_hours,
            max_hours_per_day: f.max_hours_per_day, max_hours_per_month: f.max_hours_per_month,
            requires_approval: f.requires_approval,
            time_from: f.time_from, time_to: f.time_to,
            apply_monday: f.apply_monday, apply_tuesday: f.apply_tuesday,
            apply_wednesday: f.apply_wednesday, apply_thursday: f.apply_thursday,
            apply_friday: f.apply_friday, apply_saturday: f.apply_saturday,
            apply_sunday: f.apply_sunday,
            note: f.note,
        };
        try {
            if (f.id) {
                await rpc('/web/dataset/call_kw/hr.overtime.config/write', {
                    model: 'hr.overtime.config', method: 'write',
                    args: [[f.id], vals], kwargs: {},
                });
                this.notificationService.add(_t("Rule updated"), { type: 'success' });
            } else {
                await rpc('/web/dataset/call_kw/hr.overtime.config/create', {
                    model: 'hr.overtime.config', method: 'create',
                    args: [vals], kwargs: {},
                });
                this.notificationService.add(_t("Rule created"), { type: 'success' });
            }
            this.state.modalOpen = false;
            await this.loadRules();
        } catch (e) {
            console.error('Save failed:', e);
            this.notificationService.add('Save failed: ' + (e.message || e), { type: 'danger' });
        }
        this.state.saving = false;
    }

    async deleteRule() {
        if (!confirm('Delete this overtime rule?')) return;
        try {
            await rpc('/web/dataset/call_kw/hr.overtime.config/unlink', {
                model: 'hr.overtime.config', method: 'unlink',
                args: [[this.state.form.id]], kwargs: {},
            });
            this.notificationService.add(_t("Rule deleted"), { type: 'info' });
            this.state.modalOpen = false;
            await this.loadRules();
        } catch (e) {
            this.notificationService.add('Delete failed', { type: 'danger' });
        }
    }

    goHome() { this.actionService.doAction('pb_dashboard.action_pb_dashboard'); }
    goFlowDashboard() {
        this.actionService.doAction('pb_dashboard.action_pb_dashboard');
    }
}

registry.category("actions").add("overtime_rules_dashboard", OvertimeRulesDashboard);
