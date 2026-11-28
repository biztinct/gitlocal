from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError


# Only these fields can be committed from each focused settings form. Optional
# modules still own the fields, defaults, storage and runtime interpretation.
SECTIONS = {
    'attendance_approvals': ('pb_timesheet_payroll', 'pb_timesheet_block_run'),
    'pay_run_review': ('pb_review_change_pct',),
    'employee_self_service': ('pb_ess_portal_clock', 'pb_me_project_time_enabled'),
    'ask_hr': ('pb_ask_hr_owner_id',),
    'zoho_sso': ('pb_zoho_sso_enabled', 'pb_zoho_sso_client_id',
                 'pb_zoho_sso_client_secret', 'pb_zoho_sso_accounts_url',
                 'pb_zoho_sso_auto_link_email', 'pb_zoho_sso_allowed_domains',
                 'pb_zoho_sso_default_target'),
    'branding': ('biz_debrand_brand_name', 'biz_debrand_brand_website',
                 'biz_debrand_theme_color', 'biz_debrand_product_name',
                 'biz_debrand_loader_logo', 'biz_debrand_loader_logo_url'),
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def pb_save_section(self, section, changes):
        """Apply only edited controls, without running unrelated module setup hooks."""
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only platform administrators can change these settings."))
        if (not isinstance(section, str) or section not in SECTIONS or not isinstance(changes, dict)
                or not changes.keys() <= set(SECTIONS[section]) & self._fields.keys()):
            raise ValidationError(_("This field does not belong to the selected settings section."))
        if not changes:
            return True
        company = self.env.company
        params = self.env['ir.config_parameter']
        if section == 'attendance_approvals':
            company.write(changes)
            return True
        wizard = self.new(changes)
        for name in changes:
            value = wizard[name]
            if name == 'pb_ess_portal_clock':
                from odoo.addons.pb_ess_workforce.models.ess_workforce import CLOCK_PARAM
                params.set_param(CLOCK_PARAM % company.id, '1' if value else '0')
            elif name == 'pb_me_project_time_enabled':
                from odoo.addons.pb_me_project_time.models.project_time import PARAM
                params.set_param(PARAM % company.id, '1' if value else '0')
            elif name == 'pb_ask_hr_owner_id':
                from odoo.addons.pb_ask_hr.models.ticket import OWNER_PARAM
                if value and (not value.exists() or value.share or not value.active or company not in value.company_ids):
                    raise ValidationError(_("Choose an active internal user in this company."))
                params.set_param(OWNER_PARAM % company.id, str(value.id) if value else '')
            elif name != 'biz_debrand_loader_logo':
                field = self._fields[name]
                if name == 'pb_review_change_pct' and value < 0:
                    raise ValidationError(_("The review threshold must be zero or greater."))
                if field.type == 'integer':
                    value = str(value)  # zero explicitly disables the review flag
                elif field.type == 'char':
                    value = (value or '').strip() or False
                params.set_param(field.config_parameter, value)
        if section == 'branding':
            wizard._biz_debrand_store_loader_logo()
            wizard._biz_debrand_apply_brand()
        return True
