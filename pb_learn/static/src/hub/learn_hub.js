/** @odoo-module **/
/**
 * `learn_hub` — the Learn mission, on the shared HubShell.
 *
 * WHY A HUB AT ALL, WHEN THERE WAS ONLY ONE SCREEN. Because there is about to
 * be more than one. "Learn" on the rail has meant exactly one thing since the
 * Journey shipped: the product lessons — how to run a pay run, what a mapping
 * is. RIZE Wave 2 adds the OTHER kind of learning a company does: the courses
 * an employer puts its own people through. Both are learning, both belong
 * behind the same door, and neither is a sub-item on the rail (the platform
 * contract has no rail sub-items — sub-navigation is the hub lens rail).
 *
 * ONE LENS TODAY:
 *
 *     lessons
 *
 * which is the existing `LearnJourney`, mounted unchanged. The Journey's own
 * component takes `props = ["*"]`, so the shell's `embedded: true` reaches it
 * and is ignored — the Journey draws its own hero because it IS the lesson
 * map, not a cockpit with a title bar over it. Nothing about the Journey
 * changes; it simply now has a shell around it.
 *
 * AND A REGISTRY where `pb_training` bolts its HR lens on. A registry rather
 * than an import, and the direction of the dependency is the whole reason:
 * `pb_training` depends on this module because it is mounted inside it, so
 * this module cannot import it back without a cycle no manifest can express.
 * The mechanism is `pb_home_hub`'s (R83) and `pb_lifecycle`'s, copied
 * verbatim — absent module, absent lens, no error.
 *
 *     import { LEARN_LENSES } from "@pb_learn/hub/learn_hub";
 *     registry.category(LEARN_LENSES).add("training", {
 *         key, icon, label, Component, groups,
 *         propsFromContext(ctx) { return { ... }; },   // optional
 *     }, { sequence: 20 });
 *
 * The one shipped lens carries no sequence, so bolted-on ones start at 20 and
 * land after it.
 *
 * THE OLD DOOR STILL WORKS. `pb_learn.action_learn_journey` is named BY NAME
 * from the Coach, the first-login greeting, the scenario runner, PayAI and a
 * ⌘K row, so it is deliberately left exactly as it was: the Journey remains a
 * client action of its own that opens full-screen. What changed is only which
 * action the RAIL opens, and the rail item claims both tags so either one
 * keeps the Learn entry lit (R126).
 *
 * `config` is built ONCE per instance, never in a getter: HubShell's `config`
 * prop must keep a stable identity or every render recreates every lens (the
 * refetch trap, W21).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";

import { LearnJourney } from "@pb_learn/journey/journey";

/** Where a later module bolts a lens onto Learn. */
export const LEARN_LENSES = "pb_learn_lens";

export class LearnHub extends Component {
    static template = "pb_learn.LearnHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.config = {
            key: "learn",                     // -> pbhub.learn.lens.v1
            brand: { label: _t("Learn"), icon: "bookOpen" },
            defaultLens: "lessons",
            lenses: [
                // UNGATED, and that is the Journey's own answer. A gated leaf
                // hides itself from the people who cannot use the screen it
                // teaches — which is right for a working screen and exactly
                // wrong for a learning one. The Journey marks a station "not
                // in your menu" rather than hiding it, and the rail item it
                // replaces ships no `groups_id` either.
                { key: "lessons", icon: "bookOpen", label: _t("Lessons"),
                  Component: LearnJourney },
                ...this.extraLenses(),
            ],
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(LEARN_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }
}

registry.category("actions").add("learn_hub", LearnHub);
