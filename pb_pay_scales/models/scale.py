# -*- coding: utf-8 -*-
"""WDGAP S8-A — pay scales: grades × steps, effective-dated (blueprint stage 1).

A scale is a POINT table ("grade 3, step 2 = this exact amount"), where a band
(`pb.pay.band`) is a RANGE. Five records carry it:

* `pb.pay.scale`          — the ladder: country, money, companies, how it is
                            written (amounts, or a coefficient × a base rate),
                            how many steps, the rounding;
* `pb.pay.scale.grade`    — a rung (Store associate, Senior associate…). A job
                            points at a grade through the EXISTING job-to-band
                            link (`pb.pay.band.job.pb_scale_grade_id`, see
                            `band_job.py`) — never a second job map;
* `pb.pay.scale.version`  — the table in force from a date. Dated rows never
                            overlap (the `pb.pay.band` no-overlap rule, cloned).
                            A version that has ended is kept exactly as it was;
* `pb.pay.scale.cell`     — one amount (or coefficient) per grade and step in a
                            version;
* `pb.pay.scale.package`  — grade-linked allowances in a version, each naming
                            the contract pay line it fills.

SAFETY RAIL (binding, tested): nothing in this file writes `hr.contract` or a
pay line. Editing a cell changes what the scale SAYS; a contract on the scale
whose wage now differs reads "Drifted" until a person decides. Moving people
with the scale (revisions, arrears, step-ups) is a later stage.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.pb_hr_payroll_formula.formula_engine import excel_semantics
from odoo.addons.pb_pay.models.pb_pay_band import COUNTRIES, COUNTRY_CURRENCY

_logger = logging.getLogger(__name__)

MAX_STEPS = 12
MAX_GRADES = 40


def round_to(value, rounding, decimals):
    """Excel rounding to the scale's unit (``rounding`` 0 = the currency's
    own smallest unit). Never Python's ``round()`` on money (ledger C12)."""
    value = float(value or 0.0)
    if rounding and rounding > 0:
        return excel_semantics.excel_round(value / rounding, 0) * rounding
    return excel_semantics.excel_round(value, decimals)


