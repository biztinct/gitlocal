# -*- coding: utf-8 -*-
"""The numbers behind the picture — one settings row per company.

Everything the Decision Room assumes and does not read from the roster lives
here, in one place, in plain words, so the room can show a reader exactly what
it believed when it drew the year. The defaults are Vietnam 2026, simplified to
company averages; a company on another currency gets no contribution cap and an
empty income-tax ladder (take-home is then shown as gross, and the business
cost — which is what profit is made of — is unaffected).
"""

import re

from odoo import api, fields, models, _

#: Vietnam 2026, simplified. Monthly figures in the company's own currency.
VN_PIT_LADDER = {
    'personal': 11000000.0,       # personal deduction, a month
    'dependent': 3960000.0,       # 4.4M x 0.9 dependants on average
    'bands': [                    # [top of band, rate %]
        [5000000.0, 5.0],
        [10000000.0, 10.0],
        [18000000.0, 15.0],
        [32000000.0, 20.0],
        [52000000.0, 25.0],
        [80000000.0, 30.0],
        [0.0, 35.0],              # 0 = everything above the last band
    ],
}

#: A department whose name matches this does not, on its own, earn revenue.
SUPPORT_TEAM_RE = r'finance|account|hr\b|human|admin|legal|it\b|support|payroll'


class PbDecisionAssumptions(models.Model):
    _name = 'pb.decision.assumptions'
    _description = 'Decision Room assumptions'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company', string="Company", required=True, ondelete='cascade',
        default=lambda self: self.env.company,
        help="The company these assumptions describe. One row per company.")

    # ------------------------------------------------------- what we sell
    revenue_target = fields.Monetary(
        string="Revenue target for the year", currency_field='currency_id',
        help="What the business plans to earn this year. Leave it at zero "
             "until you know it — the room then shows people and cost only.")
    demand_growth_pct = fields.Float(
        string="More work by December (%)", default=0.0,
        help="How much more work arrives in December than today, as a "
             "percentage. Zero means the year is flat.")

    # ------------------------------------------ what an employee costs
    employer_rate_pct = fields.Float(
        string="Employer contributions (% of pay)", default=23.5,
        help="Paid by the business on top of pay: social, health and "
             "unemployment insurance and the union fund.")
    employee_rate_pct = fields.Float(
        string="Employee contributions (% of pay)", default=10.5,
        help="Taken out of the employee's pay. Not an extra cost to the "
             "business — it only changes what reaches the employee.")
    contribution_cap = fields.Monetary(
        string="Contributions are capped at", currency_field='currency_id',
        help="Monthly pay above this does not raise contributions. Zero "
             "means there is no cap.")
    allowance_pct = fields.Float(
        string="Allowances (% of pay)", default=12.0,
        help="Meal, transport and phone allowances, as a share of base pay.")
    ot_multiplier = fields.Float(
        string="Overtime is paid at", default=1.5,
        help="Times the normal hourly rate. 1.5 means time and a half.")
    night_uplift_pct = fields.Float(
        string="Night work uplift (%)", default=30.0,
        help="Extra paid for a night hour. Reserved for the shift levers "
             "arriving in the next release.")
    work_days = fields.Integer(
        string="Paid working days a month", default=22,
        help="Used to turn a monthly salary into an hourly rate.")

    # ------------------------------------------------ joining and leaving
    recruit_cost_months = fields.Float(
        string="Cost to recruit someone (months of pay)", default=1.0,
        help="Agency fees, advertising and onboarding, counted once in the "
             "month the person arrives.")
    severance_months = fields.Float(
        string="Cost to let someone go (months of pay)", default=1.5,
        help="Counted once in the month the role ends.")
    ramp_first_month_pct = fields.Float(
        string="A new person delivers (%) in their first month", default=50.0,
        help="They are paid in full from day one. This is how much work they "
             "get done while they are learning.")
    attrition_pct_year = fields.Float(
        string="People who leave in a year (%)", default=12.0,
        help="Only used when you switch leavers on in the room.")

    # ------------------------------------------------------------- bonuses
    bonus_month_index = fields.Integer(
        string="Bonus is paid in month", default=1,
        help="1 is January. Zero means no yearly bonus.")
    bonus_months = fields.Float(
        string="Bonus size (months of pay)", default=1.0,
        help="One means everybody gets one extra month's pay.")

    # -------------------------------------------------- everything else
    other_fixed_monthly = fields.Monetary(
        string="Other costs a month", currency_field='currency_id',
        help="Rent, energy, software and everything else that is not people.")
    other_pct_revenue = fields.Float(
        string="Other costs that follow revenue (%)", default=25.0,
        help="Materials, delivery and commission — costs that rise with what "
             "you sell.")

    revenue_team_ids = fields.Many2many(
        'hr.department', string="Teams that earn revenue",
        help="The teams whose people directly produce what the company "
             "sells. Support teams matter, but adding one of them does not "
             "raise what the business can deliver.")

    pit_ladder = fields.Json(
        string="Income tax ladder",
        help="The bands used to estimate what an employee takes home. It "
             "never changes the cost to the business.")

    note = fields.Text(
        string="Note",
        help="Anything a reader should know about these numbers.")

    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    _company_uniq = models.Constraint(
        'unique(company_id)',
        "This company already has a set of Decision Room assumptions.")

    # ------------------------------------------------------------ defaults
    @api.model
    def _defaults_for(self, company):
        """The first row a company gets, tuned to what we can see of it."""
        vnd = (company.currency_id.name or '').upper() == 'VND'
        vals = {
            'company_id': company.id,
            'contribution_cap': 46800000.0 if vnd else 0.0,
            'pit_ladder': VN_PIT_LADDER if vnd else {'bands': []},
        }
        departments = self.env['hr.department'].sudo().search([
            ('company_id', '=', company.id), ('parent_id', '=', False),
        ])
        if not departments:
            departments = self.env['hr.department'].sudo().search([
                ('company_id', '=', company.id),
            ])
        earners = departments.filtered(
            lambda d: not re.search(SUPPORT_TEAM_RE, (d.name or '').lower()))
        vals['revenue_team_ids'] = [(6, 0, (earners or departments).ids)]
        return vals

    @api.model
    def get_for_company(self, company):
        """The row for this company, created on first read.

        The CREATE is under sudo — this is a settings row every reader of the
        room needs and nobody should have to be an administrator to open a
        screen. The READ that follows is not: the caller sees it through their
        own rights and the company rule.
        """
        company = company or self.env.company
        row = self.sudo().search([('company_id', '=', company.id)], limit=1)
        if not row:
            row = self.sudo().create(self._defaults_for(company))
        return self.browse(row.id)

    @api.depends('company_id')
    def _compute_display_name(self):
        for row in self:
            row.display_name = _("Assumptions · %s",
                                 row.company_id.display_name or "")
