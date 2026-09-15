/** @odoo-module **/
/**
 * The Hiring lens's doors.
 *
 *   1. **The Lifecycle hub's Hiring lens.** Registered into P0's lens
 *      registry rather than imported into its config, because the dependency
 *      runs the other way: this module depends on the hub, so the hub cannot
 *      import this one back.
 *
 *      SEQUENCE 10, AND IT IS FIRST FOR A REASON. New joiners took 20, Exits
 *      30, Probation 40, Growth plans 50, Contracts 60. Hiring happens
 *      BEFORE somebody joins, so it belongs before the lens about their
 *      arrival — the rail then reads as the order of a working life.
 *
 *      The LABEL is "Hiring", six characters, comfortably inside the 60px
 *      rail label box (R63/R84). "Recruitment" was measured and spills, the
 *      same way "Recognition" and "Improvement" did.
 *
 *      Its gate is P0's tier list, restated here because the Python/JS
 *      boundary cannot be imported across. `pb.hiring._can_read()` enforces
 *      the real one independently — and is WIDER, because a department head
 *      who holds no lifecycle group may still raise a request — so this only
 *      decides whether the lens is OFFERED on the hub.
 *
 *   2. **A Settings category**, "Hiring", holding the one thing an
 *      administrator sets up: who recruits for which company and country.
 *      It is a single-card category, so the hub's own `soleCard` rule opens
 *      the list directly instead of drawing a section page whose only
 *      content is that door. The card is an XMLID rather than a client
 *      action tag — `_cardPresent` accepts either, and an xmlid needs no
 *      twenty-line client action whose whole body is a `doAction`.
 *
 *   3. **⌘K palette rows**, in the **3500** deep-link block. Wave 1 ran to
 *      3200 and the Approval Matrix, Pay and Work-segment modules took up to
 *      3450, so Wave 2 starts here. Every door is an XMLID and never a bare
 *      tag: a bare tag is synthesised with no action NAME, so anything
 *      returning through a breadcrumb lands on a crumb labelled "Unnamed".
 *
 * Every icon is from the shared `ic()` registry in pb_import_kit — no
 * module-local map, no emoji.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { LIFECYCLE_LENSES, LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";

registry.category(LIFECYCLE_LENSES).add("hiring", {
    key: "hiring",
    icon: "userPlus",
    label: _t("Hiring"),
    Component: PbHiringBoard,
    groups: LIFECYCLE_GATE.concat([
        "pb_hiring.group_hiring_user",
        "pb_hiring.group_hiring_manager",
        "pb_hiring.group_hiring_admin",
    ]),
}, { sequence: 10 });

const HUB_XMLID = "pb_lifecycle.action_pb_lifecycle_hub";
const HIRING_GATE = [
    "pb_hiring.group_hiring_user",
    "pb_hiring.group_hiring_manager",
    "pb_hiring.group_hiring_admin",
    "base.group_system",
];
const HIRING_ADMIN = [
    "pb_hiring.group_hiring_admin",
    "base.group_system",
];

/* ------------------------------------------------------------ Settings ---- */
// The eight shipped categories carry no sequence, so bolted-on ones start at
// 20. P11 took Vendors 20 and Access 30 (R119), so Hiring takes 40.
registry.category(SETTINGS_CATEGORIES).add("hiring", {
    key: "hiring",
    icon: "userPlus",
    label: _t("Hiring"),
    blurb: _t("Who picks a hiring request up once it has been agreed."),
    groups: HIRING_ADMIN,
    cards: [{
        id: "hiring_rules",
        xmlid: "pb_hiring.action_pb_hiring_country_rule",
        icon: "globe",
        label: _t("Hiring rules"),
        sub: _t("One line per company and country: the recruiter and their manager."),
    }],
}, { sequence: 40 });

/* ---------------------------------------------------------- command bar --- */
const palette = registry.category("pb_hub_palette");

palette.add("hiring_board", {
    id: "hiring_board",
    label: _t("Who we are hiring"),
    sublabel: _t("Lifecycle"),
    icon: "userPlus",
    groups: HIRING_GATE.concat(LIFECYCLE_GATE),
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_hiring_board",
    action: { xmlid: HUB_XMLID, lens: "hiring" },
}, { sequence: 3500 });

palette.add("hiring_requests", {
    id: "hiring_requests",
    label: _t("Hiring requests"),
    sublabel: _t("Hiring"),
    icon: "briefcase",
    groups: HIRING_GATE,
    requires: "pb_hiring_board",
    action: { xmlid: "pb_hiring.action_pb_hiring_requisition" },
}, { sequence: 3510 });

palette.add("hiring_jds", {
    id: "hiring_jds",
    label: _t("Job descriptions"),
    sublabel: _t("Hiring"),
    icon: "fileText",
    groups: HIRING_GATE,
    requires: "pb_hiring_board",
    action: { xmlid: "pb_hiring.action_pb_hiring_jd" },
}, { sequence: 3520 });

palette.add("hiring_referrals", {
    id: "hiring_referrals",
    label: _t("Referrals"),
    sublabel: _t("Hiring"),
    icon: "users",
    groups: HIRING_GATE,
    requires: "pb_hiring_board",
    action: { xmlid: "pb_hiring.action_pb_hiring_referral" },
}, { sequence: 3530 });

palette.add("hiring_rules", {
    id: "hiring_rules",
    label: _t("Hiring rules"),
    sublabel: _t("Hiring"),
    icon: "globe",
    groups: HIRING_ADMIN,
    requires: "pb_hiring_board",
    action: { xmlid: "pb_hiring.action_pb_hiring_country_rule" },
}, { sequence: 3540 });
