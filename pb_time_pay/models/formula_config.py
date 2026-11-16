# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Application-data mode: the typed sources and the time-off take-back.

Application-data runs read overtime from `_application_time_values` (approved
weeks or approved requests) rather than from the payslip rung, so time off in
lieu is taken back there as well — from the facts, by the request ids each
fact already lists as its sources, so exactly what was counted is what comes
off. An evidence key `time_off_in_lieu_hours` is added ONLY to a fact that
actually changed (W2A-2: the snapshot fingerprint moves only where there is
new data).

Late and early minutes are two typed sources, ``time.late_minutes`` and
``time.early_minutes``. They answer the confirmed minutes of the period that
are free or already held by the payslip being worked out, list the rows in
their evidence, and the payslip holds them when it resolves its inputs
(`hr_payslip._application_resolve_inputs`) — the period-input pattern of PR-B
(ledger PRB-W2: never `consumption_required`, which can never be lifted).
"""

import logging
from collections import defaultdict

from odoo import fields, models

from .time_pay import LATE_SOURCE_KEYS

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.pb_hr_payroll_formula.models.application_domain_sources import (
        source_result)
except Exception:  # pragma: no cover — the engine is a dependency
    source_result = None


class HrFormulaConfigTimePay(models.Model):
    _inherit = 'hr.formula.config'

    def _application_source_catalogue(self):
        result = dict(super()._application_source_catalogue())
        result['time.late_minutes'] = {
            'label': 'Confirmed late minutes', 'unit': 'minutes',
            'model': 'pb.time.late', 'writable': False, 'available': True,
            'cardinality': 'many'}
        result['time.early_minutes'] = {
            'label': 'Confirmed early-leave minutes', 'unit': 'minutes',
            'model': 'pb.time.late', 'writable': False, 'available': True,
            'cardinality': 'many'}
        return result

    def _application_domain_values(self, employee, contract, date_from,
                                   date_to):
        result = dict(super()._application_domain_values(
            employee, contract, date_from, date_to))
        self.ensure_one()
        keys = {(r.application_source_key or '').strip()
                for r in self.sudo().rule_ids
                if r.column_type == 'input'} & set(LATE_SOURCE_KEYS)
        if not keys or source_result is None:
            return result
        try:
            result.update(self._pb_tp_late_facts(employee, date_from, date_to,
                                                 keys))
        except Exception:                                   # noqa: BLE001
            _logger.exception('pb_time_pay: late minutes source failed for %s',
                              employee.id)
            for key in keys:
                result[key] = source_result(
                    status='conflict',
                    reason='Confirmed late minutes could not be read.')
        return result

    def _pb_tp_late_facts(self, employee, date_from, date_to, keys):
        ctx = self.env.context
        run_id = ctx.get('pb_application_run_id') or ctx.get('application_run_id')
        slip_id = ctx.get('pb_application_payslip_id') \
            or ctx.get('application_payslip_id')
        run = self.env['hr.payslip.run'].sudo().browse(run_id or 0).exists()
        kind = getattr(run, 'pb_run_kind', False) if run else False
        out = {}
        if (kind or 'regular') != 'regular':
            for key in keys:
                out[key] = source_result(
                    0.0, 'resolved', [],
                    reason='Late minutes are taken in the regular pay run only.')
            return out
        Late = self.env['pb.time.late'].sudo()
        domain = [('employee_id', '=', employee.id),
                  ('state', '=', 'confirmed'),
                  ('date', '>=', fields.Date.to_date(date_from)),
                  ('date', '<=', fields.Date.to_date(date_to)),
                  '|', '|', ('payslip_id', '=', False),
                  ('payslip_id.state', '=', 'cancel'),
                  ('payslip_id', '=', int(slip_id or 0))]
        rows = Late.search(domain, order='date, id')
        for key in keys:
            mine = rows.filtered(lambda r, k=LATE_SOURCE_KEYS[key]: r.kind == k)
            out[key] = source_result(
                float(sum(mine.mapped('minutes'))), 'resolved', mine,
                paid_once='pb_time_pay', pb_late_ids=sorted(mine.ids))
        return out

    # ------------------------------------------------ time off, not paid
    def _application_time_values(self, employee, contract, start, end,
                                 certification):
        result = super()._application_time_values(
            employee, contract, start, end, certification)
        try:
            self._pb_tp_take_back_facts(result)
        except Exception:                                   # noqa: BLE001
            # A money path: never pay hours that were given as time off. If
            # the take-back cannot be worked out, the overtime facts stop the
            # run with a reason instead of paying them.
            _logger.exception('pb_time_pay: time off in lieu take-back failed')
            for key, fact in list(result.items()):
                if key.startswith('period.ot.') \
                        or key == 'period.approved_bonus_hours':
                    fact.update(status='conflict', reason=(
                        'Time off in lieu could not be taken out of the '
                        'overtime. Review the overtime before this run.'))
        return result

    def _pb_tp_take_back_facts(self, result):
        ids = set()
        for key, fact in result.items():
            if not (key.startswith('period.ot.')
                    or key == 'period.approved_bonus_hours'):
                continue
            for src in fact.get('source_ids') or []:
                if isinstance(src, (list, tuple)) and len(src) >= 2 \
                        and src[0] == 'hr.overtime.request':
                    ids.add(int(src[1]))
        if not ids:
            return
        requests = self.env['hr.overtime.request'].sudo().browse(
            sorted(ids)).exists()
        time_off = requests.filtered(
            lambda r: r.state == 'approved' and r.pb_comp_choice == 'time_off')
        if not time_off:
            return
        by_kind = defaultdict(float)
        bonus = 0.0
        counted = set()
        for key, fact in result.items():
            for src in fact.get('source_ids') or []:
                if isinstance(src, (list, tuple)) and len(src) >= 2 \
                        and src[0] == 'hr.overtime.request':
                    counted.add(int(src[1]))
        for req in time_off:
            if req.id not in counted:
                continue
            by_kind[req.overtime_type] += req.approved_hours or 0.0
            bonus += req.bonus_hours or 0.0
        for kind, hours in by_kind.items():
            self._pb_tp_minus(result.get('period.ot.%s.approved_hours' % kind),
                              hours, time_off.filtered(
                                  lambda r, k=kind: r.overtime_type == k))
        self._pb_tp_minus(result.get('period.approved_bonus_hours'), bonus,
                          time_off)

    def _pb_tp_minus(self, fact, hours, requests):
        if not fact or not hours or fact.get('value') is None:
            return
        listed = {int(s[1]) for s in fact.get('source_ids') or []
                  if isinstance(s, (list, tuple)) and len(s) >= 2
                  and s[0] == 'hr.overtime.request'}
        if not listed & set(requests.ids):
            return
        try:
            current = float(fact['value'])
        except (TypeError, ValueError):
            return
        fact['value'] = round(max(0.0, current - hours), 6)
        evidence = fact.setdefault('evidence', {})
        evidence['time_off_in_lieu_hours'] = round(hours, 6)
