/** @odoo-module **/
import { Component, onPatched, onWillDestroy, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { groupTyped, icon, money, moneyNumber, parseMoney } from "./pay_format";

const MODEL = "pb.pay.builder";

class AmountBox extends Component {
    static template = "pb_pay_builder.AmountBox";
    static props = ["value?", "label", "currency", "onInput", "id?", "suffix?", "large?", "numeric?", "step?"];
    setup() {
        this.ui = useState({ typing: null });
    }
    get text() {
        if (this.ui.typing !== null) return this.ui.typing;
        return this.props.value == null ? "" : moneyNumber(this.props.value, this.props.currency);
    }
    input(event) {
        const el = event.target;
        const right = el.value.slice(el.selectionEnd).replace(/[^0-9]/g, "").length;
        this.ui.typing = groupTyped(el.value, this.props.currency);
        el.value = this.ui.typing;
        let at = el.value.length, remaining = right;
        while (at > 0 && remaining > 0) {
            if (/\d/.test(el.value[--at])) remaining--;
        }
        el.setSelectionRange(at, at);
        this.props.onInput(parseMoney(el.value));
    }
    nudge(event) {
        if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
        event.preventDefault();
        const step = (this.props.step || 1) * (event.shiftKey ? 10 : 1);
        const value = Math.max(0, (parseMoney(event.target.value) || 0) + (event.key === "ArrowUp" ? step : -step));
        this.ui.typing = moneyNumber(value, this.props.currency);
        this.props.onInput(value);
    }
}

class PayFigure extends Component {
    static template = "pb_pay_builder.PayFigure";
    static props = ["value?", "currency"];
    setup() {
        this.el = useRef("number");
        useEffect((value) => {
            const el = this.el.el;
            const previous = this.displayed;
            let frame;
            const draw = (n) => { this.displayed = n; el.textContent = n == null ? "—" : money(n, this.props.currency); };
            if (previous == null || value == null || previous === value || matchMedia("(prefers-reduced-motion: reduce)").matches) {
                draw(value);
            } else {
                const start = performance.now();
                el.classList.remove("pbpb-flash");
                void el.offsetWidth;
                el.classList.add("pbpb-flash");
                const tick = (now) => {
                    const t = Math.min(1, (now - start) / 320);
                    draw(previous + (value - previous) * (1 - (1 - t) ** 3));
                    if (t < 1) frame = requestAnimationFrame(tick);
                };
                frame = requestAnimationFrame(tick);
            }
            return () => cancelAnimationFrame(frame);
        }, () => [this.props.value, this.props.currency.name]);
    }
}

export class PayBuilder extends Component {
    static template = "pb_pay_builder.PayBuilder";
    static components = { AmountBox, PayFigure };
    static props = ["home", "reference", "values", "tries?", "onChange", "onTries?", "onAnswer?", "variant?",
                    "readonly?", "fromOffer?", "example?", "fix?", "currency?", "slots?"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.root = useRef("root");
        this.icon = icon;
        this.ui = useState({ answer: null, open: {}, added: {}, zero: {}, all: {}, trying: {},
            hover: [], working: false, slow: false, failure: "", fix: "", back: false,
            target: null, solving: false, backMsg: "", more: {} });
        this.serial = 0;
        this.pending = false;
        this.attempt = 0;
        this.stopped = false;
        onPatched(() => this.focusRequestedLine());
        useEffect(() => { this.queue(this.ui.answer ? 250 : 0); }, () => [this.signature]);
        onWillDestroy(() => {
            this.stopped = true;
            clearTimeout(this.timer);
            clearTimeout(this.slowTimer);
            this.serial++;
        });
    }
    get a() { return this.ui.answer; }
    get cur() { return { ...(this.a?.currency || this.props.currency), builder: true }; }
    get head() { return this.a?.head || { code: "wage", is_wage: true, period: "month", name: _t("Monthly wage") }; }
    get readonly() { return Boolean(this.props.readonly || this.a?.can_edit === false); }
    get trials() { return this.props.tries || this.ui.trying; }
    get signature() {
        return JSON.stringify([this.props.home, this.props.reference, this.props.values, this.trials, Object.keys(this.ui.open).sort()]);
    }
    get targetLabel() { return _t("Take-home wanted each month"); }
    get suffix() { return this.head.period === "year" ? _t("%s a year", this.cur.name || "") : _t("%s a month", this.cur.name || ""); }
    get headHelp() {
        if (!this.a?.head?.value) return _t("Needed before this person can be paid.");
        return this.head.period === "year" ? _t("That is %s a month before deductions.", this.money(this.head.monthly))
                                          : _t("That is %s a year.", this.money(this.head.annual));
    }
    get headValue() { return this.value(this.head, this.props.home === "studio" ? this.head.usual || null : this.head.value); }
    askWas(row) {
        if (row.control === "money") return this.money(row.was);
        return row.options?.find(option => option.value === row.was)?.label ?? String(row.was);
    }
    value(row, fallback) { return Object.hasOwn(this.props.values, row.code) ? this.props.values[row.code] : (fallback ?? null); }
    money(n) { return n == null ? "—" : money(n, this.cur); }
    queue(delay = 0) {
        this.serial++;
        this.pending = true;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.run(), delay);
    }
    async run() {
        if (this.stopped || this.busy || !this.pending) return;
        const token = this.serial;
        const signature = this.signature;
        this.busy = true;
        this.pending = false;
        this.ui.working = true;
        this.ui.failure = "";
        this.slowTimer = setTimeout(() => { this.ui.slow = true; }, 400);
        try {
            const answer = await this.orm.call(MODEL, "work_out", [this.props.home, this.props.reference,
                this.props.values, this.trials, Object.keys(this.ui.open)]);
            if (this.stopped || token !== this.serial || this.signature !== signature) return;
            if (answer.ok) {
                this.attempt = 0;
                this.ui.answer = answer;
                this.props.onAnswer?.(answer);
            } else {
                this.ui.failure = answer.reason;
                this.ui.fix = answer.fix;
            }
        } catch {
            if (!this.stopped && token === this.serial) {
                if (this.attempt++ < 1) this.queue(500);
                else {
                    this.ui.failure = _t("The month could not be worked out.");
                    this.ui.fix = _t("Check the connection and try again.");
                }
            }
        } finally {
            this.busy = false;
            clearTimeout(this.slowTimer);
            if (!this.stopped) {
                this.ui.working = false;
                this.ui.slow = false;
                if (this.pending) this.queue(0);
            }
        }
    }
    change(code, value) {
        if (this.readonly) return;
        this.ui.backMsg = "";
        this.props.onChange(code, value);
    }
    trial(code, value, remove = false) {
        const opening = !Object.hasOwn(this.trials, code);
        const map = { ...this.trials, [code]:value };
        if (remove) delete map[code];
        if (this.props.onTries) this.props.onTries(map);
        else this.ui.trying = map;
        if (opening && !remove) this.focusLine(code, true, true);
    }
    toggle(code) {
        if (this.ui.open[code]) delete this.ui.open[code];
        else this.ui.open[code] = true;
    }
    escape(ev, code) {
        if (ev.key === "Escape" && this.ui.open[code]) {
            ev.stopPropagation();
            delete this.ui.open[code];
        }
    }
    focusLine(code, select = false, waitForInput = false) {
        this.focusRequest = { code, select, waitForInput };
        for (const section of this.sections) {
            const row = section.lines.find(line => line.code === code);
            if (!row || section.shown.includes(row)) continue;
            if (row.in_bar) this.ui.added[code] = true;
            if (row.zero && row.kind === "calc") this.ui.zero[section.key] = true;
            if (section.truncated) this.ui.all[section.key] = true;
        }
        this.focusRequestedLine();
    }
    focusRequestedLine() {
        if (!this.focusRequest) return;
        const { code, select, waitForInput } = this.focusRequest;
        const row = this.root.el?.querySelector('[data-line="' + CSS.escape(code) + '"]');
        if (!row) return;
        const input = row.querySelector("input,select");
        if (waitForInput && !input) return;
        this.focusRequest = null;
        const el = input || row.querySelector("button") || row;
        el.focus({ preventScroll: true });
        if (select && el.select) el.select();
        const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
        row.scrollIntoView({ block: "nearest", behavior: reduced ? "instant" : "smooth" });
        if (!reduced) row.animate([{backgroundColor:"var(--pbnh-p-soft)"},{backgroundColor:"transparent"}],{duration:1000});
    }
    add(row) { this.ui.added[row.code] = true; this.focusLine(row.code, true, true); }
    reset(row) { delete this.ui.added[row.code]; this.change(row.code, null); }
    get sections() {
        const sections = this.a?.sections || [];
        const huge = sections.reduce((n,s) => n+s.lines.length, 0) > 40;
        return sections.map((s) => {
            const visible = s.lines.filter(r => !this.inBar(r) && !(r.kind === "calc" && r.zero && !this.ui.zero[s.key]));
            return { ...s, title: s.key === "earn" ? _t("Earnings") : s.key === "ded" ? _t("Deductions") : _t("Paid by the company on top"),
                shown: huge && !this.ui.all[s.key] ? visible.slice(0,12) : visible,
                truncated: huge && visible.length > 12, count: visible.length,
                bar:s.lines.filter(r=>this.inBar(r)), zeros:s.lines.filter(r=>r.kind==="calc" && r.zero).length };
        });
    }
    inBar(row) { return row.in_bar && !this.ui.added[row.code] && !this.value(row, 0); }
    kindIcon(row) { return row.kind === "set" ? "pencil" : row.kind === "each" ? "calendar" : "calculator"; }
    kindText(row) {
        if (row.failed) return _t("Could not be worked out");
        if (row.kind === "set") return _t("You set");
        if (row.kind === "each") return row.source ? _t("Each month, from %s", row.source) : _t("Each month");
        return _t("Worked out");
    }
    get byline() { return _t("By %(scheme)s, for a full %(month)s.", { scheme:this.a.scheme.name, month:this.a.month_label }); }
    get waiting() { return _t("Type the %s to see the month work out", this.head.name); }
    get lockLine() { return _t("This sum belongs to %s, so it cannot be changed for one person.", this.a.scheme.name); }
    get settled() { return this.a?.state === "ok" && this.a.totals.net != null ? _t("Take-home %s a month", this.money(this.a.totals.net)) : ""; }
    perMonth(n) { return _t("%s a month", this.money(n)); }
    perYear(n) { return _t("%s a year", this.money(n)); }
    signedMonth(n) { return (n > 0 ? "+" : "") + this.perMonth(n); }
    usualLabel(row) { return _t("Back to usual %s", this.money(row.usual)); }
    zeroLabel(s) { return this.ui.zero[s.key] ? _t("Hide lines at zero") : _t("Show %s lines at zero", s.zeros); }
    allLabel(s) { return this.ui.all[s.key] ? _t("Show fewer lines") : _t("Show all %s lines", s.count); }
    get tiles() {
        return [["net", _t("Take-home")], ["gross", _t("Gross pay")], ["deductions", _t("Deductions")], ["cost", _t("Cost to the company")]];
    }
    get notes() {
        const notes = [...new Set([...(this.a?.notes || []), ...(this.props.example?.notes || [])])];
        const ex = this.props.example;
        const t = this.a?.totals;
        if (ex?.ok && t && !this.ui.working && ["gross","deductions","net"].some(k => ex[k] != null && t[k] != null && Math.abs(ex[k]-t[k]) > 1)) {
            notes.push(_t("The payslip example on the right also reads this person's working days and records, so it can differ slightly."));
        }
        return notes;
    }
    async solve() {
        if (this.ui.solving || this.readonly) return;
        if (!(this.ui.target > 0)) { this.ui.backMsg = _t("Type the take-home you want first."); return; }
        const sig = this.signature, target = this.ui.target;
        this.ui.solving = true;
        try {
            const res = await this.orm.call(MODEL, "work_back", [this.props.home, this.props.reference, this.props.values, this.trials, target]);
            if (this.stopped || this.signature !== sig || target !== this.ui.target) return;
            if (res.ok) {
                this.change(this.head.code, res.head_value);
                this.ui.backMsg = _t("%(pay)s gives a take-home of %(net)s a month. It is in the box above; change it if you like.",
                    { pay: this.head.period === "year" ? _t("%s a year",this.money(res.head_value)) : _t("%s a month",this.money(res.head_value)), net:this.money(res.net) });
            } else this.ui.backMsg = res.reason;
        } catch {
            if (!this.stopped) this.ui.backMsg = _t("Check the connection and try again.");
        } finally { if (!this.stopped) this.ui.solving = false; }
    }
}
