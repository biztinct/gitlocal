"""Full employee form uses the same read-only payroll summary as the drawer.

The vault is optional. Without it, keep the Vietnam module's original form.
Do not copy scheme rates into legacy fields or change dependent registration.
"""
from markupsafe import Markup

from odoo import api, fields, models


INSURANCE_KEYS = frozenset({
    'vietnam_social_insurance_number', 'VNSIJOIN', 'VNHIJOIN', 'VNUIJOIN',
    'VNINSMODE', 'vn_insurance_salary',
})
SHARED_KEYS = frozenset({'vn_payroll_scheme', 'vn_settings_date'})


def profile_html(rows, note):
    """Escape every label/value, including customer names and scheme names."""
    return Markup('<div><p class="text-muted">%s</p><div class="row">%s</div></div>') % (
        note,
        Markup('').join(
            Markup('<div class="col-12 col-md-6 mb-3"><div class="text-muted">%s</div>'
                   '<div><strong>%s</strong></div></div>') % (row['label'], row['value'])
            for row in rows
        ),
    )


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # Nonstored and computed as the reader: never cache a manager's salary
    # display for another account, and never elevate normal record access.
    vn_uses_payroll_profile = fields.Boolean(compute='_compute_vn_payroll_profile', compute_sudo=False)
    vn_payroll_tax_summary = fields.Html(
        string='Current payroll tax settings', compute='_compute_vn_payroll_profile', compute_sudo=False)
    vn_payroll_insurance_summary = fields.Html(
        string='Current payroll insurance settings', compute='_compute_vn_payroll_profile', compute_sudo=False)

    @api.depends_context('uid', 'company', 'lang', 'tz')
    def _compute_vn_payroll_profile(self):
        people = self.env.get('pb.people')
        available = people is not None and hasattr(people, '_e360_vietnam')
        for employee in self:
            employee.vn_uses_payroll_profile = False
            employee.vn_payroll_tax_summary = False
            employee.vn_payroll_insurance_summary = False
            if not available or not employee._origin.id:
                continue
            # The same HR gate and salary masking as get_employee_360().
            if not people._vault_is_hr():
                continue
            profile = people._e360_vietnam(employee._origin, people._vault_unmask_wage())
            if not profile:
                continue
            group = profile['groups'][0]
            employee.vn_uses_payroll_profile = True
            employee.vn_payroll_tax_summary = profile_html(
                [row for row in group['rows'] if row['key'] not in INSURANCE_KEYS], group['note'])
            employee.vn_payroll_insurance_summary = profile_html(
                [row for row in group['rows'] if row['key'] in INSURANCE_KEYS | SHARED_KEYS], group['note'])
