/** @odoo-module **/
/**
 * `pb_people_hub` — the People mission, on Cycle 1's HubShell.
 *
 * Two lenses, in the order a person exists in payroll:
 *
 *     employees · plan
 *
 * Who works here, and what we expect the payroll to cost next year. The first
 * is the EXISTING Employees cockpit mounted with `embedded: true` (W17); the
 * second is a LAUNCHER over the seven Planning screens, which this cycle
 * changes in no way at all (see plan_launcher.js — that is an owner ruling,
 * not a shortcut).
 *
 * CONTRACTS IS A DOOR INSIDE EMPLOYEES, NOT A LENS BESIDE IT (owner, 2026-09-24:
 * "it is actually connected to an employee"). The Employees lens is handed a
 * `contractsDoor` — the gate and the click — and draws a Contracts button in
 * its header plus a per-person "their contract" control that opens the
 * contract drawer in place. The board itself opens as its own page through
 * `pb_people_hub.action_pb_people_contracts`, whose context carries the way
 * back to Employees.
 *
 * ---------------------------------------------------------------------------
 * The gates (W95: from the ACL of the model behind the door)
 *
 *   employees  `hr.employee`  — base.group_system | hr.group_hr_user |
 *              pb_demo.group_payobook_demo
 *   contracts  `hr.contract`  — hr_contract.group_hr_contract_employee_manager |
 *              hr_contract.group_hr_contract_manager |
 *              pb_demo.group_payobook_demo
 *              (no longer a lens: it gates the Contracts door inside
 *              Employees, so the button is never offered to someone the
 *              board would refuse)
 *   plan       any Workforce Planning tier; each CARD then carries its own
 *              model's gate, because the seven planning models do not all grant
 *              read to the same one.
 *
 * These are deliberately NOT the gates the retired rail items carried. Both
 * `item_employees` and `item_contracts` were gated at the pb_hr_payroll_base
 * officer/manager/super tiers, which is a different group family — a persona
 * holding the payroll tier and not the HR one saw the item, clicked it, and got
 * an access dialog. That is the exact defect W95 was written about, and the
 * rail has been shipping it.
 * ---------------------------------------------------------------------------
 *
 * `config` is built ONCE per instance, never in a getter (W21).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";
import { HUB_LENS_GATES } from "@pb_hub/js/hub_gates";

import { PbPeople } from "@pb_people/js/people";
import { PlanLauncher, PLAN_GATE, heroGroups } from "@pb_people_hub/js/plan_launcher";

/** `hr.employee`'s READ access. */
export const EMPLOYEE_GATE = [
    "base.group_system",
    "hr.group_hr_user",
    "pb_demo.group_payobook_demo",
];

/** `hr.contract`'s READ access. */
export const CONTRACT_GATE = [
    "hr_contract.group_hr_contract_employee_manager",
    "hr_contract.group_hr_contract_manager",
    "pb_demo.group_payobook_demo",
];

/**
 * Where a later module bolts a lens onto this hub.
 *
 *     registry.category(PEOPLE_LENSES).add("records", {
 *         key, icon, label, Component, groups,
 *         propsFromContext(ctx) { return { ... }; },   // optional
 *     }, { sequence: 40 });
 *
 * A REGISTRY rather than an import, and the direction of the dependency is the
 * whole reason: `pb_records` depends on this hub (it is mounted inside it), so
 * this hub cannot import `pb_records` back without a cycle no manifest can
 * express. The soft-registry pattern is the one `pb_people`'s employee drawer
 * already uses (`people.js:53`) — absent module, absent lens, no error.
 *
 * `propsFromContext` exists because <HubShell/> hands a lens only
 * `{embedded, ...def.props}` and never the action — so a lens that needs the
 * deep link ("open on these twelve people") gets it by reading the arrival
 * context ONCE here, at config time, which is also what keeps the lens props
 * identity-stable across renders (W21).
 */
export const PEOPLE_LENSES = "pb_people_hub_lens";

export class PbPeopleHub extends Component {
    static template = "pb_people_hub.PbPeopleHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");

        this.config = {
            key: "people",                    // -> pbhub.people.lens.v1
            brand: { label: _t("People"), icon: "users" },
            defaultLens: "employees",
            cog: () => this.openSettings(),
            lenses: [
                // `props` is built HERE, once, so its identity is stable and
                // the shell's per-lens memo holds (W21). The door is data plus
                // a bound click; the lens decides nothing about who may pass.
                { key: "employees", icon: "users", label: _t("Employees"),
                  Component: PbPeople, groups: EMPLOYEE_GATE,
                  props: { contractsDoor: {
                      groups: CONTRACT_GATE,
                      open: () => this.openContracts(),
                  } } },
                // Bolted-on lenses sit between the Employees cockpit and the
                // Plan launcher — after the records a person IS, before the
                // plan for the people they will be.
                ...this.extraLenses(),
                // FLEET P4. Headcount planning is sold on its own; Employees
                // (and the Contracts board inside it) never are.
                // `wantsArrival` because a deep link can be more specific
                // than a lens: "open the saved plans" has to reach the planning
                // product mounted inside this launcher, and the shell only
                // hands the payload to a lens that says it reads one.
                { key: "plan", icon: "trendingUp", label: _t("Plan"),
                  Component: PlanLauncher, groups: this.planGate(),
                  wantsArrival: true, feature: "people_plan" },
            ],
        };
    }

    /**
     * Who is offered the Plan lens.
     *
     * The UNION of the Workforce Planning tiers and whatever the registered
     * planning product is offered to. Before the Decision Room the two were the
     * same set; they are not any more, and taking only the first would hide the
     * lens from somebody who holds the Decision Room role and no legacy
     * planning group — the exact shape of W95, with the gate on the wrong door.
     * Read ONCE, in setup, like everything else in this config.
     */
    planGate() {
        return [...new Set([...PLAN_GATE, ...heroGroups()])];
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(PEOPLE_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /**
     * The Contracts board, from the Employees lens. A CLICK handler.
     *
     * By XMLID, and the XMLID's own context carries the return door to
     * Employees — the same record the ⌘K row opens, so the two can never
     * disagree about where "back" goes.
     */
    openContracts() {
        openHub(this.actionService, {
            xmlid: "pb_people_hub.action_pb_people_contracts",
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            // By XMLID: a bare tag reaches the shell with no action NAME, and
            // the breadcrumb Settings' own native cards return through then
            // reads "Unnamed" (W98).
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("People"),
                    xmlid: "pb_people_hub.action_pb_people_hub" },
        });
    }
}

registry.category("actions").add("pb_people_hub", PbPeopleHub);

// LEARN REFRESH step 4 — the tabs' gates, as the config above declares them,
// so a lesson can say "not in your company" before anybody opens the hub.
registry.category(HUB_LENS_GATES).add("pb_people_hub", () => [
    { key: "employees", groups: EMPLOYEE_GATE },
    ...registry.category(PEOPLE_LENSES).getAll(),
    { key: "plan", groups: [...new Set([...PLAN_GATE, ...heroGroups()])],
      feature: "people_plan" },
]);
