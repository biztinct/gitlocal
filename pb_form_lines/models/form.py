# -*- coding: utf-8 -*-
"""The catalogue of government forms, their lines, and each company's
standing with each form.

A FORM IS DATA. Each form and each of its lines is a data record shipped with
`noupdate="1"`; a renderer method per form code turns the reader's figures into
the authority's file. Wave 2 adds forms as data plus one small renderer.

EVERY FORM SAYS WHERE IT CAME FROM (owner ruling G3). `source_note` names the
published specification it was built from (name, address, version or date);
anything that could not be confirmed from a published source is marked
`inferred` with the reason in `inferred_note`, and the screen says so.

THE ADVISER MARK (G3). Until a company's HR marks a form "Accepted by the
authority" (`pb.gov.form.company.accepted`, payroll manager only, who and when
kept, can be unticked), every file made for that company and form carries the
sentence "Check with your adviser before first filing" and the screen shows it.

Line kinds (`pb.gov.form.line.kind`):

  money     the sum of the pay items mapped to it (or, with a `base_line_id`,
            the base line's per-person amounts for one population);
  count     how many people — everyone in the filing, or those for whom
            `only_if_line_id` is not zero, for one population;
  text      a per-person text read from a mapped item (e.g. a tax status);
  computed  worked out from other lines (`compute_op`: sum / ratio / percent
            of `operand_codes`). A computed line may still be mapped; a
            mapping then wins over the computation. In a sum, an operand
            written with a leading minus ("-2i") is taken away (WDGAP S2-B:
            "3 = 1(d) - 2(i)").

Sign rules: `never_negative` shows a figure below zero as zero and says so on
the person; `positive_part` keeps only the part above zero quietly (a "still
to pay" line beside an "overpaid" line).

WDGAP S2-B adds per form: `tile_group` (the Filings tile group: tax returns,
year-end, fund files), `year_start_month` (the authority's tax year, India =
April), `employee_certificates` (one PDF per person, released to employees on
My Payobook by a payroll manager) and `screen_note` (what the files are for).
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

#: Who prepares filings and maps form lines (the filing flow's own rule,
#: `pb_govt_reports/models/pb_filing_flow.py` `_FILING_GROUPS`).
OFFICER_GROUPS = ('pb_hr_payroll_base.group_payroll_base_officer',
                  'pb_hr_payroll_base.group_payroll_base_manager')
#: Who may say "accepted by the authority".
MANAGER_GROUPS = ('pb_hr_payroll_base.group_payroll_base_manager',)

PERIOD_KINDS = [('month', 'Month'), ('quarter', 'Quarter'),
                ('tax_year', 'Tax year')]
LINE_KINDS = [('money', 'Amount'), ('count', 'Number of people'),
              ('text', 'Text'), ('computed', 'Worked out from other lines')]
SCOPES = [('employee', 'Per person'), ('total', 'Total only')]
POPULATIONS = [('all', 'Everyone'), ('resident', 'Tax residents'),
               ('non_resident', 'Non-residents')]
COMPUTE_OPS = [('sum', 'Sum of lines'), ('ratio', 'One line divided by another'),
               ('percent', 'Percentage of a line')]
SIGN_RULES = [('as_read', 'As read from the payslips'),
              ('never_negative', 'Never below zero'),
              ('positive_part', 'Only the part above zero')]
#: Where a form's tile sits on Compliance › Filings (WDGAP S2-B: year-end
#: paperwork beside the monthly returns; fund files for wave 2's other half).
TILE_GROUPS = [('tax_return', 'Tax returns'), ('year_end', 'Year-end'),
               ('fund_file', 'Fund files')]


def has_any(user, groups):
    if user._is_superuser():
        return True
    for group in groups:
        try:
            if user.has_group(group):
                return True
        except (ValueError, KeyError):
            continue
    return False


class PbGovForm(models.Model):
    _name = 'pb.gov.form'
    _description = 'Government form'
    _order = 'country_code, sequence, id'

    name = fields.Char(required=True, translate=True)
    official_name = fields.Char(
        string='Name on the form', help="The form's own title, in the "
        "authority's language. Never translated.")
    code = fields.Char(required=True, index=True,
                       help="Technical key; also picks the file renderer.")
    country_code = fields.Char(string='Country', size=2, required=True, index=True)
    authority = fields.Char(translate=True)
    period_kind = fields.Selection(PERIOD_KINDS, required=True, default='month')
    quarter_allowed = fields.Boolean(
        string='May also be filed for a quarter',
        help="A monthly form the authority also accepts per quarter.")
    output_kinds = fields.Char(string='Files made',
                               help="Comma-separated: xml, xlsx, csv.")
    total_line_code = fields.Char(
        help="The line whose total an approver sees as the amount.")
    source_note = fields.Text(string='Where the layout comes from')
    source_url = fields.Char(string='Published at')
    inferred = fields.Boolean(
        string='Not confirmed from an official source',
        help="Part of this layout could not be confirmed from the authority's "
             "own published specification.")
    inferred_note = fields.Text(string='What is not confirmed')
    valid_from = fields.Date(help="First period this layout is for.")
    valid_to = fields.Date(help="Last period this layout is for.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    line_ids = fields.One2many('pb.gov.form.line', 'form_id', string='Lines')
    # ---- WDGAP S2-B (year-end paperwork)
    tile_group = fields.Selection(
        TILE_GROUPS, string='Shown under', required=True, default='tax_return',
        help="Which group of tiles on Compliance › Filings shows this form.")
    year_start_month = fields.Integer(
        string="Authority's tax year starts in", default=1,
        help="1-12. The month the authority's own tax year starts in (India: "
             "April). Used for tax-year and quarter periods; each pay scheme "
             "still says its own tax year and the reader warns when they differ.")
    employee_certificates = fields.Boolean(
        string='Makes a certificate for each person',
        help="Preparing this form also makes one PDF per person, which a "
             "payroll manager can release to employees on My Payobook once "
             "the filing is approved.")
    screen_note = fields.Text(
        translate=True, help="A plain sentence shown on the screen beside the "
                             "form (what the files are for).")

    _code_uniq = models.Constraint('unique(code)', 'A form code is used once.')

    def _pb_valid_for(self, day):
        self.ensure_one()
        day = fields.Date.to_date(day)
        if not day:
            return True
        if self.valid_from and day < self.valid_from:
            return False
        if self.valid_to and day > self.valid_to:
            return False
        return True

    def _pb_line(self, code):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.code == code)[:1]

    def _pb_ordered_lines(self):
        self.ensure_one()
        return self.line_ids.sorted(lambda l: (l.sequence, l.id))


class PbGovFormLine(models.Model):
    _name = 'pb.gov.form.line'
    _description = 'Line of a government form'
    _order = 'form_id, sequence, id'

    form_id = fields.Many2one('pb.gov.form', required=True, index=True,
                              ondelete='cascade')
    code = fields.Char(required=True, help="The box number or column on the form.")
    label = fields.Char(required=True, translate=True)
    official_label = fields.Char(
        string='Words on the form', help="The line's own words on the form, in "
        "the authority's language. Never translated.")
    sequence = fields.Integer(default=10)
    kind = fields.Selection(LINE_KINDS, required=True, default='money')
    scope = fields.Selection(SCOPES, required=True, default='employee')
    population = fields.Selection(POPULATIONS, required=True, default='all')
    base_line_id = fields.Many2one(
        'pb.gov.form.line', string='Same people and items as',
        help="This line takes the per-person amounts of that line, for its "
             "own population only. Nothing is mapped to it.")
    only_if_line_id = fields.Many2one(
        'pb.gov.form.line', string='Only people with an amount on',
        help="Counts or adds only the people for whom that line is not zero.")
    compute_op = fields.Selection(COMPUTE_OPS)
    operand_codes = fields.Char(help="Comma-separated line codes.")
    factor = fields.Float(default=1.0, digits=(16, 6))
    round_digits = fields.Integer(
        default=-1, help="-1: the money's own rounding.")
    sign_rule = fields.Selection(SIGN_RULES, required=True, default='as_read')
    required = fields.Boolean(
        string='Needs a pay item',
        help="The form is not complete until a pay item is on this line.")
    mappable = fields.Boolean(default=True,
                              help="HR may put pay items on this line.")
    suggest_words = fields.Char(
        help="Words (any language, comma-separated) the Suggest pass looks "
             "for in pay item names.")
    suggest_roles = fields.Char(
        help="Comma-separated pay roles the Suggest pass accepts.")
    note = fields.Text(translate=True)
    inferred = fields.Boolean(string='Not confirmed from an official source')
    map_ids = fields.One2many('pb.gov.form.map', 'line_id', string='Pay items')

    _form_code_uniq = models.Constraint('unique(form_id, code)',
                                        'A line code is used once per form.')

    def _pb_operands(self):
        self.ensure_one()
        return [c.strip() for c in (self.operand_codes or '').split(',') if c.strip()]

    def _pb_kind_label(self):
        self.ensure_one()
        return dict(self._fields['kind']._description_selection(self.env)).get(
            self.kind, '')


class PbGovFormCompany(models.Model):
    """One company's standing with one form: the adviser mark (G3) and the
    few company facts the form's file needs (the employer's tax number and
    place of business). Made on first use, never by install."""
    _name = 'pb.gov.form.company'
    _description = "A company's settings for a government form"
    _inherit = ['mail.thread']
    _order = 'company_id, form_id'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    form_id = fields.Many2one('pb.gov.form', required=True, index=True,
                              ondelete='cascade')
    accepted = fields.Boolean(string='Accepted by the authority', readonly=True,
                              tracking=True)
    accepted_by = fields.Many2one('res.users', readonly=True)
    accepted_on = fields.Datetime(readonly=True)
    employer_tax_id = fields.Char(string="Employer's tax number")
    place_of_business = fields.Char(string='Place of business number')
    note = fields.Text()

    _company_form_uniq = models.Constraint(
        'unique(company_id, form_id)', 'One setting per company and form.')

    @api.model
    def _pb_for(self, form, company):
        """The row, made on first use (sudo after the caller's own door)."""
        row = self.sudo().search([('company_id', '=', company.id),
                                  ('form_id', '=', form.id)], limit=1)
        if not row:
            row = self.sudo().create({'company_id': company.id, 'form_id': form.id})
        return row

    @api.model
    def _pb_is_accepted(self, form, company):
        row = self.sudo().search([('company_id', '=', company.id),
                                  ('form_id', '=', form.id)], limit=1)
        return bool(row.accepted)

    def _pb_set_accepted(self, value):
        """Manager only. Who and when are kept; unticking is allowed and
        written down too."""
        self.ensure_one()
        if not has_any(self.env.user, MANAGER_GROUPS):
            raise AccessError(_("Only a payroll manager can say a form was accepted by the authority."))
        value = bool(value)
        if value == bool(self.accepted):
            return True
        now = fields.Datetime.now()
        if value:
            self.sudo().write({'accepted': True, 'accepted_by': self.env.uid,
                               'accepted_on': now})
            body = _("%(who)s marked “%(form)s” as accepted by the authority.",
                     who=self.env.user.name, form=self.form_id.name)
        else:
            self.sudo().write({'accepted': False, 'accepted_by': False,
                               'accepted_on': False})
            body = _("%(who)s took back “accepted by the authority” for “%(form)s”. Files will say “Check with your adviser before first filing” again.",
                     who=self.env.user.name, form=self.form_id.name)
        self.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')
        return True


class PbGovFormRights(models.AbstractModel):
    """The one door every screen of this module asks."""
    _name = 'pb.gov.form.rights'
    _description = 'Government forms: who may do what'

    @api.model
    def _pb_is_officer(self, user=None):
        return has_any(user or self.env.user, OFFICER_GROUPS)

    @api.model
    def _pb_is_manager(self, user=None):
        return has_any(user or self.env.user, MANAGER_GROUPS)

    @api.model
    def _pb_require_officer(self):
        if self._pb_is_officer():
            return True
        raise AccessError(_(
            "Government forms are prepared by payroll. Ask somebody who looks "
            "after payroll to do this, or to give you the payroll officer "
            "permission."))

    @api.model
    def _pb_company(self, company_id=None):
        """A company the user may act for (the switcher's companies)."""
        if not company_id:
            return self.env.company
        try:
            company = self.env['res.company'].browse(int(company_id))
        except (TypeError, ValueError):
            raise UserError(_("That company no longer exists."))
        if company not in self.env.companies:
            raise AccessError(_("Switch to that company first."))
        return company
