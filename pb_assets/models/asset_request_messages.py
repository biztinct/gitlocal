# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Equipment requests tell the employee theirs was sent back (WORKFLOW-2
P6a, owner decision D28 — the equipment half of it).

WHAT WAS TRUE BEFORE. An equipment request sent back by an approver went back to
draft with a note on the request. The only message was the approval engine's own
"Sent back to you", which never reaches an employee-home login.

WHAT IS TRUE NOW. Equipment owns the one "sent back" message to the person the
request is for: an email with the reason and a button to their requests, in
their own language, sent once (only when the send-back really turned it round).
The engine then leaves its own "Sent back to you" out for the person who sent
it in (the ownership rule of P2b D6, `_approval_requester_notice`). Equipment sends
no approved / turned-down email of their own, so those stay the engine's. No
address on the employee → the engine keeps its copy; switch
`biz_approval.single_notice` at 0 → the engine's copy is back (this email
still goes, it is the area's own). Same shape as time off
(`pb_timeoff/models/leave_messages.py`).
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

RETURNED_TEMPLATE = 'pb_assets.mail_template_asset_request_returned'


class PbAssetRequestMessages(models.Model):
    _inherit = 'pb.asset.request'

    #: Only "sent back" is the area's own message; approved and turned down
    #: stay the approval engine’s (equipment has no email for them).
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
        """Their own requests page for an employee-home login (equipment
        requests are listed there); the request itself for a staff login."""
        self.ensure_one()
        user = self.sudo().employee_id.user_id
        base = self.get_base_url()
        if user and user.share:
            return '%s/my/requests' % base
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
        req = self.sudo()
        address = req._pb_employee_address()
        if not address:
            _logger.info('pb_assets: equipment request %s has no address to say '
                         'it was sent back', req.id)
            return False
        try:
            with self.env.cr.savepoint():
                template = self.env.ref(RETURNED_TEMPLATE,
                                        raise_if_not_found=False)
                if not template:
                    _logger.warning('pb_assets: %s is missing',
                                    RETURNED_TEMPLATE)
                    return False
                values = {'email_to': address, 'auto_delete': False}
                company = req.company_id or self.env.company
                if company.email:
                    values['email_from'] = company.email_formatted
                template.sudo().send_mail(req.id, force_send=False,
                                          email_values=values)
            return True
        except Exception:   # noqa: BLE001
            _logger.exception('pb_assets: could not say equipment request %s was '
                              'sent back', req.id)
            return False
