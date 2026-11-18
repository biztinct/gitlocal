# -*- coding: utf-8 -*-
""""Asked us to settle year-end tax" — one person, one country, one tax year
(owner ruling YE1, WDGAP S2-B1 follow-up).

In Vietnam a person may ask the employer to settle their year-end personal
income tax for them (ủy quyền quyết toán thay). Such a person gets NO
withholding certificate for that year (Nghị định 254/2026 Điều 24 khoản 2),
is marked in column [10] of appendix 05-1 and counted in Part II of the
declaration ([37]/[38]); their figures stay in the declaration as the form
requires.

HR (payroll officer or manager — the Filings door, `pb.gov.form.rights`)
ticks it on "Prepare a filing" for the year-end form. Who and when are kept,
unticking is written down too. Employees never see or edit it: no portal
route reads this model. Kept here (not in pb_me_tax) so the year-end forms
work without that module.

Effect on certificates is decided when the filing is prepared (no
certificate is made for a ticked person) AND every time an employee asks
(a certificate of a person ticked later is no longer shown). Unticking never
brings a certificate back by itself: HR prepares and releases again.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PbGovYearSettlement(models.Model):
    _name = 'pb.gov.year.settlement'
    _description = 'Asked the employer to settle year-end tax'
    _inherit = ['mail.thread']
    _order = 'tax_year desc, employee_id'

    employee_id = fields.Many2one('hr.employee', required=True, index=True,
                                  ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True)
    country_code = fields.Char(string='Country', size=2, required=True, default='VN')
    tax_year = fields.Integer(required=True, index=True,
                              help="The calendar year the tax year starts in.")
    asked = fields.Boolean(string='Asked us to settle year-end tax')
    marked_by = fields.Many2one('res.users', readonly=True)
    marked_on = fields.Datetime(readonly=True)

    _employee_year_uniq = models.Constraint(
        'unique(employee_id, country_code, tax_year)',
        'One answer per person, country and tax year.')

    @api.model
    def _pb_asked(self, employee_ids, country, tax_year):
        """The ids of the people who asked (sudo: read after the caller's door)."""
        if not employee_ids:
            return set()
        rows = self.sudo().search([('employee_id', 'in', list(employee_ids)),
                                   ('country_code', '=', country),
                                   ('tax_year', '=', int(tax_year)), ('asked', '=', True)])
        return set(rows.mapped('employee_id').ids)

    @api.model
    def _pb_rows(self, employee_ids, country, tax_year):
        rows = self.sudo().search([('employee_id', 'in', list(employee_ids)),
                                   ('country_code', '=', country),
                                   ('tax_year', '=', int(tax_year))])
        return {r.employee_id.id: r for r in rows}

    @api.model
    def _pb_set(self, employee, company, country, tax_year, value):
        """Payroll officer or manager (the Filings door). Who and when kept;
        both directions written in the row's history."""
        self.env['pb.gov.form.rights']._pb_require_officer()
        employee = employee.sudo()
        if employee.company_id != company:
            raise UserError(_("That person belongs to another company."))
        value = bool(value)
        row = self._pb_rows([employee.id], country, tax_year).get(employee.id)
        if not row:
            if not value:
                return True
            row = self.sudo().create({'employee_id': employee.id, 'company_id': company.id,
                                      'country_code': country, 'tax_year': int(tax_year)})
        if bool(row.asked) == value:
            return True
        row.write({'asked': value, 'marked_by': self.env.uid,
                   'marked_on': fields.Datetime.now()})
        if value:
            body = _("%(who)s marked that %(name)s asked us to settle year-end tax for %(year)s.",
                     who=self.env.user.name, name=employee.name or '', year=tax_year)
        else:
            body = _("%(who)s took back “asked us to settle year-end tax” for %(name)s, %(year)s. A certificate appears only when the year is prepared and released again.",
                     who=self.env.user.name, name=employee.name or '', year=tax_year)
        row.message_post(body=body, subtype_xmlid='mail.mt_note')
        return True
