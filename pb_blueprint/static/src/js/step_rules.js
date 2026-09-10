/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { RULE_TABS } from "./recipe_text";
import { STEP_META } from "./blueprint_steps";
import { ComponentsTab } from "./components_tab";
import { TaxTab } from "./tax_tab";
import { CalendarTab } from "./calendar_tab";
import { EvidenceChip } from "./evidence_chip";

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
    static components = { ComponentsTab, TaxTab, CalendarTab, EvidenceChip };
    static props = {
        configId: { type: [Number, Boolean] },
        revision: { type: Number, optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        sampleName: { type: String, optional: true },
        currency: { type: String, optional: true },
        reloadKey: { type: Number, optional: true },
        templateName: { type: String, optional: true },
        tab: { type: String, optional: true },
        // A "Go" link on the Finish step asked for one component by id: the
        // Components tab opens its editor on arrival and then says it has,
        // so a second render does not reopen what somebody just closed.
        openRule: { type: Number, optional: true },
        openTick: { type: Number, optional: true },
        onTab: { type: Function },
        onChanged: { type: Function },
        onRevision: { type: Function },
        onGrid: { type: Function },
        onGoTest: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            tab: this.props.tab || "components",
            // Whether the checks still match these rules. Read here as well as
            // on the Test step because this is where somebody CHANGES a rule,
            // and the moment they do, evidence taken before it stops being
            // evidence — saying so where the change happened is the whole point.
            evidence: null,
            // A number the Tax tab changes has to move the row on the
            // Components tab too, so the two never disagree about what a
            // person is paid. Bumping this reloads whichever tab is next shown.
            crossTick: 0,
        });

        onWillStart(() => this.loadEvidence());
        onWillUpdateProps((next) => {
            if (next.reloadKey !== this.props.reloadKey) { this.loadEvidence(); }
        });
    }

    /** Never fatal: a chip that cannot be read is a chip that is not shown. */
    async loadEvidence() {
        if (!this.props.configId) { return; }
        try {
            const res = await this.orm.call("pb.blueprint.studio", "bp_evidence",
                                            [this.props.configId]);
            this.state.evidence = res && res.ok ? res : null;
        } catch (e) {
            this.state.evidence = null;
        }
    }

    /** Only worth the room once somebody has actually run the checks. */
    get showEvidence() {
        const e = this.state.evidence;
        return !!(e && e.ever_run);
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
        // A rule just moved, so the evidence may have gone stale in the same
        // breath. Re-read rather than wait for the next visit.
        this.loadEvidence();
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
