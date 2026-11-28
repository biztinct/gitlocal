/** @odoo-module **/
/**
 * The Plan lens — a mount point, and DELIBERATELY nothing more.
 *
 * WHAT THIS FILE USED TO BE, AND WHY IT IS NOW SHORT
 *
 * Until this release the Plan lens was a card grid over seven screens that
 * belonged to the old workforce planning module: scenarios, forecasts, pay
 * grades, a merit matrix, compensation cycles and a component-tagging wizard.
 * The owner's ruling at the time was that those screens got a menu change and
 * no product change, so the lens knew two things about each of them — an
 * action id and the groups that could read the model behind it — and opened
 * exactly what the retired rail item used to open.
 *
 * Every one of those seven has since been replaced by something built on this
 * product's own engine: planning by the Decision Room, pay grades and the
 * merit matrix by the Pay area's bands and guidance, compensation cycles by
 * the pay review, and the tagging wizard by the payroll engine classifying its
 * own components. The old module is gone, so the cards are gone with it — a
 * card that opens nothing is the worst screen this product can show.
 *
 * What is left is the registry a planning product bolts itself onto, and an
 * empty state that says what to do when nothing has.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** Who is offered the Plan lens when no planning product has registered. */
export const PLAN_GATE = [
    "pb_decision_room.group_decision_user",
    "pb_decision_room.group_decision_manager",
];

/**
 * Where a planning PRODUCT bolts itself onto the Plan lens.
 *
 *     registry.category(PLAN_HERO).add("decision_room", {
 *         id, Component, groups,
 *     }, { sequence: 10 });
 *
 * A REGISTRY rather than an import, for the reason the hub's own lens registry
 * exists: `pb_decision_room` depends on this module, so this module cannot
 * import it back without a cycle no manifest can express.
 */
export const PLAN_HERO = "pb_people_hub_plan_hero";

/** The groups the registered hero is offered to, for the lens gate. */
export function heroGroups() {
    return [...new Set(registry.category(PLAN_HERO).getAll()
        .flatMap((h) => h.groups || []))];
}

export class PlanLauncher extends Component {
    static template = "pb_people_hub.PlanLauncher";
    static props = {
        embedded: { type: Boolean, optional: true },
        arrival: { type: Object, optional: true },
        "*": true,
    };

    setup() {
        // Read ONCE, in setup. The props handed on are memoised for the same
        // reason the hub memoises a lens's: a getter returning a fresh object
        // makes OWL see the child's props as changed on every repaint.
        this.hero = registry.category(PLAN_HERO).getAll()[0] || null;
        this.heroProps = { inPlan: true, arrival: this.props.arrival || null };

        this.state = useState({ resolved: false });

        onWillStart(async () => { this.state.resolved = true; });
    }

    ic(n, s = 17) { return ic(n, s); }

    // ----------------------------------------------------------------- empty
    get emptyTitle() { return _t("Planning is not open to you."); }

    get emptyNote() {
        return _t("Planning the year — what it costs to hire, what a raise "
                  + "does to the margin, what the company can afford — is "
                  + "read by the planning roles. Your account holds none of "
                  + "them.");
    }
}
