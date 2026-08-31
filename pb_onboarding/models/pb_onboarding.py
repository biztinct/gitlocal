# -*- coding: utf-8 -*-
"""`pb.onboarding` — the New joiners lens's only server surface.

The shape `pb_people` established and every cockpit since has kept: an
`AbstractModel` facade, `@api.model` reads, every independent probe inside its
own `_safe()` so one failing metric answers zero instead of taking the screen
down, `self.env.companies` scoping on every search, a row cap, and no sudo in a
read.

The gate is SERVER-SIDE and it is the boundary — the lens gate in the hub config
is a visibility hint. A reader with no lifecycle group gets an EMPTY BOARD with
`allowed: false` rather than an access dialog, so the screen can say in words
what it is and who to ask.

It reuses P0's tiers deliberately. Onboarding is not a separate permission from
the rest of the lifecycle: the board answers "how is this joiner doing", which
is the same question the Journeys board answers about the same cases, and a
fourth ladder would be a group nobody knew to grant.
"""

import logging
from datetime import date, timedelta

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .newhire_pulse import SCORE_WORD
from .onboarding_common import (
    DAY_MARK_LABEL, GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, initials,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 300

#: A joiner is "new" for this long after their first day. Past it the journey
#: may still be running (a stray step nobody ticked) but the person is a
#: colleague, not a new joiner, and a board that says otherwise is wrong.
NEW_FOR_DAYS = 120


class PbOnboarding(models.AbstractModel):
    _name = 'pb.onboarding'
    _description = 'Payobook New Joiners cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('New joiners metric failed: %s', e)
            return default

    @api.model
    def _can_read(self):
        user = self.env.user
        return (user.has_group(GROUP_USER) or user.has_group(GROUP_MANAGER)
                or user.has_group(GROUP_ADMIN) or user._is_admin())

    @api.model
    def _can_write(self):
        user = self.env.user
        return (user.has_group(GROUP_MANAGER) or user.has_group(GROUP_ADMIN)
                or user._is_admin())

    @api.model
    def _require_write(self):
        if not self._can_write():
            raise AccessError(_(
                "You can look at the new joiners, but changing one is for the "
                "HR team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'countries': [], 'departments': [],
                    'months': []}
        Case = self.env['pb.journey.case']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()
        floor = today - timedelta(days=NEW_FOR_DAYS)

        cases = self._safe(lambda: Case.search([
            ('company_id', 'in', co_ids),
            ('case_type', '=', 'onboarding'),
            ('state', 'in', ('draft', 'active', 'on_hold')),
            '|', ('anchor_date', '=', False), ('anchor_date', '>=', floor),
        ], order='anchor_date desc, id desc', limit=BOARD_LIMIT),
            default=Case.browse())

        rows = []
        for case in cases:
            try:
                rows.append(self._row(case, today))
            except Exception:
                _logger.exception('New joiners row for case %s', case.id)

        week_end = today + timedelta(days=7)
        kpis = {
            'joining': len([r for r in rows if r['doj']
                            and today <= _d(r['doj']) <= week_end]),
            'started': len([r for r in rows if r['doj']
                            and _d(r['doj']) <= today]),
            'no_buddy': len([r for r in rows if not r['buddy']]),
            'overdue': sum(r['overdue'] for r in rows),
            'red': len([r for r in rows if r['pulse_red']]),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'countries': _facet(rows, 'country'),
            'departments': _facet(rows, 'dept'),
            'months': _facet(rows, 'month'),
        }

    @api.model
    def _row(self, case, today=None):
        today = today or date.today()
        emp = case.employee_id
        doj = case.anchor_date or self._safe(lambda: case._joining_date(),
                                             default=False)
        days = (doj - today).days if doj else None
        pulses = self._safe(lambda: self.env['pb.newhire.pulse'].search(
            [('case_id', '=', case.id)], order='due_date'),
            default=self.env['pb.newhire.pulse'].browse())
        answered = [p for p in pulses if p.state == 'answered']
        last = answered[-1] if answered else None
        batch = self._safe(
            lambda: self.env['pb.orientation.batch'].search(
                [('attendee_ids', 'in', emp.id),
                 ('state', '!=', 'cancelled')],
                order='batch_date', limit=1),
            default=self.env['pb.orientation.batch'].browse())
        buddy = emp._pb_buddy_now() if emp else None
        return {
            'id': case.id,
            'employee_id': emp.id,
            'employee': emp.name or '—',
            'initials': initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id
            if emp else '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': (emp.department_id.name if emp.department_id else '')
            or _('No team'),
            'country': (emp.country_id.name if emp.country_id else '')
            or (emp.company_id.country_id.name
                if emp.company_id and emp.company_id.country_id else '')
            or _('Not set'),
            'doj': str(doj) if doj else '',
            'month': str(doj)[:7] if doj else '',
            'days': days,
            'when': _when(days),
            'progress': case.progress,
            'open_tasks': case.open_task_count,
            'overdue': case.overdue_task_count,
            'buddy': (buddy.name if buddy else ''),
            'buddy_id': buddy.id if buddy else 0,
            'buddy_temp': bool(emp.buddy_temp_id and buddy
                               and buddy.id == emp.buddy_temp_id.id),
            'hrbp': emp.hrbp_user_id.name if emp.hrbp_user_id else '',
            'hrbp_id': emp.hrbp_user_id.id if emp.hrbp_user_id else 0,
            'orientation': str(batch.batch_date) if batch else '',
            'complete': self._safe(lambda: emp.profile_complete_pct,
                                   default=0),
            'missing': self._safe(lambda: emp.profile_missing, default='')
            or '',
            'pulses': [{'mark': p.day_mark,
                        'mark_label': DAY_MARK_LABEL.get(p.day_mark, ''),
                        'state': p.state,
                        'score': p.score or '',
                        'word': SCORE_WORD.get(p.score or '', ''),
                        'red': p.red_flag} for p in pulses],
            'pulse_last': (SCORE_WORD.get(last.score or '', '')
                           if last else ''),
            'pulse_score': (last.score or '') if last else '',
            'pulse_red': bool([p for p in pulses if p.red_flag]),
        }

    # ------------------------------------------------------------- one joiner
    @api.model
    def get_joiner(self, case_id):
        """The whole of one joiner — the P0 case detail, plus our own columns.

        The steps, check-ins and letters are read through `pb.journeys` rather
        than re-derived: two implementations of "what is on this checklist"
        would drift the first week one of them grew a column.
        """
        if not self._can_read():
            raise AccessError(_(
                "New joiners are looked after by the HR team."))
        case = self.env['pb.journey.case'].browse(int(case_id)).exists()
        if not case:
            raise UserError(_("That joining checklist is no longer there."))
        detail = self.env['pb.journeys'].get_case(case.id)
        emp = case.employee_id
        detail['joiner'] = self._row(case)
        detail['buddy_card'] = emp._pb_buddy_now()._pb_card() \
            if (emp and emp._pb_buddy_now()) else None
        detail['hrbp_card'] = {
            'name': emp.hrbp_user_id.name,
            'email': emp.hrbp_user_id.email or '',
            'initials': initials(emp.hrbp_user_id.name),
        } if (emp and emp.hrbp_user_id) else None
        return detail

    # --------------------------------------------------------------- buddies
    @api.model
    def buddy_candidates(self, employee_id, term=None):
        if not self._can_read():
            return []
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            return []
        return self.env['pb.buddy.nomination'].suggest_candidates(
            emp, term=term)

    @api.model
    def buddy_choose(self, employee_id, candidate_id, case_id=None):
        self._require_write()
        nomination = self.env['pb.buddy.nomination'].open_for(
            employee_id, case_id)
        return nomination.choose(candidate_id)

    @api.model
    def buddy_temp(self, employee_id, temp_id, date_from=None, date_to=None):
        self._require_write()
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("That person could not be found."))
        return emp.set_temp_buddy(temp_id, date_from, date_to)

    # ------------------------------------------------------------- the doing
    @api.model
    def run_step_now(self, task_id):
        """Run an automatic step today instead of waiting for its date."""
        self._require_write()
        task = self.env['pb.journey.task'].browse(int(task_id)).exists()
        if not task:
            raise UserError(_("That step is no longer there."))
        if not task.is_automatic:
            raise UserError(_(
                "This step is for a person to do — there is nothing to run."))
        if not task.action_auto(force=True):
            raise UserError(_(
                "Nothing was sent. %s",
                task.auto_error or _(
                    "There may be nobody to write to, or the step may be "
                    "switched off in the settings.")))
        return True

    @api.model
    def backfill_hrbp(self):
        self._require_write()
        return {'touched': self.env['pb.hrbp.rule'].backfill()}

    @api.model
    def run_automation(self):
        """The daily job, on demand. Managers only — it sends email."""
        self._require_write()
        return self.env['pb.journey.case'].run_onboarding_automation()

    # ------------------------------------------------------------ the pieces
    @api.model
    def get_settings(self):
        """What the cog shows: the sessions and the HR partner rules."""
        if not self._can_read():
            return {'allowed': False, 'batches': [], 'rules': []}
        co_ids = self.env.companies.ids or [self.env.company.id]
        Batch = self.env['pb.orientation.batch']
        Rule = self.env['pb.hrbp.rule']
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'batches': self._safe(lambda: [
                {'id': b.id, 'date': str(b.batch_date),
                 'state': b.state, 'people': b.attendee_count,
                 'location': b.location or ''}
                for b in Batch.search(
                    [('company_id', 'in', co_ids)],
                    order='batch_date desc', limit=24)], default=[]),
            'rules': self._safe(lambda: [
                {'id': r.id, 'name': r.name,
                 'country': r.country_id.name or '',
                 'dept': r.department_id.name or '',
                 'who': r.hrbp_user_id.name or ''}
                for r in Rule.search(
                    ['|', ('company_id', '=', False),
                     ('company_id', 'in', co_ids)],
                    order='sequence, id')], default=[]),
        }


def _d(value):
    from datetime import datetime
    return datetime.strptime(value, '%Y-%m-%d').date()


def _when(days):
    """"in 3 days" / "today" / "12 days in" — words, not arithmetic."""
    if days is None:
        return ''
    if days == 0:
        return _('starts today')
    if days == 1:
        return _('starts tomorrow')
    if days > 0:
        return _('starts in %s days', days)
    if days == -1:
        return _('1 day in')
    return _('%s days in', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
