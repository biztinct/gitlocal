# -*- coding: utf-8 -*-
"""Fact-staleness hook on the pay run (Phase N), and the "after each pay run"
mark for regular Explorer sends (WDGAP QF2 C6).

Hooked on ``write()``, deliberately NOT only on the approval actions. The demo
world advances runs with a raw ``run.write({'state': ...})`` under sudo
(``pb_demo/models/demo_history.py:175``), which never passes through
``action_payslip_run_level2_done`` — an action-level hook would simply never
fire there, and the facts would go quietly stale on the exact database used for
every demo.

The flag is an OPTIMISATION, not the correctness guarantee: ``ensure_fresh()``
compares the source fingerprint on every read regardless of it, so facts stay
correct even if this hook is bypassed entirely.

The QF2 mark is on BOTH paths: ``_approval_apply`` (cloned from
``pb_pay_delivery/models/payroll_journal.py:380-402`` — super through
``getattr``, our own work in a savepoint and a try, so an approval is NEVER
blocked or undone) and ``write(state='done')`` (the demo path). Marking twice is
harmless: it only sets "due now". The cron sends.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)

# State changes move a run between approved and provisional; everything else
# about a run (name, dates) is denormalised onto the header too.
_FACT_FIELDS = {'state', 'name', 'date_start', 'date_end'}


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    def write(self, vals):
        res = super().write(vals)
        if self.ids and _FACT_FIELDS.intersection(vals or {}):
            # sudo: marking a derived row dirty is bookkeeping, not a grant —
            # the reader still has to pass the Explorer gate to see anything.
            self.env['pb.fact.run'].sudo().search(
                [('run_id', 'in', self.ids)]).write({'dirty': True})
        if self.ids and (vals or {}).get('state') == 'done':
            self._pbx_mark_schedules_due()
        return res

    def _approval_apply(self, request):
        parent = getattr(super(), '_approval_apply', None)
        result = parent(request) if parent else True
        self._pbx_mark_schedules_due()
        return result

    def _pbx_mark_schedules_due(self):
        """Finished runs make their companies' after-each-run schedules due.
        Never raises: a regular email is never worth an approval."""
        runs = self.filtered(lambda r: r.id)
        if not runs:
            return
        try:
            with self.env.cr.savepoint():
                # hr.payslip.run has NO company_id here (C18.43): the
                # companies are the payslips'.
                self.env['hr.payslip'].flush_model(
                    ['payslip_run_id', 'company_id'])
                self.env.cr.execute(
                    "SELECT DISTINCT company_id FROM hr_payslip "
                    "WHERE payslip_run_id IN %s AND company_id IS NOT NULL",
                    (tuple(runs.ids),))
                companies = [row[0] for row in self.env.cr.fetchall()]
                if not companies:
                    companies = [self.env.company.id]
                self.env['pb.explorer.schedule'].sudo()._mark_due_after_run(
                    companies)
        except Exception:   # noqa: BLE001 — the pay run is already approved
            _logger.exception('pb_explorer: regular sends after run(s) %s '
                              'could not be marked', runs.ids)

    def unlink(self):
        # ondelete='cascade' on pb.fact.run.run_id handles the rows; this keeps
        # the ORM cache honest when a run is deleted mid-session.
        self.env['pb.fact.run'].sudo().search(
            [('run_id', 'in', self.ids)]).unlink()
        return super().unlink()
