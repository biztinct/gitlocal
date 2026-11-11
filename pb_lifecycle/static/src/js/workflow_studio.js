/** @odoo-module **/
import { Component, xml, onWillUnmount, useRef, useState, useEffect } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { openHub } from "@pb_hub/js/hub_nav";

export class WorkflowStudio extends Component {
    static props = ["*"];
    static template = xml`<iframe t-ref="frame" t-att-src="url" title="Workflow Studio" style="width:100%;height:100%;min-height:600px;border:0;flex:1;background:#f6f7fc"/>`;
    setup() {
        this.action = useService("action");
        this.frame = useRef("frame");
        const q = new URLSearchParams({v: "wf2-p3a2", company: (user.context.allowed_company_ids || [])[0] || "",
            origin: this.props.action?.context?.pb_workflow_origin ? JSON.stringify(this.props.action.context.pb_workflow_origin) : "",
            workflow: this.props.action?.context?.pb_workflow_id || "",
            template: this.props.action?.context?.pb_workflow_template_id || "",
            record_model: this.props.action?.context?.pb_workflow_record_model || "",
            record_id: this.props.action?.context?.pb_workflow_record_id || "",
            setup_model: this.props.action?.context?.pb_workflow_setup_model || "",
            setup_id: this.props.action?.context?.pb_workflow_setup_id || "",
            run: this.props.action?.context?.pb_workflow_run_id || "",
            task: this.props.action?.context?.pb_workflow_task_id || "",
            submission: this.props.action?.context?.pb_workflow_submission_id || ""});
        this.url = "/pb_lifecycle/static/workflow/index.html?" + q;
        const receive = e => {
            if (e.origin !== location.origin || e.source !== this.frame.el?.contentWindow || e.data?.type !== "pb.workflow.open") return;
            const action = e.data.action;
            if (!action || !["ir.actions.act_window", "ir.actions.client"].includes(action.type)) return;
            const origin = e.data.origin;
            if (origin && action.type === "ir.actions.client") {
                // Both the live controller and the fallback carry the exact workflow,
                // selected step and view. Never infer an origin from the last workflow opened.
                this.props.action.context = {...this.props.action.context, pb_workflow_origin: origin};
                this.url = "/pb_lifecycle/static/workflow/index.html?" + new URLSearchParams({...Object.fromEntries(q), origin: JSON.stringify(origin)});
                return openHub(this.action, {tag: action.tag, context: action.context || {},
                    clearBreadcrumbs: false, back: {tag: "pb_workflow_studio", label: _t("Workflow Studio"),
                    context: {pb_workflow_id: origin.workflow, pb_workflow_origin: origin}}});
            }
            this.action.doAction(action);
        };
        window.addEventListener("message", receive);
        onWillUnmount(() => window.removeEventListener("message", receive));
    }
}
registry.category("actions").add("pb_workflow_studio", WorkflowStudio);
// One common entry on native forms, including Expenses, Pay, Time and future
// modules. The server checks record and progress-view permissions every time.
patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.workflowProgress = useState({ available: false, canDesign: false });
        useEffect(() => {
            let live = true;
            this.workflowProgress.available = false;
            this.workflowProgress.canDesign = false;
            const record = this.model.root;
            if (record.resId && !record.resModel.startsWith("pb.workflow.")) {
                this.orm.call("pb.workflow.studio", "record_runs", [record.resModel, record.resId])
                    .then(data => { if (live) {
                        this.workflowProgress.available = !!(data.runs.length || data.approvals.length || data.record_stages?.length);
                        this.workflowProgress.canDesign = !!data.can_design;
                    } })
                    .catch(() => { if (live) this.workflowProgress.available = false; });
            }
            return () => { live = false; };
        }, () => [this.model.root.resModel, this.model.root.resId]);
    },
    async openWorkflowProgress() {
        if (!(await this.model.root.save())) return;
        return this.actionService.doAction({ type: "ir.actions.client", tag: "pb_workflow_studio",
            name: _t("Workflow progress"), context: {
                pb_workflow_record_model: this.model.root.resModel,
                pb_workflow_record_id: this.model.root.resId,
            }});
    },
    async setupRecordWorkflow() {
        if (!(await this.model.root.save())) return;
        return this.actionService.doAction({ type: "ir.actions.client", tag: "pb_workflow_studio",
            name: _t("Workflow setup"), context: {
                pb_workflow_setup_model: this.model.root.resModel,
                pb_workflow_setup_id: this.model.root.resId,
            }});
    },
    getStaticActionMenuItems() {
        return { ...super.getStaticActionMenuItems(), workflowSetup: {
            description: _t("Set up workflow"), icon: "fa fa-pencil", sequence: 96,
            isAvailable: () => this.workflowProgress.canDesign,
            callback: () => this.setupRecordWorkflow(),
        }, workflowProgress: {
            description: _t("View workflow"), icon: "fa fa-code-fork", sequence: 95,
            isAvailable: () => this.workflowProgress.available,
            callback: () => this.openWorkflowProgress(),
        }};
    },
});
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
