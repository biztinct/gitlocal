/** @odoo-module **/
/**
 * The Exits lens's doors.
 *
 *   1. **The Lifecycle hub's Exits lens.** Registered into P0's lens registry
 *      rather than imported into its config, because the dependency runs the
 *      other way: this module depends on the hub, so the hub cannot import
 *      this one back. The shipped Journeys lens carries no sequence and P3's
 *      New joiners lens took 20, so Exits takes 30 — which is right in the
 *      story as well as in the number: everything running, then the people
 *      arriving, then the people leaving.
 *
 *      Its gate is P0's tier list, restated here because the Python/JS
 *      boundary cannot be imported across. `pb.exits._can_read()` enforces it
 *      independently and answers an EXPLAINED empty board rather than an
 *      access dialog, so this only decides whether the lens is OFFERED.
 *
 *   2. **⌘K palette rows**, in the 2500 deep-link block.
 *
 *      `pb_hub/js/hub_palette_entries` auto-numbers its seeded deep links
 *      `DEEP_LINK_BASE + (i + 1) * 10`, which runs to 2370 and grows every
 *      time somebody adds a row; P2 took 2200-2220 (on top of seeded entries),
 *      P3 moved to 2400-2420, and P4 onwards starts at 2500 (R41). Count the
 *      seed file rather than trusting the comment in it.
 *
 *      Every door is an XMLID and never a bare tag: a bare tag is synthesised
 *      with no action NAME, so anything returning through a breadcrumb lands
 *      on a crumb labelled "Unnamed".
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LIFECYCLE_LENSES, LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";
import { PbExitsBoard } from "@pb_offboarding/js/exits_board";

registry.category(LIFECYCLE_LENSES).add("exits", {
    key: "exits",
    icon: "powerOff",
    label: _t("Exits"),
    Component: PbExitsBoard,
    groups: LIFECYCLE_GATE,
}, { sequence: 30 });

const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";
const ADMIN = ["pb_lifecycle.group_lifecycle_admin", "base.group_system"];
const MANAGER = [
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

const palette = registry.category("pb_hub_palette");

palette.add("offboarding_exits", {
    id: "offboarding_exits",
    label: _t("Exits"),
    sublabel: _t("Lifecycle"),
    icon: "powerOff",
    groups: LIFECYCLE_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_exits_board",
    action: { xmlid: HUB_XMLID, lens: "exits" },
}, { sequence: 2500 });

palette.add("offboarding_resignations", {
    id: "offboarding_resignations",
    label: _t("Resignations"),
    sublabel: _t("Exits"),
    icon: "fileText",
    groups: MANAGER,
    requires: "pb_exits_board",
    action: { xmlid: "pb_offboarding.action_pb_resignation" },
}, { sequence: 2510 });

palette.add("offboarding_clearances", {
    id: "offboarding_clearances",
    label: _t("Exit clearances"),
    sublabel: _t("Exits"),
    icon: "shieldCheck",
    groups: MANAGER,
    requires: "pb_exits_board",
    action: { xmlid: "pb_offboarding.action_pb_exit_clearance" },
}, { sequence: 2520 });

palette.add("offboarding_handover", {
    id: "offboarding_handover",
    label: _t("Handover items"),
    sublabel: _t("Exits"),
    icon: "arrowLeftRight",
    groups: MANAGER,
    requires: "pb_exits_board",
    action: { xmlid: "pb_offboarding.action_pb_kt_item" },
}, { sequence: 2530 });

palette.add("offboarding_notice", {
    id: "offboarding_notice",
    label: _t("Notice policies"),
    sublabel: _t("Exits"),
    icon: "calendar",
    groups: ADMIN,
    requires: "pb_exits_board",
    action: { xmlid: "pb_offboarding.action_pb_notice_policy" },
}, { sequence: 2540 });
