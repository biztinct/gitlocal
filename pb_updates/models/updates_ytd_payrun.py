# -*- coding: utf-8 -*-
"""UPDATES P5 — how a pay run receives a year-to-date figure (handover §4.4).

ONLY where a payroll manager has mapped an input pay item of the payslip's
scheme to a figure (`pb.updates.ytd.map`), and ONLY for a person with a stored
figure for that tax year that covers a time before the payslip's period —
or (UPDATES P5d, owner decision D31) a person with no figure who joined this
tax year and whose finished payslips cover every month from the joining month
(`pb.updates.ytd.line._joiner_plan`: "paid in Payobook" alone).
Everywhere else both seams return exactly what `super()` returned, called
with the caller's own arguments (test Y9).

The same two seams as the one-off pay items (ledger U24), overridden here
OUTSIDE them (this file loads later), each calling `super()` first:

  1. `hr.payslip._get_formula_input_values` — no pay data file, native
     Compute Sheet, the no-file branch of Recalculate: the figure fills the
     item only when no other source does (`src == 'none'` or blank).
  2. `hr.payroll.import.batch._transform_data_to_formula_inputs` — a pay data
     file (and the month's workbook): when the file carries a NUMBER for the
     item (`_file_cell_is_amount`, the template's filler 0 is a blank) and it
     differs, D11 applies unchanged — the pay run stops and asks, both amounts
     shown (`pb.updates.ytd.ask`, answered by the same buttons as a one-off's
     question); equal amounts go in once.

Application-data runs: nothing here (their inputs are certified; the
year-to-date view offers "Download for the pay run" instead).

The value and its two parts are recorded in the payslip's own input sources
(`ytd`: before Payobook, paid in Payobook, the figure row), and the payslip
holds the figure (`pb.updates.ytd.use`) — locked once the payslip is finished,
let go when it is cancelled or deleted.
"""
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.pb_updates.models.updates_oneoff import (
    FILE_SOURCES, OneoffClash, _blank, _same_amount)
from odoo.addons.pb_updates.models.updates_ytd import DONE_SLIP_STATES, YTD_VIA

try:
    from odoo.addons.pb_hr_payroll_formula.models import input_provenance
except Exception:  # pragma: no cover
    input_provenance = None

_logger = logging.getLogger(__name__)


def ytd_parts(info):
    parts = {'figure': info['figure'], 'basis': info['basis'], 'before': info['before'],
             'paid': info['paid'], 'value': info['value'], 'line_id': info['line_id'],
             'covers_to': info['covers_to'], 'map_id': info['map_id']}
    # UPDATES P5c — which finished payslips "paid in Payobook" added up, and
    # the months below zero it includes (kept only when there are any, so a
    # payslip that used none of this reads exactly as before).
    if info.get('slips'):
        parts['slips'] = list(info['slips'])
    if info.get('below_zero'):
        parts['below_zero'] = list(info['below_zero'])
    if info.get('twice'):
        parts['twice'] = list(info['twice'])
    # UPDATES P5d (D31) — paid in Payobook alone for a person who joined this
    # year: no figure row, the joining date instead (kept only then).
    if info.get('joined'):
        parts['joined'] = info['joined']
    return parts


def ytd_key(info):
    """The provenance key of a value from Updates: the figure row, or
    `joined` for a person paid in Payobook alone (P5d, no figure row)."""
    return 'updates_ytd:%s' % (info['line_id'] or 'joined')


def ytd_entry(info, ignored=None):
    """The provenance entry of a value that came from a year-to-date figure."""
    out = {'src': 'employee_field', 'key': ytd_key(info),
           'via': YTD_VIA, 'ytd': ytd_parts(info)}
    if ignored:
        out['ignored'] = ignored
    return out


def _ignored(src, key, value):
    if input_provenance is not None:
        return input_provenance.ignored_side(src, key, value)
    return {'src': src, 'key': key, 'value': value}


