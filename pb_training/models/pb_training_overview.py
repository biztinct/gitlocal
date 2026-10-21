# -*- coding: utf-8 -*-
"""Learning › OVERVIEW — the training team's one-glance page (LEARNING L0).

One read, `pb.training.overview()`, behind the same gate as the board
(`{'allowed': False}` without a training group, never an AccessError, so the
screen can say who it is for instead of failing).

THE NUMBERS ARE THE BOARD'S OWN NUMBERS. The queue reads the very helpers the
Assigned and Claims tabs read (`_assignment_rows` / `_assignment_kpis`,
`_claim_rows` / `_claim_kpis`) with the tabs' default filters, so "3 claims to
agree" here is always the number the Claims tab shows when it opens — a second
way of counting would sooner or later disagree with the first (R80).

THE HEADLINE IS WHOLE SENTENCES (R117): one per fact, each chosen whole for
its count, never a frame with a number dropped into it, and never a number
without its noun.

Its own file rather than `pb_training.py` because it reads methods that the
Assigned and Claims extensions add to the facade; it is imported after both.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

#: How many departments the overview lists — the biggest by people.
DEPARTMENTS_SHOWN = 6


class PbTrainingOverview(models.AbstractModel):
    _inherit = 'pb.training'

    @api.model
    def overview(self):
        if not self._can_read():
            return {'allowed': False}
        today = fields.Date.today()
        rows = self._safe(lambda: self._assignment_rows({}, today), default=[])
        kpis = self._safe(lambda: self._assignment_kpis(rows), default={})
        claim_rows = self._safe(lambda: self._claim_rows({}), default=[])
        claim_kpis = self._safe(lambda: self._claim_kpis(claim_rows),
                                default={})
        month = self._safe(lambda: self._overview_month(rows, today),
                           default={'due': 0, 'past': 0, 'finished': 0})
        people = len({r['employee_id'] for r in rows})
        courses = len({r['channel_id'] for r in rows})
        return {
            'allowed': True,
            'people': people,
            'courses': courses,
            'headline': self._overview_headline(people, courses,
                                                kpis.get('overdue', 0),
                                                month.get('finished', 0)),
            'calm': not rows and not month.get('finished'),
            'queue': [
                {'key': 'claims', 'label': _("Claims to agree"),
                 'count': claim_kpis.get('waiting', 0),
                 'lens': 'claims', 'tab': ''},
                {'key': 'requests', 'label': _("More time requests"),
                 'count': kpis.get('waiting', 0),
                 'lens': 'assigned', 'tab': 'requests'},
                {'key': 'late', 'label': _("Past their date"),
                 'count': kpis.get('overdue', 0),
                 'lens': 'assigned', 'tab': 'assignments'},
            ],
            'month': month,
            'departments': self._safe(self._overview_departments, default=[]),
        }

    # ------------------------------------------------------------ the words
    @api.model
    def _overview_headline(self, people, courses, late, finished):
        """'38 people are on 6 courses. 4 are past their date. 11 finished
        this month.' — or one calm sentence when there is nothing to say."""
        if not people:
            first = _("Nobody is on a course yet.")
            if finished:
                first = _("Nobody is on a course right now.")
        elif people == 1 and courses == 1:
            first = _("1 person is on 1 course.")
        elif people == 1:
            first = _("1 person is on %(courses)s courses.", courses=courses)
        elif courses == 1:
            first = _("%(people)s people are on 1 course.", people=people)
        else:
            first = _("%(people)s people are on %(courses)s courses.",
                      people=people, courses=courses)
        bits = [first]
        if late == 1:
            bits.append(_("1 is past their date."))
        elif late:
            bits.append(_("%(late)s are past their date.", late=late))
        if finished == 1:
            bits.append(_("1 finished this month."))
        elif finished:
            bits.append(_("%(done)s finished this month.", done=finished))
        return ' '.join(str(b) for b in bits)

    # ------------------------------------------------------------ this month
    @api.model
    def _overview_month(self, rows, today):
        """Due this month (still open), past their date, finished this month."""
        start = today.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        due = 0
        for r in rows:
            if r['state'] in ('assigned', 'in_progress') and r['due']:
                day = fields.Date.to_date(r['due'])
                if start <= day < nxt:
                    due += 1
        finished = self.env['pb.training.assignment'].sudo().search_count([
            ('company_id', 'in', self.env.companies.ids),
            ('state', '=', 'done'),
            ('completed_on', '>=', start),
            ('completed_on', '<', nxt),
        ])
        return {
            'due': due,
            'past': len([r for r in rows if r['state'] == 'overdue']),
            'finished': finished,
        }

    # ------------------------------------------------------------ departments
    @api.model
    def _overview_departments(self):
        """The biggest departments by people over the last 90 days, each with
        how much of what was set is finished — worked out by the Numbers
        tab's own `_core`, so the two can never disagree."""
        analytics = self.env['pb.training.analytics']
        start, end = analytics._range()
        rows = self.env['pb.training.assignment'].sudo().search(
            analytics._domain(start, end))
        groups = {}
        for row in rows:
            name = row.employee_id.sudo().department_id.name \
                or _('No department')
            groups.setdefault(name, self.env['pb.training.assignment'])
            groups[name] |= row
        out = []
        for name, group in groups.items():
            core = analytics._core(group)
            out.append({
                'name': name,
                'people': len(group.mapped('employee_id')),
                'percent': core.get('completion') or 0,
                'overdue': core.get('overdue', 0),
            })
        out.sort(key=lambda d: (-d['people'], d['name'].lower()))
        return out[:DEPARTMENTS_SHOWN]
