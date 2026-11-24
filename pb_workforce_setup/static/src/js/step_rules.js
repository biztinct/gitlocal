/** @odoo-module **/
/**
 * Step 4 — "What happens when someone is late or stays on?" (WFSETUP P3).
 *
 * Every rule is a sentence with its numbers highlighted and editable in
 * place. The values live in the studio (`studio.rules`) so the pay example on
 * the right works them out on the server WHILE you type, before they are
 * saved; a change is saved 600 ms after the last keystroke ("Saving… /
 * Saved"), and the leave guard saves anything pending before the step
 * changes. No sums happen here: the only maths is the real engine on the
 * server.
 *
 * Late lines: a line's "to" drives the next line's "from", so they can never
 * leave a gap; the last line is always "N minutes late or more". Overtime
 * starts at a clock time on each shift (owner ruling R5). The approval line is
 * a fixed sentence (R6).
 *
 * Read-only states: rules in use ("Change the rules" makes a new version),
 * several rule sets ("advanced"), and attendance officers.
 */
import { Component, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, errorText, deepClone, toMin, spanOf, fmtNum, dec } from "./setup_util";

const AUTOSAVE_MS = 600;

export class StepRules extends Component {
    static template = "pb_workforce_setup.StepRules";
    static props = { studio: Object, data: Object, rules: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon = icon;
        this.root = useRef("root");
        this.state = useState({
            group: "worker",
            mark: null,             // "saving" | "saved"
            error: "",
            problems: [],
            busy: false,
            discardAsk: false,
            drafting: {},           // key -> true while a number box is half typed ("0.")
        });
        this.editSeq = 0;
        this.savedSeq = 0;
        this.timer = null;
        this.inflight = null;
        this.again = false;
        this.unguard = this.props.studio.addGuard(() => this.flush());
        this.unconfirm = this.props.studio.onConfirm(() => this.confirm());
        onWillUnmount(() => {
            this.unguard();
            this.unconfirm();
            clearTimeout(this.markTimer);
            clearTimeout(this.askTimer);
            if (this.timer) {
                clearTimeout(this.timer);
                this.timer = null;
                this.save();                  // never lose the last keystrokes
            }
        });
    }

    // ------------------------------------------------------------ reading
    get r() { return this.props.rules; }
    get canEdit() { return !!this.r?.can_edit; }
    get canManage() { return !!this.props.data.can_edit; }
    get lines() { return this.r.late[this.state.group] || []; }
    isLast(i) { return i === this.lines.length - 1; }
    nf(n) { return fmtNum(n); }
    /** A read-only rate or hours value in the user's decimal mark (P5c). */
    df(v) { return dec(v, 2); }
    get groupCounts() {
        const p = this.r.people || {};
        return { worker: p.worker || 0, manager: p.manager || 0 };
    }
    groupLabel(key) {
        return key === "manager" ? _t("Managers") : _t("Workers");
    }
    get groupHint() {
        const n = this.groupCounts[this.state.group];
        if (this.state.group === "manager") {
            return n === 1 ? _t("1 person has the Manager late rule.") : _t("%s people have the Manager late rule.", fmtNum(n));
        }
        return n === 1 ? _t("1 person has the Worker late rule.") : _t("%s people have the Worker late rule.", fmtNum(n));
    }
    get noLines() { return !this.lines.length; }
    get noLinesText() {
        return this.state.group === "manager" ? _t("Managers have no late lines yet.") : _t("Workers have no late lines yet.");
    }
    lineLabel(i, part) {
        const n = i + 1;
        return {
            from: _t("Line %s: from how many minutes late", n),
            to: _t("Line %s: up to how many minutes late", n),
            hours: _t("Line %s: hours taken off", n),
        }[part];
    }
    removeLabel(i) { return _t("Remove line %s", i + 1); }
    get peopleLine() {
        const p = this.r.people || {};
        const company = this.props.data.company.name;
        if (!p.total) {
            return _t("These rules will apply to everyone in %s.", company);
        }
        return _t("These rules apply to everyone in %(company)s: %(n)s people, %(w)s with the Worker late rule and %(m)s with the Manager one.", {
            company, n: fmtNum(p.total), w: fmtNum(p.worker || 0), m: fmtNum(p.manager || 0),
        });
    }
    get inUseLine() {
        const p = this.r.people || {};
        return p.with_rules === 1
            ? _t("1 person is paid by them. To change them, make a new version: these stay in use until you confirm it.")
            : _t("%s people are paid by them. To change them, make a new version: these stay in use until you confirm it.", fmtNum(p.with_rules || 0));
    }

