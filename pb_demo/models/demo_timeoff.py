# -*- coding: utf-8 -*-
"""Time Off + Overtime demo enablement (Sudima Phase K §5.7) — extends
pb.demo.generator.

Seeds the Leave Command Center and Overtime Desk with a realistic story on the
demo world (all records generator-owned; cleaned by clean_demo_employees):

  * a demo Annual Leave type (requires allocation) + an Unpaid type (no
    allocation), idempotent by name;
  * a validated 12-day annual allocation and a validated 3-day taken leave for a
    few adults, so the BALANCE board shows 12 − 3 = 9;
  * pending leaves (To Approve) so the queue is non-empty, plus a validated leave
    spanning today so the heatmap and "out today" strip light up;
  * an engineered OT overflow — a submitted 6 h weekday request (daily cap 4 h →
    a 4 + 2 split preview in the queue) and an APPROVED 6 h request whose stored
    split (4 approved + 2 bonus) populates the Bonus Hours review + BONHRS.

Adults only for OT (the young-worker gate hard-blocks minors at creation).
"""

import logging
from datetime import timedelta

from odoo import fields, models

_logger = logging.getLogger(__name__)


class PbDemoGenerator(models.TransientModel):
    _inherit = 'pb.demo.generator'

    # -------------------------------------------------------------- types
    def _ensure_leave_type(self, name, requires_allocation, company):
        LT = self.env['hr.leave.type'].sudo()
        lt = LT.with_context(active_test=False).search([('name', '=', name)], limit=1)
        vals = {
            'name': name,
            'requires_allocation': requires_allocation,
            'leave_validation_type': 'hr',
            'allocation_validation_type': 'hr',
            'active': True,
        }
        if lt:
            # requires_allocation is fixed at creation: Odoo hard-blocks changing
            # it once any leave of the type has been taken (which is exactly the
            # state a re-run hits), so only refresh the safe fields on update.
            vals.pop('requires_allocation', None)
            lt.write(vals)
            return lt
        return LT.create(vals)

    def _validate_leave(self, leave):
        """Advance a leave to 'validate' via its OWN action (single-approval
        demo types) — never a direct state write."""
        for _ in range(2):
            if leave.state == 'validate':
                break
            try:
                leave.sudo().action_approve()
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo timeoff: could not validate leave: %s', e)
                break

    # -------------------------------------------------------------- entry
    def ensure_timeoff_demos(self):
        """Create/refresh the leave + OT overflow demo story. Called from
        action_generate_all after the ESS demo users are linked."""
        self = self.with_context(**self._GEN_CTX)
        Employee = self.env['hr.employee'].sudo().with_context(active_test=False)
        company = self.get_group_company()
        if not company:
            _logger.warning('pb_demo: no demo company; skipping timeoff demos')
            return
        today = fields.Date.context_today(self)

        adults = Employee.search([
            ('is_demo', '=', True), ('company_id', '=', company.id),
        ]).filtered(lambda e: 'Minor' not in (e.name or ''))
        if not adults:
            _logger.warning('pb_demo: no adult demo employees; skipping timeoff demos')
            return
        cohort = adults[:8]

        annual = self._ensure_leave_type('Demo Annual Leave', True, company)
        unpaid = self._ensure_leave_type('Demo Unpaid Leave', False, company)

        Leave = self.env['hr.leave'].sudo()
        Alloc = self.env['hr.leave.allocation'].sudo()

        # Each sub-seed is independent + defensive: a hiccup in one (e.g. a core
        # allocation/overlap refusal) must never abort the whole demo story.
        year_start = today.replace(month=1, day=1)

        # --- balance story: validated 12-day allocation + a taken leave ---
        for emp in cohort[:4]:
            try:
                with self.env.cr.savepoint():
                    alloc = Alloc.search([('employee_id', '=', emp.id),
                                          ('holiday_status_id', '=', annual.id)], limit=1)
                    if not alloc:
                        alloc = Alloc.create({
                            'name': 'Demo annual allocation',
                            'employee_id': emp.id,
                            'holiday_status_id': annual.id,
                            'number_of_days': 12.0,
                            'date_from': year_start,
                        })
                        alloc.action_approve()
                    # a validated taken leave in the recent past (weekday span)
                    start = self._recent_weekday(today - timedelta(days=20))
                    if not Leave.search_count([
                            ('employee_id', '=', emp.id),
                            ('holiday_status_id', '=', annual.id),
                            ('request_date_from', '=', start)]):
                        lv = Leave.create({
                            'employee_id': emp.id,
                            'holiday_status_id': annual.id,
                            'request_date_from': start,
                            'request_date_to': start + timedelta(days=2),
                            'name': 'Annual leave (demo)'})
                        self._validate_leave(lv)
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo timeoff: balance seed for %s skipped: %s',
                                emp.name, e)

        # --- pending queue: a couple of To-Approve unpaid leaves ---
        for emp in cohort[4:7]:
            try:
                with self.env.cr.savepoint():
                    start = self._recent_weekday(today + timedelta(days=3))
                    if not Leave.search_count([
                            ('employee_id', '=', emp.id),
                            ('holiday_status_id', '=', unpaid.id),
                            ('state', 'in', ('confirm', 'validate1'))]):
                        Leave.create({
                            'employee_id': emp.id,
                            'holiday_status_id': unpaid.id,
                            'request_date_from': start,
                            'request_date_to': start + timedelta(days=1),
                            'name': 'Personal matters (demo)'})   # → 'confirm'
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo timeoff: pending seed for %s skipped: %s',
                                emp.name, e)

        # --- out today: one validated leave spanning today ---
        out_emp = cohort[7] if len(cohort) > 7 else cohort[0]
        try:
            with self.env.cr.savepoint():
                if not Leave.search_count([
                        ('employee_id', '=', out_emp.id), ('state', '=', 'validate'),
                        ('request_date_from', '<=', today),
                        ('request_date_to', '>=', today)]):
                    lv = Leave.create({
                        'employee_id': out_emp.id,
                        'holiday_status_id': unpaid.id,
                        'request_date_from': today,
                        'request_date_to': today + timedelta(days=1),
                        'name': 'Out today (demo)'})
                    self._validate_leave(lv)
        except Exception as e:   # pragma: no cover
            _logger.warning('pb_demo timeoff: out-today seed skipped: %s', e)

        # --- OT overflow: submitted (queue split preview) + approved (bonus) ---
        try:
            with self.env.cr.savepoint():
                self._seed_ot_overflow(cohort, company, today)
        except Exception as e:   # pragma: no cover
            _logger.warning('pb_demo timeoff: OT overflow seed skipped: %s', e)

        _logger.info('pb_demo: timeoff + OT-overflow demos ready (%s adults).', len(cohort))

    def _recent_weekday(self, d):
        """Nearest date on/before a Friday for `d`'s week — keeps demo leaves on
        weekdays so validation doesn't trip weekend/holiday rules."""
        while d.weekday() >= 5:
            d = d - timedelta(days=1)
        return d

    def _seed_ot_overflow(self, cohort, company, today):
        if 'hr.overtime.request' not in self.env:
            return
        OT = self.env['hr.overtime.request'].sudo()
        # two distinct past weekdays so daily windows don't collide
        d1 = self._recent_weekday(today - timedelta(days=2))
        d2 = self._recent_weekday(d1 - timedelta(days=7))
        emp_sub = cohort[0]
        emp_app = cohort[1] if len(cohort) > 1 else cohort[0]

        # submitted 6h weekday → queue shows the live 4 + 2 split preview
        if not OT.search_count([('employee_id', '=', emp_sub.id), ('date', '=', d1),
                                ('overtime_type', '=', 'weekday')]):
            r = OT.create({
                'employee_id': emp_sub.id, 'company_id': company.id,
                'date': d1, 'overtime_type': 'weekday',
                'planned_hours': 6.0, 'actual_hours': 6.0,
                'reason': 'Month-end overflow (demo)',
            })
            r.action_submit()

        # approved 6h weekday → stored split 4 approved + 2 bonus (Bonus review)
        if not OT.search_count([('employee_id', '=', emp_app.id), ('date', '=', d2),
                                ('overtime_type', '=', 'weekday')]):
            r = OT.create({
                'employee_id': emp_app.id, 'company_id': company.id,
                'date': d2, 'overtime_type': 'weekday',
                'planned_hours': 6.0, 'actual_hours': 6.0,
                'reason': 'Approved overflow (demo)',
            })
            r.action_submit()
            try:
                r.action_approve()   # recomputes + stores the 4 + 2 split
            except Exception as e:   # pragma: no cover
                _logger.warning('pb_demo timeoff: OT approve failed: %s', e)
