/** @odoo-module **/
/**
 * "Where they work", as a lens on the People hub.
 *
 * WHY THIS FILE EXISTS. Until TIDY P1 this screen had no door a person could
 * see. It could be reached from ⌘K, from a chip on somebody's card, and from
 * a bookmark — and a person looking for it opened People, read
 * "Employees · Contracts · Records · Pay · Plan", and concluded the product
 * did not have it. A ⌘K row is a shortcut for somebody who already knows the
 * name of the thing; it is not a door (TIDY rule 11).
 *
 * It sits at sequence 48: after Pay (45), before Plan (last). The order the
 * lenses read in is the order a person exists in payroll — who works here,
 * on what terms, what we hold about them, what they are paid, WHERE they work
 * it, and what we plan next.
 *
 * A SEPARATE FILE FROM THE PALETTE, because the two are different promises:
 * the palette names doors, this registers a surface. The gate is shared and
 * declared once, in the palette, so a role that may open the ⌘K row is
 * exactly the role that is offered the lens.
 *
 * The registry, rather than an import from the hub, is the direction of the
 * dependency: `pb_workseg` depends on `pb_people_hub` (it is mounted inside
 * it) and the hub knows nothing about this module. An absent module is an
 * absent lens and no error.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { PbAssignmentsScreen } from "@pb_workseg/js/assignments";
import { WORKSEG_GATE } from "@pb_workseg/js/workseg_palette";

registry.category(PEOPLE_LENSES).add("where", {
    key: "where",
    icon: "mapPin",
    label: _t("Where they work"),
    Component: PbAssignmentsScreen,
    groups: WORKSEG_GATE,
    // The deep link can be more specific than the lens: "Same person?" is
    // this screen with a different focus, and the shell hands the arrival
    // payload only to a lens that has said it reads one.
    wantsArrival: true,
}, { sequence: 48 });
