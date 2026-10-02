# -*- coding: utf-8 -*-
"""The Assignments tab's server surface — everything the HR board reads.

Same doctrine as E1's board: `@api.model` reads, every independent probe in its
own `_safe()` so one failing number answers zero instead of taking the screen
down, row caps that are PARAMETERS, and no sudo in a read except where a
field's own `groups=` forces it.

WHAT THIS BOARD IS FOR is the opposite question from E1's. E1 asks "what is in
the library"; this asks "who still owes what, and who is late". So the order is
PROBLEM FIRST (R113) — the most overdue row at the top, then what is due, then
what is running, then what is done — and the tiles count the four things
somebody can act on rather than the four things that are easy to count.

THE FACETS ARE BUILT FROM THE ROWS THAT ARE SHOWN and never from the table
(R80): a chip that counts one thing over a list that shows another is two bugs,
and the honest number beside a filter is the number of rows that filter would
leave behind.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .pb_training import PbTraining
from .training_common import (
    ASSIGN_OPEN, ASSIGN_REASONS, ASSIGN_STATES, DELAY_KIND_LABEL,
    DELAY_STATE_LABEL, P_ASSIGN_LIMIT, P_BULK_CAP, P_DAY1_AUTO,
    P_DEFAULT_DUE, P_HR_DAYS, P_MANAGER_DAYS, P_REMINDERS, as_id, counted,
    flag, fold, number,
)

_logger = logging.getLogger(__name__)


class PbTrainingAssignments(models.AbstractModel):
    _inherit = 'pb.training'

    #: E1's verbs plus this phase's. Written as the base tuple PLUS the new
    #: ones rather than as a fresh list, so a verb E1 adds later is not
    #: silently dropped by this extension.
    _VERBS = PbTraining._VERBS + (
        'assign', 'set_due', 'drop', 'run_reminders', 'open_assignment',
        'open_delay', 'open_assignments', 'open_schedules', 'new_schedule',
        'open_rules', 'new_rule', 'expand_people',
    )

    # =====================================================================
    #  the tab
    # =====================================================================
    @api.model
    def get_assignments(self, filters=None):
        """Every row, every number and every dial the tab needs, in one read."""
        if not self._can_read():
            return {'allowed': False, 'rows': [], 'kpis': {}}
        filters = filters or {}
        today = fields.Date.today()
        rows = self._safe(lambda: self._assignment_rows(filters, today),
                          default=[])
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'can_admin': self._can_admin(),
            'today': fields.Date.to_string(today),
            'rows': rows,
            'kpis': self._safe(lambda: self._assignment_kpis(rows),
                               default={}),
            'facets': self._safe(lambda: self._assignment_facets(rows),
                                 default={}),
            'delays': self._safe(lambda: self._delay_rows(), default=[]),
            'schedules': self._safe(lambda: self._schedule_rows(today),
                                    default=[]),
            'rules': self._safe(lambda: self._rule_rows(), default=[]),
            'reasons': [{'key': k, 'label': v} for k, v in ASSIGN_REASONS],
            'states': [{'key': k, 'label': v} for k, v in ASSIGN_STATES],
            'switches': {
                'reminders': flag(self.env, P_REMINDERS),
                'day1': flag(self.env, P_DAY1_AUTO),
                'manager_days': number(self.env, P_MANAGER_DAYS, 2),
                'hr_days': number(self.env, P_HR_DAYS, 5),
                'default_due_days': number(self.env, P_DEFAULT_DUE, 14),
            },
        }

    def _assignment_domain(self, filters):
        domain = [('company_id', 'in', self.env.companies.ids)]
        if filters.get('reason'):
            domain.append(('reason', '=', filters['reason']))
        if filters.get('state'):
            domain.append(('state', '=', filters['state']))
        if filters.get('channel_id'):
            domain.append(('channel_id', '=', as_id(filters['channel_id'])))
        if filters.get('department_id'):
            domain.append(('employee_id.department_id', 'child_of',
                           as_id(filters['department_id'])))
        if not filters.get('include_done'):
            domain.append(('state', 'in', ASSIGN_OPEN))
        return domain

    def _assignment_rows(self, filters, today):
        cap = number(self.env, P_ASSIGN_LIMIT, 400)
        rows = self.env['pb.training.assignment'].sudo().search(
            self._assignment_domain(filters), limit=cap)
        # The state is read, so it is brought up to date first: a board that
        # shows "Not started" over somebody who finished last night is a board
        # nobody trusts twice.
        rows._refresh()
        out = [row._payload(today) for row in rows]
        needle = fold(filters.get('term') or '')
        if needle:
            out = [r for r in out
                   if needle in fold(r['who']) or needle in fold(r['course'])]
        rank = {'overdue': 0, 'excused': 1, 'assigned': 2, 'in_progress': 3,
                'done': 4}
        return sorted(out, key=lambda r: (rank.get(r['state'], 5),
                                          -r['days_over'],
                                          r['due'] or '9999-12-31',
                                          fold(r['who'])))

    def _assignment_kpis(self, rows):
        today = fields.Date.today()
        week = [r for r in rows
                if r['state'] in ('assigned', 'in_progress') and r['due']
                and 0 <= (fields.Date.to_date(r['due']) - today).days <= 7]
        waiting = [r for r in rows
                   if (r.get('delay') or {}).get('state') == 'submitted']
        month = [r for r in rows if r['state'] == 'done' and r['completed_on']
                 and r['completed_on'][:7] == fields.Date.to_string(today)[:7]]
        return {
            'overdue': len([r for r in rows if r['state'] == 'overdue']),
            'due_week': len(week),
            'waiting': len(waiting),
            'done_month': len(month),
            'total': len(rows),
        }

    def _assignment_facets(self, rows):
        """Counted over the rows on the screen, never over the table (R80)."""
        def tally(key, label_of=None):
            seen = {}
            for row in rows:
                value = row.get(key)
                if value in (None, '', False):
                    continue
                entry = seen.setdefault(
                    value, {'key': value,
                            'label': label_of(row) if label_of else value,
                            'count': 0})
                entry['count'] += 1
            return sorted(seen.values(), key=lambda e: -e['count'])
        return {
            'reason': tally('reason', lambda r: r['reason_word']),
            'state': tally('state',
                           lambda r: dict(ASSIGN_STATES).get(r['state'], '')),
            'department': tally('department'),
            'course': tally('course'),
        }

    # --------------------------------------------------------- the requests
    def _delay_rows(self):
        rows = self.env['pb.training.delay'].sudo().search([
            ('company_id', 'in', self.env.companies.ids),
        ], limit=200)
        out = []
        for row in rows:
            out.append({
                'id': row.id,
                'who': row.employee_id.sudo().name or '',
                'course': row.channel_id.sudo().name or '',
                'kind': DELAY_KIND_LABEL.get(row.reason_kind, ''),
                'days': row.days_asked,
                'note': row.note or '',
                'state': row.state,
                'state_word': DELAY_STATE_LABEL.get(row.state, ''),
                'was': fields.Date.to_string(row.old_due_date) or '',
                'now': fields.Date.to_string(row.new_due_date) or '',
                'manager': row.employee_id.sudo().parent_id.name or '',
            })
        # Waiting on somebody first — that is the only row anybody can act on.
        rank = {'submitted': 0, 'draft': 1, 'approved': 2, 'refused': 3}
        return sorted(out, key=lambda r: (rank.get(r['state'], 4), -r['id']))

    # -------------------------------------------------------- the schedules
    def _schedule_rows(self, today):
        rows = self.env['pb.training.schedule'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)], limit=200)
        return [{
            'id': row.id,
            'name': row.name or '',
            'course': row.channel_id.sudo().name or '',
            'audience': dict(row._fields['audience'].selection).get(
                row.audience, ''),
            'where': (row.department_id.name or row.job_id.name
                      or row.company_id.name or ''),
            'every_months': row.every_months,
            'due_days': row.due_days,
            'next_run': fields.Date.to_string(row.next_run) or '',
            'overdue': bool(row.next_run and row.next_run < today),
            'last_run': fields.Date.to_string(row.last_run) or '',
            'last_count': row.last_count,
            'active': bool(row.active),
        } for row in rows]

    def _rule_rows(self):
        rows = self.env['pb.training.rule'].sudo().search(
            [('company_id', 'in', self.env.companies.ids)], limit=200)
        return [{
            'id': row.id,
            'name': row.name or '',
            'courses': row.channel_ids.sudo().mapped('name'),
            'due_days': row.due_days,
            'departments': row.department_ids.mapped('name'),
            'jobs': row.job_ids.mapped('name'),
            'active': bool(row.active),
        } for row in rows]

    # =====================================================================
    #  the things the tab does
    # =====================================================================
    @api.model
    def assign(self, channel_id, employee_ids, reason='adhoc', due_date=None,
               counts_for_probation=None):
        self._require_write()
        cap = number(self.env, P_BULK_CAP, 200)
        ids = [as_id(e) for e in (employee_ids or []) if as_id(e)]
        if len(ids) > cap:
            raise UserError(_(
                "That is %(n)s people at once. The most this screen will do "
                "in one press is %(cap)s — pick fewer, or ask for the limit "
                "to be raised.", n=len(ids), cap=cap))
        return self.env['pb.training.assignment'].assign_many(
            channel_id, ids, reason, due_date, counts_for_probation)

    @api.model
    def expand_people(self, kind, value=None):
        """Everybody in a department, everybody doing a job, everybody here.

        The BULK ergonomics the design bar asks for: nobody should tick
        forty-one boxes to put a department on a course. Read narrowly and as
        the system (R56), and only people with a login are offered — a course
        assigned to somebody with nowhere to see it is a course nobody does.
        """
        self._require_read()
        Employee = self.env['hr.employee'].sudo()
        domain = [('active', '=', True),
                  ('company_id', 'in', self.env.companies.ids)]
        if kind == 'department' and as_id(value):
            domain.append(('department_id', 'child_of', as_id(value)))
        elif kind == 'job' and as_id(value):
            domain.append(('job_id', '=', as_id(value)))
        elif kind != 'company':
            raise UserError(_("%s is not a group this screen can expand.",
                              kind))
        rows = Employee.search_read(domain, ['name', 'user_id'])
        out = [{'id': r['id'], 'name': r['name']}
               for r in rows if r.get('user_id')]
        skipped = len(rows) - len(out)
        return {
            'people': sorted(out, key=lambda r: fold(r['name'])),
            'skipped': skipped,
            'message': _("%(n)s %(word)s picked.", n=len(out),
                         word=counted(len(out), _('person'), _('people')))
            + ('' if not skipped else ' ' + (
                _("1 person has no login yet and was left out.")
                if skipped == 1 else
                _("%s people have no login yet and were left out.",
                  skipped))),
        }

    @api.model
    def departments(self):
        """The picker's own lists. Built once, with the data's own values."""
        self._require_read()
        depts = self.env['hr.department'].sudo().search_read(
            [('company_id', 'in', self.env.companies.ids)], ['name'])
        jobs = self.env['hr.job'].sudo().search_read(
            [('company_id', 'in', self.env.companies.ids)], ['name'])
        return {
            'departments': sorted(
                [{'id': d['id'], 'name': d['name']} for d in depts],
                key=lambda d: fold(d['name'])),
            'jobs': sorted([{'id': j['id'], 'name': j['name']} for j in jobs],
                           key=lambda j: fold(j['name'])),
        }

    @api.model
    def set_due(self, assignment_id, due_date):
        self._require_write()
        row = self.env['pb.training.assignment'].sudo().browse(
            as_id(assignment_id)).exists()
        if not row:
            raise UserError(_("That assignment is not here any more."))
        if not due_date:
            raise UserError(_("Pick a date."))
        row.write({'due_date': due_date, 'excused_until': False})
        row._clear_reminders()
        row._refresh_one()
        return {'message': _("Now due on %s. The chasing starts again from "
                             "that date.", due_date)}

    @api.model
    def drop(self, assignment_id):
        """Take a course off somebody's list. What they DID is kept.

        A mis-assignment with no way out is a dead end, and the design bar
        does not allow one. It is deliberately not an un-enrolment: the lessons
        they finished stay finished, so putting them back on picks up where
        they left off.
        """
        self._require_write()
        row = self.env['pb.training.assignment'].sudo().browse(
            as_id(assignment_id)).exists()
        if not row:
            raise UserError(_("That assignment is not here any more."))
        if row.state == 'done':
            raise UserError(_(
                "That one is finished, and a finished course is the record "
                "that it was done. It stays."))
        who = row.employee_id.sudo().name or ''
        course = row.channel_id.sudo().name or ''
        row.unlink()
        return {'message': _(
            "%(course)s is no longer on %(who)s's list. What they had already "
            "done is kept, so putting them back on picks up where they left "
            "off.", course=course, who=who)}

    @api.model
    def run_reminders(self):
        counts = self.env['pb.training.automation'].run_now()
        told = (counts.get('employee', 0) + counts.get('manager', 0)
                + counts.get('hr', 0))
        if not told:
            return {'message': _("Everything is up to date and nobody needed "
                                 "chasing.")}
        return {'message': _(
            "%(n)s %(word)s sent: %(emp)s to people, %(mgr)s to managers, "
            "%(hr)s to the HR lead.", n=told,
            word=counted(told, _('reminder'), _('reminders')),
            emp=counts.get('employee', 0), mgr=counts.get('manager', 0),
            hr=counts.get('hr', 0))}

    # =====================================================================
    #  the doors
    # =====================================================================
    def _door(self, name, model, res_id=None, view_mode='list,form',
              domain=None, context=None):
        """R125: a hand-built act_window dict MUST carry `views`, or the
        client throws before the screen opens and the user is shown the
        generic "something went wrong" dialog with nothing in the console."""
        views = [[False, v] for v in view_mode.split(',')]
        action = {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': model,
            'view_mode': view_mode,
            'views': views,
            'target': 'current',
        }
        if res_id:
            action.update({'res_id': as_id(res_id), 'view_mode': 'form',
                           'views': [[False, 'form']]})
        if domain is not None:
            action['domain'] = domain
        if context is not None:
            action['context'] = context
        return action

    @api.model
    def open_assignment(self, assignment_id):
        self._require_read()
        return self._door(_("Training assignment"), 'pb.training.assignment',
                          res_id=assignment_id)

    @api.model
    def open_delay(self, delay_id):
        self._require_read()
        return self._door(_("Request for more time"), 'pb.training.delay',
                          res_id=delay_id)

    @api.model
    def open_assignments(self):
        self._require_read()
        return self._door(_("Training assignments"),
                          'pb.training.assignment')

    @api.model
    def open_schedules(self):
        self._require_read()
        return self._door(_("Compliance schedules"), 'pb.training.schedule')

    @api.model
    def new_schedule(self):
        self._require_write()
        return self._door(_("New schedule"), 'pb.training.schedule',
                          view_mode='form')

    @api.model
    def open_rules(self):
        self._require_read()
        return self._door(_("Day-one courses"), 'pb.training.rule')

    @api.model
    def new_rule(self):
        self._require_write()
        return self._door(_("New day-one rule"), 'pb.training.rule',
                          view_mode='form')

    # =====================================================================
    #  the dispatcher
    # =====================================================================
    @api.model
    def act(self, verb, payload=None):
        payload = payload or {}
        if verb == 'assign':
            return self.assign(payload.get('channel_id'),
                               payload.get('employee_ids'),
                               payload.get('reason') or 'adhoc',
                               payload.get('due_date'),
                               payload.get('counts_for_probation'))
        if verb == 'set_due':
            return self.set_due(payload.get('assignment_id'),
                                payload.get('due_date'))
        if verb == 'drop':
            return self.drop(payload.get('assignment_id'))
        if verb == 'open_assignment':
            return self.open_assignment(payload.get('assignment_id'))
        if verb == 'open_delay':
            return self.open_delay(payload.get('delay_id'))
        if verb == 'expand_people':
            return self.expand_people(payload.get('kind'),
                                      payload.get('value'))
        return super().act(verb, payload)
