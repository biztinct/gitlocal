/** @odoo-module **/
/**
 * CD-2 — the contract drawer. A bespoke slide-over on the Contracts lens with
 * three tabs (Terms · Components · History), READ-ONLY in this phase; CD-3
 * turns the same cells into editors.
 *
 * Shape, motion and restraint mirror `Employee360Drawer`
 * (pb_employee_vault/static/src/js/employee_360.js) — teal is a person, indigo
 * is a contract. It registers into the soft "pb_contracts_drawer" registry so
 * the Contracts cockpit keeps a hard import out of `contracts.js` and stays
 * installable if this file ever moves to a satellite module.
 *
 * RPC facade: pb.contracts (get_contract_360). Lucide icons only, from the
 * SHARED registry (W2). Wage values are masked server-side for non-payroll
 * managers — the client never sees a number it may not show.
 *
 * W96: every expression a template evaluates lives in a method here. A
 * template is compiled against the COMPONENT and nothing else, so `String(x)`
 * or `Object.keys(x)` in the XML becomes `ctx.String(...)` and dies at mount
 * with no dialog and nothing in the log.
 */
import { Component, useState, onWillStart, onMounted, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.contracts";
const TABS = ["terms", "components", "history"];

// Group key → the icon that titles its section.
const GROUP_ICON = { money: "banknote", dates: "calendar", place: "mapPin", rules: "shield" };

// Term name → the icon on its cell. A term with no entry here gets a neutral
// dot-free label; nothing is invented per module (W2).
const FIELD_ICON = {
    wage: "banknote", struct_id: "layers", type_id: "users", schedule_pay: "clock",
    grade_id: "award", compa_ratio: "percent", journal_id: "bookOpen",
    date_start: "calendar", date_end: "calendar", trial_date_end: "clock",
    resource_calendar_id: "clock",
    department_id: "building", job_id: "briefcase", location: "mapPin",
    costcenter: "hash", hr_responsible_id: "user",
    hirestatus: "activity", tupart: "users", shuipart: "shield",
    dependents: "users", tax_identification_number: "stamp",
};

// Readiness chip key → icon.
const READY_ICON = { structure: "layers", schedule: "clock", tax: "stamp", category: "users" };

// History row kind → icon.
const KIND_ICON = { component: "banknote", field: "fileText", retro: "history" };

// Contract state → the chip tone the shared kit already paints.
const STATE_TONE = { open: "ok", close: "warn", draft: "info", cancel: "muted" };

const MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export class Contract360Drawer extends Component {
    static template = "pb_contracts.Contract360Drawer";
    static props = {
        contractId: { type: [Number, String] },
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loaded: false, shown: false, tab: "terms", d: null });
        onWillStart(() => this.load());
        // One frame after mount, so the panel has a place to slide in FROM.
        onMounted(() => { this.state.shown = true; });
        // Escape closes. Capture phase is the safe pattern for an overlay that
        // does not steal focus from the roster underneath it.
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
    }

    // ---------------------------------------------------------------- reading
    async load() {
        try {
            this.state.d = await this.orm.call(MODEL, "get_contract_360", [Number(this.props.contractId)]);
        } catch (e) {
            this.state.d = { error: this._err(e) };
        } finally {
            this.state.loaded = true;
        }
    }
    _err(e) {
        return (e && e.message && e.message.data && e.message.data.message)
            || "Payobook could not open this contract just now. Try again in a moment.";
    }

    // ------------------------------------------------------------- accessors
    // Rail 10: a payload from an older server is missing keys, not broken. Every
    // accessor below hands back an empty shape rather than letting the template
    // read through `undefined`.
    get d() { return this.state.d || {}; }
    get header() { return this.d.header || {}; }
    get terms() { return this.d.terms || []; }
    get readiness() { return this.d.readiness || []; }
    get components() { return this.d.components || {}; }
    get compRows() { return this.components.rows || []; }
    get addable() { return this.components.addable || []; }
    get history() { return this.d.history || {}; }
    get pipeline() { return this.header.pipeline || []; }
    get nextActions() { return this.header.next_actions || []; }
    get compCount() { return this.compRows.length; }
    get histCount() { return this.history.total || 0; }
    get hasMoreHistory() { return (this.history.total || 0) > (this.history.shown || 0); }

    // The header's wage is a raw number; its SENTENCE was formatted once,
    // server-side (rail 8), and lives on the `wage` term. Read it from there
    // rather than teaching the client a second opinion about money.
    termEntry(name) {
        for (const group of this.terms) {
            for (const field of (group.fields || [])) {
                if (field.name === name) { return field; }
            }
        }
        return null;
    }
    get wageDisplay() {
        const entry = this.termEntry("wage");
        return (entry && entry.display) || "";
    }

    ic(n, s = 16) { return ic(n, s); }
    groupIcon(key) { return ic(GROUP_ICON[key] || "fileText", 14); }
    fieldIcon(name) { return ic(FIELD_ICON[name] || "chevron", 14); }
    readyIcon(key) { return ic(READY_ICON[key] || "check", 14); }
    kindIcon(kind) { return ic(KIND_ICON[kind] || "history", 15); }
    stateTone(s) { return STATE_TONE[s] || "muted"; }

    // ---------------------------------------------------------------- chrome
    // Switching tabs starts the new one at the top. Without this, arriving at
    // Components from the bottom of Terms lands halfway down a list of
    // twenty-one rows and the explainer above them is never seen.
    setTab(t) {
        this.state.tab = t;
        const body = document.querySelector(".pbc-body");
        if (body) { body.scrollTop = 0; }
    }
    get tabIndex() {
        const i = TABS.indexOf(this.state.tab);
        return i < 0 ? 0 : i;
    }
    // The tab underline slides because ONE bar moves, not because three bars
    // fade. Equal-width tabs make the offset pure arithmetic — no measuring, no
    // onPatched write-back into reactive state (W148).
    get inkStyle() { return "transform: translateX(" + (this.tabIndex * 100) + "%)"; }

    onKey(ev) { if (ev.key === "Escape") { this.close(); } }
    close() {
        this.state.shown = false;
        const done = this.props.onClose || (() => { });
        setTimeout(done, 180);   // let the slide-out play before we unmount
    }

    // The escape hatch. Never called "the Odoo form" — it is the full form.
    openFullForm() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.contract",
            res_id: Number(this.props.contractId), views: [[false, "form"]],
            target: "current",
        });
    }
    // CD-2 is read-only, so a lifecycle step is not performed here: the button
    // carries the person to the full contract screen that owns it rather than
    // being a chip that does nothing (zero dead-ends).
    openFullScreen() {
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_contract_detail", name: "Contract",
            params: { contract_id: Number(this.props.contractId) },
        });
    }

    // --------------------------------------------------------------- history
    // Month separators, cloned from the employee drawer's `timelineRows()`.
    historyRows() {
        const out = [];
        let lastMonth = null;
        for (const row of (this.history.rows || [])) {
            const m = (row.when || "").slice(0, 7);
            if (m && m !== lastMonth) {
                out.push({ sep: true, key: "sep-" + m + "-" + out.length, label: this._monthLabel(m) });
                lastMonth = m;
            }
            out.push(Object.assign({ sep: false, key: "it-" + out.length }, row));
        }
        return out;
    }
    _monthLabel(m) {
        const parts = m.split("-");
        return (MONTHS[parseInt(parts[1], 10)] || "") + " " + parts[0];
    }
    hasDelta(row) { return Boolean(row.from || row.to); }
    historyCountLabel() {
        return "Showing " + (this.history.shown || 0) + " of " + (this.history.total || 0);
    }
}

registry.category("pb_contracts_drawer").add("contract_360", Contract360Drawer);
