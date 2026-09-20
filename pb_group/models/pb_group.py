# -*- coding: utf-8 -*-
"""`pb.group` — the group is its own record (ruling G1).

WHY NOT `res.company.parent_id`
-------------------------------
Odoo 19's `res.company._get_company_root_delegated_field_names()` returns
`['currency_id']`: a child company copies its root's currency and shows the
field read-only. A dong parent with a Singapore-dollar child is therefore
impossible through the branch tree — and a group of companies in different
countries is the entire point of this programme. So the branch tree is left
exactly as it is, untouched by this module, and membership is one Many2one from
the company to the group.

WHAT THE GROUP DECIDES
----------------------
Three things, and only three:

  * the currency the board reads consolidated figures in (nothing is stored in
    it — see `pb.fx`);
  * how a rate is picked for a month (ruling G4);
  * which month the fiscal year starts in, which every later plan and report
    uses to know what "the year" means.

Everything else about a company stays on the company.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .pb_fx import DEFAULT_POLICY

_logger = logging.getLogger(__name__)



class PbGroup(models.Model):
    _name = 'pb.group'
    _description = 'Group'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(
        string='Group name', required=True, tracking=True,
        help="What this group of companies is called on screen.")
    code = fields.Char(
        string='Short code',
        help="A few letters for reports and file names. Optional.")
    active = fields.Boolean(default=True)

    presentation_currency_id = fields.Many2one(
        'res.currency', string='Group currency', required=True, tracking=True,
        default=lambda self: self.env.company.currency_id,
        help="The money the board reads group figures in. Nothing is stored "
             "in it: every amount keeps the currency it was paid in and is "
             "converted when somebody looks at it.")
    fx_policy = fields.Selection(
        selection=[
            ('month_end', 'The last rate of the month'),
            ('payment_date', 'The rate on the day the pay run ends'),
            ('month_avg', 'The average rate for the month'),
        ],
        string='How rates are picked', required=True, default=DEFAULT_POLICY,
        tracking=True,
        help="Which exchange rate a month's figures are converted at.")
    # An INTEGER 1-12 and not a selection of month names: the names a person
    # reads are the browser's, in the reader's own language and calendar
    # formatting, so there is one list of month names in this product rather
    # than one per model.
    fiscal_start_month = fields.Integer(
        string='Fiscal year starts in', required=True, default=1,
        help="The month your financial year begins, 1 for January. Reports "
             "and plans read this to know what a year means here.")

    # GROUP P5 — ruling G8. When somebody's month is split between two
    # entities, WHO PAYS is a group policy with a per-stretch override, and it
    # lives here because it is a statement about how this group settles between
    # its own companies rather than about any one payroll.
    #
    # `each_pays` is the default because it is the pattern that keeps each
    # entity's books its own, and because it is the only one of the two that
    # produces a second payslip — a thing a reader can see. It is also inert
    # until somebody writes a stretch of days, so shipping it changes nothing.
    split_pay_policy = fields.Selection(
        selection=[
            ('each_pays', 'Each entity pays its own days'),
            ('home_pays', 'Home pays, the other entity is charged'),
        ],
        string='How split months are paid', required=True,
        default='each_pays', tracking=True,
        help="When somebody works part of a month in another company in this "
             "group, this decides who pays for those days.")

    company_ids = fields.One2many(
        'res.company', 'pb_group_id', string='Companies',
        help="The companies this group is made of.")
    company_count = fields.Integer(
        string='Companies in the group', compute='_compute_company_count')
    note = fields.Text(string='Notes')

    _code_uniq = models.Constraint(
        'unique(code)',
        'Another group already uses that short code. Give this one a code of '
        'its own, or leave it empty.')

    # --------------------------------------------------------------- compute
    @api.depends('company_ids')
    def _compute_company_count(self):
        for group in self:
            group.company_count = len(group.company_ids)

    # ------------------------------------------------------------ validation
    @api.constrains('fiscal_start_month')
    def _check_fiscal_start_month(self):
        for group in self:
            if not 1 <= (group.fiscal_start_month or 0) <= 12:
                raise ValidationError(_(
                    "Pick the month your financial year starts in."))

    # ----------------------------------------------------------- the helpers
    @api.model
    def for_company(self, company=None):
        """The group a company belongs to, or an empty recordset."""
        if isinstance(company, models.BaseModel):
            company = company[:1]
        elif isinstance(company, int) and company:
            company = self.env['res.company'].sudo().browse(company).exists()
        else:
            company = self.env.company
        if not company:
            return self.browse()
        return company.sudo().pb_group_id

    def fiscal_year_start(self, on_date=None):
        """The first day of the fiscal year that `on_date` falls in."""
        self.ensure_one()
        day = fields.Date.to_date(on_date) if on_date else \
            fields.Date.context_today(self)
        month = int(self.fiscal_start_month or 1)
        year = day.year if day.month >= month else day.year - 1
        return fields.Date.to_date('%04d-%02d-01' % (year, month))

    def write(self, vals):
        # Archiving a group lets its companies go rather than leaving them
        # pointing at something nobody can see (a dead end by another name).
        res = super().write(vals)
        if 'active' in vals and not vals.get('active'):
            self.sudo().mapped('company_ids').write({'pb_group_id': False})
        return res
