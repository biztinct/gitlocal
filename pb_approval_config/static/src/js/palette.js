/** @odoo-module **/
/**
 * The Approval Matrix's doors.
 *
 *   1. **One panel behind the Settings cog.** Registered into `pb_settings`'s
 *      soft registry (`SETTINGS_CATEGORIES`) rather than imported into its
 *      descriptor, because the dependency runs the other way: this module
 *      depends on the hub, so the hub cannot import this one back.
 *
 *      The shipped categories carry no sequence, so bolted-on ones start at
 *      20; Vendors took 20 and the Group took 30, so approvals sit at **40**.
 *
 *   2. **Palette rows in the 3400 block**, which the ledger allocated to this
 *      programme: the Matrix (3400), People & backups (3410) and the inbox
 *      (3420). Every door is an XMLID and never a bare tag — a bare tag is
 *      synthesised with no action NAME, so anything returning through a
 *      breadcrumb lands on a crumb labelled "Unnamed".
 *
 * NO NEW RAIL ITEM. The rail is eight missions on purpose and `pb_sidebar`'s
 * own test asserts it exactly. Setting approvals up is a job done rarely, so
 * the cog is its door; DECIDING one is done daily, and that lives on Home,
 * where the Approvals lens already is.
 *
 * THE GATE IS THE FACADE'S, RESTATED ONCE. A gate that drifts from
 * `pb.approval.matrix`'s produces either a door that can only make an access
 * dialog or a screen the people it was built for cannot find.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbApprovalMatrix } from "@pb_approval_config/js/matrix_room";
import { PbInbox } from "@pb_approval_config/js/inbox";

/** `pb.approval.matrix`'s own gate, plus the system escape it also grants. */
export const APPROVAL_CONFIG_GATE = [
    "biz_approval_workflow.group_approval_config",
    "biz_approval_workflow.group_approval_publish",
    "biz_approval_workflow.group_approval_admin",
    "base.group_system",
];

/** Deciding is everybody's: the inbox shows each person only their own. */
export const APPROVAL_INBOX_GATE = [];

// =========================================================== the one panel

const categories = registry.category(SETTINGS_CATEGORIES);

categories.add("approvals", {
    key: "approvals",
    icon: "workflow",
    label: _t("Approvals"),
    blurb: _t("Who signs off what, for each part of the business — and who "
              + "stands in when they are away."),
    groups: APPROVAL_CONFIG_GATE,
    cards: [{
        id: "matrix",
        xmlid: "pb_approval_config.action_pb_approval_matrix",
        icon: "workflow",
        label: _t("Approval Matrix"),
        sub: _t("Every process that can need a sign-off, the route it "
                + "follows, and where each one applies."),
    }, {
        id: "inbox",
        xmlid: "pb_approval_config.action_pb_approval_inbox",
        icon: "inbox",
        label: _t("Approvals inbox"),
        sub: _t("Everything waiting for a decision, from every part of the "
                + "product."),
    }],
}, { sequence: 40 });

// ================================================================== the ⌘K

const palette = registry.category("pb_hub_palette");

palette.add("approval_matrix", {
    id: "approval_matrix",
    label: _t("Approval Matrix"),
    sublabel: _t("Settings"),
    icon: "workflow",
    groups: APPROVAL_CONFIG_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_approval_matrix",
    action: { xmlid: "pb_approval_config.action_pb_approval_matrix" },
}, { sequence: 3400 });

palette.add("approval_people", {
    id: "approval_people",
    label: _t("People & backups"),
    sublabel: _t("Approvals"),
    icon: "users",
    groups: APPROVAL_CONFIG_GATE,
    requires: "pb_approval_matrix",
    // `focus` is what makes a row more specific than its screen: this one
    // lands on the responsibilities grid rather than the top of the page.
    action: { xmlid: "pb_approval_config.action_pb_approval_matrix",
              focus: "people" },
}, { sequence: 3410 });

palette.add("approval_inbox", {
    id: "approval_inbox",
    label: _t("Approvals"),
    sublabel: _t("Decide"),
    icon: "inbox",
    requires: "pb_approval_inbox",
    action: { xmlid: "pb_approval_config.action_pb_approval_inbox" },
}, { sequence: 3420 });

// The components are imported so this file's `requires` probes have something
// to find — the registry entries themselves are made in their own files.
export { PbApprovalMatrix, PbInbox };
