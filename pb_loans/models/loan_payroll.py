# -*- coding: utf-8 -*-
"""WDGAP PR-B — how every kind of pay run takes a loan instalment, once.

Cloned from the paid-once machinery of `pb.updates.oneoff` (UPDATES P2d,
`pb_updates/models/updates_oneoff.py` + `updates_payrun.py`): the same two
resolver seams, the same token-in-the-context / values-in-the-cursor-cache
trick (UPDATES G31), the same reserve → paid → released life. The token key is
this module's own (`pb_loans_token`), so the two streams never read each
other's bookkeeping and both work in the same payslip (test T12).

THE TWO SEAMS (ledger U24) — each override calls `super()` FIRST:

  1. `hr.payslip._get_formula_input_values` — no pay data file, native
     "Compute Sheet", the no-file branch of "Recalculate".
  2. `hr.payroll.import.batch._transform_data_to_formula_inputs` — a run with
     a pay data file (create and recalculate) and monthly-template runs.

Application-data mode (U25) is served by a typed source instead,
`loans.instalment` (`_application_source_catalogue` /
`_application_domain_values`), reserved when the payslip resolves its inputs.

BYTE-IDENTITY RAIL: a payslip whose person has no loan to take and holds no
repayment line gets exactly what `super()` returned.

WHICH PAY ITEM: the scheme's own setting "Loan repayments go into"
(`hr.formula.config.pb_loan_rule_id`), an INPUT pay item; the instalment is fed
as a positive number and the scheme's formula decides the sign. No setting →
nothing is fed and the payslip is flagged (R4: never raise into the run).

WHO PAYS: only a REGULAR run (`pb_run_kind`), never a mid-month advance
scheme, only the scheme the person is paid by for that month (the scheme map,
when it answers), one instalment per loan per pay month whatever happens.
"""
import logging
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .loan import (DONE_SLIP_STATES, LIVE_LINE_STATES, TAKING_STATES,
                   month_of)

try:
    from odoo.addons.pb_hr_payroll_formula.models import input_provenance
except Exception:  # pragma: no cover — the engine is a dependency
    input_provenance = None
try:
    from odoo.addons.pb_hr_payroll_formula.models.application_domain_sources import (
        source_result)
except Exception:  # pragma: no cover
    source_result = None

_logger = logging.getLogger(__name__)

#: The application-data source key a scheme's input names to receive loans.
SOURCE_KEY = 'loans.instalment'
#: How a value from a loan says so in a payslip's sources.
LOANS_VIA = 'loan_repayment'
#: The pay data file's sides, as the resolver's provenance names them.
FILE_SOURCES = ('excel', 'feed', 'rule')
#: Why a payslip did not take an instalment it owed (stored on the payslip).
ISSUES = [
    ('no_item', 'No pay item for loan repayments'),
    ('currency', 'Loan in another currency'),
    ('other_source', 'Another amount for loan repayments'),
    ('error', 'Loan instalment could not be applied'),
]

# The finer "why" words of other screens, taught the new one once at import.
try:  # pragma: no cover — import-time registration only
    if input_provenance is not None and LOANS_VIA not in input_provenance.VIAS:
        input_provenance.VIAS = tuple(input_provenance.VIAS) + (LOANS_VIA,)
except Exception:  # noqa: BLE001
    pass
try:  # pragma: no cover
    from odoo.addons.pb_source_atlas.models import pb_source_atlas as _atlas
    _atlas.VIA_LABELS.setdefault(LOANS_VIA, 'a loan or salary advance instalment')
except Exception:  # noqa: BLE001
    pass

# ---------------------------------------------------------------- the token
#: Where a computing caller collects what the seams used. The context carries
#: only a token: a context is copied whenever somebody adds a key to it, so a
#: dict passed IN it would be filled on a copy (UPDATES G31).
USED_KEY = 'pb_loans_used'