class YtdClash(OneoffClash):
    """D11 for a year-to-date figure. A one-off's question type, so the
    one-off wrappers that already catch it (and stop that person's payslip)
    handle it unchanged; `_open_clash` files it under the right store."""
    ytd = True

    def __init__(self, employee, info, file_value, file_key, file_src, sentence):
        UserError.__init__(self, sentence)
        self.row_id = 0
        self.employee_id = employee.id
        self.code = info['code']
        self.label = info.get('item_label') or info['code']
        self.figure = info['figure']
        self.line_id = info['line_id']
        self.ours = info['value']
        self.file_value = file_value
        self.file_key = file_key
        self.file_src = file_src
        self.sentence = sentence


def _clash_sentence(env, employee, info, file_value):
    Line = env['pb.updates.ytd.line']
    cur = employee.company_id.currency_id
    return _("%(item)s for %(name)s: %(updates)s from the year-to-date figures in Updates, "
             "%(file)s in the pay data file. Choose which one to use in this pay run.",
             item=info.get('item_label') or info['code'], name=employee.name or '',
             updates=Line._value_label(info['figure'], info['value'], cur),
             file=Line._value_label(info['figure'], file_value, cur))


def _item_labels(config, plan):
    names = {r.code: r.name for r in config.sudo().rule_ids if r.code in plan}
    for code, info in plan.items():
        info['item_label'] = names.get(code) or code
    return plan


class HrPayslipUpdatesYtd(models.Model):
    _inherit = 'hr.payslip'

    # ------------------------------------------------------------ seam 1
    def _get_formula_input_values(self, config, provenance=None):
        ctx = self.env.context
        if ctx.get('pb_application_data_mode') or not self or len(self) != 1 or not config:
            return super()._get_formula_input_values(config, provenance=provenance)
        plan = self.env['pb.updates.ytd.line'].sudo()._plan_for_slip(
            self.employee_id, config, self.date_from, self.date_to)
        if not plan:
            return super()._get_formula_input_values(config, provenance=provenance)
        _item_labels(config, plan)
        prov = provenance if provenance is not None else {}
        values = super()._get_formula_input_values(config, provenance=prov)
        computing = bool(ctx.get('pb_updates_token'))
        run = self.payslip_run_id
        Ask = self.env['pb.updates.ytd.ask'].sudo()
        for code, info in plan.items():
            ask = Ask._for(run, None, self.employee_id, code) if run else Ask
            if ask and not ask.clash_choice:
                # The pay run asked which amount; it is answered with the file.
                if computing:
                    raise YtdClash(self.employee_id, info, ask.clash_file_amount,
                                   ask.clash_file_key, 'excel', ask._sentence())
                continue
            if ask and ask.clash_choice == 'file':
                continue
            entry = prov.get(code) or {}
            src = entry.get('src') or 'none'
            other = values.get(code)
            if src != 'none' and not _blank(other) and not (ask and ask.clash_choice == 'updates'):
                # Another source supplies this item: it stands (handover §4.4).
                continue
            if self.env['pb.updates.ytd.line']._plan_blocked(info):
                if computing:
                    raise UserError(self.env['pb.updates.ytd.line']._gap_sentence(
                        self.employee_id, info))
                continue
            values[code] = info['value']
            prov[code] = ytd_entry(info)
        return values

    # ------------------------------------------------------------ wrappers
    def _pb_compute_sheet_with_formulas(self):
        result = super()._pb_compute_sheet_with_formulas()
        self.env['pb.updates.ytd.use'].sudo()._sync_slips(self)
        return result

    def action_recompute_formula_lines(self):
        result = super().action_recompute_formula_lines()
        self.env['pb.updates.ytd.use'].sudo()._sync_slips(self)
        return result

    # ------------------------------------------------------------ hooks
    def write(self, vals):
        state = vals.get('state')
        Ask = self.env['pb.updates.ytd.ask'].sudo()
        if state in DONE_SLIP_STATES and self.mapped('payslip_run_id'):
            open_asks = Ask.search([('clash_run_id', 'in', self.mapped('payslip_run_id').ids),
                                    ('clash_choice', '=', False)])
            for slip in self:
                mine = open_asks.filtered(lambda a: a.clash_run_id == slip.payslip_run_id
                                          and a.employee_id == slip.employee_id)
                if mine:
                    raise UserError(_("%(sentence)s Until then this payslip cannot be finished.",
                                      sentence=mine[:1]._sentence()))
        Use = self.env['pb.updates.ytd.use'].sudo()
        if state == 'cancel':
            Use.search([('payslip_id', 'in', self.ids)]).unlink()
        result = super().write(vals)
        if state in DONE_SLIP_STATES:
            Use.search([('payslip_id', 'in', self.ids), ('state', '=', 'in_run')]).write(
                {'state': 'used'})
        return result


