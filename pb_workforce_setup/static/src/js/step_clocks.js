/** @odoo-module **/
/**
 * Step 6 — "How do people clock in?" (WFSETUP P4).
 *
 * One card per clock with an honest state (sending clock-ins / connected,
 * but clock-ins are switched off / not heard from since … / waiting for IT /
 * needs attention / switched off), "Switch clock-ins on" for a manager behind
 * an inline confirm (P6), "Copy setup link for IT" (a new
 * 5-day link from the clock's own invitation; the link is built exactly as
 * the clock's own setup page builds it), "Add a clock", the people who have
 * no clock number, and only those ways without a machine that exist here.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { deserializeDateTime } from "@web/core/l10n/dates";
import { MODEL, icon, errorText, fmtNum } from "./setup_util";

const { DateTime } = luxon;

export class StepClocks extends Component {
    static template = "pb_workforce_setup.StepClocks";
    static props = { studio: Object, data: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon = icon;
        this.root = useRef("root");
        this.state = useState({
            loading: true,
            error: "",
            clk: null,
            adding: false,
            name: "",
            where: "",
            addError: "",
            busy: false,
            replaceAsk: null,          // card key asking "replace the link?"
            linkShown: {},             // card key -> link to select by hand (clipboard refused)
            fresh: null,               // card key just added (highlight)
            confirming: false,
            switchAsk: null,           // card key asking "switch clock-ins on?"
        });
        useEffect(() => {
            if (this.state.adding) {
                this.root.el?.querySelector(".pbws-addclk input")?.focus();
            }
        }, () => [this.state.adding]);
        // the inline confirm takes focus when it opens (its own button) and
        // gives it back to "Switch clock-ins on" when it closes (after the
        // patch: the button is drawn again only then)
        useEffect(() => {
            if (this.state.switchAsk) {
                this.root.el?.querySelector(`[data-switch-ask="${this.state.switchAsk}"] .pbws-btn--out`)?.focus();
            } else if (this.switchBack) {
                const key = this.switchBack;
                this.switchBack = null;
                this.root.el?.querySelector(`[data-switch="${key}"]`)?.focus();
            }
        }, () => [this.state.switchAsk]);
        onWillStart(() => this.load());
        // the bar lives in the studio's state: setting it before this step is
        // mounted re-renders the studio, which makes a NEW step whose
        // willStart loads again — an endless loop (found in the walk)
        onMounted(() => {
            this.mounted = true;
            this.syncBar();
        });
        onWillUnmount(() => {
            this.mounted = false;
            this.props.studio.setBar("clocks", null);
        });
    }

    async load() {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.state.error = "";
        try {
            const clk = await this.orm.call(MODEL, "clocks", []);
            if (seq === this.seq) {
                this.state.clk = clk;
                this.syncBar();
            }
        } catch (e) {
            if (seq === this.seq) {
                this.state.error = errorText(e);
            }
        } finally {
            if (seq === this.seq) {
                this.state.loading = false;
            }
        }
    }
    retry() {
        this.state.loading = true;
        this.load();
    }

    syncBar() {
        if (!this.mounted) {
            return;
        }
        const c = this.state.clk;
        if (c && c.can_edit && !c.confirmed) {
            const n = c.later;
            this.props.studio.setBar("clocks", {
                label: !n ? _t("Clocks are fine. Confirm")
                    : n === 1 ? _t("Continue, finish 1 clock later") : _t("Continue, finish %s clocks later", fmtNum(n)),
                icon: n ? "arrowRight" : "check",
                busy: this.state.confirming,
                run: () => this.confirm(),
            });
        } else {
            this.props.studio.setBar("clocks", null);
        }
    }

    // ------------------------------------------------------------ reading
    get clk() { return this.state.clk; }
    get canEdit() { return !!this.clk?.can_edit; }
    get rows() { return this.clk?.clocks || []; }
    get options() { return this.clk?.options || []; }

    chipClass(row) {
        return {
            ok: "pbws-chip pbws-chip--ok",
            held: "pbws-chip pbws-chip--warn",
            quiet: "pbws-chip pbws-chip--warn",
            waiting: "pbws-chip pbws-chip--warn",
            attention: "pbws-chip pbws-chip--err",
            off: "pbws-chip",
        }[row.state] || "pbws-chip";
    }
    chipIcon(row) {
        return { ok: "check", held: "pause", quiet: "hourglass", waiting: "clock", attention: "triangleAlert", off: "powerOff" }[row.state] || "clock";
    }
    chipText(row) {
        switch (row.state) {
            case "ok": return _t("Sending clock-ins");
            case "held": return _t("Connected, but clock-ins are switched off");
            case "quiet": return row.last_heard ? _t("Not heard from since %s", this.since(row.last_heard)) : _t("Not heard from yet");
            case "waiting": return _t("Waiting for IT");
            case "attention": return _t("Needs attention");
            default: return _t("Switched off");
        }
    }
    kindIcon(row) { return row.kind === "machine" ? "scan" : "monitor"; }
    kindLabel(row) { return row.kind === "machine" ? _t("Clock that calls in by itself") : _t("Clock read by a PC"); }

    dt(value) {
        try {
            return value ? deserializeDateTime(value) : null;
        } catch {
            return null;
        }
    }
    ago(value) {
        const d = this.dt(value);
        return d ? d.toRelative() : "";
    }
    day(value) {
        const d = this.dt(value);
        return d ? d.toFormat("ccc d LLL") : "";
    }
    /** "14:05" today, "Mon 23 Nov" before (P6: a PC is "not heard from"
     *  after an hour, so the day alone would read wrong). */
    since(value) {
        const d = this.dt(value);
        if (!d) {
            return "";
        }
        return d.hasSame(DateTime.now(), "day") ? d.toFormat("HH:mm") : d.toFormat("ccc d LLL");
    }
    heardLine(row) { return _t("Last heard from %s", this.ago(row.last_heard)); }
    todayLine(row) {
        return row.today === 1 ? _t("1 clock-in received today") : _t("%s clock-ins received today", fmtNum(row.today));
    }
    pendingLine(row) {
        return row.pending === 1 ? _t("1 record is waiting on the PC to be sent.")
            : _t("%s records are waiting on the PC to be sent.", fmtNum(row.pending));
    }
    inviteLine(row) {
        return _t("A setup link was made. It works until %s.", this.day(row.invite_until));
    }
    quietLine(row) {
        return row.last_heard
            ? _t("Nothing received since %s. Ask your IT person to check that the PC beside the clock is on.", this.day(row.last_heard))
            : _t("Nothing received yet.");
    }
    // ------------------------------------------------------------ the switch (P6)
    /** A connected PC whose clock-ins are switched off. */
    isOff(row) { return row.switch && !row.sending && ["held", "quiet", "attention"].includes(row.state); }
    canSwitch(row) { return !!row.can_switch && this.isOff(row); }
    switchTitle(row) { return _t("Switch clock-ins on for %s", row.name); }
    askLine(row) { return this.isOff(row) && !row.can_switch; }
    askSwitch(row) {
        if (!this.canSwitch(row) || this.state.busy) {
            return;
        }
        this.state.switchAsk = row.key;
    }
    keepSwitch() {
        // focus goes back to the button that opened the question (effect above)
        this.switchBack = this.state.switchAsk;
        this.state.switchAsk = null;
    }
    onSwitchKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.keepSwitch();
        }
    }
    async switchOn(row) {
        if (!this.canSwitch(row) || this.state.busy) {
            return;
        }
        this.state.busy = true;
        let res;
        try {
            res = await this.orm.call(MODEL, "clock_switch_on", [row.id]);
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
            return;
        } finally {
            this.state.busy = false;
        }
        this.state.switchAsk = null;
        this.state.fresh = row.key;
        await Promise.all([this.load(), this.props.studio.refresh()]);
        this.props.studio.toast(res.summary);
        // the question is gone: focus stays on that clock's card
        await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve)));
        this.root.el?.querySelector(`[data-card="${row.key}"] .pbws-dev-b button`)?.focus();
    }

    canLink(row) { return this.canEdit && row.kind === "pc" && !["off", "ok", "held"].includes(row.state); }
    cardClass(row) { return `pbws-card pbws-dev is-${row.state}${this.state.fresh === row.key ? " is-fresh" : ""}`; }

    get noNumberLine() {
        const n = this.clk.no_number;
        return n === 1 ? _t("1 person has no clock number") : _t("%s people have no clock number", fmtNum(n));
    }
    option(key) {
        return {
            phone: { icon: "smartphone", title: _t("Phone clock-in"), text: _t("People tap in and out from My Payobook on their phone.") },
            import: { icon: "upload", title: _t("Upload a file"), text: _t("A spreadsheet export from any clock, on the Time screen.") },
            grid: { icon: "pencil", title: _t("Supervisor enters hours"), text: _t("Typed in on the weekly sheet.") },
        }[key];
    }
    optionState(opt) {
        if (opt.key !== "phone") {
            return "";
        }
        return opt.on ? _t("On for this company") : _t("Off for this company");
    }

    // ------------------------------------------------------------ the link
    async copyLink(row, replace = false) {
        if (!this.canEdit || this.state.busy) {
            return;
        }
        if (row.invite_until && !replace) {
            this.state.replaceAsk = row.key;
            return;
        }
        this.state.replaceAsk = null;
        this.state.busy = true;
        let res;
        try {
            res = await this.orm.call(MODEL, "clock_invite", [row.id]);
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
            return;
        } finally {
            this.state.busy = false;
        }
        // exactly as the clock's own setup page builds it (pb_clock setup.js)
        const link = location.origin + "/clock-bridge/setup#" + res.token;
        let copied = false;
        try {
            if (navigator.clipboard && window.isSecureContext !== false) {
                await navigator.clipboard.writeText(link);
                copied = true;
            }
        } catch {
            copied = false;
        }
        if (copied) {
            delete this.state.linkShown[row.key];
            this.props.studio.toast(_t("Setup link copied. It works for 5 days."));
        } else {
            this.state.linkShown[row.key] = link;
            this.props.studio.toast(_t("Copy the selected link for your IT person. It works for 5 days."), { kind: "info" });
        }
        await this.load();
        if (!copied) {
            // after the card has drawn the box: select the link for the person
            await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve)));
            const input = this.root.el?.querySelector(`[data-link="${row.key}"]`);
            input?.focus();
            input?.select();
        }
    }
    keepLink() { this.state.replaceAsk = null; }
    selectLink(ev) { ev.target.select(); }

    async details(row) {
        if (row.kind === "machine") {
            return this.action.doAction("pb_clock.action_pb_clock_lens");
        }
        try {
            const act = await this.orm.call(MODEL, "clock_details", [row.id]);
            await this.action.doAction(act);
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
        }
    }

    // ------------------------------------------------------------ add a clock
    startAdd() {
        this.state.adding = true;
        this.state.name = "";
        this.state.where = "";
        this.state.addError = "";
    }
    cancelAdd() { this.state.adding = false; }
    onAddKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.add();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.cancelAdd();
        }
    }
    async add() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.addError = "";
        try {
            const row = await this.orm.call(MODEL, "clock_add", [this.state.name, this.state.where]);
            this.state.adding = false;
            this.state.fresh = row.key;
            await this.load();
            this.props.studio.refresh();
            this.props.studio.toast(_t("“%s” is added. Copy its setup link for your IT person.", row.name));
        } catch (e) {
            this.state.addError = errorText(e);
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ elsewhere
    goNoNumber() {
        this.props.studio.goFiltered("people", "nonumber");
    }
    openOption(opt) {
        if (opt.key === "phone") {
            return this.action.doAction("hr_attendance.action_hr_attendance_settings");
        }
        return this.action.doAction("pb_mission.action_pb_workforce", {
            additionalContext: { pb_shell_lens: "time", pb_lens: opt.key === "import" ? "import" : "grid" },
        });
    }

    async confirm() {
        if (this.state.confirming) {
            return;
        }
        this.state.confirming = true;
        this.syncBar();
        try {
            const res = await this.orm.call(MODEL, "confirm_clocks", []);
            await this.load();
            await this.props.studio.refresh();
            this.props.studio.toast(res.summary);
            this.props.studio.go("live");
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
        } finally {
            this.state.confirming = false;
            this.syncBar();
        }
    }
}
