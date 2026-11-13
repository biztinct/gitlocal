/** @odoo-module **/
/**
 * The Org chart, as a lens on the People hub.
 *
 * Sequence 30: right after Employees (the cockpit is always first), before
 * Contracts (38) and Records (40) — who works here, then who they report to,
 * then on what terms (ORGCHART_LEDGER §1).
 *
 * The gate is the hub's own EMPLOYEE_GATE, imported rather than restated:
 * whoever may read the roster may read the chart drawn from it.
 *
 * The registry, rather than an import from the hub, is the direction of the
 * dependency: pb_orgchart depends on pb_people_hub and the hub knows nothing
 * about this module. An absent module is an absent lens and no error.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PEOPLE_LENSES, EMPLOYEE_GATE } from "@pb_people_hub/js/people_hub";
import { PbOrgChart } from "@pb_orgchart/js/orgchart";

registry.category(PEOPLE_LENSES).add("orgchart", {
    key: "orgchart",
    icon: "network",
    label: _t("Org chart"),
    title: _t("Org chart · who reports to whom"),
    Component: PbOrgChart,
    groups: EMPLOYEE_GATE,
    // P4: ⌘K rows say what they meant ("me", "plan", "suggest") in the
    // arrival payload; the shell hands it only to a lens that asks for it.
    wantsArrival: true,
}, { sequence: 30 });