class HrPayslipRunYtdHooks(models.Model):
    _inherit = 'hr.payslip.run'

    def unlink(self):
        self.env['pb.updates.ytd.ask'].sudo().search([('clash_run_id', 'in', self.ids)]).unlink()
        return super().unlink()


class PayrollImportBatchUpdatesYtd(models.Model):
    _inherit = 'hr.payroll.import.batch'

    # ------------------------------------------------------------ seam 2
    def _transform_data_to_formula_inputs(self, raw_data, contract=None, employee=None,
                                          provenance=None, topup_data=None):
        person = employee or (contract.employee_id if contract else None)
        config = self.formula_config_id
        plan = {}
        if person and config and len(self) == 1 and self.date_to:
            plan = self.env['pb.updates.ytd.line'].sudo()._plan_for_slip(
                person, config, self.date_from, self.date_to)
        if not plan:
            return super()._transform_data_to_formula_inputs(
                raw_data, contract=contract, employee=employee,
                provenance=provenance, topup_data=topup_data)
        _item_labels(config, plan)
        prov = provenance if provenance is not None else {}
        values = super()._transform_data_to_formula_inputs(
            raw_data, contract=contract, employee=employee, provenance=prov,
            topup_data=topup_data)
        computing = bool(self.env.context.get('pb_updates_token'))
        Ask = self.env['pb.updates.ytd.ask'].sudo()
        rules = None
        for code, info in plan.items():
            entry = prov.get(code) or {}
            src = entry.get('src') or 'none'
            other = values.get(code)
            carried = src in FILE_SOURCES and not _blank(other) and \
                self._file_cell_is_amount(entry.get('key'), raw_data, topup_data)
            if carried and _same_amount(other, 0.0) and self._template_period():
                if rules is None:
                    rules = {r.code: r for r in config.sudo().rule_ids if r.code}
                rule = rules.get(code)
                if rule and not self._template_entered_zero(person, rule):
                    carried = False
            if not carried and src not in ('none',) + FILE_SOURCES and not _blank(other):
                # A source other than the file (a connected system, a record)
                # supplies it: it stands.
                continue
            if self.env['pb.updates.ytd.line']._plan_blocked(info):
                if not carried and computing:
                    raise UserError(self.env['pb.updates.ytd.line']._gap_sentence(person, info))
                continue
            ask = Ask._for(self.payslip_run_id, self, person, code)
            choice = ask.clash_choice if ask else False
            if not carried:
                values[code] = info['value']
                prov[code] = ytd_entry(info)
            elif _same_amount(other, info['value']):
                prov[code] = dict(entry, ytd=ytd_parts(info), agreed=True)
            elif choice == 'updates':
                values[code] = info['value']
                prov[code] = ytd_entry(info, ignored=_ignored(src, entry.get('key'), other))
            elif choice == 'file':
                prov[code] = dict(entry, ignored=_ignored(
                    'employee_field', ytd_key(info), info['value']))
            elif computing:
                # D11 — stop and ask. A review screen just sees the file's value.
                raise YtdClash(person, info, other, entry.get('key'), src,
                               _clash_sentence(self.env, person, info, other))
        return values

    # ------------------------------------------------------------ wrapper
    def _create_payslip(self, employee, contract, line):
        payslip = super()._create_payslip(employee, contract, line)
        if payslip:
            self.env['pb.updates.ytd.use'].sudo()._sync_slips(payslip)
        return payslip


