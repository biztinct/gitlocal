# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools import format_date

_logger = logging.getLogger(__name__)

# The stages the board draws and the words for them — imported rather than
# re-typed, so the board can never offer a stage the model does not have.
from .hr_payslip_run import PB_BOARD_STATES, PB_STAGE_NAME

STAGE_ORDER = list(PB_BOARD_STATES)
STAGE_LABEL = dict(PB_STAGE_NAME)
BOARD_LIMIT = 60

# The month journey the hero draws (PAYRUN BOARD redesign, 2026-10-11). The
# numbers are the Pay Run hub's own tracker stages (`pb.pay.hub`, _STAGE_DOC),
# so the chip in the hub's command bar and the hero below it can never
# disagree. Stage 5 is NOT a run state: "delivered" means a completed payslip
# delivery batch hangs off the run.
MONTH_STAGES = 5
_RUN_STAGE = {'draft': 2, 'approval_pending': 3, 'done': 4}

# NAV P3b — the readiness checklist on every open card. The attendance-close
# line is ADVICE: it never blocks Submit (pb_close's cardinal rule, restated).
# One line per open week, at most this many, then "+N more weeks".
CLOSE_LINES_MAX = 2
# Who may open Workforce › Close (pb_mission LENSES `close`.groups). The door
# is offered only to them; anyone else still reads the line and its owner.
_CLOSE_LENS_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)
_OPEN_STATES = ('draft', 'approval_pending')


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
        scheme_currency_of = self._scheme_currency_by_run(runs)
        # Where each approved run's money and payslips have got to — one query
        # per delivery model, never one per card.
        delivery_of = self._delivery_by_run(runs)
        # Division names, read ONCE off the schemes that carry a division. The
        # stored label title-cases the key ("it" → "It"); the scheme's own name
        # says "Information Technology" and is what the chips already showed.
        divisions, division_name = self._divisions()

        # Batch-compute all run totals in ONE pass (single SQL) instead of letting
        # each per-run field access trigger its own aggregation.
        self._safe(lambda: runs.mapped('pb_total_net'))
        # NAV P3b — everything the open cards' checklists need, read once for
        # the whole board: the Payroll owner per company, the attendance
        # owner per run, and the day locks of every open run's period.
        readiness = self._safe(lambda: self._readiness_context(runs, owner),
                               default=None) or self._empty_readiness()

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
            # The scheme decides; the company is only the fallback for a run
            # with no scheme at all (traditional structure payroll).
            run_currency = (scheme_currency_of.get(run.id)
                            or currency_of.get(run_company)
                            or {'name': cur.name or '',
                                'symbol': cur.symbol or ''})
            if state == 'done' and run_currency['name'] == (cur.name or ''):
                # Only ever add up money of the SAME kind. A cross-currency
                # total is not a rounding problem, it is a wrong number.
                period_net += net or 0.0

            division = run.pb_division or ''
            delivery = delivery_of.get(run.id) or self._empty_delivery()
            approval = self._approval_chip(run)
            balance_ok = self._safe(lambda r=run: bool(r.pb_balance_ok),
                                    default=True)
            balance_gap = self._safe(lambda r=run: r.pb_balance_gap) or 0.0
            unsourced = self._safe(lambda r=run: r.pb_unsourced_count) or 0
            checks, ready, close_weeks = self._safe(
                lambda r=run: self._run_checks(
                    r, state, next_action, run_company, readiness,
                    unsourced=unsourced, balance_ok=balance_ok,
                    balance_gap=balance_gap,
                    symbol=run_currency['symbol']),
                default=([], False, None))
            batches.append({
                'id': run.id,
                'name': run.name or '—',
                'state': state,
                'stage_label': STAGE_LABEL.get(state, state),
                'date_start': str(run.date_start or ''),
                'date_end': str(run.date_end or ''),
                'period': self._fmt_period(run.date_start, run.date_end),
                # The calendar month the card files under ('YYYY-MM'). A run
                # is keyed by the period it pays for, so the END date names
                # the month: a 25th-to-24th cycle belongs to the month it
                # closes in.
                'month': self._month_key(run.date_end or run.date_start),
                'month_label': self._month_label(run.date_end or run.date_start),
                'employees': self._safe(lambda r=run: r.pb_employee_count),
                'net': net or 0.0,
                'gross': self._safe(lambda r=run: r.pb_total_gross) or 0.0,
                'deductions': self._safe(lambda r=run: r.pb_total_deductions) or 0.0,
                'employer_cost': self._safe(
                    lambda r=run: r.pb_total_employer_cost) or 0.0,
                # The run's own health, already stored beside its totals.
                'balance_ok': balance_ok,
                'balance_gap': balance_gap,
                'unsourced': unsourced,
                # NAV P3b — can this run move, and who must act: one line per
                # open thing, each with its owner, and `ready` when a draft has
                # nothing in its way. The three keys above stay for Learn.
                'checks': checks,
                'ready': ready,
                'close_weeks': close_weeks,
                'credit_note': bool(run.credit_note),
                'next_action': next_action,
                'can_act': can_act,
                'can_reject': may_write and state in ('draft',
                                                      'approval_pending'),
                'awaiting_me': waiting_on_me,
                # The route this run is on, and where it has got to — read off
                # the request rather than off a state name, because "who is it
                # with" is now a person, not a tier.
                'approval': approval,
                # why this run came back, if an approver sent it back
                'return_note': run.pb_return_note or '',
                'return_by': run.pb_return_uid.name or '',
                'return_on': self._fmt_date(run.pb_return_date),
                # why this run was rejected (kept for good once it is)
                'reject_note': run.pb_reject_note or '',
                'reject_by': run.pb_reject_uid.name or '',
                'prepared_by': run.pb_prepared_uid.name or '',
                # Where an approved run's money and payslips have got to.
                'delivery': delivery,
                # What happened to it, in order, in words.
                'history': self._history(run, approval, delivery),
                # The division key the board's chips filter on, and its name.
                'division': division,
                'division_label': division_name.get(division)
                or run.pb_division_label or '',
                # Each run priced in ITS OWN company's money.
                'company_id': run_company,
                'currency': run_currency['symbol'],
                'currency_name': run_currency['name'],
            })

        drawn = [s for s in STAGE_ORDER]
        columns = [{'key': s, 'label': STAGE_LABEL[s], 'count': stage_counts.get(s, 0)}
                   for s in drawn]

        # Demo users get the board pre-filtered to the live demo month (June 2026).
        is_demo_user = self._safe(
            lambda: self.env.user.has_group('pb_demo.group_payobook_demo'),
            default=False)
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
            # The month the hero talks about: the calendar month, as the Pay
            # Run hub's own tracker keys it — and, since NAV P3b, its two
            # dates from the Payroll calendar.
            'period': self._period_block(batches, company),
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
        """Which route this run is on and who it is waiting for, in words.

        Read as superuser. The reader can already see the run; the request's
        own record rules ("mine" for approval users) would refuse anyone who
        is not a seat on it, and that refusal used to escape this card and
        blank the whole board ("You don't have access to this yet"). The chip
        is a summary — route, step, names — so showing it to whoever sees the
        run leaks nothing the run itself does not.
        """
        return self._safe(lambda: self._approval_chip_data(run), default={})

    @api.model
    def _approval_chip_data(self, run):
        request = run.sudo().approval_request_id
        if not request:
            return {}
        step = None
        if request.current_step_key:
            step = request.step_ids.filtered(
                lambda s: s.key == request.current_step_key)[:1]
        # Every step the route includes, in order, with who holds it and
        # whether it has been decided — the quick look draws the whole
        # route, the card draws "Sign-off 2 of 3".
        included = request.step_ids.filtered('included').sorted(
            key=lambda s: (s.sequence, s.id))
        steps = []
        for st in included:
            open_seats = st.seat_ids.filtered(lambda s: s.status == 'open')
            done_seats = st.seat_ids.filtered(lambda s: s.status == 'approved')
            steps.append({
                'key': st.key,
                'title': st.title or '',
                'status': st.status,
                'with': sorted(set(open_seats.mapped('acting_user_id.name'))),
                'decided_by': sorted(set(done_seats.mapped('acting_user_id.name'))),
                'decided_on': self._fmt_date(st.decided_at),
            })
        index = 0
        if step:
            keys = [s['key'] for s in steps]
            index = keys.index(step.key) + 1 if step.key in keys else 0
        return {
            'request_id': request.id,
            'state': request.state,
            'workflow': request.version_id.workflow_id.name or '',
            'step': (step.title if step else ''),
            'with': ', '.join(sorted(set(
                step.seat_ids.filtered(lambda s: s.status == 'open')
                .mapped('acting_user_id.name')))) if step else '',
            'blocked': request.block_reason or '',
            'step_index': index,
            'step_total': len(steps),
            'steps': steps,
            'submitted_on': self._fmt_date(request.submitted_at),
            'closed_on': self._fmt_date(request.closed_at),
        }

    @api.model
    def _empty_delivery(self):
        return {'bank_file': False, 'paid': False, 'paid_on': '',
                'delivered': False, 'slips_sent': 0, 'delivered_on': '',
                'journals': False, 'journals_on': ''}

    @api.model
    def _delivery_by_run(self, runs):
        """{run id: delivery dict} — bank file, payment, payslips, journals.

        Each is a model of ``pb_pay_delivery``, which this module does not
        depend on, so every read is guarded by ``self.env.get`` and the
        answer on a database without it is "nothing delivered" — true, since
        nothing could have been.
        """
        out = {}
        if not runs:
            return out
        ids = runs.ids
        done_runs = runs.filtered(lambda r: r.state == 'done')
        for run in done_runs:
            out[run.id] = self._empty_delivery()
            # pb_paid / pb_paid_on live on the run only with pb_pay_delivery.
            paid_on = self._safe(lambda r=run: getattr(r, 'pb_paid_on', False),
                                 default=False)
            if self._safe(lambda r=run: bool(getattr(r, 'pb_paid', False)),
                          default=False):
                out[run.id]['paid'] = True
                out[run.id]['paid_on'] = self._fmt_date(paid_on)

        BankFile = self.env.get('pb.bank.file')
        if BankFile is not None:
            rows = self._safe(lambda: BankFile.sudo().search_read(
                [('run_id', 'in', ids), ('state', '=', 'approved')],
                ['run_id']), default=[])
            for row in rows:
                rid = row['run_id'][0]
                if rid in out:
                    out[rid]['bank_file'] = True

        Batch = self.env.get('pb.payslip.delivery.batch')
        if Batch is not None:
            rows = self._safe(lambda: Batch.sudo().search_read(
                [('run_id', 'in', ids), ('state', '=', 'done')],
                ['run_id', 'sent_count', 'write_date'], order='id asc'),
                default=[])
            for row in rows:
                rid = row['run_id'][0]
                if rid in out:
                    out[rid]['delivered'] = True
                    out[rid]['slips_sent'] += row.get('sent_count') or 0
                    out[rid]['delivered_on'] = self._fmt_date(row.get('write_date'))

        Journal = self.env.get('pb.payroll.journal')
        if Journal is not None:
            rows = self._safe(lambda: Journal.sudo().search_read(
                [('run_id', 'in', ids), ('state', '=', 'posted')],
                ['run_id', 'posted_on']), default=[])
            for row in rows:
                rid = row['run_id'][0]
                if rid in out:
                    out[rid]['journals'] = True
                    out[rid]['journals_on'] = self._fmt_date(row.get('posted_on'))
        return out

    @api.model
    def _history(self, run, approval, delivery):
        """What happened to this run, oldest first: [[sentence, date], …].

        Plain sentences built server-side so a translator sees whole lines.
        """
        ev = []
        try:
            prepared = run.pb_prepared_uid.name or run.create_uid.name or ''
            ev.append([self.env._("Prepared by %s", prepared) if prepared
                       else self.env._("Prepared"),
                       self._fmt_date(run.create_date)])
            if approval:
                if approval.get('submitted_on'):
                    ev.append([self.env._("Submitted for approval"),
                               approval['submitted_on']])
                for st in approval.get('steps') or []:
                    if st['status'] == 'done' and st['decided_by']:
                        ev.append([self.env._(
                            "%(step)s · signed off by %(who)s",
                            step=st['title'], who=', '.join(st['decided_by'])),
                            st['decided_on']])
                    elif st['status'] == 'active':
                        who = ', '.join(st['with']) or self.env._("nobody yet")
                        ev.append([self.env._(
                            "%(step)s · waiting for %(who)s",
                            step=st['title'], who=who), ''])
            if run.pb_return_note:
                ev.append([self.env._("Sent back by %s to be fixed",
                                      run.pb_return_uid.name or ''),
                           self._fmt_date(run.pb_return_date)])
            if run.state == 'done':
                ev.append([self.env._("Approved"),
                           (approval or {}).get('closed_on', '')])
                if delivery.get('bank_file'):
                    ev.append([self.env._("Bank file made"), ''])
                if delivery.get('paid'):
                    ev.append([self.env._("Paid"), delivery.get('paid_on', '')])
                if delivery.get('delivered'):
                    ev.append([self.env._("Payslips sent to %s people",
                                          delivery.get('slips_sent') or 0),
                               delivery.get('delivered_on', '')])
                if delivery.get('journals'):
                    ev.append([self.env._("Journals posted"),
                               delivery.get('journals_on', '')])
            if run.state == 'cancel' and run.pb_reject_note:
                ev.append([self.env._("Rejected by %s", run.pb_reject_uid.name or ''),
                           ''])
        except Exception as e:  # a card's story must never blank the board
            _logger.debug("Pay Runs board history failed: %s", e)
        return ev

    @api.model
    def _divisions(self):
        """([{key, label}], {key: label}) from the schemes that carry a division."""
        seen = {}
        try:
            for c in self.env['hr.formula.config'].sudo().search([]):
                d = getattr(c, 'pb_division', '')
                if d and d not in seen:
                    nm = (c.name or '').replace('Payobook', '').split('—')[0].strip()
                    seen[d] = nm or d.replace('_', ' ').title()
        except Exception:
            seen = {}
        chips = [{'key': k, 'label': v}
                 for k, v in sorted(seen.items(), key=lambda x: x[1])]
        return chips, seen

    @api.model
    def _period_block(self, batches, company=None):
        """The calendar month the hero speaks about, keyed like the hub chip.

        Stage = the LEAST advanced of the month's live runs (zero runs is
        stage 1), exactly as `pb.pay.hub._stage` does it — restated here
        because this module must not depend on the hub that mounts it.

        NAV P3b: plus the month's two dates from the Payroll calendar —
        when changes close and when people are paid (`_calendar_dates`).
        """
        today = fields.Date.context_today(self)
        first = today.replace(day=1)
        last = first + relativedelta(months=1, days=-1)
        key = first.strftime('%Y-%m')
        stages = []
        for b in batches:
            if b['state'] == 'cancel':
                continue
            try:
                ds = date.fromisoformat(b['date_start']) if b['date_start'] else None
                de = date.fromisoformat(b['date_end']) if b['date_end'] else None
            except ValueError:
                continue
            if not (ds and de) or ds > last or de < first:
                continue
            s = _RUN_STAGE.get(b['state'], 2)
            if s == 4 and b['delivery'].get('delivered'):
                s = 5
            stages.append(s)
        block = {
            'key': key,
            'label': self._month_label(first),
            'short': format_date(self.env, first, date_format='MMM y'),
            'range': self._fmt_period(first, last),
            'date_start': first.isoformat(),
            'date_end': last.isoformat(),
            'stage': min(stages) if stages else 1,
            'total': MONTH_STAGES,
            'next_label': self._month_label(first + relativedelta(months=1)),
        }
        block.update(self._calendar_dates(first, today,
                                          company or self.env.company))
        return block

    @api.model
    def _calendar_dates(self, first, today, company):
        """The month's two dates from `pb.payroll.calendar`, as the hero says
        them: ``cutoff`` / ``pay_date`` (ISO or None), ``cutoff_in_days`` /
        ``pay_in_days`` (int or None) and ``cutoff_label`` / ``pay_label``
        (the reader's short date, e.g. "Fri 24 Oct").

        `pb.payroll.calendar` is pb_comp_ben's, which this module does NOT
        depend on — read through ``self.env.get`` and absent without it. The
        company's own row wins over a shared one (company empty), exactly as
        Home reads it (pb_dashboard home_data.py). Read as the system: these
        are two dates the whole payroll team works to, not a record the
        reader has to be in Compensation & Benefits to see.
        """
        out = {'cutoff': None, 'pay_date': None, 'cutoff_in_days': None,
               'pay_in_days': None, 'cutoff_label': '', 'pay_label': ''}
        Cal = self.env.get('pb.payroll.calendar')
        if Cal is None:
            return out
        cid = company.id if company else False
        rows = self._safe(lambda: Cal.sudo().search_read(
            [('month', '=', first), ('company_id', 'in', [cid, False])],
            ['company_id', 'cutoff_date', 'pay_date']), default=[]) or []
        if not rows:
            return out
        rows.sort(key=lambda r: 0 if r['company_id'] else 1)
        row = rows[0]
        for key, field in (('cutoff', 'cutoff_date'), ('pay_date', 'pay_date')):
            d = row.get(field)
            if not d:
                continue
            days_key = 'cutoff_in_days' if key == 'cutoff' else 'pay_in_days'
            label_key = 'cutoff_label' if key == 'cutoff' else 'pay_label'
            out[key] = d.isoformat()
            out[days_key] = (d - today).days
            out[label_key] = self._day_label(d)
        return out

    @api.model
    def _day_label(self, d):
        """A bare date as the reader says it: weekday, day, month ("Fri 24
        Oct" / "Th 6, 24 thg 10"). Formatted here, on the server, from the
        DATE itself — never through a JS Date, which reads a bare date as UTC
        midnight and shows the day before west of UTC (NAV ledger, P3a)."""
        if not d:
            return ''
        return self._safe(
            lambda: format_date(self.env, d, date_format='EEE d MMM'),
            default=d.strftime('%a %d %b'))

    # ---------------- NAV P3b: readiness ----------------
    @api.model
    def _empty_readiness(self):
        return {'payroll': {}, 'attendance': {}, 'close': {},
                'close_door': False}

    @api.model
    def _readiness_context(self, runs, owner):
        """Everything the open cards' checklists need, in a fixed number of
        reads however many cards there are (spec §3.5):

          payroll     {company id: res.users | None} — the company's Payroll
                      manager (responsibility `payroll_mgr`), one resolve per
                      company
          close       {run id: {'open': [Monday, …], 'closed', 'total'}} —
                      ONE `pb.wf.lock` query for every open run's days
          attendance  {run id: res.users} — the attendance manager most of
                      the run's people report to, ONE grouped query
          close_door  may the reader open Workforce › Close at all
        """
        ctx = self._empty_readiness()
        open_runs = runs.filtered(lambda r: (r.state or 'draft') in _OPEN_STATES)
        if not open_runs:
            return ctx
        default_cid = self.env.company.id
        companies = {owner.get(r.id, default_cid) for r in open_runs}
        ctx['payroll'] = self._safe(lambda: self._payroll_owners(companies),
                                    default={}) or {}
        if 'pb.wf.lock' in self.env:
            ctx['close'] = self._safe(
                lambda: self._close_status(open_runs, owner), default={}) or {}
            with_open = [rid for rid, st in ctx['close'].items() if st['open']]
            if with_open:
                ctx['attendance'] = self._safe(
                    lambda: self._attendance_owners(with_open), default={}) or {}
                ctx['close_door'] = self._safe(self._close_door, default=False)
        return ctx

    @api.model
    def _payroll_owners(self, company_ids):
        """{company id: res.users or None} — who holds `payroll_mgr` for the
        whole company today (biz_approval_workflow `resolve`, the very lookup
        a pay run's route seats its Payroll check with)."""
        Role = self.env.get('biz.approval.role')
        Resp = self.env.get('biz.approval.responsibility')
        if Role is None or Resp is None:
            return {}
        role = Role.sudo().search([('key', '=', 'payroll_mgr')], limit=1)
        if not role:
            return {}
        out = {}
        for cid in company_ids:
            company = self.env['res.company'].sudo().browse(cid).exists()
            if not company:
                continue
            row, _via = Resp.sudo().resolve(company, role, [''])
            user = row.user_id if row else None
            if row and not user and row.pool_user_ids:
                user = row.pool_user_ids[:1]
            out[cid] = user or None
        return out

    @api.model
    def _close_weeks(self, ds, de):
        """[(Monday, [days of that week inside [ds, de]])] for every week
        overlapping the period — pb_close's own rule (`_close_weeks_in` +
        `_close_week_status`, payrun_wizard.py): a week straddling the month
        edge counts only its days inside this run's period."""
        if not ds or not de or de < ds:
            return []
        out = []
        cur = ds - timedelta(days=ds.weekday())
        while cur <= de:
            days = [cur + timedelta(days=i) for i in range(7)]
            days = [d for d in days if ds <= d <= de]
            if days:
                out.append((cur, days))
            cur += timedelta(days=7)
        return out

    @api.model
    def _close_status(self, open_runs, owner):
        """{run id: {'open': [Monday, …], 'closed': n, 'total': n}}.

        A week is closed when every one of its days inside the period is
        LOCKED for the run's company (`total == 0 or locked >= total`, the
        wizard's test). One `_locked_pairs` call covers every company and
        every day of every open run on the board.

        Only weeks that have STARTED count (Monday <= today; coordinator
        decision 2026-10-21): a week that is not here yet is not "not
        closed", so a run prepared on the 21st does not list the week of the
        26th, and `closed` / `total` are "of the weeks so far".
        """
        Lock = self.env['pb.wf.lock']
        default_cid = self.env.company.id
        today = fields.Date.context_today(self)
        plan, companies, days = {}, set(), set()
        for run in open_runs:
            weeks = [(monday, ds) for monday, ds
                     in self._close_weeks(run.date_start, run.date_end)
                     if monday <= today]
            if not weeks:
                continue
            cid = owner.get(run.id, default_cid)
            plan[run.id] = (cid, weeks)
            companies.add(cid)
            for _monday, ds in weeks:
                days.update(ds)
        if not plan:
            return {}
        locked = Lock._locked_pairs(list(companies), list(days))
        out = {}
        for rid, (cid, weeks) in plan.items():
            open_weeks = [monday for monday, ds in weeks
                          if not all((cid, d) in locked for d in ds)]
            out[rid] = {'open': open_weeks,
                        'closed': len(weeks) - len(open_weeks),
                        'total': len(weeks)}
        return out

    @api.model
    def _attendance_owners(self, run_ids):
        """{run id: res.users} — the attendance manager most of the run's
        people have (`hr.employee.attendance_manager_id`), ties to the lowest
        id. One grouped query for every run that has an open week."""
        Employee = self.env['hr.employee']
        field = Employee._fields.get('attendance_manager_id')
        if not run_ids or not field or not field.store:
            return {}
        # Raw SQL reads the table, not the cache (ledger: ABM June pay run).
        self.env['hr.payslip'].flush_model(
            ['payslip_run_id', 'employee_id', 'state'])
        Employee.flush_model(['attendance_manager_id'])
        self.env.cr.execute(
            "SELECT p.payslip_run_id, e.attendance_manager_id, COUNT(*) "
            "FROM hr_payslip p JOIN hr_employee e ON e.id = p.employee_id "
            "WHERE p.payslip_run_id IN %s AND p.state != 'cancel' "
            "AND e.attendance_manager_id IS NOT NULL "
            "GROUP BY 1, 2 ORDER BY 1, 3 DESC, 2",
            (tuple(run_ids),))
        best = {}
        for run_id, user_id, _n in self.env.cr.fetchall():
            best.setdefault(run_id, user_id)
        users = self.env['res.users'].sudo().browse(set(best.values())).exists()
        by_id = {u.id: u for u in users}
        return {rid: by_id[uid] for rid, uid in best.items() if uid in by_id}

    @api.model
    def _close_door(self):
        """True when Workforce › Close exists here and the reader may open
        it. A door that lands on a lens the reader cannot see is a dead end."""
        if not self.env.ref('pb_mission.action_pb_workforce',
                            raise_if_not_found=False):
            return False
        user = self.env.user
        for xmlid in _CLOSE_LENS_GROUPS:
            try:
                if user.has_group(xmlid):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _short_name(self, name):
        """What a chip calls a person: the given name (the last word of a
        Vietnamese name), the whole name when it is two words or fewer once a
        DEMO prefix is set aside (pb_hiring facade_p6 `_short_name`)."""
        words = (name or '').replace('DEMO ', '', 1).split()
        return ' '.join(words) if len(words) <= 2 else words[-1]

    @api.model
    def _person(self, user=None, team=''):
        """An owner chip: a person, or the team when nobody is named."""
        if user:
            return {'name': user.name or '', 'short': self._short_name(user.name),
                    'uid': user.id, 'me': user.id == self.env.uid, 'team': False}
        return {'name': team, 'short': team, 'uid': False, 'me': False,
                'team': True}

    @api.model
    def _money_words(self, amount, symbol):
        """A gap as a reader writes it: ₫1,200,000 (whole units)."""
        try:
            return '%s%s' % (symbol or '', '{:,.0f}'.format(abs(amount or 0.0)))
        except (TypeError, ValueError):
            return '%s%s' % (symbol or '', amount)

    @api.model
    def _run_checks(self, run, state, next_action, run_company, readiness,
                    unsourced=0, balance_ok=True, balance_gap=0.0, symbol=''):
        """(checks, ready, close_weeks) for one card.

        checks       [{key, tone, icon, text, detail, owner, next, advisory,
                       more}] in the spec's order — sent back · no source
                     data · does not add up · attendance weeks. Only what is
                     relevant; empty on Done and Rejected runs.
        ready        a draft with nothing in its way: it can be sent in, no
                     rose line and nothing sent back to fix. Advice (the
                     attendance line) does not make a run unready.
        close_weeks  {'closed', 'total'} when the close line is in play, for
                     the quick look's "Weeks closed: 3 of the 4 weeks so
                     far" (started weeks only); else None.
        """
        if state not in _OPEN_STATES:
            return [], False, None
        _ = self.env._
        checks = []
        payroll_user = (readiness.get('payroll') or {}).get(run_company)
        preparer = run.pb_prepared_uid
        if preparer:
            fixer = self._person(preparer)
        elif payroll_user:
            fixer = self._person(payroll_user)
        else:
            fixer = self._person(team=_("Payroll team"))
        run_door = {'key': 'run'}

        if state == 'draft' and run.pb_return_note:
            by = run.pb_return_uid
            note = run.pb_return_note
            text = (_("Sent back by %(who)s: “%(note)s”",
                      who=self._short_name(by.name), note=note) if by
                    else _("Sent back: “%s”", note))
            # the quick look names people in full
            full = (_("Sent back by %(who)s: “%(note)s”",
                      who=by.name, note=note) if by else text)
            when = self._fmt_date(run.pb_return_date)
            detail = (_("Sent back on %s. Fix what it says, then send it in again.",
                        when) if when
                      else _("Fix what it says, then send it in again."))
            checks.append({'key': 'sent_back', 'tone': 'amber', 'icon': 'rotate',
                           'text': text, 'full': full, 'detail': detail,
                           'by': (by.name or '') if by else '',
                           'owner': fixer, 'next': None, 'advisory': False,
                           'more': ''})
        if unsourced:
            checks.append({
                'key': 'unsourced', 'tone': 'rose', 'icon': 'alert',
                'text': (_("1 payslip has no source data") if unsourced == 1
                         else _("%s payslips have no source data", unsourced)),
                'detail': _("Their figures are scheme defaults, not real pay."),
                'owner': fixer,
                'next': dict(run_door, label=_("Open the payslips")),
                'advisory': False, 'more': ''})
        if balance_ok is False:
            gap = self._money_words(balance_gap, symbol)
            checks.append({
                'key': 'balance', 'tone': 'rose', 'icon': 'alert',
                'text': _("Figures do not add up (gap %s)", gap),
                'detail': _("%s is unaccounted for between gross, deductions "
                            "and net.", gap),
                'owner': fixer,
                'next': dict(run_door, label=_("Open the run to see which component")),
                'advisory': False, 'more': ''})

        close_weeks = None
        status = (readiness.get('close') or {}).get(run.id)
        if status and status['total']:
            close_weeks = {'closed': status['closed'], 'total': status['total']}
        if status and status['open']:
            att = (readiness.get('attendance') or {}).get(run.id)
            att_owner = (self._person(att) if att
                         else self._person(team=_("Attendance team")))
            door = ({'key': 'close', 'label': _("Open Workforce › Close")}
                    if readiness.get('close_door') else None)
            weeks = status['open']
            shown = weeks[:CLOSE_LINES_MAX]
            rest = len(weeks) - len(shown)
            for i, monday in enumerate(shown):
                more = ''
                last = i == len(shown) - 1
                if rest and last:
                    more = (_("+1 more week") if rest == 1
                            else _("+%s more weeks", rest))
                checks.append({
                    'key': 'close_week', 'tone': 'amber', 'icon': 'lock',
                    'text': _("Attendance week of %s not closed",
                              self._safe(lambda m=monday: format_date(
                                  self.env, m, date_format='d MMM'),
                                  default=monday.strftime('%d %b'))),
                    'detail': _("Advice only: the run can still be sent in. "
                                "Closing the week locks the attendance behind "
                                "these payslips."),
                    'week': monday.isoformat(),
                    # one door per card, on the last week line: the same
                    # door under every week was noise (found in the walk)
                    'owner': att_owner, 'next': door if last else None,
                    'advisory': True,
                    'more': more})

        ready = (state == 'draft' and next_action == 'submit'
                 and not any(c['tone'] == 'rose' or c['key'] == 'sent_back'
                             for c in checks))
        return checks, ready, close_weeks

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
    def _scheme_currency_by_run(self, runs):
        """Each run's SCHEME currency, where it has a scheme.

        SCHEMECTX P1 — an India scheme inside a Vietnamese company is an India
        run, so the money on the card is the scheme's, not that of the company
        which happens to own the payslips. Rize runs both its Vietnam and its
        India payroll out of one VND company, so reading the company priced the
        India run's gross and net in dong while the payslips inside it were
        correctly in rupees.

        Same precedent as ``pb_payrun_results`` (SCHEMECTX P1 there too), and
        derived live through ``hr.payslip.run._pb_scheme_currency`` — the very
        method the stored ``pb_currency_id`` is computed from — rather than
        read off that stored field, which on some demo runs was computed under
        a different company context.
        """
        out = {}
        for run in runs:
            currency = self._safe(lambda r=run: r._pb_scheme_currency(),
                                  default=None)
            if currency:
                out[run.id] = {'name': currency.name,
                               'symbol': currency.symbol or currency.name}
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
    def _fmt_date(self, d):
        """A date or datetime as the reader's short date, or ''."""
        if not d:
            return ''
        try:
            if hasattr(d, 'hour'):
                d = fields.Datetime.context_timestamp(self, d).date()
            return format_date(self.env, d, date_format='d MMM y')
        except Exception:
            return str(d)[:10]

    @api.model
    def _month_key(self, d):
        return d.strftime('%Y-%m') if d else ''

    @api.model
    def _month_label(self, d):
        if not d:
            return ''
        return self._safe(lambda: format_date(self.env, d, date_format='MMMM y'),
                          default=d.strftime('%B %Y'))
