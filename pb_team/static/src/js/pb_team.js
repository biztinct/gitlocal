/** @odoo-module **/
/**
 * The Team Approvals cockpit is retired. This is the door it left behind.
 *
 * WHY IT WENT. It was a second approval queue. It knew four kinds of request
 * by name — overtime, trips, attendance fixes, time off — and it decided them
 * through each model's own ladder, which meant a manager could see one answer
 * here and a different one in the Approvals inbox, and neither screen could
 * ever learn about the eleven other things people ask for. There is one inbox
 * now, it shows every kind of request, and the Workforce workspace mounts it
 * as its Approvals lens with the scope set to "my team" — the same screen this
 * one was, with everything else in it.
 *
 * WHY THE DOOR REMAINS. An action is a link somebody may have saved, put on a
 * dashboard or written into their own notes. Retiring a surface is not a reason
 * to give any of them a page that says nothing. This one goes where the queue
 * went, in one hop, and says so.
 */
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class PbTeamRedirect extends Component {
    static template = "pb_team.PbTeamRedirect";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.action = useService("action");
        onWillStart(() => this.go());
    }

    get message() {
        return _t("Taking you to Approvals…");
    }

    async go() {
        await this.action.doAction("pb_mission.action_pb_workforce", {
            additionalContext: { pb_shell_lens: "approvals" },
            clearBreadcrumbs: true,
        });
    }
}

registry.category("actions").add("pb_team", PbTeamRedirect);