def used_start(env):
    token = uuid.uuid4().hex
    env.cr.cache.setdefault(USED_KEY, {})[token] = {}
    return token


def used_of(env):
    """The bookkeeping dict of the computing caller, or None (a review screen)."""
    token = env.context.get('pb_loans_token')
    if not token:
        return None
    return env.cr.cache.setdefault(USED_KEY, {}).setdefault(token, {})


def used_end(env, token):
    return env.cr.cache.get(USED_KEY, {}).pop(token, None) or {}


def _blank(value):
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _number(value):
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same(left, right, currency):
    a, b = _number(left), _number(right)
    if a is None or b is None:
        return False
    return float_compare(a, b, precision_rounding=currency.rounding or 0.01) == 0


def loans_entry(loan_ids):
    key = 'loans:%s' % ','.join(str(i) for i in sorted(loan_ids)) if loan_ids else 'loans:'
    if input_provenance is not None:
        return input_provenance.entry('employee_field', key=key, via=LOANS_VIA)
    return {'src': 'employee_field', 'key': key, 'via': LOANS_VIA}


# =====================================================================
# The scheme's setting
# =====================================================================
class HrFormulaConfigLoans(models.Model):
    _inherit = 'hr.formula.config'

    pb_loan_rule_id = fields.Many2one(
        'hr.formula.rule', string='Loan repayments go into',
        domain="[('config_id', '=', id), ('column_type', '=', 'input')]",
        ondelete='set null',
        help="The input pay item that receives each month's loan and salary "
             "advance instalment, as a positive amount. The scheme's own formula "
             "decides whether it is taken off pay. Leave it empty and no "
             "instalment is taken by this scheme — the pay run says so.")

    @api.constrains('pb_loan_rule_id')
    def _check_pb_loan_rule(self):
        for config in self:
            rule = config.pb_loan_rule_id
            if not rule:
                continue
            if rule.config_id != config or rule.column_type != 'input':
                raise UserError(_(
                    "Loan repayments must go into an input pay item of this pay "
                    "scheme."))
            if (rule.value_kind or 'money') != 'money':
                raise UserError(_("Loan repayments must go into a money pay item."))

    def _pb_loan_rule(self):
        """The pay item a loan instalment goes into, or an empty record.

        Application-data schemes take it through the typed source instead: a
        rule whose source is `loans.instalment`."""
        self.ensure_one()
        config = self.sudo()
        if 'application_source_key' in config.rule_ids._fields:
            keyed = config.rule_ids.filtered(
                lambda r: r.column_type == 'input'
                and (r.application_source_key or '').strip() == SOURCE_KEY)
            if keyed:
                return keyed[:1]
        rule = config.pb_loan_rule_id
        if rule and rule.config_id == config and rule.column_type == 'input':
            return rule
        return self.env['hr.formula.rule']

    # -------------------------------------------- application-data mode
    def _application_source_catalogue(self):
        result = dict(super()._application_source_catalogue())
        result[SOURCE_KEY] = {
            'label': 'Loan and salary advance instalments',
            'unit': 'money', 'model': 'pb.loan', 'writable': False,
            'available': True, 'cardinality': 'many',
        }
        return result

    def _application_domain_values(self, employee, contract, date_from, date_to):
        result = dict(super()._application_domain_values(
            employee, contract, date_from, date_to))
        self.ensure_one()
        rules = self.sudo().rule_ids.filtered(
            lambda r: r.column_type == 'input'
            and (r.application_source_key or '').strip() == SOURCE_KEY)
        if not rules or source_result is None:
            return result
        try:
            result[SOURCE_KEY] = self._pb_loans_application_value(
                employee, date_from, date_to)
        except Exception:       # noqa: BLE001 — R4: a loan never breaks a run
            _logger.exception('pb_loans: application source failed for %s',
                              employee.id)
            result[SOURCE_KEY] = source_result(
                status='conflict', reason='Loan instalments could not be read.')
        return result

    def _pb_loans_application_value(self, employee, date_from, date_to):
        ctx = self.env.context
        run_id = ctx.get('pb_application_run_id') or ctx.get('application_run_id')
        slip_id = ctx.get('pb_application_payslip_id') or ctx.get('application_payslip_id')
        run = self.env['hr.payslip.run'].sudo().browse(run_id or 0).exists()
        plan = self.env['pb.loan']._plan_for_slip(
            employee, self, fields.Date.to_date(date_from), fields.Date.to_date(date_to),
            slip_id=slip_id or None, run=run)
        if not plan or not plan.get('items'):
            # Nothing due (or nothing this run may take): a confident zero —
            # the loans store IS the record of what is owed.
            return source_result(0.0, 'resolved', [],
                                 reason='No loan instalment is due this month.')
        if plan.get('issue') == 'currency':
            return source_result(status='conflict', reason=(
                'A loan of this person is in another currency than this pay scheme.'))
        loans = self.env['pb.loan'].sudo().browse([i['loan'].id for i in plan['items']])
        return source_result(
            plan['total'], 'resolved', loans,
            month=str(plan['month']), paid_once='pb_loans',
            pb_loan_amounts={str(i['loan'].id): i['amount'] for i in plan['items']})


