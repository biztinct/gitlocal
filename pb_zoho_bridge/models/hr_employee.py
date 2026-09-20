# -*- coding: utf-8 -*-
"""What the bridge remembers on the employee, and the credentials email.

Three small columns and one method. The columns exist because matching and
change-detection both need somewhere honest to stand:

  * `pb_zoho_id` — the connected system's OWN record id. This is the only
    identifier that survives a person changing their name, their email and
    their employee number in the same week, so it is tried first every time.
    `employee_id` (the employee NUMBER, which om_hr_payroll already added and
    the legacy Zoho staging already fills) is tried second and is deliberately
    reused rather than duplicated.
  * `pb_zoho_status` — the last employment status word we were told. Without it
    every push would look like a status change, and every push would open a
    journey.
  * `pb_portal_user_id` — the account made for them on arrival. It is NOT
    `user_id`: that field is for internal users, and a joiner who has not
    started gets a portal account and nothing more.

`send_credentials()` is separate from creating the account ON PURPOSE (ruling
D6). The account is ready three weeks early; the email arrives on day one,
sent by that step of their joining checklist.
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_zoho_id = fields.Char(
        string='Connected system id', index=True, copy=False,
        help='How the connected system refers to this person. Filled in '
             'automatically when their record arrives.')
    pb_zoho_status = fields.Char(
        string='Status in the connected system', copy=False, readonly=True,
        help='The last employment status word we were sent. Payobook compares '
             'against it to notice a real change.')
    pb_portal_user_id = fields.Many2one(
        'res.users', string='Their Payobook account', copy=False,
        ondelete='set null',
        help='The account created for this person so they can sign in. '
             'Creating it does not tell them about it — that is a step on '
             'their joining checklist.')
    pb_portal_signup_url = fields.Char(
        string='Sign-in link', compute='_compute_pb_portal_signup_url',
        help='The one-time link that lets them choose their own password.')

    def _compute_pb_portal_signup_url(self):
        """The invitation link, computed rather than stored.

        Stored it would be a live credential sitting in a column that every
        export and every list view can reach. Computed, it is minted at the
        moment somebody with the right to send it asks for it, and nowhere else.
        Each probe gets its own try/except: one employee whose partner cannot
        mint a token must not blank the field for the other forty-nine.
        """
        for rec in self:
            url = False
            try:
                user = rec.pb_portal_user_id
                partner = user.sudo().partner_id if user else False
                if partner and hasattr(partner, '_get_signup_url_for_action'):
                    partner.sudo().signup_prepare(signup_type='signup')
                    url = partner.sudo()._get_signup_url_for_action().get(
                        partner.id, False)
            except Exception:            # noqa: BLE001 - one probe, one failure
                _logger.exception(
                    'pb_zoho_bridge: could not build a sign-in link for %s',
                    rec.id)
                url = False
            rec.pb_portal_signup_url = url

    # ------------------------------------------------------------- the email
    def send_credentials(self):
        """Tell these people their account is ready. Returns an honest count.

        Deliberately NOT `action_reset_password()` from the standard invite
        flow, for two reasons that both matter here. That method force-sends
        inside the request and deletes the message afterwards, so a joining-day
        batch either blocks on the mail server or vanishes without a trace; and
        its wording is the platform's, not ours. This queues our own template
        instead, which the outgoing debrand then handles like any other mail.

        The recipient is passed EXPLICITLY in `email_values`. A template's own
        rendered `email_to` can reach `mail.mail` empty, and the message is then
        created, queued and addressed to nobody with no error anywhere (R6).
        """
        template = self.env.ref(
            'pb_zoho_bridge.mail_template_portal_credentials',
            raise_if_not_found=False)
        if not template:
            raise UserError(_(
                'The welcome email template is missing. Ask your administrator '
                'to reinstall the connected-system bridge.'))
        sent, skipped = 0, []
        for emp in self:
            user = emp.pb_portal_user_id
            to = (user.email if user else False) or emp.work_email
            if not user or not to:
                skipped.append(emp.name or str(emp.id))
                continue
            try:
                template.sudo().send_mail(
                    emp.id, force_send=False,
                    email_values={'email_to': to, 'auto_delete': False})
                sent += 1
            except Exception as err:     # noqa: BLE001 - per record, always
                _logger.exception(
                    'pb_zoho_bridge: credentials mail failed for employee %s',
                    emp.id)
                skipped.append('%s (%s)' % (emp.name or emp.id, err))
        _logger.info('pb_zoho_bridge: credentials queued for %s employee(s), '
                     '%s skipped', sent, len(skipped))
        return {'sent': sent, 'skipped': skipped}

    def action_send_credentials(self):
        """The button. Says what happened, in words, and never silently."""
        res = self.send_credentials()
        if not res['sent']:
            raise UserError(_(
                'Nothing was sent. These people have no Payobook account or no '
                'work email yet: %s', ', '.join(res['skipped']) or _('none')))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Welcome email queued'),
                'message': _('%s person(s) will be told their account is ready.',
                             res['sent']),
                'sticky': False,
            },
        }

    @api.model
    def _pb_zoho_find(self, zoho_id=False, employee_number=False, email=False):
        """Identity lookup, most trustworthy key first. Never guesses."""
        Emp = self.sudo().with_context(active_test=False)
        for domain in ([('pb_zoho_id', '=', zoho_id)] if zoho_id else [],
                       [('employee_id', '=', employee_number)] if employee_number else [],
                       [('work_email', '=ilike', email)] if email else []):
            if not domain:
                continue
            found = Emp.search(domain, limit=2)
            if len(found) == 1:
                return found
            if len(found) > 1:
                return found          # the caller decides; ambiguity is not a match
        return Emp.browse()
