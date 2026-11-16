# -*- coding: utf-8 -*-
"""WDGAP S8-D (owner rulings SC1 + SC2) — "Raise the scale" in ONE request.

WHAT WAS TRUE BEFORE (S8-A). A new version of a scale changed what the scale
SAID and nothing else: everybody on it read "Drifted" from the new date and
each person was brought to their step from their own contract, one approval
each.

WHAT IS TRUE NOW. HR prepares ONE request: a new dated version of the scale
(every amount raised by a percentage, by a flat amount, or typed as a table)
and sees, before anything is sent, who moves and from/to, who is Pinned and
left alone, who is already paid ABOVE their new step (ruling SC2: they keep
their pay, nothing changes for them), who cannot be moved and why, and what
it really costs a month and a year in each currency (never two currencies
added). ONE approval for the whole request (process key ``scaleraise``,
manager-free: HR lead, then the Finance approver — the pay-change precedent).

NOTHING CHANGES ON ANY CONTRACT OR PAYSLIP UNTIL THE REQUEST IS APPROVED. On
approval the new version is written (so joiners from that date start on the
new amounts) and, on the effective date, every moving contract's wage is
written through the SAME dated contract amount-change record Change job uses
(`hr.contract.advantage.change`, dated the effective date, source "From the
pay scale") — which is what the Past-month re-work reads, so a rise dated in a
month already paid is found there. This module writes NO back-pay input (C-6).
A future date waits as "Approved, starts later" and a quiet hourly job writes
it on the day; applying twice writes nothing twice. Before the day it can be
taken back (the version goes, nothing else had moved); after it only a new
request changes pay again.

Each moved person gets one letter (a letter type of this module, added to the
letter engine's list by `selection_add`; `pb_lifecycle` is not edited), filed
in their documents the way every other letter is.
"""
import json
import logging
from datetime import timedelta

from psycopg2 import errors as pg_errors

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.modules import module as odoo_module
from odoo.tools.misc import format_date

from odoo.addons.biz_approval_workflow.models.chain_shim import role_step, route

from .resolver import WAGE_CODES

_logger = logging.getLogger(__name__)

RAISE_PROCESS_KEY = 'scaleraise'

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('scheduled', 'Approved, starts later'),
    ('applied', 'Done'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('cancelled', 'Cancelled'),
    ('taken_back', 'Taken back'),
]
OPEN_STATES = ('draft', 'returned')
LIVE_STATES = ('pending', 'scheduled')

METHODS = [
    ('percent', 'By a percentage'),
    ('flat', 'By a flat amount'),
    ('table', 'Type the new table'),
]

OUTCOMES = [
    ('move', 'Moves'),
    ('above', 'Above step'),
    ('pinned', 'Pinned'),
    ('cannot', 'Cannot move'),
    ('left_out', 'Left out'),
]

LINE_STATES = [('waiting', 'Waiting'), ('done', 'Written'),
               ('skipped', 'Not written')]

#: A rise reaches this many people through the pay rules for its cost; the
#: rest (rare) are costed by the wage difference alone and the screen says so.
ENGINE_COST_CAP = 400
#: Letters printed inside the click; the pay letters job prints the rest.
LETTERS_INLINE = 25
MAX_AHEAD_DAYS = 366
MAX_BACK_DAYS = 366
LETTER_SCALE_RAISE = 'pay_scale_raise'

LOCK_ERRORS = (pg_errors.LockNotAvailable,)

#: The pay-change states that mean "a raise for this person is on its way".
PAYCHANGE_WAITING = ('proposed', 'hr_review', 'finance', 'approved')


