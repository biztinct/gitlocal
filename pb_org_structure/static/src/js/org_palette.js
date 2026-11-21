/** @odoo-module **/
/**
 * The Jobs tab's doors: a People hub lens (sequence 58, between Exits 56 and
 * the agency-staff lens S8-B puts at 59) and ⌘K rows in this phase's block
 * 4500–4560. Every door is an XMLID, never a bare tag (a bare tag reaches a
 * breadcrumb as "Unnamed").
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { PbOrgJobs } from "@pb_org_structure/js/org_board";

/** Who is OFFERED the tab; `pb.org.structure` checks again on every call. */
export const ORG_GATE = [
    "hr.group_hr_user",
    "hr.group_hr_manager",
    "pb_hiring.group_hiring_manager",
    "base.group_system",
];

registry.category(PEOPLE_LENSES).add("jobs", {
    key: "jobs",
    icon: "briefcase",
    label: _t("Jobs"),
    Component: PbOrgJobs,
    groups: ORG_GATE,
    wantsArrival: true,
}, { sequence: 58 });

const HUB_XMLID = "pb_people_hub.action_pb_people_hub";
const palette = registry.category("pb_hub_palette");

palette.add("org_jobs", {
    id: "org_jobs",
    label: _t("Jobs"),
    sublabel: _t("People"),
    icon: "briefcase",
    groups: ORG_GATE,
    requires: "pb_org_jobs",
    action: { xmlid: HUB_XMLID, lens: "jobs" },
    keywords: ["job levels", "cost centre", "cost center", "pause hiring", "cấp bậc", "trung tâm chi phí"],
}, { sequence: 4500 });

palette.add("org_cost_centres", {
    id: "org_cost_centres",
    label: _t("Cost centres"),
    sublabel: _t("Jobs"),
    icon: "wallet",
    groups: ORG_GATE,
    requires: "pb_org_jobs",
    action: { xmlid: HUB_XMLID, lens: "jobs", focus: "cost" },
    keywords: ["cost center", "pusat biaya"],
}, { sequence: 4510 });

palette.add("org_hiring_pause", {
    id: "org_hiring_pause",
    label: _t("Pause hiring"),
    sublabel: _t("Jobs"),
    icon: "pause",
    groups: ORG_GATE,
    requires: "pb_org_jobs",
    action: { xmlid: HUB_XMLID, lens: "jobs", focus: "pause" },
    keywords: ["hiring freeze", "freeze"],
}, { sequence: 4520 });
