/** @odoo-module **/
/**
 * `pb_learning_hub` — GROW › Learning (LEARNING L0, 2026-10-21).
 *
 * Everything a company teaches its people, in one place:
 *
 *     overview · my learning · courses · assigned · required · tests ·
 *     claims · numbers
 *
 * Training used to be one tab inside Talent (NAV P2). The owner moved it out
 * (ledger LD3): Talent keeps goals, growth and praise; Learning gets its own
 * rail. This hub ships NO lens of its own — each tab is registered by the
 * module that owns the board (`LEARNING_LENSES`; `pb_training` registers all
 * eight today), so the dependency runs one way only. With nothing registered
 * the shell shows its own honest empty state.
 *
 * Everybody opens it: a plain employee sees MY LEARNING and nothing else (the
 * other tabs carry the training team's groups, so the shell leaves them off
 * the rail), and `defaultLens: "overview"` falls back to the first tab this
 * reader can use (`HubShell._resolveAccess`).
 *
 * `config` is built ONCE per instance, never in a getter (W21).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";
import { HUB_LENS_GATES } from "@pb_hub/js/hub_gates";

/**
 * Where a module bolts its board onto Learning.
 *
 *     registry.category(LEARNING_LENSES).add("courses", {
 *         key, icon, label, title?, Component, groups, probe?, feature?,
 *         props?,                                       // or:
 *         propsFromContext(ctx) { return { ... }; },    // read the arrival
 *     }, { sequence: 30 });
 *
 * Overview 10, My learning 20, Courses 30, Assigned 40, Required 50,
 * Tests 60, Claims 70, Numbers 80.
 */
export const LEARNING_LENSES = "pb_learning_hub_lens";

export const LEARNING_HUB_XMLID = "pb_learning_hub.action_pb_learning_hub";

export class PbLearningHub extends Component {
    static template = "pb_learning_hub.PbLearningHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        this.config = {
            key: "learning",                 // -> pbhub.learning.lens.v1
            brand: { label: _t("Learning"), icon: "graduationCap" },
            defaultLens: "overview",
            cog: () => this.openSettings(),
            lenses: this.extraLenses(),
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(LEARNING_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Learning"), xmlid: LEARNING_HUB_XMLID },
        });
    }
}

registry.category("actions").add("pb_learning_hub", PbLearningHub);

// The tabs' gates, so a lesson and the Access board can say "not for you"
// before anybody opens the hub.
registry.category(HUB_LENS_GATES).add("pb_learning_hub", () => [
    ...registry.category(LEARNING_LENSES).getAll(),
]);
