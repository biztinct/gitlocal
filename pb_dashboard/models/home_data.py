# -*- coding: utf-8 -*-
"""HOME P1 — the new Home's one data call, `pb.dashboard.get_home_data()`.

Same AbstractModel as `pb_dashboard.py` (`_inherit`), its own file because the
payload is large. The rules that bind every line below (HOME_LEDGER H-R1..R8):

1. ONE PAY BAND. Every money figure is a sum of the stored pay run roll-ups
   (`pb_total_net / _gross / _deductions / _employer_cost`), read only after
   `'pb_total_net' in Run._fields`. The payslip LINE table is never read from
   here, not even to count — it is the twelve-second statement on payobook.
   (The absence test greps this file for its name, so this docstring does not
   spell it.)
2. NO NEW HARD DEPENDENCY. Every model another module owns is reached through
   `optional('<model>', lambda: env['<model>'], None)`, which answers None when
   the registry has no such model. The returned model object is then used
   directly, so the guard is the registry probe and `tests/test_home_data.py`
   (test 9) checks the syntax tree for it. NOTE: an empty recordset is falsy,
   so every guard result is tested with `is None`, never with `not`.
3. FACTS, NOT SENTENCES. Keys, numbers, dates and names that already exist as
   data (run names, people, division labels). The browser owns the words.
4. COMPANY SCOPE EVERYWHERE. Employees, contracts and payslips by
   `env.companies`; pay runs have no `company_id`, so a run is visible when at
   least one of its payslips is in the reader's companies — or when it has no
   payslip at all (an empty draft run, which the period tracker also counts).
5. ONE BROKEN SOURCE NEVER BLANKS HOME. Every section runs inside a savepoint
   and falls back to its empty value; every individual foreign read is wrapped
   again in `safe()`.
"""
import logging
import re
import time
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)

#: The order the "Needs you" chips are drawn in.
NEEDS_ORDER = ('runs_to_approve', 'leave_to_approve', 'other_to_approve',
               'settlements_to_check', 'renewals_to_start', 'writeups_overdue')

#: payload key -> stored roll-up on hr.payslip.run (pb_payruns).
MONEY_FIELDS = (('net', 'pb_total_net'), ('gross', 'pb_total_gross'),
                ('ded', 'pb_total_deductions'),
                ('er', 'pb_total_employer_cost'))

RENEWAL_DAYS = 30            # "contracts ending" window
INTERVIEW_DAYS = 7           # "interviews this week"
WRITEUP_LOOKBACK_DAYS = 42   # same window the hiring board scans
WRITEUP_SCAN = 500           # bounded: feedback_late is not stored
LEAVE_WEEK_SCAN = 3000       # bounded, like pb_timeoff's heatmap
UPCOMING_CAP = 6
MONTHS = 12
STEP_KEYS = ('setup', 'prepare', 'approve', 'pay', 'deliver')

#: Run state -> period stage, the pay hub's own rule (pb_payhub _RUN_STAGE);
#: used only when the hub is absent and the steps still need a stage.
_STAGE_OF_STATE = {'draft': 2, 'approval_pending': 3, 'done': 4}

#: The lunar new year, as public holidays are named on a Vietnamese calendar.
_TET = re.compile(r'\bt[eêế]t\b|lunar new year', re.IGNORECASE)


def _ms(start):
    return int(round((time.perf_counter() - start) * 1000))


def _iso(day):
    return day.isoformat() if day else None


def _initials(text, most=3):
    """'Ho Chi Minh · Sales' -> 'HCM'; 'Manufacturing' -> 'MA'."""
    words = re.findall(r'\w+', text or '')
    if not words:
        return ''
    if len(words) == 1:
        return words[0][:2].upper()
    return ''.join(w[0] for w in words[:most]).upper()


def _person_initials(name):
    """'Minh Tran' -> 'MT' (first and last word)."""
    words = re.findall(r'\w+', name or '')
    if not words:
        return ''
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


def _guards(env):
    """`safe` and `optional` for this payload.

    `safe` runs inside a savepoint: a failed statement poisons the whole
    transaction on this platform, so a swallowed error without one would make
    every later read on Home fail too.
    """
    def safe(fn, default=None):
        try:
            with env.cr.savepoint():
                return fn()
        except Exception:                               # noqa: BLE001
            _logger.debug('home_data: a read fell back', exc_info=True)
            return default

    def optional(model, fn, default=None):
        if model not in env:
            return default
        return safe(fn, default)

    return safe, optional


