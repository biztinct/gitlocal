/** @odoo-module **/
/**
 * Agency staff's doors — all by registry or `patch()` (no edit of another
 * module):
 *   1. People › "Agency staff" lens, sequence 59 (S8 facts §9).
 *   2. ⌘K rows 4470–4471.
 *   3. The People headcount line: "+12 agency staff" BESIDE the headcount,
 *      never added to it (ruling J5). Shown only when there are any.
 *   4. The agency's drawer in Vendors lists the people it supplies (template
 *      inheritance; the data comes from `pb.vendors.get_vendor`).
 */
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { openHub } from "@pb_hub/js/hub_nav";
import { PbPeople } from "@pb_people/js/people";
import { PbAgencyStaff } from "@pb_agency_staff/js/agency_staff";

export const AGENCY_GATE = ["hr.group_hr_user"];
const HUB_XMLID = "pb_people_hub.action_pb_people_hub";

registry.category(PEOPLE_LENSES).add("agency", {
    key: "agency",
    icon: "building",
    label: _t("Agency staff"),
    title: _t("People an agency supplies — not on your payroll"),
    Component: PbAgencyStaff,
    groups: AGENCY_GATE,
}, { sequence: 59 });

const palette = registry.category("pb_hub_palette");
palette.add("agency_staff", {
    id: "agency_staff",
    label: _t("Agency staff"),
    sublabel: _t("People"),
    icon: "building",
    groups: AGENCY_GATE,
    requires: "pb_agency_staff",
    action: { xmlid: HUB_XMLID, lens: "agency" },
    keywords: ["agency", "outsourced", "contractor", "nhân sự thuê ngoài", "outsourcing"],
}, { sequence: 4470 });

patch(PbPeople.prototype, {
    get glance() {
        const out = super.glance;
        const n = (this.state.kpis || {}).agency_staff || 0;
        if (!n) { return out; }
        const extra = {
            key: "agency", n: "+" + Number(n).toLocaleString(), label: _t("agency staff"), tone: "",
            run: () => openHub(this.action, { xmlid: HUB_XMLID, lens: "agency" }),
        };
        return [out[0], extra, ...out.slice(1)];
    },
});
