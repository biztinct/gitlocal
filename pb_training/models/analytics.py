# -*- coding: utf-8 -*-
"""`pb.training.analytics` — what the training actually did, in numbers.

TWO RATIOS AND EVERYTHING ELSE IS CONTEXT. A training programme is judged on
whether people FINISH what they were put on (the completion ratio) and whether
they PASS the test at the end of it (the performance ratio). Everything else on
this lens — the overdue count, the splits by department, course and reason, the
week-by-week trend — is there to say WHERE the two ratios come from, and is
drawn underneath them rather than beside them.

THE COHORT IS EVERY ASSIGNMENT HANDED OUT INSIDE THE RANGE, by `assigned_on`.
That is what makes the figures comparable to each other: "we set ninety courses
and sixty-one are finished" is about the same ninety, so a reader can do sums
across the tiles. A cohort defined by completion date could not answer "how
much of what we set has been done" at all.

EXCUSED IS OUT OF THE BOTTOM, NOT COUNTED AS A FAILURE. Somebody whose manager
agreed they could have longer has not failed to finish; counting them against
the ratio would make agreeing an extension look like a drop in performance,
which is how a number teaches people to stop agreeing extensions.

COMPANY-SCOPED AND NEVER SUDO IN A READ. Every search below carries
`company_id in self.env.companies.ids`, written out (R89 reached from the
Explorer's own rule): the one thing a reader must not be able to do is add up
another company's training.

AN EMPTY RANGE SAYS SO IN WORDS (R27/R54). A range with nothing in it draws a
sentence with the dates in it, never eight zeros — a screen of zeros is how a
working feature gets reported as broken.
"""

import base64
import io
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .training_common import (
    ASSIGN_REASON_LABEL, GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, as_id,
    counted, fold, money_words,
)

_logger = logging.getLogger(__name__)

#: How many weeks of trend a chart can show before it is a smear. Thirteen is
#: a quarter, which is the longest stretch anybody reads bar by bar.
TREND_WEEKS = 13


