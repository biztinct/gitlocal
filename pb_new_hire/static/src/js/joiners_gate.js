/** @odoo-module **/
/**
 * NEWHIRE P8 E — the New joiners tab and its ⌘K row also open for the narrow
 * "New joiners board" right (implied by the HR manager role). Each entry gets
 * its OWN copy of the gate: the shared Lifecycle gate array is never changed,
 * so nothing else of Lifecycle opens. Access previews read these same gates.
 */
import { registry } from "@web/core/registry";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";

export const JOINERS_BOARD_GROUP = "pb_new_hire.group_joiners_board";

function widen(category, key) {
    const reg = registry.category(category);
    if (!reg.contains(key)) {
        return;
    }
    const entry = reg.get(key);
    if (Array.isArray(entry.groups) && !entry.groups.includes(JOINERS_BOARD_GROUP)) {
        entry.groups = [...entry.groups, JOINERS_BOARD_GROUP];
    }
}

widen(PEOPLE_LENSES, "newjoiners");
widen("pb_hub_palette", "onboarding_newjoiners");
