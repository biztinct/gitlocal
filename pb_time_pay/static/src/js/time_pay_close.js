/** @odoo-module **/
/**
 * <TimePayClose/> — the "Time into pay" section of the weekly Close.
 *
 * Registered into the Close lens's section slot (`pb_close_lens_section`), so
 * the lens learns nothing about overtime suggestions or late minutes: it hands
 * every section the board's payload and a way to re-read it.
 *
 * MOUNT HOOKS READ, CLICK HANDLERS WRITE (W21.1, the Close lens's own rule).
 * This component has NO read of its own at all — its data is the board's
 * `time_pay` key — and every server write below is reachable only from a
 * `t-on-click`. After a write it asks the lens to re-read (`onChanged`).
 *
 * The server rebuilds every set it acts on from the same read the board made
 * (keys, never hours or minutes from the browser), checks the decider gate,
 * and refuses per row — own records, locked days, minutes already paid — with
 * the reason shown on the surface rather than in a toast that fades.
 */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.time.pay";

export class TimePayClose extends Component {
    static template = "pb_time_pay.TimePayClose";
    static props = {
        data: { type: Object, optional: true },
        ctx: { type: Object, optional: true },
        onChanged: { type: Function, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            busy: false,
            pickS: {},          // suggestion key -> true
            pickL: {},          // late row key -> true
            choice: "pay",      // what "Accept" gives: pay it / time off
            note: null,         // {mode: 'excuse'|'dismiss', keys, title}
            noteText: "",
            result: null,       // what the last action did, kept on screen
            showFile: false,
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    // ------------------------------------------------------------ accessors
    get d() { return (this.props.data && this.props.data.time_pay) || null; }
    get sugg() { return (this.d && this.d.suggestions) || []; }
    get late() { return (this.d && this.d.late) || []; }
    get ls() { return (this.d && this.d.late_stats) || {}; }
    get canDecide() { return !!(this.d && this.d.can_decide); }
    get fileSchemes() { return (this.d && this.d.file_schemes) || []; }
    get fileMonth() { return (this.d && this.d.file_month) || {}; }

    _ctx() {
        const c = this.props.ctx || {};
        return {
            department_id: c.departmentId || false,
            week_start: c.weekStart || false,
            search: c.search || "",
        };
    }

    hours(v) {
        return Number(v || 0).toLocaleString(undefined, {
            minimumFractionDigits: 0, maximumFractionDigits: 2 });
    }

    hoursLabel(v) { return _t("%s h", this.hours(v)); }
    whyLine(row) {
        return row.expected
            ? _t("worked %(worked)s h, expected %(expected)s h", {
                worked: this.hours(row.worked), expected: this.hours(row.expected) })
            : _t("worked %s h", this.hours(row.worked));
    }
    wasLabel(row) { return _t("was %s", row.decided_minutes); }
    moreLabel(shown, total) {
        return _t("Showing the first %(shown)s of %(total)s. Narrow the department or the search to see the rest.", { shown, total });
    }
    get graceLabel() {
        const d = this.d || {};
        return _t("Counted from the expected time once past the grace minutes (%(late)s min late, %(early)s min early).", {
            late: d.grace_in, early: d.grace_out });
    }
    get showFiguresLabel() {
        return _t("Show the figures for %s", this.fileMonth.month || "");
    }
    get skippedLabel() {
        const n = ((this.state.result && this.state.result.skipped) || []).length;
        return _t("%s could not be done:", n);
    }

    suggActionable(row) { return this.canDecide && !row.locked && !row.own; }
    lateActionable(row) {
        return this.canDecide && !row.locked && !row.own && !row.paid;
    }
    lateNeedsDecision(row) {
        return (row.state === "open" && row.minutes > 0) || (row.changed && !row.paid);
    }

    lateStateLabel(row) {
        if (row.paid) { return _t("Paid"); }
        if (row.changed) { return _t("Changed since decided"); }
        if (row.state === "confirmed") { return _t("Confirmed"); }
        if (row.state === "excused") { return _t("Excused"); }
        return _t("To decide");
    }
    lateStateTone(row) {
        if (row.paid) { return "slate"; }
        if (row.changed) { return "amber"; }
        if (row.state === "confirmed") { return "indigo"; }
        if (row.state === "excused") { return "green"; }
        return "amber";
    }

    get pickedS() { return Object.keys(this.state.pickS).filter((k) => this.state.pickS[k]); }
    get pickedL() { return Object.keys(this.state.pickL).filter((k) => this.state.pickL[k]); }

    get suggSelectable() { return this.sugg.filter((r) => this.suggActionable(r)); }
    get lateSelectable() { return this.late.filter((r) => this.lateActionable(r)); }

    get allSPicked() {
        const rows = this.suggSelectable;
        return rows.length > 0 && rows.every((r) => this.state.pickS[r.key]);
    }
    get allLPicked() {
        const rows = this.lateSelectable;
        return rows.length > 0 && rows.every((r) => this.state.pickL[r.key]);
    }

    get glance() {
        const d = this.d || {};
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "sugg", n: d.suggestions_total || 0,
              label: _t("Overtime suggestions"), tone: tone(d.suggestions_total, "amber"), run: null },
            { key: "open", n: this.ls.open || 0,
              label: _t("Late or early to decide"), tone: tone(this.ls.open, "amber"), run: null },
            { key: "conf", n: this.ls.minutes_confirmed || 0,
              label: _t("Minutes confirmed"), tone: "", run: null },
            { key: "exc", n: this.ls.excused || 0,
              label: _t("Excused"), tone: "", run: null },
        ];
    }

