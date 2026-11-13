# -*- coding: utf-8 -*-
"""pb.clock.pairing — punch ledger → hr.attendance (CLOCK ledger D1–D6).

THE RULES, IN ORDER

  1. Outliers (D6): a punch more than 10 minutes in the future, or dated before
     2015, is `ignored_outlier` — a machine whose clock was reset.
  2. Match (D5): the number on the machine → a person of the punch's company:
     clock number, then badge ID, then ID number; active people before archived
     ones (a leaver's late punches still match). No one → `unmatched`.
     Unmatched numbers are retried on every run, so giving someone that badge
     ID on their record heals the back-log by itself.
  3. Double taps (D2): the same person again within `pb_clock_double_tap_min`
     of the last KEPT punch → `ignored_duplicate_tap`.
  4. Anchor + span (D1): a work day opens at the first kept punch and takes
     every kept punch within `pb_clock_max_span_h` hours of it. The day's date
     is the anchor's LOCAL date for that person (ledger rule 11), so a 19:18 →
     07:36 night shift is one day dated the evening it began.
  5. First punch in, last punch out (D3, direction not trusted by default);
     the taps in between are `middle` — kept and shown, not paid.
  6. Reconcile (D4): the engine owns ONLY rows whose pb_entry_source is
     'device'. Per day: update the device row in place, create one if none,
     remove device rows no day claims any more. A day that is closed, inside a
     week under approval, carries a correction, or would overlap a row a person
     made is left exactly as it is — the punches are `held` with the reason.

IDEMPOTENT (rule 10). Re-running computes the same days and writes nothing:
every write goes through `_apply`, which skips equal values.

NEVER INLINE (rule 12). Intake paths only add ledger rows and `_trigger()` the
cron; this is the only code that turns a punch into attendance.
"""

import json
import logging
import time
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

_FUTURE_SLACK = timedelta(minutes=10)
_OLDEST = datetime(2015, 1, 1)
# the states the day-builder recomputes (outliers and unmatched stay out)
_ACTIVE = ('matched', 'paired', 'middle', 'held', 'ignored_duplicate_tap')
_OFFICER_GROUP = 'hr_attendance.group_hr_attendance_officer'
_RUNS_PARAM = 'pb_clock.pair_runs'


def _AUTO_CLOSED_NOTE():
    return _("Check-out missing; closed so later days can be paired.")


