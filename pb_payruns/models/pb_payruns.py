# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Approval pipeline — ordered stages + display labels.
STAGE_ORDER = ['draft', 'level1', 'level2', 'done']
STAGE_LABEL = {
    'draft': 'Draft', 'level1': 'HR review', 'level2': 'GM review',
    'done': 'Done', 'cancel': 'Rejected',
}
BOARD_LIMIT = 60


class PbPayruns(models.AbstractModel):
    _name = 'pb.payruns'
    _description = 'Payobook Pay Runs board data'

    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug("Pay Runs board metric failed: %s", e)
            return default

    @api.model
    def get_board_data(self):
        company = self.env.company
        cur = company.currency_id
        Run = self.env['hr.payslip.run']
        user = self.env.user

        # Demo users drive the full approval workflow (showcase) — see note in
        # hr.payslip.run._pb_user_roles. They keep the upsell sidebar locks.
        try:
            is_demo_role = user.has_group('pb_demo.group_payobook_demo')
        except Exception:
            is_demo_role = False
        has_officer = is_demo_role \
            or user.has_group('pb_hr_payroll_base.group_payroll_base_officer') \
            or user.has_group('pb_hr_payroll_base.group_payroll_base_manager')
        has_manager = is_demo_role \
            or user.has_group('pb_hr_payroll_base.group_payroll_base_manager')
        has_final = is_demo_role \
            or user.has_group('pb_hr_payroll_base.group_payroll_final_approver') \
            or user.has_group('pb_hr_payroll_base.group_payroll_super_admin')

        runs = self._safe(
            lambda: Run.search([], order='date_end desc, id desc', limit=BOARD_LIMIT),
            default=Run.browse())

        # Batch-compute all run totals in ONE pass (single SQL) instead of letting
        # each per-run field access trigger its own aggregation.
        self._safe(lambda: runs.mapped('pb_total_net'))

        batches = []
        stage_counts = {s: 0 for s in STAGE_ORDER}
        stage_counts['cancel'] = 0
        my_pending = 0
        period_net = 0.0

        for run in runs:
            state = run.state or 'draft'
            stage_counts[state] = stage_counts.get(state, 0) + 1
            # context-aware next action + permission
            next_action = ''
            can_act = False
            if state == 'draft':
                next_action, can_act = 'submit', has_officer
            elif state == 'level1':
                next_action, can_act = 'approve_hr', has_manager
            elif state == 'level2':
                next_action, can_act = 'approve_gm', has_final
            if can_act and state in ('level1', 'level2'):
                my_pending += 1

            net = self._safe(lambda r=run: r.pb_total_net)
            if state == 'done':
                period_net += net or 0.0

            batches.append({
                'id': run.id,
                'name': run.name or '—',
                'state': state,
                'stage_label': STAGE_LABEL.get(state, state),
                'date_start': str(run.date_start or ''),
                'date_end': str(run.date_end or ''),
                'period': self._fmt_period(run.date_start, run.date_end),
                'employees': self._safe(lambda r=run: r.pb_employee_count),
                'net': net or 0.0,
                'gross': self._safe(lambda r=run: r.pb_total_gross) or 0.0,
                'deductions': self._safe(lambda r=run: r.pb_total_deductions) or 0.0,
                'credit_note': bool(run.credit_note),
                'next_action': next_action,
                'can_act': can_act,
                'journal': self._journal_name(run),
            })

        columns = [{'key': s, 'label': STAGE_LABEL[s], 'count': stage_counts.get(s, 0)}
                   for s in STAGE_ORDER]

        # Division filter chips — derived from the formula configs that carry a
        # division (the demo's 6; empty for plain structure-based payroll).
        divisions = []
        try:
            seen = {}
            for c in self.env['hr.formula.config'].sudo().search([]):
                d = getattr(c, 'pb_division', '')
                if d and d not in seen:
                    nm = (c.name or '').replace('Payobook', '').split('—')[0].strip()
                    seen[d] = nm or d.replace('_', ' ').title()
            divisions = [{'key': k, 'label': v}
                         for k, v in sorted(seen.items(), key=lambda x: x[1])]
        except Exception:
            divisions = []

        # Demo users get the board pre-filtered to the live demo month (June 2026).
        is_demo_user = False
        try:
            is_demo_user = user.has_group('pb_demo.group_payobook_demo')
        except Exception:
            is_demo_user = False
        demo_period = {'from': '2026-06-01', 'to': '2026-06-30'} if is_demo_user else None

        return {
            'currency': cur.symbol or '',
            'company': company.name,
            'divisions': divisions,
            'is_demo_user': is_demo_user,
            'demo_period': demo_period,
            'can_officer': has_officer,
            'can_manager': has_manager,
            'can_final': has_final,
            'columns': columns,
            'batches': batches,
            'rejected_count': stage_counts.get('cancel', 0),
            'kpis': {
                'total': len(batches),
                'done': stage_counts.get('done', 0),
                'in_pipeline': stage_counts.get('draft', 0) + stage_counts.get('level1', 0)
                + stage_counts.get('level2', 0),
                'my_pending': my_pending,
                'period_net': period_net,
            },
        }

    # ---------------- helpers ----------------
    @api.model
    def _fmt_period(self, d1, d2):
        if not d1 and not d2:
            return ''
        try:
            a = d1.strftime('%d %b') if d1 else '?'
            b = d2.strftime('%d %b %Y') if d2 else '?'
            return '%s – %s' % (a, b)
        except Exception:
            return '%s – %s' % (d1 or '?', d2 or '?')

    @api.model
    def _journal_name(self, run):
        try:
            j = getattr(run, 'journal_id', False)
            return j.name if j else ''
        except Exception:
            return ''
