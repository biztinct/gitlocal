# -*- coding: utf-8 -*-
"""`pb.goals.analytics` — the Goals lens on Insights, and the spreadsheet.

FIVE QUESTIONS, AND THE ANSWERS ARE NOT INTERCHANGEABLE.

  1. **Is anybody writing goals?** How many sheets, how many agreed, and how
     long each rung took.
  2. **Is anybody talking about them?** Check-ins done against check-ins owed
     — which is MANAGER COMPLIANCE, and is the number this whole lens exists
     for. A goal year where nobody has a monthly conversation is a goal year
     that is not happening, and nothing else on this screen would say so.
  3. **Is the work moving?** Mean progress across every key result, and how
     many goals have been marked complete.
  4. **Is the plan still the plan?** How many change requests, and what
     happened to them.
  5. **What did the year come out at?** The score distribution by band.

THE COMPLIANCE FIGURE IS PER MANAGER AND THAT IS THE POINT. A company average
of 78% tells nobody what to do; "four of Lam's eleven people have not had a
conversation since June" is a sentence somebody can act on this afternoon.

COMPANY-SCOPED AND NEVER SUDO AROUND A READ. Every search carries
`company_id in self.env.companies.ids` written out (R89), and `sudo()` appears
only after that clause is already in the domain — for names behind payroll
groups (R56) and for the relational hops a department name needs.

THE SPREADSHEET IS BUILT FROM THE SAME READ THE SCREEN DREW (the precedent
`pb_budget/models/budget_export.py:73` set, followed by `pb_training`). A second
query is a second opinion, and the day the two disagree nobody can tell which
one is the report.

EMPTY IS A STATE AND IT GETS A SENTENCE (R27), not a grid of noughts. A goal
year nobody has written anything on yet is the ordinary first week of a
roll-out, and a screen of zeroes over it reads as a broken screen.
"""

import base64
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .goals_common import ALL_GROUPS, CHANGE_KIND_LABEL, as_id, counted

_logger = logging.getLogger(__name__)


