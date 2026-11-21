/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Contract360Drawer } from "@pb_contracts/js/contract_360";

patch(Contract360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.expanded = false;
    },
    get workspaceRecordId() { return Number(this.props.contractId); },
    get workspaceExpandLabel() { return this.state.expanded ? _t("Collapse") : _t("Expand"); },
    toggleWorkspace() { this.state.expanded = !this.state.expanded; },
    openFullForm() {
        if (this.isDirty) {
            this.notif.add(_t("Save or discard your changes before opening Full details."), { type: "warning" });
            return;
        }
        this.reallyClose();
        return super.openFullForm(...arguments);
    },
    async close() {
        if (this.fs3Studio.state.open) { return; }
        return super.close(...arguments);
    },
    onKey(ev) {
        if (this.fs3Studio.state.open || document.querySelector(".o_dialog, .pbfb-overlay")) { return; }
        return super.onKey(ev);
    },
    async runAction(act) {
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
        if (this.isDirty) {
            this.notif.add(_t("Save or discard your record changes before changing the form."), { type: "info" });
            return;
        }
        this.fs3Studio.open();
    },
    get workspaceStudioProps() {
        return { ...this.fs3Studio.overlayProps, surface: "full", returnLabel: _t("Back to contract") };
    },
});
