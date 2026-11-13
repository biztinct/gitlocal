# -*- coding: utf-8 -*-
"""UPDATES P2c — what a pay run's preparation says about scheduled changes.

The pay run reads a contract's CURRENT values (ledger U14). A change that is
scheduled for a day inside the run's pay period has not been written yet, so
it is not in the run — and the person preparing the run should know that,
once, in a sentence, without it ever blocking them.

Rules (handover §4.4):
  * scheduled, starting on or before the period's last day, touching somebody
    in the run → one line per start date, never a blocker;
  * starting after the period → not mentioned;
  * cancelled → never mentioned;
  * waiting for approval → exactly as before (this file does not touch it).

This lives in `pb_records` (which owns the scheduled state and already depends
on `pb_hr_payroll_formula`), as an extension of the preparation model, so the
large payroll-formula module needs no upgrade for a notice.

It also words one existing blocker honestly: a preparation edit whose record
proposal was CANCELLED was still described as "waiting for approval". The
blocker itself is unchanged (the edit still cannot feed the run); only its
sentence says what really happened.
"""
import logging

from odoo import _, models
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class PayrollPreparationScheduled(models.Model):
    _inherit = 'hr.payroll.preparation'

    def _records_scheduled(self):
        """`[{date, count, people, message}]` — one line per start date."""
        self.ensure_one()
        people = set(self.employee_ids.ids)
        if not people or not self.date_to:
            return []
        applies = self.env['pb.records.apply'].sudo().search([
            ('state', '=', 'scheduled'), ('applied', '=', False),
            ('start_date', '!=', False), ('start_date', '<=', self.date_to),
        ], order='start_date, id')
        by_date = {}
        for rec in applies:
            values, who = 0, set()
            for row in rec.plan():
                try:
                    emp_id = int(row.get('emp_id') or 0)
                except (TypeError, ValueError):
                    continue
                if emp_id in people:
                    values += 1
                    who.add(emp_id)
            if values:
                slot = by_date.setdefault(rec.start_date, [0, set()])
                slot[0] += values
                slot[1] |= who
        out = []
        for day in sorted(by_date):
            values, who = by_date[day]
            when = format_date(self.env, day)
            if self.date_from and day < self.date_from:
                message = _(
                    "1 scheduled change was due on %(date)s and has not been "
                    "written yet. It is not in this pay run unless you start it "
                    "now.", date=when) if values == 1 else _(
                    "%(n)s scheduled changes were due on %(date)s and have not "
                    "been written yet. They are not in this pay run unless you "
                    "start them now.", n=values, date=when)
            else:
                message = _(
                    "1 scheduled change starts on %(date)s, inside this pay "
                    "period. It is not in this pay run unless you start it "
                    "now.", date=when) if values == 1 else _(
                    "%(n)s scheduled changes start on %(date)s, inside this pay "
                    "period. They are not in this pay run unless you start them "
                    "now.", n=values, date=when)
            out.append({'date': str(day), 'count': values, 'people': len(who),
                        'message': message})
        return out

    def _workspace(self):
        answer = super()._workspace()
        try:
            answer['scheduled_changes'] = self._records_scheduled()
        except Exception:   # noqa: BLE001 — a notice must never break the worksheet
            _logger.exception('pb_records: scheduled-change notice failed for '
                              'preparation %s', self.id)
            answer['scheduled_changes'] = []
        return answer

    def _apply_row(self, row, edits, strict=False):
        prefix = '%s:' % row.get('employee_id')
        mine = {key: edit.get('proposal_id') for key, edit in edits.items()
                if key.startswith(prefix) and edit.get('proposal_id')}
        row = super()._apply_row(row, edits, strict=strict)
        if not mine:
            return row
        cancelled_ids = set(self.env['pb.records.apply'].sudo().browse(
            sorted(set(mine.values()))).exists().filtered(
                lambda a: a.state == 'cancelled').ids)
        codes = {key.split(':', 1)[1] for key, pid in mine.items()
                 if pid in cancelled_ids}
        if not codes:
            return row
        why = _("The saved record change was cancelled. Restore the source "
                "value, or enter the correction again.")
        for cell in row.get('inputs') or []:
            if cell.get('code') in codes and cell.get('status') == 'conflict':
                cell['reason'] = why
        for blocker in row.get('blockers') or []:
            if blocker.get('code') in codes:
                blocker['reason'] = why
        return row
