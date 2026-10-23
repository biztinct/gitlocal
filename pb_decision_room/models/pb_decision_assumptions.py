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

GROUP PHASE 4 gave the row a SCOPE. There is no longer one set of assumptions
per company: there is one per thing a plan can be about — the group, a country,
a company, a division, a payroll scheme — created on first read, exactly as the
company row always was. Two consequences worth knowing before reading further:

  * the statutory half of this record (contribution rates, the ceiling, the
    allowance share, working days, the bonus, the tax ladder) now has a
    SOURCE. `use_country_rules` says whether it comes from
    `pb.decision.ruleset` for the company's own country or from the numbers
    typed here. A row somebody has already tuned keeps its numbers — the
    upgrade sets the switch OFF for every row that existed before this phase,
    because a picture that changed by itself on the morning of an upgrade is
    the one thing a planning record may never do;
  * the business half (the revenue target, demand, shifts, other costs) is
    always this row's own, whatever the scope. Singapore's law does not have an
    opinion about your revenue target.
"""

import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

#: The statutory half — the fields a country ruleset can supply.
from .pb_decision_ruleset import RULE_FIELDS  # noqa: E402  (documented above)

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
        help="The company these assumptions describe. For a group or a "
             "country this is the first company in it, and the scope below is "
             "what the row is really about.")

    # ------------------------------------------------------------- the scope
    scope_kind = fields.Selection(
        [('group', "Whole group"), ('country', "Country"),
         ('company', "Company"), ('division', "Division"),
         ('scheme', "Payroll scheme")],
        string="These numbers are for", required=True, default='company',
        index=True, tracking=True,
        help="What these assumptions describe: the whole group, one country, "
             "one company, one division, or the people one payroll scheme "
             "pays.")
    scope_ref = fields.Char(
        string="Which one", index=True,
        help="Which group, country, company, division or scheme.")
    scope_label = fields.Char(
        string="Scope", tracking=True,
        help="The name a reader sees on the chip at the top of the room.")
    company_ids = fields.Many2many(
        'res.company', 'pb_decision_assumptions_company_rel',
        'assumptions_id', 'company_id', string="Companies in this scope",
        help="Every legal entity these assumptions cover.")

    use_country_rules = fields.Boolean(
        string="Follow the rules for this country", default=True,
        tracking=True,
        help="On: contributions, the ceiling, allowances, working days and "
             "the bonus come from the rules shipped for this company's "
             "country. Off: they are the numbers typed here.")
    ruleset_id = fields.Many2one(
        'pb.decision.ruleset', string="Country rules",
        compute='_compute_ruleset_id',
        help="The set of country rules this scope follows when the switch "
             "above is on.")

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
        'res.currency', string="Currency", compute='_compute_currency_id',
        help="The money the amounts on this row are written in. For a scope "
             "that spans two currencies it is the group's own money.")

    _scope_uniq = models.Constraint(
        'unique(scope_kind, scope_ref)',
        "There is already a set of Decision Room assumptions for this.")

    # ------------------------------------------------------------- computes
    @api.depends('company_id', 'company_ids', 'scope_kind')
    def _compute_currency_id(self):
        """One currency, or the group's when the scope spans several.

        Never a guess and never a conversion: this only decides which money the
        numbers a person TYPES on this row are written in.
        """
        for row in self:
            currencies = (row.company_ids or row.company_id).mapped(
                'currency_id')
            if len(currencies) == 1:
                row.currency_id = currencies
                continue
            group = row.company_id.sudo().pb_group_id \
                if 'pb_group_id' in self.env['res.company']._fields else None
            row.currency_id = (group.presentation_currency_id if group
                               else row.company_id.currency_id)

    @api.depends('company_id', 'scope_kind')
    def _compute_ruleset_id(self):
        Ruleset = self.env['pb.decision.ruleset']
        for row in self:
            row.ruleset_id = Ruleset.for_company(row.company_id)

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
        return self.get_for_scope({
            'kind': 'company', 'ref': str(company.id),
            'label': company.display_name, 'company_ids': company.ids,
        })

    @api.model
    def get_for_scope(self, scope):
        """The row for one scope, created on first read.

        A company scope keeps the row it has always had — same record, same
        chatter, same numbers — which is what makes the identity test possible
        at all. Every other scope gets a row of its own the first time somebody
        looks at it.
        """
        scope = scope or {}
        kind = scope.get('kind') or 'company'
        ref = str(scope.get('ref') or '')
        ids = [int(i) for i in (scope.get('company_ids') or []) if i]
        company = self.env['res.company'].sudo().browse(
            ids[0]) if ids else self.env.company
        row = self.sudo().search(
            [('scope_kind', '=', kind), ('scope_ref', '=', ref)], limit=1)
        if not row and kind == 'company':
            # The row this company has carried since Phase 1, before scopes
            # existed. Adopted rather than duplicated.
            row = self.sudo().search(
                [('company_id', '=', company.id),
                 ('scope_kind', '=', 'company'),
                 '|', ('scope_ref', '=', False), ('scope_ref', '=', '')],
                limit=1)
            if row:
                row.write({'scope_ref': ref or str(company.id),
                           'scope_label': company.display_name})
        if not row:
            vals = self._defaults_for(company)
            vals.update({
                'scope_kind': kind,
                'scope_ref': ref,
                'scope_label': scope.get('label') or company.display_name,
                'company_ids': [(6, 0, ids or company.ids)],
            })
            row = self.sudo().create(vals)
        elif scope.get('label') and row.scope_label != scope.get('label'):
            row.sudo().write({'scope_label': scope.get('label')})
        if ids and set(row.company_ids.ids) != set(ids):
            row.sudo().write({'company_ids': [(6, 0, ids)]})
        return self.browse(row.id)

    @api.model
    def effective(self, row, company, config=None):
        """The whole assumption dictionary the engine is handed for a company.

        The business half is the ROW's; the statutory half is whatever
        `pb.decision.ruleset.effective_for()` resolves. One function, so the
        picture on screen and the exact-cost job can never disagree about which
        rules were used.
        """
        Ruleset = self.env['pb.decision.ruleset']
        rules = Ruleset.effective_for(company, config=config)
        out = self.env['pb.decision.room']._assumptions_dict(row)
        if row and not row.use_country_rules:
            rules['source'] = 'company' if not config else rules.get(
                'source', 'company')
            rules['overrides'] = list(RULE_FIELDS)
            for name in RULE_FIELDS:
                rules[name] = out.get(name, rules.get(name))
            rules['cap_note'] = ''
        for name in RULE_FIELDS:
            out[name] = rules[name]
        out['rules_source'] = rules.get('source', 'country')
        out['rules_country'] = rules.get('country_code', '')
        out['rules_name'] = rules.get('ruleset_name', '')
        out['cap_note'] = rules.get('cap_note', '')
        out['cap_currency'] = rules.get('cap_currency', '')
        return out

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

    @api.depends('company_id', 'scope_label')
    def _compute_display_name(self):
        for row in self:
            row.display_name = _("Assumptions · %s",
                                 row.scope_label
                                 or row.company_id.display_name or "")
