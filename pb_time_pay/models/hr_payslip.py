# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The payslip side of time into pay — one rung ABOVE both overtime producers.

`_get_formula_input_values` is a chain (SOURCING S1): the base fills what the
scheme knows, `pb_workforce_payroll_bridge` adds live approved overtime, and
`pb_timesheet_approval` replaces it from approved weeks. This module depends on
the second, so its override runs after both and sees what they produced.

TWO THINGS, BOTH INVISIBLE WHEN THERE IS NO NEW DATA (golden rail)
-------------------------------------------------------------------
1. TIME OFF IN LIEU IS NOT ALSO PAID. For every approved overtime request the
   manager gave as time off, exactly the hours the producer counted for it are
   taken back out of the OTHRS* / BONHRS value it produced — the producer that
   ACTUALLY answered, decided with the same tests the rungs below use (approved
   weeks when the company pays from them and a week was approved, otherwise the
   bridge when the run is one it feeds). No time-off request in the period: the
   values are returned exactly as received.
2. CONFIRMED LATE AND EARLY MINUTES. For a scheme that declares LATEMIN /
   EARLYMIN as inputs, in a payslip the bridge would feed (regular run or no
   run), the confirmed minutes of the period are fed and HELD by this payslip
   (`pb.time.late.payslip_id`) so no other payslip can pay them again. No
   confirmed minutes in the period: the value is left exactly as the rungs
   below left it.

