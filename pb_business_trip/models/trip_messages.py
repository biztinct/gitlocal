# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Business trips tell the employee their request was sent back (WORKFLOW-2
P6a, owner decision D28 — the trips half of it).

WHAT WAS TRUE BEFORE. A trip request sent back by an approver went back to
draft with a note on the trip. The only message was the approval engine's own
"Sent back to you", which never reaches an employee-home login.

WHAT IS TRUE NOW. Trips own the one "sent back" message to the person the trip
is for: an email with the reason and a button to their trip, in their own
language, sent once (only when the send-back really turned the trip round).
The engine then leaves its own "Sent back to you" out for the person who sent
it in (the ownership rule of P2b D6, `_approval_requester_notice`). Trips send
no approved / turned-down email of their own, so those stay the engine's. No
address on the employee → the engine keeps its copy; switch
`biz_approval.single_notice` at 0 → the engine's copy is back (this email
still goes, it is the area's own). Same shape as time off
(`pb_timeoff/models/leave_messages.py`).
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

RETURNED_TEMPLATE = 'pb_business_trip.mail_template_trip_returned'


class PbBusinessTripMessages(models.Model):
    _inherit = 'pb.business.trip'

    #: Only "sent back" is the area's own message; approved and turned down
    #: stay the approval engine's (trips have no email for them).
    _approval_requester_notice = ('returned',)

    def _approval_area_tells_requester(self, request, result):
        self.ensure_one()
        if result == 'returned':
            return bool(self._pb_employee_address())
        return False

    def _approval_return(self, request, reason):
        self.ensure_one()
        turning = self.state not in ('draft', 'refused', 'cancelled')
        res = super()._approval_return(request, reason)
        if turning and self.state == 'draft':
            self._pb_tell_sent_back()
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
            ('res_model', '=', self._name), ('res_id', '=', self.id),
            ('state', '=', 'returned')], order='attempt desc, id desc',
            limit=1)
        return (request.return_note or '').strip()

    def _pb_sent_back_url(self):
        """The trip on the employee home for an employee-home login (when
        that page is installed); the trip itself for a staff login."""
        self.ensure_one()
        user = self.sudo().employee_id.user_id
        base = self.get_base_url()
        if user and user.share:
            pages = self.env['ir.module.module'].sudo().search_count([
                ('name', '=', 'pb_me_trip'), ('state', '=', 'installed')])
            return '%s/my/trips/%s' % (base, self.id) if pages else '%s/my' % base
        return '%s/mail/view?model=%s&res_id=%s' % (base, self._name, self.id)

    def _pb_mail_lang(self):
        self.ensure_one()
        employee = self.sudo().employee_id
        return (employee.user_id.lang or employee.work_contact_id.lang
                or self.sudo().company_id.partner_id.lang or 'en_US')

    def _pb_tell_sent_back(self):
        """Queue the one email. Never raises: a decision never fails over
        mail."""
        self.ensure_one()
        trip = self.sudo()
        address = trip._pb_employee_address()
        if not address:
            _logger.info('pb_business_trip: trip %s has no address to say '
                         'it was sent back', trip.id)
            return False
        try:
            with self.env.cr.savepoint():
                template = self.env.ref(RETURNED_TEMPLATE,
                                        raise_if_not_found=False)
                if not template:
                    _logger.warning('pb_business_trip: %s is missing',
                                    RETURNED_TEMPLATE)
                    return False
                values = {'email_to': address, 'auto_delete': False}
                company = trip.company_id or self.env.company
                if company.email:
                    values['email_from'] = company.email_formatted
                template.sudo().send_mail(trip.id, force_send=False,
                                          email_values=values)
            return True
        except Exception:   # noqa: BLE001
            _logger.exception('pb_business_trip: could not say trip %s was '
                              'sent back', trip.id)
            return False