class PbClockPairing(models.AbstractModel):
    _name = 'pb.clock.pairing'
    _description = 'Time clock pairing engine'

    # ------------------------------------------------------------ access
    @api.model
    def _require_officer(self):
        if self.env.su:
            return
        u = self.env.user
        if not (u.has_group(_OFFICER_GROUP) or u.has_group('base.group_system')):
            raise AccessError(_("Pairing punches is for attendance officers."))

    # ------------------------------------------------------------ entry points
    @api.model
    def _cron_run(self):
        """The scheduled job body. Runs one bounded batch, then (CLOCK-3 §6)
        asks to run again right away while punches still wait — so a 100 000
        line history finishes in minutes, not 20 runs × 5 minutes. It only
        re-triggers on `new` punches (each run turns every one it reads into
        something else), never on a `matched` leftover a failing person would
        keep there: the job cannot spin."""
        started = time.monotonic()
        t0 = fields.Datetime.now()
        res = self.sudo().run()
        if 'pb.clock.command' in self.env:
            try:
                with self.env.cr.savepoint():
                    self.env['pb.clock.command'].sudo()._sweep()
            except Exception:  # noqa: BLE001 — the sweep never stops pairing
                _logger.warning("pb_clock: command sweep failed", exc_info=True)
        n = res.get('read', 0)
        if n:
            self._remember_run(t0, time.monotonic() - started, n)
        left = res.get('more') or bool(self.env['pb.clock.punch'].sudo().search_count(
            [('state', '=', 'new')], limit=1))
        if left:
            cron = self.env.ref('pb_clock.cron_pair_punches', raise_if_not_found=False)
            if cron:
                cron.sudo()._trigger()
        res['retriggered'] = bool(left)
        return res

    # ------------------------------------------------------------ throughput (CLOCK-3 §6)
    @api.model
    def _remember_run(self, started_at, secs, n):
        """Keep the last 5 runs that did something: [start, seconds, punches]."""
        ICP = self.env['ir.config_parameter'].sudo()
        try:
            runs = json.loads(ICP.get_param(_RUNS_PARAM) or '[]')
        except ValueError:
            runs = []
        runs = (runs + [[fields.Datetime.to_string(started_at), round(secs, 2), int(n)]])[-5:]
        ICP.set_param(_RUNS_PARAM, json.dumps(runs))

    @api.model
    def _rate_per_min(self):
        """Punches paired per minute over the last 5 runs, gaps between runs
        included (a re-triggered run waits for the scheduler). None when
        nothing was measured."""
        try:
            runs = json.loads(self.env['ir.config_parameter'].sudo().get_param(
                _RUNS_PARAM) or '[]')
        except ValueError:
            return None
        if not runs:
            return None
        total = sum(int(r[2]) for r in runs)
        if len(runs) >= 2:
            first = fields.Datetime.to_datetime(runs[0][0])
            last = fields.Datetime.to_datetime(runs[-1][0])
            span = (last - first).total_seconds() + float(runs[-1][1])
        else:
            span = float(runs[0][1])
        if span <= 0 or not total:
            return None
        return total / span * 60.0

    @api.model
    def _trigger_soon(self):
        """Ask the scheduled job to run now (an upload just landed)."""
        cron = self.env.ref('pb_clock.cron_pair_punches', raise_if_not_found=False)
        if cron:
            try:
                cron.sudo()._trigger()
                return True
            except Exception:  # noqa: BLE001 — the 5-minute schedule still runs
                _logger.warning("pb_clock: could not trigger the pairing job",
                                exc_info=True)
        return False

    @api.model
    def run(self, company_ids=None, employee_ids=None, limit=5000, now=None):
        """Match and pair waiting punches. Returns a summary for the lens toast:
        {matched, unmatched, paired_days, held, ignored, more}."""
        self._require_officer()
        self = self.sudo()
        now = fields.Datetime.to_datetime(now) or fields.Datetime.now()
        summary = {'matched': 0, 'unmatched': 0, 'paired_days': 0, 'held': 0,
                   'ignored': 0, 'more': False}
        Punch = self.env['pb.clock.punch']
        dom = [('state', '=', 'new')]
        if company_ids:
            dom.append(('company_id', 'in', list(company_ids)))
        new = Punch.search(dom, order='punch_utc, id', limit=limit)
        summary['more'] = len(new) >= limit
        summary['read'] = len(new)

        # 1. outliers
        outliers = new.filtered(
            lambda p: p.punch_utc > now + _FUTURE_SLACK or p.punch_utc < _OLDEST)
        for p in outliers:
            self._apply(p, {'state': 'ignored_outlier',
                            'note': _("Ignored: the machine's clock looks wrong "
                                      "(%s).") % fields.Datetime.to_string(p.punch_local)})
        summary['ignored'] += len(outliers)
        todo = new - outliers

        # 2. match — the waiting punches plus yesterday's unknown numbers
        retry_dom = [('state', '=', 'unmatched')]
        if company_ids:
            retry_dom.append(('company_id', 'in', list(company_ids)))
        retry = Punch.search(retry_dom, order='punch_utc, id', limit=limit)
        matched_now = self._match(todo | retry, summary)
        # a person whose earlier pairing failed half-way is picked up again
        left_dom = [('state', '=', 'matched')]
        if company_ids:
            left_dom.append(('company_id', 'in', list(company_ids)))
        matched_now |= Punch.search(left_dom, order='punch_utc, id', limit=limit)

        # 3–6. pair every person who has a newly matched punch
        first_new = {}
        for p in matched_now:
            cur = first_new.get(p.employee_id.id)
            if cur is None or p.punch_utc < cur:
                first_new[p.employee_id.id] = p.punch_utc
        if employee_ids:
            wanted = {int(e) for e in employee_ids}
            first_new = {e: t for e, t in first_new.items() if e in wanted}
        Emp = self.env['hr.employee'].with_context(active_test=False)
        for emp_id, t_from in first_new.items():
            try:
                with self.env.cr.savepoint():
                    self._pair_employee(Emp.browse(emp_id), t_from, summary)
            except Exception:  # noqa: BLE001 — one person never stops the batch
                _logger.exception("pb_clock: pairing failed for employee %s", emp_id)
        return summary

    @api.model
    def repair_employee(self, employee_id, date_from, date_to):
        """Recompute this person's days from `date_from` (local) onward —
        used after a number is assigned and by "Re-pair this week". Writes only
        what differs, so repeating it is free."""
        self._require_officer()
        self = self.sudo()
        emp = self.env['hr.employee'].with_context(active_test=False).browse(
            int(employee_id)).exists()
        summary = {'matched': 0, 'unmatched': 0, 'paired_days': 0, 'held': 0,
                   'ignored': 0, 'more': False}
        if not emp:
            return summary
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to) or date_from
        lo, hi = self.env['hr.attendance']._pb_week_window_utc(emp, date_from, date_to)
        first = self.env['pb.clock.punch'].search([
            ('employee_id', '=', emp.id), ('state', 'in', _ACTIVE),
            ('punch_utc', '>=', lo), ('punch_utc', '<=', hi),
        ], order='punch_utc, id', limit=1)
        if first:
            self._pair_employee(emp, first.punch_utc, summary)
        return summary

    # ------------------------------------------------------------ matching
    @api.model
    def _code_index(self, company, codes):
        """{code: employee} for `codes` in `company` by the D5 order."""
        codes = sorted({c for c in codes if c})
        if not codes:
            return {}
        Emp = self.env['hr.employee'].sudo().with_context(active_test=False)
        emps = Emp.search([
            ('company_id', '=', company.id),
            '|', '|',
            ('pb_clock_code', 'in', codes),
            ('barcode', 'in', codes),
            ('identification_id', 'in', codes),
        ])
        best = {}
        for e in emps:
            for rank, value in ((0, e.pb_clock_code), (1, e.barcode),
                                (2, e.identification_id)):
                value = (value or '').strip()
                if value not in codes:
                    continue
                key = (rank, 0 if e.active else 1, e.id)
                if value not in best or key < best[value][0]:
                    best[value] = (key, e)
        return {code: hit[1] for code, hit in best.items()}

    @api.model
    def _match(self, punches, summary):
        matched = self.env['pb.clock.punch']
        by_company = {}
        for p in punches:
            by_company.setdefault(p.company_id, self.env['pb.clock.punch'])
            by_company[p.company_id] |= p
        for company, recs in by_company.items():
            index = self._code_index(company, recs.mapped('user_code'))
            for p in recs:
                emp = index.get(p.user_code)
                if emp:
                    self._apply(p, {'employee_id': emp.id, 'state': 'matched',
                                    'note': False})
                    matched |= p
                    summary['matched'] += 1
                elif p.state != 'unmatched':
                    self._apply(p, {'state': 'unmatched', 'note': False})
                    summary['unmatched'] += 1
        return matched

    # ------------------------------------------------------------ the day
    @api.model
    def _pair_employee(self, emp, t_from, summary):
        """Recompute every day of `emp` from the one containing `t_from`."""
        Punch = self.env['pb.clock.punch']
        Att = self.env['hr.attendance'].sudo()
        company = emp.company_id
        span = timedelta(hours=company.pb_clock_max_span_h or 21.0)
        tap = timedelta(minutes=max(company.pb_clock_double_tap_min or 0, 0))
        trust = bool(company.pb_clock_trust_direction)

        # T0: the anchor of any already-built day that could reach t_from
        t0 = t_from
        prior = Punch.search([
            ('employee_id', '=', emp.id), ('state', 'in', ('paired', 'middle', 'held')),
            ('work_day', '!=', False),
            ('punch_utc', '>=', t_from - span), ('punch_utc', '<', t_from)])
        if prior:
            anchor = Punch.search([
                ('employee_id', '=', emp.id), ('state', 'in', _ACTIVE),
                ('work_day', 'in', list(set(prior.mapped('work_day')))),
            ], order='punch_utc, id', limit=1)
            if anchor and anchor.punch_utc < t0:
                t0 = anchor.punch_utc
        punches = Punch.search([
            ('employee_id', '=', emp.id), ('state', 'in', _ACTIVE),
            ('punch_utc', '>=', t0)], order='punch_utc, id')
        if not punches:
            return

        # double taps, then anchor + span
        kept, taps = [], []          # taps: (punch, kept partner)
        for p in punches:
            if kept and tap and p.punch_utc - kept[-1].punch_utc < tap:
                taps.append((p, kept[-1]))
                continue
            kept.append(p)
        days = []
        for p in kept:
            if not days or p.punch_utc - days[-1][0].punch_utc > span:
                days.append([p])
            else:
                days[-1].append(p)

        cache = {}
        desired = []
        day_of = {}
        for i, group in enumerate(days):
            ci_p, co_p = self._ends(group, trust)
            # D11: a day with no check-out that is followed by a later day is
            # closed at its own check-in (0 h) so the later day can be paired
            # (one open attendance per person is a platform limit)
            auto = co_p is None and i < len(days) - 1
            d = {
                'date': Att._pb_local_day_of(emp, group[0].punch_utc, cache),
                'punches': group,
                'ci': ci_p.punch_utc,
                'co': co_p.punch_utc if co_p else (ci_p.punch_utc if auto else False),
                'auto': auto,
                'ends': {ci_p.id} | ({co_p.id} if co_p else set()),
                'row': Att.browse(),
            }
            desired.append(d)
            for p in group:
                day_of[p.id] = d

        # the device rows this recompute owns
        linked = punches.mapped('attendance_id').filtered(
            lambda a: a.pb_entry_source == 'device')
        rows = Att.search([('employee_id', '=', emp.id),
                           ('pb_entry_source', '=', 'device'),
                           ('check_in', '>=', t0)], order='check_in') | linked
        by_day = {}
        for row in rows.sorted('check_in'):
            by_day.setdefault(row._pb_local_day(cache), []).append(row)
        claimed = set()
        for d in desired:
            mine = {p.attendance_id.id for p in d['punches'] if p.attendance_id}
            pool = [r for r in by_day.get(d['date'], []) if r.id not in claimed]
            pick = [r for r in pool if r.id in mine][:1] or pool[:1]
            if pick:
                d['row'] = pick[0]
                claimed.add(pick[0].id)
        orphans = rows.filtered(lambda r: r.id not in claimed)

        # which days a person already decided about
        dates = {d['date'] for d in desired} | {
            r._pb_local_day(cache) for r in orphans}
        guard = self._guards(emp, dates)

        # orphans first (frees the time they occupy), unless their day is guarded
        for row in orphans:
            day = row._pb_local_day(cache)
            if guard.get(day):
                continue
            try:
                with self.env.cr.savepoint():
                    row.unlink()
            except Exception as exc:  # noqa: BLE001
                _logger.info("pb_clock: kept device row %s: %s", row.id, exc)

        if desired:
            self._close_earlier_open_day(emp, desired[0], rows, cache)

        for d in desired:
            reason = guard.get(d['date'])
            if not reason:
                reason = self._manual_overlap(emp, d, span)
            if not reason:
                reason = self._write_day(emp, d, summary)
            if reason:
                self._hold(d, reason, summary)
            else:
                self._mark(d)

        for p, partner in taps:
            d = day_of.get(partner.id)
            self._apply(p, {
                'state': 'ignored_duplicate_tap', 'attendance_id': False,
                'work_day': d['date'] if d else False,
                'note': _("Counted once: a second tap within %s minutes.")
                % (company.pb_clock_double_tap_min or 0)})

    @api.model
    def _close_earlier_open_day(self, emp, first, rows, cache):
        """D11 for a day built by an EARLIER run: the person's latest open
        time-clock day before this recompute is closed at its own check-in and
        flagged, so the new day can be written. Only a `device` row, only on an
        earlier local day, never on a day a person decided about (closed,
        under approval, corrected) — those stay as they are and the new day is
        held with the reason, as before."""
        Att = self.env['hr.attendance'].sudo()
        stale = Att.search([('employee_id', '=', emp.id), ('check_out', '=', False),
                            ('check_in', '<', first['ci'])],
                           order='check_in desc', limit=1)
        if not stale or stale.id in rows.ids or stale.pb_entry_source != 'device':
            return False
        day = stale._pb_local_day(cache)
        if not day or day >= first['date'] or self._guards(emp, {day}).get(day):
            return False
        try:
            with self.env.cr.savepoint():
                stale.write({'check_out': stale.check_in, 'pb_clock_auto_closed': True})
        except Exception as exc:  # noqa: BLE001 — the new day is then held
            _logger.info("pb_clock: could not close open day %s: %s", stale.id, exc)
            return False
        for p in self.env['pb.clock.punch'].search([('attendance_id', '=', stale.id)]):
            self._apply(p, {'note': _AUTO_CLOSED_NOTE()})
        return True

    @api.model
    def _ends(self, group, trust):
        """(check-in punch, check-out punch or None) of one day."""
        if trust:
            ins = [p for p in group if p.direction == 'in']
            ci = ins[0] if ins else group[0]
            outs = [p for p in group if p.direction == 'out'
                    and p.punch_utc > ci.punch_utc]
            if outs:
                return ci, outs[-1]
            last = group[-1]
            if last.id != ci.id and last.direction != 'in':
                return ci, last
            return ci, None
        return group[0], (group[-1] if len(group) > 1 else None)

    @api.model
    def _guards(self, emp, dates):
        """{date: plain reason} for the days device data must not touch."""
        out = {}
        dates = [d for d in dates if d]
        if not dates:
            return out
        if 'pb.wf.lock' in self.env:
            for day in self.env['pb.wf.lock'].sudo()._locked_dates(
                    emp.company_id, dates):
                out[day] = _("Not applied: %s is closed.") % day.strftime('%d %b %Y')
        if 'pb.timesheet.freeze' in self.env:
            frozen = self.env['pb.timesheet.freeze'].sudo().frozen_map(
                [(emp.id, d) for d in dates])
            for (_e, day), packet in frozen.items():
                out.setdefault(day, (
                    _("Not applied: the week of %s has been approved.")
                    if packet.state == 'approved' else
                    _("Not applied: the week of %s is waiting for approval."))
                    % packet.week_start.strftime('%d %b'))
        if 'hr.attendance.correction' in self.env:
            corrs = self.env['hr.attendance.correction'].sudo().search([
                ('employee_id', '=', emp.id), ('date', 'in', dates),
                ('state', '!=', 'refused')])
            for c in corrs:
                out.setdefault(c.date, _(
                    "Not applied: a correction exists for this day (%s).")
                    % (c.name or ''))
        return out

    @api.model
    def _manual_overlap(self, emp, d, span):
        """A reason if a row a PERSON made overlaps this day's hours."""
        ci = d['ci']
        co = d['co'] if d['co'] and d['co'] > ci else (ci + timedelta(minutes=1))
        dom = [('employee_id', '=', emp.id),
               ('check_in', '<', co),
               '|', ('pb_entry_source', '!=', 'device'),
               ('pb_entry_source', '=', False),
               '|', ('check_out', '>', ci),
               '&', ('check_out', '=', False), ('check_in', '>=', ci - span)]
        if d['row']:
            dom.append(('id', '!=', d['row'].id))
        if self.env['hr.attendance'].sudo().search_count(dom, limit=1):
            return _("Not applied: a manual entry exists for this day.")
        return False

    @api.model
    def _write_day(self, emp, d, summary):
        """Create / update the day's device row. A plain reason on refusal."""
        Att = self.env['hr.attendance'].sudo()
        vals = {'check_in': d['ci'], 'check_out': d['co'] or False,
                'pb_clock_auto_closed': bool(d.get('auto'))}
        try:
            with self.env.cr.savepoint():
                row = d['row']
                if row:
                    diff = {k: v for k, v in vals.items() if row[k] != v}
                    if diff:
                        row.write(diff)
                        summary['paired_days'] += 1
                else:
                    d['row'] = Att.create(dict(vals, employee_id=emp.id,
                                               pb_entry_source='device'))
                    summary['paired_days'] += 1
        except Exception as exc:  # noqa: BLE001 — refusal → held, never a crash
            d['row'] = d['row'].exists() if d['row'] else d['row']
            return self._plain_refusal(exc)
        return False

    @api.model
    def _plain_refusal(self, exc):
        msg = str(getattr(exc, 'args', [''])[0] or exc or '')
        if "checked out since" in msg:
            return _("Not applied: an earlier day has no check-out yet. Fix "
                     "that day first.")
        if "already checked in" in msg:
            return _("Not applied: a manual entry exists for this day.")
        return (_("Not applied: %s") % msg)[:250]

    @api.model
    def _mark(self, d):
        row = d['row']
        note = _AUTO_CLOSED_NOTE() if d.get('auto') else False
        for p in d['punches']:
            self._apply(p, {
                'state': 'paired' if p.id in d['ends'] else 'middle',
                'attendance_id': row.id if row else False,
                'work_day': d['date'], 'note': note})

    @api.model
    def _hold(self, d, reason, summary):
        """Leave the day as it is: punches already counted on it stay counted,
        the rest wait with the reason."""
        for p in d['punches']:
            if (p.state in ('paired', 'middle') and p.work_day == d['date']
                    and p.attendance_id):
                continue
            self._apply(p, {'state': 'held', 'work_day': d['date'],
                            'note': reason})
            summary['held'] += 1

    @api.model
    def _apply(self, punch, vals):
        """Write only what differs (rule 10: a second run writes nothing)."""
        diff = {}
        for k, v in vals.items():
            cur = punch[k]
            if hasattr(cur, 'id') and not isinstance(cur, (str, bytes)):
                cur = cur.id or False
            if (cur or False) != (v or False):
                diff[k] = v
        if diff:
            punch.write(diff)
        return bool(diff)
