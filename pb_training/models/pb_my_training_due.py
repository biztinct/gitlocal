# -*- coding: utf-8 -*-
"""What E2 adds to the employee's own pages: a date, a reason, and a way out.

E1's page answers "what am I on and how far through am I". The three things
missing from it the moment training is ASSIGNED are the three things a person
actually worries about: by when, why me, and what do I do if I cannot.

WHO "ME" IS HAS NOT CHANGED and is still never a parameter. Every method here
resolves the session user's own employee record and reads only their own
assignments; there is no url anybody can craft that shows them somebody else's
due dates. The ONE exception is the team page, which is a different question
asked by a different person — and it answers it from `parent_id`, as the
system, and shows nothing at all to somebody who manages nobody.
"""

import logging

from odoo import _, api, fields, models

from .training_common import (
    ASSIGN_OPEN, ASSIGN_REASON_LABEL, ASSIGN_STATE_LABEL, DELAY_KINDS,
    DELAY_KIND_LABEL, DELAY_STATE_LABEL, as_id, counted, days_over, due_words,
)

_logger = logging.getLogger(__name__)


class PbMyTrainingDue(models.AbstractModel):
    _inherit = 'pb.my.training'

    # =====================================================================
    #  my own assignments
    # =====================================================================
    @api.model
    def _my_employee(self):
        """My employee record, as the system and narrowly (R56)."""
        return self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)

    @api.model
    def _my_assignments(self):
        """Every course I owe, newest first. Brought up to date as it is read.

        A due date that was true last night is not an answer: somebody who
        finished a course at ten o'clock must not open their own page at
        eleven and be told they are overdue.
        """
        emp = self._my_employee()
        if not emp:
            return self.env['pb.training.assignment'].sudo().browse()
        rows = self.env['pb.training.assignment'].sudo().search(
            [('employee_id', '=', emp.id)])
        rows._refresh()
        return rows

    @api.model
    def _assignment_by_channel(self):
        by_channel = {}
        for row in self._my_assignments():
            # The OPEN one wins over a finished one for the same course: a
            # yearly compliance course has both, and the one that matters is
            # the one somebody still has to do.
            existing = by_channel.get(row.channel_id.id)
            if existing is None or (row.state in ASSIGN_OPEN
                                    and existing.state not in ASSIGN_OPEN):
                by_channel[row.channel_id.id] = row
        return by_channel

    def _due_block(self, assignment, today):
        """The three lines a tile shows about a due date, or nothing."""
        if not assignment:
            return None
        # The LATEST request, whatever it said. A refusal has to be visible on
        # their own page or the answer is "nothing happened", which is how a
        # person ends up asking three times.
        delay = assignment.delay_ids.sudo().sorted(
            lambda d: d.id, reverse=True)[:1]
        waiting = bool(delay) and delay.state == 'submitted'
        return {
            'id': assignment.id,
            'due': fields.Date.to_string(assignment.due_date) or '',
            'due_words': due_words(assignment.due_date, today),
            'late': bool(days_over(assignment.due_date, today))
            and assignment.state != 'done',
            'days_over': days_over(assignment.due_date, today),
            'reason': assignment.reason,
            'reason_word': ASSIGN_REASON_LABEL.get(assignment.reason, ''),
            'state': assignment.state or 'assigned',
            'state_word': ASSIGN_STATE_LABEL.get(assignment.state or '', ''),
            'probation': bool(assignment.counts_for_probation),
            'can_ask': assignment.state in ASSIGN_OPEN and not waiting,
            'delay': {
                'state': delay.state,
                'state_word': DELAY_STATE_LABEL.get(delay.state, ''),
                'days': delay.days_asked,
                'kind_word': DELAY_KIND_LABEL.get(delay.reason_kind, ''),
            } if delay else None,
        }

    # -------------------------------------------------- the tile and the page
    def _tile(self, row):
        tile = super()._tile(row)
        try:
            today = fields.Date.today()
            assignment = self._assignment_by_channel().get(row.channel_id.id)
            tile['assignment'] = self._due_block(assignment, today)
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the due date could not be read for '
                            'course %s', row.channel_id.id, exc_info=True)
            tile['assignment'] = None
        return tile

    @api.model
    def home(self):
        data = super().home()
        try:
            due = [c for c in data['courses']
                   if (c.get('assignment') or {}).get('state') in ASSIGN_OPEN]
            data['overdue'] = len([c for c in due
                                   if c['assignment']['state'] == 'overdue'])
            today = fields.Date.today()
            data['due_soon'] = len([
                c for c in due
                if c['assignment']['state'] != 'overdue'
                and c['assignment']['due']
                and 0 <= (fields.Date.to_date(c['assignment']['due'])
                          - today).days <= 7])
            data['delay_kinds'] = [{'key': k, 'label': v}
                                   for k, v in DELAY_KINDS]
            data['manages'] = self.i_manage_people()
        except Exception:               # noqa: BLE001 — never a 500 on /my
            _logger.warning('pb_training: the training home extras could not '
                            'be read', exc_info=True)
            data.setdefault('overdue', 0)
            data.setdefault('due_soon', 0)
            data.setdefault('delay_kinds', [])
            data.setdefault('manages', False)
        return data

    @api.model
    def course(self, channel_id):
        data = super().course(channel_id)
        if not data:
            return data
        try:
            today = fields.Date.today()
            assignment = self._assignment_by_channel().get(as_id(channel_id))
            data['assignment'] = self._due_block(assignment, today)
            data['delay_kinds'] = [{'key': k, 'label': v}
                                   for k, v in DELAY_KINDS]
        except Exception:               # noqa: BLE001
            _logger.warning('pb_training: the due date could not be read for '
                            'the course page', exc_info=True)
            data['assignment'] = None
            data['delay_kinds'] = []
        return data

    # =====================================================================
    #  finishing a lesson moves the assignment, immediately
    # =====================================================================
    def _complete(self, slide, row):
        """E1's own completion write, plus the one thing E2 added to it.

        Without this the state would still be right — every read refreshes and
        the nightly job sweeps — but only AFTER the next page load, so
        somebody finishing their last lesson would watch the page still say
        "Overdue" underneath the tick they had just earned.
        """
        result = super()._complete(slide, row)
        try:
            with self.env.cr.savepoint():
                assignments = self.env['pb.training.assignment'].sudo().search(
                    [('channel_id', '=', row.channel_id.id),
                     ('partner_id', '=', row.partner_id.id)])
                assignments._refresh()
        except Exception:               # noqa: BLE001 — never lose a tick
            _logger.warning('pb_training: a lesson was marked done but the '
                            'assignment could not be brought up to date',
                            exc_info=True)
        return result

    # =====================================================================
    #  asking for more time
    # =====================================================================
    @api.model
    def ask_more_time(self, assignment_id, reason_kind, days_asked, note=''):
        """One press: the request is made AND sent in. See `delay.ask`."""
        return self.env['pb.training.delay'].ask(
            assignment_id, reason_kind, days_asked, note)

    # =====================================================================
    #  the manager's own page
    # =====================================================================
    @api.model
    def i_manage_people(self):
        try:
            emp = self._my_employee()
            if not emp:
                return False
            return bool(self.env['hr.employee'].sudo().search_count(
                [('parent_id', '=', emp.id), ('active', '=', True)]))
        except Exception:               # noqa: BLE001
            return False

    @api.model
    def team(self):
        """My reports' training, as the system, scoped to my own company.

        AS THE SYSTEM AND NOT AS THEM. A manager holds no HR group by
        definition (R104), so reading a report's name or department in their
        own right would be an AccessError naming thirty payroll fields nobody
        asked for (R56). The boundary is the search — `parent_id` is me — and
        it is written out in the domain rather than assumed.
        """
        emp = self._my_employee()
        blank = {'manages': False, 'name': '', 'rows': [], 'people': 0,
                 'overdue': 0, 'due': 0, 'done': 0}
        if not emp:
            return blank
        reports = self.env['hr.employee'].sudo().search(
            [('parent_id', '=', emp.id), ('active', '=', True)])
        if not reports:
            return blank
        today = fields.Date.today()
        rows = self.env['pb.training.assignment'].sudo().search(
            [('employee_id', 'in', reports.ids),
             ('company_id', 'in', self.env.companies.ids)])
        rows._refresh()
        payload = [row._payload(today) for row in rows]
        rank = {'overdue': 0, 'excused': 1, 'assigned': 2, 'in_progress': 3,
                'done': 4}
        payload.sort(key=lambda r: (rank.get(r['state'], 5), -r['days_over'],
                                    r['due'] or '9999-12-31', r['who']))
        return {
            'manages': True,
            'name': emp.name or '',
            'rows': payload,
            'people': len(reports),
            'people_words': counted(len(reports), _('person'), _('people')),
            'overdue': len([r for r in payload if r['state'] == 'overdue']),
            'due': len([r for r in payload if r['state'] in ASSIGN_OPEN
                        and r['state'] != 'overdue']),
            'done': len([r for r in payload if r['state'] == 'done']),
        }

    @api.model
    def team_overdue_count(self):
        """The number on the portal home card for a manager. Never raises."""
        return self.env['pb.training.automation'].team_overdue_count()
