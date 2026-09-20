/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/**
 * The settings that used to live in a panel of their own, as cards in the
 * journey — on the step where the decision belongs.
 *
 * Three groups, mounted by the shell underneath whichever step is open:
 *
 * | Step      | Group        | Cards                                            |
 * |-----------|--------------|--------------------------------------------------|
 * | Start     | `advanced`   | Advanced (reference code, structure, workbook and export options) |
 * | Pay rules | `automation` | Part-month pay · Back-pay                        |
 * | Connect   | `connect`    | Connected system · Where values come from · Accounting |
 *
 * Every one of them is a SETTING, never a rule (BLUEPRINT rule 8a), so they
 * stay editable on a live configuration exactly as the old panel's fields
 * always were. They are shown in create mode too — a new configuration
 * deserves them — but folded, so the six-step flow stays light.
 *
 * Nothing here decides anything: the server owns the whitelist, the refusals
 * and the locks, and this only shows what it said.
 */

/** Which group of cards belongs under which step. */
export function settingsGroupFor(step) {
    return { start: "advanced", rules: "automation", connect: "connect" }[step] || "";
}

/** The three source lanes, in the words the Sources card uses. */
export function laneLabels() {
    return {
        api: {
            label: _t("Connected system"),
            sub: _t("values arriving from the connected HR system"),
        },
        excel: {
            label: _t("Spreadsheet"),
            sub: _t("the pay data file uploaded for a run"),
        },
        records: {
            label: _t("Payobook records"),
            sub: _t("employee, contract and amount data kept here"),
        },
    };
}

/** "api,excel,records" -> a clean list of three, whatever was stored. */
export function laneOrder(priority) {
    const order = String(priority || "api,excel,records")
        .split(",")
        .map((s) => s.trim())
        .filter((s) => ["api", "excel", "records"].includes(s));
    for (const key of ["api", "excel", "records"]) {
        if (!order.includes(key)) { order.push(key); }
    }
    return order;
}

/** One sentence saying what the order MEANS, not what it is. */
export function laneSentence(lanes) {
    const on = lanes.filter((l) => l.on);
    if (!on.length) {
        return _t("Every source is off — components use only their own formulas and fixed values.");
    }
    const order = on.map((l) => l.label).join(" → ");
    if (on[0].key === "records") {
        return _t(
            "Order: %s. Payobook records are the source of truth: a value already held is never overwritten — lower sources may only fill empty boxes.",
            order);
    }
    return _t("Order: %s. A lower source is used only where every higher one is silent.",
              order);
}

/** What switching a lane off would cost, counted rather than asserted. */
export function laneWarnings(lanes) {
    return lanes
        .filter((l) => !l.on && l.count)
        .map((l) => _t(
            "%(n)s component(s) take values from “%(lane)s” today — they will fall through to the next source.",
            { n: l.count, lane: l.label }));
}

/** The name a change is reported under on the Save changes page. */
export function settingLabel(field) {
    return {
        name: _t("Name"),
        code: _t("Reference code"),
        country_code: _t("Country"),
        cycle_type: _t("Pay cycle"),
        structure_id: _t("Legacy payroll structure"),
        connector_id: _t("Connected system"),
        use_color_coded_excel_import: _t("Colour-coded workbook import"),
        export_identity_columns: _t("Identity columns on the export"),
        payroll_journal_id: _t("Payroll journal"),
        debit_account_id: _t("Default debit account"),
        credit_account_id: _t("Default credit account"),
        use_proration: _t("Part-month pay"),
        proration_basis: _t("Part-month basis"),
        proration_component_ids: _t("Components paid part-month"),
        proration_rounding: _t("Part-month rounding"),
        use_auto_retro: _t("Back-pay"),
        retro_component_id: _t("Back-pay component"),
        source_api_enabled: _t("Connected system as a source"),
        source_excel_enabled: _t("Spreadsheet as a source"),
        source_records_enabled: _t("Payobook records as a source"),
        source_priority: _t("Which source wins"),
        effective_from: _t("Effective from"),
    }[field] || field;
}


