/** @odoo-module **/
/**
 * Change job's ⌘K rows, in the 4460–4469 block reserved for it (WDGAP S8
 * facts §9). Every door is an XMLID, never a bare tag (a bare tag returns
 * through a breadcrumb labelled "Unnamed").
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { JOB_CHANGE_GATE } from "@pb_job_change/js/job_change_patches";

const palette = registry.category("pb_hub_palette");

palette.add("job_change_new", {
    id: "job_change_new",
    label: _t("Change someone's job"),
    sublabel: _t("People"),
    icon: "briefcase",
    groups: JOB_CHANGE_GATE,
    requires: "pb_job_change",
    action: { xmlid: "pb_job_change.action_pb_job_change_new" },
    keywords: ["promotion", "transfer", "pay change", "thăng chức", "điều chuyển", "promosi", "mutasi"],
}, { sequence: 4460 });

palette.add("job_change_board", {
    id: "job_change_board",
    label: _t("Job changes"),
    sublabel: _t("People"),
    icon: "briefcase",
    groups: JOB_CHANGE_GATE,
    requires: "pb_job_change",
    action: { xmlid: "pb_job_change.action_pb_job_change" },
}, { sequence: 4461 });
