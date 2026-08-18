/** @odoo-module **/
/**
 * The Schedule cockpit — the Deputy-shaped roster, rebuilt as an instrument.
 *
 * The Gen-0 screen it replaces (`shift_planning_grid`) was kept registered
 * through P2-P6 under W18 and was finally deleted in P7. This is a NEW
 * component over NEW facade methods, which is why that deletion cost this file
 * nothing: the two never shared a payload.
 *
 * What carried over, deliberately: the employee × day grid, the sticky people
 * column with its hours-vs-contract bar, the Open Shifts row, the leave
 * overlay, conflict marks, publish-all with a draft badge, week⇄fortnight, and
 * the template quick-create with colour swatches. What did not: the private
 * department and job dropdowns (W4 — department comes from `wf_context` now,
 * and the job filter was a second unsynchronized context), the U+26A0 warning
 * emoji, the FontAwesome icons, the eleven hand-picked 2013 hexes, and
 * `target:"current"` on a shift card, which replaced the whole cockpit with a
 * form and no way back (W5).
 *
 * Later work packages hang off the same read call: the stats strip (WP-3), the
 * coverage overlay (WP-4) and the edit-time warnings (WP-5).
 *
 * P3 note: the component takes an `embedded` prop (W17) so Mission Control can
 * host it as a lens without a fork — `embedded` suppresses ONLY the chrome a
 * host would own (its own title row and `<WfContextBar/>`), never a facade call.
 */
import { Component, useState, onWillStart, onWillUpdateProps, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfContextBar } from "@pb_wf_kit/js/wf_context_bar";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { WfPersonWeek } from "@pb_wf_kit/js/wf_person_week";
import { WF_ROW_CAP } from "@pb_wf_kit/js/wf_rows";

const MODEL = "hr.shift.planning.grid";
const HUB_MODEL = "pb.time.hub";
const SPAN_KEY = "pbsc.span.v1";
const COVER_KEY = "pbsc.coverage.v1";

/**
 * Template identity colours: ELEVEN slots, and not one hex in this file.
 *
 * `hr.shift.template.color` is a plain integer index, so the grid needs a
 * stable index → identity mapping. The legacy grid hardcoded eleven 2013 flat-UI
 * hexes in JS (`SHIFT_COLORS`), which is exactly what W1 forbids. Here the
 * index only ever becomes a CLASS NAME; the eleven identities are defined in
 * pb_schedule.scss out of `--pbim-*` tokens and `color-mix()`, so the palette
 * follows the design system automatically and this file cannot invent a colour
 * even by accident.
 */
export const TEMPLATE_TONES = 11;

