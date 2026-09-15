# -*- coding: utf-8 -*-
"""The one job that runs at night, and the button that runs exactly it.

TWO NUDGES AND NOTHING ELSE. An advert that has been waiting to be agreed for
longer than it should, and a role that is open with nobody recruiting it.
Both are the same shape of failure: somebody is waiting for a person who does
not know they are being waited for.

IDEMPOTENT BY THE TO-DO IT RAISES, not by a stamp of its own. A search for an
open activity with the same summary on the same record is the only test that
survives a record being nudged, dealt with and going stale again — which is
the whole point of a daily job. Every record gets its own try/except, the
counts are honest, and a failure is logged at WARNING with its traceback
(R92), never swallowed.

"RUN IT NOW" DOES EXACTLY WHAT THE NIGHT DOES (R53). A button that runs four
fifths of a job produces a number nobody can compare to the morning's log.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models

from .hiring_common import (
    P_DOC_REMINDER_DAYS, P_JD_REMINDER_DAYS, P_RECRUITER_NUDGE_DAYS,
    P_REMINDER_CAP, P_REMINDERS, P_URGENT_AFTER_HOURS, counted, flag, leg,
    number,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'


class PbHiringAutomation(models.AbstractModel):
    _name = 'pb.hiring.automation'
    _description = 'Payobook Hiring daily step'

    # =====================================================================
    #  The night
    # =====================================================================
    @api.model
    def _cron_daily(self):
        counts = self.run_now()
        _logger.info('pb_hiring: %s', self.describe(counts))
        return counts

    @api.model
    def run_now(self):
        counts = {'jd': 0, 'recruiter': 0, 'late_feedback': 0,
                  'documents': 0, 'doc_overdue': 0, 'cover_started': 0,
                  'cover_ended': 0}
        for key, fn in (('jd', self._nudge_adverts),
                        ('recruiter', self._nudge_open_roles),
                        ('late_feedback', self._chase_late_feedback),
                        ('documents', self._chase_documents),
                        ('doc_overdue', self._document_deadlines),
                        ('cover', self._move_covers)):
            try:
                answer = fn()
                if key == 'cover':
                    counts['cover_started'] = answer.get('started', 0)
                    counts['cover_ended'] = answer.get('ended', 0)
                else:
                    counts[key] = answer
            except Exception:           # noqa: BLE001 — a job never raises
                _logger.warning('pb_hiring: the %s nudge failed', key,
                                exc_info=True)
        return counts

    @api.model
    def describe(self, counts):
        """The sentence a person reads, with the real numbers in it.

        BRANCHED WHOLE (R117): a frame with one word swapped in produces
        "You does not have", and a translator handed the frame and the word
        separately cannot fix a verb they were never given. With three
        numbers the combinations stop being worth branching by hand, so each
        clause is a whole sentence of its own and they are joined.
        """
        jd = counts.get('jd', 0)
        rec = counts.get('recruiter', 0)
        late = counts.get('late_feedback', 0)
        parts = []
        if jd:
            parts.append(_("%(n)s %(word)s nudged.", n=jd,
                           word=counted(jd, _('job description was'),
                                        _('job descriptions were'))))
        if rec:
            parts.append(_("%(n)s open %(word)s still nobody recruiting it.",
                           n=rec,
                           word=counted(rec, _('role has'), _('roles have'))))
        if late:
            parts.append(_("%(n)s late %(word)s chased.", n=late,
                           word=counted(late, _('opinion was'),
                                        _('opinions were'))))
        docs = counts.get('documents', 0)
        if docs:
            parts.append(_("%(n)s %(word)s reminded about their papers.",
                           n=docs, word=counted(docs, _('candidate was'),
                                                _('candidates were'))))
        overdue = counts.get('doc_overdue', 0)
        if overdue:
            parts.append(_("%(n)s document %(word)s past the date.", n=overdue,
                           word=counted(overdue, _('request is'),
                                        _('requests are'))))
        started = counts.get('cover_started', 0)
        ended = counts.get('cover_ended', 0)
        if started:
            parts.append(_("%(n)s %(word)s started.", n=started,
                           word=counted(started, _('cover has'),
                                        _('covers have'))))
        if ended:
            parts.append(_("%(n)s %(word)s finished.", n=ended,
                           word=counted(ended, _('cover has'),
                                        _('covers have'))))
        if not parts:
            return _("Nothing needed chasing today.")
        return ' '.join(parts)

    # =====================================================================
    #  An advert nobody has agreed
    # =====================================================================
    @api.model
    def _nudge_adverts(self):
        days = max(1, number(self.env, P_JD_REMINDER_DAYS, 3))
        # THE SERVER'S OWN CLOCK, never the caller's (R36): the live box runs
        # a day behind the agent writing the test, and a job that compares a
        # laptop's date to a server's finds nothing and looks broken.
        cutoff = fields.Datetime.now() - timedelta(days=days)
        Jd = self.env['pb.hiring.jd'].sudo()
        rows = Jd.search([('state', '=', 'submitted'),
                          ('write_date', '<=', cutoff)])
        made = 0
        Activity = self.env['mail.activity'].sudo()
        for jd in rows:
            summary = _('Agree the advert: %s', jd.title or jd.name or '')
            try:
                uids = jd._jd_approver_uids()
                if not uids:
                    _logger.info('pb_hiring: advert %s has nobody to chase',
                                 jd.name)
                    continue
                existing = Activity.search_count([
                    ('res_model', '=', 'pb.hiring.jd'),
                    ('res_id', '=', jd.id), ('summary', '=', summary)])
                if existing:
                    continue
                jd.activity_schedule(
                    act_type_xmlid=_TODO, summary=summary,
                    note=_("This advert has been waiting %(n)s %(word)s to be "
                           "agreed. Until it is, the role cannot be "
                           "advertised.", n=days,
                           word=counted(days, _('day'), _('days'))),
                    user_id=uids[0],
                    date_deadline=fields.Date.context_today(self))
                made += 1
            except Exception:           # noqa: BLE001 — per record
                _logger.warning('pb_hiring: could not chase advert %s', jd.id,
                                exc_info=True)
        return made

    # =====================================================================
    #  An open role with nobody on it
    # =====================================================================
    @api.model
    def _nudge_open_roles(self):
        days = max(1, number(self.env, P_RECRUITER_NUDGE_DAYS, 3))
        cutoff = fields.Date.context_today(self) - timedelta(days=days)
        Requisition = self.env['pb.hiring.requisition'].sudo()
        rows = Requisition.search([('state', '=', 'open'),
                                   ('recruiter_id', '=', False),
                                   ('opened_on', '<=', cutoff)])
        if not rows:
            return 0
        admins = self._admin_uids()
        if not admins:
            _logger.warning('pb_hiring: %s open %s nobody recruiting them and '
                            'this database has no hiring administrator to '
                            'tell', len(rows),
                            counted(len(rows), _('role has'),
                                    _('roles have')))
            return 0
        made = 0
        Activity = self.env['mail.activity'].sudo()
        for req in rows:
            summary = _('Name a recruiter: %s', req.title or req.name or '')
            try:
                existing = Activity.search_count([
                    ('res_model', '=', 'pb.hiring.requisition'),
                    ('res_id', '=', req.id), ('summary', '=', summary)])
                if existing:
                    continue
                req.activity_schedule(
                    act_type_xmlid=_TODO, summary=summary,
                    note=_("This role was agreed on %(when)s and nobody is "
                           "recruiting for it. Add a hiring rule for "
                           "%(where)s, or name a recruiter on the request.",
                           when=req.opened_on or '',
                           where=req.country_id.name or req.company_id.name),
                    user_id=admins[0],
                    date_deadline=fields.Date.context_today(self))
                made += 1
            except Exception:           # noqa: BLE001 — per record
                _logger.warning('pb_hiring: could not chase open role %s',
                                req.id, exc_info=True)
        return made

    # =====================================================================
    #  A2 — the hour that is coming, every ten minutes
    # =====================================================================
    @api.model
    def _cron_reminders(self):
        counts = self.run_reminders()
        _logger.info('pb_hiring: %s', self.describe_reminders(counts))
        return counts

    @api.model
    def run_reminders(self):
        """The day-before and half-hour nudges, in one pass.

        A SEPARATE JOB FROM THE NIGHT, because it is a different question. The
        nightly one asks "what has gone stale"; this one asks "who has
        something in half an hour", and the answer is only useful if it is
        asked every ten minutes. Running it by hand is harmless: both nudges
        are stamped on the interview, so a second pass in the same window
        sends nothing.
        """
        counts = {'day_before': 0, 'half_hour': 0}
        if not flag(self.env, P_REMINDERS):
            _logger.info('pb_hiring: interview reminders are switched off, so '
                         'nobody was told about an hour that is coming')
            return counts
        for key, fn in (('day_before', self._remind_day_before),
                        ('half_hour', self._remind_half_hour)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — a job never raises
                _logger.warning('pb_hiring: the %s reminder failed', key,
                                exc_info=True)
        return counts

    @api.model
    def describe_reminders(self, counts):
        day = counts.get('day_before', 0)
        half = counts.get('half_hour', 0)
        parts = []
        if day:
            parts.append(_("%(n)s %(word)s tomorrow.", n=day,
                           word=counted(day, _('interview is'),
                                        _('interviews are'))))
        if half:
            parts.append(_("%(n)s %(word)s within the half hour.", n=half,
                           word=counted(half, _('interview is'),
                                        _('interviews are'))))
        if not parts:
            return _("No interview needed a reminder just now.")
        return ' '.join(parts)

    @api.model
    def _due_interviews(self, low, high, stamp_field):
        """The interviews inside a WINDOW, not past a threshold.

        A threshold ("start is less than a day away") would fire on every
        interview in the next twenty-four hours, every ten minutes, for ever
        — it is only the stamp that would stop it, and a stamp is a repair
        rather than a design. A window is the honest question, and the stamp
        is then belt as well as braces.

        THE SERVER'S OWN CLOCK (R36): the live box runs a day behind the
        laptop these tests are written on.
        """
        now = fields.Datetime.now()
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        return self.env['pb.hiring.interview'].sudo().search([
            ('state', '=', 'scheduled'),
            ('start', '>=', now + low),
            ('start', '<=', now + high),
            (stamp_field, '=', False),
        ], order='start', limit=cap)

    @api.model
    def _remind_day_before(self):
        rows = self._due_interviews(timedelta(hours=23, minutes=50),
                                    timedelta(hours=24, minutes=10),
                                    'reminder_24h_sent')
        return self._remind_each(rows, '24h')

    @api.model
    def _remind_half_hour(self):
        rows = self._due_interviews(timedelta(minutes=25),
                                    timedelta(minutes=35),
                                    'reminder_30m_sent')
        return self._remind_each(rows, '30m')

    @api.model
    def _remind_each(self, rows, which):
        made = 0
        for interview in rows:
            # PER RECORD, IN ITS OWN SAVEPOINT. One interview whose candidate
            # address is malformed must not cost the other forty their
            # reminder, and a failure that reached the database would take
            # the whole run with it (R131).
            if leg(self.env, 'the %s reminder on interview %s'
                   % (which, interview.id),
                   lambda i=interview: i._remind(which)) is not False:
                made += 1
        return made

    # =====================================================================
    #  A2 — the opinions that are late, once a day
    # =====================================================================
    @api.model
    def _chase_late_feedback(self):
        """ONE urgent mail per late opinion, ever.

        Idempotent by `urgent_sent_at` rather than by a search for an open
        to-do, because the to-do is raised on the INTERVIEW and three late
        opinions on one interview are three different people to chase. R49's
        lesson from the other side: only an identifier a row actually HAS may
        be the key.
        """
        grace = max(0, number(self.env, P_URGENT_AFTER_HOURS, 0))
        cutoff = fields.Datetime.now() - timedelta(hours=grace)
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        rows = self.env['pb.hiring.feedback'].sudo().search([
            ('state', '=', 'pending'),
            ('urgent_sent_at', '=', False),
            ('due_at', '!=', False),
            ('due_at', '<=', cutoff),
            ('interview_id.state', 'in', ('scheduled', 'done')),
        ], order='due_at', limit=cap)
        made = 0
        for row in rows:
            if leg(self.env, 'the chase on opinion %s' % row.id,
                   row._chase) is not False:
                made += 1
        return made

    # =====================================================================
    #  A3 — the papers a candidate has not sent
    # =====================================================================
    @api.model
    def _chase_documents(self):
        """ONE reminder a day per candidate, and never two.

        Idempotent by a DATE and not by a counter: a stamp that says "we
        reminded them today" survives a job that runs twice in a morning, a
        recruiter pressing the button by hand and a server that was restarted
        — and it forgets itself overnight, which is exactly the behaviour a
        daily nudge needs.
        """
        every = max(1, number(self.env, P_DOC_REMINDER_DAYS, 1))
        today = fields.Date.context_today(self)
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        rows = self.env['pb.hiring.docreq'].sudo().search([
            ('state', 'in', ('sent', 'partial', 'expired')),
            ('sent_on', '!=', False),
            ('offer_id.state', 'not in', ('closed', 'declined', 'refused')),
            '|', ('last_reminder_on', '=', False),
            ('last_reminder_on', '<=', today - timedelta(days=every)),
        ], order='deadline', limit=cap)
        made = 0
        for row in rows:
            if leg(self.env, 'the document reminder on request %s' % row.id,
                   row.action_remind) is not False:
                made += 1
        return made

    @api.model
    def _document_deadlines(self):
        """The recruiter gets a to-do on the day the window shuts, once.

        A CANDIDATE WHO HAS GONE QUIET IS A PERSON TO RING, not a row to
        expire. Nothing is closed here and the link stays live — this only
        makes sure somebody knows.
        """
        today = fields.Date.context_today(self)
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        rows = self.env['pb.hiring.docreq'].sudo().search([
            ('deadline', '!=', False), ('deadline', '<', today),
            ('deadline_todo_on', '=', False),
            ('state', '!=', 'complete'),
            ('offer_id.state', 'not in', ('closed', 'declined', 'refused')),
        ], order='deadline', limit=cap)
        made = 0
        for row in rows:
            if leg(self.env, 'the document deadline on request %s' % row.id,
                   row._raise_deadline_todo) is not False:
                made += 1
        return made

    # =====================================================================
    #  A3 — the covers that start and finish today
    # =====================================================================
    @api.model
    def _move_covers(self):
        return self.env['pb.hiring.cover'].run_window()

    @api.model
    def _admin_uids(self):
        """`all_user_ids` and never `group_ids` (R7): direct membership misses
        everybody who holds the tier through an implied group, which is most
        administrators."""
        group = self.env.ref('pb_hiring.group_hiring_admin',
                             raise_if_not_found=False)
        if not group:
            return []
        users = group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share)
        return users.sorted('id').ids
