/** @odoo-module **/
/**
 * `pb_talent_hub` — GROW › Talent (NAV P2, 2026-10-21).
 *
 * How people grow, in one place:
 *
 *     goals · growth · training · praise
 *
 * Before NAV P2 these four boards lived on three hubs (People had Goals and
 * Praise, the Lifecycle hub had Growth plans, Learn had Training). This hub
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
import { Component } from "@odoo/owl";
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
 * Goals 10, Growth 20, Training 30, Praise 40.
 */
export const TALENT_LENSES = "pb_talent_hub_lens";

export class PbTalentHub extends Component {
    static template = "pb_talent_hub.PbTalentHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        this.config = {
            key: "talent",                   // -> pbhub.talent.lens.v1
            brand: { label: _t("Talent"), icon: "graduationCap" },
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
