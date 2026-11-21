# -*- coding: utf-8 -*-
"""Country of Work as a country record, for the Form builder (R10).

The employee's Country of Work is the selection `payroll_country`
(`pb_hr_payroll_base/models/hr_payroll_structure_base.py:266`, extra choices
`pb_hr_payroll_formula/models/employee_work_timezone.py:70`) — the same box
the People list's "Country of Work" filter reads (`pb_people.py:307`,
FIELD_AUDIT_FACTS §6). Its values are country CODES; the Form builder's host
contract asks for a path to a `res.country` record (`country_field`) and a
direct many2one for the "Full details" page (`country_view_field`). This
non-stored field is that bridge: no column, nothing written, recomputed
whenever the box changes.
"""
import logging

from odoo import api, fields, models

from odoo.addons.pb_form_studio.models.form_standard import STD_RAW

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # ------------------------------------------------- R23 screen rule
    @api.model
    def _get_view_cache_key(self, view_id=None, view_type='form', **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        return key + (bool(self.env.context.get(STD_RAW)),)

    @api.model
    def _pbfs_tab_names(self, arch):
        """FS-7 addition (coordinator, 2026-11-20): the tab names of Full
        details still English for Indonesian readers — "Payroll Info"
        (pb_hr_payroll_formula), "Insurance (BH)" and "Tax & Dependents"
        (pb_hr_payroll_vietnam) have no Indonesian text of their own. The same
        seam as FS follow-up 1 (`pb_employee_form_tidy` `_pb_tidy_tab_names`,
        gotcha FU1-4): a page still carrying the English words gets this
        module's words (code terms of this module's .po); the stored copy is
        fixed on each database by the go-live too. An owner translation, once
        it exists, wins (the English words are then gone)."""
        if (self.env.lang or 'en_US') == 'en_US':
            return
        words = {
            'Payroll Info': self.env._("Payroll Info"),
            'Insurance (BH)': self.env._("Insurance (BH)"),
            'Tax & Dependents': self.env._("Tax & Dependents"),
        }
        self.env['pb.form.studio']._pbfs_translate_pages(arch, words)

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """Every employee form ("Full details" and the others) follows the
        administrator's screen rule for standard fields (R23): hidden ones get
        `invisible` joined with the product's own rule, renamed ones their
        own label — on the COMBINED form, so a field an upgrade removed
        simply matches nothing (TIDY-E's seam, `pb_employee_form_tidy/models/
        hr_employee.py`). Never costs the form: on any error it is shown as
        the modules draw it."""
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != 'form':
            return arch, view
        self._pbfs_tab_names(arch)
        if self.env.context.get(STD_RAW):
            return arch, view
        try:
            self.env['pb.form.studio']._pbfs_std_apply_arch(
                arch, self._name, 'pbfs_country_of_work_id')
        except Exception:                               # noqa: BLE001
            _logger.exception('Form builder: the screen rule of standard fields could not be '
                              'applied to the employee form; it is shown as the modules draw it.')
            arch, view = super()._get_view(view_id, view_type, **options)
        return arch, view

    pbfs_country_of_work_id = fields.Many2one(
        'res.country', string='Country of Work',
        compute='_compute_pbfs_country_of_work_id', compute_sudo=True,
        help='The country of the Country of Work box, used to show only the '
             'fields that apply to it.')

    @api.depends('payroll_country')
    def _compute_pbfs_country_of_work_id(self):
        codes = {str(c).upper() for c in self.mapped('payroll_country') if c}
        by_code = {}
        if codes:
            for country in self.env['res.country'].sudo().search([('code', 'in', list(codes))]):
                by_code[(country.code or '').upper()] = country.id
        for emp in self:
            emp.pbfs_country_of_work_id = by_code.get(str(emp.payroll_country or '').upper(), False)
