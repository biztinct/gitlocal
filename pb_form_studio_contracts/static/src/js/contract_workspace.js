/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Contract360Drawer } from "@pb_contracts/js/contract_360";
import { PremiumRecordForm } from "@pb_form_studio/js/record_form";

Contract360Drawer.components = { ...Contract360Drawer.components, PremiumRecordForm };
patch(Contract360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.expanded = false;
        if (!this.props.tab) { this.state.tab = "record"; }
        this.recordForm = null;
    },
    get workspaceRecordId() { return Number(this.props.contractId); },
    get workspaceExpandLabel() { return this.state.expanded ? _t("Collapse") : _t("Expand"); },
    workspaceReady(form) { this.recordForm = form; },
    openFullForm() { this.state.expanded = !this.state.expanded; },
    async close() {
        if (this.fs3Studio.state.open) { return; }
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return super.close(...arguments);
    },
    async setTab(tab) {
        // The pay tools have their own approval-aware draft. Do not allow
        // two different editors to hold competing drafts of the same terms.
        if (tab !== this.state.tab) {
            if (this.isDirty) {
                this.notif.add(_t("Save or discard the changes in this tab first."), { type: "warning" });
                return;
            }
            if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
            if (tab === "record" && this.recordForm?.controller) {
                await this.recordForm.controller.model.load();
            }
        }
        return super.setTab(tab);
    },
    onKey(ev) {
        if (this.fs3Studio.state.open || document.querySelector(".o_dialog, .pbfb-overlay")) { return; }
        if (this.state.tab === "record") {
            if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
                ev.preventDefault();
                this.recordForm?.controller?.pbRecordSave();
                return;
            }
            if (ev.key === "Escape" && ev.target?.closest(".o_field_widget")) { return; }
        }
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
        if (this.isDirty || (this.recordForm && !(await this.recordForm.guardLeave()))) {
            this.notif.add(_t("Save or discard your record changes before changing the form."), { type: "info" });
            return;
        }
        this.fs3Studio.open();
    },
    get workspaceStudioProps() {
        return { ...this.fs3Studio.overlayProps, surface: "full", returnLabel: _t("Back to contract") };
    },
    async fs3OnPublished() {
        await super.fs3OnPublished(...arguments);
        if (this.recordForm) { await this.recordForm.reloadDesign(); }
    },
});
