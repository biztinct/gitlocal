/** @odoo-module **/
/**
 * `pb_lifecycle_hub` — the Lifecycle mission, on the shared HubShell.
 *
 * One lens today:
 *
 *     journeys
 *
 * and a REGISTRY where P5 (Probation), P6 (PIP) and P10 (Contract lifecycle)
 * bolt theirs on. A registry rather than an import, and the direction of the
 * dependency is the whole reason: those modules will depend on this hub because
 * they are mounted inside it, so this hub cannot import them back without a
 * cycle no manifest can express. The mechanism is `pb_people_hub`'s, copied
 * verbatim — absent module, absent lens, no error.
 *
 *     import { LIFECYCLE_LENSES } from "@pb_lifecycle/js/lifecycle_hub";
 *     registry.category(LIFECYCLE_LENSES).add("probation", {
 *         key, icon, label, Component, groups,
 *         propsFromContext(ctx) { return { ... }; },   // optional
 *     }, { sequence: 20 });
 *
 * `propsFromContext` exists because <HubShell/> hands a lens only
 * `{embedded, ...def.props}` and never the action — so a lens that needs the
 * deep link reads the arrival context ONCE here, at config time, which is also
 * what keeps the lens props identity-stable across renders (W21).
 *
 * ---------------------------------------------------------------------------
 * THE GATE (W95: derived from the model behind the door, never copied from the
 * rail item that opens it)
 *
 *   journeys   `pb.journeys._can_read()` — the three lifecycle tiers. Restated
 *              here as `LIFECYCLE_GATE` because the Python/JS boundary cannot
 *              be imported across; the facade still enforces its own (W12), and
 *              it answers an EMPTY BOARD rather than an access dialog, which is
 *              why the RAIL item beside it is deliberately ungated.
 * ---------------------------------------------------------------------------
 *
 * `config` is built ONCE per instance, never in a getter (W21).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";

import { PbJourneys } from "@pb_lifecycle/js/journeys";

/** `pb.journeys._can_read()`'s tiers, verbatim. */
export const LIFECYCLE_GATE = [
    "pb_lifecycle.group_lifecycle_user",
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

/** Where a later phase bolts a lens onto this hub. */
export const LIFECYCLE_LENSES = "pb_lifecycle_lenses";

export class PbLifecycleHub extends Component {
    static template = "pb_lifecycle.PbLifecycleHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");

        this.config = {
            key: "lifecycle",                 // -> pbhub.lifecycle.lens.v1
            brand: { label: _t("Lifecycle"), icon: "refresh" },
            defaultLens: "journeys",
            cog: () => this.openSettings(),
            lenses: [
                { key: "journeys", icon: "list", label: _t("Journeys"),
                  Component: PbJourneys, groups: LIFECYCLE_GATE },
                // Bolted-on lenses sit after the board every one of them is a
                // detail of.
                ...this.extraLenses(),
            ],
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(LIFECYCLE_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            // By XMLID: a bare tag reaches the shell with no action NAME, and
            // anything returning through a breadcrumb reads "Unnamed" (W98).
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Lifecycle"),
                    xmlid: "pb_lifecycle.action_pb_lifecycle_hub" },
        });
    }
}

registry.category("actions").add("pb_lifecycle_hub", PbLifecycleHub);
