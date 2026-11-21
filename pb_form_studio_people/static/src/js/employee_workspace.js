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
        this.state.tab = this.props.embedded ? "documents" : "profile";
        this.recordForms = {};
        this.state.sectionFields = {};
    },
    groups(tab) {
        const groups = super.groups(tab);
        if (!["job", "personal", "pay"].includes(tab) || this.recordForm?.state.error) { return groups; }
        const editable = new Set(this.state.sectionFields[tab] || []);
        if (tab === "personal" && editable.has("private_street")) { editable.add("_home_address"); }
        return groups.map(group => {
            const rows = group.rows.filter(row => !editable.has(row.key));
            return { ...group, rows, filled: rows.filter(row => !row.empty).length };
        }).filter(group => group.rows.length);
    },
    get workspaceRecordId() { return Number(this.props.empId); },
    get workspaceExpandLabel() { return this.state.expanded ? _t("Collapse") : _t("Expand"); },
    get recordForm() { return this.recordForms[this.state.tab] || null; },
    workspaceJobReady(form) { this.workspaceReady("job", form); },
    workspacePersonalReady(form) { this.workspaceReady("personal", form); },
    workspacePayReady(form) { this.workspaceReady("pay", form); },
    workspaceResumeReady(form) { this.workspaceReady("resume", form); },
    workspaceSettingsReady(form) { this.workspaceReady("settings", form); },
    workspaceDocumentsReady(form) { this.workspaceReady("documents", form); },
    workspaceReady(section, form) {
        this.recordForms[section] = form;
        const fields = form?.projectedFields || [];
        if (JSON.stringify(this.state.sectionFields[section] || []) !== JSON.stringify(fields)) {
            this.state.sectionFields[section] = fields;
        }
    },
    toggleWorkspace() { this.state.expanded = !this.state.expanded; },
    async openFull() {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return super.openFull(...arguments);
    },
    async setTab(tab) {
        if (tab !== this.state.tab && this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return this.pbfsGuard(() => super.setTab(tab));
    },
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
