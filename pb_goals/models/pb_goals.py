# -*- coding: utf-8 -*-
"""`pb.goals` — the facade behind the Goals lens on the People hub.

ONE BOARD, TWO READERS, AND THE SERVER DECIDES WHICH. A manager opening this
sees their own team; the HR team sees the company. That is NOT a switch on the
screen and it is not two lenses: it is the record rules doing what record rules
are for, plus one honest sentence at the top saying whose sheets are on the
board. A screen that asks somebody to choose a scope they do not have is a
screen with a dead end in it.

NOTHING HERE USES `sudo()` FOR A READ THE CALLER SHOULD NOT HAVE. The searches
run as the caller and the rules narrow them, which is the product's rule for
every cockpit facade. The two places `sudo()` appears are the ones where reading
as the caller would be a lie about permissions rather than a permission: an
employee's NAME (R56 — one field prefetches forty, forty of them behind payroll
groups) and the counts on the cycle strip, which are about the year rather than
about any one sheet.

EVERY PROBE HAS ITS OWN try/except (the platform rule). A board that cannot work
out one number still draws the other eleven, and the failure is logged at
WARNING with a traceback rather than swallowed at DEBUG (R92).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .goals_common import (
    ALL_GROUPS, P_REMINDERS, P_ROW_LIMIT, RATING_LABEL, SET_RANK, SET_STATES,
    SET_STATE_LABEL, WEIGHT_TOTAL, counted, due_words, flag, fold, as_id,
    number,
)

_logger = logging.getLogger(__name__)


class PbGoals(models.AbstractModel):
    _name = 'pb.goals'
    _description = 'Goals board'

    # ------------------------------------------------------------- plumbing
    @api.model
    def _safe(self, label, fn, default=None):
        try:
            return fn()
        except Exception:               # noqa: BLE001 — one probe, one guard
            _logger.warning('pb_goals: the board could not work out %s',
                            label, exc_info=True)
            return default

    @api.model
    def _me(self):
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)

    @api.model
    def _is_hr(self):
        return self.env.user.has_group('pb_goals.group_goals_manager')

    @api.model
    def _can_read(self):
        """Who may open the board at all.

        THE GATE THAT DECIDES WHAT SOMEBODY MAY DO AND THE GATE THAT DECIDES
        WHETHER THEY MAY LOOK HAVE TO AGREE (R157). A manager holds no goals
        group by definition and the record rule is what lets them see their
        team — so "do you hold a group" is the wrong question here and would
        close the board on exactly the people it is for. The right question is
        "is there anything for you to see", and the rules answer it.
        """
        if any(self.env.user.has_group(group) for group in ALL_GROUPS):
            return True
        try:
            return bool(self.env['pb.goal.set'].search_count([], limit=1))
        except AccessError:
            return False

    @api.model
    def _scope_sentence(self):
        """Whose sheets are on this board, said in one line.

        AND IT HAS TO BE TRUE OF THE READER. "Your team's goals" over a board
        holding one row — their own — is a screen telling somebody they manage
        people they do not, which is worse than saying nothing. The question is
        whether anybody actually reports to them.
        """
        if self._is_hr():
            return _("Everybody's goals, in the companies you can see.")
        me = self._me()
        if not me:
            return _("Your own goals.")
        team = self.env['hr.employee'].sudo().search_count(
            [('parent_id', '=', me.id)])
        if team:
            return _("Your team's goals, and your own.")
        return _("Your own goals.")

    # ==================================================================
    #  The board
    # ==================================================================
    @api.model
    def get_board(self, filters=None):
        """Everything the Goals lens draws, in one read."""
        if not self._can_read():
            return {'allowed': False,
                    'why': _("Goal sheets are for the people they belong to, "
                             "their manager and the HR team.")}
        filters = dict(filters or {})
        today = fields.Date.today()
        cycles = self._safe('the goal years', lambda: self._cycles(), []) or []
        cycle_id = int(filters.get('cycle_id') or 0)
        if not cycle_id and cycles:
            # THE DEFAULT IS THE YEAR PEOPLE ARE IN, NOT THE NEWEST ONE.
            # Found live: next year's sheet had been set up ready to open, it
            # sorts first by start date, and the board opened on it — empty,
            # for everybody, over a database with eight goal sheets in it.
            # "Newest first" is right for the strip and wrong for the default.
            live = [c for c in cycles if c['state'] == 'open']
            cycle_id = (live or cycles)[0]['id']
        rows = self._safe('the goal sheets',
                          lambda: self._rows(cycle_id, filters, today),
                          []) or []
        return {
            'allowed': True,
            'is_hr': self._is_hr(),
            'scope': self._scope_sentence(),
            'today': str(today),
            'cycles': cycles,
            'cycle_id': cycle_id,
            'rows': rows,
            'stats': self._safe('the numbers',
                                lambda: self._stats(rows), []) or [],
            'bar': self._safe('the status bar',
                              lambda: self._bar(rows), []) or [],
            'facets': self._safe('the filters',
                                 lambda: self._facets(rows), {}) or {},
            'states': [{'key': key, 'label': label}
                       for key, label in SET_STATES],
            'reminders_on': flag(self.env, P_REMINDERS),
            # ZERO DEAD ENDS. Everybody with a login can open this lens now
            # (a manager holds no goals group and the team view is FOR them),
            # so somebody who is neither HR nor a manager lands on a board
            # holding their own sheet — and the one thing they want from it is
            # the page where they can actually write.
            'my_page': bool(self._me()),
            'limit': number(self.env, P_ROW_LIMIT, 400),
            'headline': self._headline(rows, cycles, cycle_id),
        }

    @api.model
    def _cycles(self):
        rows = self.env['pb.goal.cycle'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)],
            order='date_start desc', limit=12)
        out = [{
            'id': cycle.id,
            'name': cycle.name or '',
            'state': cycle.state,
            'state_word': dict(cycle._fields['state'].selection).get(
                cycle.state, cycle.state),
            'company': cycle.company_id.name or '',
            'from': str(cycle.date_start or ''),
            'to': str(cycle.date_end or ''),
            'mid': str(cycle.mid_year_date or ''),
            'sheets': cycle.set_count,
            'locked': cycle.locked_count,
            'days': cycle.submission_days,
        } for cycle in rows]
        # The open year sits at the front of the strip, then the rest newest
        # first — so the eye lands on the year everybody is working in. A
        # STABLE PARTITION and not a re-sort: the search already came back
        # newest first, and re-sorting on an ISO string to get the same order
        # back is a second opinion waiting to disagree.
        return ([c for c in out if c['state'] == 'open']
                + [c for c in out if c['state'] != 'open'])

    @api.model
    def _rows(self, cycle_id, filters, today):
        domain = []
        if cycle_id:
            domain.append(('cycle_id', '=', int(cycle_id)))
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('department_id'):
            domain.append(('department_id', '=',
                           int(filters['department_id'])))
        if filters.get('manager_id'):
            domain.append(('manager_user_id', '=', int(filters['manager_id'])))
        if filters.get('mine'):
            me = self._me()
            domain.append(('employee_id', '=', me.id or 0))
        limit = number(self.env, P_ROW_LIMIT, 400)
        sheets = self.env['pb.goal.set'].search(domain, limit=limit)
        needle = fold(filters.get('q') or '')
        out = []
        for sheet in sheets:
            employee = sheet.employee_id.sudo()
            name = employee.name or ''
            if needle and needle not in fold(name):
                continue
            out.append({
                'id': sheet.id,
                'employee_id': employee.id,
                'name': name,
                'avatar': '/web/image/hr.employee/%s/avatar_128' % employee.id,
                'job': employee.job_title or (employee.job_id.name or ''),
                'department': sheet.department_id.name or '',
                'department_id': sheet.department_id.id or 0,
                'manager': sheet.manager_employee_id.sudo().name or '',
                'manager_id': sheet.manager_user_id.id or 0,
                'state': sheet.state,
                'state_word': SET_STATE_LABEL.get(sheet.state, sheet.state),
                'rank': SET_RANK.get(sheet.state, 9),
                'deadline': str(sheet.deadline or ''),
                'due_words': ('' if sheet.state in ('locked', 'refused')
                              else due_words(sheet.deadline, today)),
                'overdue': bool(sheet.deadline and sheet.deadline < today
                                and sheet.state in ('draft', 'returned')),
                'goals': sheet.goal_count,
                'krs': sheet.kr_count,
                'weight_total': round(sheet.weight_total or 0.0, 1),
                'weights_ok': abs((sheet.weight_total or 0.0)
                                  - WEIGHT_TOTAL) < 0.01,
                'progress': round(sheet.progress or 0.0, 1),
                'locked_on': str(sheet.locked_at or '')[:10],
            })
        # PROBLEM FIRST (R113), and never by the spelling of the state (R50).
        out.sort(key=lambda r: (r['rank'], not r['overdue'],
                                r['deadline'] or '9999', r['name']))
        return out

    @api.model
    def _stats(self, rows):
        total = len(rows)
        locked = len([r for r in rows if r['state'] == 'locked'])
        waiting = len([r for r in rows
                       if r['state'] in ('submitted', 'manager_ok')])
        not_started = len([r for r in rows if r['state'] == 'draft'])
        overdue = len([r for r in rows if r['overdue']])
        sent_back = len([r for r in rows if r['state'] == 'returned'])
        return [
            {'key': 'total', 'label': _('Goal sheets'), 'value': total,
             'icon': 'target'},
            {'key': 'locked', 'label': _('Agreed and locked'), 'value': locked,
             'icon': 'lock', 'tone': 'good'},
            {'key': 'waiting', 'label': _('Waiting on somebody'),
             'value': waiting, 'icon': 'clock'},
            {'key': 'draft', 'label': _('Not written yet'),
             'value': not_started, 'icon': 'pencil'},
            {'key': 'back', 'label': _('Sent back'), 'value': sent_back,
             'icon': 'undo', 'tone': 'warn' if sent_back else ''},
            {'key': 'overdue', 'label': _('Past their date'), 'value': overdue,
             'icon': 'alert', 'tone': 'bad' if overdue else ''},
        ]

    @api.model
    def _bar(self, rows):
        """The segmented bar: one band per state, widest first is WRONG here.

        The bands keep the LIFECYCLE order, left to right, because the bar is
        read as a journey — not written, waiting, agreed — and a bar that
        reorders itself as the numbers change is a bar nobody can read twice.
        """
        total = len(rows) or 1
        bands = []
        for key, label in SET_STATES:
            count = len([r for r in rows if r['state'] == key])
            if not count:
                continue
            bands.append({'key': key, 'label': label, 'count': count,
                          'pct': round(count * 100.0 / total, 1)})
        return bands

    @api.model
    def _facets(self, rows):
        def tally(key, label_key):
            seen = {}
            for row in rows:
                ident = row.get(key)
                if not ident:
                    continue
                entry = seen.setdefault(
                    ident, {'id': ident, 'label': row.get(label_key) or '',
                            'count': 0})
                entry['count'] += 1
            return sorted(seen.values(),
                          key=lambda e: (-e['count'], e['label']))[:14]
        return {
            'departments': tally('department_id', 'department'),
            'managers': tally('manager_id', 'manager'),
        }

    @api.model
    def _headline(self, rows, cycles, cycle_id):
        """One sentence that does the arithmetic so the reader does not."""
        cycle = next((c for c in cycles if c['id'] == cycle_id), None)
        if not cycles:
            return _("No goal year has been set up yet. Make one, open it, "
                     "and everybody can start writing.")
        if not rows:
            return _("Nobody has a goal sheet for %s yet.",
                     (cycle or {}).get('name') or _('this year'))
        locked = len([r for r in rows if r['state'] == 'locked'])
        overdue = len([r for r in rows if r['overdue']])
        waiting = len([r for r in rows
                       if r['state'] in ('submitted', 'manager_ok')])
        first = _("%(locked)s of %(total)s %(word)s agreed and locked for "
                  "%(cycle)s.", locked=locked, total=len(rows),
                  word=counted(len(rows), _('goal sheet'), _('goal sheets')),
                  cycle=(cycle or {}).get('name') or _('this year'))
        parts = [first]
        if waiting:
            parts.append(_("%(n)s %(word)s waiting on somebody to read them.",
                           n=waiting, word=counted(waiting, _('is'), _('are'))))
        if overdue:
            parts.append(_("%(n)s %(word)s past the date they were due.",
                           n=overdue, word=counted(overdue, _('is'), _('are'))))
        return ' '.join(parts)

    # ==================================================================
    #  The drawer
    # ==================================================================
    @api.model
    def get_set(self, set_id):
        """One goal sheet, opened out: the goals, the key results, the trail."""
        sheet = self.env['pb.goal.set'].browse(as_id(set_id)).exists()
        if not sheet:
            return {'ok': False,
                    'why': _("That goal sheet is not there any more.")}
        try:
            sheet.check_access('read')
        except AccessError:
            return {'ok': False,
                    'why': _("That goal sheet is not one you can see.")}
        today = fields.Date.today()
        employee = sheet.employee_id.sudo()
        may_weight = self._may_weight(sheet)
        goals = []
        for goal in sheet.goal_ids.sorted(lambda g: (g.sequence, g.id)):
            goals.append({
                'id': goal.id,
                'title': goal.title or '',
                'description': goal.description or '',
                'weight': round(goal.weight or 0.0, 1),
                'from': str(goal.date_start or ''),
                'to': str(goal.date_end or ''),
                'rating': goal.self_rating or '',
                'rating_word': RATING_LABEL.get(goal.self_rating or '', ''),
                'progress': round(goal.progress or 0.0, 1),
                'locked': bool(goal.locked),
                'krs': [{
                    'id': kr.id,
                    'title': kr.title or '',
                    'measure': kr.measure or '',
                    'target': kr.target or 0.0,
                    'current': kr.current or 0.0,
                    'progress': round(kr.progress or 0.0, 1),
                    'due': str(kr.due_date or ''),
                    'moves': len(kr.history_ids),
                } for kr in goal.kr_ids.sorted(lambda k: (k.sequence, k.id))],
            })
        return {
            'ok': True,
            'id': sheet.id,
            'name': employee.name or '',
            'avatar': '/web/image/hr.employee/%s/avatar_128' % employee.id,
            'job': employee.job_title or (employee.job_id.name or ''),
            'department': sheet.department_id.name or '',
            'manager': sheet.manager_employee_id.sudo().name or '',
            'cycle': sheet.cycle_id.sudo().name or '',
            'state': sheet.state,
            'state_word': SET_STATE_LABEL.get(sheet.state, sheet.state),
            'deadline': str(sheet.deadline or ''),
            'due_words': ('' if sheet.state in ('locked', 'refused')
                          else due_words(sheet.deadline, today)),
            'joined_on': str(sheet.joined_on or ''),
            'weight_total': round(sheet.weight_total or 0.0, 1),
            'weights_ok': abs((sheet.weight_total or 0.0)
                              - WEIGHT_TOTAL) < 0.01,
            'weight_target': WEIGHT_TOTAL,
            'progress': round(sheet.progress or 0.0, 1),
            'locked_on': str(sheet.locked_at or '')[:19],
            'locked_by': sheet.locked_by_id.sudo().name or '',
            'return_note': sheet.return_note or '',
            # WHY A SHEET IS SITTING STILL, in the engine's own words. A route
            # that was approved and then could not be carried out — somebody
            # reworded a goal after it went in — leaves the record where it
            # was with the reason buried inside the approval request. Nothing
            # was on any screen until this line put it on one.
            'stuck': self._safe('why it is stuck',
                                lambda: self._stuck(sheet), '') or '',
            'may_weight': may_weight,
            'may_send_back': self._may_send_back(sheet),
            'goals': goals,
            'history': self._safe(
                'the trail', lambda: self._history(sheet), []) or [],
        }

    @api.model
    def _stuck(self, sheet):
        """The block reason off the sheet's own latest approval request."""
        request = sheet.sudo().approval_request_id
        if not request or sheet.state == 'locked':
            return ''
        return request.block_reason or ''

    @api.model
    def _may_weight(self, sheet):
        """Whose word the weights are.

        The manager's, while the sheet is waiting on them; the HR team's at
        any point before it is locked. Once it is locked they are nobody's —
        which is what locked means.

        "IS IT LOCKED" IS TWO QUESTIONS AND BOTH HAVE TO BE FALSE. The status
        is what a board shows and `locked_at` is what actually happened. They
        agree on every path this module ships; asking only the first would make
        the guard depend on a status rather than on the fact.
        """
        if sheet.state == 'locked' or sheet.locked_at:
            return False
        if self._is_hr():
            return True
        # THE MANAGER'S WINDOW CLOSES WHEN THEY AGREE IT, and only then. Left
        # open through `manager_ok` they could change the weights after their
        # own decision and before the HR lead reads it — so the HR lead would
        # be agreeing to a split nobody had signed off. The weights are what
        # they agreed to, from the moment they agree.
        return bool(sheet.manager_user_id.id == self.env.uid
                    and sheet.state == 'submitted')

    @api.model
    def _may_send_back(self, sheet):
        if sheet.state not in ('submitted', 'manager_ok'):
            return False
        if self._is_hr():
            return True
        return bool(sheet.manager_user_id.id == self.env.uid)

    @api.model
    def _history(self, sheet):
        rows = self.env['pb.goal.kr.history'].sudo().search(
            [('set_id', '=', sheet.id)], order='at desc', limit=30)
        return [{
            'at': str(row.at or '')[:16],
            'who': row.by_user_id.name or '',
            'kr': row.kr_id.title or '',
            'goal': row.kr_id.goal_id.title or '',
            'progress': round(row.progress or 0.0, 1),
            'current': row.current or 0.0,
            'note': row.note or '',
        } for row in rows]

    # ==================================================================
    #  The presses
    # ==================================================================
    @api.model
    def set_weights(self, set_id, weights):
        """The manager's one job on this screen.

        `weights` is `{goal_id: number}` and every goal has to be in it —
        a partial write is how a total ends up at 97 and nobody can see which
        one is missing. Written under `sudo()` after the permission is checked
        here, because the manager holds no permission on `pb.goal` and the
        record rule cannot say "this field but not that one".
        """
        sheet = self.env['pb.goal.set'].browse(as_id(set_id)).exists()
        if not sheet:
            raise UserError(_("That goal sheet is not there any more."))
        sheet.check_access('read')
        # THE LOCKED SENTENCE COMES FIRST, because it is the one somebody can
        # act on: "it is finished" tells them what to do next, and "you are
        # not allowed" over a sheet everybody has already agreed reads as a
        # permissions problem that is not one.
        if sheet.state == 'locked' or sheet.locked_at:
            raise UserError(_(
                "This sheet has been agreed and locked, so the weights cannot "
                "change. Ask HR to send it back if something has to move."))
        if not self._may_weight(sheet):
            raise UserError(_(
                "The weights are set by the person's own manager while they "
                "are waiting to be agreed, or by the HR team."))
        wanted = {int(key): float(value or 0)
                  for key, value in dict(weights or {}).items()}
        total = 0.0
        for goal in sheet.sudo().goal_ids:
            if goal.id not in wanted:
                continue
            value = max(0.0, min(100.0, round(wanted[goal.id], 2)))
            if abs((goal.weight or 0.0) - value) > 0.001:
                goal.sudo().write({'weight': value})
            total += value
        sheet.invalidate_recordset(['weight_total'])
        left = round(WEIGHT_TOTAL - (sheet.sudo().weight_total or 0.0), 1)
        return {
            'ok': True,
            'weight_total': round(sheet.sudo().weight_total or 0.0, 1),
            'weights_ok': abs(left) < 0.01,
            'sentence': (_("The weights add up to 100. It can be agreed now.")
                         if abs(left) < 0.01 else
                         _("The weights add up to %(have)s. %(gap)s to go.",
                           have=int(round(sheet.sudo().weight_total or 0)),
                           gap=int(round(left)) if left > 0
                           else _("%s too many") % int(round(-left)))),
        }

    @api.model
    def send_back(self, set_id, note):
        """Send a sheet back with a note the person actually reads."""
        sheet = self.env['pb.goal.set'].browse(as_id(set_id)).exists()
        if not sheet:
            raise UserError(_("That goal sheet is not there any more."))
        sheet.check_access('read')
        if not self._may_send_back(sheet):
            raise UserError(_(
                "Only the person's own manager or the HR team can send a "
                "goal sheet back."))
        text = (note or '').strip()
        if not text:
            raise UserError(_(
                "Write what you would like changed. A sheet that comes back "
                "with no note is a sheet somebody has to guess about."))
        sheet.action_goals_send_back(text)
        return {'ok': True, 'state': sheet.state,
                'sentence': _("Sent back. %s has been told and can edit it "
                              "again.", sheet.employee_id.sudo().name or '')}

    # ==================================================================
    #  The doors
    # ==================================================================
    @api.model
    def open_set(self, set_id):
        """R125 — `views` on every hand-built act_window dict."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal sheet'),
            'res_model': 'pb.goal.set',
            'res_id': as_id(set_id),
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }

    @api.model
    def open_cycles(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal years'),
            'res_model': 'pb.goal.cycle',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
        }

    @api.model
    def open_templates(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Goal templates'),
            'res_model': 'pb.goal.template',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
        }

    @api.model
    def preview_open_for_everyone(self, cycle_id):
        return self.env['pb.goal.cycle'].preview_open_for_everyone(cycle_id)

    @api.model
    def open_for_everyone(self, cycle_id):
        result = self.env['pb.goal.cycle'].open_for_everyone(cycle_id)
        made = result.get('made', 0)
        skipped = result.get('skipped', 0)
        # ZERO IS A REAL AND COMMON OUTCOME HERE, and "0 goal sheets opened,
        # each due 30 September" is a machine writing (R117). Somebody
        # pressing this a second time after the new starters arrive is the
        # ordinary case, and the honest answer is a sentence rather than a
        # number with a date hanging off it.
        if not made:
            sentence = (_("Nothing new — all %s already had one.", skipped)
                        if skipped else
                        _("There was nobody to open one for."))
        else:
            sentence = _(
                "%(n)s %(word)s opened, each due %(due)s.%(skip)s", n=made,
                word=counted(made, _('goal sheet'), _('goal sheets')),
                due=result.get('deadline') or '',
                skip=(_(" %s already had one.", skipped) if skipped else ''))
        return dict(result, sentence=sentence)
