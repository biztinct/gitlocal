# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# Approval pipeline — ordered stages + display labels (Phase L: 3 tiers).
STAGE_ORDER = ['draft', 'level0', 'level1', 'level2', 'done']
STAGE_LABEL = {
    'draft': 'Draft', 'level0': 'Officer review', 'level1': 'HR review',
    'level2': 'Finance approval', 'done': 'Done', 'cancel': 'Rejected',
}
BOARD_LIMIT = 60

# Where a refused run goes back to — mirrors PB_SEND_BACK on hr.payslip.run.
# Imported rather than re-typed so the board can never offer a send-back the
# model would not perform.
try:
    from .hr_payslip_run import PB_SEND_BACK
except ImportError:  # pragma: no cover - defensive, same package
    PB_SEND_BACK = {'level0': 'draft', 'level1': 'level0',
                    'level2': 'level1', 'done': 'level2'}


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

        # GROUP P3 — the board used to list EVERY pay run on the database.
        # `hr.payslip.run` has no `company_id` of its own, so nothing scoped
        # it: on a group, one company's board showed another company's runs
        # and priced them all in the active company's money. A run belongs to
        # the company that its payslips belong to (and, since P2, to the
        # company of the scheme it was run for), so that is what scopes it.
        runs = self._safe(
            lambda: Run.search([], order='date_end desc, id desc',
                               limit=BOARD_LIMIT * 4),
            default=Run.browse())
        owner = self._run_companies(runs)
        allowed = set(self.env.companies.ids or [company.id])
        runs = runs.filtered(
            lambda r: owner.get(r.id, company.id) in allowed)[:BOARD_LIMIT]
        currency_of = self._currency_by_company()

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
            elif state == 'level0':
                next_action, can_act = 'approve_officer', has_officer
            elif state == 'level1':
                next_action, can_act = 'approve_hr', has_manager
            elif state == 'level2':
                next_action, can_act = 'approve_gm', has_final
            if can_act and state in ('level0', 'level1', 'level2'):
                my_pending += 1

            # Send back one stage. Offered to the tier that holds the run — the
            # same people who may reject it, minus draft (nothing before it).
            # On a finished run this is the final approver's undo, and the model
            # is asked whether it is still allowed (payslips already emailed
            # close the door) rather than the board guessing.
            can_send_back = can_act and state in ('level0', 'level1', 'level2')
            if state == 'done':
                can_send_back = has_final and self._safe(
                    lambda r=run: bool(r.pb_can_undo_approval), default=False)
            back_to = PB_SEND_BACK.get(state, '')

            net = self._safe(lambda r=run: r.pb_total_net)
            run_company = owner.get(run.id, company.id)
            run_currency = currency_of.get(run_company) or {
                'name': cur.name or '', 'symbol': cur.symbol or ''}
            if state == 'done' and run_currency['name'] == (cur.name or ''):
                # Only ever add up money of the SAME kind. A cross-currency
                # total is not a rounding problem, it is a wrong number.
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
                'can_send_back': can_send_back,
                'send_back_to': back_to,
                'send_back_label': STAGE_LABEL.get(back_to, ''),
                # why this run is sitting where it is, if somebody sent it back
                'sendback_note': run.pb_sendback_note or '',
                'sendback_by': run.pb_sendback_uid.name or '',
                'sendback_from_label': STAGE_LABEL.get(run.pb_sendback_from or '', ''),
                'journal': self._journal_name(run),
                # The division key the board's chips filter on. It has always
                # been sent as the CHIP LIST ('divisions' below) with nothing on
                # the cards to match it against, so the board could offer a
                # filter it could not apply. The kanban filtered server-side on
                # the same stored field, which is why only the board was poorer.
                'division': run.pb_division or '',
                'division_label': run.pb_division_label or '',
                # Each run priced in ITS OWN company's money.
                'company_id': run_company,
                'currency': run_currency['symbol'],
                'currency_name': run_currency['name'],
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

        currencies = sorted({b['currency_name'] for b in batches if
                             b.get('currency_name')})
        return {
            'currency': cur.symbol or '',
            'currency_name': cur.name or '',
            # More than one money on the board is worth SAYING: the stage
            # total below only ever adds up the active company's own runs.
            'many_currencies': len(currencies) > 1,
            'currencies': currencies,
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
                'in_pipeline': stage_counts.get('draft', 0) + stage_counts.get('level0', 0)
                + stage_counts.get('level1', 0) + stage_counts.get('level2', 0),
                'my_pending': my_pending,
                'period_net': period_net,
            },
        }

    # ---------------- helpers ----------------
    @api.model
    def _run_companies(self, runs):
        """{run id: company id} — the entity a pay run actually happened in.

        `hr.payslip.run` carries no company of its own on this build. Its
        payslips do, and since GROUP P2 so does the scheme it was run for, so
        the answer is read from those in ONE indexed query rather than guessed
        from whichever company the reader is looking at.
        """
        if not runs:
            return {}
        out = {}
        Run = self.env['hr.payslip.run']
        if 'pb_formula_config_id' in Run._fields:
            for run in runs:
                config = run.pb_formula_config_id
                if config and config.company_id:
                    out[run.id] = config.company_id.id
        self.env.cr.execute(
            "SELECT payslip_run_id, MIN(company_id) FROM hr_payslip "
            "WHERE payslip_run_id IN %s AND state != 'cancel' GROUP BY 1",
            (tuple(runs.ids),))
        for run_id, company_id in self.env.cr.fetchall():
            if company_id:
                out[run_id] = company_id      # payslip truth wins
        return out

    @api.model
    def _currency_by_company(self):
        rows = self.env['res.company'].sudo().with_context(
            active_test=False).search_read([], ['currency_id'])
        currencies = self.env['res.currency'].sudo().with_context(
            active_test=False).browse(
            [r['currency_id'][0] for r in rows if r['currency_id']]).exists()
        by_id = {c.id: {'name': c.name, 'symbol': c.symbol or c.name}
                 for c in currencies}
        return {r['id']: by_id.get(r['currency_id'][0])
                for r in rows if r['currency_id']}

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
