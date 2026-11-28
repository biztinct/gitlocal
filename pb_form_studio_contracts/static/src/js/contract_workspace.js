/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PremiumRecordForm } from "@pb_form_studio/js/record_form";
import { Contract360Drawer } from "@pb_contracts/js/contract_360";
import { useSubEnv } from "@odoo/owl";

Contract360Drawer.components = { ...Contract360Drawer.components, PremiumRecordForm };

patch(Contract360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.expanded = false;
        this.recordForm = null;
        useSubEnv({ pbWorkspaceNavigate: () => this.reallyClose() });
    },
    get workspaceRecordId() { return Number(this.props.contractId); },
    get workspaceExpandLabel() { return this.state.expanded ? _t("Collapse") : _t("Expand"); },
    toggleWorkspace() { this.state.expanded = !this.state.expanded; },
    workspaceReady(form) { this.recordForm = form; },
    async setTab(tab) {
        if (tab !== this.state.tab && this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        if (tab === 'agreement' && this.isDirty) {
            this.notif.add(_t("Save or discard your terms before editing agreement details."), { type: "warning" });
            return;
        }
        return super.setTab(tab);
    },
    async openFullForm() {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        if (this.isDirty) {
            this.notif.add(_t("Save or discard your changes before opening the advanced record."), { type: "warning" });
            return;
        }
        this.reallyClose();
        return super.openFullForm(...arguments);
    },
    async close() {
        if (this.fs3Studio.state.open) { return; }
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return super.close(...arguments);
    },
    onKey(ev) {
        if (ev.key === "Escape" && document.querySelector(".o-dropdown--menu")) { return; }
        if (this.state.tab === 'agreement' && ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault(); ev.stopPropagation();
            this.recordForm?.controller?.pbRecordSave();
            return;
        }
        if (ev.key === 'Escape' && ev.target?.closest('.o_field_widget')) { return; }
        if (this.fs3Studio.state.open || document.querySelector(".o_dialog, .pbfb-overlay")) { return; }
        return super.onKey(ev);
    },
    async runAction(act) {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        if (act.method === "renew") {
            if (this.isDirty || !this.canWrite) { return; }
            const action = { type: "ir.actions.client", tag: "pb_contract_wizard", name: _t("Renew contract"),
                params: { employee_id: this.header.employee_id, renew_from: this.workspaceRecordId } };
            this.reallyClose();
            return this.action.doAction(action);
        }
        return super.runAction(act);
    },
    actTitle(act) { return act.method === "renew" ? _t("Renew this contract") : super.actTitle(act); },
    async workspaceBuilder() {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        if (this.isDirty) {
            this.notif.add(_t("Save or discard your record changes before changing the form."), { type: "info" });
            return;
        }
        this.fs3Studio.open();
    },
    async fs3OnPublished() {
        await super.fs3OnPublished(...arguments);
        if (this.recordForm) { await this.recordForm.reloadDesign(); }
    },
    get workspaceStudioProps() {
        return { ...this.fs3Studio.overlayProps, surface: "full", returnLabel: _t("Back to contract") };
    },
});
