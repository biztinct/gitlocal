# -*- coding: utf-8 -*-
"""The numbers behind the picture — one settings row per company.

Everything the Decision Room assumes and does not read from the roster lives
here, in one place, in plain words, so the room can show a reader exactly what
it believed when it drew the year. The defaults are Vietnam 2026, simplified to
company averages; a company on another currency gets no contribution cap and an
empty income-tax ladder (take-home is then shown as gross, and the business
cost — which is what profit is made of — is unaffected).

PHASE 2 made this row EDITABLE from the room, which is why every number now
carries `tracking=True` and the model carries `mail.thread`: an assumption that
anybody can change is only trustworthy if the record can say who changed it,
when, and what it used to be. `EDIT_FORM` below is the single description of
that editing surface — label, help, kind and range — so the dialog in the
browser is GENERATED from the model rather than hand-written a second time and
allowed to drift from it.
"""

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

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

#: The editable surface, in the order the dialog shows it.
#: (group, field, kind, step, min, max). `kind` tells the browser which control
#: to draw: a compact money box, a percentage, months of pay, a whole number, or
#: the department chips.
EDIT_FORM = [
    ("Revenue & demand", 'revenue_target', 'money', 1, 0, 0),
    ("Revenue & demand", 'demand_growth_pct', 'pct', 1, -50, 100),
    ("Revenue & demand", 'revenue_team_ids', 'teams', 0, 0, 0),
    ("Pay & contributions", 'employer_rate_pct', 'pct', 0.5, 0, 60),
    ("Pay & contributions", 'employee_rate_pct', 'pct', 0.5, 0, 40),
    ("Pay & contributions", 'contribution_cap', 'money', 1, 0, 0),
    ("Pay & contributions", 'allowance_pct', 'pct', 0.5, 0, 60),
    ("Pay & contributions", 'bonus_months', 'months', 0.5, 0, 4),
    ("Pay & contributions", 'bonus_month_index', 'int', 1, 0, 12),
    ("Hiring & leaving", 'recruit_cost_months', 'months', 0.25, 0, 6),
    ("Hiring & leaving", 'severance_months', 'months', 0.25, 0, 12),
    ("Hiring & leaving", 'ramp_first_month_pct', 'pct', 5, 0, 100),
    ("Hiring & leaving", 'attrition_pct_year', 'pct', 1, 0, 80),
    ("Shifts & hours", 'work_days', 'int', 1, 1, 31),
    ("Shifts & hours", 'ot_multiplier', 'rate', 0.05, 1, 4),
    ("Shifts & hours", 'shift_evening_pct', 'pct', 1, 0, 50),
    ("Shifts & hours", 'shift_night_pct', 'pct', 1, 0, 40),
    ("Shifts & hours", 'evening_uplift_pct', 'pct', 1, 0, 100),
    ("Shifts & hours", 'night_uplift_pct', 'pct', 1, 0, 100),
    ("Shifts & hours", 'demand_day_pct', 'pct', 1, 0, 100),
    ("Shifts & hours", 'demand_evening_pct', 'pct', 1, 0, 100),
    ("Shifts & hours", 'demand_night_pct', 'pct', 1, 0, 100),
    ("Other costs", 'other_fixed_monthly', 'money', 1, 0, 0),
    ("Other costs", 'other_pct_revenue', 'pct', 1, 0, 95),
    ("Other costs", 'productivity_cost_per_point', 'money', 1, 0, 0),
]

#: The order the dialog groups appear in.
EDIT_GROUPS = ["Revenue & demand", "Pay & contributions", "Hiring & leaving",
               "Shifts & hours", "Other costs"]