class PbDashboardHome(models.AbstractModel):
    _inherit = 'pb.dashboard'

    # ================================================================ the call
    @api.model
    def get_home_data(self):
        """The whole new Home in one call. No arguments: the chart carries all
        twelve months, so the browser never asks for a period."""
        started = time.perf_counter()
        env = self.env
        safe, optional = _guards(env)
        timing = {key: 0 for key in ('period', 'needs_you', 'months', 'runs',
                                     'people', 'hiring', 'learn', 'schemes')}

        def section(key, fn, default):
            t0 = time.perf_counter()
            try:
                with env.cr.savepoint():
                    out = fn()
            except AccessError:
                # A reader without rights to a source simply does not get
                # that card; this is a normal state, not a fault.
                _logger.debug('home_data: section %s not readable by uid %s',
                              key, env.uid)
                out = default
            except Exception:                           # noqa: BLE001
                _logger.warning('home_data: section %s fell back', key,
                                exc_info=True)
                out = default
            timing[key] += _ms(t0)
            return out

        today = fields.Date.context_today(self)
        st = {
            'today': today,
            'cos': list(env.companies.ids or [env.company.id]),
        }

        period = section('period', lambda: self._home_period(st, safe, optional),
                         None) or self._home_period_empty(today)
        st['period'] = period
        runs = section('runs', lambda: self._home_runs(st, safe, optional), [])
        st['run_rows'] = runs
        needs, approvals_total = section(
            'needs_you', lambda: self._home_needs(st, safe, optional),
            ([], None))
        months = section('months', lambda: self._home_months(st, safe, optional),
                         [])
        people = section('people', lambda: self._home_people(st, safe, optional),
                         None)
        hiring = section('hiring', lambda: self._home_hiring(st, safe, optional),
                         None)
        learn = section('learn', lambda: self._home_learn(st, safe, optional),
                        None)
        schemes = section('schemes',
                          lambda: self._home_schemes(st, safe, optional), None)
        # Steps and the calendar are the period's own story: timed with it.
        steps = section('period', lambda: self._home_steps(st, people), [])
        upcoming = section('period',
                           lambda: self._home_upcoming(st, safe, optional), [])

        # The activation checklist (pb_dashboard.py `_activation`), fed the
        # same three counts the old payload fed it (test 12).
        cdom = [('company_id', 'in', env.companies.ids)]
        employees = safe(lambda: env['hr.employee'].search_count(cdom), 0)
        contracts = (safe(lambda: env['hr.contract'].search_count(
            cdom + [('state', '=', 'open')]), 0)
            or safe(lambda: env['hr.contract'].search_count(cdom), 0))
        all_runs = safe(lambda: env['hr.payslip.run'].search_count([]), 0)
        activation = safe(lambda: self._activation(
            employees, contracts, all_runs, optional),
            {'show': not all_runs, 'items': []})

        cur = env.company.currency_id
        timing['total'] = _ms(started)
        _logger.info('home_data %d ms %s', timing['total'], ' '.join(
            '%s=%d' % (k, v) for k, v in timing.items() if k != 'total'))
        return {
            'user': env.user.name or '',
            'company': env.company.name or '',
            'currency': {
                'symbol': (cur.symbol if cur else None) or '',
                'position': (cur.position if cur else None) or 'before',
            },
            'today': today.isoformat(),
            'period': period,
            'needs_you': needs,
            'approvals_total': approvals_total,
            'months': months,
            'runs': runs,
            'steps': steps,
            'upcoming': upcoming,
            'people': people,
            'hiring': hiring,
            'learn': learn,
            'schemes': schemes,
            'activation': activation,
            'timing_ms': timing,
        }

    # ============================================================ shared reads
    @api.model
    def _home_run_facts(self, runs, cos):
        """(visible runs, {run_id: counts}) — ONE statement over the payslips.

        A run is visible when one of its payslips is in `cos`, or when it has
        none at all. Counts are of the reader's companies' payslips only.
        """
        Run = self.env['hr.payslip.run']
        if not runs:
            return Run, {}
        self.env['hr.payslip'].flush_model(
            ['payslip_run_id', 'company_id', 'state', 'employee_id'])
        self.env.cr.execute("""
            SELECT r.id,
                   count(p.id) FILTER (WHERE p.company_id IN %(cos)s
                                         AND p.state != 'cancel'),
                   count(p.id) FILTER (WHERE p.company_id IN %(cos)s
                                         AND p.state = 'done'),
                   count(p.id) FILTER (WHERE p.company_id IN %(cos)s
                                         AND p.state NOT IN ('draft', 'cancel')),
                   count(DISTINCT p.employee_id) FILTER (
                       WHERE p.company_id IN %(cos)s AND p.state != 'cancel'),
                   count(p.id)
              FROM hr_payslip_run r
              LEFT JOIN hr_payslip p ON p.payslip_run_id = r.id
             WHERE r.id IN %(ids)s
             GROUP BY r.id
        """, {'cos': tuple(cos), 'ids': tuple(runs.ids)})
        facts = {}
        for rid, slips, done, moved, people, every in self.env.cr.fetchall():
            if slips or not every:
                facts[rid] = {'slips': slips, 'done': done, 'moved': moved,
                              'people': people}
        return runs.filtered(lambda r: r.id in facts), facts

    @api.model
    def _home_money(self, runs):
        """{run_id: stored roll-ups} or {} when pb_payruns is absent (H4).

        A run in another currency than the company's carries no money here:
        no total on Home ever adds two currencies together.
        """
        Run = self.env['hr.payslip.run']
        if not runs or 'pb_total_net' not in Run._fields:
            return {}
        names = [f for _k, f in MONEY_FIELDS] + [
            f for f in ('pb_employee_count', 'pb_balance_ok',
                        'pb_unsourced_count', 'pb_currency_id')
            if f in Run._fields]
        company_cur = self.env.company.currency_id.id
        out = {}
        for row in runs.read(names):
            cur = row.get('pb_currency_id')
            cur_id = cur[0] if cur else False
            same = not cur_id or cur_id == company_cur
            out[row['id']] = {
                'money': same,
                'net': row['pb_total_net'] or 0.0,
                'gross': row['pb_total_gross'] or 0.0,
                'ded': row['pb_total_deductions'] or 0.0,
                'er': row['pb_total_employer_cost'] or 0.0,
                'people': row.get('pb_employee_count'),
                'balance_ok': row.get('pb_balance_ok'),
                'unsourced': row.get('pb_unsourced_count'),
            }
        return out

    @api.model
    def _home_delivered(self, run_ids, optional):
        """{run_id: last day a delivery batch completed} for these runs."""
        if not run_ids:
            return {}
        Batch = optional('pb.payslip.delivery.batch',
                         lambda: self.env['pb.payslip.delivery.batch'])
        if Batch is None:
            return {}
        out = {}
        for row in Batch.search_read(
                [('run_id', 'in', list(run_ids)), ('state', '=', 'done')],
                ['run_id', 'write_date']):
            rid = row['run_id'] and row['run_id'][0]
            day = row['write_date'] and row['write_date'].date()
            if rid and day and (rid not in out or day > out[rid]):
                out[rid] = day
        return out

    @api.model
    def _home_contract_ends(self, st):
        """Contracts ending soon, renewals and leavers — one search + one
        grouped read on hr.contract. Cached on `st`."""
        if 'contract_ends' in st:
            return st['contract_ends']
        Contract = self.env['hr.contract']
        today = st['today']
        horizon = today + timedelta(days=RENEWAL_DAYS)
        first = fields.Date.to_date(st['period']['date_start'])
        last = fields.Date.to_date(st['period']['date_end'])
        ending = Contract.search([
            ('company_id', 'in', st['cos']),
            ('state', 'in', ('open', 'close')),
            ('date_end', '>=', min(today, first)),
            ('date_end', '<=', max(horizon, last)),
        ])
        latest = {}
        if ending:
            for emp, start in Contract._read_group(
                    [('employee_id', 'in', ending.employee_id.ids),
                     ('state', '!=', 'cancel')],
                    ['employee_id'], ['date_start:max']):
                latest[emp.id] = start

        def renewed(c):
            nxt = latest.get(c.employee_id.id)
            return bool(nxt and c.date_end and nxt > c.date_end)

        window = ending.filtered(
            lambda c: c.state == 'open' and today <= c.date_end <= horizon)
        renewals = window.filtered(lambda c: not renewed(c))
        leavers = ending.filtered(
            lambda c: first <= c.date_end <= last and not renewed(c))
        out = {
            'window_n': len(window),
            'window_first': min(window.mapped('date_end')) if window else None,
            'renewals': len(renewals),
            'renewed': len(window) - len(renewals),
            'leaving': len(set(leavers.employee_id.ids)),
        }
        st['contract_ends'] = out
        return out

    @api.model
    def _home_writeups(self, st, safe, optional):
        """Interview write-ups past their due date (None without hiring)."""
        if 'writeups' in st:
            return st['writeups']
        env = self.env
        Interview = optional('pb.hiring.interview',
                             lambda: env['pb.hiring.interview'])
        value = None
        if Interview is not None:
            since = fields.Datetime.now() - timedelta(days=WRITEUP_LOOKBACK_DAYS)
            value = safe(lambda: sum(
                rec.feedback_late or 0 for rec in Interview.search(
                    [('company_id', 'in', st['cos']), ('start', '>=', since),
                     ('state', 'in', ('scheduled', 'done'))],
                    order='start desc', limit=WRITEUP_SCAN)), None)
        st['writeups'] = value
        return value

    @api.model
    def _home_settlements(self, st, safe, optional):
        """Final settlements worked out and waiting for somebody to check
        them (stored `pb_to_check`; 0 where the flag does not exist)."""
        if 'settlements' in st:
            return st['settlements']
        env = self.env
        Fnf = optional('hr.full.final.settlement',
                       lambda: env['hr.full.final.settlement'])
        value = 0
        if Fnf is not None and 'pb_to_check' in Fnf._fields:
            value = safe(lambda: Fnf.search_count(
                [('company_id', 'in', st['cos']), ('pb_to_check', '=', True)]),
                0) or 0
        st['settlements'] = value
        return value

    @api.model
    def _home_leave_pending(self, st, safe, optional):
        env = self.env
        Leave = optional('hr.leave', lambda: env['hr.leave'])
        if Leave is None:
            return None
        return safe(lambda: Leave.search_count([
            ('state', 'in', ('confirm', 'validate1')),
            ('employee_id.company_id', 'in', st['cos'])]), None)

    # ================================================================ period
    @api.model
    def _home_period_empty(self, today):
        first = today.replace(day=1)
        last = first + relativedelta(months=1, days=-1)
        return {
            'key': first.strftime('%Y-%m'), 'date_start': first.isoformat(),
            'date_end': last.isoformat(), 'stage': None, 'total': 5,
            'run_count': 0, 'delivered_count': 0, 'cutoff': None,
            'payday': None, 'prepared': 0, 'expected': 0, 'net_so_far': None,
            'awaiting_me': 0, 'awaiting_run': None, 'now_run': None,
        }

    @api.model
    def _home_period(self, st, safe, optional):
        env = self.env
        Run = env['hr.payslip.run']
        cos = st['cos']
        today = st['today']
        first = today.replace(day=1)
        last = first + relativedelta(months=1, days=-1)
        Hub = optional('pb.pay.hub', lambda: env['pb.pay.hub'])
        hub = safe(Hub.get_period_state, None) if Hub is not None else None
        if hub:
            first = fields.Date.to_date(hub['date_start'])
            last = fields.Date.to_date(hub['date_end'])

        runs = Run.search([('date_start', '<=', last), ('date_end', '>=', first),
                           ('state', '!=', 'cancel')],
                          order='date_end desc, id desc')
        runs, facts = self._home_run_facts(runs, cos)
        money = self._home_money(runs)
        delivered = self._home_delivered(runs.ids, optional)

        # THE HUB'S OWN RULE over the runs this reader can see, so the stage
        # and the runs listed under it can never disagree.
        stage = None
        if Hub is not None:
            stage = safe(lambda: Hub._stage(runs, set(delivered)), None)
            if stage is None and hub:
                stage = hub.get('stage')
        st['delivered_ids'] = set(delivered)
        st['local_stage'] = (min(
            (5 if _STAGE_OF_STATE.get(r.state, 2) == 4 and r.id in delivered
             else _STAGE_OF_STATE.get(r.state, 2)) for r in runs)
            if runs else 1)

        cutoff = payday = None
        Cal = optional('pb.payroll.calendar', lambda: env['pb.payroll.calendar'])
        if Cal is not None:
            rows = safe(lambda: Cal.search_read(
                [('month', '=', first), ('company_id', 'in', cos + [False])],
                ['company_id', 'cutoff_date', 'pay_date']), []) or []
            rows.sort(key=lambda r: 0 if r['company_id'] else 1)
            if rows:
                cutoff, payday = rows[0]['cutoff_date'], rows[0]['pay_date']

        expected_groups = safe(lambda: env['hr.contract']._read_group(
            [('state', '=', 'open'), ('company_id', 'in', cos)],
            ['employee_id']), []) or []
        st['expected'] = len(expected_groups)

        net_so_far = None
        if money:
            net_so_far = sum(m['net'] for m in money.values() if m['money'])

        mine = set()
        if hasattr(Run, '_pb_runs_awaiting'):
            mine = safe(lambda: Run._pb_runs_awaiting(env.uid), set()) or set()
        awaiting = runs.filtered(lambda r: r.id in mine)
        st['awaiting_ids'] = set(awaiting.ids)

        awaiting_run = None
        if awaiting:
            run = awaiting[0]
            who = self._home_submitter(run, safe, optional)
            m = money.get(run.id) or {}
            awaiting_run = {
                'id': run.id, 'name': run.name or '',
                'division': self._home_division(run),
                'people': self._home_people_of(run, facts, money),
                'net': m.get('net') if m.get('money') else None,
                'submitted_by': who,
                'initials': _person_initials(who),
            }

        now_run = None
        drafts = runs.filtered(
            lambda r: r.state == 'draft' and facts[r.id]['slips'] > 0)
        if drafts:
            run = max(drafts, key=lambda r: (r.write_date, r.id))
            now_run = {
                'id': run.id, 'name': run.name or '',
                'division': self._home_division(run),
                # "done" = payslips already past draft; "total" = payslips in
                # the run. A per-run head count to prepare is not stored.
                'done': facts[run.id]['moved'],
                'total': facts[run.id]['slips'],
            }

        st['period_runs'] = runs
        st['period_facts'] = facts
        st['period_money'] = money
        return {
            'key': first.strftime('%Y-%m'),
            'date_start': first.isoformat(),
            'date_end': last.isoformat(),
            'stage': stage,
            'total': 5,
            'run_count': len(runs),
            'delivered_count': len(set(delivered) & set(runs.ids)),
            'cutoff': _iso(cutoff),
            'payday': _iso(payday),
            'prepared': sum(f['slips'] for f in facts.values()),
            'expected': st['expected'],
            'net_so_far': net_so_far,
            'awaiting_me': len(awaiting),
            'awaiting_run': awaiting_run,
            'now_run': now_run,
        }

    @api.model
    def _home_division(self, run):
        """The run's division as the Pay Runs board names it: the scheme's
        name without the brand and the cycle ("Information Technology"),
        never the stored title-cased key ("It" for IT — walk 2026-10-12)."""
        cfg = run.pb_formula_config_id if 'pb_formula_config_id' in run._fields \
            else None
        if cfg:
            try:
                name = (cfg.sudo().name or '').replace('Payobook', '')
                name = name.split('—')[0].strip()
                if name:
                    return name
            except Exception:                       # noqa: BLE001 - label only
                pass
        if 'pb_division_label' in run._fields:
            return run.pb_division_label or ''
        return ''

    @api.model
    def _home_people_of(self, run, facts, money):
        stored = (money.get(run.id) or {}).get('people')
        if stored is not None:
            return int(stored or 0)
        return int((facts.get(run.id) or {}).get('people') or 0)

    @api.model
    def _home_submitter(self, run, safe, optional):
        """Who sent this run in: the open approval request's submitter, else
        the person who last touched the run."""
        env = self.env
        Req = optional('biz.approval.request', lambda: env['biz.approval.request'])
        name = None
        if Req is not None:
            req = safe(lambda: Req.search(
                [('res_model', '=', 'hr.payslip.run'), ('res_id', '=', run.id),
                 ('state', 'in', ('pending', 'blocked'))],
                order='id desc', limit=1), None)
            if req:
                user = (req.submitter_uid if 'submitter_uid' in req._fields
                        else req.create_uid) or req.create_uid
                name = safe(lambda: user.name, None)
        return name or safe(lambda: run.write_uid.name, '') or ''

    # ================================================================== runs
    @api.model
    def _home_runs(self, st, safe, optional):
        runs = st.get('period_runs')
        if not runs:
            return []
        facts = st['period_facts']
        money = st['period_money']
        no_bank = safe(lambda: self._home_no_bank(runs.ids, st['cos']), {}) or {}
        st['no_bank_total'] = sum(no_bank.values()) if no_bank else 0
        mine = st.get('awaiting_ids', ())
        pending = runs.filtered(
            lambda r: r.state == 'approval_pending' and r.id not in mine)
        waiting = safe(lambda: self._home_waiting_on(pending, optional),
                       {}) or {}
        out = []
        for run in runs:
            f = facts[run.id]
            m = money.get(run.id) or {}
            division = self._home_division(run)
            out.append({
                'id': run.id,
                'name': run.name or '',
                'division': division,
                'initials': _initials(division or run.name),
                'state': run.state,
                'people': self._home_people_of(run, facts, money),
                'slips': f['slips'],
                'done': f['done'],
                'net': m.get('net') if m.get('money') else None,
                'balance_ok': m.get('balance_ok') if m else None,
                'unsourced': m.get('unsourced') if m else None,
                'awaiting_me': run.id in mine,
                # HOME P3: who the run is waiting on, when it is not me —
                # the name on the current step's open seat (None otherwise).
                'waiting_on': waiting.get(run.id),
                'no_bank': no_bank.get(run.id, 0),
            })
        return out

    @api.model
    def _home_waiting_on(self, runs, optional):
        """{run_id: name of the person the run waits on} for submitted runs —
        the open seat on the request's ACTIVE step (the same seat
        `_pb_runs_awaiting` counts for me). One search over the period's
        submitted runs; a seat held by the reader is skipped, so a run that
        waits on me never reads "waiting on <someone else>"."""
        env = self.env
        if not runs:
            return {}
        Req = optional('biz.approval.request', lambda: env['biz.approval.request'])
        if Req is None or 'seat_ids' not in Req._fields:
            return {}
        out = {}
        for req in Req.search([('res_model', '=', 'hr.payslip.run'),
                               ('res_id', 'in', runs.ids),
                               ('state', 'in', ('pending', 'blocked'))],
                              order='id desc'):
            if req.res_id in out:
                continue
            for seat in req.seat_ids:
                if seat.status != 'open' or seat.step_id.status != 'active':
                    continue
                user = seat.acting_user_id or seat.user_id
                if user and user.id != env.uid and user.name:
                    out[req.res_id] = user.name
                    break
        return out

    @api.model
    def _home_bank_link(self):
        """(SQL fragment testing that employee `p.employee_id` has a bank
        account) for whichever field this build carries, or None."""
        Employee = self.env['hr.employee']
        tests = []
        many = Employee._fields.get('bank_account_ids')
        if many is not None and getattr(many, 'relation', None):
            tests.append(SQL('EXISTS (SELECT 1 FROM %s b WHERE b.%s = p.employee_id)',
                             SQL.identifier(many.relation),
                             SQL.identifier(many.column1)))
        elif 'bank_account_id' in Employee._fields:
            tests.append(SQL('EXISTS (SELECT 1 FROM hr_employee e WHERE e.id = '
                             'p.employee_id AND e.bank_account_id IS NOT NULL)'))
        # The pay data keeps the account on the employee itself
        # (pb_hr_payroll_formula `account_number`) — the People screen's
        # "with bank" count reads that. On payobook 4,500 of 4,547 people have
        # one and NOBODY has a linked bank record (walk 2026-10-12, H31).
        acct = Employee._fields.get('account_number')
        if acct is not None and acct.store:
            tests.append(SQL("EXISTS (SELECT 1 FROM hr_employee e WHERE e.id = "
                             "p.employee_id AND COALESCE(e.account_number, '') <> '')"))
        if not tests:
            return None
        return SQL('(%s)', SQL(' OR ').join(tests))

    @api.model
    def _home_month_people(self, run_ids, cos):
        """{'YYYY-MM' (run date_end): distinct people paid} — one statement on
        the payslip_run_id index; never the line table (H-R1)."""
        if not run_ids:
            return {}
        self.env.cr.execute(SQL("""
            SELECT to_char(r.date_end, 'YYYY-MM'), count(DISTINCT p.employee_id)
              FROM hr_payslip p
              JOIN hr_payslip_run r ON r.id = p.payslip_run_id
             WHERE p.payslip_run_id IN %s AND p.company_id IN %s
               AND p.state != 'cancel'
             GROUP BY 1
        """, tuple(run_ids), tuple(cos)))
        return dict(self.env.cr.fetchall())

    @api.model
    def _home_no_bank(self, run_ids, cos):
        """{run_id: people in the run with no bank account} — one statement."""
        has_bank = self._home_bank_link()
        if not run_ids or has_bank is None:
            return {}
        self.env.cr.execute(SQL("""
            SELECT p.payslip_run_id, count(DISTINCT p.employee_id)
              FROM hr_payslip p
             WHERE p.payslip_run_id IN %s AND p.company_id IN %s
               AND p.state != 'cancel' AND NOT %s
             GROUP BY 1
        """, tuple(run_ids), tuple(cos), has_bank))
        return dict(self.env.cr.fetchall())

    # ============================================================= needs you
    @api.model
    def _home_needs(self, st, safe, optional):
        env = self.env
        counts = {key: 0 for key in NEEDS_ORDER}
        counts['runs_to_approve'] = st['period']['awaiting_me'] or 0

        approvals_total = None
        Inbox = optional('pb.approval.inbox', lambda: env['pb.approval.inbox'])
        inbox = safe(lambda: Inbox.list_requests(tab='mine'), None) \
            if Inbox is not None else None
        if inbox:
            approvals_total = int((inbox.get('counts') or {}).get('mine') or 0)
            # The leave process is keyed `leave`; its area (`time`) is shared
            # with overtime, timesheets and corrections, so the area is too
            # wide to call "leave".
            counts['leave_to_approve'] = sum(
                1 for c in inbox.get('cards') or ()
                if c.get('process_key') == 'leave')
            counts['other_to_approve'] = max(
                0, approvals_total - counts['runs_to_approve']
                - counts['leave_to_approve'])
        else:
            counts['leave_to_approve'] = self._home_leave_pending(
                st, safe, optional) or 0

        counts['settlements_to_check'] = self._home_settlements(
            st, safe, optional)
        ends = safe(lambda: self._home_contract_ends(st), None)
        counts['renewals_to_start'] = (ends or {}).get('renewals') or 0
        counts['writeups_overdue'] = self._home_writeups(st, safe, optional) or 0
        needs = [{'key': key, 'n': int(counts[key])}
                 for key in NEEDS_ORDER if counts[key] > 0]
        return needs, approvals_total

    # ================================================================ months
    @api.model
    def _home_months(self, st, safe, optional):
        env = self.env
        Run = env['hr.payslip.run']
        period = st['period']
        p_first = fields.Date.to_date(period['date_start'])
        p_last = fields.Date.to_date(period['date_end'])
        starts = [p_first - relativedelta(months=MONTHS - 1 - i)
                  for i in range(MONTHS)]
        keys = [d.strftime('%Y-%m') for d in starts]
        w_first = starts[0]

        runs = Run.search([('date_end', '>=', w_first), ('date_end', '<=', p_last),
                           ('state', '!=', 'cancel')])
        runs, facts = self._home_run_facts(runs, st['cos'])
        money = self._home_money(runs)
        delivered = safe(lambda: self._home_delivered(runs.ids, optional),
                         {}) or {}
        approved = safe(lambda: self._home_approved(runs.ids, optional), {}) or {}
        tet = safe(lambda: self._home_tet_months(w_first, p_last, optional),
                   set()) or set()

        by_key = {key: [] for key in keys}
        for run in runs:
            key = run.date_end.strftime('%Y-%m')
            if key in by_key:
                by_key[key].append(run)

        # People paid = each person ONCE per month. Summing the runs' head
        # counts counted a mid-month advance and the end-month run twice
        # (payobook June read 8,879 for 4,486 people — walk 2026-10-12, H32).
        heads = safe(lambda: self._home_month_people(runs.ids, st['cos']), None)

        has_money = bool(money) or 'pb_total_net' in Run._fields
        out = []
        for index, key in enumerate(keys):
            group = by_key[key]
            people = heads.get(key, 0) if heads is not None else sum(
                self._home_people_of(r, facts, money) for r in group)
            row = {
                'key': key,
                'year_mark': index == 0 or key.endswith('-01'),
                'people': people,
                'net': None, 'gross': None, 'ded': None, 'er': None,
                'total': None, 'avg': None,
                'runs': len(group),
                'balance_ok': None,
                'done': bool(group) and all(r.state == 'done' for r in group),
                'latest': False,
                'inprogress': key == period['key'],
                'approved': _iso(max((approved[r.id] for r in group
                                      if r.id in approved), default=None)),
                'delivered': _iso(max((delivered[r.id] for r in group
                                       if r.id in delivered), default=None)),
                'note': 'tet' if key in tet else None,
                # HOME P2 (H21): runs in this month whose money is in another
                # currency than the company's — counted in `runs`, left out
                # of every sum, and said so on the month's facts line.
                'foreign_runs': sum(1 for r in group if r.id in money
                                    and not money[r.id]['money']),
            }
            if has_money:
                counted = [money[r.id] for r in group
                           if r.id in money and money[r.id]['money']]
                for k, _f in MONEY_FIELDS:
                    row[k] = float(sum(m[k] for m in counted))
                row['total'] = row['gross'] + row['er']
                row['avg'] = (row['net'] / row['people']) if row['people'] \
                    else None
                flags = [money[r.id]['balance_ok'] for r in group
                         if r.id in money and facts[r.id]['slips']]
                row['balance_ok'] = all(flags) if flags else None
            out.append(row)

        done_before = [m for m in out if m['done'] and m['key'] < period['key']]
        if done_before:
            done_before[-1]['latest'] = True
        st['period_approved'] = out[-1]['approved'] if out else None
        return out

    @api.model
    def _home_approved(self, run_ids, optional):
        """{run_id: day its approval closed} (approved or applied)."""
        env = self.env
        if not run_ids:
            return {}
        Req = optional('biz.approval.request', lambda: env['biz.approval.request'])
        if Req is None or 'closed_at' not in Req._fields:
            return {}
        out = {}
        for row in Req.search_read(
                [('res_model', '=', 'hr.payslip.run'),
                 ('res_id', 'in', list(run_ids)),
                 ('state', 'in', ('approved', 'applied')),
                 ('closed_at', '!=', False)],
                ['res_id', 'closed_at']):
            day = row['closed_at'].date()
            rid = row['res_id']
            if rid not in out or day > out[rid]:
                out[rid] = day
        return out

    @api.model
    def _home_tet_months(self, first, last, optional):
        """Month keys holding the lunar new year, read off the company's own
        public-holiday names (pb.holidays). Empty when the module is absent
        or the holidays are named otherwise; no lunar arithmetic here."""
        env = self.env
        Hol = optional('pb.holidays', lambda: env['pb.holidays'])
        if Hol is None or not hasattr(Hol, '_column'):
            return set()
        column = Hol._column(env.company, first, last, fields.Date.context_today(self))
        out = set()
        for row in (column or {}).get('rows') or ():
            if _TET.search(row.get('name') or ''):
                for day in (row.get('date'), row.get('date_to')):
                    if day:
                        out.add(day[:7])
        return out

    # ================================================================ people
    @api.model
    def _home_people(self, st, safe, optional):
        env = self.env
        cos = st['cos']
        today = st['today']
        Employee = env['hr.employee']
        Contract = env['hr.contract']
        first = fields.Date.to_date(st['period']['date_start'])
        last = fields.Date.to_date(st['period']['date_end'])
        prev_first = first - relativedelta(months=1)

        headcount = Employee.search_count([('company_id', 'in', cos)])
        active = Contract.search_count([('company_id', 'in', cos),
                                        ('state', '=', 'open')])
        expected = st.get('expected')
        if expected is None:
            expected = len(Contract._read_group(
                [('state', '=', 'open'), ('company_id', 'in', cos)],
                ['employee_id']))
        joined = joined_prev = 0
        if 'first_contract_date' in Employee._fields:
            joined = Employee.search_count([
                ('company_id', 'in', cos), ('first_contract_date', '>=', first),
                ('first_contract_date', '<=', last)])
            joined_prev = Employee.search_count([
                ('company_id', 'in', cos),
                ('first_contract_date', '>=', prev_first),
                ('first_contract_date', '<', first)])
        st['joined'] = joined
        ends = safe(lambda: self._home_contract_ends(st), None) or {}

        out = {
            'headcount': headcount,
            'active_contracts': active,
            'no_contract': max(0, headcount - expected),
            'joined': joined,
            'joined_prev': joined_prev,
            'leaving': ends.get('leaving') or 0,
            'settlements_to_check': self._home_settlements(st, safe, optional),
            'out_today': None,
            'out_breakdown': [],
            'week': None,
            'leave_pending': self._home_leave_pending(st, safe, optional),
        }
        Leave = optional('hr.leave', lambda: env['hr.leave'])
        if Leave is not None:
            leave = safe(lambda: self._home_leave(Leave, cos, today), None)
            if leave:
                out.update(leave)
        return out

    @api.model
    def _home_leave(self, Leave, cos, today):
        """Out today (count + top 3 leave types) and the next 7 days — the
        pb_timeoff `_kpis` shape, from one grouped read and one bounded
        search."""
        base = [('state', '=', 'validate'),
                ('employee_id.company_id', 'in', cos)]
        groups = Leave._read_group(
            base + [('request_date_from', '<=', today),
                    ('request_date_to', '>=', today)],
            ['holiday_status_id'], ['__count'])
        breakdown = sorted(
            ({'label': (kind.display_name if kind else '') or '', 'n': n}
             for kind, n in groups),
            key=lambda r: -r['n'])
        end = today + timedelta(days=6)
        rows = Leave.search_read(
            base + [('request_date_from', '<=', end),
                    ('request_date_to', '>=', today)],
            ['request_date_from', 'request_date_to'], limit=LEAVE_WEEK_SCAN)
        week = []
        for i in range(7):
            day = today + timedelta(days=i)
            n = sum(1 for r in rows
                    if r['request_date_from'] and r['request_date_to']
                    and r['request_date_from'] <= day <= r['request_date_to'])
            week.append({'date': day.isoformat(), 'n': n,
                         'weekend': day.weekday() >= 5})
        return {
            'out_today': sum(r['n'] for r in breakdown),
            'out_breakdown': breakdown[:3],
            'week': week,
        }

    # ================================================================ hiring
    @api.model
    def _home_hiring(self, st, safe, optional):
        env = self.env
        cos = st['cos']
        Hiring = optional('pb.hiring', lambda: env['pb.hiring'])
        if Hiring is None or not safe(Hiring._can_read, False):
            return None
        Req = optional('pb.hiring.requisition',
                       lambda: env['pb.hiring.requisition'])
        if Req is None:
            return None
        open_reqs = Req.search([('state', '=', 'open'),
                                ('company_id', 'in', cos)])
        now = fields.Datetime.now()
        month_start = st['today'].replace(day=1)

        candidates = None
        Applicant = optional('hr.applicant', lambda: env['hr.applicant'])
        if Applicant is not None and 'pb_requisition_id' in Applicant._fields:
            candidates = safe(lambda: Applicant.search_count(
                [('pb_requisition_id', 'in', open_reqs.ids)]), None) \
                if open_reqs else 0

        interviews = None
        Interview = optional('pb.hiring.interview',
                             lambda: env['pb.hiring.interview'])
        if Interview is not None:
            interviews = safe(lambda: Interview.search_count([
                ('company_id', 'in', cos), ('state', '=', 'scheduled'),
                ('start', '>=', now),
                ('start', '<', now + timedelta(days=INTERVIEW_DAYS))]), None)

        over = None
        if 'budget_status' in Req._fields:
            over = len(open_reqs.filtered(lambda r: r.budget_status == 'over'))

        offers = None
        Offer = optional('pb.hiring.offer', lambda: env['pb.hiring.offer'])
        if Offer is not None:
            offers = safe(lambda: Offer.search_count(
                [('state', '=', 'sent'), ('company_id', 'in', cos)]), None)

        referrals = None
        Referral = optional('pb.hiring.referral', lambda: env['pb.hiring.referral'])
        if Referral is not None and 'submitted_on' in Referral._fields:
            referrals = safe(lambda: Referral.search_count(
                [('company_id', 'in', cos),
                 ('submitted_on', '>=', month_start)]), None)

        return {
            'open': len(open_reqs),
            'candidates': candidates,
            'interviews_week': interviews,
            'writeups_overdue': self._home_writeups(st, safe, optional),
            'over_budget': over,
            'offers_waiting': offers,
            'referrals': referrals,
        }

    # ================================================================= learn
    @api.model
    def _home_learn(self, st, safe, optional):
        env = self.env
        Runtime = optional('learn.runtime', lambda: env['learn.runtime'])
        if Runtime is None:
            return None
        best = safe(Runtime.next_best, {}) or {}
        if not best.get('key'):
            return None
        Content = optional('learn.content', lambda: env['learn.content'])
        item = None
        if Content is not None:
            if best.get('kind') == 'mission':
                item = safe(lambda: Content.mission(best['key']), None)
            else:
                item = safe(lambda: Content.station(best['key']), None)
        item = item or {}
        lang = (env.context.get('lang') or env.user.lang or '')

        def words(value):
            # Learn content carries {'en': …, 'vi': …} for names and reasons;
            # the browser shows text (payobook walk: "[object Object]", H43).
            if isinstance(value, dict):
                return value.get('vi' if lang.startswith('vi') else 'en') \
                    or value.get('en') or ''
            return value or ''

        reason = words(best.get('reason'))
        streak = safe(Runtime.streak, {}) or {}
        minutes = item.get('duration_min')
        return {
            'key': best['key'],
            'title': words(item.get('name') or item.get('title')),
            'minutes': int(minutes) if minutes else None,
            'reason': reason or '',
            'streak_days': int(streak.get('days') or 0),
        }

    # =============================================================== schemes
    @api.model
    def _home_schemes(self, st, safe, optional):
        env = self.env
        Config = optional('hr.formula.config', lambda: env['hr.formula.config'])
        out = {'count': 0, 'active': 0, 'components': 0, 'tests_total': 0,
               'tests_passed': None, 'last_run': None, 'failing_configs': 0}
        if Config is None:
            return out
        cfgs = safe(lambda: Config.search(
            [('company_id', 'in', st['cos'] + [False])]), None)
        if not cfgs:
            return out
        out['count'] = len(cfgs)
        out['active'] = safe(lambda: len(cfgs.filtered(
            lambda c: c.state == 'active')), 0) or 0
        out['components'] = safe(lambda: sum(c.rule_count for c in cfgs), 0) or 0
        out['failing_configs'] = safe(lambda: len(cfgs.filtered(
            lambda c: c.validation_status == 'failed')), 0) or 0

        Result = optional('hr.formula.test.result',
                          lambda: env['hr.formula.test.result'])
        link = Config._fields.get('test_result_ids')
        link = getattr(link, 'inverse_name', None) if link is not None else None
        if Result is None or not link:
            return out
        dom = [(link, 'in', cfgs.ids)]
        out['tests_total'] = safe(lambda: Result.search_count(dom), 0) or 0
        if 'status' in Result._fields:
            out['tests_passed'] = safe(lambda: Result.search_count(
                dom + [('status', '=', 'passed')]), None)
        last = safe(lambda: Result.search(dom, order='create_date desc',
                                          limit=1).create_date, None)
        out['last_run'] = last.strftime('%Y-%m-%d %H:%M') if last else None
        return out

    # ================================================================= steps
    @api.model
    def _home_steps(self, st, people):
        """The five steps, derived from the period. One `now` at most."""
        period = st['period']
        stage = period['stage']
        if stage is None:
            stage = st.get('local_stage') or 1
        has_runs = bool(period['run_count'])
        awaiting = period['awaiting_me'] or 0
        payday = fields.Date.to_date(period['payday']) if period['payday'] \
            else None
        approved = st.get('period_approved')

        def step(key, state, when=None, n=None, who=None, run=None):
            return {'key': key, 'state': state, 'when': when, 'n': n,
                    'who': who, 'run': run}

        setup_done = stage >= 2 or has_runs
        steps = [step('setup', 'done' if setup_done else 'now',
                      when=period['date_start'] if setup_done else None,
                      n=(people or {}).get('joined'))]

        prepare = 'done' if stage >= 3 else 'now' if stage == 2 else 'todo'
        now_run = period.get('now_run') or {}
        steps.append(step('prepare', prepare, n=period['prepared'],
                          run=now_run.get('name')))

        awaiting_run = period.get('awaiting_run') or {}
        who = None
        if awaiting_run.get('submitted_by'):
            who = {'name': awaiting_run['submitted_by'],
                   'initials': awaiting_run.get('initials') or ''}
        if awaiting > 0:
            approve = 'wait'
        elif stage >= 4:
            approve = 'done'
        elif stage == 3:
            approve = 'now'
        else:
            approve = 'todo'
        steps.append(step('approve', approve, when=approved, who=who,
                          run=awaiting_run.get('name')))

        steps.append(step('pay', 'done' if stage >= 4 else 'todo',
                          when=_iso(payday), n=st.get('no_bank_total', 0)))

        delivered_all = (period['run_count'] > 0
                         and period['delivered_count'] == period['run_count'])
        deliver = 'done' if delivered_all else 'now' if stage == 4 else 'todo'
        steps.append(step('deliver', deliver,
                          when=_iso(payday + timedelta(days=2)) if payday
                          else None))
        return steps

    # ============================================================== upcoming
    @api.model
    def _home_upcoming(self, st, safe, optional):
        env = self.env
        today = st['today']
        period = st['period']
        items = []
        cutoff = fields.Date.to_date(period['cutoff']) if period['cutoff'] \
            else None
        if cutoff and cutoff >= today:
            items.append({'kind': 'cutoff', 'date': cutoff.isoformat(),
                          'n': None, 'extra': {}})
        else:
            # HOME P3: this month's cut-off has passed (or the calendar has
            # none) — the next one to plan for is next month's. `extra.month`
            # tells the browser which month's changes it closes.
            nxt = safe(lambda: self._home_next_cutoff(st, optional), None)
            if nxt and nxt[1] >= today:
                items.append({'kind': 'cutoff', 'date': nxt[1].isoformat(),
                              'n': None, 'extra': {'month': nxt[0]}})
        payday = fields.Date.to_date(period['payday']) if period['payday'] \
            else None
        if payday and payday >= today:
            banks = safe(lambda: self._home_bank_count(st['cos']), None)
            items.append({'kind': 'payday', 'date': payday.isoformat(),
                          'n': None,
                          'extra': {'banks': banks} if banks is not None else {}})

        ends = safe(lambda: self._home_contract_ends(st), None) or {}
        if ends.get('window_n'):
            items.append({'kind': 'contracts_end',
                          'date': ends['window_first'].isoformat(),
                          'n': ends['window_n'],
                          'extra': {'renewals': ends['renewals'],
                                    'renewed': ends['renewed']}})

        Hol = optional('pb.holidays', lambda: env['pb.holidays'])
        if Hol is not None:
            nxt = safe(Hol.next_one, None)
            if nxt and nxt.get('date'):
                last_day = nxt.get('date_to') or nxt['date']
                if last_day >= today.isoformat():
                    items.append({'kind': 'holiday', 'date': nxt['date'],
                                  'n': None,
                                  'extra': {'name': nxt.get('name') or ''}})

        Interview = optional('pb.hiring.interview',
                             lambda: env['pb.hiring.interview'])
        if Interview is not None:
            now = fields.Datetime.now()
            dom = [('company_id', 'in', st['cos']), ('state', '=', 'scheduled'),
                   ('start', '>=', now),
                   ('start', '<', now + timedelta(days=INTERVIEW_DAYS))]
            n = safe(lambda: Interview.search_count(dom), 0) or 0
            if n:
                first = safe(lambda: Interview.search(
                    dom, order='start', limit=1).start, None)
                if first:
                    day = fields.Datetime.context_timestamp(self, first).date()
                    items.append({'kind': 'interviews',
                                  'date': day.isoformat(), 'n': n,
                                  'extra': {}})

        items = [i for i in items if i['date'] >= today.isoformat()]
        items.sort(key=lambda i: i['date'])
        return items[:UPCOMING_CAP]

    @api.model
    def _home_next_cutoff(self, st, optional):
        """('YYYY-MM', cut-off day) of the month after the period, from its
        pb.payroll.calendar row (the company's own row before a shared one),
        or None."""
        env = self.env
        Cal = optional('pb.payroll.calendar', lambda: env['pb.payroll.calendar'])
        if Cal is None:
            return None
        first = fields.Date.to_date(st['period']['date_start']) \
            + relativedelta(months=1)
        rows = Cal.search_read(
            [('month', '=', first), ('company_id', 'in', st['cos'] + [False]),
             ('cutoff_date', '!=', False)],
            ['company_id', 'cutoff_date'])
        if not rows:
            return None
        rows.sort(key=lambda r: 0 if r['company_id'] else 1)
        return first.strftime('%Y-%m'), rows[0]['cutoff_date']

    @api.model
    def _home_bank_count(self, cos):
        """Distinct banks across the people with an open contract — one
        statement; None when this build keeps no bank on the employee."""
        Employee = self.env['hr.employee']
        many = Employee._fields.get('bank_account_ids')
        if many is not None and getattr(many, 'relation', None):
            link = SQL("""
                JOIN %s rel ON rel.%s = c.employee_id
                JOIN res_partner_bank b ON b.id = rel.%s""",
                       SQL.identifier(many.relation),
                       SQL.identifier(many.column1),
                       SQL.identifier(many.column2))
        elif 'bank_account_id' in Employee._fields:
            link = SQL("""
                JOIN hr_employee e ON e.id = c.employee_id
                JOIN res_partner_bank b ON b.id = e.bank_account_id""")
        else:
            return None
        self.env.cr.execute(SQL("""
            SELECT count(DISTINCT b.bank_id)
              FROM hr_contract c %s
             WHERE c.state = 'open' AND c.company_id IN %s
        """, link, tuple(cos)))
        return int((self.env.cr.fetchone() or [0])[0] or 0)
