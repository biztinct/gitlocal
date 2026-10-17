# -*- coding: utf-8 -*-
"""RECRUIT P5 — Google Calendar + Meet (RC-D3) and the recruiter's own
scheduling link (G-37).

THE GOOGLE INSERT ANSWER (verified on this build, 2026-10-01).
`GoogleCalendarService.insert()` RETURNS the created event resource — with
`conferenceDataVersion=1` that is `hangoutLink` and
`conferenceData.entryPoints[]` — but the standard sync throws all of it away
except the id (`google.calendar.sync._get_post_sync_values` writes `google_id`
and `need_sync` only), and it runs AFTER COMMIT (`_google_insert` is wrapped by
`after_commit`), so nothing inside the scheduling transaction can read it.
This file hooks `_get_post_sync_values`: when the entry belongs to an
interview, the Meet link is read from that same answer, written on the entry
(`videocall_location`) and the interview (`videocall_url`), and the
invitations that were waiting for it go out with it. No second sync call.

QUIET BY DESIGN. Google must never write to a candidate in its own words:
inserts carry `send_updates=False`; a PATCH (`_google_patch`) ignores that
context and asks `not _is_event_over()` instead, so an interview entry
answers "over" while the `pb_hiring_quiet_google` context is set.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .hiring_common import leg

_logger = logging.getLogger(__name__)


def meet_url(google_values):
    """The video link in a Google event resource, or ''."""
    if not isinstance(google_values, dict):
        return ''
    conf = google_values.get('conferenceData') or {}
    for entry in conf.get('entryPoints') or []:
        if entry.get('entryPointType') == 'video' and entry.get('uri'):
            return entry['uri']
    return google_values.get('hangoutLink') or ''


#: The context every diary entry this module makes is created and moved
#: under: no stock invitation, no alarm mail, no chatter noise, and Google
#: (when the organiser is connected) told to email nobody (RC63).
QUIET = dict(dont_notify=True, no_mail_to_attendees=True,
             mail_create_nolog=True, mail_notrack=True,
             send_updates=False, pb_hiring_quiet_google=True)


class CalendarEventHiring(models.Model):
    _inherit = 'calendar.event'

    # RECRUIT P6: a meet-the-team chat is a diary entry too.
    pb_prejoin_id = fields.Many2one('pb.hiring.prejoin', string='Before they join',
                                    index='btree_not_null', ondelete='set null',
                                    copy=False)

    @api.model
    def _pb_quiet_create(self, vals):
        """THE ONE HELPER every hiring diary entry is made through (RECRUIT
        P6 extracted it from the interview path for the meet-the-team chats).

        One `calendar.event`, and NOT ONE BRANDED INVITATION: our own mails
        with our own `.ics` say it. When the organiser (`user_id`) has
        connected Google, the entry goes to their Google calendar after the
        transaction commits; a video entry created WITHOUT a location is
        what makes Google attach a Meet, and the link comes back through
        `_get_post_sync_values` below.
        """
        return self.sudo().with_context(**QUIET).create(vals)

    def _pb_quiet_write(self, vals):
        """Move or call off an entry without anybody being emailed by the
        calendar or by Google (RC63: `_google_patch` reads `_is_event_over`)."""
        return self.sudo().with_context(**QUIET).write(vals)

    def _pb_interview(self):
        self.ensure_one()
        return self.env['pb.hiring.interview'].sudo().search(
            [('event_id', '=', self.id)], order='id desc', limit=1)

    def _is_event_over(self):
        # `_google_patch` reads this to decide whether Google emails the
        # attendees about a change. An interview entry moved or called off by
        # this module never does: our own mails say it.
        if self.env.context.get('pb_hiring_quiet_google'):
            return True
        return super()._is_event_over()

    def _need_video_call(self):
        """Only a VIDEO interview asks Google for a Meet; an in-person one
        on a connected calendar is a plain entry."""
        self.ensure_one()
        if self.pb_prejoin_id:
            return self.pb_prejoin_id.chat_mode == 'video'
        interview = self._pb_interview() if self.applicant_id else False
        if interview:
            return interview.mode == 'video'
        return super()._need_video_call()

    def _get_post_sync_values(self, request_values, google_values):
        vals = super()._get_post_sync_values(request_values, google_values)
        url = meet_url(google_values)
        if url and self.pb_prejoin_id:
            vals['videocall_location'] = url
            item = self.pb_prejoin_id
            leg(self.env, 'the Meet link on chat %s' % item.id,
                lambda: item._pb_meet_arrived(url))
            return vals
        if url and self.applicant_id:
            interview = self._pb_interview()
            if interview:
                vals['videocall_location'] = url
                leg(self.env, 'the Meet link on interview %s' % interview.id,
                    lambda: interview._pb_meet_arrived(url))
        return vals


class HiringInterviewMeet(models.Model):
    _inherit = 'pb.hiring.interview'

    def _pb_meet_arrived(self, url):
        """Google answered with a Meet link: it goes on the interview, and
        the invitations that waited for it go out with it in."""
        self.ensure_one()
        if not url:
            return False
        rec = self.sudo()
        if not rec.videocall_url:
            rec.write({'videocall_url': url})
        if rec.invites_pending and rec.state == 'scheduled':
            rec._pb_send_invites()
        elif rec.state == 'scheduled' and not rec.video_link_sent_at:
            # The invitations already went (Google took longer than ten
            # minutes): everybody gets one short "Your video link" mail.
            rec._pb_send_video_link()
        return True

    def _pb_send_video_link(self):
        self.ensure_one()
        if not self.videocall_url:
            return 0
        sent = 0
        recipients = []
        from .hiring_common import P_CANDIDATE_MAIL, flag
        if flag(self.env, P_CANDIDATE_MAIL) and self.candidate_email:
            recipients.append(self.candidate_email)
        recipients += [a for _emp, a in self._panel_contacts()]
        if self.recruiter_id and self.recruiter_id.email:
            recipients.append(self.recruiter_id.email)
        for address in dict.fromkeys(recipients):
            sent += 1 if self._send('pb_hiring.mail_template_interview_video_link',
                                    address, with_ics=True) else 0
        self.sudo().write({'video_link_sent_at': fields.Datetime.now()})
        return sent

    @api.model
    def _pb_send_overdue_invites(self, minutes=10):
        """Google never sent a Meet link (offline, refused, slow): after ten
        minutes the invitations go without it, saying a link will follow."""
        from datetime import timedelta
        cutoff = fields.Datetime.now() - timedelta(minutes=minutes)
        rows = self.sudo().search([('invites_pending', '=', True),
                                   ('state', '=', 'scheduled'),
                                   ('create_date', '<=', cutoff)], limit=200)
        made = 0
        for rec in rows:
            if leg(self.env, 'the waiting invitations on interview %s' % rec.id,
                   rec._pb_send_invites) is not False:
                made += 1
        return made


class ResUsersSchedulingLink(models.Model):
    _inherit = 'res.users'

    pb_scheduling_link = fields.Char(
        string='Scheduling link',
        help='Your own Calendly (or similar) link. Moving a candidate into '
             'Recruiter review sends it to them in the "Let\'s chat" email.')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['pb_scheduling_link']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['pb_scheduling_link']

    @api.constrains('pb_scheduling_link')
    def _check_pb_scheduling_link(self):
        for user in self:
            link = (user.pb_scheduling_link or '').strip()
            if link and not link.lower().startswith(('https://', 'http://')):
                raise ValidationError(_(
                    "A scheduling link starts with https:// — copy it from "
                    "your Calendly page."))