export class PbSchedule extends Component {
    static template = "pb_schedule.PbSchedule";
    static components = { WfContextBar, WfDrawer, WfPersonWeek };
    static props = {
        action: { type: Object, optional: true },
        // W17: the hub owns the title row and the context bar; the cockpit
        // keeps every facade call and every instrument.
        embedded: { type: Boolean, optional: true },
        // P3b §3.6 — one palette instruction, consumed by nonce. Always an
        // object, never null: a TYPED optional prop rejects null (W35).
        pbCmd: { type: Object, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false, pbCmd: { name: "", nonce: 0 } };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        this.ctxSvc = useService("wf_context");
        this.wf = useState(this.ctxSvc.state);

        this.state = useState({
            data: null,
            loading: true,
            // 7 | 14 — a LOCAL view choice that widens the window from the
            // context week; the shared context stays a week (W4).
            span: this._restoreSpan(),
            // quick-create
            create: null,           // { employeeId, employeeName, date, label }
            creating: false,
            checks: null,           // check_day payload for the open square
            checking: false,
            // copy week
            copyOpen: false,
            copying: false,
            copyReport: null,       // the refuse-on-paste skip report
            // person drawer
            person: null,
            personLoading: false,
            drawerHidden: !!this.ctxSvc.state.personId,
            publishing: false,
            // budget dialog (WP-3)
            budgetOpen: false,
            budgetValue: "",
            budgetSaving: false,
            // coverage (WP-4)
            coverageOn: this._restoreFlag(COVER_KEY),
            coverageDrawer: false,
            coverageData: null,
            coverageForm: null,
            coverageSaving: false,
            // templates drawer (WP-6) — the retired rail item's new home
            templatesDrawer: false,
            templatesData: null,
        });

        // Stable handler identities — a fresh inline arrow makes OWL treat the
        // child's props as changed and remount it, restarting its onWillStart.
        this._h = {
            onOpenProfile: () => this.openProfile(),
        };

        const off = this.ctxSvc.onChange(() => this.load());
        onWillUnmount(off);

        // The palette's instruction can only be applied once the roster is in
        // hand (a quick-create needs a day and an employee), so it is consumed
        // AFTER the load, and again whenever the host sends a new nonce.
        this._cmdNonce = 0;
        onWillUpdateProps((next) => { this._applyPbCmd(next.pbCmd); });
        onWillStart(async () => {
            await this.load();
            this._applyPbCmd(this.props.pbCmd);
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    // -------------------------------------------------------------- span
    _restoreFlag(key) {
        try { return window.localStorage.getItem(key) === "1"; }
        catch { return false; }
    }

    _saveFlag(key, on) {
        try { window.localStorage.setItem(key, on ? "1" : "0"); }
        catch { /* private mode */ }
    }

    _restoreSpan() {
        try {
            const v = parseInt(window.localStorage.getItem(SPAN_KEY), 10);
            if (v === 14) { return 14; }
        } catch { /* private mode */ }
        return 7;
    }

    setSpan(n) {
        const v = n === 14 ? 14 : 7;
        if (this.state.span === v) { return; }
        this.state.span = v;
        try { window.localStorage.setItem(SPAN_KEY, String(v)); } catch { /* private mode */ }
        this.load();
    }

    // -------------------------------------------------------------- data
    async load(silent = false) {
        if (!silent) { this.state.loading = true; }
        try {
            const data = await this.orm.call(MODEL, "get_schedule_data", [
                this.wf.weekStart, this.wf.departmentId || false,
                this.state.span, this.wf.search || "",
            ]);
            this.state.data = data;
        } catch (e) {
            this.state.data = null;
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not load the roster."), { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    refresh() { return this.load(); }

    get d() { return this.state.data; }
    get days() { return (this.d && this.d.days) || []; }
    get employees() { return (this.d && this.d.employees) || []; }
    get templates() { return (this.d && this.d.templates) || []; }
    get counts() { return (this.d && this.d.counts) || {}; }
    get truncated() { return (this.d && this.d.truncated) || 0; }
    get rowCap() { return WF_ROW_CAP; }

    get openShiftsForDay() { return (this.d && this.d.open_shifts) || {}; }

    /**
     * W29 — the Open Shifts row is real, but it cannot currently FILL.
     *
     * `hr.shift.planning.employee_id` is `required=True`
     * (pb_hr_workforce/models/shift_planning.py:17-19) and nothing in the tree
     * relaxes it, so `not s.employee_id` is unsatisfiable and the legacy grid's
     * open-shift bucket was always `{}`. Worse, its cells were a create door
     * into `quick_create_shift(false, …)`, which would have been refused by the
     * ORM's own required-field check.
     *
     * So: the row is KEPT (this is where unassigned demand belongs, and P4's
     * engine is the phase that gets to relax the field), rendered only when the
     * payload really has open shifts, and it is NOT a create door. A door that
     * can only ever produce an error is worse than no door at all (W5).
     */
    get hasOpenShifts() {
        return Object.values(this.openShiftsForDay).some((a) => a && a.length);
    }

    /** The grid's column template — one sticky people column + N days. */
    get gridStyle() {
        return `grid-template-columns: 232px repeat(${this.days.length}, minmax(112px, 1fr));`;
    }

    /** index → one of the ELEVEN token-derived identities (never a hex). */
    tone(colorIdx) {
        const i = Number.isFinite(colorIdx) ? colorIdx : 0;
        return ((i % TEMPLATE_TONES) + TEMPLATE_TONES) % TEMPLATE_TONES;
    }

    /** "7.5" — hours, never "7.5000000001". */
    hrs(v) { return String(Math.round((v || 0) * 10) / 10); }

    /** 0–100, clamped: a 60-hour week must not paint outside its own bar. */
    hoursPct(row) {
        if (!row.contracted_hours) { return 0; }
        return Math.max(0, Math.min(100, (row.total_hours / row.contracted_hours) * 100));
    }

    hoursTone(row) {
        if (!row.contracted_hours) { return ""; }
        const pct = (row.total_hours / row.contracted_hours) * 100;
        if (pct > 100) { return "over"; }
        if (pct >= 90) { return "full"; }
        return "";
    }

    fmtHour(h) {
        const hr = Math.floor(h || 0);
        const mn = Math.round(((h || 0) % 1) * 60);
        return `${String(hr).padStart(2, "0")}:${String(mn).padStart(2, "0")}`;
    }

    dayLabel(day) { return `${day.label} ${day.day_num} ${day.month}`; }

    // ================================================ WP-3: cost & budget
    get stats() { return (this.d && this.d.stats) || null; }

    /** Day stats keyed by ISO date, so a header cell is an O(1) lookup. */
    get statsByDay() {
        const out = {};
        for (const s of (this.stats && this.stats.days) || []) { out[s.date] = s; }
        return out;
    }

    /**
     * Money, COMPACT. A Vietnamese week of 200 people is nine digits, and nine
     * digits in a 112-pixel day column is a column of "…". `Intl` does the
     * locale work; the currency code comes from the company, never guessed.
     */
    money(v, compact = true) {
        const st = this.stats;
        if (v === null || v === undefined) { return "—"; }
        const code = (st && st.currency && st.currency.name) || "USD";
        try {
            return new Intl.NumberFormat(undefined, {
                style: "currency",
                currency: code,
                notation: compact ? "compact" : "standard",
                maximumFractionDigits: compact ? 1 : 0,
            }).format(v);
        } catch {
            // an unknown/invalid ISO code must not take the strip down
            return `${Math.round(v).toLocaleString()} ${code}`;
        }
    }

    get budget() { return (this.stats && this.stats.budget) || null; }
    get canEditBudget() { return !!(this.stats && this.stats.can_edit_budget); }

    /** 0–100 of the bar; the LABEL still reports the true percentage. */
    get budgetPct() {
        const b = this.budget;
        if (!b || !b.amount) { return 0; }
        return Math.max(0, Math.min(100, (this.stats.total_cost / b.amount) * 100));
    }

    get budgetRatio() {
        const b = this.budget;
        if (!b || !b.amount) { return 0; }
        return (this.stats.total_cost / b.amount) * 100;
    }

    /** under budget green · ≥90% amber · over rose (W1 semantics). */
    get budgetTone() {
        const r = this.budgetRatio;
        if (r > 100) { return "over"; }
        if (r >= 90) { return "near"; }
        return "under";
    }

    /** True when a fortnight is being compared against fewer weeks of money. */
    get budgetPartial() {
        const b = this.budget;
        return !!(b && b.weeks_budgeted < b.weeks_in_span);
    }

    openBudget() {
        if (!this.canEditBudget) { return; }
        const b = this.budget;
        this.state.budgetValue = b && b.amount ? String(b.amount) : "";
        this.state.budgetOpen = true;
    }

    closeBudget() { this.state.budgetOpen = false; }

    onBudgetInput(ev) { this.state.budgetValue = ev.target.value; }

    async saveBudget() {
        if (this.state.budgetSaving) { return; }
        const raw = parseFloat(String(this.state.budgetValue).replace(/[^\d.-]/g, ""));
        if (!Number.isFinite(raw) || raw < 0) {
            this.notif.add(_t("Enter a positive amount."), { type: "warning" });
            return;
        }
        this.state.budgetSaving = true;
        try {
            await this.orm.call(MODEL, "set_budget", [
                this.wf.weekStart, this.wf.departmentId || false, raw,
            ]);
            this.state.budgetOpen = false;
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not save the budget."), { type: "danger" });
        } finally {
            this.state.budgetSaving = false;
        }
    }

    async clearBudget() {
        if (this.state.budgetSaving) { return; }
        this.state.budgetSaving = true;
        try {
            await this.orm.call(MODEL, "clear_budget", [
                this.wf.weekStart, this.wf.departmentId || false,
            ]);
            this.state.budgetOpen = false;
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not remove the budget."), { type: "danger" });
        } finally {
            this.state.budgetSaving = false;
        }
    }

    // ==================================================== WP-4: coverage
    get coverage() { return (this.d && this.d.coverage) || null; }

    /** Chips only render when the scope has actually STATED a requirement. */
    get hasCoverage() { return !!this.coverage; }

    coverageFor(day) {
        const c = this.coverage;
        return (c && c[day.date]) || null;
    }

    toggleCoverage() {
        this.state.coverageOn = !this.state.coverageOn;
        this._saveFlag(COVER_KEY, this.state.coverageOn);
    }

    async openCoverageDrawer() {
        this.state.coverageDrawer = true;
        this.state.coverageForm = null;
        await this._loadCoverage();
    }

    closeCoverageDrawer() {
        this.state.coverageDrawer = false;
        this.state.coverageForm = null;
    }

    /**
     * W21: this runs from a CLICK handler, never a mount hook — and it is a
     * pure read, so re-entering it cannot mint anything.
     */
    async _loadCoverage() {
        try {
            this.state.coverageData = await this.orm.call(
                MODEL, "get_coverage_requirements",
                [this.wf.departmentId || false]);
        } catch (e) {
            this.state.coverageData = null;
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not load coverage requirements."), { type: "danger" });
        }
    }

    get coverageRows() {
        return (this.state.coverageData && this.state.coverageData.rows) || [];
    }

    get coverageWeekdays() {
        return (this.state.coverageData && this.state.coverageData.weekdays) || [];
    }

    get canEditCoverage() {
        return !!(this.state.coverageData && this.state.coverageData.can_edit);
    }

    newCoverageRow() {
        this.state.coverageForm = {
            id: false,
            department_id: this.wf.departmentId || false,
            mode: "weekday",
            weekday: "0",
            date: this.wf.weekStart,
            template_id: false,
            required_headcount: 1,
        };
    }

    editCoverageRow(row) {
        this.state.coverageForm = {
            id: row.id,
            department_id: row.department_id,
            mode: row.date ? "date" : "weekday",
            weekday: row.weekday || "0",
            date: row.date || this.wf.weekStart,
            template_id: row.template_id || false,
            required_headcount: row.required_headcount,
        };
    }

    cancelCoverageForm() { this.state.coverageForm = null; }

    onCoverageField(field, ev) {
        const f = this.state.coverageForm;
        if (!f) { return; }
        let v = ev.target.value;
        if (field === "required_headcount") { v = parseInt(v, 10) || 0; }
        if (field === "template_id") { v = v ? parseInt(v, 10) : false; }
        f[field] = v;
    }

    async saveCoverageRow() {
        const f = this.state.coverageForm;
        if (!f || this.state.coverageSaving) { return; }
        this.state.coverageSaving = true;
        try {
            await this.orm.call(MODEL, "save_coverage_requirement", [{
                department_id: f.department_id || false,
                // exactly one of the two, which is what the model constrains
                weekday: f.mode === "weekday" ? f.weekday : false,
                date: f.mode === "date" ? f.date : false,
                template_id: f.template_id || false,
                required_headcount: f.required_headcount,
            }, f.id || false]);
            this.state.coverageForm = null;
            await this._loadCoverage();
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not save that requirement."), { type: "danger" });
        } finally {
            this.state.coverageSaving = false;
        }
    }

    async deleteCoverageRow(row) {
        if (this.state.coverageSaving) { return; }
        this.state.coverageSaving = true;
        try {
            await this.orm.call(MODEL, "delete_coverage_requirement", [row.id]);
            await this._loadCoverage();
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not remove that requirement."), { type: "danger" });
        } finally {
            this.state.coverageSaving = false;
        }
    }

    // =========================================== WP-6: templates drawer
    async openTemplates() {
        this.state.templatesDrawer = true;
        await this._loadTemplates();
    }

    closeTemplates() { this.state.templatesDrawer = false; }

    /** W21: click handler, pure read. */
    async _loadTemplates() {
        try {
            this.state.templatesData = await this.orm.call(
                MODEL, "get_templates",
                [this.wf.weekStart, this.state.span,
                 this.wf.departmentId || false]);
        } catch (e) {
            this.state.templatesData = null;
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not load the shift library."), { type: "danger" });
        }
    }

    get templateRows() {
        return (this.state.templatesData && this.state.templatesData.rows) || [];
    }

    /**
     * Editing stays on the NATIVE form (W5: dialog + return path). A bespoke
     * editor for a five-field configuration model would be a second source of
     * truth for `duration`, whose compute lives on the model.
     */
    openTemplate(row) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.shift.template",
            res_id: row ? row.id : false,
            views: [[false, "form"]],
            target: "new",
        }, {
            onClose: async () => {
                await this._loadTemplates();
                await this.load();
            },
        });
    }

        /**
         * The `pb_cmd` channel (P3b §3.6).
         *
         * Mission Control forwards ONE palette instruction as a prop with a
         * NONCE, and this lens tracks the last nonce it ran. That is the whole
         * protocol, and it is shaped that way on purpose: a "consumed" callback
         * would be a CHILD writing HOST state from a mount hook, which is the
         * bug that cost P1a 591 junk records and then bit a second time on a
         * keyed child (W21/W21.1). Nothing here writes anything but this
         * component's own state, and an unknown command is ignored — a lens
         * that does not implement a verb is not an error.
         */
    _applyPbCmd(cmd) {
        if (!cmd || !cmd.nonce || cmd.nonce === this._cmdNonce) { return; }
        this._cmdNonce = cmd.nonce;
        if (cmd.name === "copy_week") {
            this.openCopy();
        } else if (cmd.name === "set_budget") {
            if (this.canEditBudget) {
                this.openBudget();
            } else {
                this.notif.add(
                    _t("Only a scheduling manager can set the labour budget."),
                    { type: "warning" });
            }
        } else if (cmd.name === "quick_create") {
            // W29: `hr.shift.planning.employee_id` is REQUIRED, so a create with
            // no employee is a door that can only ever produce an error. With an
            // empty roster the honest answer is to say so.
            const emp = this.employees[0];
            const day = this.days.find((d) => d.date === this.wf.day)
                || this.days[0];
            if (!emp || !day) {
                this.notif.add(
                    _t("There is nobody to schedule in this department yet."),
                    { type: "warning" });
                return;
            }
            this.openCreate(emp.id, day);
        }
    }

    // ------------------------------------------------------ quick create
    openCreate(employeeId, day) {
        const emp = employeeId
            ? this.employees.find((e) => e.id === employeeId) : null;
        this.state.create = {
            employeeId: employeeId || false,
            employeeName: emp ? emp.name : "",
            date: day.date,
            label: this.dayLabel(day),
            onLeave: emp ? (emp.leaves[day.date] || null) : null,
        };
        this.state.checks = null;
        if (employeeId) { this._loadChecks(employeeId, day.date); }
    }

    closeCreate() {
        this.state.create = null;
        this.state.checks = null;
    }

    /**
     * WP-5: every template's verdict, BEFORE any of them is clicked.
     *
     * W21: fired from a click handler (openCreate), never a mount hook, and it
     * is a pure read — `check_day` cannot write anything.
     */
    async _loadChecks(employeeId, dateStr) {
        const ids = this.templates.map((t) => t.id);
        if (!ids.length) { return; }
        this.state.checking = true;
        try {
            const res = await this.orm.call(MODEL, "check_day",
                                            [employeeId, dateStr, ids]);
            // a modal the officer has since closed must not repaint
            if (this.state.create && this.state.create.date === dateStr) {
                this.state.checks = res;
            }
        } catch {
            // warnings are a courtesy: losing them must not break the modal,
            // and the server constraint is still the real guard
            this.state.checks = null;
        } finally {
            this.state.checking = false;
        }
    }

    get contextWarnings() {
        return (this.state.checks && this.state.checks.context) || [];
    }

    warningsFor(templateId) {
        const by = this.state.checks && this.state.checks.by_template;
        return (by && by[String(templateId)]) || [];
    }

    blockFor(templateId) {
        return this.warningsFor(templateId).find((w) => w.severity === "block")
            || null;
    }

    /** "" | "warn" | "block" — the tile's marker tone. */
    templateTone(templateId) {
        const w = this.warningsFor(templateId);
        if (w.some((x) => x.severity === "block")) { return "block"; }
        if (w.some((x) => x.severity === "warn")) { return "warn"; }
        return "";
    }

    async createShift(templateId) {
        const c = this.state.create;
        if (!c || this.state.creating) { return; }
        // `block` prevents the create in the UI. The server constraint remains
        // the real guard — this only means the officer is told first.
        const blocked = this.blockFor(templateId);
        if (blocked) {
            this.notif.add(blocked.text, { type: "danger", sticky: true });
            return;
        }
        this.state.creating = true;
        try {
            await this.orm.call(MODEL, "quick_create_shift",
                                [c.employeeId || false, c.date, templateId]);
            this.state.create = null;
            this.notif.add(_t("Shift added."), { type: "success" });
            await this.load();
        } catch (e) {
            // The young-worker constraint raises here, with its law citation.
            // Surface the server's own message: it is better written than any
            // generic "could not create" we could put in its place.
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not add that shift."), { type: "danger" });
        } finally {
            this.state.creating = false;
        }
    }

    async deleteShift(shift) {
        if (!shift || shift.state !== "draft") { return; }
        try {
            const ok = await this.orm.call(MODEL, "delete_shift", [shift.id]);
            if (!ok) {
                this.notif.add(_t("Only draft shifts can be removed."),
                               { type: "warning" });
                return;
            }
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not remove that shift."), { type: "danger" });
        }
    }

    /**
     * A shift card is a DOOR to its native form — as a dialog with a return
     * path (W5). The legacy grid used `target: "current"`, which replaced the
     * whole roster with a form view and left no way back to the week.
     */
    openShift(shift) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.shift.planning",
            res_id: shift.id,
            views: [[false, "form"]],
            target: "new",
        }, { onClose: () => this.load() });
    }

    // ----------------------------------------------------------- publish
    async publishAll() {
        if (this.state.publishing || !this.counts.draft) { return; }
        this.state.publishing = true;
        try {
            const n = await this.orm.call(MODEL, "publish_shifts", [
                this.wf.weekStart, this.wf.departmentId || false, this.state.span,
            ]);
            this.notif.add(_t("%s shifts published.", n), { type: "success" });
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Publish failed."), { type: "danger" });
        } finally {
            this.state.publishing = false;
        }
    }

    // --------------------------------------------------------- copy week
    get nextSpanStart() {
        const [y, m, d] = String(this.wf.weekStart).split("-").map(Number);
        const dt = new Date(y, m - 1, d);
        dt.setDate(dt.getDate() + this.state.span);
        const p = (n) => String(n).padStart(2, "0");
        return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
    }

    openCopy() {
        this.state.copyOpen = true;
        this.state.copyReport = null;
    }

    closeCopy() {
        this.state.copyOpen = false;
        this.state.copyReport = null;
    }

    /**
     * Copy Week is REFUSE-ON-PASTE (§3.6). The legacy button pasted everything
     * unconditionally — onto approved leave, onto shifts people already had,
     * and onto nights a young worker is legally barred from, which the ORM then
     * refused, aborting the whole paste with no report of what happened.
     *
     * The modal stays open on the report: "12 copied, 3 skipped" with names and
     * reasons is the entire point, and a toast that disappears is not it.
     */
    async doCopy() {
        if (this.state.copying) { return; }
        this.state.copying = true;
        try {
            const res = await this.orm.call(MODEL, "copy_week_checked", [
                this.wf.weekStart, this.nextSpanStart,
                this.wf.departmentId || false, this.state.span,
            ]);
            this.state.copyReport = res;
            if (!res.skipped.length) {
                this.notif.add(_t("%s shifts copied forward.", res.created),
                               { type: "success" });
            }
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("Copy failed."), { type: "danger" });
        } finally {
            this.state.copying = false;
        }
    }

    // ------------------------------------------------------ person door
    openPerson(employeeId) {
        if (!employeeId) { return; }
        this.state.drawerHidden = false;
        this.ctxSvc.set({ personId: employeeId });
        this._loadPerson(employeeId, this.wf.weekStart);
    }

    closePerson() {
        this.state.drawerHidden = true;
        this.state.person = null;
        this.ctxSvc.set({ personId: false });
    }

    get drawerOpen() { return !!this.wf.personId && !this.state.drawerHidden; }

    /**
     * W21/W21.1: this is called from a CLICK handler, never from a mount hook.
     * `get_person_week` is a pure read, so re-entering it is harmless — but the
     * rule that keeps it that way is that mounts read and handlers write, and
     * nothing here is allowed to become a write later.
     */
    async _loadPerson(personId, weekStart) {
        this.state.personLoading = true;
        try {
            const data = await this.orm.call(HUB_MODEL, "get_person_week",
                                             [personId, weekStart]);
            if (this.wf.personId !== personId) { return; }
            this.state.person = data && data.employee ? data : null;
        } catch (e) {
            this.state.person = null;
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not load that person."), { type: "danger" });
        } finally {
            this.state.personLoading = false;
        }
    }

    get drawerTitle() {
        const p = this.state.person;
        return (p && p.employee.name) || _t("Loading…");
    }

    get drawerSubtitle() {
        const p = this.state.person;
        if (!p) { return ""; }
        return [p.employee.job, p.employee.dept, p.employee.badge]
            .filter((x) => x).join(" · ");
    }

    openProfile() {
        const p = this.state.person;
        if (!p) { return; }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: p.employee.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    // ------------------------------------------------------ empty states
    get emptyState() {
        if (this.state.loading) { return null; }
        if (!this.d) {
            return { icon: "alert", title: _t("The roster could not load"),
                     sub: _t("Refresh to try again. If it keeps failing you may not have attendance-officer access.") };
        }
        if (!this.employees.length) {
            return { icon: "users", title: _t("Nobody to schedule here"),
                     sub: _t("No employee matches this department or search. Clear the filter and the week fills up.") };
        }
        return null;
    }
}

registry.category("actions").add("pb_schedule", PbSchedule);