Pay data file runs never call this method (ledger S5-1). Application-data runs
read late minutes through the typed sources in `formula_config.py`; this rung
leaves them alone there, so each mode has exactly one way in.
"""

import logging
from collections import defaultdict

from odoo import fields, models

from odoo.addons.pb_hr_payroll_formula.models import input_provenance
from odoo.addons.pb_workforce_payroll_bridge.models.hr_payslip import (
    BONUS_INPUT_CODE, OT_INPUT_MAP)

from .time_pay import (COMPUTING_STATES, LATE_INPUT_CODES, LATE_SOURCE_KEYS,
                       LATE_VIA)

_logger = logging.getLogger(__name__)

#: overtime kind -> the pay item code the producers fill for it
TYPE_TO_CODE = {kind: code for code, kind in OT_INPUT_MAP.items()}


class HrPayslipTimePay(models.Model):
    _inherit = 'hr.payslip'

    pb_late_ids = fields.One2many('pb.time.late', 'payslip_id',
                                  string='Late and early minutes taken',
                                  readonly=True)

    # =============================================================== seam 1
    def _get_formula_input_values(self, config, provenance=None):
        values = super()._get_formula_input_values(config,
                                                   provenance=provenance)
        self.ensure_one()
        input_codes = {rule.code for rule in config.rule_ids
                       if rule.column_type == 'input'}
        ot_codes = input_codes & (set(OT_INPUT_MAP) | {BONUS_INPUT_CODE})
        if ot_codes:
            self._pb_tp_take_back(values, ot_codes)
        if self.env.context.get('pb_application_data_mode') \
                or self._pb_tp_application():
            return values
        late_codes = input_codes & set(LATE_INPUT_CODES)
        if late_codes or (self.id and self.pb_late_ids):
            self._pb_tp_late(values, late_codes, provenance)
        return values

    def _pb_tp_application(self):
        try:
            return bool(self.id) and self._application_mode()
        except Exception:                                   # noqa: BLE001
            return False

    # ------------------------------------------------ time off, not paid
    def _pb_tp_take_back(self, values, codes):
        employee = self.employee_id
        if not (employee and self.date_from and self.date_to):
            return
        company = self.company_id or self.env.company
        Req = self.env['hr.overtime.request'].sudo()
        minus = defaultdict(float)
        packets = None
        if getattr(company, 'pb_timesheet_payroll', False):
            packets = self.env['pb.timesheet.packet'].approved_in_period(
                employee.id, self.date_from, self.date_to)
        if packets:
            rows = []
            for packet in packets:
                for day in packet.days():
                    for ot_type, row in (day.get('ot') or {}).items():
                        if row.get('id'):
                            rows.append((ot_type, row))
            if not rows:
                return
            requests = Req.browse(sorted({r['id'] for _t, r in rows})).exists()
            time_off = {r.id for r in requests
                        if r.state == 'approved'
                        and r.pb_comp_choice == 'time_off'}
            if not time_off:
                return
            for ot_type, row in rows:
                if row['id'] not in time_off:
                    continue
                code = TYPE_TO_CODE.get(ot_type)
                if code in codes:
                    minus[code] += float(row.get('hours') or 0.0)
                if BONUS_INPUT_CODE in codes:
                    minus[BONUS_INPUT_CODE] += float(row.get('bonus') or 0.0)
        elif self._pb_ot_bridge_feeds():
            requests = Req.search([
                ('employee_id', '=', employee.id),
                ('date', '>=', self.date_from), ('date', '<=', self.date_to),
                ('state', '=', 'approved'),
                ('pb_comp_choice', '=', 'time_off'),
            ])
            for req in requests:
                code = TYPE_TO_CODE.get(req.overtime_type)
                if code in codes:
                    minus[code] += req.approved_hours or 0.0
                if BONUS_INPUT_CODE in codes:
                    minus[BONUS_INPUT_CODE] += req.bonus_hours or 0.0
        for code, hours in minus.items():
            if hours and code in values:
                try:
                    current = float(values[code] or 0.0)
                except (TypeError, ValueError):
                    continue
                values[code] = round(max(0.0, current - hours), 6)

    # ------------------------------------------------- confirmed minutes
    def _pb_tp_late_rows(self, kinds):
        """The confirmed rows this payslip may take: free ones, ones it
        already holds, ones a cancelled payslip let go of. A finished payslip
        only ever reads what it holds."""
        Late = self.env['pb.time.late'].sudo()
        if not self.employee_id or not kinds:
            return Late
        domain = [('employee_id', '=', self.employee_id.id),
                  ('state', '=', 'confirmed'),
                  ('kind', 'in', list(kinds)),
                  ('date', '>=', self.date_from),
                  ('date', '<=', self.date_to)]
        if self.id and self.state not in COMPUTING_STATES:
            return Late.search(domain + [('payslip_id', '=', self.id)])
        holder = [('payslip_id', '=', False),
                  ('payslip_id.state', '=', 'cancel')]
        if self.id:
            holder = ['|', ('payslip_id', '=', self.id)] + ['|'] + holder
        else:
            holder = ['|'] + holder
        return Late.search(domain + holder, order='date, id')

    def _pb_tp_late(self, values, codes, provenance):
        kinds = {LATE_INPUT_CODES[c] for c in codes}
        feeds = self._pb_ot_bridge_feeds()
        rows = self._pb_tp_late_rows(kinds) if feeds else \
            self.env['pb.time.late'].sudo()
        rows = self._pb_tp_hold(rows)
        for code in codes:
            mine = rows.filtered(lambda r, k=LATE_INPUT_CODES[code]:
                                 r.kind == k)
            if not mine:
                continue
            values[code] = float(sum(mine.mapped('minutes')))
            if provenance is not None:
                provenance[code] = input_provenance.entry(
                    'employee_field',
                    key='%s confirmed day(s)' % len(mine), via=LATE_VIA)

    def _pb_tp_hold(self, rows):
        """Take ``rows`` for this payslip and let go of any it holds that it
        no longer takes. Only a payslip still being worked out writes; the
        rows are locked first so two payslips can never both take one.
        Returns the rows this payslip ends up with."""
        Late = self.env['pb.time.late'].sudo()
        if not self.id or self.state not in COMPUTING_STATES:
            return rows
        if rows:
            self.env.cr.execute(
                'SELECT id FROM pb_time_late WHERE id IN %s FOR UPDATE',
                [tuple(rows.ids)])
            rows.invalidate_recordset(['payslip_id'])
            rows = rows.filtered(
                lambda r: not r.payslip_id or r.payslip_id.id == self.id
                or r.payslip_id.state == 'cancel')
        held = Late.search([('payslip_id', '=', self.id)])
        gone = held - rows
        if gone:
            gone.write({'payslip_id': False})
        take = rows.filtered(lambda r: r.payslip_id.id != self.id)
        if take:
            take.write({'payslip_id': self.id})
        return rows

    # ======================================================== application
    def _application_resolve_inputs(self, config):
        answer = super()._application_resolve_inputs(config)
        try:
            _values, sources = answer
        except (TypeError, ValueError):
            return answer
        ids = set()
        for entry in (sources or {}).values():
            if isinstance(entry, dict) and entry.get('key') in LATE_SOURCE_KEYS:
                for rid in (entry.get('evidence') or {}).get('pb_late_ids') or []:
                    ids.add(int(rid))
        if ids or self.pb_late_ids:
            rows = self.env['pb.time.late'].sudo().browse(sorted(ids)).exists()
            self._pb_tp_hold(rows)
        return answer
