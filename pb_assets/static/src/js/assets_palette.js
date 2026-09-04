/** @odoo-module **/
/**
 * The register's two doors.
 *
 *   1. **The People hub's Assets lens.** Registered into `pb_people_hub`'s lens
 *      registry rather than imported into its config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back. It sits at sequence 50 — after Records (40) and
 *      before the Plan launcher the hub ships last, which is the right place in
 *      the story: who works here, what their record says, what they were given,
 *      and then what we plan to spend.
 *
 *      Its gate is this module's OWN tier list and not `hr.employee`'s: the
 *      register is not employee data, and a person who may read the roster has
 *      no business knowing which laptop is out of warranty. The facade refuses
 *      independently — `pb.assets._can_read()` answers an EXPLAINED empty board
 *      rather than an access dialog — so the gate here only decides whether the
 *      lens is offered at all.
 *
 *   2. **⌘K palette rows**, in the 2200 deep-link block, clear of P0's
 *      2100-2120. The door is an XMLID and not a bare tag: a bare tag is
 *      synthesised with no action NAME, so anything returning through a
 *      breadcrumb lands on a crumb labelled "Unnamed".
 *
 * The lens icon is `package` — added to the shared `ic()` registry in this same
 * change, never to a module-local map.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { PbAssetsBoard } from "@pb_assets/js/assets_board";

/** Who is offered the register. The facade decides who actually gets it. */
export const ASSETS_GATE = [
    "pb_assets.group_assets_user",
    "pb_assets.group_assets_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

registry.category(PEOPLE_LENSES).add("assets", {
    key: "assets",
    icon: "package",
    label: _t("Assets"),
    Component: PbAssetsBoard,
    groups: ASSETS_GATE,
}, { sequence: 50 });

const HUB_XMLID = "pb_people_hub.action_pb_people_hub";

const palette = registry.category("pb_hub_palette");

palette.add("peoplehub_assets", {
    id: "peoplehub_assets",
    label: _t("Assets"),
    sublabel: _t("People"),
    icon: "package",
    groups: ASSETS_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_assets",
    action: { xmlid: HUB_XMLID, lens: "assets" },
}, { sequence: 2200 });

palette.add("assets_requests", {
    id: "assets_requests",
    label: _t("Asset requests"),
    sublabel: _t("Assets"),
    icon: "inbox",
    groups: ASSETS_GATE,
    requires: "pb_assets",
    action: { xmlid: "pb_assets.action_pb_asset_request" },
}, { sequence: 2210 });

palette.add("assets_categories", {
    id: "assets_categories",
    label: _t("Asset categories"),
    sublabel: _t("Assets"),
    icon: "layers",
    groups: ["pb_assets.group_assets_manager", "base.group_system"],
    requires: "pb_assets",
    action: { xmlid: "pb_assets.action_pb_asset_category" },
}, { sequence: 2220 });