class PbDecisionAssumptions(models.Model):
    _name = 'pb.decision.assumptions'
    _inherit = ['mail.thread']
    _description = 'Decision Room assumptions'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company', string="Company", required=True, ondelete='cascade',
        default=lambda self: self.env.company,
        help="The company these assumptions describe. One row per company.")

    # ------------------------------------------------------- what we sell
    revenue_target = fields.Monetary(
        string="Revenue target for the year", currency_field='currency_id',
        tracking=True,
        help="What the business plans to earn this year. Leave it at zero "
             "until you know it — the room then shows people and cost only.")
    demand_growth_pct = fields.Float(
        string="More work by December (%)", default=0.0, tracking=True,
        help="How much more work arrives in December than today, as a "
             "percentage. Zero means the year is flat.")

    # ------------------------------------------ what an employee costs
    employer_rate_pct = fields.Float(
        string="Employer contributions (% of pay)", default=23.5,
        tracking=True,
        help="Paid by the business on top of pay: social, health and "
             "unemployment insurance and the union fund.")
    employee_rate_pct = fields.Float(
        string="Employee contributions (% of pay)", default=10.5,
        tracking=True,
        help="Taken out of the employee's pay. Not an extra cost to the "
             "business — it only changes what reaches the employee.")
    contribution_cap = fields.Monetary(
        string="Contributions are capped at", currency_field='currency_id',
        tracking=True,
        help="Monthly pay above this does not raise contributions. Zero "
             "means there is no cap.")
    allowance_pct = fields.Float(
        string="Allowances (% of pay)", default=12.0, tracking=True,
        help="Meal, transport and phone allowances, as a share of base pay.")
    ot_multiplier = fields.Float(
        string="Overtime is paid at", default=1.5, tracking=True,
        help="Times the normal hourly rate. 1.5 means time and a half.")
    work_days = fields.Integer(
        string="Paid working days a month", default=22, tracking=True,
        help="Used to turn a monthly salary into an hourly rate.")

    # ------------------------------------------------------------ shifts
    shift_evening_pct = fields.Float(
        string="People on the evening shift (%)", default=25.0, tracking=True,
        help="The share of the people who earn revenue who work the evening "
             "shift. The rest of the day is covered by the day shift.")
    shift_night_pct = fields.Float(
        string="People on the night shift (%)", default=15.0, tracking=True,
        help="The share of the people who earn revenue who work nights.")
    evening_uplift_pct = fields.Float(
        string="Evening work uplift (%)", default=0.0, tracking=True,
        help="Extra pay for evening shifts, on top of base pay.")
    night_uplift_pct = fields.Float(
        string="Night work uplift (%)", default=30.0, tracking=True,
        help="Extra pay for night shifts, on top of base pay.")
    demand_day_pct = fields.Float(
        string="Work that arrives during the day (%)", default=60.0,
        tracking=True,
        help="How the year's work is spread across the three shifts. The "
             "three shares must add up to 100.")
    demand_evening_pct = fields.Float(
        string="Work that arrives in the evening (%)", default=25.0,
        tracking=True,
        help="How much of the work has to be done in the evening.")
    demand_night_pct = fields.Float(
        string="Work that arrives at night (%)", default=15.0, tracking=True,
        help="How much of the work has to be done at night.")

    # ------------------------------------------------ joining and leaving
    recruit_cost_months = fields.Float(
        string="Cost to recruit someone (months of pay)", default=1.0,
        tracking=True,
        help="Agency fees, advertising and onboarding, counted once in the "
             "month the person arrives.")
    severance_months = fields.Float(
        string="Cost to let someone go (months of pay)", default=1.5,
        tracking=True,
        help="Counted once in the month the role ends.")
    ramp_first_month_pct = fields.Float(
        string="A new person delivers (%) in their first month", default=50.0,
        tracking=True,
        help="They are paid in full from day one. This is how much work they "
             "get done while they are learning.")
    attrition_pct_year = fields.Float(
        string="People who leave in a year (%)", default=12.0, tracking=True,
        help="Only used when you switch leavers on in the room.")

    # ------------------------------------------------------------- bonuses
    bonus_month_index = fields.Integer(
        string="Bonus is paid in month", default=1, tracking=True,
        help="1 is January. Zero means no yearly bonus.")
    bonus_months = fields.Float(
        string="Bonus size (months of pay)", default=1.0, tracking=True,
        help="One means everybody gets one extra month's pay.")

    # -------------------------------------------------- everything else
    other_fixed_monthly = fields.Monetary(
        string="Other costs a month", currency_field='currency_id',
        tracking=True,
        help="Rent, energy, software and everything else that is not people.")
    other_pct_revenue = fields.Float(
        string="Other costs that follow revenue (%)", default=25.0,
        tracking=True,
        help="Materials, delivery and commission — costs that rise with what "
             "you sell.")
    productivity_cost_per_point = fields.Monetary(
        string="Cost of one point of productivity", currency_field='currency_id',
        default=0.0, tracking=True,
        help="What it costs, per person per month, to gain one percent more "
             "productive time — training, tools and supervision. Zero means "
             "the improvement is assumed to be free.")

    revenue_team_ids = fields.Many2many(
        'hr.department', string="Teams that earn revenue", tracking=True,
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

    # ------------------------------------------------------------- rails
    @api.constrains('demand_day_pct', 'demand_evening_pct',
                    'demand_night_pct')
    def _check_demand_shares(self):
        """The work has to arrive at some point in the day.

        Said as a sentence a person can act on, and with the three numbers in
        it, because "constraint violated" tells a reader nothing about which
        box to change.
        """
        for row in self:
            total = (row.demand_day_pct + row.demand_evening_pct
                     + row.demand_night_pct)
            if abs(total - 100.0) > 0.01:
                raise ValidationError(_(
                    "Day, evening and night have to add up to 100%% of the "
                    "work. They currently add up to %(total)s%% "
                    "(%(day)s + %(evening)s + %(night)s).",
                    total=round(total, 1), day=round(row.demand_day_pct, 1),
                    evening=round(row.demand_evening_pct, 1),
                    night=round(row.demand_night_pct, 1)))

    @api.constrains('shift_evening_pct', 'shift_night_pct')
    def _check_shift_shares(self):
        for row in self:
            if row.shift_evening_pct + row.shift_night_pct > 80.0 + 1e-6:
                raise ValidationError(_(
                    "Evening and night together cannot be more than 80% of "
                    "your people — somebody has to work the day."))

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

    # --------------------------------------------------------- the form
    @api.model
    def edit_form(self):
        """The editable surface, described once, for the browser to draw.

        Label and help come from the FIELD, so a wording change lands in the
        dialog without anybody remembering to copy it across.
        """
        out = []
        for group, name, kind, step, low, high in EDIT_FORM:
            field = self._fields.get(name)
            if not field:
                continue
            out.append({
                'group': group,
                'key': name,
                'label': field.string or name,
                'help': field.help or '',
                'kind': kind,
                'step': step,
                'min': low,
                'max': high,
            })
        return out

    @api.depends('company_id')
    def _compute_display_name(self):
        for row in self:
            row.display_name = _("Assumptions · %s",
                                 row.company_id.display_name or "")
