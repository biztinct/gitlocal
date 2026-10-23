/** @odoo-module **/
/**
 * `pb_expenses_hub` — OPERATE › Expenses (NAV P2, 2026-10-21).
 *
 *     trips · claims
 *
 * Trips is the existing trips board (`PbTrips`, embedded) — it was a tab of
 * Workforce until NAV P2 and keeps that tab's gate (everybody the entry lets
 * in) and the Workforce product switch. Claims is the expense-claims list
 * (`PbClaimsLens`), offered to expense approvers.
 *
 * Other modules may add a tab through `EXPENSES_LENSES`.
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
import { PbTrips } from "@pb_business_trip/js/pb_trips";
import { PbClaimsLens } from "@pb_expenses_hub/js/claims_lens";

/** `pb.expense.claim`'s full ACL row (the list is an approver's screen). */
export const CLAIMS_GATE = ["hr_expense.group_hr_expense_team_approver"];

/** Where a later module bolts a tab onto Expenses. */
export const EXPENSES_LENSES = "pb_expenses_hub_lens";

export class PbExpensesHub extends Component {
    static template = "pb_expenses_hub.PbExpensesHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        this.config = {
            key: "expenses",                 // -> pbhub.expenses.lens.v1
            brand: { label: _t("Expenses"), icon: "wallet" },
            // Trips was sold with Workforce and still is.
            feature: "workforce",
            defaultLens: "trips",
            cog: () => this.openSettings(),
            lenses: [
                { key: "trips", icon: "plane", label: _t("Trips"),
                  title: _t("Business trips"),
                  Component: PbTrips, groups: [] },
                { key: "claims", icon: "receipt", label: _t("Claims"),
                  title: _t("Expense claims"),
                  Component: PbClaimsLens, groups: CLAIMS_GATE },
                ...this.extraLenses(),
            ],
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(EXPENSES_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Expenses"), xmlid: "pb_expenses_hub.action_pb_expenses_hub" },
        });
    }
}

registry.category("actions").add("pb_expenses_hub", PbExpensesHub);

registry.category(HUB_LENS_GATES).add("pb_expenses_hub", () => [
    { key: "trips", groups: [] },
    { key: "claims", groups: CLAIMS_GATE },
    ...registry.category(EXPENSES_LENSES).getAll(),
].map((l) => ({ ...l, hubFeature: "workforce" })));
