/** @odoo-module **/
/**
 * `pb_comp_ben_paycal` — the Payroll calendar lens on the Pay Run hub.
 *
 * THE HERO IS THE COUNTDOWN. Every other lens on this hub answers "what is in
 * front of me"; this one answers "how long have I got", which is the question
 * an officer actually has on a Tuesday. So the biggest thing on the screen is a
 * number of days, and the year strip underneath is the context for it.
 *
 * THE SWITCH SAYS WHICH WAY IT IS SET (R54). Reminders ship OFF, and a screen
 * that does not say so is a screen somebody reports as broken. The banner says
 * it, with the number the nightly job would have sent.
 *
 * R1 — OWL reserves `lt`/`gt`/`lte`/`gte`/`and`/`or`/`not`/`in` as operators, so
 * no `t-as` variable here is named any of those; the month loop is `mo`.
 * R2 — JavaScript has no implicit string concatenation; every sentence in this
 * file is one expression.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbPaycalBoard extends Component {
    static template = "pb_comp_ben.PbPaycalBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            why: "",
            canWrite: false,
            remindersOn: false,
            year: new Date().getFullYear(),
            years: [],
            months: [],
            next: null,
            kpis: {},

            open: null,          // the month whose panel is open
            building: false,     // the "build the year" dialog
            build: { cutoff: 25, pay: 1, months: 12, offsets: "5,2,0" },
            busy: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load(year) {
        try {
            const data = await this.orm.call("pb.paycal", "get_board",
                                             [year || this.state.year]);
            Object.assign(this.state, {
                allowed: data.allowed,
                why: data.why || "",
                canWrite: data.can_write,
                remindersOn: data.reminders_on,
                year: data.year || this.state.year,
                years: data.years || [],
                months: data.months || [],
                next: data.next || null,
                kpis: data.kpis || {},
            });
        } catch (e) {
            console.warn("pb_comp_ben: the payroll calendar could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The payroll calendar could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async refresh() { await this.load(this.state.year); }

    async pickYear(year) {
        this.state.open = null;
        await this.load(year);
    }

    // ------------------------------------------------------------- the hero
    /** The countdown sentence, built as ONE expression (R34). */
    get countdown() {
        const n = this.state.next;
        if (!n) { return _t("Nothing is planned ahead — build the year to see a countdown here."); }
        const d = n.days_left;
        if (d === 0) { return _t("Changes close today."); }
        if (d === 1) { return _t("Changes close tomorrow."); }
        return _t("%s days until changes close for %s.", d, n.label);
    }

    get hasMonths() { return (this.state.months || []).length > 0; }

    // ------------------------------------------------------------ the panel
    toggleMonth(mo) {
        this.state.open = (this.state.open && this.state.open.id === mo.id)
            ? null : mo;
    }

    isOpen(mo) { return !!(this.state.open && this.state.open.id === mo.id); }

    async setState(mo, next) {
        if (!this.state.canWrite) { return; }
        this.state.busy = true;
        try {
            await this.orm.call("pb.paycal", "set_state", [mo.id, next]);
            await this.load(this.state.year);
            this.notif.add(next === "closed"
                ? _t("This month is closed to changes.")
                : _t("This month is open again."), { type: "success" });
        } catch (e) {
            this.notif.add(e.message ? e.message.data ? e.message.data.message
                : e.message : _t("That could not be saved."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------- build the year
    openBuild() {
        this.state.build = { cutoff: 25, pay: 1, months: 12, offsets: "5,2,0" };
        this.state.building = true;
    }

    closeBuild() { this.state.building = false; }

    onBuildField(field, ev) { this.state.build[field] = ev.target.value; }

    async confirmBuild() {
        this.state.busy = true;
        try {
            const b = this.state.build;
            const res = await this.orm.call("pb.paycal", "build_year", [
                parseInt(b.cutoff, 10), parseInt(b.pay, 10), false,
                parseInt(b.months, 10), b.offsets,
            ]);
            this.state.building = false;
            await this.load(this.state.year);
            const made = res.created || 0;
            const skipped = res.skipped || 0;
            this.notif.add(
                made === 1
                    ? _t("1 month added. %s were already there.", skipped)
                    : _t("%s months added. %s were already there.", made, skipped),
                { type: "success" });
        } catch (e) {
            this.notif.add(
                (e.message && e.message.data && e.message.data.message)
                || _t("The year could not be built."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // -------------------------------------------------------- the reminders
    async toggleReminders() {
        this.state.busy = true;
        try {
            const on = await this.orm.call("pb.paycal", "set_reminders",
                                           [!this.state.remindersOn]);
            this.state.remindersOn = on;
            this.notif.add(on
                ? _t("Reminders are on. People will be emailed before each closing date.")
                : _t("Reminders are off. Nothing will be emailed."),
                { type: "success" });
        } finally {
            this.state.busy = false;
        }
    }

    async runReminders() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.paycal", "run_reminders_now", []);
            await this.load(this.state.year);
            // R46 — no bracketed plurals anywhere a person reads.
            let msg;
            if (!res.enabled) {
                msg = _t("Reminders are switched off. %s would have gone out today.",
                         res.would);
            } else if (res.sent === 1) {
                msg = _t("1 reminder went out.");
            } else {
                msg = _t("%s reminders went out.", res.sent);
            }
            this.notif.add(msg, { type: "info" });
        } catch (e) {
            this.notif.add(_t("That could not be run just now."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openAll() { this.action.doAction("pb_comp_ben.action_pb_payroll_calendar"); }
}

registry.category("actions").add("pb_comp_ben_paycal", PbPaycalBoard);
