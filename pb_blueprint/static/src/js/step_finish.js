/** @odoo-module **/

import { Component } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";
import { AUDIENCES, REALLIFE, STEP_META } from "./blueprint_steps";

/**
 * Step 6 — everything you decided, on one page.
 *
 * Finishing marks the SETUP complete. It does not activate the configuration
 * for real pay runs: that stays the existing, separately checked step, and the
 * line under the button says so, because "Finish" that quietly starts paying
 * people is the single worst thing this screen could do.
 */
export class StepFinish extends Component {
    static template = "pb_blueprint.StepFinish";
    static props = {
        config: { type: Object },
        blueprint: { type: Object },
        counts: { type: Object },
        busy: { type: Boolean, optional: true },
        error: { type: [String, Boolean], optional: true },
        onFinish: { type: Function },
    };

    ic(name, size = 16) { return ic(name, size); }

    get meta() { return STEP_META.finish; }

    get tiles() {
        const c = this.props.counts || {};
        return [
            { key: "components", icon: "layers", value: c.components || 0,
              label: _t("Components") },
            { key: "formulas", icon: "sigma", value: c.formulas || 0,
              label: _t("Calculated components") },
            { key: "inputs", icon: "table", value: c.inputs || 0,
              label: _t("Inputs to collect") },
        ];
    }

    /** The situations, back in the words they were chosen with. */
    get chips() {
        const s = this.props.blueprint.situations || {};
        const out = [];
        for (const a of AUDIENCES) {
            if ((s.audiences || []).includes(a.key)) out.push(a.label);
        }
        for (const r of REALLIFE) {
            if ((s.reallife || []).includes(r.key)) out.push(r.label);
        }
        return out;
    }

    get rows() {
        const c = this.props.config;
        const b = this.props.blueprint;
        return [
            { label: _t("Name"), value: c.name },
            { label: _t("Reference"), value: c.code, mono: true },
            { label: _t("Company"), value: c.company },
            { label: _t("Country"), value: c.country_label || c.country_code },
            { label: _t("Kind of pay run"), value: c.cycle_label },
            { label: _t("Effective from"), value: b.effective_from || _t("Not set") },
            { label: _t("Started from"), value: b.template_name || _t("Blank canvas") },
        ];
    }

    get finished() { return this.props.blueprint.state === "finished"; }
}
