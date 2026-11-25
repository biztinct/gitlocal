/** @odoo-module **/
/**
 * NEWHIRE P1 — the old "Add employee" door opens the New Hire Studio.
 *
 * Done from THIS module, never by editing the modules that own the door
 * (`pb_people` button, the org chart's "A new starter"): both open the client
 * tag `pb_onboard_wizard`, which this file re-registers with `force` to a tiny
 * hand-over that opens the studio by its xmlid, forwarding the org chart's
 * `params.prefill`. A database without this module keeps the old window
 * exactly as it was (D10). The asset order makes it win: this module depends
 * on `pb_people_advanced`, whose registration therefore runs first.
 *
 * The org chart checks `registry.category("actions").contains("pb_onboard_wizard")`
 * before opening it: still true.
 */
import { Component, onMounted } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ACTION_XMLID } from "./studio_util";

export class NewHireDoor extends Component {
    static template = "pb_new_hire.Door";
    static props = { "*": true };

    setup() {
        this.action = useService("action");
        onMounted(() => {
            const params = (this.props.action && this.props.action.params) || {};
            const context = params.prefill ? { pb_nh_prefill: params.prefill } : {};
            this.action.doAction(ACTION_XMLID, {
                stackPosition: "replaceCurrentAction",
                additionalContext: context,
            });
        });
    }

    get opening() { return _t("Opening Add employee…"); }
}

registry.category("actions").add("pb_onboard_wizard", NewHireDoor, { force: true });