    // ================================================================ picks
    togglePickS(row) {
        if (!this.suggActionable(row)) { return; }
        this.state.pickS[row.key] = !this.state.pickS[row.key];
    }
    togglePickL(row) {
        if (!this.lateActionable(row)) { return; }
        this.state.pickL[row.key] = !this.state.pickL[row.key];
    }
    pickAllS() {
        const on = !this.allSPicked;
        for (const r of this.suggSelectable) { this.state.pickS[r.key] = on; }
    }
    pickAllL() {
        const on = !this.allLPicked;
        for (const r of this.lateSelectable) { this.state.pickL[r.key] = on; }
    }
    setChoice(choice) { this.state.choice = choice; }
    toggleFile() { this.state.showFile = !this.state.showFile; }
    dismissResult() { this.state.result = null; }

    // ================================================================ writes
    // Everything below is reachable ONLY from a t-on-click (W21.1).
    async accept(keys) {
        if (!keys.length || this.state.busy) { return; }
        await this._run(async () => {
            const res = await this.orm.call(MODEL, "accept_suggestions", [keys], {
                choice: this.state.choice, ...this._ctx() });
            this.state.pickS = {};
            const n = (res && res.created) || 0;
            this.state.result = {
                title: n === 1 ? _t("1 overtime request sent for approval.")
                    : _t("%s overtime requests sent for approval.", n),
                skipped: (res && res.skipped) || [] };
        });
    }
    acceptOne(row) { return this.accept([row.key]); }
    acceptPicked() { return this.accept(this.pickedS); }

    async decide(keys, decision, note) {
        if (!keys.length || this.state.busy) { return; }
        await this._run(async () => {
            const res = await this.orm.call(MODEL, "decide_late", [keys, decision], {
                note: note || false, ...this._ctx() });
            this.state.pickL = {};
            const n = (res && res.decided) || 0;
            this.state.result = {
                title: decision === "confirmed"
                    ? (n === 1 ? _t("1 row confirmed for pay.") : _t("%s rows confirmed for pay.", n))
                    : (n === 1 ? _t("1 row excused.") : _t("%s rows excused.", n)),
                skipped: (res && res.skipped) || [] };
        });
    }
    confirmOne(row) { return this.decide([row.key], "confirmed"); }
    confirmPicked() { return this.decide(this.pickedL, "confirmed"); }

    openExcuse(keys) {
        if (!keys.length) { return; }
        this.state.note = { mode: "excuse", keys, title: keys.length === 1
            ? _t("Excuse these minutes") : _t("Excuse %s rows", keys.length) };
        this.state.noteText = "";
    }
    excuseOne(row) { this.openExcuse([row.key]); }
    excusePicked() { this.openExcuse(this.pickedL); }

    openDismiss(row) {
        this.state.note = { mode: "dismiss", keys: [row.key],
            title: _t("Not overtime") };
        this.state.noteText = "";
    }
    onNote(ev) { this.state.noteText = ev.target.value; }
    cancelNote() { this.state.note = null; this.state.noteText = ""; }

    async confirmNote() {
        const n = this.state.note;
        if (!n || this.state.busy) { return; }
        const text = this.state.noteText.trim();
        this.state.note = null;
        this.state.noteText = "";
        if (n.mode === "excuse") {
            await this.decide(n.keys, "excused", text);
            return;
        }
        await this._run(async () => {
            await this.orm.call(MODEL, "dismiss_suggestion", [n.keys[0]], {
                note: text || false, ...this._ctx() });
            this.notif.add(_t("Marked as not overtime."), { type: "success" });
        });
    }

    async _run(fn) {
        this.state.busy = true;
        try {
            await fn();
            if (this.props.onChanged) { await this.props.onChanged(); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || (e && e.message)
                || _t("Something went wrong."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("pb_close_lens_section").add("time_pay", {
    Component: TimePayClose,
}, { sequence: 10 });
