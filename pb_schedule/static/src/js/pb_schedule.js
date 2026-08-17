/** @odoo-module **/
/**
 * The Schedule cockpit — the Deputy-shaped roster, rebuilt as an instrument.
 *
 * The Gen-0 screen it replaces (`shift_planning_grid`) is still registered and
 * still works (W18 retirement, not deletion); this is a NEW component over NEW
 * facade methods, so nothing the old screen consumes can drift underneath it.
 *
 * What carried over, deliberately: the employee × day grid, the sticky people
 * column with its hours-vs-contract bar, the Open Shifts row, the leave
 * overlay, conflict marks, publish-all with a draft badge, week⇄fortnight, and
 * the template quick-create with colour swatches. What did not: the private
 * department and job dropdowns (W4 — department comes from `wf_context` now,
 * and the job filter was a second unsynchronized context), the `⚠️` emoji, the
 * FontAwesome icons, the eleven hand-picked 2013 hexes, and `target:"current"`
 * on a shift card, which replaced the whole cockpit with a form and no way back
 * (W5).
 *
 * Later work packages hang off the same read call: the stats strip (WP-3), the
 * coverage overlay (WP-4) and the edit-time warnings (WP-5).
 *
 * P3 note: the component takes an `embedded` prop (W17) so Mission Control can
 * host it as a lens without a fork — `embedded` suppresses ONLY the chrome a
 * host would own (its own title row and `<WfContextBar/>`), never a facade call.
 */
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
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
        "*": true,
    };
    static defaultProps = { embedded: false };

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
            // copy week
            copyOpen: false,
            copying: false,
            // person drawer
            person: null,
            personLoading: false,
            drawerHidden: !!this.ctxSvc.state.personId,
            publishing: false,
            // budget dialog (WP-3)
            budgetOpen: false,
            budgetValue: "",
            budgetSaving: false,
        });

        // Stable handler identities — a fresh inline arrow makes OWL treat the
        // child's props as changed and remount it, restarting its onWillStart.
        this._h = {
            onOpenProfile: () => this.openProfile(),
        };

        const off = this.ctxSvc.onChange(() => this.load());
        onWillUnmount(off);

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 14) { return ic(n, s); }

    // -------------------------------------------------------------- span
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
    }

    closeCreate() { this.state.create = null; }

    async createShift(templateId) {
        const c = this.state.create;
        if (!c || this.state.creating) { return; }
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

    openCopy() { this.state.copyOpen = true; }
    closeCopy() { this.state.copyOpen = false; }

    async doCopy() {
        if (this.state.copying) { return; }
        this.state.copying = true;
        try {
            const n = await this.orm.call(MODEL, "copy_week", [
                this.wf.weekStart, this.nextSpanStart,
                this.wf.departmentId || false,
            ]);
            this.state.copyOpen = false;
            this.notif.add(_t("%s shifts copied forward.", n), { type: "success" });
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
