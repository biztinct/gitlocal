/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Employee360Drawer } from "@pb_employee_vault/js/employee_360";
import { PremiumRecordForm } from "@pb_form_studio/js/record_form";
import { useSubEnv } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";

Employee360Drawer.components = { ...Employee360Drawer.components, PremiumRecordForm, Dropdown, DropdownItem };
Employee360Drawer.props = { ...Employee360Drawer.props,
    workspaceStartTab: { type: String, optional: true },
    workspaceExpanded: { type: Boolean, optional: true },
    workspaceTrail: { type: Array, optional: true },
};
patch(Employee360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.expanded = Boolean(this.props.workspaceExpanded);
        this.state.tab = this.props.embedded ? "documents" : (this.props.workspaceStartTab || "profile");
        this.recordForms = {};
        this.state.sectionFields = {};
        useSubEnv({ pbEmployeeWorkspace: this });
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
    get workspaceHasOrgChart() { return registry.category("pb_people_hub_lens").contains("orgchart"); },
    async openWorkspaceOrgChart() {
        if (!this.workspaceHasOrgChart) { return; }
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return this.pbfsGuard(() => {
            const id = this.workspaceRecordId;
            this.state.shown = false;
            this.props.onClose?.();
            return this.action.doAction("pb_people_hub.action_pb_people_hub", {
                additionalContext: { pb_lens: "orgchart", pb_focus: `employee:${id}` },
                clearBreadcrumbs: false,
            });
        });
    },
    get workspaceBackLabel() {
        const previous = this.props.workspaceTrail?.at(-1);
        return previous ? _t("Back to %s", previous.name) : "";
    },
    openRelatedEmployee(id) {
        if (Number(id) === this.workspaceRecordId) { return; }
        const previous = { id: this.workspaceRecordId, name: this.profile.name,
            tab: this.state.tab, expanded: this.state.expanded };
        return this.changeWorkspaceEmployee({ id: Number(id), tab: "job", expanded: this.state.expanded },
            [...(this.props.workspaceTrail || []), previous]);
    },
    workspaceBack() {
        const trail = this.props.workspaceTrail || [];
        if (trail.length) { return this.changeWorkspaceEmployee(trail.at(-1), trail.slice(0, -1)); }
    },
    async changeWorkspaceEmployee(target, trail) {
        if (this.recordForm && !(await this.recordForm.guardLeave())) { return; }
        return this.pbfsGuard(() => {
            // Replace the current panel, rather than stacking dialogs or
            // leaving hidden drawers listening for Escape. Each back step
            // reloads authoritative data after the existing save guard.
            this.state.shown = false;
            this.props.onClose?.();
            const remove = this.overlay.add(Employee360Drawer, {
                empId: target.id, workspaceStartTab: target.tab,
                workspaceExpanded: target.expanded, workspaceTrail: trail,
                onClose: () => remove(),
            });
        });
    },
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
        if (ev.key === "Escape" && document.querySelector(".o-dropdown--menu")) { return; }
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
