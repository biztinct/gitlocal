/** @odoo-module **/
/**
 * <HubTracker/> — the period chip on the command bar.
 *
 * Option B put a stage tracker in the RAIL and bet the whole IA on it. The
 * dossier's verdict was to keep the organ and drop the bet: the tracker becomes
 * a chip in a hub's command bar, so the lifecycle is visible without the
 * navigation depending on it being right.
 *
 * C1 ships the component and its contract only. `stage`/`total` are handed in by
 * the hub; nothing here computes a period, and nothing here calls the server —
 * the real period read arrives in Cycle 2. That order is deliberate: a tracker
 * that guesses is worse than no tracker ("stage tracking must be computed and
 * kept honest per period, or the WOW becomes a lie", IA dossier, Option B).
 *
 * Degradation is explicit rather than accidental: with no `stage` it renders the
 * label alone, so a hub that has a period name but not yet a stage still shows
 * the truth it has.
 */
import { Component } from "@odoo/owl";

export class HubTracker extends Component {
    static template = "pb_hub.HubTracker";
    static props = {
        // "Aug cycle" — already human, already localised by the hub
        label: { type: String },
        // 1-based stage; 0/absent means "no stage known yet"
        stage: { type: Number, optional: true },
        total: { type: Number, optional: true },
        // optional click-through, e.g. into the Close lens
        onClick: { type: Function, optional: true },
    };

    /** True only when BOTH numbers are usable — "stage 2/0" is not a fact. */
    get hasStage() {
        const { stage, total } = this.props;
        return !!stage && !!total && total > 0 && stage <= total;
    }

    get title() {
        return this.hasStage
            ? `${this.props.label} — stage ${this.props.stage} of ${this.props.total}`
            : this.props.label;
    }

    onClick() {
        if (this.props.onClick) { this.props.onClick(); }
    }
}
