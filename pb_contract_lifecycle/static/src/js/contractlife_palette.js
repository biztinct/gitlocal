/** @odoo-module **/
/**
 * The Contracts lens's doors.
 *
 *   1. **The Lifecycle hub's Contracts lens.** Registered into P0's lens
 *      registry rather than imported into its config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back. The shipped Journeys lens carries no sequence,
 *      P3's New joiners took 20, P4's Exits 30, P5's Probation 40 and P6's
 *      Growth plans 50, so Contracts takes **60** — which is right in the
 *      story as well as in the number: everything running, the people
 *      arriving, the people leaving, the people being decided about, the
 *      people being helped, and then the agreements underneath all of it.
 *
 *      The LABEL is "Contracts", nine characters, which measures the same as
 *      the People hub's own shipped "Contracts" lens in the 60px rail box
 *      (R63/R84). "Contract lifecycle" and "Contracts & interns" were both
 *      measured and both spill.
 *
 *      Its gate is P0's tier list, restated here because the Python/JS
 *      boundary cannot be imported across. `pb.contractlife._can_read()`
 *      enforces it independently and answers an EXPLAINED empty board rather
 *      than an access dialog, so this only decides whether the lens is
 *      OFFERED.
 *
 *   2. **⌘K palette rows**, in the **3100** deep-link block. P9 took 3000-3030
 *      and said P10 starts at 3100 (R98). Every door is an XMLID and never a
 *      bare tag: a bare tag is synthesised with no action NAME, so anything
 *      returning through a breadcrumb lands on a crumb labelled "Unnamed".
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LIFECYCLE_LENSES, LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";
import { PbContractLifeBoard } from "@pb_contract_lifecycle/js/contractlife_board";

registry.category(LIFECYCLE_LENSES).add("contracts", {
    key: "contracts",
    icon: "scrollText",
    label: _t("Contracts"),
    Component: PbContractLifeBoard,
    groups: LIFECYCLE_GATE,
}, { sequence: 60 });

const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";
const MANAGER = [
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

const palette = registry.category("pb_hub_palette");

palette.add("contracts_board", {
    id: "contracts_board",
    label: _t("Contracts ending soon"),
    sublabel: _t("Lifecycle"),
    icon: "scrollText",
    groups: LIFECYCLE_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_contractlife_board",
    action: { xmlid: HUB_XMLID, lens: "contracts" },
}, { sequence: 3100 });

palette.add("contracts_decisions", {
    id: "contracts_decisions",
    label: _t("Decisions needed"),
    sublabel: _t("Contracts"),
    icon: "checkCircle",
    groups: MANAGER,
    requires: "pb_contractlife_board",
    action: { xmlid: "pb_contract_lifecycle.action_pb_contract_review" },
}, { sequence: 3110 });

palette.add("contracts_extensions", {
    id: "contracts_extensions",
    label: _t("Extension requests"),
    sublabel: _t("Contracts"),
    icon: "rotate",
    groups: MANAGER,
    requires: "pb_contractlife_board",
    action: { xmlid: "pb_contract_lifecycle.action_pb_contract_extension" },
}, { sequence: 3120 });