class PbGoalsAnalytics(models.AbstractModel):
    _name = 'pb.goals.analytics'
    _description = 'Goals: the numbers'

    # ------------------------------------------------------------- plumbing
    @api.model
    def _safe(self, label, fn, default=None):
        try:
            return fn()
        except Exception:               # noqa: BLE001 — one probe, one guard
            _logger.warning('pb_goals: the numbers could not work out %s',
                            label, exc_info=True)
            return default

    @api.model
    def _can_read(self):
        """ITS OWN GATE AND NOT THE HUB'S (R97).

        AND IT IS THE HR GATE, unlike the board's. The board is about one
        person or one team and a line manager is entitled to their own; this
        is the whole company's goal year with every manager's compliance
        figure on it, which is a management report and not a team view.
        """
        user = self.env.user
        return any(user.has_group(group) for group in ALL_GROUPS) \
            or user._is_admin()

    @api.model
    def _require(self):
        if not self._can_read():
            raise AccessError(_(
                "The goal numbers are for the HR team. Ask your HR "
                "administrator to add you to it."))

    @api.model
    def _cycles(self):
        rows = self.env['pb.goal.cycle'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)],
            order='date_start desc', limit=12)
        out = [{'id': cycle.id, 'name': cycle.name or '',
                'state': cycle.state,
                'from': str(cycle.date_start or ''),
                'to': str(cycle.date_end or ''),
                'company': cycle.company_id.name or ''} for cycle in rows]
        # The open year at the front, then the rest newest first — the same
        # stable partition the board uses, so the two screens open on the same
        # year (found live on the board: it opened on next year's empty one).
        return ([c for c in out if c['state'] == 'open']
                + [c for c in out if c['state'] != 'open'])

    @api.model
    def _pick_cycle(self, cycle_id, cycles):
        if cycle_id:
            return int(cycle_id)
        return cycles[0]['id'] if cycles else 0

    @api.model
    def _domain(self, cycle_id, filters):
        filters = dict(filters or {})
        domain = [('company_id', 'in', self.env.companies.ids)]
        if cycle_id:
            domain.append(('cycle_id', '=', int(cycle_id)))
        if filters.get('department_id'):
            domain.append(('department_id', 'child_of',
                           as_id(filters['department_id'])))
        if filters.get('manager_id'):
            domain.append(('manager_user_id', '=',
                           as_id(filters['manager_id'])))
        return domain

    # ==================================================================
    #  The lens
    # ==================================================================
    @api.model
    def get_numbers(self, cycle_id=None, filters=None):
        """Everything the Goals lens draws, in one read.

        IT DOES NOT RAISE (unlike `export_xlsx`). A screen can draw a sentence
        saying who this is for; a download has nowhere to put one.
        """
        if not self._can_read():
            return {'allowed': False, 'empty': True, 'tiles': [],
                    'cycles': [], 'by_manager': [], 'by_department': [],
                    'bands': [], 'rungs': [], 'changes': {},
                    'why': _("The goal numbers are for the HR team.")}
        filters = dict(filters or {})
        cycles = self._safe('the goal years', lambda: self._cycles(), []) or []
        picked = self._pick_cycle(cycle_id, cycles)
        sheets = self.env['pb.goal.set'].sudo().search(
            self._domain(picked, filters))
        cycle = next((c for c in cycles if c['id'] == picked), None)
        if not sheets:
            return {
                'allowed': True, 'empty': True, 'cycles': cycles,
                'cycle_id': picked, 'cycle': (cycle or {}).get('name') or '',
                'tiles': [], 'by_manager': [], 'by_department': [],
                'bands': [], 'rungs': [], 'changes': {},
                'lists': self._safe('the filters',
                                    lambda: self._lists(picked), {}) or {},
                'filters': filters,
                'headline': _(
                    "Nobody has a goal sheet on %s yet. As soon as goals are "
                    "handed out this fills in.",
                    (cycle or {}).get('name') or _('this goal year')),
            }
        core = self._core(sheets)
        return {
            'allowed': True,
            'empty': False,
            'cycles': cycles,
            'cycle_id': picked,
            'cycle': (cycle or {}).get('name') or '',
            'filters': filters,
            'total': len(sheets),
            'headline': self._safe('the headline',
                                   lambda: self._headline(core, cycle),
                                   '') or '',
            'tiles': self._safe('the numbers',
                                lambda: self._tiles(core), []) or [],
            'rungs': self._safe('how long each rung took',
                                lambda: self._rungs(sheets), []) or [],
            'by_manager': self._safe('the managers',
                                     lambda: self._by_manager(sheets),
                                     []) or [],
            'by_department': self._safe('the departments',
                                        lambda: self._by_department(sheets),
                                        []) or [],
            'bands': self._safe('the bands',
                                lambda: self._bands(sheets), []) or [],
            'changes': self._safe('the change requests',
                                  lambda: self._changes(sheets), {}) or {},
            'lists': self._safe('the filters',
                                lambda: self._lists(picked), {}) or {},
        }

    # ------------------------------------------------------------- the maths
    @api.model
    def _core(self, sheets):
        """Every figure the tiles and the headline are made of, counted once."""
        goals = sheets.with_context(active_test=False).mapped('goal_ids')
        krs = goals.mapped('kr_ids')
        checkins = self.env['pb.goal.checkin'].sudo().search(
            [('set_id', 'in', sheets.ids)])
        done = len(checkins.filtered(lambda c: c.state == 'done'))
        owed = len(checkins.filtered(lambda c: c.state in ('done', 'missed')))
        return {
            'sheets': len(sheets),
            'locked': len(sheets.filtered(
                lambda s: s.state in ('locked', 'closed'))),
            'waiting': len(sheets.filtered(
                lambda s: s.state in ('submitted', 'manager_ok'))),
            'not_started': len(sheets.filtered(lambda s: s.state == 'draft')),
            'goals': len(goals),
            'goals_done': len(goals.filtered('done_at')),
            'progress': round(sum(krs.mapped('progress')) / len(krs), 1)
            if krs else 0.0,
            'checkins_done': done,
            'checkins_owed': owed,
            'checkins_missed': owed - done,
            'compliance': round(done * 100.0 / owed, 1) if owed else None,
            'scored': len(sheets.filtered('scored')),
            'score': round(sum(sheets.filtered('scored').mapped('score'))
                           / len(sheets.filtered('scored')), 2)
            if sheets.filtered('scored') else None,
            'on_time': len(sheets.filtered(
                lambda s: s.submitted_at and s.deadline
                and s.submitted_at.date() <= s.deadline)),
            'late': len(sheets.filtered(
                lambda s: s.submitted_at and s.deadline
                and s.submitted_at.date() > s.deadline)),
            'never': len(sheets.filtered(lambda s: not s.submitted_at)),
        }

    @api.model
    def _tiles(self, core):
        """The six numbers, with the sub-line that makes each one readable."""
        compliance = core['compliance']
        return [
            {'key': 'sheets', 'icon': 'target',
             'label': _('Goal sheets'), 'value': str(core['sheets']),
             'sub': _("%s agreed and locked", core['locked'])},
            {'key': 'progress', 'icon': 'trendingUp',
             'label': _('How far along'),
             'value': '%s%%' % self._tidy(core['progress']),
             'sub': _("across every key result")},
            {'key': 'checkins', 'icon': 'calendar',
             'label': _('Monthly conversations'),
             'value': ('%s%%' % self._tidy(compliance)
                       if compliance is not None else '—'),
             'sub': (_("%(done)s of %(owed)s happened",
                       done=core['checkins_done'], owed=core['checkins_owed'])
                     if core['checkins_owed'] else _("none owed yet")),
             'tone': self._tone(compliance)},
            {'key': 'done', 'icon': 'checkCircle',
             'label': _('Goals finished'),
             'value': str(core['goals_done']),
             'sub': _("of %s written", core['goals'])},
            {'key': 'score', 'icon': 'award',
             'label': _('Average score'),
             'value': (str(self._tidy(core['score']))
                       if core['score'] is not None else '—'),
             'sub': (_("%s scored so far", core['scored'])
                     if core['scored'] else _("nothing scored yet"))},
            {'key': 'late', 'icon': 'clock',
             'label': _('Sent in late'), 'value': str(core['late']),
             'sub': _("%(on)s on time, %(never)s never sent",
                      on=core['on_time'], never=core['never']),
             'tone': 'warn' if core['late'] else ''},
        ]

    @api.model
    def _tidy(self, value):
        """"78" and "3.6", never "78.0" — a machine writes 78.0 (R207)."""
        if value is None:
            return ''
        number = round(float(value), 2)
        return int(number) if number == int(number) else number

    @api.model
    def _tone(self, compliance):
        if compliance is None:
            return ''
        if compliance >= 90:
            return 'good'
        return 'bad' if compliance < 60 else 'warn'

    @api.model
    def _headline(self, core, cycle):
        """One sentence that does the arithmetic so the reader does not."""
        year = (cycle or {}).get('name') or _('this goal year')
        parts = [_(
            "%(locked)s of %(total)s %(word)s agreed on %(year)s.",
            locked=core['locked'], total=core['sheets'],
            word=counted(core['sheets'], _('goal sheet'), _('goal sheets')),
            year=year)]
        if core['compliance'] is not None:
            parts.append(_(
                "%(pct)s%% of the monthly conversations owed have happened.",
                pct=self._tidy(core['compliance'])))
            if core['checkins_missed']:
                parts.append(_(
                    "%(n)s %(word)s missed.", n=core['checkins_missed'],
                    word=counted(core['checkins_missed'], _('was'),
                                 _('were'))))
        if core['score'] is not None:
            parts.append(_(
                "The %(n)s scored so far average %(score)s out of 5.",
                n=core['scored'], score=self._tidy(core['score'])))
        return ' '.join(parts)

    @api.model
    def _rungs(self, sheets):
        """How long each rung took, on average, in days.

        MEASURED BETWEEN STAMPS AND NEVER FROM `write_date`. A sheet that was
        never sent in has no answer at all and is counted as such, rather than
        being given a nought that drags every average towards zero.
        """
        out = []
        pairs = (
            ('written', _('Opened, then sent in'), 'create_date',
             'submitted_at'),
            ('manager', _('Sent in, then agreed by their manager'),
             'submitted_at', 'manager_ok_at'),
            ('hr', _('Agreed, then locked'), 'manager_ok_at', 'locked_at'),
        )
        for key, label, start_field, end_field in pairs:
            spans = []
            for sheet in sheets:
                start = sheet[start_field]
                end = sheet[end_field]
                if not start or not end:
                    continue
                # A NEGATIVE SPAN IS AN ARTEFACT, NOT DATA (R155): floor it at
                # nought and count it, rather than dropping exactly the
                # fastest rows and reporting "no answer" over the sheets that
                # went through in an afternoon.
                spans.append(max(0.0, (end - start).total_seconds() / 86400.0))
            out.append({
                'key': key, 'label': label, 'n': len(spans),
                'n_word': counted(len(spans), _('goal sheet'),
                                  _('goal sheets')),
                'days': round(sum(spans) / len(spans), 1) if spans else None,
            })
        never = len([s for s in sheets if not s.submitted_at])
        out.append({'key': 'open', 'label': _('Still not sent in'),
                    'n': never, 'days': None,
                    'n_word': counted(never, _('goal sheet'),
                                      _('goal sheets'))})
        return out

    @api.model
    def _by_manager(self, sheets):
        """Manager compliance — the number this lens exists for."""
        return self._split(sheets, 'manager_user_id', 'manager_employee_id')

    @api.model
    def _by_department(self, sheets):
        return self._split(sheets, 'department_id', 'department_id')

    @api.model
    def _split(self, sheets, key_field, label_field):
        checkins = self.env['pb.goal.checkin'].sudo().search(
            [('set_id', 'in', sheets.ids)])
        buckets = {}
        for sheet in sheets:
            ident = sheet[key_field].id
            if not ident:
                continue
            row = buckets.setdefault(ident, {
                'id': ident,
                'label': sheet[label_field].sudo().name or _('Not set'),
                'sheets': 0, 'locked': 0, 'scored': 0, 'score_sum': 0.0,
                'progress_sum': 0.0, 'done': 0, 'owed': 0, 'late': 0,
            })
            row['sheets'] += 1
            if sheet.state in ('locked', 'closed'):
                row['locked'] += 1
            if sheet.scored:
                row['scored'] += 1
                row['score_sum'] += sheet.score or 0.0
            row['progress_sum'] += sheet.progress or 0.0
            if sheet.submitted_at and sheet.deadline \
                    and sheet.submitted_at.date() > sheet.deadline:
                row['late'] += 1
        by_set = {sheet.id: sheet[key_field].id for sheet in sheets}
        for checkin in checkins:
            ident = by_set.get(checkin.set_id.id)
            row = buckets.get(ident)
            if not row or checkin.state == 'planned':
                continue
            row['owed'] += 1
            if checkin.state == 'done':
                row['done'] += 1
        out = []
        for row in buckets.values():
            owed = row['owed']
            out.append({
                'id': row['id'],
                'label': row['label'],
                'sheets': row['sheets'],
                # THE WORD COMES FROM THE SERVER, WHOLE (R117). "1 sheets" is
                # a machine writing, and a frame with a number in it is
                # something a translator cannot fix because they were never
                # given the verb.
                'sheets_word': counted(row['sheets'], _('goal sheet'),
                                       _('goal sheets')),
                'locked': row['locked'],
                'late': row['late'],
                'progress': round(row['progress_sum'] / row['sheets'], 1)
                if row['sheets'] else 0.0,
                'done': row['done'],
                'owed': owed,
                'missed': owed - row['done'],
                'compliance': round(row['done'] * 100.0 / owed, 1)
                if owed else None,
                'scored': row['scored'],
                'score': round(row['score_sum'] / row['scored'], 2)
                if row['scored'] else None,
            })
        # WORST COMPLIANCE FIRST (R113). A management report is read to find
        # the problem, and a list sorted by name buries it in the middle.
        # "No conversations owed yet" is not a problem and sorts last.
        return sorted(out, key=lambda r: (
            r['compliance'] if r['compliance'] is not None else 1000,
            -r['sheets'], r['label']))[:40]

    @api.model
    def _bands(self, sheets):
        """The score distribution, in band order and never by size."""
        scored = sheets.filtered('scored')
        if not scored:
            return []
        cycle = sheets[:1].cycle_id
        bands = cycle._bands() if cycle else []
        counts = {}
        for sheet in scored:
            counts[sheet.score_band or _('No band')] = counts.get(
                sheet.score_band or _('No band'), 0) + 1
        out = []
        for band in bands:
            count = counts.pop(band.name, 0)
            out.append({'label': band.name or '', 'count': count,
                        'tone': band.tone or 'ok',
                        'pct': round(count * 100.0 / len(scored), 1)})
        for label, count in counts.items():
            out.append({'label': label, 'count': count, 'tone': '',
                        'pct': round(count * 100.0 / len(scored), 1)})
        return out

    @api.model
    def _changes(self, sheets):
        rows = self.env['pb.goal.change'].sudo().search(
            [('set_id', 'in', sheets.ids)])
        by_kind = {}
        for row in rows:
            entry = by_kind.setdefault(row.kind, {
                'label': CHANGE_KIND_LABEL.get(row.kind, row.kind),
                'count': 0, 'agreed': 0, 'refused': 0, 'open': 0})
            entry['count'] += 1
            if row.state == 'approved':
                entry['agreed'] += 1
            elif row.state == 'refused':
                entry['refused'] += 1
            else:
                entry['open'] += 1
        return {
            'total': len(rows),
            'agreed': len(rows.filtered(lambda r: r.state == 'approved')),
            'refused': len(rows.filtered(lambda r: r.state == 'refused')),
            'open': len(rows.filtered(
                lambda r: r.state in ('draft', 'submitted', 'manager_ok'))),
            'kinds': sorted(by_kind.values(), key=lambda e: -e['count']),
            'sentence': (_(
                "%(n)s %(word)s asked for this year: %(agreed)s agreed, "
                "%(refused)s turned down, %(open)s still being decided.",
                n=len(rows),
                word=counted(len(rows), _('change was'), _('changes were')),
                agreed=len(rows.filtered(lambda r: r.state == 'approved')),
                refused=len(rows.filtered(lambda r: r.state == 'refused')),
                open=len(rows.filtered(
                    lambda r: r.state in ('draft', 'submitted',
                                          'manager_ok'))))
                if rows else _(
                    "Nobody has asked to change an agreed goal this year.")),
        }

    @api.model
    def _lists(self, cycle_id):
        """THE FILTER LISTS COME FROM THE DATA, never from a vocabulary (R27).

        A filter that matches nothing is a broken promise.
        """
        sheets = self.env['pb.goal.set'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)]
            + ([('cycle_id', '=', int(cycle_id))] if cycle_id else []))
        departments = {}
        managers = {}
        for sheet in sheets:
            if sheet.department_id:
                departments[sheet.department_id.id] = \
                    sheet.department_id.sudo().name or ''
            if sheet.manager_user_id:
                managers[sheet.manager_user_id.id] = \
                    sheet.manager_employee_id.sudo().name \
                    or sheet.manager_user_id.name or ''
        return {
            'departments': sorted(
                ({'id': key, 'name': value}
                 for key, value in departments.items()),
                key=lambda row: row['name']),
            'managers': sorted(
                ({'id': key, 'name': value}
                 for key, value in managers.items()),
                key=lambda row: row['name']),
        }

    # ==================================================================
    #  The spreadsheet
    # ==================================================================
    @api.model
    def export_xlsx(self, cycle_id=None, filters=None):
        """The same read the screen drew, as a workbook.

        NOT A SECOND QUERY (the precedent `pb_budget/models/budget_export.py`
        set): the day a report and the screen beside it disagree, nobody can
        tell which one is the report.

        IT RAISES where `get_numbers` returns a sentence, because a download
        has nowhere to draw a sentence.
        """
        self._require()
        board = self.get_numbers(cycle_id, filters)
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
            from openpyxl.utils import get_column_letter
        except ImportError:
            from odoo.exceptions import UserError
            raise UserError(_(
                "This system cannot build spreadsheets at the moment. Ask an "
                "administrator to look at it."))

        head = Font(bold=True, color='FFFFFF')
        fill = PatternFill('solid', fgColor='6355C7')
        bold = Font(bold=True)
        centre = Alignment(horizontal='center', wrap_text=True)

        def sheet(ws, title, columns):
            ws.title = title
            for index, (label, width) in enumerate(columns, start=1):
                cell = ws.cell(row=1, column=index, value=label)
                cell.font = head
                cell.fill = fill
                cell.alignment = centre
                ws.column_dimensions[get_column_letter(index)].width = width
            ws.freeze_panes = 'A2'
            return ws

        wb = openpyxl.Workbook()

        # ------------------------------------------------ what it all says
        ws = sheet(wb.active, _('Summary'), [(_('What'), 44), (_('Figure'),
                                                               22)])
        ws.cell(row=2, column=1, value=_('Goal year')).font = bold
        ws.cell(row=2, column=2, value=board.get('cycle') or '')
        row = 3
        for tile in board.get('tiles') or []:
            ws.cell(row=row, column=1, value=tile['label']).font = bold
            ws.cell(row=row, column=2, value=tile['value'])
            row += 1
            if tile.get('sub'):
                ws.cell(row=row, column=1, value='    %s' % tile['sub'])
                row += 1
        row += 1
        ws.cell(row=row, column=1, value=_('In one line')).font = bold
        ws.cell(row=row, column=2, value=board.get('headline') or '')

        # ------------------------------------------------ manager compliance
        ws = sheet(wb.create_sheet(), _('By manager'), [
            (_('Manager'), 30), (_('Goal sheets'), 14), (_('Agreed'), 12),
            (_('Sent in late'), 14), (_('How far along'), 16),
            (_('Conversations owed'), 20), (_('Happened'), 14),
            (_('Missed'), 12), (_('Compliance %'), 16), (_('Scored'), 12),
            (_('Average score'), 16)])
        for index, line in enumerate(board.get('by_manager') or [], start=2):
            for column, value in enumerate((
                    line['label'], line['sheets'], line['locked'],
                    line['late'], line['progress'], line['owed'],
                    line['done'], line['missed'],
                    line['compliance'] if line['compliance'] is not None
                    else '', line['scored'],
                    line['score'] if line['score'] is not None else ''),
                    start=1):
                ws.cell(row=index, column=column, value=value)

        # ------------------------------------------------ by department
        ws = sheet(wb.create_sheet(), _('By department'), [
            (_('Part of the business'), 30), (_('Goal sheets'), 14),
            (_('Agreed'), 12), (_('How far along'), 16),
            (_('Conversations owed'), 20), (_('Happened'), 14),
            (_('Compliance %'), 16), (_('Average score'), 16)])
        for index, line in enumerate(board.get('by_department') or [],
                                     start=2):
            for column, value in enumerate((
                    line['label'], line['sheets'], line['locked'],
                    line['progress'], line['owed'], line['done'],
                    line['compliance'] if line['compliance'] is not None
                    else '',
                    line['score'] if line['score'] is not None else ''),
                    start=1):
                ws.cell(row=index, column=column, value=value)

        # ------------------------------------------------ the bands
        ws = sheet(wb.create_sheet(), _('Scores'), [
            (_('Band'), 26), (_('People'), 14), (_('Share %'), 14)])
        for index, line in enumerate(board.get('bands') or [], start=2):
            ws.cell(row=index, column=1, value=line['label'])
            ws.cell(row=index, column=2, value=line['count'])
            ws.cell(row=index, column=3, value=line['pct'])

        # ------------------------------------------------ how long it took
        ws = sheet(wb.create_sheet(), _('How long'), [
            (_('Step'), 40), (_('Sheets'), 14), (_('Average days'), 16)])
        for index, line in enumerate(board.get('rungs') or [], start=2):
            ws.cell(row=index, column=1, value=line['label'])
            ws.cell(row=index, column=2, value=line['n'])
            ws.cell(row=index, column=3,
                    value=line['days'] if line['days'] is not None else '')

        # ------------------------------------------------ the changes
        ws = sheet(wb.create_sheet(), _('Changes asked for'), [
            (_('What kind'), 30), (_('Asked for'), 14), (_('Agreed'), 12),
            (_('Turned down'), 14), (_('Still being decided'), 20)])
        for index, line in enumerate(
                (board.get('changes') or {}).get('kinds') or [], start=2):
            for column, value in enumerate((
                    line['label'], line['count'], line['agreed'],
                    line['refused'], line['open']), start=1):
                ws.cell(row=index, column=column, value=value)

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return {
            'ok': True,
            'file_b64': base64.b64encode(out.read()).decode(),
            'filename': _('Goals %s.xlsx', board.get('cycle')
                          or fields.Date.today()),
            'mimetype': ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'),
            'rows': len(board.get('by_manager') or []),
        }

    # ==================================================================
    #  The doors
    # ==================================================================
    @api.model
    def open_checkins(self, cycle_id=None, manager_id=None):
        """R125 — `views` on every hand-built act_window dict."""
        domain = []
        if cycle_id:
            domain.append(('cycle_id', '=', as_id(cycle_id)))
        if manager_id:
            domain.append(('manager_user_id', '=', as_id(manager_id)))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Monthly check-ins'),
            'res_model': 'pb.goal.checkin',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
        }

    @api.model
    def open_changes(self, cycle_id=None):
        domain = []
        if cycle_id:
            domain.append(('cycle_id', '=', as_id(cycle_id)))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Change requests'),
            'res_model': 'pb.goal.change',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
        }