class PbTrainingAnalytics(models.AbstractModel):
    _name = 'pb.training.analytics'
    _description = 'Payobook Training — the numbers'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_training: a numbers read failed', exc_info=True)
            return default

    @api.model
    def _can_read(self):
        """ITS OWN GATE AND NOT THE HUB'S (R97).

        A data analyst holds no training group and a trainer holds no analytics
        group, so this lens's readers are genuinely not the Insights hub's
        usual readers. Anybody in the training ladder, plus a system
        administrator.
        """
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN) or user._is_admin())

    @api.model
    def _require(self):
        if not self._can_read():
            raise AccessError(_(
                "The training numbers are for the training team. Ask your HR "
                "administrator to add you to it."))

    # =====================================================================
    #  the range
    # =====================================================================
    @api.model
    def _range(self, date_from=None, date_to=None):
        """(from, to) as real dates, whatever the browser sent.

        THE SERVER'S CLOCK AND NEVER `context_today` (R154): a range that
        decides what is in a report must not change with who is looking at it.
        """
        today = fields.Date.today()
        try:
            end = fields.Date.to_date(date_to) if date_to else today
        except (TypeError, ValueError):
            end = today
        try:
            start = fields.Date.to_date(date_from) if date_from \
                else end - timedelta(days=90)
        except (TypeError, ValueError):
            start = end - timedelta(days=90)
        if start > end:
            start, end = end, start
        return start, end

    def _domain(self, start, end, filters=None):
        filters = filters or {}
        domain = [
            ('company_id', 'in', self.env.companies.ids),
            ('assigned_on', '>=', start),
            ('assigned_on', '<=', end),
        ]
        if filters.get('department_id'):
            domain.append(('employee_id.department_id', 'child_of',
                           as_id(filters['department_id'])))
        if filters.get('channel_id'):
            domain.append(('channel_id', '=', as_id(filters['channel_id'])))
        if filters.get('reason'):
            domain.append(('reason', '=', filters['reason']))
        return domain

    # =====================================================================
    #  the whole lens, in one read
    # =====================================================================
    @api.model
    def get_numbers(self, date_from=None, date_to=None, filters=None):
        if not self._can_read():
            return {'allowed': False, 'empty': True, 'tiles': []}
        start, end = self._range(date_from, date_to)
        filters = filters or {}
        rows = self.env['pb.training.assignment'].sudo().search(
            self._domain(start, end, filters))
        # The states are READ, so they are brought up to date first: a report
        # that counts "Not started" over somebody who finished last night is a
        # report nobody trusts twice.
        rows._refresh()
        payload = {
            'allowed': True,
            'from': fields.Date.to_string(start),
            'to': fields.Date.to_string(end),
            'total': len(rows),
            'empty': not rows,
            'headline': '',
            'tiles': [],
            'by_department': [],
            'by_course': [],
            'by_reason': [],
            'trend': [],
            'claims': {},
            'lists': self._safe(lambda: self._lists(), default={}),
            'reasons': [{'key': k, 'label': v}
                        for k, v in ASSIGN_REASON_LABEL.items()],
        }
        if not rows:
            payload['headline'] = _(
                "Nothing was set between %(from)s and %(to)s. Widen the dates, "
                "or put somebody on a course and the figures start here.",
                **{'from': fields.Date.to_string(start),
                   'to': fields.Date.to_string(end)})
            payload['claims'] = self._safe(
                lambda: self._claims(start, end, filters), default={})
            return payload
        core = self._safe(lambda: self._core(rows), default={})
        payload.update({
            'tiles': self._tiles(core),
            'core': core,
            'headline': self._headline(core),
            'by_department': self._safe(
                lambda: self._split(rows, 'department'), default=[]),
            'by_course': self._safe(lambda: self._split(rows, 'course'),
                                    default=[]),
            'by_reason': self._safe(lambda: self._split(rows, 'reason'),
                                    default=[]),
            'trend': self._safe(lambda: self._trend(rows, start, end),
                                default=[]),
            'claims': self._safe(lambda: self._claims(start, end, filters),
                                 default={}),
        })
        return payload

    # ------------------------------------------------------------ the ratios
    def _core(self, rows):
        """Every number the lens shows, computed ONCE.

        The split tables and the spreadsheet all come back here, so a
        department's completion ratio and the headline's can never be worked
        out two different ways.
        """
        today = fields.Date.today()
        counted_rows = rows.filtered(lambda r: r.state != 'excused')
        done = counted_rows.filtered(lambda r: r.state == 'done')
        overdue = rows.filtered(lambda r: r.state == 'overdue')
        late_days = [max((today - r.due_date).days, 0)
                     for r in overdue if r.due_date]
        scored = done.filtered(lambda r: r.score)
        # WHO SAT A TEST AND WHO PASSED IT. `_progress()` is E1's own single
        # answer to "how far has this person got", so a pass here is the same
        # pass the employee's own page shows.
        taken = passed = 0
        for row in rows:
            try:
                facts = row._progress()
            except Exception:               # noqa: BLE001 — one row, one grave
                continue
            if facts['test'] == 'passed':
                taken += 1
                passed += 1
            elif facts['test'] == 'failed':
                taken += 1
        return {
            'total': len(rows),
            'counted': len(counted_rows),
            'excused': len(rows) - len(counted_rows),
            'done': len(done),
            'overdue': len(overdue),
            'open': len(rows.filtered(
                lambda r: r.state in ('assigned', 'in_progress'))),
            'completion': int(round(100.0 * len(done) / len(counted_rows)))
            if counted_rows else None,
            'taken': taken,
            'passed': passed,
            'performance': int(round(100.0 * passed / taken)) if taken
            else None,
            'mean_score': round(sum(scored.mapped('score')) / len(scored), 1)
            if scored else None,
            'mean_late': round(sum(late_days) / len(late_days), 1)
            if late_days else None,
        }

    def _tiles(self, core):
        """The six numbers, in the order somebody asks for them."""
        pct = lambda v: '—' if v is None else '%s%%' % v      # noqa: E731
        return [
            {'key': 'completion', 'label': _('Finished'),
             'value': pct(core.get('completion')), 'icon': 'checkCheck',
             'sub': _("%(done)s of %(n)s", done=core.get('done', 0),
                      n=core.get('counted', 0))},
            {'key': 'performance', 'label': _('Passed the test'),
             'value': pct(core.get('performance')), 'icon': 'target',
             'sub': _("%(passed)s of %(n)s who sat one",
                      passed=core.get('passed', 0), n=core.get('taken', 0))},
            {'key': 'overdue', 'label': _('Past their date'),
             'value': core.get('overdue', 0), 'icon': 'alert',
             'sub': _("%s days late on average", core['mean_late'])
             if core.get('mean_late') else _('none are late')},
            {'key': 'open', 'label': _('Still to do'),
             'value': core.get('open', 0), 'icon': 'clock',
             'sub': _('in hand, not yet past their date')},
            {'key': 'score', 'label': _('Average score'),
             'value': '—' if core.get('mean_score') is None
             else '%s%%' % core['mean_score'], 'icon': 'barChart',
             'sub': _('of the tests that were passed')},
            {'key': 'excused', 'label': _('More time agreed'),
             'value': core.get('excused', 0), 'icon': 'sunrise',
             'sub': _('left out of the finished figure')},
        ]

    def _headline(self, core):
        """One sentence, first, so nobody has to do the arithmetic (R113)."""
        bits = [_("%(n)s %(word)s set", n=core.get('total', 0),
                  word=counted(core.get('total', 0), _('course'),
                               _('courses')))]
        if core.get('completion') is not None:
            bits.append(_("%s%% finished", core['completion']))
        if core.get('performance') is not None:
            bits.append(_("%s%% passed the test", core['performance']))
        if core.get('overdue'):
            bits.append(counted(core['overdue'], _('1 is past its date'),
                                _('%s are past their date')
                                % core['overdue']))
        return ' · '.join(bits)

    # ------------------------------------------------------------ the splits
    def _split(self, rows, key):
        """One table. EVERY SPLIT ADDS UP TO THE TOTAL, including the gap.

        A department table that quietly drops the people with no department is
        a table whose rows do not sum to the headline, and nothing on the
        screen says why. So an empty value becomes a NAMED row.
        """
        buckets = {}
        for row in rows:
            if key == 'department':
                name = row.employee_id.sudo().department_id.name \
                    or _('No department')
            elif key == 'course':
                name = row.channel_id.sudo().name or _('A course that is gone')
            else:
                name = ASSIGN_REASON_LABEL.get(row.reason, _('Not said'))
            buckets.setdefault(name, self.env['pb.training.assignment'])
            buckets[name] |= row
        out = []
        for name, group in buckets.items():
            core = self._core(group)
            out.append({
                'name': name,
                'total': core['total'],
                'done': core['done'],
                'overdue': core['overdue'],
                'completion': core['completion'],
                'performance': core['performance'],
            })
        # PROBLEM FIRST, then size: the row with the most overdue is the one
        # somebody has to act on.
        return sorted(out, key=lambda r: (-r['overdue'], -r['total'],
                                          fold(r['name'])))

    def _trend(self, rows, start, end):
        """Set versus finished, per ISO week, oldest first.

        BUCKETED BY THE MONDAY of each week rather than by ISO week NUMBER: a
        range that crosses a new year has two week 1s, and a chart with two
        bars labelled the same is a chart that is wrong in a way nobody spots.
        """
        weeks = {}

        def monday(day):
            return day - timedelta(days=day.weekday())

        cursor = monday(start)
        while cursor <= end and len(weeks) <= TREND_WEEKS * 4:
            weeks[cursor] = {'key': fields.Date.to_string(cursor),
                             'label': cursor.strftime('%d %b'),
                             'set': 0, 'done': 0}
            cursor = cursor + timedelta(days=7)
        for row in rows:
            if row.assigned_on:
                bucket = weeks.get(monday(row.assigned_on))
                if bucket:
                    bucket['set'] += 1
            if row.state == 'done' and row.completed_on:
                bucket = weeks.get(monday(row.completed_on))
                if bucket:
                    bucket['done'] += 1
        out = [weeks[k] for k in sorted(weeks)]
        return out[-TREND_WEEKS:]

    # ------------------------------------------------------------ the money
    def _claims(self, start, end, filters=None):
        """What the training cost, over the same range. Empty is an answer."""
        if 'pb.training.claim' not in self.env:
            return {}
        domain = [
            ('company_id', 'in', self.env.companies.ids),
            ('paid_on', '>=', start), ('paid_on', '<=', end),
        ]
        if (filters or {}).get('department_id'):
            domain.append(('employee_id.department_id', 'child_of',
                           as_id(filters['department_id'])))
        rows = self.env['pb.training.claim'].sudo().search(domain)
        agreed = rows.filtered(lambda r: r.state == 'approved')
        currency = (agreed[:1].currency_id or rows[:1].currency_id
                    or self.env.company.currency_id)
        total = sum(agreed.mapped('amount'))
        return {
            'claims': len(rows),
            'agreed': len(agreed),
            'waiting': len(rows.filtered(lambda r: r.state == 'submitted')),
            'refused': len(rows.filtered(lambda r: r.state == 'refused')),
            'paid': len(agreed.filtered(lambda r: r.fulfilment == 'paid')),
            'total': total,
            'total_words': money_words(self.env, total, currency),
            'currency': currency.name or '',
        }

    def _lists(self):
        """The filter bar's own lists, built from the data that EXISTS (R27).

        A filter that matches nothing is a broken promise, so the courses
        offered are the courses somebody has actually been put on and the
        departments are the departments those people are in.
        """
        rows = self.env['pb.training.assignment'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)])
        courses, departments = {}, {}
        for row in rows:
            channel = row.channel_id.sudo()
            if channel:
                courses[channel.id] = channel.name or ''
            dept = row.employee_id.sudo().department_id
            if dept:
                departments[dept.id] = dept.name or ''
        return {
            'courses': sorted(
                [{'id': k, 'name': v} for k, v in courses.items()],
                key=lambda r: fold(r['name'])),
            'departments': sorted(
                [{'id': k, 'name': v} for k, v in departments.items()],
                key=lambda r: fold(r['name'])),
        }

    # =====================================================================
    #  the spreadsheet
    # =====================================================================
    @api.model
    def export_xlsx(self, date_from=None, date_to=None, filters=None):
        """The same payload the screen draws, as a workbook.

        BUILT FROM THE SAME READ AND NEVER FROM A SECOND QUERY (the precedent
        `pb_budget/models/budget_export.py:73` set): a spreadsheet that
        disagrees with the board it came off is worse than no spreadsheet.

        It comes back as base64 and the browser saves it without leaving the
        page. No attachment is left behind — an export is a copy somebody
        takes away, not a record, and a company's training figures sitting in
        a table nobody remembers to clear is a leak with a filename.
        """
        self._require()
        board = self.get_numbers(date_from, date_to, filters)
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise UserError(_(
                "This system cannot build spreadsheets at the moment. Ask an "
                "administrator to look at it."))

        wb = openpyxl.Workbook()
        head = Font(bold=True, color='FFFFFF')
        fill = PatternFill('solid', fgColor='6355C7')
        bold = Font(bold=True)

        def sheet(ws, title, columns):
            ws.title = title[:31]
            for i, label in enumerate(columns, start=1):
                cell = ws.cell(row=1, column=i, value=label)
                cell.font = head
                cell.fill = fill
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
            for i in range(1, len(columns) + 1):
                ws.column_dimensions[get_column_letter(i)].width = \
                    30 if i == 1 else 16
            ws.freeze_panes = 'A2'
            return ws

        # ---- the summary -------------------------------------------------
        ws = sheet(wb.active, _('Summary'), [_('Figure'), _('Value')])
        ws.cell(row=2, column=1, value=_('Range')).font = bold
        ws.cell(row=2, column=2,
                value='%s → %s' % (board['from'], board['to']))
        core = board.get('core') or {}
        lines = [
            (_('Courses set'), core.get('total', 0)),
            (_('Finished'), core.get('done', 0)),
            (_('Finished %'), core.get('completion')),
            (_('Sat the test'), core.get('taken', 0)),
            (_('Passed the test'), core.get('passed', 0)),
            (_('Passed %'), core.get('performance')),
            (_('Average score'), core.get('mean_score')),
            (_('Past their date'), core.get('overdue', 0)),
            (_('Days late on average'), core.get('mean_late')),
            (_('More time agreed'), core.get('excused', 0)),
        ]
        claims = board.get('claims') or {}
        if claims:
            lines += [
                (_('Claims made'), claims.get('claims', 0)),
                (_('Claims agreed'), claims.get('agreed', 0)),
                (_('What was agreed'), claims.get('total', 0)),
                (_('Currency'), claims.get('currency', '')),
            ]
        for row, (label, value) in enumerate(lines, start=3):
            ws.cell(row=row, column=1, value=label).font = bold
            ws.cell(row=row, column=2,
                    value='—' if value is None else value)

        # ---- the three splits --------------------------------------------
        columns = [_('Name'), _('Set'), _('Finished'), _('Past their date'),
                   _('Finished %'), _('Passed %')]
        for key, title in (('by_department', _('By department')),
                           ('by_course', _('By course')),
                           ('by_reason', _('Why'))):
            tab = sheet(wb.create_sheet(), title, columns)
            for row, line in enumerate(board.get(key) or [], start=2):
                for col, value in enumerate(
                        [line['name'], line['total'], line['done'],
                         line['overdue'],
                         '—' if line['completion'] is None
                         else line['completion'],
                         '—' if line['performance'] is None
                         else line['performance']], start=1):
                    tab.cell(row=row, column=col, value=value)

        # ---- week by week -------------------------------------------------
        tab = sheet(wb.create_sheet(), _('Week by week'),
                    [_('Week beginning'), _('Set'), _('Finished')])
        for row, line in enumerate(board.get('trend') or [], start=2):
            tab.cell(row=row, column=1, value=line['key'])
            tab.cell(row=row, column=2, value=line['set'])
            tab.cell(row=row, column=3, value=line['done'])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return {
            'ok': True,
            'file_b64': base64.b64encode(out.read()).decode(),
            'filename': _('Training %(from)s to %(to)s.xlsx',
                          **{'from': board['from'], 'to': board['to']}),
            'mimetype': ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'),
            'rows': board.get('total', 0),
        }