    // ------------------------------------------------------------ checks while typing
    /** The first problem in the late lines of a group, as a sentence. */
    lineProblem(group) {
        const lines = this.r.late[group] || [];
        for (let i = 0; i < lines.length; i++) {
            const l = lines[i];
            if (!(Number.isInteger(l.from) && l.from >= 1)) {
                return { i, part: "from", text: _t("A late line starts at 1 minute or more.") };
            }
            if (i < lines.length - 1 && !(Number.isInteger(l.to) && l.to >= l.from)) {
                return { i, part: "to", text: _t("Each late line must end at or after the minute it starts.") };
            }
            if (!(Number.isFinite(l.hours) && l.hours >= 0 && l.hours <= 24 && Math.abs(l.hours * 4 - Math.round(l.hours * 4)) < 1e-9)) {
                return { i, part: "hours", text: _t("Hours taken off are a number from 0 to 24, in quarter hours.") };
            }
        }
        return null;
    }
    get problemHere() { return this.lineProblem(this.state.group); }
    bad(i, part) {
        if (this.state.drafting[`${this.state.group}-${i}-${part}`]) {
            return true;
        }
        const p = this.problemHere;
        return !!(p && p.i === i && p.part === part);
    }
    typing(key) { return !!this.state.drafting[key]; }
    shiftProblem(line) {
        const start = toMin(line.start);
        const span = spanOf(line.start, line.end);
        const ot = toMin(line.overtime_from);
        const brk = toMin(line.break_start);
        if (start === null || ot === null || brk === null || !span) {
            return _t("Use a time like 08:30.");
        }
        const otAt = (ot - start + 1440) % 1440;
        if (!(otAt > 0 && otAt <= span)) {
            return _t("Overtime must start after the shift starts and no later than it ends.");
        }
        if ((brk - start + 1440) % 1440 + (line.break_minutes || 0) > span) {
            return _t("The unpaid break must start after the shift starts and end before it ends.");
        }
        return "";
    }
    rateProblem(key) {
        const v = this.r.rates[key];
        if (key === "night") {
            return Number.isInteger(v) && v >= 0 && v <= 500 ? "" : _t("Night work extra is a percentage from 0 to 500.");
        }
        return Number.isInteger(v) && v >= 100 && v <= 1000 ? "" : _t("An overtime rate is a percentage from 100 to 1000.");
    }
    clockProblem(key) {
        const v = this.r.clock[key];
        return Number.isFinite(v) && v >= 0 && v <= 6 ? "" : _t("Clock-ins and clock-outs are counted up to 6 hours before or after a shift.");
    }
    get nightProblem() {
        const n = this.r.night;
        if (toMin(n.from) === null || toMin(n.to) === null) {
            return _t("Use a time like 08:30.");
        }
        return n.from === n.to ? _t("Night work must start and end at different times.") : "";
    }
    /** Everything wrong on the screen right now (nothing is saved meanwhile). */
    get problemsNow() {
        if (!this.r) {
            return [];
        }
        const out = [];
        if (Object.keys(this.state.drafting).length) {
            out.push(_t("Finish typing the number in the box marked in red."));
        }
        for (const g of ["worker", "manager"]) {
            const p = this.lineProblem(g);
            if (p) {
                out.push(p.text);
            }
        }
        for (const line of this.r.shifts) {
            const p = this.shiftProblem(line);
            if (p) {
                out.push(`${line.name}: ${p}`);
            }
        }
        for (const key of ["normal", "rest_day", "holiday", "night"]) {
            const p = this.rateProblem(key);
            if (p) {
                out.push(p);
            }
        }
        if (this.nightProblem) {
            out.push(this.nightProblem);
        }
        for (const key of ["before", "after"]) {
            const p = this.clockProblem(key);
            if (p) {
                out.push(p);
            }
        }
        return [...new Set(out)];
    }

