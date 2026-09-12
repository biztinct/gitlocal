# -*- coding: utf-8 -*-
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)

# The stages the board draws and the words for them — imported rather than
# re-typed, so the board can never offer a stage the model does not have.
from .hr_payslip_run import PB_BOARD_STATES, PB_STAGE_NAME

STAGE_ORDER = list(PB_BOARD_STATES)
STAGE_LABEL = dict(PB_STAGE_NAME)
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

        # WHO MAY DO WHAT IS NO LONGER A GROUP QUESTION. A pay run is signed
        # off by whoever the published route resolves to, so the board asks the
        # engine which runs are waiting on THIS person rather than deciding it
        # from a role. Submitting and rejecting are ordinary edits of the run,
        # so they follow the run's own write access.
        may_write = self._safe(lambda: Run.has_access('write'), default=False)
        awaiting = self._safe(lambda: Run._pb_runs_awaiting(self.env.uid),
                              default=set())

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
            waiting_on_me = run.id in awaiting
            if state == 'draft':
                next_action, can_act = 'submit', may_write
            elif state == 'approval_pending':
                next_action, can_act = 'decide', waiting_on_me
            else:
                next_action, can_act = '', False
            if waiting_on_me:
                my_pending += 1

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
                'can_reject': may_write and state in ('draft',
                                                      'approval_pending'),
                'awaiting_me': waiting_on_me,
                # The route this run is on, and where it has got to — read off
                # the request rather than off a state name, because "who is it
                # with" is now a person, not a tier.
                'approval': self._approval_chip(run),
                # why this run came back, if an approver sent it back
                'return_note': run.pb_return_note or '',
                'return_by': run.pb_return_uid.name or '',
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

        drawn = [s for s in STAGE_ORDER]
        columns = [{'key': s, 'label': STAGE_LABEL[s], 'count': stage_counts.get(s, 0)}
                   for s in drawn]

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
            'can_submit': may_write,
            'columns': columns,
            'batches': batches,
            'rejected_count': stage_counts.get('cancel', 0),
            'kpis': {
                'total': len(batches),
                'done': stage_counts.get('done', 0),
                'in_pipeline': stage_counts.get('draft', 0)
                + stage_counts.get('approval_pending', 0),
                'my_pending': my_pending,
                'period_net': period_net,
            },
        }

    # ---------------- helpers ----------------
    @api.model
    def _approval_chip(self, run):
        """Which route this run is on and who it is waiting for, in words."""
        request = self._safe(lambda: run.approval_request_id, default=None)
        if not request:
            return {}
        step = None
        if request.current_step_key:
            step = request.step_ids.filtered(
                lambda s: s.key == request.current_step_key)[:1]
        return {
            'request_id': request.id,
            'state': request.state,
            'workflow': request.version_id.workflow_id.name or '',
            'step': (step.title if step else ''),
            'with': ', '.join(sorted(set(
                step.seat_ids.filtered(lambda s: s.status == 'open')
                .mapped('acting_user_id.name')))) if step else '',
            'blocked': request.block_reason or '',
        }

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
