/** @odoo-module **/

import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { evidenceChip, lastRunLine } from "./outputs_text";

/**
 * "Passed 12 checks" · "Changed since the last check — run it again".
 *
 * One component, mounted on three different steps, so the answer to "is what we
 * checked still true" is worded identically wherever a person meets it. The
 * chip is a BUTTON when somebody can act on it and a plain span when they
 * cannot: a control that does nothing is worse than a label.
 */
export class EvidenceChip extends Component {
    static template = "pb_blueprint.EvidenceChip";
    static props = {
        evidence: { type: [Object, Boolean], optional: true },
        // Given only where running the checks from here makes sense.
        onRun: { type: Function, optional: true },
        busy: { type: Boolean, optional: true },
        showWhen: { type: Boolean, optional: true },
        // What the button half says. On the Test step it runs them; on the Pay
        // rules step it walks you to where they are run, and saying "Run again"
        // there would promise something this chip does not do.
        goLabel: { type: String, optional: true },
    };

    ic(name, size = 14) { return ic(name, size); }

    get evidence() { return this.props.evidence || {}; }

    get chip() { return evidenceChip(this.evidence); }

    get lastRun() { return lastRunLine(this.evidence); }

    get goLabel() { return this.props.goLabel || _t("Run again"); }

    /**
     * On the Pay rules step the chip is only worth space when it has something
     * to say — a configuration nobody has checked yet is not a warning, it is
     * simply a configuration somebody is still building.
     */
    get visible() {
        if (this.props.showWhen !== undefined) {
            return this.props.showWhen;
        }
        return !!(this.evidence.ever_run);
    }

    onClick() {
        if (this.props.onRun && !this.props.busy) {
            this.props.onRun();
        }
    }
}
