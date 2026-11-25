/** @odoo-module **/
import { onMounted } from "@odoo/owl";
import { SettingsConfirmationDialog } from "@web/webclient/settings_form_view/settings_confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { SettingsFormController } from "@web/webclient/settings_form_view/settings_form_controller";
import { SETTINGS_CATEGORIES } from "./settings_hub";

const sections = {
    attendance_approvals: {
        group: "payroll", label: _t("Attendance approvals"), icon: "calendar",
        sub: _t("Company settings for approved timesheets and blocking unapproved weeks."),
        selectors: ["block[name='pb_timesheet_approval']"],
        views: ["pb_timesheet_approval.res_config_settings_view_form_pb_timesheets"],
    },
    pay_run_review: {
        group: "payroll", label: _t("Pay run review"), icon: "receipt",
        sub: _t("Database-wide threshold for flagging changes in take-home pay. Set to zero to switch it off."),
        selectors: ["block[name='pb_review_block']"],
        views: ["pb_payslip_review.res_config_settings_view_form_review"],
    },
    employee_self_service: {
        group: "hr", label: _t("Employee self-service"), icon: "users",
        sub: _t("Choose whether employees at this company can clock in and record project time."),
        selectors: ["setting#pb_ess_portal_clock_setting", "setting#pb_me_project_time_setting"],
        views: ["pb_ess_workforce.res_config_settings_view_form_portal_clock", "pb_me_project_time.res_config_settings_view_form_project_time"],
    },
    ask_hr: {
        group: "hr", label: _t("Ask HR"), icon: "users",
        sub: _t("Choose who receives new questions for this company, or leave them in the HR queue."),
        selectors: ["block[name='pb_ask_hr_setting_container']"],
        views: ["pb_ask_hr.res_config_settings_view_form_ask_hr"],
    },
    zoho_sso: {
        group: "integrations", label: _t("Zoho single sign-on"), icon: "key",
        sub: _t("Configure this database’s OAuth client, account linking and login destination."),
        selectors: ["block[name='pb_zoho_sso']"],
        views: ["pb_zoho_sso.res_config_settings_view_form_pb_zoho_sso"],
    },
    branding: {
        group: "system", label: _t("Branding"), icon: "layers",
        sub: _t("Platform administration of the product name, theme colour, website and loading logo."),
        selectors: ["block[name='biz_debrand_container']"],
        views: ["biz_debrand.res_config_settings_view_form_biz_debrand"],
    },
};

for (const [key, section] of Object.entries(sections)) {
    registry.category(SETTINGS_CATEGORIES).add(key, {
        key, group: section.group, icon: section.icon, label: section.label,
        blurb: section.sub, groups: ["base.group_system"],
        cards: [{ id: key, icon: section.icon, label: section.label, sub: section.sub,
            nativeSection: key, viewXmlids: section.views }],
    });
}

// Use the real settings record, field widgets, onchange handlers and Save/Discard.
// Scoped saves apply only edited fields. Other installed modules keep their own save hooks.
patch(SettingsFormController.prototype, {
    setup() {
        super.setup(...arguments);
        const section = sections[this.props.context.pb_settings_section];
        if (!section) return;
        const original = this.archInfo.xmlDoc;
        const form = original.cloneNode(false);
        const app = original.ownerDocument.createElement("app");
        app.setAttribute("name", "pb_settings");
        app.setAttribute("logo", "/base/static/description/icon.png");
        app.setAttribute("string", section.label);
        const block = original.ownerDocument.createElement("block");
        block.setAttribute("title", section.label);
        for (const selected of original.querySelectorAll(section.selectors.join(","))) {
            if (selected.tagName === "setting") block.appendChild(selected.cloneNode(true));
            else app.appendChild(selected.cloneNode(true));
        }
        if (block.children.length) app.appendChild(block);
        form.appendChild(app);
        this.archInfo = { ...this.archInfo, xmlDoc: form, arch: form.outerHTML };
        this.initialApp = "pb_settings";
        this.sectionFields = [...form.querySelectorAll("field")].filter(el => el.getAttribute("readonly") !== "1")
            .map(el => el.getAttribute("name"));
        onMounted(() => { this.sectionInitial = this.sectionValues(); });
    },
    sectionValues() {
        const { data, fields } = this.model.root;
        return Object.fromEntries(this.sectionFields.map(name => [
            name, fields[name].type === "many2one" ? (data[name]?.id || false) : data[name],
        ]));
    },
    async saveSection() {
        await this.model.root.getChanges(); // flush edits in the focused widget
        if (!await this.model.root.checkValidity({displayNotification: true})) return false;
        const changes = Object.fromEntries(Object.entries(this.sectionValues())
            .filter(([name, value]) => value !== this.sectionInitial[name]));
        await this.orm.call("res.config.settings", "pb_save_section", [this.props.context.pb_settings_section, changes],
            {context: this.model.root.context});
        await this.model.root.discard();
        return true;
    },
    async save() {
        if (!this.sectionFields) return super.save(...arguments);
        if (await this.saveSection()) return this.env.config.historyBack();
    },
    async discard() {
        if (!this.sectionFields) return super.discard(...arguments);
        await this.model.root.discard();
        return this.env.config.historyBack();
    },
    async _confirmSave() {
        if (!this.sectionFields) return super._confirmSave(...arguments);
        return new Promise(resolve => this.dialogService.add(SettingsConfirmationDialog, {
            body: _t("Would you like to save your changes?"),
            confirm: async () => resolve(await this.saveSection()),
            cancel: async () => { await this.model.root.discard(); resolve(true); },
            stayHere: () => resolve(false),
        }, {onClose: () => resolve(false)}));
    },
});
