/** @odoo-module **/
import { Component, xml, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";

export class WorkflowStudio extends Component {
    static props = ["*"];
    static template = xml`<iframe t-ref="frame" t-att-src="url" title="Workflow Studio" style="width:100%;height:100%;min-height:600px;border:0;flex:1;background:#f6f7fc"/>`;
    setup() {
        this.action = useService("action");
        this.frame = useRef("frame");
        const q = new URLSearchParams({company: (user.context.allowed_company_ids || [])[0] || "",
            workflow: this.props.action?.context?.pb_workflow_id || ""});
        this.url = "/pb_lifecycle/static/workflow/index.html?" + q;
        const receive = e => {
            if (e.origin !== location.origin || e.source !== this.frame.el?.contentWindow || e.data?.type !== "pb.workflow.open") return;
            const action = e.data.action;
            if (action && ["ir.actions.act_window", "ir.actions.client"].includes(action.type)) this.action.doAction(action);
        };
        window.addEventListener("message", receive);
        onWillUnmount(() => window.removeEventListener("message", receive));
    }
}
registry.category("actions").add("pb_workflow_studio", WorkflowStudio);
registry.category(SETTINGS_CATEGORIES).add("workflow_studio", {
    key: "workflow_studio", group: "workflows", icon: "workflow", label: _t("Workflow Studio"),
    blurb: _t("Steps, forms and tasks across your business. Existing approvals and settings stay connected."),
    groups: ["pb_lifecycle.group_workflow_designer", "base.group_system"],
    cards: [{id: "workflow_studio", xmlid: "pb_lifecycle.action_pb_workflow_studio", icon: "workflow",
        label: _t("Workflow Studio"), sub: _t("Build, try and run your processes.")}],
}, {sequence: 41});
registry.category("pb_hub_palette").add("workflow_studio", {
    id: "workflow_studio", label: _t("Workflows & my tasks"), sublabel: _t("Workflow Studio"),
    icon: "workflow", requires: "pb_workflow_studio",
    action: {xmlid: "pb_lifecycle.action_pb_workflow_studio"},
}, {sequence: 3430});
