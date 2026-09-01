# -*- coding: utf-8 -*-
"""`pb.probation` — the Probation lens's only server surface.

The shape every cockpit in this product keeps: an `AbstractModel` facade,
`@api.model` reads, every independent probe inside its own `_safe()` so one
failing metric answers zero instead of taking the screen down,
`self.env.companies` scoping on every search, a row cap, and no sudo in a READ.

It reuses P0's tiers, the same call P3 and P4 made for the same reason: a trial
period is not a separate permission from the rest of the lifecycle, and a sixth
ladder would be a group nobody knew to grant.

THE QUESTION THIS BOARD ANSWERS is the one an HR coordinator asks on the first
Monday of a month: WHOSE TRIAL PERIOD ENDS SOON, and is anything in the way of
deciding. So a row is a PERSON, the number beside their name is the days left,
and the four things after it are the four things that hold a decision up — the
colleagues nobody has chosen, the answers nobody has given, the course nobody
has finished, and the flag somebody raised at the sixty-day conversation.
"""

import logging
from datetime import date

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError

from .probation_common import (
    GROUP_ADMIN, GROUP_MANAGER, GROUP_USER, MAX_NOMINEES, MIN_NOMINEES,
    P_AUTO_TRIGGER, PROBATION_STATE_LABEL, REVIEW_STATE_LABEL, VERDICT_LABEL,
    flag, initials,
)

_logger = logging.getLogger(__name__)

BOARD_LIMIT = 300

#: How red the days-left number goes.
URGENT_DAYS = 7


