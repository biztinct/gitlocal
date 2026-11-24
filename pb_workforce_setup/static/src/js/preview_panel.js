/** @odoo-module **/
/**
 * The right panel — "See it on a real person".
 *
 * P1: a person picker (search as you type, keyboard friendly) and that
 * person's CURRENT week from their working week, computed on the server with
 * the real cycle formula.
 *
 * P3: the pay example. Two sliders (clock-in, clock-out) and a Normal day /
 * Rest day / Public holiday choice feed `pay_example`, which runs the REAL
 * engine on the server with the screen's current rule values (unsaved edits
 * included) and writes nothing. No maths happens here.
 *   * Requests are throttled (leading + trailing, 120 ms) and every reply
 *     carries a sequence number: an older reply never replaces a newer one.
 *   * The last good answer stays on screen while the next one loads (no
 *     flicker, no spinner over the numbers); while the rules on the left
 *     have a line in red, the panel keeps the last good answer.
 *   * Early arrival is not paid by the engine: the slider says so.
 */
import { Component, onMounted, onWillUnmount, onWillUpdateProps, useExternalListener, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, errorText, timeRange, deepClone, rich, hoursText } from "./setup_util";

const THROTTLE_MS = 120;

export class PreviewPanel extends Component {
    static template = "pb_workforce_setup.PreviewPanel";
    static props = {
        studio: Object,
        person: { type: [Object, Boolean], optional: true },
        step: { type: String, optional: true },
        rules: { type: [Object, Boolean], optional: true },
        rulesRev: { type: Number, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.icon = icon;
        this.range = timeRange;
        this.root = useRef("root");
        this.input = useRef("query");
        this.state = useState({
            picking: false, query: "", results: [], active: 0, loading: false, error: "",
            // the pay example
            inM: 12, outM: 60, kind: "normal", result: null, waiting: false,
        });
        this.exSeq = 0;
        this.exShown = 0;
        this.throttle = null;
        this.pending = false;
        useExternalListener(window, "pointerdown", (ev) => {
            if (this.state.picking && this.root.el && !this.root.el.contains(ev.target)) {
                this.state.picking = false;
            }
        });
        onMounted(() => this.example());
        onWillUpdateProps((next) => {
            const personChanged = (next.person && next.person.id) !== (this.props.person && this.props.person.id)
                || (next.person && next.person.week_id) !== (this.props.person && this.props.person.week_id);
            if (personChanged || next.rulesRev !== this.props.rulesRev) {
                if (personChanged) {
                    this.state.result = null;
                }
                this.example(next);
            }
        });
        onWillUnmount(() => {
            clearTimeout(this.timer);
            clearTimeout(this.throttle);
        });
    }

    get person() { return this.props.person || null; }
    get hasWeek() { return !!(this.person && this.person.week_name); }
    get caption() {
        const p = this.person;
        if (!p || !p.week_name) {
            return "";
        }
        return p.week_no ? _t("%(week)s · week %(n)s", { week: p.week_name, n: p.week_no }) : p.week_name;
    }
    get noWeekLine() {
        return _t("%s has no working week yet.", this.person.name);
    }
    dayTitle(day) {
        return day.shift_id ? _t("%(shift)s, %(start)s to %(end)s", { shift: day.name, start: day.start, end: day.end }) : _t("Day off");
    }

    // ------------------------------------------------------------ person picker
    async open() {
        this.state.picking = !this.state.picking;
        if (!this.state.picking) {
            return;
        }
        this.state.query = "";
        this.state.active = 0;
        await this.search("");
        this.input.el?.focus();
    }
    onQuery(ev) {
        this.state.query = ev.target.value;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.search(this.state.query), 180);
    }
    async search(query) {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.state.loading = true;
        try {
            const rows = await this.orm.call(MODEL, "find_people", [query, 20]);
            if (seq === this.seq) {
                this.state.results = rows;
                this.state.active = 0;
                this.state.error = "";
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
    onKey(ev) {
        const n = this.state.results.length;
        if (ev.key === "ArrowDown" && n) {
            ev.preventDefault();
            this.state.active = (this.state.active + 1) % n;
        } else if (ev.key === "ArrowUp" && n) {
            ev.preventDefault();
            this.state.active = (this.state.active - 1 + n) % n;
        } else if (ev.key === "Enter" && n) {
            ev.preventDefault();
            this.choose(this.state.results[this.state.active]);
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            this.state.picking = false;
        }
    }
    choose(row) {
        this.state.picking = false;
        this.props.studio.setPerson(row.id);
    }
    goPeople() {
        this.props.studio.go("people");
    }

    // ------------------------------------------------------------ the pay example
    get kinds() {
        return [
            { key: "normal", label: _t("Normal day") },
            { key: "rest_day", label: _t("Rest day") },
            { key: "holiday", label: _t("Public holiday") },
        ];
    }
    setKind(key) {
        if (this.state.kind !== key) {
            this.state.kind = key;
            this.example();
        }
    }
    onIn(ev) {
        this.state.inM = Number(ev.target.value) || 0;
        this.example();
    }
    onOut(ev) {
        this.state.outM = Number(ev.target.value) || 0;
        this.example();
    }
    get inLabel() {
        const m = this.state.inM;
        if (m > 0) {
            return _t("%s min late", m);
        }
        return m < 0 ? _t("%s min early (not counted)", -m) : _t("on time");
    }
    get outLabel() {
        const m = this.state.outM;
        if (m > 0) {
            return _t("%s min after the shift ends", m);
        }
        return m < 0 ? _t("%s min before the shift ends", -m) : _t("when the shift ends");
    }

    /** Throttled, leading + trailing: the first move answers at once, the
     *  last position is always sent, and at most one call per 120 ms. */
    example(props = this.props) {
        this.nextProps = props;
        if (this.throttle) {
            this.pending = true;
            return;
        }
        this.fire(props);
        this.throttle = setTimeout(() => {
            this.throttle = null;
            if (this.pending) {
                this.pending = false;
                this.example(this.nextProps);
            }
        }, THROTTLE_MS);
    }

    async fire(props) {
        const person = props.person;
        if (!person || !person.week_name) {
            return;
        }
        // a line in red on the left: keep the last good answer on screen
        if (props.studio.rulesInvalid && this.state.result) {
            return;
        }
        const rules = props.rules && props.rules.state !== "advanced" ? deepClone(props.rules) : null;
        const seq = ++this.exSeq;
        this.state.waiting = true;
        try {
            const res = await this.orm.silent.call(MODEL, "pay_example",
                [person.id, this.state.inM, this.state.outM, rules, this.state.kind]);
            if (seq > this.exShown) {                 // an older reply never wins
                this.exShown = seq;
                this.state.result = res;
            }
        } catch (e) {
            if (seq > this.exShown) {
                this.exShown = seq;
                this.state.result = { error: errorText(e) };
            }
        } finally {
            if (seq === this.exSeq) {
                this.state.waiting = false;
            }
        }
    }

    get res() { return this.state.result; }
    get ok() { return !!(this.res && !this.res.error); }
    get isNormal() { return this.ok && this.res.day_kind === "normal"; }
    pct(v) { return `${v} %`; }
    get sentence() {
        const r = this.res;
        const out = [];
        out.push(rich(_t("%(name)s clocks in at %(in)s and out at %(out)s on %(day)s (%(shift)s)."),
            { name: r.first_name || r.name, in: r.clock_in, out: r.clock_out }, { day: r.day_label, shift: r.shift_name }));
        const rule = r.group === "manager" ? _t("Manager") : _t("Worker");
        if (r.late_minutes > 0) {
            out.push(r.taken_off_hours > 0
                ? rich(_t("That is %(late)s, so %(off)s comes off (%(rule)s rule)."),
                    { late: _t("%s min late", r.late_minutes), off: hoursText(r.taken_off_hours) }, { rule })
                : rich(_t("That is %(late)s; nothing comes off (%(rule)s rule)."),
                    { late: _t("%s min late", r.late_minutes) }, { rule }));
        } else if (r.early_minutes > 0) {
            out.push(rich(_t("Coming in %(n)s early is not paid: the day starts at %(start)s."),
                { n: _t("%s min", r.early_minutes) }, { start: r.shift_start }));
        } else {
            out.push(rich(_t("On time.")));
        }
        if (this.isNormal) {
            if (r.overtime_hours > 0) {
                out.push(rich(_t("%(h)s counts as overtime at %(rate)s, once a manager approves it."),
                    { h: hoursText(r.overtime_hours) }, { rate: this.pct(r.rate_percent) }));
            } else {
                out.push(rich(_t("Overtime starts at %(at)s, so none today."), {}, { at: r.overtime_from }));
            }
        } else {
            out.push(rich(r.day_kind === "holiday"
                ? _t("On a public holiday every paid hour counts at %(rate)s, once a manager approves it.")
                : _t("On a rest day every paid hour counts at %(rate)s, once a manager approves it."),
            { rate: this.pct(r.rate_percent) }));
        }
        if (r.night_hours > 0) {
            out.push(rich(_t("%(h)s of it is night work, with %(pct)s extra."),
                { h: hoursText(r.night_hours) }, { pct: this.pct(r.night_percent) }));
        }
        return out;
    }
    get rows() {
        const r = this.res;
        const rows = [
            { key: "w", label: _t("Worked after break"), value: hoursText(r.worked_hours) },
            { key: "l", label: _t("Taken off for lateness"), value: r.taken_off_hours > 0 ? `− ${hoursText(r.taken_off_hours)}` : hoursText(0) },
        ];
        if (this.isNormal) {
            rows.push({ key: "o", label: _t("Overtime at %s", this.pct(r.rate_percent)), value: hoursText(r.overtime_hours) });
        }
        if (r.night_on) {
            rows.push({ key: "n", label: _t("Night work, %s extra", this.pct(r.night_percent)), value: hoursText(r.night_hours) });
        }
        return rows;
    }
    get totalLabel() {
        const r = this.res;
        if (this.isNormal) {
            return _t("Paid normal hours");
        }
        return r.day_kind === "holiday" ? _t("Paid at %s (public holiday)", this.pct(r.rate_percent))
            : _t("Paid at %s (rest day)", this.pct(r.rate_percent));
    }
    get totalValue() {
        const r = this.res;
        return hoursText(this.isNormal ? r.normal_hours : r.overtime_hours);
    }
    get fix() {
        const f = this.res && this.res.fix;
        if (!f || f === this.props.step) {
            return null;
        }
        return f === "people" ? { key: "people", label: _t("Go to who works what") }
            : f === "rules" ? { key: "rules", label: _t("Go to late and overtime rules") } : null;
    }
    goFix() {
        if (this.fix) {
            this.props.studio.go(this.fix.key);
        }
    }
}
