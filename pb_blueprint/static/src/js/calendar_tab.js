/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/**
 * Close the loop on payday.
 *
 * Three promises and two preferences. The promises are the day inputs close,
 * the day people are paid, and what happens to something that arrives late —
 * and the payday one is shown as the REAL DATE it lands on next, worked out
 * from the company's own working calendar, because "the second last working
 * day" is a rule and rent is paid on a date.
 *
 * Nothing about a bank account is invented here: the payment currency is the
 * configuration's own and is shown, not chosen, and the bank layouts have their
 * own screen, which this opens with a way back.
 */
export class CalendarTab extends Component {
    static template = "pb_blueprint.CalendarTab";
    static props = {
        configId: { type: Number },
        revision: { type: Number, optional: true },
        reloadKey: { type: Number, optional: true },
        onChanged: { type: Function },
        onRevision: { type: Function },
        onGrid: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            error: "",
            data: null,
            calendar: {},
            payment: {},
            preview: null,
            previewBusy: false,
            busy: false,
            dirty: false,
        });

        onWillStart(async () => {
            await this.load();
            this.state.loading = false;
        });

        onWillUpdateProps(async (next) => {
            if (next.reloadKey !== this.props.reloadKey) await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(reason || _t("The server could not be reached."),
                           { type: "danger" });
            return { ok: false, reason };
        }
    }

    async load() {
        const res = await this.rpc("bp_calendar_data", [this.props.configId]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("The pay calendar could not be loaded.");
            return;
        }
        this.state.error = "";
        this.state.data = res;
        this.state.calendar = { ...res.calendar };
        this.state.payment = { ...res.payment };
        this.state.preview = res.preview;
        this.state.dirty = false;
        if (res.revision !== undefined) this.props.onRevision(res.revision);
    }

    // ==================================================================
    // Reading
    // ==================================================================
    get data() { return this.state.data || {}; }
    get editable() { return !!this.data.editable; }
    get preview() { return this.state.preview; }

    get FLOW() {
        return [
            { key: "inputs", label: _t("Approved inputs"), icon: "inbox" },
            { key: "calc", label: _t("Calculation"), icon: "calculator",
              sub: this.data.cycle_label || "" },
            { key: "review", label: _t("HR and Finance review"), icon: "userCheck" },
            { key: "bank", label: _t("Bank release"), icon: "landmark" },
            { key: "payslip", label: _t("Payslip"), icon: "receipt" },
        ];
    }

    get PAYDAY_RULES() {
        return [
            { value: "second_last_working", label: _t("Second last working day") },
            { value: "last_working", label: _t("Last working day") },
            { value: "fixed", label: _t("A fixed day of the month") },
        ];
    }

    /** The same three shapes as a payday, because it is the same promise. */
    get CUTOFF_RULES() {
        return [
            { value: "before_payday", label: _t("Days before payday") },
            { value: "last_working", label: _t("Last working day") },
            { value: "fixed", label: _t("A fixed day of the month") },
        ];
    }

    get LATE_POLICIES() {
        return [
            { value: "next_cycle", label: _t("Carry it to the next pay run"),
              hint: _t("The amount is paid next time, and the payslip says which run it belongs to.") },
            { value: "off_cycle", label: _t("Approve an off-cycle payment"),
              hint: _t("A separate, approved run pays it before the next ordinary payday.") },
            { value: "reopen", label: _t("Reopen the run"),
              hint: _t("Only with HR and Finance both agreeing. Everything already checked is checked again.") },
        ];
    }

    get BANK_TYPES() {
        return [
            { value: "domestic", label: _t("Domestic bank code") },
            { value: "swift", label: _t("SWIFT / BIC") },
        ];
    }

    get isFixed() { return this.state.calendar.payday_rule === "fixed"; }

    get isCutoffFixed() { return this.state.calendar.cutoff_rule === "fixed"; }

    get isCutoffBefore() {
        return this.state.calendar.cutoff_rule === "before_payday";
    }

    get previewLine() {
        const p = this.preview;
        if (!p) {
            return _t("No working day could be found in that month. Check the company's working calendar.");
        }
        const skipped = [];
        if (p.skipped_weekends) {
            skipped.push(p.skipped_weekends === 1
                ? _t("1 non-working day") : _t("%s non-working days", p.skipped_weekends));
        }
        if (p.skipped_holidays) {
            skipped.push(p.skipped_holidays === 1
                ? _t("1 public holiday") : _t("%s public holidays", p.skipped_holidays));
        }
        if (!skipped.length) {
            return _t("is the next payday in the company calendar.");
        }
        return _t("is the next payday in the company calendar (%s skipped).",
                  skipped.join(_t(" and ")));
    }

    get calendarNote() {
        const p = this.preview;
        if (p && p.has_calendar) {
            return p.calendar_name
                ? _t("Working days come from “%s”.", p.calendar_name) : "";
        }
        return _t("Set the company's working calendar to get an exact date. Saturdays and Sundays only are skipped for now.");
    }

    /**
     * The cut-off in one sentence — the RULE, then the date it lands on.
     *
     * The date is the half that was missing. "Day 28" told nobody which Friday
     * they had to have their overtime in by, and a person choosing 31 found
     * out it was impossible only when the save was refused.
     */
    get cutoffLine() {
        const cal = this.state.calendar;
        if (cal.cutoff_rule === "before_payday") {
            const n = Number(cal.cutoff_days_before) || 0;
            return n === 1
                ? _t("Inputs close one working day before payday.")
                : _t("Inputs close %s working days before payday.", n);
        }
        if (cal.cutoff_rule === "last_working") {
            return _t("Inputs close on the last working day of the month.");
        }
        return _t("Inputs close on the %s of the month, or the working day before it.",
                  this.ordinal(Number(cal.cutoff_day) || 0));
    }

    /** "Wednesday 28 October 2026 — 2 days before payday", or nothing. */
    get cutoffDateLine() {
        const c = this.preview && this.preview.cutoff;
        if (!c) return "";
        const gap = Number(c.days_to_payday) || 0;
        if (gap <= 0) return c.long;
        return gap === 1
            ? _t("%s — the day before payday", c.long)
            : _t("%s — %s days before payday", c.long, gap);
    }

    /** Why the day box stops at 28, said before it is typed into, not after. */
    get cutoffDayNote() {
        return _t("1 to 28, so the day exists in every month — February has no 29th most years, and April has no 31st at all.");
    }

    ordinal(n) {
        const value = Number(n) || 0;
        const rest = value % 100;
        if (rest >= 11 && rest <= 13) return _t("%sth", value);
        return [_t("%sth", value), _t("%sst", value), _t("%snd", value),
                _t("%srd", value)][value % 10] || _t("%sth", value);
    }

    // ==================================================================
    // Changing
    // ==================================================================
    async setCalendar(key, value) {
        this.state.calendar[key] = value;
        this.state.dirty = true;
        // The cut-off keys are in here too: a cut-off set "before payday" is
        // worked out FROM the payday, so changing either one moves both dates
        // and the panel would otherwise show a stale pair.
        if (["payday_rule", "payday_day", "cutoff_rule", "cutoff_day",
             "cutoff_days_before"].includes(key)) {
            await this.refreshPreview();
        }
    }

    onNumber(key, ev) {
        const n = Number(String(ev.target.value).replace(/[\s,]/g, ""));
        if (!Number.isFinite(n)) return;
        this.setCalendar(key, Math.round(n));
    }

    setPayment(key, value) {
        this.state.payment[key] = value;
        this.state.dirty = true;
    }

    async refreshPreview() {
        this.state.previewBusy = true;
        const cal = this.state.calendar;
        const res = await this.rpc("bp_calendar_preview", [
            this.props.configId, false, cal.payday_rule, cal.payday_day,
            { cutoff_rule: cal.cutoff_rule, cutoff_day: cal.cutoff_day,
              cutoff_days_before: cal.cutoff_days_before }]);
        this.state.previewBusy = false;
        if (res && res.ok) this.state.preview = res.preview;
    }

    get canSave() { return this.editable && this.state.dirty && !this.state.busy; }

    async save() {
        if (!this.canSave) return;
        this.state.busy = true;
        const res = await this.rpc("bp_calendar_save", [
            this.props.configId, { ...this.state.calendar },
            { ...this.state.payment }, this.props.revision]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The calendar could not be saved."),
                           { type: "danger", sticky: true });
            if (res && res.conflict) this.props.onChanged({ conflict: true });
            return;
        }
        this.state.calendar = { ...res.calendar };
        this.state.payment = { ...res.payment };
        this.state.preview = res.preview;
        this.state.dirty = false;
        if (res.revision !== undefined) this.props.onRevision(res.revision);
        this.notif.add(_t("The pay calendar is saved."), { type: "success" });
    }

    // ==================================================================
    // The door to the bank layouts
    // ==================================================================
    get hasPayDelivery() {
        return !!(this.data.doors && this.data.doors.pay_delivery)
            && registry.category("actions").contains("pb_pay_delivery");
    }

    async openPayDelivery() {
        if (this.state.dirty) await this.save();
        const res = await this.rpc("bp_pay_delivery_action", [this.props.configId]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("Bank file layouts could not be opened."),
                           { type: "warning" });
            return;
        }
        this.action.doAction(res.action, { clearBreadcrumbs: true });
    }

    onKeydown(ev) {
        // Enter inside this tab belongs to the field it was pressed in, not to
        // the journey's "continue" (BP20).
        if (ev.key === "Enter") ev.stopPropagation();
    }
}
