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

    get cutoffLine() {
        const day = Number(this.state.calendar.cutoff_day) || 0;
        return _t("Anything approved after the %s of the month waits for the next run.",
                  this.ordinal(day));
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
        if (key === "payday_rule" || key === "payday_day") {
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
        const res = await this.rpc("bp_calendar_preview", [
            this.props.configId, false, this.state.calendar.payday_rule,
            this.state.calendar.payday_day]);
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
