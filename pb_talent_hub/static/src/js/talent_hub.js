/** @odoo-module **/
/**
 * `pb_talent_hub` — GROW › Talent (NAV P2, 2026-10-21).
 *
 * How people grow, in one place:
 *
 *     goals · growth · praise
 *
 * Before NAV P2 these boards lived on two hubs (People had Goals and Praise,
 * the Lifecycle hub had Growth plans). Training was a fourth tab until
 * LEARNING L0 (2026-10-21) gave it its own entry, GROW › Learning; an old
 * link that asks this hub for `pb_lens: "training"` is sent there, to
 * Learning › Courses, without drawing Talent first (R10). This hub
 * ships NO lens of its own: each tab is registered by the module that owns
 * the board (`TALENT_LENSES`), so a company without one of them simply has a
 * tab fewer, and the dependency runs one way only. With nothing registered
 * the shell shows its own honest empty state.
 *
 * No product switch on the hub: each part is sold with the product, and the
 * Growth tab carries the Lifecycle switch on the lens itself (`feature`).
 *
 * `config` is built ONCE per instance, never in a getter (W21).
 */
import { Component, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";
import { HUB_LENS_GATES } from "@pb_hub/js/hub_gates";

/**
 * Where a module bolts its board onto Talent.
 *
 *     registry.category(TALENT_LENSES).add("goals", {
 *         key, icon, label, Component, groups, probe?, feature?,
 *         propsFromContext(ctx) { return { ... }; },   // optional
 *     }, { sequence: 10 });
 *
 * Goals 10, Growth 20, Praise 40 (30 was Training until LEARNING L0).
 */
export const TALENT_LENSES = "pb_talent_hub_lens";

/** Where an old "Talent › Training" link lands since LEARNING L0. */
export const TRAINING_REDIRECT = {
    xmlid: "pb_learning_hub.action_pb_learning_hub",
    lens: "courses",
};

/** True when the arrival asks for the Training tab Talent no longer has. */
export function asksForTraining(ctx) {
    return !!ctx && ctx.pb_lens === "training";
}

export class PbTalentHub extends Component {
    static template = "pb_talent_hub.PbTalentHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        const ctx = (this.props.action && this.props.action.context) || {};
        // R10: Training moved to GROW › Learning. Draw nothing and hand the
        // reader over once mounted (a redirect from inside a mounting
        // action is not safe before mount). Named by xmlid string: this
        // module does not depend on the Learning hub.
        this.redirecting = asksForTraining(ctx);
        if (this.redirecting) {
            onMounted(() => openHub(this.actionService, {
                ...TRAINING_REDIRECT,
                focus: ctx.pb_focus || "",
                back: ctx.pb_back || null,
            }));
        }
        this.config = {
            key: "talent",                   // -> pbhub.talent.lens.v1
            brand: { label: _t("Talent"), icon: "target" },
            defaultLens: "goals",
            cog: () => this.openSettings(),
            lenses: this.extraLenses(),
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(TALENT_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Talent"), xmlid: "pb_talent_hub.action_pb_talent_hub" },
        });
    }
}

registry.category("actions").add("pb_talent_hub", PbTalentHub);

// The tabs' gates, so a lesson and the Access board can say "not for you"
// before anybody opens the hub.
registry.category(HUB_LENS_GATES).add("pb_talent_hub", () => [
    ...registry.category(TALENT_LENSES).getAll(),
]);
