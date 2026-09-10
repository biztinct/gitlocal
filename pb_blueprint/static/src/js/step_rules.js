/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { RULE_TABS } from "./recipe_text";
import { STEP_META } from "./blueprint_steps";
import { ComponentsTab } from "./components_tab";

/**
 * Step 2 — what goes into pay.
 *
 * Three tabs. **Components** is the whole of this release: every pay component
 * as a sentence you can change. **Tax & protection** and **Calendar & payment**
 * are honest panels — they say what arrives next, and they offer the door that
 * works today rather than pretending to be empty.
 */
export class StepRules extends Component {
    static template = "pb_blueprint.StepRules";
    static components = { ComponentsTab };
    static props = {
        configId: { type: [Number, Boolean] },
        revision: { type: Number, optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        sampleName: { type: String, optional: true },
        currency: { type: String, optional: true },
        reloadKey: { type: Number, optional: true },
        templateName: { type: String, optional: true },
        tab: { type: String, optional: true },
        onTab: { type: Function },
        onChanged: { type: Function },
        onRevision: { type: Function },
        onGrid: { type: Function },
    };

    setup() {
        this.state = useState({ tab: this.props.tab || "components" });
    }

    ic(name, size = 16) { return ic(name, size); }

    get TABS() { return RULE_TABS; }
    get meta() { return STEP_META.rules; }

    onTab(key) {
        this.state.tab = key;
        this.props.onTab(key);
    }

    /** The heading of the tab you are standing on. */
    get panelTitle() {
        return {
            tax: _t("Tax and the protections that come with pay"),
            calendar: _t("When pay is worked out, and how it is sent"),
        }[this.state.tab] || "";
    }

    get panelLead() {
        return {
            tax: _t("The income-tax bands, the reliefs and the insurance caps this configuration uses."),
            calendar: _t("The day inputs close, the day people are paid, and how the money leaves the bank."),
        }[this.state.tab] || "";
    }

    get panelNote() {
        return {
            tax: _t("Arrives in the next release — the starter's tax values are already in place and you can see them in the grid."),
            calendar: _t("Arrives in the next release — pay runs already follow the company's own calendar until then."),
        }[this.state.tab] || "";
    }

    get panelIcon() {
        return this.state.tab === "tax" ? "shield" : "calendar";
    }
}
