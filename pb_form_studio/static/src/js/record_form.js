/** @odoo-module **/
// Keep the original employee/contract controller and server-processed arch.
// Only the enclosing presentation changes; installed field widgets and hooks stay.
import { Component, onError, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useEffect, useState, useSubEnv } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { View, getDefaultConfig } from "@web/views/view";
import { rpcBus } from "@web/core/network/rpc";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    get isPremiumRecord() {
        const host = this.env.pbRecordWorkspace;
        return Boolean(host && this.props.resModel === host.props.resModel && this.props.resId === host.props.resId);
    },
    setup() {
        super.setup(...arguments);
        if (!this.isPremiumRecord) { return; }
        this.pbRecordUI = useState({ busy: false });
        const notebookChanged = this.onNotebookPageChange;
        this.onNotebookPageChange = (id, page) => {
            notebookChanged(id, page);
            if (page) { this.env.pbRecordWorkspace.notebookPages[id] = page; }
        };
        onMounted(() => { this.env.pbRecordWorkspace.controller = this; });
        onWillUnmount(() => { this.env.pbRecordWorkspace.controller = null; });
        useEffect(() => {
            const version = this.model.root.data.version_id;
            if (this.pbObservedVersion !== undefined && version?.id !== this.pbObservedVersion) {
                this.env.pbRecordWorkspace.props.onVersionChanged?.(version);
            }
            this.pbObservedVersion = version?.id;
        }, () => [this.model.root.data.version_id?.id]);
    },
    get modelParams() {
        const params = super.modelParams;
        if (this.isPremiumRecord) {
            params.config.mode = "readonly";
            params.useSendBeaconToSaveUrgently = false;
        }
        return params;
    },
    get className() {
        const classes = { ...super.className };
        if (this.isPremiumRecord) { delete classes["o_xxl_form_view h-100"]; }
        return classes;
    },
    async pbRecordEdit() {
        if (this.canEdit) { await this.model.root.switchMode("edit"); }
    },
    async pbRecordSave() {
        if (this.pbRecordUI.busy) { return false; }
        this.pbRecordUI.busy = true;
        try {
            const saved = await this.saveButtonClicked();
            if (saved) { await this.model.root.switchMode("readonly"); }
            return saved;
        } finally { this.pbRecordUI.busy = false; }
    },
    async pbRecordCancel() {
        await this.model.root.discard();
        await this.model.root.switchMode("readonly");
    },
    async beforeExecuteActionButton(params) {
        if (this.isPremiumRecord) {
            if (!(await this.pbRecordGuard())) { return false; }
            this.pbActionOrigin = this.actionService.currentController;
        }
        return super.beforeExecuteActionButton(params);
    },
    async afterExecuteActionButton(params) {
        await super.afterExecuteActionButton(params);
        if (this.isPremiumRecord && this.pbActionOrigin !== this.actionService.currentController) {
            this.env.pbWorkspaceNavigate?.();
        }
    },
    async pbRecordWorkflow(setup) {
        if (!(await this.pbRecordGuard())) { return; }
        await (setup ? this.setupRecordWorkflow() : this.openWorkflowProgress());
        this.env.pbWorkspaceNavigate?.();
    },
    beforeVisibilityChange() {
        if (!this.isPremiumRecord) { return super.beforeVisibilityChange(...arguments); }
    },
    async beforeUnload(ev) {
        if (!this.isPremiumRecord) { return super.beforeUnload(...arguments); }
        if (this.model.root.dirty) { ev.preventDefault(); ev.returnValue = _t("Unsaved changes"); }
    },
    beforeLeave() {
        return this.isPremiumRecord ? this.pbRecordGuard() : super.beforeLeave(...arguments);
    },
    async pbRecordGuard() {
        if (!(await this.model.root.isDirty())) { return true; }
        return new Promise((resolve) => {
            this.dialogService.add(ConfirmationDialog, {
                title: _t("Unsaved changes"),
                body: _t("Save or cancel your changes before leaving this record."),
                confirmLabel: _t("Save and continue"), cancelLabel: _t("Keep editing"),
                confirm: async () => resolve(Boolean(await this.pbRecordSave())),
                cancel: () => resolve(false),
            }, { onClose: () => resolve(false) });
        });
    },
});

export class PremiumRecordForm extends Component {
    static template = "pb_form_studio.RecordForm";
    static components = { View };
    static props = {
        resModel: String, resId: Number, onReady: Function,
        onSaved: { type: Function, optional: true },
        section: { type: String, optional: true },
        title: { type: String, optional: true },
        recordContext: { type: Object, optional: true },
        onVersionChanged: { type: Function, optional: true },
    };
    setup() {
        this.state = useState({ generation: 0, error: false });
        onError((error) => {
            const cause = error.cause || error;
            this.state.error = cause.data?.name === "odoo.exceptions.AccessError"
                ? _t("Your role cannot open all details on this record. The summary and available tools are still accessible.")
                : _t("The complete form could not be loaded. You can retry or use the other tabs.");
        });
        this.viewService = useService("view");
        this.sectionView = null;
        onWillStart(() => this.loadSection());
        onWillUpdateProps((next) => {
            if (JSON.stringify(next.recordContext || {}) !== JSON.stringify(this.props.recordContext || {})) {
                this.state.generation++;
            }
        });
        onMounted(() => this.props.onReady(this));
        this.controller = null;
        this.notebookPages = {};
        // A drawer may originate from any list or dashboard. Its form must
        // never inherit that action's model-specific view ids or pager.
        useSubEnv({ pbRecordWorkspace: this, config: { ...getDefaultConfig(), noBreadcrumbs: true } });
        onWillUnmount(() => this.props.onReady(null));
    }
    async loadSection() {
        if (!this.props.section) { return; }
        try {
            const result = await this.viewService.loadViews({
                resModel: this.props.resModel, views: [[false, "form"]], context: {},
            }, { pb_workspace_section: this.props.section, pb_workspace_revision: 4 });
            this.sectionView = { arch: result.views.form.arch, fields: result.fields,
                relatedModels: result.relatedModels, viewId: result.views.form.id };
        } catch (error) {
            this.state.error = _t("This section could not be loaded. Please retry.");
        }
    }
    get projectedFields() {
        if (!this.sectionView?.arch || this.state.error) { return []; }
        const arch = new DOMParser().parseFromString(this.sectionView.arch, "text/xml");
        return [...arch.querySelectorAll("section field[name]")]
            .filter(node => !node.parentElement.closest("field"))
            .map(node => node.getAttribute("name"));
    }
    get viewProps() {
        return {
            type: "form", resModel: this.props.resModel, resId: this.props.resId,
            preventCreate: true, loadActionMenus: !this.props.section,
            ...(this.sectionView || {}),
            state: { activeNotebookPages: { ...this.notebookPages } },
            context: { ...this.props.recordContext, pb_premium_record: true }, display: { controlPanel: !this.props.section },
            onSave: () => this.props.onSaved?.(),
        };
    }
    async guardLeave() { return this.controller ? this.controller.pbRecordGuard() : true; }
    async retry() { this.state.error = false; await this.loadSection(); this.props.onReady(this); this.state.generation++; }
    async reloadDesign() {
        if (this.controller && await this.controller.model.root.isDirty()) { return false; }
        rpcBus.trigger("CLEAR-CACHES", "get_views");
        await this.loadSection();
        this.props.onReady(this);
        this.state.generation++;
        return true;
    }
}
