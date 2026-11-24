# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Step 7 "Check and go live" (WFSETUP P4, handover §2.3) — facade methods.

THE CHECK (`live_check`) is a pure read: the checklist from the step
statuses, and — for an attendance manager — the working-week engine's own
plan (`pb.shift.pattern.engine.plan`, facts B.3) for this company's active
working weeks over the window, plus the drafts already there. Nothing is
written.

PUBLISHING is the riskiest write of the programme, so it is:
  * company-scoped: every search carries `company_id = env.company` (roster
    rows have no company rule — facts B.5, K2). `publish_shifts` /
    `publish_shifts_notified` are NOT used: they have no company filter;
  * one week per call (`go_live_week`) so the screen shows progress and
    nothing times out on 12,000+ rows; each week runs in its own savepoint,
    so a failed week leaves earlier weeks published and says where it stopped;
  * idempotent and resumable: the search is `state = draft`, so a re-run or a
    "Carry on" publishes only what is left; the engine keeps hand-edited and
    published rows (facts B.3);
  * through the records' own `action_publish()` (the acknowledgement override
    in `pb_ess_workforce` mints its tokens), then that module's
    `_ess_notify_published()` on the same records (it works on a recordset —
    `publish_notify.py:95`). Mail may be off: the counts say so.

THE WINDOW starts TODAY, not on Monday. The board's `make_drafts` snaps the
start back to Monday, and the engine then removes this week's untouched
drafts on days already past (they are "no longer wanted": past days are never
wanted). Calling `plan` / `apply` with first = today keeps the past exactly as
it is. The last day is the Sunday of week N.

Tracking is off for the publish writes (as the engine does for mass rows,
facts K19): the roster's `state` is tracked, and 16,000 chatter lines on
go-live day help nobody.

THE ENGINE RUNS ONE DAY / WEEK AT A TIME (P5c). Until P5c `go_live_start` ran
the engine over the whole window before the first week could tick (28.7 s in
P4, 35.5 s on the P5c machine, for 700 people x 4 weeks). Now `go_live_start`
only checks, re-marks the existing rows and opens the run. The screen makes
the drafts a few days per call (`go_live_make` up to a day; about 1,000 shifts
a call: one day at 700 people, ~2.5 s, the whole week at 120 people) and publishes each week with `go_live_week`, which first
makes whatever is left of its week (`_make_until`; `run.made_to` keeps the
days in order, so the old week-only protocol still works). Why the result is
the same roster as one pass over the window — the argument holds at every
day boundary, so for any split into consecutive day ranges:
  * what the engine wants, keeps, removes, and refuses for leave / holidays /
    the young-worker rule / the overtime ceiling (overtime REQUESTS, not
    roster rows) is decided per person and day. The only thing that links
    two days is the overlap test, and it only looks one day either side;
  * a person on ONE working week is planned day after day, so a day is only
    ever compared with the day before as planned in this pass — in a later
    call that day is an earlier call's row, already made. And with the rows on the next
    day as they are in the database, MINUS the drafts the engine is about to
    remove there: those go first (`Eng.plan` of that one day, its `remove`),
    exactly as one pass removes everything before it judges anything;
  * a person on TWO working weeks on the same day is planned pattern after
    pattern, so a later pattern's Sunday is judged against an earlier
    pattern's next Monday. That order cannot be kept range by range, so then
    (`_live_split_ok` False) the engine runs over the whole window at the
    start, as before.
The holiday / rest-day re-mark does not depend on roster rows
(`hr.shift.planning._pb_day_kinds`), so re-marking the existing rows at the
start and letting new rows mark themselves on create (roster.py) gives the
same day types as re-marking after the engine. Test: `test_p5c.py`.
One knowing difference: a working-week shift the engine refills on a day
already decided by hand is deleted again in the same call. One pass deleted
it only after the WHOLE window was planned, so for the rest of that pass it
could still block the next day's shift (a ghost); range by range, a refill on
a range's last day is gone before the next range is planned. Only a working week
whose shift on that day runs past midnight into the next day's shift can
meet this; the week-by-week answer is the right one.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from .setup import COLOUR_NAME, DEFAULT_COLOUR

_logger = logging.getLogger(__name__)

MAX_LIVE_WEEKS = 12
CHUNK = 1000
SAMPLE_PEOPLE = 6


