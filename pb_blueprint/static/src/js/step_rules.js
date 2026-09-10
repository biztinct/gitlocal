/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { RULE_TABS } from "./recipe_text";
import { STEP_META } from "./blueprint_steps";
import { ComponentsTab } from "./components_tab";
import { TaxTab } from "./tax_tab";
import { CalendarTab } from "./calendar_tab";

/**
 * Step 2 — what goes into pay.
 *
 * Three tabs, and each one answers a different question about the same
 * configuration. **Components**: what is paid and taken off, every line as a
 * sentence. **Tax & protection**: the shared rules underneath those lines, and
 * where they come from. **Calendar & payment**: when the money is worked out
 * and how it leaves the bank.
 */
export class StepRules extends Component {
    static template = "pb_blueprint.StepRules";
    static components = { ComponentsTab, TaxTab, CalendarTab };
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
        this.state = useState({
            tab: this.props.tab || "components",
            // A number the Tax tab changes has to move the row on the
            // Components tab too, so the two never disagree about what a
            // person is paid. Bumping this reloads whichever tab is next shown.
            crossTick: 0,
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    get TABS() { return RULE_TABS; }
    get meta() { return STEP_META.rules; }

    onTab(key) {
        this.state.tab = key;
        this.props.onTab(key);
    }

    /** Every tab reloads when another one has changed a shared number. */
    get tick() {
        return (this.props.reloadKey || 0) + this.state.crossTick;
    }

    onSubChanged(res) {
        this.state.crossTick++;
        this.props.onChanged(res);
    }

    /** "Review the insurance components" — the same list, already filtered. */
    onComponents(what) {
        this.state.tab = "components";
        this.props.onTab("components");
        this.componentSearch = what === "ins" ? _t("insurance") : "";
        this.state.crossTick++;
    }

    get search() { return this.componentSearch || ""; }
}
