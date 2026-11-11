/** @odoo-module **/
/**
 * UPDATES P3b — "Since the last pay run" on the pay run's "Review pay data".
 *
 * One line under the worksheet's summary ("Since the last pay run: 14 people
 * have changes (9 pay, 3 bank, 2 new)") opening a side panel: search, one
 * chip per kind, one block per person (open or closed), and "Download as a
 * sheet". Information only: nothing here changes a figure or blocks the run.
 * The data comes with the worksheet's own answer (`since_last_run`, added by
 * `pb_updates` only when there is something to show).
 */
import { Component, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { PayrollReviewDialog } from "@pb_payrun_wizard/js/payroll_review";

const KIND_ICON = {
    pay: "banknote", contract: "fileText", bank: "creditCard", details: "user",
    oneoff: "coins", scheduled: "calendarClock", new: "userPlus",
};

/** A CSV cell, quoted when it needs to be. */
function csvCell(value) {
    const text = String(value === null || value === undefined ? "" : value);
    return /[",\n;]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export class PbuSincePanel extends Component {
    static template = "pb_updates.SincePanel";
    static props = { data: Object, period: { type: String, optional: true }, onClose: Function };

    setup() {
        this.ui = useState({ q: "", kind: "", open: {} });
        this.icons = {};
    }

    icon(name, size = 14) {
        const key = `${name}:${size}`;
        if (!this.icons[key]) { this.icons[key] = ic(name, size); }
        return this.icons[key];
    }

    kindIcon(kind) { return this.icon(KIND_ICON[kind] || "info", 13); }

    get kinds() { return this.props.data.kinds || []; }

    get people() {
        const q = (this.ui.q || "").trim().toLowerCase();
        const kind = this.ui.kind;
        return (this.props.data.people || []).filter((p) =>
            (!kind || p.kinds.includes(kind)) &&
            (!q || p.name.toLowerCase().includes(q) ||
             p.items.some((i) => i.text.toLowerCase().includes(q))));
    }

    items(p) {
        return this.ui.kind ? p.items.filter((i) => i.kind === this.ui.kind) : p.items;
    }

    isOpen(p) {
        const v = this.ui.open[p.employee_id];
        return v === undefined ? this.people.length <= 12 : v;
    }

    toggle(p) { this.ui.open[p.employee_id] = !this.isOpen(p); }

    setKind(key) { this.ui.kind = this.ui.kind === key ? "" : key; }

    kindLabel(key) {
        return (this.kinds.find((k) => k.key === key) || {}).label || key;
    }

    get shownLine() {
        const n = this.people.length;
        const all = (this.props.data.people || []).length;
        if (n === all) { return ""; }
        return _t("Showing %(n)s of %(all)s people", { n, all });
    }

    download() {
        const rows = [[_t("Person"), _t("Kind"), _t("Change"), _t("Date")]];
        for (const p of this.people) {
            for (const i of this.items(p)) {
                rows.push([p.name, this.kindLabel(i.kind), i.text, i.date || ""]);
            }
        }
        const body = "﻿" + rows.map((r) => r.map(csvCell).join(",")).join("\n");
        const url = URL.createObjectURL(new Blob([body], { type: "text/csv;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = _t("Changes since the last pay run %s.csv", this.props.period || "").replace(/\s+\.csv$/, ".csv");
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    onKey(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            this.props.onClose();
        }
    }
}

PayrollReviewDialog.components = { ...(PayrollReviewDialog.components || {}), PbuSincePanel };

patch(PayrollReviewDialog.prototype, {
    pbuSinceOpen() { this.state.pbuSince = true; },
    pbuSinceClose() { this.state.pbuSince = false; },
    get pbuSincePeriod() {
        const p = (this.state.data && this.state.data.period) || [];
        return p.length === 2 ? `${p[0]} – ${p[1]}` : "";
    },
});
