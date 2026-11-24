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
                _("%(n)s of %(total)s people have no working week yet and are left out.", n=missing, total=total),
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
            out['publish_label'] = _("Publish for the %s who are ready", '{:,}'.format(numbers['people']))
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
    def go_live_start(self, weeks=4):
        """Make the roster for the window (the engine, once), mark holiday and
        rest-day shifts, and open a run the screen publishes week by week."""
        self._gate_edit()
        n = self._live_n(weeks)
        blocked = self._live_blocked()
        if blocked:
            raise UserError(blocked[0])
        today, monday, last = self._live_window(n)
        Eng = self.env['pb.shift.pattern.engine']
        patterns = self._live_patterns()
        made = {'created': 0, 'removed': 0, 'skipped': 0}
        if patterns:
            Shift = self._roster()
            hand = self._hand_days(today, last)
            newest = Shift.sudo().search([], order='id desc', limit=1).id or 0
            report = Eng.apply(patterns, today, last)
            # what the engine just made on a day already decided by hand goes
            # again (see `_live_plan`); only rows made by THIS call
            extra = Shift.search(self._company_domain() + [
                ('id', '>', newest), ('date', '>=', today), ('date', '<=', last),
                ('state', '=', 'draft'), ('pb_pattern_id', '!=', False)]).filtered(
                    lambda r: (r.employee_id.id, r.date) in hand)
            if extra:
                extra.unlink()
            made = {'created': report.get('created', 0) - len(extra), 'removed': report.get('removed', 0),
                    'skipped': report.get('skipped_total', 0) + len(extra)}
        remark = self.remark_days(today)
        slices = self._live_slices(monday, n, today)
        run = self.env['pb.workforce.setup.run'].create({
            'first': today, 'last': last, 'weeks': slices, 'done': [], 'people_ids': [], 'made': made,
        })
        return {'run_id': run.id, 'weeks': slices, 'made': made, 'remark': remark.get('summary') or ''}

    @api.model
    def _publish_chunk(self, rows):
        """One chunk through the records' own publish (the seam a test can
        break on purpose)."""
        rows.action_publish()

    @api.model
    def go_live_week(self, run_id, index):
        """Publish week `index` of the run: this company's DRAFT rows in that
        week, in chunks, in one savepoint. A failure rolls this week back,
        keeps earlier weeks and says where it stopped."""
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
        Shift = self._roster().with_context(tracking_disable=True, mail_notrack=True, mail_create_nolog=True)
        rows = Shift.search(self._window_domain(wk['from'], wk['to'], 'draft'), order='date, employee_id, id')
        try:
            with self.env.cr.savepoint():
                for k in range(0, len(rows), CHUNK):
                    self._publish_chunk(rows[k:k + CHUNK])
                self.env.flush_all()
        except Exception as error:                      # noqa: BLE001 — reported, never half-applied
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
                        n='{:,}'.format(n), p='{:,}'.format(p), to=self._date_label(vals['pb_wfs_live_to']))
        elif n:
            summary = _("%(n)s shifts are on the roster for %(p)s people, from %(from)s to %(to)s.",
                        n='{:,}'.format(n), p='{:,}'.format(p),
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
                'published': run.published}

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
