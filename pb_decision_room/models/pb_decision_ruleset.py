# -*- coding: utf-8 -*-
"""`pb.decision.ruleset` — one set of statutory starting points per country.

WHY THIS MODEL EXISTS
---------------------
Phases 1-3 of the Decision Room shipped ONE set of rules: Vietnam's. Every
company on every database inherited a 23.5 % employer contribution and a
₫46,800,000 monthly cap, which is exactly right for Hanoi and nonsense for
Singapore. A group that runs payroll in eight countries then read one picture
built on another country's law and had no way to say so.

So the rules become a RECORD, one per country the payroll engine knows, shipped
as data and editable by the planning lead. A company picks up the rules for its
own country automatically; a scheme inside that company can override them; and
a company that has deliberately typed its own numbers keeps them.

THE RESOLUTION ORDER, which is the whole model in one line:

    the scheme's own overrides
      → the company's own assumptions (only when somebody chose to type them)
        → the ruleset for the company's country
          → Vietnam

The last rung is not a preference, it is the promise that this screen always
has an answer. A company in a country nobody has shipped rules for still draws
a year; it says which rules it used.

THE CAP IS IN A CURRENCY, AND THAT MATTERS
------------------------------------------
"Contributions are capped at 6,800" is a sentence about Singapore dollars.
Applied to a company keeping its books in dong it would cap every salary in the
country at the price of a coffee. So a ruleset carries the CURRENCY its cap is
written in, and `effective_for()` drops the cap — and says why — when the
company's own money is not that currency. Converting it would be worse: an
exchange rate moves and a statutory ceiling does not.

WHAT IS SIMPLIFIED, SAID OUT LOUD
---------------------------------
Every country here has more than one contribution scheme, each with its own
base, its own ceiling and its own split. This model carries ONE employer
percentage, ONE employee percentage and ONE ceiling, because the Decision Room
is a planning picture at company-average precision and not a payroll engine —
the payroll engine is `hr.formula.config`, it is in the same product, and the
"Exact cost" lane runs the plan's people through it. Every shipped row says so
in its own note, in the words a person reads.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

#: The eight countries the payroll engine ships schemes for.
COUNTRIES = [
    ('VN', 'Vietnam'),
    ('SG', 'Singapore'),
    ('ID', 'Indonesia'),
    ('IN', 'India'),
    ('MY', 'Malaysia'),
    ('TH', 'Thailand'),
    ('KH', 'Cambodia'),
    ('PH', 'Philippines'),
]

#: The country every picture falls back to. Not a favourite — the first rules
#: this product ever shipped, and the ones its whole test suite is pinned to.
FALLBACK_COUNTRY = 'VN'

#: The fields a ruleset supplies to the engine. Everything else the engine
#: reads (the revenue target, the shift split, the other costs) is a decision
#: about THIS BUSINESS and stays on `pb.decision.assumptions`.
RULE_FIELDS = (
    'employer_rate_pct', 'employee_rate_pct', 'contribution_cap',
    'allowance_pct', 'ot_multiplier', 'night_uplift_pct', 'work_days',
    'recruit_cost_months', 'severance_months', 'ramp_first_month_pct',
    'bonus_month_index', 'bonus_months', 'pit_ladder',
)


class PbDecisionRuleset(models.Model):
    _name = 'pb.decision.ruleset'
    _inherit = ['mail.thread']
    _description = 'Decision Room country rules'
    _order = 'country_code'
    _rec_name = 'name'

    name = fields.Char(
        string="Name", required=True, tracking=True,
        help="What these rules are called on screen.")
    country_code = fields.Selection(
        COUNTRIES, string="Country", required=True, tracking=True, index=True,
        help="The country these rules describe. A company picks up the rules "
             "for its own country automatically.")
    currency_code = fields.Char(
        string="Money the cap is written in", size=3, tracking=True,
        help="Three letters, for example SGD. A contribution ceiling is a "
             "sentence about one country's money; it is only applied to a "
             "company that keeps its books in it.")
    active = fields.Boolean(default=True)

    employer_rate_pct = fields.Float(
        string="Employer contributions (% of pay)", default=0.0, tracking=True,
        help="Paid by the business on top of pay.")
    employee_rate_pct = fields.Float(
        string="Employee contributions (% of pay)", default=0.0, tracking=True,
        help="Taken out of the employee's pay. Not an extra cost to the "
             "business.")
    contribution_cap = fields.Float(
        string="Contributions are capped at", default=0.0, tracking=True,
        help="Monthly pay above this does not raise contributions. Zero means "
             "there is no ceiling.")
    allowance_pct = fields.Float(
        string="Allowances (% of pay)", default=10.0, tracking=True,
        help="Meal, transport and phone allowances, as a share of base pay.")
    ot_multiplier = fields.Float(
        string="Overtime is paid at", default=1.5, tracking=True,
        help="Times the normal hourly rate.")
    night_uplift_pct = fields.Float(
        string="Night work uplift (%)", default=0.0, tracking=True,
        help="Extra pay for night shifts, on top of base pay.")
    work_days = fields.Integer(
        string="Paid working days a month", default=22, tracking=True,
        help="Used to turn a monthly salary into an hourly rate.")
    recruit_cost_months = fields.Float(
        string="Cost to recruit someone (months of pay)", default=1.0,
        tracking=True)
    severance_months = fields.Float(
        string="Cost to let someone go (months of pay)", default=1.0,
        tracking=True)
    ramp_first_month_pct = fields.Float(
        string="A new person delivers (%) in their first month", default=50.0,
        tracking=True)
    bonus_month_index = fields.Integer(
        string="Bonus is paid in month", default=1, tracking=True,
        help="1 is January. Zero means no yearly bonus.")
    bonus_months = fields.Float(
        string="Bonus size (months of pay)", default=1.0, tracking=True)
    pit_ladder = fields.Json(
        string="Income tax ladder",
        help="The bands used to estimate what an employee takes home. It "
             "never changes the cost to the business.")
    note = fields.Text(
        string="What this simplifies", tracking=True,
        help="What a reader should know before trusting these numbers.")

    _country_uniq = models.Constraint(
        'unique(country_code)',
        "There is already a set of rules for this country.")

    # ------------------------------------------------------------ resolution
    @api.model
    def for_country(self, code):
        """The rules for a country code, falling back to Vietnam.

        Never an empty recordset on a database that installed this module: the
        fallback row is shipped data. On a database where somebody archived
        every row it IS empty, and `effective_for` copes.
        """
        code = (code or '').upper().strip()
        Rule = self.sudo()
        row = Rule.search([('country_code', '=', code)], limit=1) if code \
            else Rule.browse()
        if not row:
            row = Rule.search([('country_code', '=', FALLBACK_COUNTRY)],
                              limit=1)
        return row

    @api.model
    def for_company(self, company):
        """The rules a company follows, read off its own country."""
        company = company[:1] if isinstance(company, models.BaseModel) else \
            self.env['res.company'].sudo().browse(int(company or 0))
        # GR20: `res.company.country_id` is a NON-STORED related field. Reading
        # it is fine; putting it in a domain is a hard error. This reads it.
        code = ''
        if company:
            code = (company.sudo().country_id.code or '').upper()
        return self.for_country(code)

    def _as_dict(self, company=None):
        """The engine-shaped dictionary this ruleset supplies.

        `cap_note` is not decoration: a screen that silently drops a ceiling is
        a screen that lies about a number, and the assumptions card prints this
        sentence beside the cap.
        """
        self.ensure_one()
        out = {name: self[name] for name in RULE_FIELDS}
        out['pit_ladder'] = self.pit_ladder or {'bands': []}
        out['ruleset_id'] = self.id
        out['ruleset_name'] = self.name or ''
        out['country_code'] = self.country_code or ''
        out['cap_currency'] = (self.currency_code or '').upper()
        out['cap_note'] = ''
        own = ''
        if company is not None and company:
            own = (company.sudo().currency_id.name or '').upper()
        if out['contribution_cap'] and out['cap_currency'] and own \
                and own != out['cap_currency']:
            out['cap_note'] = _(
                "The %(country)s ceiling is written in %(cap)s and this "
                "company keeps its books in %(own)s, so no ceiling is applied "
                "here. Type one under Pay & contributions if you need it.",
                country=dict(COUNTRIES).get(self.country_code,
                                            self.country_code or ''),
                cap=out['cap_currency'], own=own)
            out['contribution_cap'] = 0.0
        return out

    @api.model
    def _fallback_dict(self):
        """What a database with no rules at all still answers."""
        from .pb_decision_assumptions import VN_PIT_LADDER
        return {
            'employer_rate_pct': 23.5, 'employee_rate_pct': 10.5,
            'contribution_cap': 0.0, 'allowance_pct': 12.0,
            'ot_multiplier': 1.5, 'night_uplift_pct': 30.0, 'work_days': 22,
            'recruit_cost_months': 1.0, 'severance_months': 1.5,
            'ramp_first_month_pct': 50.0, 'bonus_month_index': 1,
            'bonus_months': 1.0, 'pit_ladder': VN_PIT_LADDER,
            'ruleset_id': 0, 'ruleset_name': _("Vietnam"),
            'country_code': FALLBACK_COUNTRY, 'cap_currency': 'VND',
            'cap_note': '',
        }

    @api.model
    def effective_for(self, company, config=None):
        """Every rule this company (and optionally this scheme) plans under.

        The whole resolution order lives here and nowhere else, so a number on
        the screen and a number in the exact-cost job cannot disagree.
        """
        Assumptions = self.env['pb.decision.assumptions']
        rules = self.for_company(company)
        out = rules._as_dict(company) if rules else self._fallback_dict()
        out['source'] = 'country'
        out['overrides'] = []

        company_row = Assumptions.sudo().search(
            [('company_id', '=', company.id),
             ('scope_kind', '=', 'company')], limit=1)
        if company_row and not company_row.use_country_rules:
            for name in RULE_FIELDS:
                out[name] = company_row[name]
            out['pit_ladder'] = company_row.pit_ladder or {'bands': []}
            out['cap_note'] = ''
            out['source'] = 'company'
            out['overrides'] = list(RULE_FIELDS)

        if config:
            scheme_row = Assumptions.sudo().search(
                [('scope_kind', '=', 'scheme'),
                 ('scope_ref', '=', str(config.id))], limit=1)
            if scheme_row and not scheme_row.use_country_rules:
                for name in RULE_FIELDS:
                    out[name] = scheme_row[name]
                out['pit_ladder'] = scheme_row.pit_ladder or {'bands': []}
                out['cap_note'] = ''
                out['source'] = 'scheme'
                out['overrides'] = list(RULE_FIELDS)
                out['scheme_name'] = config.name or ''
        return out

    @api.model
    def catalogue(self):
        """Every shipped set of rules, for the assumptions card's picker."""
        rows = self.sudo().search([])
        labels = dict(COUNTRIES)
        return [{
            'id': row.id,
            'country_code': row.country_code or '',
            'country': labels.get(row.country_code, row.country_code or ''),
            'name': row.name or '',
            'employer_rate_pct': row.employer_rate_pct,
            'employee_rate_pct': row.employee_rate_pct,
            'contribution_cap': row.contribution_cap,
            'cap_currency': (row.currency_code or '').upper(),
            'note': row.note or '',
        } for row in rows]

    @api.depends('name', 'country_code')
    def _compute_display_name(self):
        labels = dict(COUNTRIES)
        for row in self:
            row.display_name = row.name or labels.get(
                row.country_code, row.country_code or '')