class WorkforceSetupRun(models.TransientModel):
    """One go-live publish, so the screen can call one week at a time and
    carry on after a failure or a reload. Only its creator may use it."""
    _name = 'pb.workforce.setup.run'
    _description = 'Workforce setup: one roster publish'
    _transient_max_hours = 24.0

    user_id = fields.Many2one('res.users', required=True, index=True,
                              default=lambda self: self.env.user, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True,
                                 default=lambda self: self.env.company, ondelete='cascade')
    first = fields.Date(required=True)
    last = fields.Date(required=True)
    weeks = fields.Json()
    done = fields.Json()
    failed_index = fields.Integer(default=-1)
    failed_text = fields.Char()
    published = fields.Integer()
    people_ids = fields.Json()
    emailed = fields.Integer()
    mail_enabled = fields.Boolean()
    capped = fields.Boolean()
    finished = fields.Boolean()
    made = fields.Json()
    # P5c: the working-week engine runs inside each week's call (only that
    # week's days) instead of once over the whole window at the start
    per_week = fields.Boolean()
    made_to = fields.Date()          # the engine has made every day up to here


class WorkforceSetupGoLive(models.AbstractModel):
    _inherit = 'pb.workforce.setup'

    # ============================================================ helpers
    @api.model
    def _live_n(self, weeks):
        n = self._int(weeks, 4)
        if not 1 <= n <= MAX_LIVE_WEEKS:
            raise UserError(_("Choose 1 to %s weeks.", MAX_LIVE_WEEKS))
        return n

    @api.model
    def _live_window(self, n):
        """(today, monday, last): the window runs from today to the Sunday of
        week n (week 1 = this week)."""
        today = self._today()
        monday = self._monday(today)
        return today, monday, monday + timedelta(days=7 * n - 1)

    @api.model
    def _date_label(self, day, pattern='EEE d MMM'):
        return format_date(self.env, day, date_format=pattern) if day else ''

    @api.model
    def _live_slices(self, monday, n, today):
        out = []
        for i in range(n):
            start = monday + timedelta(days=7 * i)
            frm = max(start, today)
            to = start + timedelta(days=6)
            out.append({'from': fields.Date.to_string(frm), 'to': fields.Date.to_string(to),
                        'from_label': self._date_label(frm), 'to_label': self._date_label(to),
                        'label': _("%(from)s to %(to)s", **{'from': self._date_label(frm), 'to': self._date_label(to)})})
        return out

    @api.model
    def _live_patterns(self):
        """This company's active working weeks (the engine reads members with
        sudo itself; patterns are searched as the caller)."""
        return self.env['pb.shift.pattern'].search(self._company_domain())

    @api.model
    def _roster(self):
        return self.env['hr.shift.planning']            # as the caller (manager)

    @api.model
    def _window_domain(self, first, last, state):
        return self._company_domain() + [('date', '>=', first), ('date', '<=', last), ('state', '=', state)]

    # ============================================================ the checklist
    @api.model
    def _live_steps(self):
        """The six checks above the publish card, from the real statuses.
        `blocking` = cannot publish while it is not ok; the rest are amber
        with a Fix button."""
        shifts = self._shift_rows()
        weeks = self._week_rows()
        status = {s['key']: s for s in self._steps(shifts, weeks)}
        rules_state = self._rules_state()[0]
        out = []

        def add(key, title, ok, text, blocking, fix=None):
            out.append({'key': key, 'title': title, 'ok': bool(ok), 'text': text,
                        'blocking': bool(blocking and not ok), 'fix': fix or key})

        add('shifts', _("Shifts"), bool(shifts),
            status['shifts']['text'] if shifts else _("No shift yet. Add the shifts you run."), True)
        add('weeks', _("Working weeks"), bool(weeks),
            status['weeks']['text'] if weeks else _("No working week yet."), True)
        people = status['people']
        total, missing = people.get('total', 0), people.get('missing', 0)
        if not total or missing >= total:
            add('people', _("Who works what"), False, _("Nobody has a working week yet."), True)
        elif missing:
            add('people', _("Who works what"), False,
                _("1 person has no working week yet and is left out.") if missing == 1 else
                _("%(n)s of %(total)s people have no working week yet and are left out.", n=self._num(missing), total=self._num(total)),
                False)
        else:
            add('people', _("Who works what"), True, people['text'], True)
        if rules_state == 'active':
            add('rules', _("Late and overtime rules"), True, _("Confirmed"), True)
        elif rules_state == 'revision':
            add('rules', _("Late and overtime rules"), False,
                _("A new version is not confirmed yet. The rules in use stay as they are."), False)
        elif rules_state == 'advanced':
            add('rules', _("Late and overtime rules"), False,
                _("More than one set of rules is in use. Check them on the advanced rules screen."), False)
        else:
            add('rules', _("Late and overtime rules"), False,
                _("Not confirmed yet. Shifts are only paid by your rules once they are confirmed."), True)
        hol = status['holidays']
        add('holidays', _("Holidays"), hol['state'] == 'done',
            hol['text'] if hol['state'] == 'done' else _("Not confirmed yet."), False)
        clk = status['clocks']
        if clk['state'] == 'done':
            add('clocks', _("Time clocks"), True, clk['text'], False)
        else:
            later = sum(1 for r in self._clock_rows() if r['state'] in ('waiting', 'quiet', 'attention'))
            add('clocks', _("Time clocks"), False,
                (_("1 clock still needs setting up. You can go live without it.") if later == 1 else
                 _("%s clocks still need setting up. You can go live without them.", later)) if later
                else _("Not confirmed yet."), False)
        return out, people

    @api.model
    def _live_blocked(self):
        steps, _people = self._live_steps()
        sentences = {
            'shifts': _("Add a shift first (step 1)."),
            'weeks': _("Build a working week first (step 2)."),
            'people': _("Give people a working week first (step 3)."),
            'rules': _("Confirm the late and overtime rules first (step 4)."),
        }
        return [sentences[s['key']] for s in steps if s['blocking']]

    # ============================================================ the plan
    @api.model
    def _hand_days(self, first, last):
        """{(employee_id, day)} in the window that already hold a shift NOT
        made by a working week (a one-off from step 3, a shift added on the
        Schedule): the day was decided by hand."""
        rows = self._roster().search(self._company_domain() + [
            ('date', '>=', first), ('date', '<=', last),
            ('state', 'in', ('draft', 'published', 'completed')), ('pb_pattern_id', '=', False)])
        return {(r.employee_id.id, r.date) for r in rows}

    @api.model
    def _live_plan(self, first, last):
        """The engine's plan over [first, last] + the drafts already there.
        Pure read. Returns (numbers, creates, remaining drafts).

        A day that already holds a shift made by hand is never given a
        working-week shift as well: the engine only skips such a day when the
        two shifts overlap in time (facts C), so a night one-off on a day-shift
        day would be "refilled". Those creates are left out here and removed
        again right after the engine runs in `go_live_start`."""
        numbers, creates, remaining = self._live_plan_detail(first, last)
        numbers.pop('removed_rows')
        numbers.pop('skipped_rows')
        return numbers, creates, remaining

    @api.model
    def _live_plan_detail(self, first, last):
        """`_live_plan` plus the rows behind two of its numbers (the drafts
        the engine would take away, and the days left out with their reason),
        so `live_plan` can split them per week."""
        Eng = self.env['pb.shift.pattern.engine']
        Eng._require_maker()
        patterns = self._live_patterns()
        plan = Eng.plan(patterns, first, last) if patterns else None
        creates = plan['creates'] if plan else []
        hand = self._hand_days(first, last) if creates else set()
        kept, by_hand_rows = [], []
        for c in creates:
            if (c['employee_id'], fields.Date.to_date(c['date'])) in hand:
                by_hand_rows.append({'date': fields.Date.to_string(c['date']), 'code': 'by_hand'})
            else:
                kept.append(c)
        by_hand = len(by_hand_rows)
        creates = kept
        Shift = self._roster()
        removed_rows = plan['remove'] if plan else Shift.browse()
        remove_ids = set(removed_rows.ids)
        drafts = Shift.search(self._window_domain(first, last, 'draft'))
        remaining = drafts.filtered(lambda r: r.id not in remove_ids)
        people = {c['employee_id'] for c in creates} | set(remaining.mapped('employee_id').ids)
        numbers = {
            'people': len(people),
            'new_shifts': len(creates),
            'already_planned': len(remaining),
            'shifts': len(creates) + len(remaining),
            'already_published': Shift.search_count(self._window_domain(first, last, 'published')),
            'removed': len(remove_ids),
            'skipped': dict(plan['counts'], **({'by_hand': by_hand} if by_hand else {})) if plan else {},
            'skipped_total': (len(plan['skipped']) + by_hand) if plan else 0,
            'removed_rows': removed_rows,
            'skipped_rows': ((plan['skipped'] if plan else []) + by_hand_rows),
        }
        return numbers, creates, remaining

    @api.model
    def _live_sample(self, creates, remaining, today, monday, last):
        """The first full week of the roster for up to six people (one per
        working week first). Pure read."""
        start = monday if today == monday or monday + timedelta(days=7) > last else monday + timedelta(days=7)
        days = [start + timedelta(days=i) for i in range(7)]
        dayset = set(days)
        cells, week_of = {}, {}
        for c in creates:
            day = fields.Date.to_date(c['date'])
            if day in dayset:
                cells[(c['employee_id'], day)] = c['shift_template_id']
                week_of.setdefault(c['employee_id'], c.get('pb_pattern_id') or 0)
        Shift = self._roster()
        rows = remaining.filtered(lambda r: r.date in dayset) | Shift.search(
            self._company_domain() + [('date', '>=', start), ('date', '<=', days[-1]), ('state', '=', 'published')])
        for r in rows:
            cells.setdefault((r.employee_id.id, r.date), r.shift_template_id.id)
            week_of.setdefault(r.employee_id.id, r.pb_pattern_id.id if 'pb_pattern_id' in r._fields else 0)
        emp_ids = {e for e, _d in cells}
        emps = self.env['hr.employee'].sudo().browse(sorted(emp_ids)).sorted(lambda e: (e.name or '', e.id))
        chosen, seen = [], set()
        for e in emps:
            if week_of.get(e.id) not in seen:
                seen.add(week_of.get(e.id))
                chosen.append(e)
        for e in emps:
            if len(chosen) >= SAMPLE_PEOPLE:
                break
            if e not in chosen:
                chosen.append(e)
        chosen = sorted(chosen[:SAMPLE_PEOPLE], key=lambda e: (e.name or '', e.id))
        templates = self.env['hr.shift.template'].sudo().browse(
            sorted({t for t in cells.values() if t})).exists()
        tmap = {t.id: t for t in templates}
        out_rows = []
        for e in chosen:
            out_days = []
            for d in days:
                t = tmap.get(cells.get((e.id, d)))
                out_days.append({'start': self._hhmm(t.start_hour) if t else False,
                                 'shift_id': t.id if t else False,
                                 'name': t.name if t else '',
                                 'color': COLOUR_NAME.get(t.color, DEFAULT_COLOUR) if t else False})
            out_rows.append({'id': e.id, 'name': e.name or '', 'days': out_days})
        return {
            'days': [{'date': fields.Date.to_string(d), 'label': self._date_label(d, 'EEE d'),
                      'today': d == today} for d in days],
            'rows': out_rows,
            'people': len(emp_ids),
        }

    # ============================================================ the plan, once (P5a)
    @api.model
    def _live_plan_key(self):
        """A cheap fingerprint of everything the plan reads: today, and for
        each table the plan depends on (roster rows, working weeks, their
        days and people, shifts, days off, time off, people) the row count,
        the newest change and the highest id, this company only. The screen
        keeps the 12-week plan while the key stays the same."""
        cid = self.env.company.id
        parts = [fields.Date.to_string(self._today()), str(cid)]
        sources = (
            ('hr.shift.planning', [('company_id', '=', cid)]),
            ('pb.shift.pattern', [('company_id', '=', cid), ('active', 'in', (True, False))]),
            ('pb.shift.pattern.member', [('pattern_id.company_id', '=', cid)]),
            ('pb.shift.pattern.slot', [('pattern_id.company_id', '=', cid)]),
            ('pb.shift.pattern.team', [('pattern_id.company_id', '=', cid)]),
            ('hr.shift.template', ['|', ('company_id', '=', False), ('company_id', '=', cid),
                                   ('active', 'in', (True, False))]),
            ('resource.calendar.leaves', [('company_id', '=', cid)]),
            ('hr.leave', [('employee_company_id', '=', cid)]),
            ('hr.employee', [('company_id', '=', cid), ('active', 'in', (True, False))]),
        )
        for model, domain in sources:
            if model not in self.env:
                continue
            Model = self.env[model].sudo().with_context(active_test=False)
            if 'employee_company_id' in domain[0] and 'employee_company_id' not in Model._fields:
                domain = [('employee_id.company_id', '=', cid)]
            [(count, newest, top)] = Model._read_group(domain, [], ['__count', 'write_date:max', 'id:max'])
            parts.append('%s:%s:%s' % (count, newest or '', top or 0))
        return '|'.join(parts)

    @api.model
    def live_plan(self):
        """Step 7: the working-week plan for the WHOLE window the screen
        offers (12 weeks), worked out once and split per week, so changing
        the week count on screen is a sum of the first N weeks — no second
        pass over every person and day (P4 report: 12 s for 700 people).

        Per week: new shifts, drafts already there, published before, drafts
        the engine would take away, days left out (by reason), and the people
        whose FIRST planned shift falls in that week (so the sum of the first
        N weeks is the number of different people). Two sample weeks: this
        week (used for a 1-week window) and next week (longer windows), the
        same choice `_live_sample` makes. Writes nothing."""
        self._gate_edit()
        key = self._live_plan_key()
        today, monday, last = self._live_window(MAX_LIVE_WEEKS)
        numbers, creates, remaining = self._live_plan_detail(today, last)
        weeks = [{'people': 0, 'new_shifts': 0, 'already_planned': 0, 'shifts': 0,
                  'already_published': 0, 'removed': 0, 'skipped': {}, 'skipped_total': 0}
                 for _i in range(MAX_LIVE_WEEKS)]

        def week_of(day):
            i = (fields.Date.to_date(day) - monday).days // 7
            return i if 0 <= i < MAX_LIVE_WEEKS else None

        first_seen = {}
        for c in creates:
            i = week_of(c['date'])
            if i is None:
                continue
            weeks[i]['new_shifts'] += 1
            weeks[i]['shifts'] += 1
            first_seen[c['employee_id']] = min(first_seen.get(c['employee_id'], i), i)
        for r in remaining:
            i = week_of(r.date)
            if i is None:
                continue
            weeks[i]['already_planned'] += 1
            weeks[i]['shifts'] += 1
            first_seen[r.employee_id.id] = min(first_seen.get(r.employee_id.id, i), i)
        for i in first_seen.values():
            weeks[i]['people'] += 1
        for r in numbers['removed_rows']:
            i = week_of(r.date)
            if i is not None:
                weeks[i]['removed'] += 1
        for row in numbers['skipped_rows']:
            i = week_of(row['date'])
            if i is not None:
                bucket = weeks[i]['skipped']
                bucket[row['code']] = bucket.get(row['code'], 0) + 1
                weeks[i]['skipped_total'] += 1
        published = self._roster()._read_group(
            self._window_domain(today, last, 'published'), ['date:day'], ['__count'])
        for day, count in published:
            i = week_of(day)
            if i is not None:
                weeks[i]['already_published'] += count
        this_week = self._live_sample(creates, remaining, today, monday, monday + timedelta(days=6))
        later = this_week if today == monday else self._live_sample(
            creates, remaining, today, monday, monday + timedelta(days=13))
        return {'key': key, 'weeks': weeks, 'max_weeks': MAX_LIVE_WEEKS,
                'samples': {'one': this_week, 'more': later}}

    @api.model
    def _live_state(self):
        company = self.env.company.sudo()
        to = company.pb_wfs_live_to
        if not to:
            return False
        today = self._today()
        return {
            'on': fields.Date.to_string(company.pb_wfs_live_on) if company.pb_wfs_live_on else False,
            'to': fields.Date.to_string(to),
            'to_label': self._date_label(to, 'EEE d MMM y'),
            'runs_out': to < today + timedelta(days=7),
            'ran_out': to < today,
        }

    @api.model
    def live_check(self, weeks=4, with_plan=True):
        """Step 7: the checklist, and for an attendance manager the plan, the
        first-week sample and the publish label. Writes nothing.

        `with_plan=False` returns the checklist alone (fast): the screen shows
        it at once and asks for the plan — the engine's pass over every
        person and day, ~12 s for 700 people over 4 weeks — straight after."""
        self._gate_read()
        n = self._live_n(weeks)
        today, monday, last = self._live_window(n)
        steps, people = self._live_steps()
        blocked = [s for s in steps if s['blocking']]
        out = {
            'steps': steps,
            'weeks': n,
            'max_weeks': MAX_LIVE_WEEKS,
            'window': {'from': fields.Date.to_string(today), 'to': fields.Date.to_string(last),
                       'from_label': self._date_label(today), 'to_label': self._date_label(last)},
            'slices': self._live_slices(monday, n, today),
            'live': self._live_state(),
            'can_edit': self._can_edit(),
            'blocked': bool(blocked),
            'plan': False,
            'sample': False,
            'can_publish': False,
            'publish_label': '',
            # P5a: everything the screen needs to change the week count
            # without asking again — the twelve weeks it offers, the people
            # count for the "working out" line, and the plan's fingerprint
            'all_slices': self._live_slices(monday, MAX_LIVE_WEEKS, today),
            'headcount': people.get('total', 0),
            'missing': people.get('missing', 0),
            'plan_key': self._live_plan_key() if self._can_edit() else False,
        }
        if not self._can_edit() or not with_plan:
            return out
        numbers, creates, remaining = self._live_plan(today, last)
        out['plan'] = numbers
        out['sample'] = self._live_sample(creates, remaining, today, monday, last)
        missing = people.get('missing', 0)
        out['can_publish'] = not blocked and numbers['shifts'] > 0
        if missing and numbers['people']:
            out['publish_label'] = _("Publish for the %s who are ready", self._num(numbers['people']))
        else:
            out['publish_label'] = _("Publish 1 week") if n == 1 else _("Publish %s weeks", n)
        return out

    # ============================================================ publishing
    @api.model
    def _own_run(self, run_id):
        run = self.env['pb.workforce.setup.run'].search([
            ('id', '=', self._int(run_id)), ('user_id', '=', self.env.uid),
            ('company_id', '=', self.env.company.id)], limit=1)
        if not run:
            raise UserError(_("This publish is no longer there. Press Publish again: shifts already published are skipped."))
        return run

    @api.model
    def _live_split_ok(self, patterns, first, last):
        """Can the engine run one week at a time with exactly the result of
        one pass over [first, last]? Yes unless somebody is on two of these
        working weeks on the same day inside the window (module docstring)."""
        members = self.env['pb.shift.pattern.member'].sudo().search([
            ('pattern_id', 'in', patterns.ids),
            '|', ('date_from', '=', False), ('date_from', '<=', last),
            '|', ('date_to', '=', False), ('date_to', '>=', first)])
        spans = {}
        for m in members:
            if not m.employee_id.active:
                continue
            spans.setdefault(m.employee_id.id, []).append(
                (m.pattern_id.id, max(first, m.date_from or first), min(last, m.date_to or last)))
        for rows in spans.values():
            for k, (pat_a, lo_a, hi_a) in enumerate(rows):
                for pat_b, lo_b, hi_b in rows[k + 1:]:
                    if pat_a != pat_b and max(lo_a, lo_b) <= min(hi_a, hi_b):
                        return False
        return True

    @api.model
    def _live_make(self, patterns, first, last, next_day=None):
        """The working-week engine over [first, last] (`Eng.apply`), then the
        shifts it just refilled on a day already decided by hand go again (see
        `_live_plan`). With `next_day` (the first day of the next week of a
        week-by-week publish), the drafts the engine will take away on that
        day go FIRST, as one pass over the whole window would have removed
        them before judging this week's last day. Returns the counts."""
        Eng = self.env['pb.shift.pattern.engine']
        Shift = self._roster()
        hand = self._hand_days(first, last)
        newest = Shift.sudo().search([], order='id desc', limit=1).id or 0
        removed_ahead = 0
        # only the working weeks' own drafts can be taken away: no such draft
        # on that day, nothing to remove and no second plan to work out
        if next_day and Shift.search_count([
                ('pb_pattern_id', 'in', patterns.ids), ('date', '=', next_day), ('state', '=', 'draft')], limit=1):
            ahead = Eng.plan(patterns, next_day, next_day)['remove']
            if ahead:
                removed_ahead = len(ahead)
                ahead.unlink()
        report = Eng.apply(patterns, first, last)
        # what the engine just made on a day already decided by hand goes
        # again; only rows made by THIS call
        extra = Shift.search(self._company_domain() + [
            ('id', '>', newest), ('date', '>=', first), ('date', '<=', last),
            ('state', '=', 'draft'), ('pb_pattern_id', '!=', False)]).filtered(
                lambda r: (r.employee_id.id, r.date) in hand)
        if extra:
            extra.unlink()
        return {'created': report.get('created', 0) - len(extra),
                'removed': report.get('removed', 0) + removed_ahead,
                'skipped': report.get('skipped_total', 0) + len(extra)}

    @api.model
    def go_live_start(self, weeks=4):
        """Check, re-mark holiday and rest-day shifts already on the roster,
        and open a run the screen publishes week by week. The working-week
        engine runs inside each week's call (P5c); only when somebody is on
        two working weeks at once does it run here over the whole window."""
        self._gate_edit()
        n = self._live_n(weeks)
        blocked = self._live_blocked()
        if blocked:
            raise UserError(blocked[0])
        today, monday, last = self._live_window(n)
        patterns = self._live_patterns()
        if patterns:
            self.env['pb.shift.pattern.engine']._require_maker()      # as `Eng.apply` here did before P5c
        per_week = bool(patterns) and self._live_split_ok(patterns, today, last)
        made = {'created': 0, 'removed': 0, 'skipped': 0}
        if patterns and not per_week:
            made = self._live_make(patterns, today, last)
        remark = self.remark_days(today)
        slices = self._live_slices(monday, n, today)
        run = self.env['pb.workforce.setup.run'].create({
            'first': today, 'last': last, 'weeks': slices, 'done': [], 'people_ids': [], 'made': made,
            'per_week': per_week, 'made_to': today - timedelta(days=1),
        })
        return {'run_id': run.id, 'weeks': slices, 'made': made, 'remark': remark.get('summary') or '',
                'per_week': per_week}

    @api.model
    def _publish_chunk(self, rows):
        """One chunk through the records' own publish (the seam a test can
        break on purpose)."""
        rows.action_publish()

    @api.model
    def _week_failed(self, run, i, wk, error):
        self.env.invalidate_all()
        if isinstance(error, (UserError, AccessError)) and error.args:
            why = str(error.args[0])
        else:
            _logger.exception('WFSETUP go-live: week %s of run %s failed', i + 1, run.id)
            why = _("Something went wrong on the server.")
        sentence = _("Week %(n)s (%(label)s) was not published: %(why)s The weeks before it are published. Press Carry on to try this week again.",
                     n=i + 1, label=wk.get('label', ''), why=why.rstrip('.') + '.')
        run.write({'failed_index': i, 'failed_text': sentence[:500]})
        return {'ok': False, 'index': i, 'sentence': sentence, 'total': run.published}

    @api.model
    def _make_until(self, run, until):
        """Week-by-week runs: make every day after `run.made_to` up to `until`
        (never past the run). Days are made in order, so each day is judged
        against the day before as already made (module docstring). Nothing to
        do for a one-pass run or a day already made; a "Carry on" after a
        failed publish does not run the engine again, as before P5c."""
        until = min(fields.Date.to_date(until), run.last)
        done_to = run.made_to or (run.first - timedelta(days=1))
        if not run.per_week or until <= done_to:
            return False
        # never earlier than today: the engine drops untouched drafts on past
        # days, and a publish may run past midnight
        first = max(done_to + timedelta(days=1), self._today())
        next_day = until + timedelta(days=1) if until < run.last else None
        made = {'created': 0, 'removed': 0, 'skipped': 0}
        patterns = self._live_patterns()
        if patterns and first <= until:
            with self.env.cr.savepoint():
                made = self._live_make(patterns, first, until, next_day)
                self.env.flush_all()
        total = dict(run.made or {})
        for key, value in made.items():
            total[key] = int(total.get(key) or 0) + value
        run.write({'made': total, 'made_to': until})
        return True

    @api.model
    def go_live_make(self, run_id, index, day=None):
        """Week-by-week runs: make the drafts of week `index` up to `day` (the
        whole week without one). The screen calls it day by day so the
        progress moves within seconds on a big company; `go_live_week` makes
        whatever is left of its week itself. A failure is reported like a
        failed week and rolled back whole."""
        self._gate_edit()
        run = self._own_run(run_id)
        slices = run.weeks or []
        i = self._int(index, -1)
        if not 0 <= i < len(slices):
            raise UserError(_("There is no such week in this publish."))
        wk = slices[i]
        until = fields.Date.to_date(day) if day else fields.Date.to_date(wk['to'])
        if not until or until > fields.Date.to_date(wk['to']):
            until = fields.Date.to_date(wk['to'])
        try:
            made = self._make_until(run, until)
        except Exception as error:                      # noqa: BLE001 — reported, rolled back by its savepoint
            return self._week_failed(run, i, wk, error)
        return {'ok': True, 'index': i, 'made': bool(made),
                'made_to': fields.Date.to_string(run.made_to) if run.made_to else False}

    @api.model
    def go_live_week(self, run_id, index):
        """Make (P5c) and publish week `index` of the run: this company's
        DRAFT rows in that week, in chunks, in one savepoint. A failure rolls
        this week's publish back, keeps earlier weeks and says where it
        stopped; the drafts made for the week stay drafts, as before P5c."""
        self._gate_edit()
        run = self._own_run(run_id)
        slices = run.weeks or []
        i = self._int(index, -1)
        if not 0 <= i < len(slices):
            raise UserError(_("There is no such week in this publish."))
        done = list(run.done or [])
        if i in done:
            return {'ok': True, 'index': i, 'published': 0, 'total': run.published, 'already': True}
        wk = slices[i]
        try:
            self._make_until(run, wk['to'])
        except Exception as error:                      # noqa: BLE001 — reported, rolled back by its savepoint
            return self._week_failed(run, i, wk, error)
        Shift = self._roster().with_context(tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
        rows = Shift.search(self._window_domain(wk['from'], wk['to'], 'draft'), order='date, employee_id, id')
        try:
            with self.env.cr.savepoint():
                for k in range(0, len(rows), CHUNK):
                    self._publish_chunk(rows[k:k + CHUNK])
                self.env.flush_all()
        except Exception as error:                      # noqa: BLE001 — reported, never half-applied
            return self._week_failed(run, i, wk, error)
        notify = {}
        if rows and hasattr(rows, '_ess_notify_published'):
            notify = rows.sudo()._ess_notify_published() or {}
        people = sorted(set(run.people_ids or []) | set(rows.mapped('employee_id').ids))
        run.write({
            'done': done + [i],
            'failed_index': -1,
            'failed_text': False,
            'published': run.published + len(rows),
            'people_ids': people,
            'emailed': run.emailed + int(notify.get('emailed') or 0),
            'mail_enabled': bool(notify.get('mail_enabled', run.mail_enabled)),
            'capped': run.capped or bool(notify.get('capped')),
        })
        return {'ok': True, 'index': i, 'published': len(rows), 'total': run.published,
                'people': len(people), 'notify': notify}

    @api.model
    def go_live_finish(self, run_id):
        """Every week published: write the company's live dates and return
        the totals for the finish card."""
        self._gate_edit()
        run = self._own_run(run_id)
        done = set(run.done or [])
        for i in range(len(run.weeks or [])):
            if i not in done:
                raise UserError(_("Week %s is not published yet. Press Carry on.", i + 1))
        company = self.env.company.sudo()
        before = company.pb_wfs_live_to
        vals = {'pb_wfs_live_to': max(company.pb_wfs_live_to or run.last, run.last)}
        if not company.pb_wfs_live_on:
            vals['pb_wfs_live_on'] = run.first
        company.write(vals)
        emps = self.env['hr.employee'].sudo().browse(run.people_ids or []).exists()
        # the same two channels `_ess_notify_published` counts: a login, or a work email
        portal = emps.filtered(lambda e: e.user_id and e.user_id.active)
        no_channel = emps.filtered(lambda e: not (e.user_id and e.user_id.active) and not (e.work_email or '').strip())
        run.write({'finished': True})
        n, p = run.published, len(emps)
        if n and before:
            summary = _("%(n)s more shifts published for %(p)s people. The roster now runs to %(to)s.",
                        n=self._num(n), p=self._num(p), to=self._date_label(vals['pb_wfs_live_to']))
        elif n:
            summary = _("%(n)s shifts are on the roster for %(p)s people, from %(from)s to %(to)s.",
                        n=self._num(n), p=self._num(p),
                        **{'from': self._date_label(run.first), 'to': self._date_label(run.last)})
        else:
            summary = _("Everything up to %s was already published. Nothing new to publish.", self._date_label(run.last))
        return {
            'published': n,
            'people': p,
            'from': fields.Date.to_string(run.first),
            'to': fields.Date.to_string(run.last),
            'live': self._live_state(),
            'portal': len(portal),
            'no_channel': len(no_channel),
            'emailed': run.emailed,
            'mail_enabled': run.mail_enabled,
            'capped': run.capped,
            'made': run.made or {},
            'summary': summary,
        }

    @api.model
    def go_live_resume(self):
        """The latest unfinished publish of this person in this company, so a
        reload can carry on where it stopped (False when there is none)."""
        self._gate_read()
        if not self._can_edit():
            return False
        run = self.env['pb.workforce.setup.run'].search([
            ('user_id', '=', self.env.uid), ('company_id', '=', self.env.company.id),
            ('finished', '=', False)], order='id desc', limit=1)
        if not run:
            return False
        return {'run_id': run.id, 'weeks': run.weeks or [], 'done': run.done or [],
                'failed_index': run.failed_index, 'failed_text': run.failed_text or '',
                'published': run.published, 'per_week': run.per_week,
                'made_to': fields.Date.to_string(run.made_to) if run.made_to else False}

    # ============================================================ statuses (§2.4)
    @api.model
    def _live_step(self):
        live = self._live_state()
        if not live:
            return {'state': 'todo', 'text': _("Last step")}
        to = fields.Date.to_date(live['to'])
        if live['ran_out']:
            return {'state': 'warn', 'text': _("The roster ran out on %s", self._date_label(to))}
        if live['runs_out']:
            return {'state': 'warn', 'text': _("The roster runs out on %s", self._date_label(to))}
        return {'state': 'done', 'text': _("Roster published up to %s", self._date_label(to))}

    @api.model
    def _steps(self, shifts, weeks):
        steps = super()._steps(shifts, weeks)
        extra = {'holidays': self._holidays_step(), 'clocks': self._clocks_step(), 'live': self._live_step()}
        for step in steps:
            if step['key'] in extra:
                step.update(extra[step['key']])
        return steps
