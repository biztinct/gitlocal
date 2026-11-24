/** @odoo-module **/
/**
 * The right panel — "See it on a real person".
 *
 * P1: a person picker (search as you type, keyboard friendly) and that
 * person's CURRENT week from their working week, computed on the server with
 * the real cycle formula. The pay example (sliders + result) arrives with the
 * late and overtime rules.
 */
import { Component, onWillUnmount, useExternalListener, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, errorText, timeRange } from "./setup_util";

export class PreviewPanel extends Component {
    static template = "pb_workforce_setup.PreviewPanel";
    static props = { studio: Object, person: { type: [Object, Boolean], optional: true }, step: { type: String, optional: true } };

    setup() {
        this.orm = useService("orm");
        this.icon = icon;
        this.range = timeRange;
        this.root = useRef("root");
        this.input = useRef("query");
        this.state = useState({ picking: false, query: "", results: [], active: 0, loading: false, error: "" });
        useExternalListener(window, "pointerdown", (ev) => {
            if (this.state.picking && this.root.el && !this.root.el.contains(ev.target)) {
                this.state.picking = false;
            }
        });
        onWillUnmount(() => clearTimeout(this.timer));
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
}
