/** @odoo-module **/

import { Component } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";
import { STEP_META } from "./blueprint_steps";

/**
 * Steps 2 to 5, as they stand today.
 *
 * These are HONEST placeholders, not empty pages: each one carries the real
 * heading and the real promise of the step, says plainly that the tools for it
 * arrive in the next release, and offers the door that works right now — the
 * components grid. Pay rules goes further and lists the components that were
 * actually seeded, so the step proves the configuration exists rather than
 * asking the reader to take it on trust.
 */
export class StepThin extends Component {
    static template = "pb_blueprint.StepThin";
    static props = {
        step: { type: String },
        components: { type: Array, optional: true },
        counts: { type: Object, optional: true },
        templateName: { type: String, optional: true },
        onGrid: { type: Function },
        onImport: { type: Function },
    };

    ic(name, size = 16) { return ic(name, size); }

    get meta() { return STEP_META[this.props.step] || STEP_META.rules; }

    get showsComponents() { return this.props.step === "rules"; }

    get components() { return this.props.components || []; }

    /** What arrives next, in the words of the step you are standing on. */
    get promise() {
        switch (this.props.step) {
            case "rules":
                return _t("Writing each component as a plain sentence — and editing tax bands, reliefs and the pay calendar — arrives in the next release.");
            case "connect":
                return _t("Pointing inputs at the systems that already hold them, and arranging the payslip, arrives in the next release.");
            case "outputs":
                return _t("The full table of every component, its calculation and its value for the sample employee arrives in the next release.");
            default:
                return _t("Running the awkward cases — joiners, leavers, tax-band edges — arrives in the next release.");
        }
    }

    get door() {
        return _t("Your components are ready in the grid. Open it any time with Skip to the grid.");
    }

    typeLabel(t) {
        if (t === "input") return _t("Input");
        if (t === "constant") return _t("Fixed value");
        return _t("Calculated");
    }

    /** Empty is a state with words, never a blank box. */
    get emptyLine() {
        return _t("This configuration has no components yet. That is expected on a blank canvas — add them in the grid, or import a workbook.");
    }

    /**
     * A configuration with nothing in it needs the two doors that FILL it, not
     * just a sentence naming them. Cancelling the workbook review left a draft
     * with zero components and no way back to the review — the empty state
     * described a door that did not exist.
     */
    get isEmpty() { return !this.components.length; }
}
