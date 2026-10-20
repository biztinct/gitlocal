/** @odoo-module **/
/**
 * Home › ASK HR (NAV P2, 2026-10-21).
 *
 * Ask HR used to be its own left-menu entry (OPERATE, between People and
 * Lifecycle). The owner's revised menu makes it a tab of Home — it is a queue,
 * like the Inbox beside it — and takes the entry off the menu.
 *
 * The lens is the EXISTING kanban (New / With HR / Answered / Closed), mounted
 * through the web client's own `View` with the same search defaults the native
 * action uses. Nothing is re-implemented: the record rules still keep a plain
 * employee on their own questions and give the HR team every one, and a card
 * opens the native form (the breadcrumb brings the reader back to Home).
 * The native action and its menu stay for administrators.
 *
 * `noBreadcrumbs` (a View prop): the Home command bar already says where the
 * reader is, so the embedded control panel keeps its search and buttons and
 * drops a second trail.
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";

const MODEL = "pb.ask.hr.ticket";

export class PbAskHrLens extends Component {
    static template = "pb_ask_hr.PbAskHrLens";
    static components = { View };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.action = useService("action");
        // Built ONCE: a fresh props object per render would reload the view.
        this.viewProps = {
            resModel: MODEL,
            type: "kanban",
            context: { search_default_filter_open: 1 },
            display: { controlPanel: {} },
            // The hub's command bar already says where the reader is: no
            // second trail. A PROP — Odoo 19's View writes it into its own
            // config, so an env value would be overwritten.
            noBreadcrumbs: true,
            // `false` = the model's default search view. Without it the
            // search view is not loaded and the default filter is ignored.
            searchViewId: false,
            selectRecord: (resId) => this.openTicket(resId),
            createRecord: () => this.openTicket(false),
        };
    }

    /** A CLICK handler: the native form, in the main breadcrumb. */
    openTicket(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Ask HR"),
            res_model: MODEL,
            res_id: resId || false,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category(HOME_LENSES).add("askhr", {
    key: "askhr",
    icon: "messageSquare",
    label: _t("Ask HR"),
    Component: PbAskHrLens,
    // Every internal user: an employee sees their own questions (record
    // rule), the HR team sees the queue.
    groups: ["base.group_user"],
}, { sequence: 15 });

/* ---------------------------------------------------------- command bar --- */
registry.category("pb_hub_palette").add("askhr_home", {
    id: "askhr_home",
    label: _t("Ask HR"),
    sublabel: _t("Home"),
    icon: "messageSquare",
    requires: "pb_home_hub",
    action: { xmlid: "pb_home_hub.action_pb_home_hub", lens: "askhr" },
    keywords: ["ask hr", "hr request", "hr question", "hỏi nhân sự"],
}, { sequence: 2050 });