class PbUpdatesOneoffYtdQuestions(models.Model):
    """One set of D11 buttons for both kinds of question. A year-to-date
    question travels with the id `y:<n>`; everything else is a one-off's."""
    _inherit = 'pb.updates.oneoff'

    @api.model
    def _open_clash(self, clash, run=None, batch=None):
        if getattr(clash, 'ytd', False):
            ask = self.env['pb.updates.ytd.ask'].sudo()._open(clash, run=run, batch=batch)
            return ask
        return super()._open_clash(clash, run=run, batch=batch)

    @api.model
    def resolve_clash(self, row_id=0, choice=''):
        text = str(row_id or '')
        if not text.startswith('y:'):
            return super().resolve_clash(row_id=row_id, choice=choice)
        if choice not in ('updates', 'file'):
            return {'ok': False, 'msg': _("Pick one of the two amounts.")}
        if not self._may_choose():
            raise AccessError(_("Choosing which amount is used needs the right to run "
                                "payroll."))
        try:
            ask_id = int(text[2:] or 0)
        except (TypeError, ValueError):
            ask_id = 0
        ask = self.env['pb.updates.ytd.ask'].sudo().search(
            [('id', '=', ask_id), ('company_id', 'in', self.env.companies.ids)], limit=1)
        if not ask or ask.clash_choice or not ask.clash_run_id:
            return {'ok': False, 'msg': _(
                "This choice has already been made, or the pay run that asked it is gone.")}
        run = ask.clash_run_id
        if run.state in ('close', 'done', 'paid', 'cancel'):
            ask.unlink()
            return {'ok': False, 'msg': _(
                "Pay run %s is already finished, so the choice cannot be used there.")
                % (run.name or '')}
        ask.write({'clash_choice': choice, 'clash_by': self.env.uid,
                   'clash_at': fields.Datetime.now()})
        slip = self._recompute_after_choice(ask)
        used = ask.updates_amount if choice == 'updates' else ask.clash_file_amount
        if slip:
            # Say what the payslip really took (a figure that can no longer be
            # worked out leaves the file's number in place).
            try:
                slip.invalidate_recordset(['formula_input_values'])
                values = json.loads(slip.formula_input_values or '{}')
                if ask.code in values and isinstance(values[ask.code], (int, float)):
                    used = values[ask.code]
            except (TypeError, ValueError):
                pass
        return {'ok': True, 'row_id': 'y:%s' % ask.id, 'choice': choice, 'state': 'chosen',
                'slip_id': slip.id if slip else 0,
                'msg': _("%(item)s for %(name)s: %(amount)s is used in pay run %(run)s.",
                         item=ask.label or ask.code, name=ask.employee_id.name or '',
                         amount=ask._amount(used), run=run.name or '')}


class PayslipRunYtdSummary(models.AbstractModel):
    """The Run Payroll review step lists the year-to-date questions with the
    one-off ones (same box, same buttons)."""
    _inherit = 'pb.payrun.wizard'

    @api.model
    def get_summary(self, run_id):
        answer = super().get_summary(run_id)
        try:
            run = self.env['hr.payslip.run'].sudo().browse(int(run_id or 0)).exists()
            if run and isinstance(answer, dict):
                asks = self.env['pb.updates.ytd.ask'].sudo().search(
                    [('clash_run_id', '=', run.id), ('clash_choice', '=', False)])
                if asks:
                    answer['oneoff_clashes'] = list(answer.get('oneoff_clashes') or []) + \
                        asks._payload()
                    answer['oneoff_can_choose'] = self.env['pb.updates.oneoff']._may_choose()
        except Exception:  # noqa: BLE001
            _logger.exception('pb_updates: the year-to-date questions failed')
        return answer
