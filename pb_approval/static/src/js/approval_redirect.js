/** @odoo-module **/
/**
 * The old Approvals cockpit, as a door to the new one.
 *
 * This client action used to BE the approvals screen: three lanes, one per rung
 * of the Officer → HR → Finance ladder that pay runs used to climb. There is no
 * ladder now, and there is no longer anything specific to pay runs about
 * approvals at all — every kind of request a business signs off arrives in one
 * queue, and that queue is the Approvals lens on Home.
 *
 * The action tag is KEPT, and this is why: it is named in saved sidebar rows
 * (`pb_sidebar_data.xml`), in a team's own sidebar, and in whatever anybody has
 * bookmarked. Deleting it would turn each of those into a blank screen with a
 * technical error. So the tag still resolves — it just hands straight over to
 * the one place approvals live, and nobody ever sees this component.
 */
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class PbApprovalRedirect extends Component {
    static template = "pb_approval.Redirect";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        onWillStart(async () => {
            try {
                await this.action.doAction(
                    "pb_home_hub.action_pb_home_hub",
                    { additionalContext: { pb_home_lens: "approvals" } });
            } catch {
                this.notification.add(
                    _t("Approvals have moved to Home. Open Home and choose Approvals."),
                    { type: "info" });
            }
        });
    }
}

registry.category("actions").add("pb_approval", PbApprovalRedirect);