# =====================================================================
# The plan for one payslip
# =====================================================================
class PbLoanPlan(models.Model):
    _inherit = 'pb.loan'

    @api.model
    def _plan_for_slip(self, employee, config, date_from, date_to, slip_id=None,
                       run=None, lock=False):
        """What a payslip of this person, scheme and period takes, or None.

        `{'month', 'code', 'items': [{'loan', 'amount'}], 'total', 'issue',
        'held'}` — `held` is True when this payslip already holds a repayment
        line (so a recompute can drop it). None means: nothing to do, and the
        caller returns exactly what `super()` returned."""
        if not employee or not config or not date_to:
            return None
        Line = self.env['pb.loan.repayment'].sudo()
        month = month_of(date_to)
        held = Line.search([('payslip_id', '=', slip_id), ('kind', '=', 'payroll'),
                            ('state', 'in', LIVE_LINE_STATES)]) if slip_id else Line
        run = run or self.env['hr.payslip.run']
        taking = True
        if run and 'pb_run_kind' in run._fields and (run.pb_run_kind or 'regular') != 'regular':
            taking = False          # a top-up never takes an instalment
        config = config.sudo()
        if config.cycle_type == 'mid_cycle':
            taking = False          # a mid-month advance scheme never does
        loans = self.sudo().browse()
        if taking:
            loans = self.sudo().search([
                ('employee_id', '=', employee.id), ('state', 'in', TAKING_STATES),
                ('first_month', '<=', month)], order='id')
        if not loans and not held:
            return None
        if taking and loans and not self._pb_scheme_pays(employee, config, date_to):
            loans = self.sudo().browse()
            if not held:
                return None
        if lock and loans:
            self.env.cr.execute('SELECT id FROM pb_loan WHERE id IN %s ORDER BY id FOR UPDATE',
                                (tuple(loans.ids),))
            loans.invalidate_recordset()
            loans.repayment_ids.invalidate_recordset()
        currency = config.currency_id or config.company_id.currency_id \
            or self.env.company.currency_id
        rule = config._pb_loan_rule()
        leaving_day = employee.sudo().departure_date if 'departure_date' in employee._fields else False
        start = fields.Date.to_date(date_from) or month
        end = fields.Date.to_date(date_to)
        items, issue = [], False
        for loan in loans:
            mine = loan.repayment_ids.filtered(
                lambda l: l.kind == 'payroll' and l.state in LIVE_LINE_STATES
                and l.pay_month == month)
            if mine and mine.payslip_id and mine.payslip_id.id != slip_id:
                continue            # this month's instalment is another payslip's
            if loan.currency_id != currency:
                issue = 'currency'
                continue
            available = loan._available(exclude_slip_id=slip_id,
                                        exclude_line_ids=tuple(mine.ids))
            leaving = (loan.on_leaving == 'take_rest' and leaving_day
                       and start <= leaving_day <= end)
            amount = available if leaving else min(loan.plan_amount or 0.0, available)
            amount = loan.currency_id.round(amount)
            if amount <= 0:
                continue
            items.append({'loan': loan, 'amount': amount, 'leaving': bool(leaving)})
        if items and not rule:
            issue = 'no_item'
        total = currency.round(sum(i['amount'] for i in items))
        return {'month': month, 'code': rule.code if rule else False,
                'items': items, 'total': total, 'issue': issue,
                'held': bool(held), 'currency': currency}

    @api.model
    def _pb_scheme_pays(self, employee, config, on_date):
        """Is `config` the scheme this person is paid by for that month?

        Asked of the scheme map (the pay run's own resolver) for the scheme's
        own kind of cycle. A map that names nobody answers yes: the one live
        line per loan and month still makes sure only the first payslip takes
        it."""
        Map = self.env.get('pb.scheme.map')
        if Map is None:
            return True
        try:
            answer = Map.sudo().resolve(employee, config.cycle_type or 'any', on_date) or {}
        except Exception:       # noqa: BLE001 — a resolver never stops a payslip
            return True
        other = answer.get('config_id') or 0
        return not other or other == config.id

    # ------------------------------------------------------------ merge
    @api.model
    def _merge(self, plan, values, prov, used, carried=None):
        """Put a plan into a resolver's answer. Returns nothing; fills `used`.

        `carried(code, entry, other)` says whether ANOTHER source of this run
        really carried an amount for the loan pay item (default: a non-zero
        number from any source but none and this module)."""
        if plan is None:
            return
        code = plan.get('code')
        items = plan.get('items') or []
        issue = plan.get('issue') or False
        lines = {}
        if code and items and issue not in ('no_item',):
            entry = prov.get(code) or {}
            src = entry.get('src') or 'none'
            other = values.get(code)
            if carried is not None:
                other_carries = carried(code, entry, other)
            else:
                number = _number(other)
                other_carries = (src != 'none' and entry.get('via') != LOANS_VIA
                                 and number is not None and number != 0)
            currency = plan['currency']
            if not other_carries:
                values[code] = plan['total']
                prov[code] = loans_entry([i['loan'].id for i in items])
                lines = {i['loan'].id: i['amount'] for i in items}
            elif _same(other, plan['total'], currency):
                lines = {i['loan'].id: i['amount'] for i in items}
            else:
                issue = 'other_source'
        elif code and plan.get('held'):
            # A recompute without the instalment it took before: say 0 so the
            # stored value is not carried over (`action_recompute_formula_lines`
            # keeps a stored value only for codes nothing answers).
            entry = prov.get(code) or {}
            if (entry.get('src') or 'none') == 'none' or entry.get('via') == LOANS_VIA \
                    or _blank(values.get(code)):
                values[code] = 0.0
                prov[code] = loans_entry([])
        if used is not None:
            used['lines'] = lines
            used['issue'] = issue
            used['month'] = plan.get('month')
            used['seen'] = True


