# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Time off tells the employee their request was sent back (WORKFLOW-2 P5a,
owner decision D28, 11 Nov).

WHAT WAS TRUE BEFORE. A time-off request sent back by an approver became a
refusal with a note "Sent back: …" (hr_holidays has no "back to draft" while
a request is under approval). The employee heard the standard "has been
refused" message from time off and, from the approval engine, "Sent back to
you" — which never reaches an employee-home login.

WHAT IS TRUE NOW. Time off owns the one "sent back" message to the person it
is about: an email with the reason and a button to their requests, sent once
(only when the send-back really turned the request round). The engine then
leaves its own "Sent back to you" out for the person who sent it in (the same
ownership rule as approved / refused, P2b D6). No address on the employee →
the engine keeps its copy; switch `biz_approval.single_notice` at 0 → the
engine's copy is back (this email still goes, it is the area's own).
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

RETURNED_TEMPLATE = 'pb_timeoff.mail_template_leave_returned'


class HrLeaveMessages(models.Model):
    _inherit = 'hr.leave'

    #: approved / refused: hr_holidays' own messages (P2b). Sent back: the
    #: email below (P5a, D28).
    _approval_requester_notice = ('approved', 'rejected', 'returned')

    def _approval_area_tells_requester(self, request, result):
        self.ensure_one()
        if result == 'returned':
            return bool(self._pb_employee_address())
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        turning = self.state not in ('refuse', 'cancel')
        res = super()._approval_return(request, reason)
        if turning and self.state == 'refuse':
            self._pb_tell_sent_back(reason)
        return res

    # ------------------------------------------------------------ the email
    def _pb_employee_address(self):
        self.ensure_one()
        employee = self.sudo().employee_id
        return (employee.work_email or employee.user_id.email
                or employee.work_contact_id.email or '').strip()

    def _pb_sent_back_note(self):
        """The reason the approver gave, as written on the request."""
        self.ensure_one()
        request = self.env['biz.approval.request'].sudo().search([
            ('res_model', '=', 'hr.leave'), ('res_id', '=', self.id),
            ('state', '=', 'returned')], order='attempt desc, id desc',
            limit=1)
        return (request.return_note or '').strip()

    def _pb_sent_back_url(self):
        """Their own requests page for an employee-home login; the request
        itself (the standard redirect) for a staff login."""
        self.ensure_one()
        user = self.sudo().employee_id.user_id
        base = self.get_base_url()
        if user and user.share:
            return '%s/my/requests' % base
        return '%s/mail/view?model=hr.leave&res_id=%s' % (base, self.id)

    def _pb_mail_lang(self):
        self.ensure_one()
        employee = self.sudo().employee_id
        return (employee.user_id.lang or employee.work_contact_id.lang
                or self.sudo().company_id.partner_id.lang or 'en_US')

    def _pb_tell_sent_back(self, reason=''):
        """Queue the one email. Never raises: a decision never fails over
        mail."""
        self.ensure_one()
        leave = self.sudo()
        address = leave._pb_employee_address()
        if not address:
            _logger.info('pb_timeoff: time off %s has no address to say it '
                         'was sent back', leave.id)
            return False
        try:
            with self.env.cr.savepoint():
                template = self.env.ref(RETURNED_TEMPLATE,
                                        raise_if_not_found=False)
                if not template:
                    _logger.warning('pb_timeoff: %s is missing',
                                    RETURNED_TEMPLATE)
                    return False
                values = {'email_to': address, 'auto_delete': False}
                company = leave.company_id or self.env.company
                if company.email:
                    values['email_from'] = company.email_formatted
                template.sudo().send_mail(leave.id, force_send=False,
                                          email_values=values)
            return True
        except Exception:   # noqa: BLE001
            _logger.exception('pb_timeoff: could not say time off %s was '
                              'sent back', leave.id)
            return False