    // ------------------------------------------------------------ editing
    /** The number in a box, or `undefined` while it is half typed or empty
     *  ("0." reads as "" in a number box): then the stored value is left
     *  alone — writing it back would wipe what the person is typing — and the
     *  box is marked until it holds a number again. */
    num(ev, key) {
        const raw = String(ev.target.value ?? "").trim().replace(",", ".");
        const value = raw === "" ? NaN : Number(raw);
        if (!Number.isFinite(value)) {
            this.state.drafting[key] = true;
            return undefined;
        }
        delete this.state.drafting[key];
        return value;
    }
    pending() {
        // a half-typed box: nothing is saved and the example keeps its answer
        this.props.studio.setRulesInvalid(true);
        this.props.studio.setRulesBusy(true);
        clearTimeout(this.timer);
        this.timer = null;
        this.state.mark = null;
    }
    setGroup(key) {
        this.state.group = key;
    }
    clearDrafting() {
        for (const k of Object.keys(this.state.drafting)) {
            delete this.state.drafting[k];
        }
    }
    onFrom(i, ev) {
        const v = this.num(ev, `${this.state.group}-${i}-from`);
        if (v === undefined) {
            return this.pending();
        }
        this.lines[i].from = Math.round(v);
        this.edited();
    }
    onTo(i, ev) {
        const v = this.num(ev, `${this.state.group}-${i}-to`);
        if (v === undefined) {
            return this.pending();
        }
        const lines = this.lines;
        lines[i].to = Math.round(v);
        if (lines[i + 1]) {
            lines[i + 1].from = Math.round(v) + 1;        // the next line follows on
        }
        this.edited();
    }
    onHours(i, ev) {
        const v = this.num(ev, `${this.state.group}-${i}-hours`);
        if (v === undefined) {
            return this.pending();
        }
        this.lines[i].hours = v;
        this.edited();
    }
    addLine() {
        const lines = this.lines;
        if (!lines.length) {
            lines.push({ from: 1, to: null, hours: 0 });
        } else {
            const last = lines[lines.length - 1];
            const from = Number.isInteger(last.from) ? last.from : 1;
            lines.splice(lines.length - 1, 0, { from, to: from + 14, hours: Number.isFinite(last.hours) ? last.hours : 0 });
            last.from = from + 15;
        }
        this.edited();
        this.focusLater(`.pbws-late .pbws-sent:nth-last-child(2) input[data-part="hours"]`);
    }
    removeLine(i) {
        const lines = this.lines;
        if (lines.length > 1) {
            if (i === lines.length - 1) {
                lines[i - 1].to = null;                    // the line before becomes "or more"
            } else {
                lines[i + 1].from = lines[i].from;         // the next line takes over its start
            }
        }
        lines.splice(i, 1);
        this.clearDrafting();
        this.edited();
    }
    onShiftTime(line, key, ev) {
        line[key] = ev.target.value;
        line.touched = true;
        this.edited();
    }
    onRate(key, ev) {
        const v = this.num(ev, `rate-${key}`);
        if (v === undefined) {
            return this.pending();
        }
        this.r.rates[key] = Math.round(v);
        this.edited();
    }
    toggleNight() {
        this.r.night.on = !this.r.night.on;
        this.edited();
    }
    onNight(key, ev) {
        this.r.night[key] = ev.target.value;
        this.edited();
    }
    onClock(key, ev) {
        const v = this.num(ev, `clock-${key}`);
        if (v === undefined) {
            return this.pending();
        }
        this.r.clock[key] = v;
        this.edited();
    }
    focusLater(selector) {
        requestAnimationFrame(() => this.root.el?.querySelector(selector)?.focus());
    }

    // ------------------------------------------------------------ saving
    edited() {
        this.editSeq++;
        this.state.error = "";
        this.state.problems = [];
        const studio = this.props.studio;
        const invalid = this.problemsNow.length > 0;
        studio.setRulesInvalid(invalid);
        studio.rulesEdited();
        clearTimeout(this.timer);
        this.timer = null;
        if (invalid) {
            this.state.mark = null;
            studio.setRulesBusy(true);       // keep the screen's values; nothing is saved yet
            return;
        }
        studio.setRulesBusy(true);
        this.state.mark = "saving";
        this.timer = setTimeout(() => {
            this.timer = null;
            this.save();
        }, AUTOSAVE_MS);
    }

    payload() {
        const r = this.r;
        return deepClone({ late: r.late, shifts: r.shifts, rates: r.rates, night: r.night, clock: r.clock });
    }