# =====================================================================
# Paid once: reserve, pay, release
# =====================================================================
class PbLoanRepaymentSync(models.Model):
    _inherit = 'pb.loan.repayment'

    @api.model
    def _sync_slip(self, slip, used):
        """After a payslip computed: hold what it used, free what it no longer
        uses, write why nothing was taken. Never two payslips for one line."""
        slip = slip.sudo()
        if not slip or not slip.id:
            return
        used = used or {}
        issue = used.get('issue') or False
        if 'pb_loan_issue' in slip._fields and used.get('seen') \
                and (slip.pb_loan_issue or False) != issue:
            slip.with_context(pb_loans_issue_write=True).write({'pb_loan_issue': issue})
        held = self.sudo().search([('payslip_id', '=', slip.id), ('kind', '=', 'payroll'),
                                   ('state', 'in', LIVE_LINE_STATES)])
        wanted = used.get('lines') or {}
        if not wanted and not held:
            return
        month = used.get('month') or month_of(slip.date_to)
        done = slip.state in DONE_SLIP_STATES
        Loan = self.env['pb.loan'].sudo()
        touched = Loan.browse()
        for loan_id, amount in sorted(wanted.items()):
            loan = Loan.browse(int(loan_id)).exists()
            if not loan:
                continue
            touched |= loan
            line = held.filtered(lambda l: l.loan_id == loan)[:1] or self.sudo().search([
                ('loan_id', '=', loan.id), ('pay_month', '=', month),
                ('kind', '=', 'payroll'), ('state', 'in', LIVE_LINE_STATES)], limit=1)
            if line and line.payslip_id and line.payslip_id != slip:
                # The seam skips such a loan; reaching this means a race the
                # row lock did not catch. Never pay twice: stop this payslip.
                raise UserError(_(
                    "The %(month)s instalment of %(ref)s is already in pay run "
                    "%(run)s, so it is not taken again here.",
                    ref=loan.name, month=loan._month_label(month),
                    run=line._run_label()))
            vals = {'amount': amount, 'payslip_id': slip.id,
                    'run_id': slip.payslip_run_id.id or False,
                    'state': 'paid' if done else 'reserved'}
            if done:
                vals['paid_on'] = fields.Date.context_today(self)
            if line:
                changes = {k: v for k, v in vals.items()
                           if (line[k].id if hasattr(line[k], 'id') else line[k]) != v}
                if changes:
                    line._write_line(changes)
            else:
                vals.update({'loan_id': loan.id, 'pay_month': month, 'kind': 'payroll',
                             'note': _("Taken by payslip %s.", slip.name or slip.id)})
                self.sudo().create(vals)
                loan._post(_("%(amount)s taken in pay run %(run)s for %(month)s.",
                             amount=loan._money(amount),
                             run=slip.payslip_run_id.name or slip.name or '',
                             month=loan._month_label(month)))
        for line in held.filtered(lambda l: l.loan_id.id not in wanted):
            touched |= line.loan_id
            line._release(_("Payslip %s no longer takes it.", slip.name or slip.id))
        touched._touch()
        touched._check_closed()

    def _release(self, why):
        for line in self.sudo():
            if line.state not in LIVE_LINE_STATES or line.kind != 'payroll':
                continue
            was_paid = line.state == 'paid'
            line._write_line({'state': 'released', 'note': why})
            line.loan_id._post(_("%(amount)s for %(month)s given back: %(why)s",
                                 amount=line.loan_id._money(line.amount),
                                 month=line.loan_id._month_label(line.pay_month),
                                 why=why))
            if was_paid:
                line.loan_id._check_closed()

    @api.model
    def _slips_done(self, slips):
        lines = self.sudo().search([('payslip_id', 'in', slips.ids),
                                    ('state', '=', 'reserved'), ('kind', '=', 'payroll')])
        for line in lines:
            line._write_line({'state': 'paid', 'paid_on': fields.Date.context_today(self)})
        lines.loan_id._check_closed()

    @api.model
    def _slips_undone(self, slips):
        """A finished payslip set back to an earlier step: it holds its
        instalment again rather than having paid it."""
        lines = self.sudo().search([('payslip_id', 'in', slips.ids),
                                    ('state', '=', 'paid'), ('kind', '=', 'payroll')])
        for line in lines:
            line._write_line({'state': 'reserved', 'paid_on': False})
        lines.loan_id._check_closed()

    @api.model
    def _slips_gone(self, slips, why):
        if not slips:
            return
        self.sudo().search([('payslip_id', 'in', slips.ids), ('kind', '=', 'payroll'),
                            ('state', 'in', LIVE_LINE_STATES)])._release(why)