class PbProbation(models.AbstractModel):
    _name = 'pb.probation'
    _description = 'Payobook Probation cockpit data'

    # ------------------------------------------------------------------ gates
    @api.model
    def _safe(self, fn, default=0):
        try:
            return fn()
        except Exception as e:
            _logger.debug('Probation metric failed: %s', e)
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
                "You can look at who is in their trial period, but running a "
                "review is for the HR team. Ask them to make the change."))
        return True

    # ------------------------------------------------------------- the board
    @api.model
    def get_board(self):
        if not self._can_read():
            return {'allowed': False, 'can_write': False, 'kpis': {},
                    'rows': [], 'countries': [], 'departments': [],
                    'states': [], 'auto_on': False}
        Emp = self.env['hr.employee']
        co_ids = self.env.companies.ids or [self.env.company.id]
        today = date.today()

        people = self._safe(lambda: Emp.search([
            ('company_id', 'in', co_ids),
            ('active', '=', True),
            ('pb_probation_state', 'in', ['in_probation', 'extended']),
        ], order='id', limit=BOARD_LIMIT), default=Emp.browse())

        rows = []
        for person in people:
            try:
                rows.append(self._row(person, today))
            except Exception:
                _logger.exception('Probation row for employee %s', person.id)
        rows.sort(key=lambda r: (r['days'] if r['days'] is not None else 9999,
                                 r['employee']))

        kpis = {
            'in_probation': len(rows),
            'running': len([r for r in rows if r['review_state']
                            and r['review_state'] != 'closed']),
            'verdicts': len([r for r in rows
                             if r['review_state'] == 'verdict']),
            'overdue_feedback': len([r for r in rows if r['feedback_late']]),
            'urgent': len([r for r in rows if r['days'] is not None
                           and r['days'] <= URGENT_DAYS]),
        }
        return {
            'allowed': True,
            'can_write': self._can_write(),
            'auto_on': flag(self.env, P_AUTO_TRIGGER),
            'kpis': kpis,
            'rows': rows,
            'total': len(rows),
            'capped': len(rows) >= BOARD_LIMIT,
            'countries': _facet(rows, 'country'),
            'departments': _facet(rows, 'dept'),
            'states': _facet(rows, 'review_label'),
            'min_nominees': MIN_NOMINEES,
            'max_nominees': MAX_NOMINEES,
        }

    @api.model
    def _row(self, emp, today=None):
        today = today or date.today()
        Review = self.env['pb.probation.review']
        review = self._safe(
            lambda: Review.search([('employee_id', '=', emp.id)],
                                  order='state, id desc', limit=1),
            default=Review.browse())
        trial = self._safe(lambda: emp.sudo().trial_date_end, default=False)
        days = (trial - today).days if trial else None
        training = self._safe(
            lambda: self.env['pb.training.status'].summary_for(emp),
            default={'total': 0, 'done': 0, 'pending': [], 'ok': True,
                     'has_track': False})
        flags = self._safe(
            lambda: self.env['pb.employee.checkin'].sudo().search_count([
                ('employee_id', '=', emp.id), ('red_flag', '=', True),
                ('state', '!=', 'cancelled')]), default=0)
        deadline = review.feedback_deadline if review else False
        return {
            'id': emp.id,
            'review_id': review.id if review else 0,
            'employee': emp.name or '—',
            'initials': initials(emp.name),
            'avatar': '/web/image/hr.employee/%s/avatar_128' % emp.id,
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '')
            or '',
            'dept': (emp.department_id.name if emp.department_id else '')
            or _('No team'),
            'country': (emp.country_id.name if emp.country_id else '')
            or (emp.company_id.country_id.name
                if emp.company_id and emp.company_id.country_id else '')
            or _('Not set'),
            'manager': emp.parent_id.name if emp.parent_id else '',
            'doj': str(self._safe(lambda: emp._pb_join_date(), default='')
                       or ''),
            'trial_end': str(trial) if trial else '',
            'days': days,
            'when': _when(days),
            'urgent': bool(days is not None and days <= URGENT_DAYS),
            'state': emp.pb_probation_state or '',
            'state_label': PROBATION_STATE_LABEL.get(
                emp.pb_probation_state or '', ''),
            'round': review.round if review else 0,
            'review_state': review.state if review else '',
            'review_label': REVIEW_STATE_LABEL.get(review.state, '')
            if review else _('Not started'),
            'nominees': review.nominee_count if review else 0,
            'feedback_in': review.feedback_in if review else 0,
            'feedback_total': review.feedback_total if review else 0,
            'deadline': str(deadline) if deadline else '',
            'feedback_late': bool(
                review and review.state == 'feedback' and deadline
                and deadline < today),
            'deadline_extended': bool(review and review.deadline_extended),
            'verdict': review.verdict if review else '',
            'verdict_label': VERDICT_LABEL.get(review.verdict, '')
            if review else '',
            'training_ok': training['ok'],
            'training_done': training['done'],
            'training_total': training['total'],
            'training_pending': training['pending'],
            'red_flags': flags,
            'has_report': bool(review and review.consolidated_html),
        }

    # ------------------------------------------------------------ one person
    @api.model
    def get_person(self, employee_id):
        """One trial period, whole — the drawer behind a row."""
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        emp = self.env['hr.employee'].browse(int(employee_id)).exists()
        if not emp:
            raise UserError(_("That person could not be found."))
        review = self.env['pb.probation.review'].search(
            [('employee_id', '=', emp.id)], order='state, id desc', limit=1)
        checkins = self._safe(
            lambda: self.env['pb.employee.checkin'].sudo().search(
                [('employee_id', '=', emp.id), ('state', '!=', 'cancelled')],
                order='scheduled_date'),
            default=self.env['pb.employee.checkin'].browse())
        training = self._safe(
            lambda: self.env['pb.training.status'].sudo().search(
                [('employee_id', '=', emp.id)], order='track_id, id'),
            default=self.env['pb.training.status'].browse())
        return {
            'row': self._row(emp),
            'timeline': self._timeline(emp, review, checkins),
            'report': str(review.consolidated_html or '') if review else '',
            'avg_rating': review.avg_rating if review else 0.0,
            'strengths': (review.strengths or '') if review else '',
            'improvements': (review.improvements or '') if review else '',
            'peers': [{
                'name': p.name or '',
                'dept': p.department_id.name if p.department_id else '',
                'answered': self._peer_answered(review, p),
            } for p in (review.nominee_ids if review
                        else self.env['hr.employee'].browse())],
            'training': [{
                'id': t.id,
                'name': t.item_id.name or '',
                'track': t.track_id.name or '',
                'required': t.required,
                'done': t.state == 'done',
                'score': t.score,
            } for t in training],
            'checkins': [{
                'id': c.id,
                'name': c.name or '',
                'date': str(c.scheduled_date) if c.scheduled_date else '',
                'state': c.state,
                'notes': c.notes or '',
                'red': c.red_flag,
                'red_note': c.red_flag_note or '',
            } for c in checkins],
            'one_on_one': {
                'id': review.one_on_one_checkin_id.id,
                'date': str(review.one_on_one_checkin_id.scheduled_date or ''),
                'done': review.one_on_one_checkin_id.state == 'done',
            } if (review and review.one_on_one_checkin_id) else None,
            'letter_id': review.letter_id.id
            if (review and review.letter_id) else 0,
            'exit_case_id': review.exit_case_id.id
            if (review and review.exit_case_id) else 0,
        }

    def _peer_answered(self, review, person):
        if not review:
            return False
        for row in review.feedback_request_ids:
            same_user = (row.respondent_user_id and person.user_id
                         and row.respondent_user_id.id == person.user_id.id)
            same_mail = (row.respondent_email and person.work_email
                         and row.respondent_email.strip().lower()
                         == person.work_email.strip().lower())
            if same_user or same_mail:
                return row.state == 'submitted'
        return False

    def _timeline(self, emp, review, checkins):
        """Joining day, the conversations, the review, the trial end.

        One list, in date order, so the drawer tells a story rather than
        showing four boxes the reader has to reconcile.
        """
        out = []
        joined = self._safe(lambda: emp._pb_join_date(), default=False)
        if joined:
            out.append({'date': str(joined), 'kind': 'start',
                        'title': _('Joined'), 'note': ''})
        for row in checkins:
            out.append({
                'date': str(row.scheduled_date or ''),
                'kind': 'flag' if row.red_flag else 'checkin',
                'title': row.name or '',
                'note': row.red_flag_note or row.notes or '',
                'done': row.state == 'done',
            })
        if review:
            if review.create_date:
                out.append({'date': str(review.create_date.date()),
                            'kind': 'review',
                            'title': _('Review opened'), 'note': ''})
            if review.feedback_deadline:
                out.append({
                    'date': str(review.feedback_deadline), 'kind': 'review',
                    'title': _('Colleagues answer by'),
                    'note': _('%(done)s of %(total)s answered',
                              done=review.feedback_in,
                              total=review.feedback_total)})
            if review.verdict_at:
                out.append({'date': str(review.verdict_at.date()),
                            'kind': 'verdict',
                            'title': VERDICT_LABEL.get(review.verdict, ''),
                            'note': ''})
        trial = self._safe(lambda: emp.sudo().trial_date_end, default=False)
        if trial:
            out.append({'date': str(trial), 'kind': 'end',
                        'title': _('Trial period ends'), 'note': ''})
        out.sort(key=lambda e: e['date'] or '')
        return out

    # =====================================================================
    #  WRITES. Every one of them goes through the model that owns the fact.
    # =====================================================================
    @api.model
    def start_review(self, employee_id):
        self._require_write()
        review = self.env['pb.probation.review'].open_for(int(employee_id))
        review.action_start_nomination()
        return {'review_id': review.id}

    @api.model
    def nominee_options(self, employee_id, term=None):
        if not self._can_read():
            return []
        review = self.env['pb.probation.review'].open_for(int(employee_id))
        return review.suggest_nominees(term=term)

    @api.model
    def confirm_nominees(self, employee_id, nominee_ids):
        self._require_write()
        review = self.env['pb.probation.review'].open_for(int(employee_id))
        return review.action_confirm_nominees(nominee_ids)

    @api.model
    def extend_deadline(self, review_id):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_extend_deadline()

    @api.model
    def consolidate(self, review_id):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        review.action_consolidate()
        return True

    @api.model
    def finish_one_on_one(self, review_id, notes=None):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_one_on_one_done(notes=notes)

    @api.model
    def verdict_preview(self, review_id, verdict, extension_months=None):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.verdict_preview(verdict, extension_months)

    @api.model
    def save_verdict(self, review_id, verdict, strengths=None,
                     improvements=None, extension_months=None):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_verdict(verdict, strengths=strengths,
                                     improvements=improvements,
                                     extension_months=extension_months)

    @api.model
    def start_exit(self, review_id):
        self._require_write()
        review = self.env['pb.probation.review'].browse(
            int(review_id)).exists()
        if not review:
            raise UserError(_("That review could not be found."))
        return review.action_start_exit()

    @api.model
    def settle_training(self, status_id, done=True, score=None):
        self._require_write()
        row = self.env['pb.training.status'].sudo().browse(
            int(status_id)).exists()
        if not row:
            raise UserError(_("That training item could not be found."))
        return row.action_done(score=score) if done else row.action_reopen()

    @api.model
    def run_automation(self):
        self._require_write()
        return self.env['pb.journey.case'].run_probation_automation()

    # ------------------------------------------------------------ the doors
    @api.model
    def open_review_action(self, review_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pb.probation.review',
            'res_id': int(review_id),
            'view_mode': 'form',
        }

    @api.model
    def open_letter_action(self, letter_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        letter = self.env['pb.hr.letter'].browse(int(letter_id)).exists()
        if not letter:
            raise UserError(_("That letter could not be found."))
        return letter.action_open_pdf()

    @api.model
    def open_employee_action(self, employee_id):
        if not self._can_read():
            raise AccessError(_("This is looked after by the HR team."))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'res_id': int(employee_id),
            'view_mode': 'form',
        }


def _when(days):
    """"in 12 days" / "today" / "6 days ago" — never a bare number."""
    if days is None:
        return _('no date set')
    if days == 0:
        return _('ends today')
    if days == 1:
        return _('ends tomorrow')
    if days > 1:
        return _('in %s days', days)
    if days == -1:
        return _('ended yesterday')
    return _('%s days ago', -days)


def _facet(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key) or ''
        if value:
            counts[value] = counts.get(value, 0) + 1
    return [{'id': k, 'label': k, 'count': v}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]
