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
    P_JD_REMINDER_DAYS, P_RECRUITER_NUDGE_DAYS, counted, number,
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
        counts = {'jd': 0, 'recruiter': 0}
        for key, fn in (('jd', self._nudge_adverts),
                        ('recruiter', self._nudge_open_roles)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — a job never raises
                _logger.warning('pb_hiring: the %s nudge failed', key,
                                exc_info=True)
        return counts

    @api.model
    def describe(self, counts):
        """The sentence a person reads, with the real numbers in it."""
        jd, rec = counts.get('jd', 0), counts.get('recruiter', 0)
        # BRANCH THE WHOLE SENTENCE (R117): a frame with one word swapped in
        # produces "You does not have", and a translator handed the frame and
        # the word separately cannot fix a verb they were never given.
        if not jd and not rec:
            return _("Nothing needed chasing today.")
        if jd and not rec:
            return _("%(n)s %(word)s nudged.", n=jd,
                     word=counted(jd, _('job description was'),
                                  _('job descriptions were')))
        if rec and not jd:
            return _("%(n)s open %(word)s still nobody recruiting it.", n=rec,
                     word=counted(rec, _('role has'), _('roles have')))
        return _("%(jn)s %(jword)s nudged, and %(rn)s open %(rword)s still "
                 "nobody recruiting it.",
                 jn=jd, jword=counted(jd, _('job description was'),
                                      _('job descriptions were')),
                 rn=rec, rword=counted(rec, _('role has'), _('roles have')))

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