# =====================================================================
# Seam 1 + the computing wrappers + the payslip hooks
# =====================================================================
class HrPayslipLoans(models.Model):
    _inherit = 'hr.payslip'

    pb_loan_issue = fields.Selection(
        ISSUES, string='Loan instalment not taken', readonly=True, copy=False,
        help='Why this payslip did not take a loan instalment the person owes.')
    pb_loan_line_ids = fields.One2many('pb.loan.repayment', 'payslip_id',
                                       string='Loan repayments', readonly=True)

    # ------------------------------------------------------------ seam 1
    def _get_formula_input_values(self, config, provenance=None):
        ctx = self.env.context
        if ctx.get('pb_application_data_mode') or not self or len(self) != 1:
            return super()._get_formula_input_values(config, provenance=provenance)
        used = used_of(self.env)
        slip_id = self.id if isinstance(self.id, int) else None
        try:
            plan = self.env['pb.loan']._plan_for_slip(
                self.employee_id, config, self.date_from, self.date_to, slip_id,
                self.payslip_run_id, lock=used is not None)
        except Exception:       # noqa: BLE001 — R4: log + flag, never raise
            _logger.exception('pb_loans: the loan plan failed for payslip %s', slip_id)
            if used is not None:
                used.update({'issue': 'error', 'seen': True, 'lines': {}})
            return super()._get_formula_input_values(config, provenance=provenance)
        if plan is None:
            if used is not None:
                used.update({'issue': False, 'seen': True, 'lines': {}})
            return super()._get_formula_input_values(config, provenance=provenance)
        prov = provenance if provenance is not None else {}
        values = super()._get_formula_input_values(config, provenance=prov)
        self.env['pb.loan']._merge(plan, values, prov, used)
        return values

    # ------------------------------------------------------------ wrappers
    def _pb_compute_sheet_with_formulas(self):
        Line = self.env['pb.loan.repayment'].sudo()
        for slip in self:
            if hasattr(slip, '_application_mode') and slip._application_mode():
                super(HrPayslipLoans, slip)._pb_compute_sheet_with_formulas()
                continue
            token = used_start(self.env)
            try:
                super(HrPayslipLoans, slip.with_context(
                    pb_loans_token=token))._pb_compute_sheet_with_formulas()
            except Exception:
                used_end(self.env, token)
                raise
            Line._sync_slip(slip, used_end(self.env, token))
        return True

    def action_recompute_formula_lines(self):
        Line = self.env['pb.loan.repayment'].sudo()
        result = None
        for slip in self:
            if hasattr(slip, '_application_mode') and slip._application_mode():
                result = super(HrPayslipLoans, slip).action_recompute_formula_lines()
                continue
            token = used_start(self.env)
            try:
                result = super(HrPayslipLoans, slip.with_context(
                    pb_loans_token=token, pb_loans_slip_id=slip.id)
                ).action_recompute_formula_lines()
            except Exception:
                used_end(self.env, token)
                raise
            Line._sync_slip(slip, used_end(self.env, token))
        return result

    # -------------------------------------------- application-data mode
    def _application_resolve_inputs(self, config):
        answer = super()._application_resolve_inputs(config)
        try:
            values, sources = answer
        except (TypeError, ValueError):
            return answer
        wanted, month = {}, None
        for code, entry in (sources or {}).items():
            if not isinstance(entry, dict) or entry.get('key') != SOURCE_KEY:
                continue
            evidence = entry.get('evidence') or {}
            for loan_id, amount in (evidence.get('pb_loan_amounts') or {}).items():
                wanted[int(loan_id)] = float(amount)
            if evidence.get('month'):
                month = fields.Date.to_date(evidence['month'])
        self.env['pb.loan.repayment'].sudo()._sync_slip(
            self, {'lines': wanted, 'month': month or month_of(self.date_to),
                   'issue': False, 'seen': True})
        return answer

    # ------------------------------------------------------------ hooks
    def write(self, vals):
        state = vals.get('state')
        Line = self.env['pb.loan.repayment'].sudo()
        if state == 'cancel':
            Line._slips_gone(self, _("payslip cancelled."))
        undone = self.env['hr.payslip']
        if state and state not in DONE_SLIP_STATES and state != 'cancel':
            undone = self.filtered(lambda s: s.state in DONE_SLIP_STATES)
        result = super().write(vals)
        if state in DONE_SLIP_STATES:
            Line._slips_done(self)
        elif undone:
            Line._slips_undone(undone)
        return result

    def unlink(self):
        self.env['pb.loan.repayment'].sudo()._slips_gone(self, _("payslip deleted."))
        return super().unlink()