class PbPayScale(models.Model):
    _name = 'pb.pay.scale'
    _description = 'Pay scale'
    _inherit = ['mail.thread']
    _order = 'sequence, name, id'

    name = fields.Char(string='Pay scale', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    country_code = fields.Selection(
        COUNTRIES, string='Country', required=True, index=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    company_ids = fields.Many2many(
        'res.company', 'pb_pay_scale_company_rel', 'scale_id', 'company_id',
        string='Only these companies',
        help='Leave empty and every company in this country uses the scale.')
    family_id = fields.Many2one(
        'pb.pay.family', string='Job family', ondelete='set null')
    mode = fields.Selection(
        [('amount', 'Amounts'), ('coefficient', 'Coefficient × base rate')],
        string='Written as', required=True, default='amount', tracking=True)
    step_count = fields.Integer(
        string='Steps', required=True, default=4, tracking=True,
        help='How many steps each grade has. One step is a plain grade table.')
    rounding = fields.Float(
        string='Round to', default=0.0,
        help='Amounts round to this unit (for example 10,000). Empty rounds '
             'to the currency.')
    active = fields.Boolean(default=True)
    note = fields.Text(string='Notes')

    grade_ids = fields.One2many('pb.pay.scale.grade', 'scale_id', string='Grades')
    version_ids = fields.One2many('pb.pay.scale.version', 'scale_id',
                                  string='Versions')

    @api.constrains('step_count')
    def _check_steps(self):
        for scale in self:
            if not 1 <= scale.step_count <= MAX_STEPS:
                raise ValidationError(_(
                    "A scale has from 1 to %(top)s steps.", top=MAX_STEPS))

    @api.constrains('rounding')
    def _check_rounding(self):
        for scale in self:
            if scale.rounding < 0:
                raise ValidationError(_("Round to a unit above zero, or leave it empty."))

    @api.onchange('country_code')
    def _onchange_country_code(self):
        for scale in self:
            code = COUNTRY_CURRENCY.get(scale.country_code)
            currency = self.env['res.currency'].with_context(
                active_test=False).search([('name', '=', code)], limit=1) if code else False
            if currency:
                scale.currency_id = currency

    # ---------------------------------------------------------------- reads
    def decimals(self):
        self.ensure_one()
        currency = self.currency_id
        return currency.decimal_places if currency and currency.decimal_places is not None else 2

    def round_amount(self, value):
        self.ensure_one()
        return round_to(value, self.rounding, self.decimals())

    def version_on(self, day=None):
        """The version in force on ``day`` (today when empty), or nothing."""
        self.ensure_one()
        day = fields.Date.to_date(day) if day else fields.Date.context_today(self)
        for version in self.version_ids.sorted('date_from', reverse=True):
            if version.date_from <= day and (not version.date_to or version.date_to >= day):
                return version
        return self.env['pb.pay.scale.version']

    def serves_company(self, company):
        """May contracts of ``company`` use this scale?"""
        self.ensure_one()
        if not company:
            return False
        if self.company_ids:
            return company.id in self.company_ids.ids
        country = (company.country_id.code or '').upper()
        return not country or country == self.country_code


class PbPayScaleGrade(models.Model):
    _name = 'pb.pay.scale.grade'
    _description = 'Grade on a pay scale'
    _order = 'scale_id, sequence, id'

    scale_id = fields.Many2one('pb.pay.scale', string='Pay scale', required=True,
                               ondelete='cascade', index=True)
    name = fields.Char(string='Grade', required=True)
    sequence = fields.Integer(default=10)
    band_id = fields.Many2one(
        'pb.pay.band', string='Pay band', ondelete='set null',
        help='The band whose range this grade sits in, when there is one.')
    job_link_ids = fields.One2many('pb.pay.band.job', 'pb_scale_grade_id',
                                   string='Jobs')

    @api.constrains('name')
    def _check_name(self):
        for grade in self:
            if not (grade.name or '').strip():
                raise ValidationError(_("A grade needs a name."))

    @api.constrains('scale_id')
    def _check_count(self):
        for grade in self:
            if len(grade.scale_id.grade_ids) > MAX_GRADES:
                raise ValidationError(_(
                    "A scale holds up to %(top)s grades.", top=MAX_GRADES))

    def unlink(self):
        placed = self.env['pb.pay.scale.placement'].sudo().search_count(
            [('grade_id', 'in', self.ids)])
        if placed:
            raise UserError(_(
                "People are placed on this grade. Move them to another grade "
                "first, then remove it."))
        return super().unlink()


class PbPayScaleVersion(models.Model):
    _name = 'pb.pay.scale.version'
    _description = 'Pay scale version'
    _order = 'scale_id, date_from desc'
    _rec_name = 'date_from'

    scale_id = fields.Many2one('pb.pay.scale', string='Pay scale', required=True,
                               ondelete='cascade', index=True)
    date_from = fields.Date(string='In force from', required=True, index=True)
    date_to = fields.Date(string='In force until', index=True)
    base_rate = fields.Float(
        string='Base rate', digits=(16, 2),
        help='For a scale written as coefficients: each cell is its '
             'coefficient times this rate.')
    note = fields.Text(string='Notes')
    cell_ids = fields.One2many('pb.pay.scale.cell', 'version_id', string='Amounts')
    package_ids = fields.One2many('pb.pay.scale.package', 'version_id',
                                  string='Allowances')

    @api.constrains('date_from', 'date_to', 'scale_id')
    def _check_no_overlap(self):
        """Two versions of one scale may never cover the same day (the band
        rule, `pb_pay_band._check_no_overlap`, cloned)."""
        for version in self:
            if version.date_to and version.date_to < version.date_from:
                raise ValidationError(_(
                    "A version cannot end before it starts."))
            clash = self.search([
                ('id', '!=', version.id),
                ('scale_id', '=', version.scale_id.id),
                ('date_from', '<=', version.date_to or '9999-12-31'),
                '|', ('date_to', '=', False),
                ('date_to', '>=', version.date_from),
            ], limit=1)
            if clash:
                raise ValidationError(_(
                    "%(scale)s already has a version in force from %(since)s. "
                    "Two versions cannot cover the same days.",
                    scale=version.scale_id.name or _('This scale'),
                    since=fields.Date.to_string(clash.date_from)))

    def has_ended(self):
        self.ensure_one()
        return bool(self.date_to and self.date_to < fields.Date.context_today(self))

    def cell_for(self, grade, step_no):
        self.ensure_one()
        for cell in self.cell_ids:
            if cell.grade_id.id == grade.id and cell.step_no == int(step_no or 0):
                return cell
        return self.env['pb.pay.scale.cell']

    def value_of(self, grade, step_no):
        """The amount of (grade, step) in this version, or None."""
        self.ensure_one()
        cell = self.cell_for(grade, step_no)
        if not cell:
            return None
        value = cell.value
        return value if value else None


class PbPayScaleCell(models.Model):
    _name = 'pb.pay.scale.cell'
    _description = 'Pay scale amount'
    _order = 'version_id, grade_id, step_no'

    version_id = fields.Many2one('pb.pay.scale.version', required=True,
                                 ondelete='cascade', index=True)
    scale_id = fields.Many2one(related='version_id.scale_id', store=True, index=True)
    grade_id = fields.Many2one('pb.pay.scale.grade', string='Grade', required=True,
                               ondelete='cascade', index=True)
    step_no = fields.Integer(string='Step', required=True, default=1)
    amount = fields.Float(string='Amount', digits=(16, 2))
    coefficient = fields.Float(string='Coefficient', digits=(16, 4))
    value = fields.Float(string='Monthly amount', compute='_compute_value',
                         digits=(16, 2))

    _cell_uniq = models.Constraint(
        'unique(version_id, grade_id, step_no)',
        'A grade has one amount per step in a version.')

    @api.depends('amount', 'coefficient', 'version_id.base_rate',
                 'version_id.scale_id.mode', 'version_id.scale_id.rounding')
    def _compute_value(self):
        for cell in self:
            scale = cell.version_id.scale_id
            if scale.mode == 'coefficient':
                raw = (cell.coefficient or 0.0) * (cell.version_id.base_rate or 0.0)
                cell.value = scale.round_amount(raw) if scale else raw
            else:
                cell.value = cell.amount or 0.0

    @api.constrains('amount', 'coefficient', 'step_no')
    def _check_cell(self):
        for cell in self:
            if cell.amount < 0 or cell.coefficient < 0:
                raise ValidationError(_("An amount on a scale cannot be below zero."))
            top = cell.version_id.scale_id.step_count or 1
            if not 1 <= cell.step_no <= top:
                raise ValidationError(_(
                    "This scale has steps 1 to %(top)s.", top=top))


class PbPayScalePackage(models.Model):
    _name = 'pb.pay.scale.package'
    _description = 'Grade allowance on a pay scale'
    _order = 'version_id, grade_id, id'

    version_id = fields.Many2one('pb.pay.scale.version', required=True,
                                 ondelete='cascade', index=True)
    grade_id = fields.Many2one('pb.pay.scale.grade', string='Grade', required=True,
                               ondelete='cascade', index=True)
    template_id = fields.Many2one(
        'hr.contract.advantage.template', string='Pay line', required=True,
        ondelete='restrict')
    code = fields.Char(related='template_id.code', string='Code')
    amount = fields.Float(string='Amount', digits=(16, 2))

    _package_uniq = models.Constraint(
        'unique(version_id, grade_id, template_id)',
        'A grade fills each pay line once.')

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(_("An allowance cannot be below zero."))