class PbPayScaleRaise(models.Model):
    _name = 'pb.pay.scale.raise'
    _description = 'Pay scale rise'
    _inherit = ['mail.thread', 'biz.approval.adapter.mixin']
    _order = 'id desc'

    _approval_process_key = RAISE_PROCESS_KEY

    name = fields.Char(string='Reference', readonly=True, copy=False,
                       default='/', index=True)
    scale_id = fields.Many2one('pb.pay.scale', string='Pay scale', required=True,
                               ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, default=lambda s: s.env.company)
    currency_id = fields.Many2one(related='scale_id.currency_id', string='Currency')
    user_id = fields.Many2one('res.users', string='Prepared by', readonly=True,
                              index=True, default=lambda s: s.env.user)
    effective_date = fields.Date(string='Starts on', index=True)
    method = fields.Selection(METHODS, string='How', default='percent',
                              required=True)
    pct = fields.Float(string='Percentage', digits=(16, 4))
    flat = fields.Float(string='Flat amount', digits=(16, 2))
    new_base_rate = fields.Float(string='New base rate', digits=(16, 2))
    #: Typed table: ``[{grade_id, step, amount|coefficient}]``.
    typed_json = fields.Text(string='Typed table (JSON)')
    #: Contracts HR un-ticked in the preview.
    excluded_json = fields.Text(string='Left out (JSON)')
    reason = fields.Text(string='Why')
    state = fields.Selection(STATES, default='draft', required=True, index=True,
                             readonly=True, copy=False, tracking=True)

    # ------------------------------------------------------- frozen at send
    base_version_id = fields.Many2one('pb.pay.scale.version',
                                      string='Starts from version',
                                      ondelete='set null', readonly=True)
    #: The new table, ``[{grade_id, step, amount, coefficient, value}]``, and
    #: the new base rate for a coefficient scale.
    cells_json = fields.Text(string='New table (JSON)', readonly=True, copy=False)
    cells_base_rate = fields.Float(readonly=True, copy=False, digits=(16, 2))
    cost_json = fields.Text(string='Cost (JSON)', readonly=True, copy=False)
    facts_json = fields.Text(string='Facts (JSON)', readonly=True, copy=False)
    line_ids = fields.One2many('pb.pay.scale.raise.line', 'raise_id',
                               string='People')

    # -------------------------------------------------------------- outcome
    version_id = fields.Many2one('pb.pay.scale.version', string='New version',
                                 ondelete='set null', readonly=True, copy=False)
    applied_at = fields.Datetime(string='Written on', readonly=True, copy=False)
    applied_by = fields.Many2one('res.users', string='Written by',
                                 readonly=True, copy=False)
    started_by_job = fields.Boolean(readonly=True, copy=False)
    block_note = fields.Text(string='Why it could not be done', readonly=True,
                             copy=False)
    start_fail_days = fields.Integer(readonly=True, copy=False)
    start_last_fail = fields.Date(readonly=True, copy=False)
    taken_back_at = fields.Datetime(readonly=True, copy=False)
    taken_back_by = fields.Many2one('res.users', readonly=True, copy=False)
    #: ``[{month, month_label, config_id, config, people}]`` — finished
    #: payslips of moved people ending on or after the start date. A count
    #: only (C-6): nothing is recalculated here.
    paid_months_json = fields.Text(readonly=True, copy=False)
    rework_ids_json = fields.Text(readonly=True, copy=False)
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_pay_scale_raise_seat_rel', 'raise_id', 'user_id',
        string='Asked to decide', copy=False)

    # ==================================================================
    # Small readers
    # ==================================================================
    def _json(self, name, default):
        self.ensure_one()
        try:
            value = json.loads(self[name] or 'null')
        except (TypeError, ValueError):
            return default
        return value if isinstance(value, type(default)) else default

    def facts(self):
        return self._json('facts_json', {})

    def cells(self):
        return self._json('cells_json', [])

    def costs(self):
        return self._json('cost_json', [])

    def excluded(self):
        return {int(x) for x in self._json('excluded_json', []) if str(x).isdigit()}

    def paid_months(self):
        return self._json('paid_months_json', [])

    @api.model
    def _sel_label(self, field, key, model=None):
        if not key:
            return ''
        Model = self.env[model] if model else self
        return dict(Model._fields[field]._description_selection(self.env)).get(key, '')

    def _day(self, value):
        return format_date(self.env, value, date_format='d MMM y') if value else ''

    def _month(self, value):
        return format_date(self.env, value, date_format='MMMM y') if value else ''

    @api.model
    def _money(self, amount, currency):
        return self.env['pb.pay.bands']._money(float(amount or 0.0), currency)

    @api.model
    def _today_for(self, company=None):
        """The date it is for a company (its time zone) — the one reading every
        dated change in this product uses (`pb.records.apply._today_for`)."""
        Apply = self.env.get('pb.records.apply')
        if Apply is not None and hasattr(Apply, '_today_for'):
            try:
                return Apply._today_for(company or self.env.company)
            except Exception:       # noqa: BLE001 — the plain date is fine
                _logger.debug('scale rise: company date unreadable', exc_info=True)
        return fields.Date.context_today(self)

    def _company_today(self):
        self.ensure_one()
        return self._today_for(self.company_id)

    # ==================================================================
    # Gates
    # ==================================================================
    @api.model
    def _may_prepare(self):
        return bool(self.env.su or self.env['pb.pay.scales']._can_write())

    @api.model
    def _require_prepare(self):
        if not self._may_prepare():
            raise AccessError(_("Only the people who set pay bands can raise a "
                                "pay scale."))

    def _check_companies(self):
        """The reader may only act on a request of a company they work in."""
        self.ensure_one()
        if self.env.su:
            return True
        if self.company_id not in self.env['pb.pay.scales']._companies():
            raise AccessError(_("This scale rise belongs to a company you do "
                                "not work in."))
        return True

    # ==================================================================
    # The new table
    # ==================================================================
    def _base_version(self, effective=None):
        """The version the rise starts from: the latest one that starts before
        the effective date (the table people are paid on the day before)."""
        self.ensure_one()
        scale = self.scale_id.sudo()
        day = fields.Date.to_date(effective or self.effective_date) \
            if (effective or self.effective_date) else self._company_today()
        older = scale.version_ids.filtered(lambda v: v.date_from < day) \
            .sorted('date_from')
        return older[-1:] if older else scale.version_ids.browse()

    def _typed(self):
        rows = self._json('typed_json', [])
        out = {}
        for row in rows:
            try:
                key = (int(row.get('grade_id') or 0), int(row.get('step') or 0))
                if self.scale_id.mode == 'coefficient':
                    out[key] = float(row.get('coefficient') or 0.0)
                else:
                    out[key] = float(row.get('amount') or 0.0)
            except (TypeError, ValueError, AttributeError):
                continue
        return out

    def _new_table(self, base):
        """``(cells, base_rate, problems)``. ``cells`` is one dict per grade and
        step: ``{grade_id, step, old, new, amount, coefficient}`` where ``old``
        and ``new`` are the monthly amounts the person reads."""
        self.ensure_one()
        scale = self.scale_id.sudo()
        problems = []
        if not base:
            return [], 0.0, [_("%s has no table before that date to raise.",
                               scale.name)]
        coef = scale.mode == 'coefficient'
        old_rate = float(base.base_rate or 0.0)
        new_rate = old_rate
        if coef:
            if self.method == 'percent':
                new_rate = old_rate * (1.0 + float(self.pct or 0.0) / 100.0)
            elif self.method == 'flat':
                new_rate = old_rate + float(self.flat or 0.0)
            else:
                new_rate = float(self.new_base_rate or 0.0)
            new_rate = round(new_rate, 2)
        typed = self._typed() if self.method == 'table' else {}
        cells = []
        for grade in scale.grade_ids.sorted(lambda g: (g.sequence, g.id)):
            for step in range(1, (scale.step_count or 1) + 1):
                cell = base.cell_for(grade, step)
                if not cell:
                    continue
                old = cell.value or 0.0
                if not old:
                    continue
                coefficient = cell.coefficient or 0.0
                amount = cell.amount or 0.0
                if coef:
                    if self.method == 'table' and (grade.id, step) in typed \
                            and typed[(grade.id, step)] > 0:
                        coefficient = typed[(grade.id, step)]
                    new = scale.round_amount(coefficient * new_rate)
                else:
                    if self.method == 'percent':
                        amount = scale.round_amount(
                            old * (1.0 + float(self.pct or 0.0) / 100.0))
                    elif self.method == 'flat':
                        amount = scale.round_amount(old + float(self.flat or 0.0))
                    else:
                        amount = scale.round_amount(typed.get((grade.id, step), old))
                    new = amount
                if new + 1e-9 < old:
                    problems.append(_(
                        "%(grade)s, step %(step)s would go down, from %(old)s to "
                        "%(new)s. A rise never lowers a step; make a new version "
                        "of the scale for that.", grade=grade.name, step=step,
                        old=self._money(old, scale.currency_id),
                        new=self._money(new, scale.currency_id)))
                cells.append({'grade_id': grade.id, 'grade': grade.name,
                              'step': step, 'old': old, 'new': new,
                              'amount': amount if not coef else 0.0,
                              'coefficient': coefficient if coef else 0.0})
        if not cells:
            problems.append(_("%s has no amounts to raise yet.", scale.name))
        elif all(abs(c['new'] - c['old']) < 1e-9 for c in cells):
            problems.append(_("Nothing on the table goes up. Type a percentage, "
                              "an amount or new figures."))
        return cells, new_rate, problems

    # ==================================================================
    # Who moves
    # ==================================================================
    def _reach(self):
        """The companies a rise reaches: the ones whoever prepared it works in
        (the Scales tab's own reading, `pb.pay.bands._companies`). Never the
        whole database, even when the request is read under sudo."""
        self.ensure_one()
        user = self.user_id if self.user_id and self.user_id.active else self.env.user
        companies = self.env['pb.pay.scales'].with_user(user)._companies()
        return companies.filtered(lambda c: self.scale_id.sudo().serves_company(c))

    def _placements(self):
        """Everybody placed on this scale, in the companies the request can
        reach."""
        self.ensure_one()
        companies = self._reach()
        return self.env['pb.pay.scale.placement'].sudo().search([
            ('scale_id', '=', self.scale_id.id),
            ('contract_id.state', 'in', ('draft', 'open')),
            ('company_id', 'in', companies.ids or [0]),
        ])

    @api.model
    def _busy_reason(self, contract, raise_id=0):
        """Why another request already holds this person's pay, or ''."""
        employee = contract.employee_id
        if 'pb.job.change' in self.env:
            other = self.env['pb.job.change'].sudo().search([
                ('employee_id', '=', employee.id), ('state', 'in', ('pending', 'scheduled')),
                ('change_pay', '=', True)], limit=1)
            if other:
                return _("A job change with new pay is waiting for them (%s).",
                         other.name)
        if 'pb.pay.change' in self.env:
            other = self.env['pb.pay.change'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', 'in', PAYCHANGE_WAITING)], limit=1)
            if other:
                return _("A pay change for them is waiting (%s).",
                         other.display_name or '')
        line = self.env['pb.pay.scale.raise.line'].sudo().search([
            ('contract_id', '=', contract.id), ('outcome', '=', 'move'),
            ('raise_id.state', 'in', LIVE_STATES), ('raise_id', '!=', raise_id or 0),
            ('state', '=', 'waiting')], limit=1)
        if line:
            return _("Another scale rise for them is waiting (%s).",
                     line.raise_id.name)
        return ''

    def _plan(self, cells):
        """One row per placed person: ``{placement, contract, outcome, why,
        old, new, step_old, drifted}``."""
        self.ensure_one()
        scale = self.scale_id.sudo()
        Scales = self.env['pb.pay.scales']
        decimals = scale.decimals()
        half = 0.5 * 10.0 ** (-decimals)
        table = {(c['grade_id'], c['step']): c for c in cells}
        effective = self.effective_date
        left_out = self.excluded()
        rows = []
        for placement in self._placements():
            contract = placement.contract_id.sudo()
            wage = float(contract.wage or 0.0)
            cell = table.get((placement.grade_id.id, placement.step_no))
            row = {'placement': placement, 'contract': contract, 'outcome': '',
                   'why': '', 'old': wage, 'new': wage,
                   'step_old': cell['old'] if cell else 0.0, 'drifted': False}
            if placement.pinned:
                row.update(outcome='pinned', why=placement.label())
            elif contract.state != 'open':
                row.update(outcome='cannot', why=_(
                    "Their contract is not running yet."))
            elif effective and contract.date_end and contract.date_end < effective:
                row.update(outcome='cannot', why=_(
                    "Their contract ends before the rise starts."))
            elif not cell:
                row.update(outcome='cannot', why=_(
                    "Their step has no amount in the new table."))
            else:
                currency = Scales._pay_currency(contract.employee_id, contract.company_id)
                busy = self._busy_reason(contract, self.id)
                if currency and scale.currency_id and currency != scale.currency_id:
                    row.update(outcome='cannot', why=_(
                        "They are paid in %(pay)s and the scale is in %(scale)s.",
                        pay=currency.name, scale=scale.currency_id.name))
                elif busy:
                    row.update(outcome='cannot', why=busy)
                elif wage + half >= cell['new']:
                    row.update(outcome='above', why=_(
                        "Already paid the new step or more, so their pay stays "
                        "as it is.") if wage - half <= cell['new'] else _(
                        "Paid above their new step, so their pay stays as it is."))
                else:
                    drifted = abs(wage - cell['old']) >= half
                    row.update(outcome='left_out' if contract.id in left_out else 'move',
                               new=cell['new'], drifted=drifted,
                               why=_("Was paid differently from their step.")
                               if drifted else '')
            rows.append(row)
        return rows

    # ==================================================================
    # What it costs, through the pay rules
    # ==================================================================
    def _cost_engine(self):
        """``(Engine, totals)`` from Formula Studio and Build-from-a-total when
        both are installed, else ``(None, None)`` — then the cost is the wage
        difference alone, and the screen says so."""
        if 'pb.formula.studio' not in self.env or 'pb.pay.package' not in self.env:
            return None, None
        try:
            from odoo.addons.pb_formula_studio.models.take_home import _Engine
        except Exception:       # noqa: BLE001 — an optional calculator
            return None, None
        return _Engine, self.env['pb.pay.package']._totals

    def _person_inputs(self, contract, config):
        """Every other figure of the person as the pay run would read it: the
        latest payslip of that scheme, or the contract's own amounts (the
        take-home calculator's rule, W2-C)."""
        slip = self.env['hr.payslip'].sudo().search([
            ('employee_id', '=', contract.employee_id.id),
            ('formula_config_id', '=', config.id), ('state', '!=', 'cancel'),
            ('formula_input_values', '!=', False)], order='date_to desc, id desc', limit=1)
        inputs = {}
        if slip:
            try:
                inputs = json.loads(slip.formula_input_values or '{}')
            except (TypeError, ValueError):
                inputs = {}
        else:
            try:
                Batch = self.env['hr.payroll.import.batch'].sudo()
                inputs = dict(Batch._contract_component_values(contract, config=config) or {})
            except Exception:   # noqa: BLE001
                inputs = {}
        return inputs if isinstance(inputs, dict) else {}

    def _costs_for(self, rows):
        """Fill ``row['cost']`` (a month, in the person's money) and
        ``row['how']`` ('engine' / 'wage'); return the totals per currency."""
        self.ensure_one()
        Engine, totals = self._cost_engine()
        Scales = self.env['pb.pay.scales']
        Studio = self.env['pb.formula.studio'].sudo() if Engine else None
        engines = {}
        budget = ENGINE_COST_CAP
        sums = {}
        for row in rows:
            if row['outcome'] != 'move':
                continue
            contract = row['contract']
            diff = float(row['new']) - float(row['old'])
            row['cost'], row['how'] = diff, 'wage'
            currency = self.scale_id.currency_id
            schemes = Scales._schemes_for(contract.employee_id)
            config = schemes[:1] if schemes else None
            if config and config.currency_id:
                currency = config.currency_id
            if Engine and config and budget > 0:
                budget -= 1
                try:
                    engine = engines.get(config.id)
                    if engine is None:
                        engine = engines[config.id] = Engine(self.env, config.sudo())
                    codes = Studio._th_wage_codes(config.sudo())
                    if codes:
                        inputs = self._person_inputs(contract, config.sudo())
                        decimals = currency.decimal_places or 0
                        before = dict(inputs, **{c: row['old'] for c in codes})
                        after = dict(inputs, **{c: row['new'] for c in codes})
                        t0 = totals(engine, engine.evaluate(before), decimals)['total']
                        t1 = totals(engine, engine.evaluate(after), decimals)['total']
                        row['cost'], row['how'] = t1 - t0, 'engine'
                except Exception:   # noqa: BLE001 — the wage difference stands
                    _logger.debug('scale rise: cost through the pay rules failed '
                                  'for contract %s', contract.id, exc_info=True)
            row['currency'] = currency
            bucket = sums.setdefault(currency.id, {
                'currency_id': currency.id, 'currency': currency.name or '',
                'month': 0.0, 'people': 0, 'engine': 0, 'wage': 0})
            bucket['month'] += row['cost']
            bucket['people'] += 1
            bucket[row['how']] += 1
        out = []
        for bucket in sums.values():
            currency = self.env['res.currency'].browse(bucket['currency_id'])
            bucket['year'] = bucket['month'] * 12.0
            bucket['month_label'] = self._money(bucket['month'], currency)
            bucket['year_label'] = self._money(bucket['year'], currency)
            out.append(bucket)
        return sorted(out, key=lambda b: b['currency'])

    # ==================================================================
    # Months already paid (a count; C-6)
    # ==================================================================
    def _paid_months_for(self, employees):
        self.ensure_one()
        if not self.effective_date or not employees or 'hr.payslip' not in self.env:
            return []
        Payslip = self.env['hr.payslip'].sudo()
        known = dict(Payslip._fields['state']._description_selection(self.env))
        finished = [s for s in ('done', 'paid') if s in known] or ['done']
        slips = Payslip.search([
            ('employee_id', 'in', employees.ids), ('state', 'in', finished),
            ('date_to', '>=', self.effective_date)], order='date_to')
        out = {}
        for slip in slips:
            run = slip.payslip_run_id
            kind = getattr(run, 'pb_run_kind', False) if run else False
            if kind and kind != 'regular':
                continue
            month = slip.date_to.replace(day=1)
            config = getattr(slip, 'formula_config_id', False)
            key = (fields.Date.to_string(month), config.id if config else 0)
            row = out.setdefault(key, {
                'month': key[0], 'month_label': self._month(month),
                'config_id': key[1], 'config': config.name if config else '',
                'people': [], 'count': 0})
            if slip.employee_id.id not in row['people']:
                row['people'].append(slip.employee_id.id)
                row['count'] += 1
        return [out[k] for k in sorted(out)]

    # ==================================================================
    # Checks before sending
    # ==================================================================
    def _problems(self, cells=None):
        self.ensure_one()
        out = []
        scale = self.scale_id.sudo()
        if not scale or not scale.active:
            return [_("That pay scale is no longer in use.")]
        if not self.effective_date:
            out.append(_("Choose the day the rise starts."))
        else:
            today = self._company_today()
            if self.effective_date > today + timedelta(days=MAX_AHEAD_DAYS):
                out.append(_("A rise can start at most a year ahead."))
            if self.effective_date < today - timedelta(days=MAX_BACK_DAYS):
                out.append(_("A rise can start at most a year back."))
            latest = scale.version_ids.sorted('date_from')[-1:]
            if latest and self.effective_date <= latest.date_from:
                out.append(_(
                    "The scale already has a version from %(day)s. A rise must "
                    "start after it.", day=self._day(latest.date_from)))
        if self.method == 'percent' and float(self.pct or 0.0) <= 0:
            out.append(_("Type a percentage above zero."))
        if self.method == 'flat' and float(self.flat or 0.0) <= 0:
            out.append(_("Type an amount above zero."))
        if not (self.reason or '').strip():
            out.append(_("Say why, in a few words. The people who sign it off "
                         "read this first."))
        if cells is None and self.effective_date:
            cells, _rate, more = self._new_table(self._base_version())
            out.extend(more)
        other = self.sudo().search([('scale_id', '=', scale.id),
                                    ('state', 'in', LIVE_STATES),
                                    ('id', '!=', self.id or 0)], limit=1)
        if other:
            out.append(_("This scale already has a rise waiting (%s). Finish or "
                         "take back that one first.", other.name))
        return out

    # ==================================================================
    # Sending it in
    # ==================================================================
    def _freeze(self):
        """Work everything out once more and keep it: the table, the people
        (one line each) and the cost. What the approver signs is this."""
        self.ensure_one()
        base = self._base_version()
        cells, rate, problems = self._new_table(base)
        problems = self._problems(cells) + problems
        if problems:
            raise UserError('\n'.join(dict.fromkeys(problems)))
        rows = self._plan(cells)
        costs = self._costs_for(rows)
        if not any(r['outcome'] == 'move' for r in rows):
            raise UserError(_("Nobody's pay would change with this rise, so there "
                              "is nothing to send."))
        Line = self.env['pb.pay.scale.raise.line'].sudo()
        self.sudo().line_ids.unlink()
        vals = []
        for row in rows:
            contract = row['contract']
            placement = row['placement']
            vals.append({
                'raise_id': self.id, 'contract_id': contract.id,
                'employee_id': contract.employee_id.id,
                'grade_id': placement.grade_id.id, 'step_no': placement.step_no,
                'outcome': row['outcome'], 'why': (row['why'] or '')[:500],
                'old_wage': row['old'], 'new_wage': row['new'],
                'step_old': row['step_old'], 'drifted': row['drifted'],
                'cost_month': row.get('cost', 0.0),
                'cost_how': row.get('how') or False,
                'cost_currency_id': row['currency'].id if row.get('currency') else False,
            })
        Line.create(vals)
        movers = self.env['hr.employee'].browse(
            [r['contract'].employee_id.id for r in rows if r['outcome'] == 'move'])
        moving = [r for r in rows if r['outcome'] == 'move']
        rise = [(r['new'] - r['old']) / r['old'] * 100.0 for r in moving if r['old']]
        scale_cost = sum(c['month'] for c in costs
                         if c['currency_id'] == self.scale_id.currency_id.id)
        facts = {
            'people': {'value': len(moving), 'unit': ''},
            'rise_pct': {'value': round(sum(rise) / len(rise), 2) if rise else 0.0,
                         'unit': '%'},
            'monthly_cost': {'value': round(scale_cost, 2),
                             'unit': self.scale_id.currency_id.name or ''},
            'starts_in_past': {'value': bool(self.effective_date
                                             < self._company_today()), 'unit': ''},
        }
        self.sudo().write({
            'base_version_id': base.id or False,
            'cells_json': json.dumps(cells, default=str),
            'cells_base_rate': rate,
            'cost_json': json.dumps(costs, default=str),
            'facts_json': json.dumps(facts, default=str),
            'paid_months_json': json.dumps(self._paid_months_for(movers), default=str),
            'block_note': False,
        })
        return True

    def action_send(self):
        self.ensure_one()
        self._require_prepare()
        self._check_companies()
        if self.state not in OPEN_STATES:
            raise UserError(_("This scale rise has already been sent in."))
        self._freeze()
        if self.name in (False, '/'):
            self.sudo().name = 'SR%05d' % self.id
        self.env['biz.approval.engine'].sudo().submit(self)
        self.invalidate_recordset()
        return self.answer()

    def answer(self):
        self.ensure_one()
        request = self.sudo().approval_request_id
        if self.state == 'applied':
            message = _("Done. The new pay is written for everybody who moves.")
        elif self.state == 'scheduled':
            message = _("Approved. It starts on %s and is written that morning.",
                        self._day(self.effective_date))
        elif self.state == 'pending':
            who = self._waiting_for()
            message = _("Sent for approval — %s", who) if who else _("Sent for approval.")
        elif request and request.state == 'blocked':
            message = _("It could not be sent: %s", request.block_reason or '')
        else:
            message = self.block_note or ''
        return {'ok': True, 'id': self.id, 'reference': self.name,
                'state': self.state, 'message': message}

    def _waiting_for(self):
        self.ensure_one()
        request = self.sudo().approval_request_id
        if not request:
            return ''
        step = request.step_ids.filtered(lambda s: s.key == request.current_step_key)[:1]
        names = sorted({seat.acting_user_id.name or '' for seat in step.seat_ids
                        if seat.status == 'open'})
        return ', '.join(n for n in names if n)

    # ==================================================================
    # The adapter contract
    # ==================================================================
    def _headline(self):
        self.ensure_one()
        return _("Pay scale rise · %s", self.scale_id.sudo().name or '')

    def _approval_validate(self):
        self.ensure_one()
        if self.state not in OPEN_STATES:
            raise UserError(_("This scale rise has already been sent in."))
        return True

    def _approval_payload(self):
        self.ensure_one()
        rec = self.sudo()
        return {
            'scale': rec.scale_id.id,
            'date': fields.Date.to_string(rec.effective_date),
            'cells': rec.cells(),
            'rate': rec.cells_base_rate,
            'lines': sorted((l.contract_id.id, l.outcome, round(l.old_wage, 4),
                             round(l.new_wage, 4)) for l in rec.line_ids),
        }

    def _approval_context(self):
        # Read under sudo: the engine calls this as whoever decided the last
        # step, and a Finance approver may hold no pay role (ledger W2B-2).
        self.ensure_one()
        rec = self.sudo()
        company = rec.company_id or self.env.company
        facts = rec.facts()
        return {
            'company_id': company.id,
            'title': rec._headline(),
            'scope_keys': [''],
            'scope_label': company.name,
            'scope_date': fields.Date.to_string(fields.Date.context_today(rec)),
            'kind_key': 'any',
            'facts': facts,
            'amount': float((facts.get('monthly_cost') or {}).get('value') or 0.0),
            'currency_id': (rec.scale_id.currency_id or company.currency_id).id,
            'maker_uids': [rec.user_id.id] if rec.user_id else [],
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._approval_revision_of(rec._approval_payload()),
            'evidence': [{
                'key': 'reason_given', 'name': _('A reason was written down'),
                'ok': bool((rec.reason or '').strip()),
                'note': (rec.reason or '')[:240]}],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': self._fact_specs(),
            'kinds': [],
            'evidence': [{'key': 'reason_given',
                          'label': _('A reason was written down')}],
            'scope_levels': [_('Whole company')],
            'manager_mode': False,
        }

    @api.model
    def _fact_specs(self):
        return {
            'people': {'type': 'decimal', 'label': _('How many people move')},
            'rise_pct': {'type': 'percent', 'label': _('Average rise')},
            'monthly_cost': {'type': 'decimal', 'label': _('Cost a month')},
            'starts_in_past': {'type': 'bool',
                               'label': _('Starts on a date already gone')},
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        people = int((self.sudo().facts().get('people') or {}).get('value') or 0)
        return self.env['pb.pay.bands']._people_phrase(people)

    def _approval_detail(self, request):
        self.ensure_one()
        rec = self.sudo()
        currency = rec.scale_id.currency_id
        rows = []
        for line in rec.line_ids.filtered(lambda l: l.outcome == 'move')[:40]:
            rows.append({
                'head': (line.employee_id.name or '')[:60],
                'sub': _("%(grade)s, step %(step)s", grade=line.grade_id.name or '',
                         step=line.step_no)[:60],
                'cells': [self._money(line.old_wage, currency),
                          self._money(line.new_wage, currency)],
                'tone': 'on'})
        chips = [{'label': _('Scale'), 'value': rec.scale_id.name or ''},
                 {'label': _('Starts on'), 'value': self._day(rec.effective_date)}]
        counts = rec._counts()
        chips.append({'label': _('Moves'), 'value': str(counts.get('move', 0))})
        if counts.get('above'):
            chips.append({'label': _('Above step, pay kept'),
                          'value': str(counts['above'])})
        if counts.get('pinned'):
            chips.append({'label': _('Pinned'), 'value': str(counts['pinned'])})
        for cost in rec.costs():
            chips.append({'label': _('Cost a month (%s)', cost.get('currency') or ''),
                          'value': cost.get('month_label') or ''})
        note = rec.reason or ''
        if rec.effective_date and rec.effective_date < rec._company_today():
            note = (note + '\n' if note else '') + _(
                "This rise starts on a date already gone. The pay team can re-work "
                "the months already paid.")
        return {'title': _('Who moves'), 'columns': [_('Now'), _('New')],
                'rows': rows, 'chips': chips, 'note': note}

    def _counts(self):
        self.ensure_one()
        out = {key: 0 for key, _l in OUTCOMES}
        for line in self.sudo().line_ids:
            out[line.outcome] = out.get(line.outcome, 0) + 1
        return out

    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending', 'block_note': False})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected'})
        return True

    def _approval_withdraw(self, request, reason):
        self.ensure_one()
        if self.state in LIVE_STATES:
            self.sudo().write({'state': 'cancelled'})
        return True

    def _approval_apply(self, request):
        """Approved: write the new version now (joiners from that day start on
        it) and the wages on the day — now when the day has come."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state in ('applied', 'scheduled', 'taken_back'):
            return True
        if rec.state == 'cancelled':
            raise UserError(_("This scale rise was cancelled, so nothing was written."))
        rec._write_version()
        if rec.effective_date and rec.effective_date > rec._company_today():
            rec.write({'state': 'scheduled', 'block_note': False})
            return True
        rec._write_wages(actor=self.env.user, by_job=False)
        return True

    # ==================================================================
    # Carrying it out
    # ==================================================================
    def _write_version(self):
        """The new version of the scale, from the effective date, holding the
        approved table. Idempotent: a request writes its version once."""
        self.ensure_one()
        rec = self.sudo()
        if rec.version_id:
            return rec.version_id
        scale = rec.scale_id
        start = rec.effective_date
        versions = scale.version_ids.sorted('date_from')
        latest = versions[-1:]
        if latest and start <= latest.date_from:
            raise UserError(_(
                "Nothing was written: the scale got a version from %(day)s after "
                "this rise was sent. Take this one back and prepare it again.",
                day=self._day(latest.date_from)))
        base = rec.base_version_id or latest
        if latest and (not latest.date_to or latest.date_to >= start):
            latest.date_to = start - timedelta(days=1)
        Version = self.env['pb.pay.scale.version'].sudo()
        version = Version.create({
            'scale_id': scale.id, 'date_from': start,
            'base_rate': rec.cells_base_rate if scale.mode == 'coefficient'
            else (base.base_rate if base else 0.0),
            'note': _("From scale rise %s", rec.name),
        })
        Cell = self.env['pb.pay.scale.cell'].sudo()
        for cell in rec.cells():
            Cell.create({'version_id': version.id, 'grade_id': int(cell['grade_id']),
                         'step_no': int(cell['step']),
                         'amount': float(cell.get('amount') or 0.0),
                         'coefficient': float(cell.get('coefficient') or 0.0)})
        if base:
            for line in base.package_ids:
                self.env['pb.pay.scale.package'].sudo().create({
                    'version_id': version.id, 'grade_id': line.grade_id.id,
                    'template_id': line.template_id.id, 'amount': line.amount})
        rec.version_id = version.id
        return version

    @api.model
    def _template_for(self, code):
        """Get-or-create the pay-line catalogue row for one code — the shape
        Change job and the contract drawer write."""
        Template = self.env['hr.contract.advantage.template'].sudo()
        found = Template.search([('code', '=', code)], limit=1)
        if found:
            return found
        vals = {'name': code, 'code': code, 'lower_bound': 0.0,
                'upper_bound': 0.0, 'default_value': 0.0}
        if 'value_type' in Template._fields:
            vals['value_type'] = 'amount'
        return Template.create(vals)

    @api.model
    def _wage_code(self, employee):
        """The input of the scheme that pays the person which reads the
        contract wage (BASIC / WAGE / BASE), if it has one."""
        for config in (self.env['pb.pay.scales']._schemes_for(employee) or []):
            for rule in config.sudo().rule_ids:
                if (rule.code or '').upper() in WAGE_CODES and rule.column_type == 'input':
                    return rule.code
        return ''

    def _write_wages(self, actor, by_job=False):
        """Every moving contract's wage, one savepoint per person. A person
        whose pay changed since the request was sent is skipped with the
        reason (nothing written for them); everybody else moves. Twice is
        once: a line already written is never written again."""
        self.ensure_one()
        rec = self.sudo()
        effective = rec.effective_date or rec._company_today()
        me = self.env(user=actor.id, su=True)
        C = me['hr.contract'].with_context(pb_pay_no_rebuild=True)
        Change = me['hr.contract.advantage.change']
        Apply = me['pb.pay.apply']
        note = _("Scale rise %(ref)s, from %(day)s", ref=rec.name, day=self._day(effective))
        now = fields.Datetime.now()
        written = self.env['pb.pay.apply']
        decimals = rec.scale_id.decimals()
        half = 0.5 * 10.0 ** (-decimals)
        for line in rec.line_ids.filtered(lambda l: l.outcome == 'move' and l.state == 'waiting'):
            contract = line.contract_id
            skip = ''
            if not contract or contract.state != 'open':
                skip = _("Their contract is no longer running.")
            elif abs(float(contract.wage or 0.0) - float(line.old_wage or 0.0)) >= half:
                skip = _("Their pay changed since the rise was sent (now %s), so "
                         "nothing was written for them.",
                         self._money(contract.wage, rec.scale_id.currency_id))
            elif contract.date_end and contract.date_end < effective:
                skip = _("Their contract ends before the rise starts.")
            if skip:
                line.write({'state': 'skipped', 'skip_reason': skip})
                continue
            try:
                with self.env.cr.savepoint():
                    C.browse(contract.id).write({'wage': float(line.new_wage)})
                    code = rec._wage_code(contract.employee_id)
                    if code:
                        # The dated row is what the Past-month re-work and
                        # proration read (facts §1.2 #5) — the record Change
                        # job writes, dated the rise's own day.
                        Change.log(contract, self._template_for(code),
                                   float(line.old_wage), float(line.new_wage),
                                   'pay_scale', notes=note, user=actor,
                                   effective_date=effective)
                    row = Apply.create({
                        'pb_scale_raise_id': rec.id,
                        'employee_id': contract.employee_id.id,
                        'contract_id': contract.id,
                        'company_id': (contract.company_id or contract.employee_id.company_id).id,
                        'currency_id': (line.cost_currency_id or rec.scale_id.currency_id).id,
                        'old_wage': float(line.old_wage),
                        'new_wage': float(line.new_wage),
                        'effective_date': effective,
                        'applied_at': now, 'applied_by': actor.id,
                        'undo_until': False,
                        'letter_state': 'pending',
                        'note': rec.name,
                    })
                    line.write({'state': 'done', 'apply_id': row.id, 'skip_reason': False})
                    written |= row
            except Exception as error:      # noqa: BLE001 — one never stops the rest
                self.env.invalidate_all()
                _logger.exception('scale rise %s: contract %s not written', rec.name,
                                  contract.id)
                line.write({'state': 'skipped', 'skip_reason': _(
                    "It could not be written: %s",
                    str(error.args[0] if getattr(error, 'args', None) else error)[:300])})
        rec.write({
            'state': 'applied', 'applied_at': now, 'applied_by': actor.id,
            'started_by_job': bool(by_job), 'block_note': False,
            'start_fail_days': 0,
        })
        if written:
            try:
                written._make_letters(limit=LETTERS_INLINE)
            except Exception:       # noqa: BLE001 — the paperwork is not the rise
                _logger.exception('scale rise %s: letters not printed', rec.name)
            try:
                self.env['pb.pay.apply']._recompute_positions(
                    written.mapped('company_id'))
            except Exception:       # noqa: BLE001 — positions are a report
                _logger.info('scale rise: pay positions not rebuilt')
        done = len(written)
        rec.message_post(body=_("Done. New pay written for %(n)s from %(day)s.",
                                n=self.env['pb.pay.bands']._people_phrase(done),
                                day=self._day(effective)))
        return done

    # ==================================================================
    # The day comes: the hourly job
    # ==================================================================
    def _lock(self, wait=False):
        self.ensure_one()
        self.env.flush_all()
        query = ('SELECT id FROM pb_pay_scale_raise WHERE id = %s FOR UPDATE '
                 + ('NOWAIT' if wait else 'SKIP LOCKED'))
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(query, [self.id])
                got = self.env.cr.fetchone()
        except LOCK_ERRORS:
            return False
        self.invalidate_recordset()
        return bool(got)

    def _start_user(self):
        self.ensure_one()
        if self.user_id and self.user_id.active:
            return self.user_id
        request = self.sudo().approval_request_id
        if request:
            for decision in self.env['biz.approval.decision'].sudo().search(
                    [('request_id', '=', request.id)], order='id desc'):
                if decision.create_uid and decision.create_uid.active:
                    return decision.create_uid
        return self.env.user

    def _start_scheduled(self):
        """``(outcome, sentence)``: started / busy / gone."""
        self.ensure_one()
        if not self._lock():
            return 'busy', ''
        rec = self.sudo()
        if rec.state != 'scheduled':
            return 'gone', ''
        if rec.effective_date and rec.effective_date > rec._company_today():
            return 'gone', ''
        with self.env.cr.savepoint():
            rec._write_wages(actor=rec._start_user(), by_job=True)
        return 'started', ''

    @api.model
    def _cron_apply_due(self, limit=50):
        """The quiet hourly job: write every approved rise whose day has come,
        one transaction each. Safe on an empty database (one search)."""
        testing = bool(odoo_module.current_test)
        todo = self.sudo().search([('state', '=', 'scheduled'),
                                   ('effective_date', '!=', False)],
                                  order='effective_date, id', limit=int(limit or 50))
        tally = {}
        for rec in todo:
            if rec.effective_date > rec._company_today():
                continue
            try:
                with self.env.cr.savepoint():
                    outcome, _sentence = rec._start_scheduled()
            except LOCK_ERRORS:
                self.env.invalidate_all()
                outcome = 'busy'
            except Exception:   # noqa: BLE001 — one never stops the rest
                self.env.invalidate_all()
                _logger.exception('scale rise: could not start %s', rec.name)
                rec._record_start_failure()
                outcome = 'failed'
            tally[outcome] = tally.get(outcome, 0) + 1
            if not testing:
                self.env.cr.commit()
        if tally:
            _logger.info('pb_pay_scales: scale rises %s', tally)
        return tally

    def _record_start_failure(self):
        self.ensure_one()
        rec = self.sudo()
        today = rec._company_today()
        days = rec.start_fail_days or 0
        if rec.start_last_fail != today:
            days += 1
        rec.write({'start_fail_days': days, 'start_last_fail': today,
                   'block_note': _("Could not be written on %s; it will be tried "
                                   "again.", self._day(today))})
        return days

    # ==================================================================
    # Cancel and take back
    # ==================================================================
    def _may_act(self):
        self.ensure_one()
        return bool(self.user_id == self.env.user or self._may_prepare())

    def action_cancel(self):
        """Stop a request that is still being prepared or waiting."""
        self.ensure_one()
        if not self._may_act():
            raise AccessError(_("Only the person who prepared it or the people "
                                "who set pay bands can cancel a scale rise."))
        if self.state not in ('draft', 'pending', 'returned'):
            raise UserError(_("Only a rise that has not been approved yet can be "
                              "cancelled."))
        request = self.sudo().approval_request_id
        if request and request.state in ('pending', 'blocked'):
            try:
                self.env['biz.approval.engine'].sudo().cancel(
                    request, _("Cancelled from the scale rise."))
            except Exception:   # noqa: BLE001 — the rise still stops
                _logger.info('scale rise: request %s not withdrawn', request.id)
        self.sudo().write({'state': 'cancelled', 'block_note': False})
        return True

    def action_take_back(self):
        """Before the effective date: the approved rise goes, with its version.
        Nothing on any contract had moved yet. After the date only a new
        request changes pay again."""
        self.ensure_one()
        if not self._may_act():
            raise AccessError(_("Only the person who prepared it or the people "
                                "who set pay bands can take a scale rise back."))
        rec = self.sudo()
        if rec.state != 'scheduled':
            raise UserError(_(
                "Only an approved rise that has not started yet can be taken "
                "back. Once it has started, prepare a new request instead."))
        if not rec._lock(wait=True):
            raise UserError(_("This rise is being written right now. Look again "
                              "in a minute."))
        if rec.state != 'scheduled' or (rec.effective_date
                                        and rec.effective_date <= rec._company_today()):
            raise UserError(_(
                "This rise has started, so it can no longer be taken back. "
                "Prepare a new request instead."))
        version = rec.version_id
        if version and version.exists():
            before = rec.scale_id.version_ids.filtered(
                lambda v: v.date_from < version.date_from).sorted('date_from')[-1:]
            later = rec.scale_id.version_ids.filtered(
                lambda v: v.date_from > version.date_from)
            version.unlink()
            if before and not later:
                before.date_to = False
            elif before and later:
                before.date_to = later.sorted('date_from')[0].date_from - timedelta(days=1)
        rec.write({'state': 'taken_back', 'version_id': False,
                   'taken_back_at': fields.Datetime.now(),
                   'taken_back_by': self.env.uid})
        rec.message_post(body=_("Taken back before it started. Nobody's pay changed."))
        return True

    # ==================================================================
    # The Past-month re-work door (C-6: deep link only)
    # ==================================================================
    @api.model
    def _retro_installed(self):
        return 'pb.retro.review' in self.env and 'pb.retro.board' in self.env

    def action_open_rework(self):
        """Open NEW draft Past-month re-works for the moved people and the paid
        months, one per pay scheme, through the re-work's own door and gate.
        Writes nothing else. Returns the first re-work's id."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'applied':
            raise UserError(_("This rise has not been written yet."))
        if not self._retro_installed():
            raise UserError(_("Past-month re-work is not part of this database. "
                              "Tell the pay team: they can work out any difference "
                              "by hand on the next pay run."))
        months = rec.paid_months()
        moved = set(rec.line_ids.filtered(lambda l: l.state == 'done')
                    .mapped('employee_id').ids)
        known = [int(i) for i in rec._json('rework_ids_json', [])]
        alive = self.env['pb.retro.review'].sudo().browse(known).exists()
        if alive:
            return {'ok': True, 'review_id': alive[:1].id, 'review_ids': alive.ids}
        by_scheme = {}
        for row in months:
            if not row.get('config_id'):
                continue
            entry = by_scheme.setdefault(row['config_id'], {'months': set(), 'people': set()})
            entry['months'].add(row['month'])
            entry['people'].update(p for p in row.get('people') or [] if p in moved)
        if not by_scheme:
            raise UserError(_("No month already paid is affected."))
        made = []
        for config_id, entry in sorted(by_scheme.items()):
            if not entry['people']:
                continue
            picked = sorted(entry['months'])
            first = fields.Date.to_date(picked[0])
            last = fields.Date.to_date(picked[-1])
            if (last.year - first.year) * 12 + last.month - first.month >= 12:
                first = (last.replace(day=1) - timedelta(days=330)).replace(day=1)
            answer = self.env['pb.retro.board'].save_review({
                'config_id': config_id,
                'month_from': fields.Date.to_string(first),
                'month_to': fields.Date.to_string(last),
                'people': 'picked',
                'employee_ids': sorted(entry['people'])[:500],
                'reason': _("Scale rise %(ref)s on %(scale)s starts on %(day)s, in "
                            "a month already paid.", ref=rec.name,
                            scale=rec.scale_id.name, day=self._day(rec.effective_date)),
            })
            if (answer or {}).get('id'):
                made.append(int(answer['id']))
        rec.write({'rework_ids_json': json.dumps(made)})
        return {'ok': True, 'review_id': made[0] if made else 0, 'review_ids': made}

    # ==================================================================
    # The route
    # ==================================================================
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', ('pb_pay.group_pay_manager',))
        Seed.fill_role_from_group(company, 'finance', ('pb_pay.group_pay_finance',))
        return Seed.lay(
            company, RAISE_PROCESS_KEY, 'Pay scale rises', _raise_route(),
            binding_note='The route every pay scale rise follows: HR, then '
                         'Finance.',
            model_name='pb.pay.scale.raise',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when pay scale rises were installed')


def _raise_route():
    """Owner rulings SC1 / Q4 defaults: HR lead, then the Finance approver.
    No manager step: a whole scale has no single line manager (the
    pay-change precedent, `pb_pay_approval._pay_route`)."""
    return route(
        role_step(_('HR lead'), 'hr_lead', key='hr'),
        role_step(_('Finance approver'), 'finance', key='fin'),
    )


class PbPayScaleRaiseLine(models.Model):
    _name = 'pb.pay.scale.raise.line'
    _description = 'Person in a pay scale rise'
    _order = 'raise_id, outcome, id'

    raise_id = fields.Many2one('pb.pay.scale.raise', required=True,
                               ondelete='cascade', index=True)
    contract_id = fields.Many2one('hr.contract', string='Contract',
                                  ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Person',
                                  ondelete='cascade', index=True)
    company_id = fields.Many2one(related='raise_id.company_id', store=True)
    grade_id = fields.Many2one('pb.pay.scale.grade', string='Grade',
                               ondelete='set null')
    step_no = fields.Integer(string='Step')
    outcome = fields.Selection(OUTCOMES, string='What happens', required=True,
                               index=True)
    why = fields.Char(string='Why')
    old_wage = fields.Float(string='Paid now', digits=(16, 2))
    new_wage = fields.Float(string='Paid after', digits=(16, 2))
    step_old = fields.Float(string='Their step now', digits=(16, 2))
    drifted = fields.Boolean(string='Paid differently from their step')
    cost_month = fields.Float(string='Cost a month', digits=(16, 2))
    cost_how = fields.Selection([('engine', 'Through the pay rules'),
                                 ('wage', 'Wage difference only')],
                                string='Worked out')
    cost_currency_id = fields.Many2one('res.currency', string='Paid in')
    state = fields.Selection(LINE_STATES, default='waiting', required=True,
                             index=True)
    skip_reason = fields.Char(string='Why it was not written')
    apply_id = fields.Many2one('pb.pay.apply', string='Pay written',
                               ondelete='set null')


class PbPayApplyScaleRaise(models.Model):
    """The wage row a scale rise writes — so the person's pay history, the
    portal's "what last changed my pay" and the pay letters job see it the way
    they see every other written pay change."""
    _inherit = 'pb.pay.apply'

    pb_scale_raise_id = fields.Many2one('pb.pay.scale.raise', string='Scale rise',
                                        ondelete='cascade', index=True)

    def _make_letters(self, source=None, limit=None):
        """Rows of a scale rise get the scale rise letter; every other row
        keeps the pay letter exactly as before."""
        mine = self.filtered('pb_scale_raise_id')
        rest = self - mine
        made = super(PbPayApplyScaleRaise, rest)._make_letters(source, limit) if rest else 0
        if mine:
            made += mine._pbs_raise_letters(limit)
        return made

    def _pbs_raise_letters(self, limit=None):
        template = self._pbs_raise_template()
        if not template:
            self.sudo().write({'letter_state': 'none'})
            return 0
        Letter = self.env['pb.hr.letter'].sudo()
        money = self.env['pb.pay.bands']
        made = 0
        todo = self if limit is None else self[:limit]
        for row in todo:
            try:
                with self.env.cr.savepoint():
                    rise = row.pb_scale_raise_id.sudo()
                    line = rise.line_ids.filtered(lambda l: l.apply_id == row)[:1]
                    currency = row.currency_id or row.company_id.currency_id
                    extra = {
                        'old_pay': money._money(row.old_wage, currency),
                        'new_pay': money._money(row.new_wage, currency),
                        'increase_pct': '%.2f' % (
                            (row.new_wage - row.old_wage) / row.old_wage * 100.0
                            if row.old_wage else 0.0),
                        'effective_date': format_date(self.env, row.effective_date,
                                                      date_format='d MMM y')
                        if row.effective_date else '',
                        'scale': rise.scale_id.name or '',
                        'grade': line.grade_id.name if line else '',
                        'step': str(line.step_no) if line else '',
                    }
                    letter = Letter.create({
                        'employee_id': row.employee_id.id,
                        'template_id': template.id,
                        'subject': template.subject or template.name,
                        'context_json': json.dumps(extra, default=str),
                        'company_id': (row.company_id or self.env.company).id,
                    })
                    letter.action_generate()
                    row.sudo().write({'letter_id': letter.id, 'letter_state': 'done'})
                    made += 1
            except Exception:   # noqa: BLE001 — a letter never undoes a rise
                _logger.exception('pb_pay_scales: no rise letter for employee %s',
                                  row.employee_id.id)
        return made

    @api.model
    def _pbs_raise_template(self):
        if 'pb.letter.template' not in self.env:
            return None
        Template = self.env['pb.letter.template'].sudo()
        found = Template.search([('letter_type', '=', LETTER_SCALE_RAISE),
                                 ('active', '=', True)], order='sequence, id', limit=1)
        if found:
            return found
        name = _('Pay scale rise letter')
        body = ('<div><p>Dear ${employee_name},</p>'
                '<p>${scale} rises from ${effective_date}. You are on ${grade}, '
                'step ${step}, so your monthly pay changes from '
                '<strong>${old_pay}</strong> to <strong>${new_pay}</strong>, an '
                'increase of ${increase_pct}%.</p>'
                '<p>Everything else in your terms of employment is unchanged.</p>'
                '<p>${company}</p><p>${date}</p></div>')
        category = self.env.ref('pb_employee_vault.cat_other', raise_if_not_found=False)
        return Template.create({
            'name': name, 'letter_type': LETTER_SCALE_RAISE, 'subject': name,
            'sequence': 50, 'body_html': body, 'company_id': False,
            'vault_category_id': category.id if category else False,
        })


class PbLetterTemplateScaleRaise(models.Model):
    _inherit = 'pb.letter.template'

    letter_type = fields.Selection(
        selection_add=[(LETTER_SCALE_RAISE, 'Pay scale rise letter')],
        ondelete={LETTER_SCALE_RAISE: 'set default'})


class BizApprovalRequestSeatScaleRaise(models.Model):
    """A seat on a scale rise is also a permission to READ it (AM60)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.pay.scale.raise' or not request.res_id:
                continue
            record = self.env['pb.pay.scale.raise'].sudo().browse(request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats


class ResCompanyScaleRaiseSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.pay.scale.raise']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('scale rise: %s has no route yet', company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.pay.scale.raise']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an install must not die here
            _logger.exception('scale rise: %s has no route yet', company.name)
    _logger.info('pb_pay_scales: %s companies have a scale rise route', done)
    return done


def post_init_hook(env):
    seed_all(env)
