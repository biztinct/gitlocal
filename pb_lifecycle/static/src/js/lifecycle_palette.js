/** @odoo-module **/
/**
 * The Lifecycle module's rows in the global ⌘K palette.
 *
 * NAV P2 (2026-10-21): the Lifecycle hub is retired. Its boards live in
 * People, Hiring and Talent; Journeys opens on its own and from Settings › HR.
 * The rows below open Journeys (`pb_journeys`) directly.
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
import { LIFECYCLE_GATE, JOURNEYS_XMLID } from "@pb_lifecycle/js/lifecycle_hub";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";

const palette = registry.category("pb_hub_palette");
// NAV P2: the Lifecycle hub is retired (its tag is a redirector). Journeys
// opens on its own, from Settings › HR and from these rows.
const JOURNEYS_TAG = "pb_journeys";
const ADMIN = ["pb_lifecycle.group_lifecycle_admin", "base.group_system"];
const MANAGER = [
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

// ---------------------------------------------------------- Journeys itself
// NAV P2: the row keeps its id (recents) and the old word "lifecycle".
palette.add("lifecycle", {
    id: "lifecycle",
    label: _t("Journeys"),
    sublabel: _t("Settings › HR"),
    icon: "refresh",
    groups: LIFECYCLE_GATE,
    action: { xmlid: JOURNEYS_XMLID },
    requires: JOURNEYS_TAG,
    keywords: ["lifecycle", "vòng đời", "hành trình"],
}, { sequence: 2095 });

// ------------------------------------------------- Settings › HR › Journeys
// NAV P2: the journey board and its checklists are set-up work, so they sit
// in the HR group of Settings. One card, so the category title opens it.
registry.category(SETTINGS_CATEGORIES).add("journeys", {
    key: "journeys",
    group: "hr",
    icon: "refresh",
    label: _t("Journeys"),
    blurb: _t("Everything that has to happen when somebody joins, leaves or finishes probation."),
    groups: LIFECYCLE_GATE,
    cards: [{
        id: "journeys",
        tag: JOURNEYS_TAG,
        icon: "list",
        label: _t("Journeys"),
        sub: _t("Each person's steps, with a date and a name beside every one."),
    }],
}, { sequence: 45 });

// ------------------------------------------------------------- deep links
palette.add("lifecycle_start", {
    id: "lifecycle_start",
    label: _t("Start a journey"),
    sublabel: _t("Journeys"),
    icon: "plus",
    groups: LIFECYCLE_GATE,
    action: { xmlid: JOURNEYS_XMLID },
    requires: JOURNEYS_TAG,
}, { sequence: 2100 });

palette.add("lifecycle_templates", {
    id: "lifecycle_templates",
    label: _t("Journey checklists"),
    sublabel: _t("Journeys"),
    icon: "list",
    group: G_ADMIN,
    groups: ADMIN,
    action: { xmlid: "pb_lifecycle.action_journey_template" },
    requires: JOURNEYS_TAG,
}, { sequence: 2110 });

palette.add("lifecycle_letters", {
    id: "lifecycle_letters",
    label: _t("Letters"),
    sublabel: _t("Journeys"),
    icon: "fileText",
    groups: MANAGER,
    action: { xmlid: "pb_lifecycle.action_hr_letter" },
    requires: JOURNEYS_TAG,
}, { sequence: 2120 });
