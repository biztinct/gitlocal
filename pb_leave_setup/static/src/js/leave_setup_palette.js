/** @odoo-module **/
/**
 * The doors into the Kinds of leave screen (WDGAP S5-A).
 *
 *   1. Settings › HR › "Kinds of leave". A soft-registry category: the
 *      registry key is WRITTEN OUT, not imported, so this module does not
 *      depend on pb_settings (the pb_training / pb_clock precedent). A test
 *      reads pb_settings' own source and fails if the two spellings ever stop
 *      agreeing. HR categories: Hiring 40, Journeys 45, Learning 47 — this
 *      one is 42. One card, so the category opens the screen directly.
 *   2. ⌘K rows in the 3800 block after the Time Off rows (3800-3820).
 *
 * The doors are XMLIDs, never bare tags (R180). `requires` is the presence
 * probe: the actions registry holding this module's tag says its JS shipped.
 * The gates are hints; `pb.leave.setup` decides on the server.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/** `pb.leave.setup._can_read`, restated as a hint. */
export const LEAVE_SETUP_GATE = [
    "hr_holidays.group_hr_holidays_user",
    "hr_holidays.group_hr_holidays_manager",
    "hr.group_hr_manager",
    "om_hr_payroll.group_hr_payroll_manager",
    "base.group_system",
];
const XMLID = "pb_leave_setup.action_pb_leave_kinds";

registry.category("pb_settings_category").add("leave_kinds", {
    key: "leave_kinds",
    group: "hr",
    icon: "umbrella",
    label: _t("Kinds of leave"),
    blurb: _t("Every kind of leave people can take, how it is paid and how the days build up."),
    groups: LEAVE_SETUP_GATE,
    cards: [{
        id: "leave_kinds",
        xmlid: XMLID,
        icon: "umbrella",
        label: _t("Kinds of leave"),
        sub: _t("Add, review and switch on kinds of leave, with ready-made kinds for each country."),
    }],
}, { sequence: 42 });

const palette = registry.category("pb_hub_palette");

palette.add("wf_leave_kinds", {
    id: "wf_leave_kinds",
    label: _t("Kinds of leave"),
    sublabel: _t("Settings"),
    icon: "umbrella",
    groups: LEAVE_SETUP_GATE,
    requires: "pb_leave_kinds",
    action: { xmlid: XMLID },
}, { sequence: 3830 });

palette.add("wf_leave_starters", {
    id: "wf_leave_starters",
    label: _t("Ready-made kinds of leave"),
    sublabel: _t("Kinds of leave"),
    icon: "sparkles",
    groups: LEAVE_SETUP_GATE,
    requires: "pb_leave_kinds",
    // the palette hands `lens` over as `context[lensKey]` (pb_hub hub_nav)
    action: { xmlid: XMLID, lens: "starters", lensKey: "pb_leave_open" },
}, { sequence: 3840 });
