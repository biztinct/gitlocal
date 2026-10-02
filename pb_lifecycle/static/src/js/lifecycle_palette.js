/** @odoo-module **/
/**
 * The Lifecycle mission's rows in the global ⌘K palette.
 *
 * Four entries, and they obey the two rules the seed file's header sets out:
 *
 *  1. **Every gate mirrors the rail item that owns the same door.** The rail's
 *     Lifecycle item is deliberately UNGATED — the hub's facade answers an empty
 *     board with an explanation rather than an access dialog — so the mission
 *     row here is ungated too. The three DEEP LINKS are gated, because they open
 *     native admin screens whose ACL really would refuse (W29/W95).
 *  2. **No entry names a door that does not exist here.** Each xmlid row carries
 *     a `requires` tag from this same module, which is the presence probe the
 *     palette service runs before offering it.
 *
 * Sequences: the mission block is 110-180 and Lifecycle is 190, which is the
 * number the platform contract reserves for it. Deep links live in the 2000
 * band; ours are 2100-2120, clear of the seed file's 2010-2360.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { G_ADMIN } from "@pb_hub/js/hub_palette_entries";
import { LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";

const palette = registry.category("pb_hub_palette");
const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";
const ADMIN = ["pb_lifecycle.group_lifecycle_admin", "base.group_system"];
const MANAGER = [
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

// ------------------------------------------------------------- the mission
palette.add("lifecycle", {
    id: "lifecycle",
    label: _t("Lifecycle"),
    sublabel: _t("Journeys"),
    icon: "refresh",
    action: { xmlid: HUB_XMLID },
    requires: "pb_lifecycle_hub",
}, { sequence: 190 });

// ------------------------------------------------------------- deep links
palette.add("lifecycle_start", {
    id: "lifecycle_start",
    label: _t("Start a journey"),
    sublabel: _t("Lifecycle"),
    icon: "plus",
    groups: LIFECYCLE_GATE,
    action: { xmlid: HUB_XMLID, lens: "journeys" },
    requires: "pb_lifecycle_hub",
}, { sequence: 2100 });

palette.add("lifecycle_templates", {
    id: "lifecycle_templates",
    label: _t("Journey checklists"),
    sublabel: _t("Lifecycle"),
    icon: "list",
    group: G_ADMIN,
    groups: ADMIN,
    action: { xmlid: "pb_lifecycle.action_journey_template" },
    requires: "pb_lifecycle_hub",
}, { sequence: 2110 });

palette.add("lifecycle_letters", {
    id: "lifecycle_letters",
    label: _t("Letters"),
    sublabel: _t("Lifecycle"),
    icon: "fileText",
    groups: MANAGER,
    action: { xmlid: "pb_lifecycle.action_hr_letter" },
    requires: "pb_lifecycle_hub",
}, { sequence: 2120 });
