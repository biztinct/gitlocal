/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { EvidenceChip } from "./evidence_chip";
import { lastRunLine } from "./outputs_text";

/**
 * The pay panel, on the Test step only: a scoreboard.
 *
 * Everywhere else the panel answers "what is this doing to somebody's pay". On
 * the step whose whole subject is confidence, that is the wrong question — the
 * one worth the same space is "how much of this is proven, and how fresh is the
 * proof". Leaving the step puts the normal hero back; nothing is lost, the
 * panel simply reports whatever the step it is beside is about.
 */
export class Scoreboard extends Component {
    static template = "pb_blueprint.Scoreboard";
    static components = { EvidenceChip };
    static props = {
        tests: { type: [Object, Boolean], optional: true },
        running: { type: Boolean, optional: true },
        onRun: { type: Function },
    };

    setup() {
        // Below 1200px the pay panel is a bottom bar and its body is hidden
        // until it is opened — the same disclosure the hero uses, because on a
        // phone an open panel covers the step you came to walk. Without a bar
        // of its own the scoreboard would simply not be there (found in the
        // browser at 500px, where `.pbbp-pay-body` is `display: none`).
        this.state = useState({ open: false });
    }

    ic(name, size = 16) { return ic(name, size); }

    toggleOpen() { this.state.open = !this.state.open; }

    get tests() { return this.props.tests || {}; }
    get tally() { return this.tests.tally || {}; }
    get evidence() { return this.tests.evidence || {}; }

    get passed() { return Number(this.tally.passed || 0); }
    get attention() { return Number(this.tally.attention || 0); }
    get pending() { return Number(this.tally.pending || 0); }
    get checks() { return Number(this.tests.checks || 0); }

    /**
     * "12 / 12" — the whole answer, in the size the take-home figure had.
     *
     * Before anybody has pressed Run there is deliberately NO score. Each
     * scenario does carry a standing of its own, and the list below shows it,
     * but a standing is a comparison made the last time the numbers were worked
     * out — and with nothing stamped, nothing can say whether that was before
     * or after the last change to the rules. A confident "5 / 5" over evidence
     * that says "not checked yet" is the contradiction B4 spent a defect
     * learning to avoid (BP39).
     */
    get scored() { return !!this.evidence.ever_run && this.checks > 0; }

    get score() {
        if (!this.scored) { return "—"; }
        return `${this.passed} / ${this.checks}`;
    }

    get scoreWord() {
        if (!this.checks) { return _t("Nothing to check yet"); }
        if (!this.scored) { return _t("not checked yet"); }
        // Amber alone does not say WHEN, and a score over rules that have since
        // moved has to say when or it reads as a promise about now.
        if (this.evidence.stale) { return _t("passed — before the change"); }
        if (this.attention) { return _t("passed — the rest need attention"); }
        if (this.pending) { return _t("passed — the rest are waiting for you"); }
        return _t("passed");
    }

    get tone() {
        if (!this.scored) { return ""; }
        if (this.evidence.stale) { return "is-stale"; }
        if (this.attention) { return "is-bad"; }
        if (this.pending) { return "is-wait"; }
        if (this.checks && this.passed === this.checks) { return "is-good"; }
        return "";
    }

    get lastRun() { return lastRunLine(this.evidence); }

    /** Said under the counters, and only when there is a next thing to do. */
    get nextStep() {
        if (!this.checks) {
            return _t("Add the boundary cases this configuration branches on, and the checks have something to run against.");
        }
        if (this.evidence.stale) {
            return _t("Something changed since the last run. Run the checks again so the evidence matches the rules.");
        }
        if (!this.evidence.ever_run) {
            return _t("Press “Run the checks”. Nothing is changed by running them.");
        }
        if (this.attention) {
            return _t("Open the ones that need attention — each says which component disagreed, and by how much.");
        }
        if (this.pending) {
            return _t("Confirm the numbers you expect, and these count as evidence rather than as a guess.");
        }
        return _t("Every check passed against the rules as they are right now.");
    }
}