export class SettingsCards extends Component {
    static template = "pb_blueprint.SettingsCards";
    static props = {
        group: { type: String },
        values: { type: Object },
        meta: { type: Object },
        locks: { type: Object, optional: true },
        mode: { type: String, optional: true },
        busy: { type: Boolean, optional: true },
        error: { type: String, optional: true },
        onSet: { type: Function },
        onCommit: { type: Function },
    };

    setup() {
        // Open on arrival when somebody came here to CHANGE settings; folded
        // when they came here to build a payroll and these are extras.
        this.state = useState({ open: this.props.mode === "edit" });
    }

    ic(name, size = 16) { return ic(name, size); }

    get v() { return this.props.values || {}; }
    get meta() { return this.props.meta || {}; }
    get open() { return this.state.open; }

    toggleOpen() { this.state.open = !this.state.open; }

    get title() {
        return {
            advanced: _t("Advanced"),
            automation: _t("Months that are not ordinary"),
            connect: _t("Where the numbers come from, and where they post"),
        }[this.props.group] || "";
    }

    get lead() {
        return {
            advanced: _t("The details most configurations never need to touch."),
            automation: _t("Somebody joins on the 12th, or last month's pay rise is agreed today."),
            connect: _t("The connected system, the order sources win in, and the books."),
        }[this.props.group] || "";
    }

    get icon() {
        return { advanced: "sliders", automation: "calendar", connect: "plug" }[this.props.group]
            || "settings";
    }

    // ==================================================================
    // Writing
    // ==================================================================
    set(field, value) { this.props.onSet(field, value); }

    commit(fields) { this.props.onCommit(fields); }

    onText(field, ev) { this.set(field, ev.target.value); }

    onTextCommit(field, ev) {
        this.set(field, ev.target.value);
        this.commit([field]);
    }

    onNumberCommit(field, ev) {
        const raw = ev.target.value;
        this.set(field, raw === "" ? 0 : Number(raw));
        this.commit([field]);
    }

    onSelectCommit(field, ev) {
        this.set(field, ev.target.value);
        this.commit([field]);
    }

    onM2OCommit(field, ev) {
        const raw = ev.target.value;
        this.set(field, raw ? Number(raw) : false);
        this.commit([field]);
    }

    onCheckCommit(field, ev) {
        this.set(field, !!ev.target.checked);
        this.commit([field]);
    }

    // ==================================================================
    // Part-month pay
    // ==================================================================
    /** The engine refuses part-month pay with nothing to prorate (SC12). */
    get prorationIncomplete() {
        return !!this.v.use_proration && !(this.v.proration_component_ids || []).length;
    }

    get prorationNote() {
        return _t("Choose at least one component below — part-month pay cannot be switched on with nothing to prorate.");
    }

    /** The toggle and the components are ONE save, or the server says no. */
    onProrationToggle(ev) {
        const on = !!ev.target.checked;
        this.set("use_proration", on);
        if (!on) {
            this.commit(["use_proration"]);
            return;
        }
        if ((this.v.proration_component_ids || []).length) {
            this.commit(["use_proration", "proration_component_ids"]);
        }
        // Otherwise wait: the note says what is still needed, and picking the
        // first component is what sends both.
    }

    hasProrated(id) {
        return (this.v.proration_component_ids || []).includes(id);
    }

    toggleProrated(id) {
        const current = (this.v.proration_component_ids || []).slice();
        const at = current.indexOf(id);
        if (at >= 0) { current.splice(at, 1); } else { current.push(id); }
        this.set("proration_component_ids", current);
        if (this.v.use_proration && !current.length) {
            // Taking the last one out would be refused. Switch part-month pay
            // off in the same breath rather than leaving a refusal on screen.
            this.set("use_proration", false);
        }
        this.commit(["use_proration", "proration_component_ids"]);
    }

    // ==================================================================
    // Back-pay
    // ==================================================================
    /** The same shape of refusal as part-month pay: it needs a target (SC12). */
    get retroIncomplete() {
        return !!this.v.use_auto_retro && !this.v.retro_component_id;
    }

    get retroNote() {
        return _t("Choose the component the back-pay is paid as — it cannot be switched on without one.");
    }

