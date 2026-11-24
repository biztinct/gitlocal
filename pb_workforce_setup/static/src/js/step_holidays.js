/** @odoo-module **/
/**
 * Step 5 — "Which days is the company closed?" (WFSETUP P4).
 *
 * The year as twelve small month calendars (design of record `.months`):
 * public holidays, company days off and weekly rest days shaded. A click (or
 * Enter / Space on the focused day) adds a company day off or takes one away;
 * a public holiday asks first, inline. Arrow keys move one day / one week,
 * Page Up / Page Down one month. Every change says what it did to the roster
 * and offers Undo in the studio toast.
 *
 * The server does the work (`holidays`, `add_day_off`, `remove_days_off`,
 * `restore_days_off`, `add_suggested`, `confirm_holidays`); this component
 * only draws the year it is given.
 */
import { Component, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, errorText } from "./setup_util";

const { DateTime } = luxon;

function iso(d) {
    return d.toISODate();
}

export class StepHolidays extends Component {
    static template = "pb_workforce_setup.StepHolidays";
    static props = { studio: Object, data: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon = icon;
        this.root = useRef("root");
        this.weekLetters = [_t("M"), _t("T"), _t("W"), _t("T"), _t("F"), _t("S"), _t("S")];
        this.state = useState({
            loading: true,
            error: "",
            hol: null,
            year: null,
            focus: null,
            ask: null,
            busy: false,
            confirming: false,
        });
        this.version = 0;
        this.moved = false;
        useEffect(() => {
            if (this.moved && this.state.focus) {
                this.moved = false;
                this.root.el?.querySelector(`[data-iso="${this.state.focus}"]`)?.focus();
            }
        }, () => [this.state.focus]);
        useEffect(() => {
            if (this.state.ask) {
                this.root.el?.querySelector(".pbws-hask .pbws-btn--danger-solid")?.focus();
            }
        }, () => [this.state.ask]);
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
            this.props.studio.setBar("holidays", null);
        });
    }

    // ------------------------------------------------------------ data
    async load(year) {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.state.error = "";
        try {
            const hol = await this.orm.call(MODEL, "holidays", [year || this.state.year || false]);
            if (seq !== this.seq) {
                return;
            }
            this.version++;
            this.state.hol = hol;
            this.state.year = hol.year;
            if (!this.state.focus || !this.state.focus.startsWith(String(hol.year))) {
                const today = DateTime.fromISO(hol.today);
                this.state.focus = today.year === hol.year ? hol.today : `${hol.year}-01-01`;
            }
            this.syncBar();
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

    /** The bar's solid button: "The holidays are right. Confirm" until this
     *  year is confirmed, then the usual "Next". */
    syncBar() {
        if (!this.mounted) {
            return;
        }
        const h = this.state.hol;
        if (h && h.can_edit && !h.confirmed) {
            this.props.studio.setBar("holidays", {
                label: _t("The holidays are right. Confirm"),
                icon: "check",
                busy: this.state.confirming,
                run: () => this.confirm(),
            });
        } else {
            this.props.studio.setBar("holidays", null);
        }
    }

    // ------------------------------------------------------------ reading
    get hol() { return this.state.hol; }
    get canEdit() { return !!this.hol?.can_edit; }
    get readOnly() { return !this.props.data.can_edit; }

    /** {iso: day-off row} with ranges expanded. */
    get dayMap() {
        if (this._mapV !== this.version) {
            this._mapV = this.version;
            const map = {};
            for (const row of this.hol?.days || []) {
                let d = DateTime.fromISO(row.date);
                const last = DateTime.fromISO(row.date_to || row.date);
                while (d <= last) {
                    map[iso(d)] = row;
                    d = d.plus({ days: 1 });
                }
            }
            this._map = map;
        }
        return this._map;
    }

    get months() {
        const key = `${this.version}|${this.state.year}`;
        if (this._monthsKey !== key && this.hol) {
            this._monthsKey = key;
            const year = this.hol.year;
            const rest = new Set(this.hol.rest_weekdays);
            const map = this.dayMap;
            const today = this.hol.today;
            const out = [];
            for (let m = 1; m <= 12; m++) {
                const first = DateTime.fromObject({ year, month: m, day: 1 });
                const lead = first.weekday - 1;            // Monday first
                const days = [];
                for (let d = 1; d <= first.daysInMonth; d++) {
                    const day = first.set({ day: d });
                    const k = iso(day);
                    const row = map[k];
                    const isRest = rest.has(day.weekday - 1);
                    let cls = "";
                    let what = "";
                    if (row) {
                        cls = row.kind === "company" ? "is-co" : "is-hol";
                        what = row.kind === "company" ? _t("company day off") : _t("public holiday");
                    } else if (isRest) {
                        cls = "is-rest";
                        what = _t("rest day");
                    }
                    if (k === today) {
                        cls += " is-today";
                    }
                    const long = day.toFormat("cccc d LLLL");
                    days.push({
                        iso: k,
                        d,
                        cls,
                        title: row ? row.name : what,
                        label: row ? `${long}, ${what}: ${row.name}` : what ? `${long}, ${what}` : long,
                    });
                }
                out.push({ key: m, name: first.toFormat("LLLL"), lead: Array.from({ length: lead }, (_, i) => i), days });
            }
            this._months = out;
        }
        return this._months || [];
    }

    tab(day) {
        return day.iso === this.state.focus ? "0" : "-1";
    }
    cellClass(day) {
        return `pbws-md ${day.cls}${this.state.ask && this.state.ask.iso === day.iso ? " is-asked" : ""}`;
    }

    get list() {
        return [...(this.hol?.days || [])].sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    }
    kindLabel(row) {
        return row.kind === "company" ? _t("Company day off")
            : row.kind === "collective" ? _t("Collective leave") : _t("Public holiday");
    }
    rangeLabel(row) {
        const a = DateTime.fromISO(row.date);
        const b = DateTime.fromISO(row.date_to || row.date);
        if (iso(a) === iso(b)) {
            return a.toFormat("ccc d LLL");
        }
        return a.month === b.month ? `${a.toFormat("d")}–${b.toFormat("d LLL")}` : `${a.toFormat("d LLL")} – ${b.toFormat("d LLL")}`;
    }
    removeLabel(row) { return _t("Remove %s", row.name); }

    get workingChip() {
        return _t("%(n)s working days in %(year)s", { n: this.hol.working_days, year: this.hol.year });
    }
    get offLine() {
        const n = this.hol.off_count;
        return n === 1 ? _t("1 day off in %s", this.hol.year) : _t("%(n)s days off in %(year)s", { n, year: this.hol.year });
    }
    get sugg() {
        const s = this.hol?.suggestions;
        return s && s.missing.length ? s : null;
    }
    get suggLine() {
        const s = this.sugg;
        return _t("%(country)s public holidays for %(year)s", { country: s.country, year: s.year });
    }
    get suggCount() {
        const n = this.sugg.missing.length;
        return n === 1 ? _t("1 day") : _t("%s days", n);
    }
    get nudgeLine() {
        return _t("Next year's holidays are not set yet.");
    }
    get nudgeButton() {
        return _t("Go to %s", this.hol.nudge);
    }
    get confirmedLine() {
        return _t("Holidays for %s are confirmed.", this.hol.year);
    }
    get askLine() {
        return _t("Remove %s for everyone?", this.state.ask?.name || "");
    }
    yearClass(y) {
        return y === this.state.year ? "is-on" : "";
    }

    // ------------------------------------------------------------ year
    setYear(y) {
        if (y === this.state.year) {
            return;
        }
        this.state.ask = null;
        this.state.year = y;
        this.state.focus = null;
        this.load(y);
    }

    // ------------------------------------------------------------ keyboard
    onCalKey(ev) {
        if (ev.key === "Escape" && this.state.ask) {
            ev.preventDefault();
            this.keepAsk();
            return;
        }
        if (!ev.target?.dataset?.iso) {
            return;                       // a button of the question strip keeps its own keys
        }
        const cur = DateTime.fromISO(this.state.focus || `${this.state.year}-01-01`);
        let next = null;
        switch (ev.key) {
            case "ArrowLeft": next = cur.minus({ days: 1 }); break;
            case "ArrowRight": next = cur.plus({ days: 1 }); break;
            case "ArrowUp": next = cur.minus({ days: 7 }); break;
            case "ArrowDown": next = cur.plus({ days: 7 }); break;
            case "PageUp": next = cur.minus({ months: 1 }); break;
            case "PageDown": next = cur.plus({ months: 1 }); break;
            case "Home": next = cur.minus({ days: cur.weekday - 1 }); break;
            case "End": next = cur.plus({ days: 7 - cur.weekday }); break;
            case "Enter":
            case " ":
                ev.preventDefault();
                this.toggle(iso(cur));
                return;
            default:
                return;
        }
        ev.preventDefault();
        if (next.year !== this.state.year) {
            return;                       // the year strip changes years
        }
        this.moved = true;
        this.state.focus = iso(next);
    }
    onDayFocus(day) {
        this.state.focus = day.iso;
    }

    // ------------------------------------------------------------ changes
    onDay(day) {
        this.state.focus = day.iso;
        this.toggle(day.iso);
    }

    toggle(k) {
        if (!this.canEdit || this.state.busy) {
            return;
        }
        const row = this.dayMap[k];
        if (!row) {
            this.state.ask = null;
            return this.add(k);
        }
        if (row.kind === "company") {
            this.state.ask = null;
            return this.remove(row);
        }
        this.state.ask = { id: row.id, name: row.name, iso: k };
    }

    async run(fn) {
        if (this.state.busy) {
            return null;
        }
        this.state.busy = true;
        try {
            return await fn();
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    async after(res, undo) {
        await this.load();
        this.props.studio.refresh();
        if (res) {
            this.props.studio.toast(res.summary, undo ? { undo } : {});
        }
    }

    async add(k) {
        const res = await this.run(() => this.orm.call(MODEL, "add_day_off", [k]));
        if (res) {
            await this.after(res, () => this.undoAdd(res.ids));
        }
    }

    async remove(row) {
        this.state.ask = null;
        const res = await this.run(() => this.orm.call(MODEL, "remove_days_off", [[row.id]]));
        if (res) {
            await this.after(res, () => this.undoRemove(res.restore));
        }
    }

    removeRow(row) {
        if (row.kind === "company") {
            return this.remove(row);
        }
        this.state.ask = { id: row.id, name: row.name, iso: row.date };
    }

    confirmAsk() {
        const ask = this.state.ask;
        const row = ask && (this.hol.days || []).find((r) => r.id === ask.id);
        if (row) {
            this.remove(row);
        } else {
            this.state.ask = null;
        }
    }
    keepAsk() {
        const k = this.state.ask?.iso;
        this.state.ask = null;
        if (k) {
            this.moved = true;
            this.state.focus = k;
        }
    }

    async addAll() {
        const s = this.sugg;
        if (!s) {
            return;
        }
        const res = await this.run(() => this.orm.call(MODEL, "add_suggested", [s.year]));
        if (res) {
            await this.after(res, res.ids.length ? () => this.undoAdd(res.ids) : null);
        }
    }

    async undoAdd(ids) {
        const res = await this.run(() => this.orm.call(MODEL, "remove_days_off", [ids]));
        if (res) {
            await this.after(res);
        }
    }

    async undoRemove(rows) {
        const res = await this.run(() => this.orm.call(MODEL, "restore_days_off", [rows]));
        if (res) {
            await this.after(res);
        }
    }

    async confirm() {
        if (this.state.confirming) {
            return;
        }
        this.state.confirming = true;
        this.syncBar();
        try {
            const res = await this.orm.call(MODEL, "confirm_holidays", [this.state.year]);
            await this.load();
            await this.props.studio.refresh();
            this.props.studio.toast(res.summary);
            this.props.studio.go("clocks");
        } catch (e) {
            this.props.studio.toast(errorText(e), { kind: "error" });
        } finally {
            this.state.confirming = false;
            this.syncBar();
        }
    }

    openCalendars() {
        this.action.doAction("resource.action_resource_calendar_form");
    }
}