    async save() {
        if (this.inflight) {
            this.again = true;
            return this.inflight;
        }
        if (!this.canEdit || this.savedSeq === this.editSeq) {
            return true;
        }
        if (this.problemsNow.length) {
            return false;
        }
        const seq = this.editSeq;
        const vals = this.payload();
        const studio = this.props.studio;
        this.state.mark = "saving";
        this.inflight = (async () => {
            try {
                const fresh = await this.orm.call(MODEL, "save_rules", [vals]);
                this.savedSeq = seq;
                if (seq === this.editSeq) {
                    studio.setRules(fresh);
                    studio.setRulesBusy(false);
                    this.state.mark = "saved";
                    clearTimeout(this.markTimer);
                    this.markTimer = setTimeout(() => {
                        if (this.state.mark === "saved") {
                            this.state.mark = null;
                        }
                    }, 2200);
                }
                return true;
            } catch (e) {
                this.state.mark = null;
                this.state.error = errorText(e);
                return false;
            } finally {
                this.inflight = null;
                if (this.again) {
                    this.again = false;
                    if (this.editSeq !== this.savedSeq && !this.timer) {
                        this.save();
                    }
                }
            }
        })();
        return this.inflight;
    }

    /** Leave guard: save what is pending; a refused or impossible save keeps
     *  the person on this step, next to its sentence. */
    async flush() {
        if (this.timer) {
            clearTimeout(this.timer);
            this.timer = null;
        }
        if (this.inflight) {
            await this.inflight;
        }
        if (this.editSeq === this.savedSeq || !this.canEdit) {
            return true;
        }
        if (this.problemsNow.length) {
            this.state.error = _t("Fix the line marked in red first, or it cannot be saved.");
            return false;
        }
        return await this.save();
    }

    // ------------------------------------------------------------ the big buttons
    async confirm() {
        const studio = this.props.studio;
        if (!(await this.flush())) {
            this.scrollTo(".pbws-err, .is-bad");
            return;
        }
        studio.setConfirming(true);
        try {
            const res = await this.orm.call(MODEL, "confirm_rules", []);
            if (res.problems && res.problems.length) {
                this.state.problems = res.problems;
                this.scrollTo(".pbws-problems");
                return;
            }
            this.state.problems = [];
            studio.setRulesBusy(false);
            await studio.refresh();
            studio.toast(res.summary);
        } catch (e) {
            this.state.error = errorText(e);
        } finally {
            studio.setConfirming(false);
        }
    }
    async change() {
        await this.call("change_rules");
    }
    askDiscard() {
        this.state.discardAsk = true;
        clearTimeout(this.askTimer);
        this.askTimer = setTimeout(() => (this.state.discardAsk = false), 6000);
    }
    async discard() {
        this.state.discardAsk = false;
        clearTimeout(this.timer);
        this.timer = null;
        if (this.inflight) {
            await this.inflight;
        }
        this.savedSeq = this.editSeq;
        if (await this.call("discard_rules")) {
            this.props.studio.toast(_t("The new version is gone. The rules in use stay as they were."), { kind: "info" });
        }
    }
    async call(method) {
        const studio = this.props.studio;
        this.state.busy = true;
        try {
            const fresh = await this.orm.call(MODEL, method, []);
            this.state.problems = [];
            this.state.error = "";
            studio.setRulesBusy(false);
            studio.setRulesInvalid(false);
            this.clearDrafting();
            studio.setRules(fresh);
            studio.refresh();
            return true;
        } catch (e) {
            this.state.error = errorText(e);
            return false;
        } finally {
            this.state.busy = false;
        }
    }
    async remark() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "remark_days", []);
            this.props.studio.toast(res.summary, { kind: "info" });
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
        } finally {
            this.state.busy = false;
        }
    }
    openAdvanced() {
        this.action.doAction("pb_attendance_policy.action_policy");
    }
    scrollTo(selector) {
        requestAnimationFrame(() => {
            const el = this.root.el?.querySelector(selector);
            if (el) {
                el.scrollIntoView({ block: "center", behavior: this.props.studio.motion });
                if (el.matches("input")) {
                    el.focus({ preventScroll: true });
                }
            }
        });
    }

    // ------------------------------------------------------------ shift lines
    shiftRange(line) { return `${line.start}–${line.end}`; }
    shiftTitle(line) { return _t("%(shift)s, %(start)s to %(end)s", { shift: line.name, start: line.start, end: line.end }); }
    breakLabel(line) { return _t("%s: when the unpaid break starts", line.name); }
    overtimeLabel(line) { return _t("%s: when overtime starts", line.name); }
    noBreakText(line) { return line.break_minutes ? "" : _t("No unpaid break"); }
}
