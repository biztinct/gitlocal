# -*- coding: utf-8 -*-
"""The employee record as a Form builder host (FS-2).

THE HOST CONTRACT (FS1_REPORT.md §5) item 1: one host, `employee_detail`,
on `hr.employee` ONLY (never `hr.version` / `hr.employee.public`,
FS_HOST_FACTS §F). Its sections mirror the side panel: the panel's own tabs
are LOCKED sections (drawn by the screen, no field can be placed there) and
three OPEN sections make up the new "Company details" tab. The same
published layout drives the panel tab, the full page and the "Company
details" page on Full details (item 5, the engine's native-view sync).

Nothing here runs at install: the native page is registered the first time a
layout of this record type is published or a field of it deleted.
"""
from odoo import api, models
from odoo.exceptions import AccessError

HOST = 'employee_detail'
MODEL = 'hr.employee'
#: The native form that "Full details" opens (FS_HOST_FACTS §A.1).
NATIVE_VIEW = 'hr.view_employee_form'

#: The side panel's gate (`pb_employee_vault/models/pb_people_360.py:16-19, 28-31`).
HR_GROUPS = ('om_hr_payroll.group_hr_payroll_user', 'hr.group_hr_user')


def page_titles():
    """The Full details page title per language. Plain data on purpose: the
    engine stores it on its own record and puts it in the page it writes."""
    return {'en_US': 'Company details', 'vi_VN': 'Thông tin công ty',
            'id_ID': 'Detail perusahaan'}


class PbFormStudio(models.AbstractModel):
    _inherit = 'pb.form.studio'

    # ------------------------------------------------------------ host
    @api.model
    def _pbfs_hosts(self):
        hosts = super()._pbfs_hosts()
        if MODEL not in self.env:
            return hosts
        _ = self.env._
        locked = _('Drawn by the side panel itself. Fields cannot be placed here.')
        hosts[HOST] = {
            'model': MODEL,
            'title': _('Employee'),
            'icon': 'user',
            # Host order = the side panel's tab order; ids are stable forever.
            'sections': [
                {'id': 'profile', 'title': _('Profile'), 'icon': 'user', 'tone': 'teal',
                 'kind': 'locked',
                 'note': _('Wage, department, manager and contract dates. %s', locked)},
                {'id': 'personal', 'title': _('Personal'), 'icon': 'idCard', 'tone': 'blue',
                 'kind': 'locked',
                 'note': _('Identity, contact and family details. %s', locked)},
                {'id': 'job', 'title': _('Job'), 'icon': 'briefcase', 'tone': 'blue',
                 'kind': 'locked',
                 'note': _('Position, team and place of work. %s', locked)},
                {'id': 'pay', 'title': _('Pay & tax'), 'icon': 'banknote', 'tone': 'green',
                 'kind': 'locked',
                 'note': _('Tax, insurance and bank details. %s', locked)},
                {'id': 'custom', 'title': _('Company details'), 'icon': 'sparkles',
                 'tone': 'brand', 'kind': 'open'},
                {'id': 'job_more', 'title': _('More about the job'), 'icon': 'briefcase',
                 'tone': 'amber', 'kind': 'open'},
                {'id': 'person_more', 'title': _('More about the person'), 'icon': 'user',
                 'tone': 'teal', 'kind': 'open'},
                {'id': 'documents', 'title': _('Documents'), 'icon': 'fileText', 'tone': 'brand',
                 'kind': 'locked',
                 'note': _('Uploaded documents, by kind. %s', locked)},
                {'id': 'timeline', 'title': _('Timeline'), 'icon': 'history', 'tone': 'brand',
                 'kind': 'locked',
                 'note': _('Every change to this person, newest first. %s', locked)},
            ],
            'default_layout': {'custom': [], 'job_more': [], 'person_more': []},
            # Standard fields stay where the panel draws them (R8: look-only).
            'std_fields': [],
            'custom_section': 'custom',
            # R10 — Country of Work (FIELD_AUDIT_FACTS §6), as a country record.
            'country_field': 'pbfs_country_of_work_id',
            'country_view_field': 'pbfs_country_of_work_id',
            'copy_custom': False,
            'native_views': [NATIVE_VIEW],
        }
        return hosts

    # ------------------------------------------------------------ gates
    @api.model
    def _pbfs_people_is_hr(self):
        """The side panel's own gate: HR, payroll or the administrator."""
        user = self.env.user
        return self.env.su or user._is_admin() or any(user.has_group(g) for g in HR_GROUPS)

    @api.model
    def render(self, host_key, record_id):
        """The employee host answers HR only, like the side panel it feeds —
        a line manager, an employee or a portal user gets nothing, even with
        a hand-made request."""
        if host_key == HOST and not self._pbfs_people_is_hr():
            raise AccessError(self.env._('Only HR can see these details.'))
        return super().render(host_key, record_id)

    # ------------------------------------------------------------ native page
    @api.model
    def _pbfs_people_register_native(self):
        """Make sure the engine knows the Full details form of this host.
        A registration only: the page itself is written by the engine, and
        only when a custom field is placed (THE HOST CONTRACT item 5)."""
        if not self.env.ref(NATIVE_VIEW, raise_if_not_found=False):
            return False
        Native = self.env['pb.form.native.view'].sudo()
        rec = Native.search([('model', '=', MODEL), ('parent_xmlid', '=', NATIVE_VIEW)], limit=1)
        if not rec:
            rec = Native.create({'model': MODEL, 'parent_xmlid': NATIVE_VIEW, 'host_key': HOST,
                                 'titles': page_titles()})
        return rec

    @api.model
    def _pbfs_resync_native(self, model, exclude=()):
        # Called by the engine on every publish and BEFORE every field delete
        # (FS1-6): the employee page is registered just in time, so install
        # stays silent and the very first publish already writes the page.
        if model == MODEL:
            self._pbfs_people_register_native()
        return super()._pbfs_resync_native(model, exclude=exclude)
