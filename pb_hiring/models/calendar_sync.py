"""Keep externally moved calendar entries and interview audit trails aligned."""
from odoo import _, models


class HiringCalendarInbound(models.Model):
    _inherit = 'calendar.event'

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get('pb_hiring_quiet_google') or self.env.context.get('pb_hiring_calendar_inbound'):
            return result
        if not set(vals) & {'start', 'stop', 'active', 'videocall_location', 'location'}:
            return result
        for event in self:
            interview = event._pb_interview()
            if not interview or interview.state != 'scheduled':
                continue
            interview = interview.with_context(pb_hiring_calendar_inbound=True)
            if not event.active:
                interview.action_cancel(_('Cancelled in the connected calendar.'))
            elif event.start != interview.start or event.stop != interview.stop:
                fresh = interview.reschedule({'start': event.start,
                    'duration_minutes': max(5, int((event.stop - event.start).total_seconds() / 60)),
                    'location': event.location or interview.location,
                    'reason': _('Time changed in the calendar. Review the recorded reason and whose side requested the change.'),
                    'delay_kind': 'internal'})
                # A provider cannot identify who requested the change reliably;
                # explicitly ask the organiser to review the audit classification.
                if fresh.recruiter_id:
                    fresh.activity_schedule('mail.mail_activity_data_todo',
                        user_id=fresh.recruiter_id.id, summary=_('Review calendar reschedule reason'))
            elif event.videocall_location and event.videocall_location != interview.videocall_url:
                interview.write({'videocall_url': event.videocall_location})
        return result

    def unlink(self):
        if not self.env.context.get('pb_hiring_calendar_inbound'):
            for event in self:
                interview = event._pb_interview()
                if interview and interview.state == 'scheduled':
                    interview.with_context(pb_hiring_calendar_inbound=True).action_cancel(
                        _('Interview entry removed from the calendar.'))
        return super().unlink()
