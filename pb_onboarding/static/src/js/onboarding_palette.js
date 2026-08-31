/** @odoo-module **/
/**
 * The New joiners lens's two doors.
 *
 *   1. **The Lifecycle hub's New joiners lens.** Registered into P0's lens
 *      registry rather than imported into its config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back. The shipped Journeys lens carries no sequence, so
 *      bolted-on lenses start at 20 (platform contract) — and 20 is right in
 *      the story as well as in the number: the board of everything running
 *      first, then the one board that is about people rather than cases.
 *
 *      Its gate is P0's tier list, restated here because the Python/JS
 *      boundary cannot be imported across. `pb.onboarding._can_read()` enforces
 *      it independently and answers an EXPLAINED empty board rather than an
 *      access dialog, so this only decides whether the lens is OFFERED.
 *
 *   2. **⌘K palette rows**, in the 2300 deep-link block, clear of P0's
 *      2100-2120 and P2's 2200-2220. The door is an XMLID and never a bare
 *      tag: a bare tag is synthesised with no action NAME, so anything
 *      returning through a breadcrumb lands on a crumb labelled "Unnamed".
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LIFECYCLE_LENSES, LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";
import { PbOnboardingBoard } from "@pb_onboarding/js/onboarding_board";

registry.category(LIFECYCLE_LENSES).add("newjoiners", {
    key: "newjoiners",
    icon: "sunrise",
    label: _t("New joiners"),
    Component: PbOnboardingBoard,
    groups: LIFECYCLE_GATE,
}, { sequence: 20 });

const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";

const palette = registry.category("pb_hub_palette");

palette.add("onboarding_newjoiners", {
    id: "onboarding_newjoiners",
    label: _t("New joiners"),
    sublabel: _t("Lifecycle"),
    icon: "sunrise",
    groups: LIFECYCLE_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_onboarding_board",
    action: { xmlid: HUB_XMLID, lens: "newjoiners" },
}, { sequence: 2300 });

palette.add("onboarding_sessions", {
    id: "onboarding_sessions",
    label: _t("Welcome sessions"),
    sublabel: _t("New joiners"),
    icon: "calendar",
    groups: LIFECYCLE_GATE,
    requires: "pb_onboarding_board",
    action: { xmlid: "pb_onboarding.action_pb_orientation_batch" },
}, { sequence: 2310 });

palette.add("onboarding_hrbp_rules", {
    id: "onboarding_hrbp_rules",
    label: _t("HR partner rules"),
    sublabel: _t("New joiners"),
    icon: "users",
    groups: ["pb_lifecycle.group_lifecycle_admin", "base.group_system"],
    requires: "pb_onboarding_board",
    action: { xmlid: "pb_onboarding.action_pb_hrbp_rule" },
}, { sequence: 2320 });