    onRetroToggle(ev) {
        const on = !!ev.target.checked;
        this.set("use_auto_retro", on);
        if (!on || this.v.retro_component_id) {
            this.commit(["use_auto_retro", "retro_component_id"]);
        }
    }

    onRetroComponent(ev) {
        const raw = ev.target.value;
        this.set("retro_component_id", raw ? Number(raw) : false);
        if (this.v.use_auto_retro && !this.v.retro_component_id) {
            // Clearing the target would be refused. Switch back-pay off in the
            // same breath rather than leaving a refusal on screen.
            this.set("use_auto_retro", false);
        }
        this.commit(["use_auto_retro", "retro_component_id"]);
    }

    // ==================================================================
    // The source lanes
    // ==================================================================
    get lanes() {
        const labels = laneLabels();
        const counts = this.meta.source_lane_counts || {};
        const on = {
            api: this.v.source_api_enabled !== false,
            excel: this.v.source_excel_enabled !== false,
            records: this.v.source_records_enabled !== false,
        };
        return laneOrder(this.v.source_priority).map((key, index) => ({
            key,
            rank: index + 1,
            count: counts[key] || 0,
            on: on[key],
            label: labels[key].label,
            sub: labels[key].sub,
        }));
    }

    get laneSentence() { return laneSentence(this.lanes); }
    get laneWarnings() { return laneWarnings(this.lanes); }

    moveLane(key, direction) {
        const order = laneOrder(this.v.source_priority);
        const from = order.indexOf(key);
        const to = from + direction;
        if (from < 0 || to < 0 || to >= order.length) { return; }
        [order[from], order[to]] = [order[to], order[from]];
        this.set("source_priority", order.join(","));
        this.commit(["source_priority"]);
    }

    toggleLane(key) {
        const field = "source_" + key + "_enabled";
        this.set(field, this.v[field] === false);
        this.commit([field]);
    }

    /** Arrow keys reorder a lane without ever reaching for the mouse. */
    onLaneKeydown(key, ev) {
        if (ev.key === "ArrowUp") { ev.preventDefault(); this.moveLane(key, -1); }
        if (ev.key === "ArrowDown") { ev.preventDefault(); this.moveLane(key, 1); }
    }

    // ==================================================================
    // Lists
    // ==================================================================
    get structures() { return this.meta.structures || []; }
    get connectors() { return this.meta.connectors || []; }
    get journals() { return this.meta.journals || []; }
    get accounts() { return this.meta.accounts || []; }
    get components() { return this.meta.components || []; }

    componentLabel(row) {
        return row.name || row.code || row.col || "";
    }
}


/**
 * The last page of an EDIT sitting — what changed, and one button.
 *
 * Deliberately not the six-step Finish page. That page asks "may this be
 * finished" and answers with a gate about checks and evidence; none of that
 * applies to somebody who came in to change an accounting journal. This one
 * answers the only question an edit leaves open: what did I just change?
 */
export class StepSaved extends Component {
    static template = "pb_blueprint.StepSaved";
    static props = {
        changes: { type: Array },            // [{field, label, before, after}]
        configName: { type: String, optional: true },
        schemeState: { type: String, optional: true },
        schemeStateLabel: { type: String, optional: true },
        locks: { type: Object, optional: true },
        busy: { type: Boolean, optional: true },
        onSave: { type: Function },
        onGrid: { type: Function },
    };

    ic(name, size = 16) { return ic(name, size); }

    get changes() { return this.props.changes || []; }

    get lead() {
        if (!this.changes.length) {
            return _t("Nothing has been changed in this sitting. Closing here leaves the configuration exactly as you found it.");
        }
        return this.changes.length === 1
            ? _t("One change was saved as you made it. Here it is.")
            : _t("%s changes were saved as you made them. Here they are.",
                 this.changes.length);
    }

    get note() {
        if (this.props.locks && this.props.locks.pay_logic) {
            return _t("Nothing about what people are paid was touched — the pay rules of this configuration are read-only here.");
        }
        return _t("Every change was written as you made it, so there is nothing left to save.");
    }
}
