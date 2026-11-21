/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Employee360Drawer } from "@pb_employee_vault/js/employee_360";
import { PremiumRecordForm } from "@pb_form_studio/js/record_form";

Employee360Drawer.components = { ...Employee360Drawer.components, PremiumRecordForm };
patch(Employee360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.expanded = false;
        this.state.tab = this.props.embedded ? "documents" : "record";
        this.recordForm = null;
    },
    get workspaceRecordId() { return Number(this.props.empId); },
    get workspaceExpandLabel() { return this.state.expanded ? _t("Collapse") : _t("Expand"); },
    workspaceReady(form) { this.recordForm = form; },
    openFull() { this.state.expanded = !this.state.expanded; },
    async close() {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return super.close(...arguments);
    },
    async openContract(contractId, tab) {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return super.openContract(contractId, tab);
    },
    onKey(ev) {
        if (this.props.embedded) { return; }
        if (document.querySelector(".o_dialog, .pbfb-overlay")) { return; }
        if (ev.key === "Escape" && ev.target?.closest(".o_field_widget")) { return; }
        return super.onKey(ev);
    },
    async pbfsOpenStudio() {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return super.pbfsOpenStudio();
    },
    async pbfsReload() {
        await super.pbfsReload(...arguments);
        if (this.recordForm) { await this.recordForm.reloadDesign(); }
    },
});