class HrPayslipRunLoans(models.Model):
    _inherit = 'hr.payslip.run'

    def unlink(self):
        self.env['pb.loan.repayment'].sudo()._slips_gone(
            self.mapped('slip_ids'), _("pay run deleted."))
        return super().unlink()


# =====================================================================
# Seam 2 — a pay run with a pay data file
# =====================================================================
class PayrollImportBatchLoans(models.Model):
    _inherit = 'hr.payroll.import.batch'

    def _transform_data_to_formula_inputs(self, raw_data, contract=None, employee=None,
                                          provenance=None, topup_data=None):
        person = employee or (contract.employee_id if contract else None)
        config = self.formula_config_id
        ctx = self.env.context
        used = used_of(self.env)
        plan = None
        if person and config and len(self) == 1 and self.date_to:
            try:
                plan = self.env['pb.loan']._plan_for_slip(
                    person, config, self.date_from, self.date_to,
                    ctx.get('pb_loans_slip_id') or None, self.payslip_run_id,
                    lock=used is not None)
            except Exception:   # noqa: BLE001 — R4
                _logger.exception('pb_loans: the loan plan failed in batch %s', self.id)
                if used is not None:
                    used.update({'issue': 'error', 'seen': True, 'lines': {}})
                plan = None
        if plan is None:
            if used is not None and not used.get('seen'):
                used.update({'issue': False, 'seen': True, 'lines': {}})
            return super()._transform_data_to_formula_inputs(
                raw_data, contract=contract, employee=employee,
                provenance=provenance, topup_data=topup_data)
        prov = provenance if provenance is not None else {}
        values = super()._transform_data_to_formula_inputs(
            raw_data, contract=contract, employee=employee, provenance=prov,
            topup_data=topup_data)

        def carried(code, entry, other):
            """Did the pay data file (or another source) really carry a
            non-zero AMOUNT for the loan pay item? A monthly-template file
            writes 0 in every cell nobody filled (UPDATES G33): a 0 is a
            blank here."""
            src = entry.get('src') or 'none'
            if src == 'none' or entry.get('via') == LOANS_VIA:
                return False
            number = _number(other)
            if number is None or number == 0:
                return False
            if src in FILE_SOURCES and hasattr(self, '_file_cell_is_amount'):
                try:
                    return bool(self._file_cell_is_amount(entry.get('key'), raw_data,
                                                          topup_data))
                except Exception:   # noqa: BLE001
                    return True
            return True

        self.env['pb.loan']._merge(plan, values, prov, used, carried=carried)
        return values

    def _create_payslip(self, employee, contract, line):
        token = used_start(self.env)
        try:
            payslip = super(PayrollImportBatchLoans, self.with_context(
                pb_loans_token=token, pb_loans_slip_id=False)
            )._create_payslip(employee, contract, line)
        except Exception:
            used_end(self.env, token)
            raise
        used = used_end(self.env, token)
        if payslip:
            self.env['pb.loan.repayment'].sudo()._sync_slip(
                payslip.with_env(self.env), used)
        return payslip
