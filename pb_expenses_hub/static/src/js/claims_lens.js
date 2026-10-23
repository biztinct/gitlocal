/** @odoo-module **/
/**
 * Expenses › CLAIMS (NAV P2) — the existing expense-claims list, in the hub.
 *
 * Mounted through the web client's own `View` with the model's own list and
 * search views (filters: Waiting approval, Approved, Refused, Paid), so the
 * hub adds a place, never a second copy of the screen. A row opens the native
 * form in the main breadcrumb, which brings the reader back here. Decisions
 * are still taken from Approvals; nothing here approves anything.
 */
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";

const MODEL = "pb.expense.claim";

export class PbClaimsLens extends Component {
    static template = "pb_expenses_hub.PbClaimsLens";
    static components = { View };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.action = useService("action");
        // Built ONCE: a fresh props object per render would reload the view.
        this.viewProps = {
            resModel: MODEL,
            type: "list",
            context: { search_default_waiting: 1 },
            display: { controlPanel: {} },
            // The hub's command bar already says where the reader is: no
            // second trail. A PROP — Odoo 19's View writes it into its own
            // config, so an env value would be overwritten.
            noBreadcrumbs: true,
            // `false` = the model's default search view. Without it the
            // search view is not loaded and the default filter is ignored.
            searchViewId: false,
            selectRecord: (resId) => this.openClaim(resId),
            createRecord: () => this.openClaim(false),
        };
    }

    /** A CLICK handler: the native form, in the main breadcrumb. */
    openClaim(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Expense claims"),
            res_model: MODEL,
            res_id: resId || false,
            views: [[false, "form"]],
            target: "current",
        });
    }
}
