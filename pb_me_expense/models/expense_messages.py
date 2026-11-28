# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Telling the employee what happened to their claim (WORKFLOW-2 P2b, D6).

WHAT WAS TRUE BEFORE. Nobody told the employee when a claim was approved,
refused or paid. The approval engine never writes to an employee-home login,
and even a staff login only heard "Approved: …" from the engine, never "Paid".

WHAT IS TRUE NOW. Expenses owns the three messages to the person the claim is
for: approved, refused (with the reason) and paid (with the amount and the
date). Each is one email to the employee's work address, in their language,
with one button to the claim on their own pages. Each is sent once per
decision (a stamp per result on the claim); a claim fixed and sent again after
a refusal can be told about its new decision. The engine leaves out its own
"Approved" / "Turned down" copy for the person who sent it in
(`_approval_requester_notice`), so nobody hears it twice.

NEVER A BACKFILL. A message goes out only when a claim MOVES (approved,
refused, paid) after this code is loaded; claims decided before are left
alone.
"""

import logging

from markupsafe import Markup, escape

from odoo import api, fields, models
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

#: result -> (mail template xmlid, stamp field)
CLAIM_MESSAGES = {
    'approved': ('pb_me_expense.mail_template_claim_approved',
                 'pb_told_approved_at'),
    'refused': ('pb_me_expense.mail_template_claim_refused',
                'pb_told_refused_at'),
    'paid': ('pb_me_expense.mail_template_claim_paid', 'pb_told_paid_at'),
    # WF2 P5a (D28): sent back, with the reason. Once per send-back; sending
    # the claim in again clears it so a later send-back is told too.
    'returned': ('pb_me_expense.mail_template_claim_returned',
                 'pb_told_returned_at'),
}

BRAND = '#5A4BB0'


class PbExpenseClaimMessages(models.Model):
    _inherit = 'pb.expense.claim'

    #: The engine leaves its own "Approved" / "Turned down" / "Sent back" out
    #: for the person who sent the claim in: these emails tell them (sent back
    #: since WF2 P5a, owner decision D28).
    _approval_requester_notice = ('approved', 'rejected', 'returned')

    pb_told_approved_at = fields.Datetime(
        string='Employee told it was approved', readonly=True, copy=False)
    pb_told_refused_at = fields.Datetime(
        string='Employee told it was refused', readonly=True, copy=False)
    pb_told_paid_at = fields.Datetime(
        string='Employee told it was paid', readonly=True, copy=False)
    pb_told_returned_at = fields.Datetime(
        string='Employee told it was sent back', readonly=True, copy=False)

    # ------------------------------------------------------------ the hooks
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state in ('approved', 'refused'):
            for claim in self:
                claim._pb_tell_employee(to_state)
        elif to_state == 'submitted':
            # sent in again: a later send-back is a new one to tell (D28)
            stamped = self.sudo().filtered('pb_told_returned_at')
            if stamped:
                stamped.write({'pb_told_returned_at': False})
        return res

    def _approval_return(self, request, reason):
        """Sent back by an approver (D28): after the claim is a draft again
        with the reason on it, the employee gets one email saying so."""
        res = super()._approval_return(request, reason)
        for claim in self:
            claim._pb_tell_employee('returned')
        return res

    def _sync_paid(self):
        before = self.sudo().filtered(lambda c: c.state == 'approved')
        res = super()._sync_paid()
        for claim in before.filtered(lambda c: c.state == 'paid'):
            claim._pb_tell_employee('paid')
        return res

    def _pb_back_to_draft(self, reason=None):
        """A claim that is a draft again can be decided again: a NEW decision
        may be told (the stamps belong to the decision, not to the claim)."""
        res = super()._pb_back_to_draft(reason=reason)
        stamped = self.sudo().filtered(
            lambda c: c.pb_told_approved_at or c.pb_told_refused_at)
        if stamped:
            stamped.write({'pb_told_approved_at': False,
                           'pb_told_refused_at': False})
        return res

    def _approval_area_tells_requester(self, request, result):
        """The engine leaves its copy out only when this claim really has
        somewhere to send ours."""
        self.ensure_one()
        return bool(self._pb_employee_address())

    # ------------------------------------------------------------- the send
    def _pb_employee_address(self):
        self.ensure_one()
        employee = self.sudo().employee_id
        return (employee.work_email or employee.user_id.email
                or employee.work_contact_id.email or '').strip()

    def _pb_tell_employee(self, result):
        """Queue the one email for `result`, once. Never raises."""
        self.ensure_one()
        template_xmlid, stamp = CLAIM_MESSAGES[result]
        claim = self.sudo()
        if claim[stamp]:
            return False
        address = claim._pb_employee_address()
        if not address:
            _logger.info('pb_me_expense: claim %s has no address to tell '
                         'the employee it was %s', claim.id, result)
            return False
        try:
            with self.env.cr.savepoint():
                template = self.env.ref(template_xmlid,
                                        raise_if_not_found=False)
                if not template:
                    _logger.warning('pb_me_expense: %s is missing',
                                    template_xmlid)
                    return False
                values = {'email_to': address, 'auto_delete': False}
                sender = claim._pb_mail_sender()
                if sender:
                    values['email_from'] = sender
                template.sudo().send_mail(claim.id, force_send=False,
                                          email_values=values)
                claim.write({stamp: fields.Datetime.now()})
            return True
        except Exception:   # noqa: BLE001 — a decision never fails over mail
            _logger.exception('pb_me_expense: could not tell the employee '
                              'claim %s was %s', claim.id, result)
            return False

    # ------------------------------------------------- what the email says
    def _pb_mail_sender(self):
        """The company's address, else the system's own — never the person
        who happened to press Approve."""
        self.ensure_one()
        company = self.sudo().company_id
        if company.email:
            return company.email_formatted
        try:
            return self.env['ir.mail_server']._get_default_from_address() or ''
        except Exception:   # noqa: BLE001
            return ''

    def _pb_mail_lang(self):
        self.ensure_one()
        employee = self.sudo().employee_id
        return (employee.user_id.lang or employee.work_contact_id.lang
                or self.sudo().company_id.partner_id.lang or 'en_US')

    def _pb_mail_url(self):
        self.ensure_one()
        return '%s/my/expenses/%s' % (self.get_base_url(), self.id)

    def _pb_mail_subject(self, result):
        _ = self.env._
        return {
            'approved': _('Your expense claim was approved'),
            'refused': _('Your expense claim was refused'),
            'paid': _('Your expense claim was paid'),
            'returned': _('Your expense claim was sent back'),
        }.get(result, '')

    def _pb_mail_body(self, result):
        """The email, in the language of the environment it is rendered in
        (the template renders in the employee's language)."""
        self.ensure_one()
        _ = self.env._
        claim = self.sudo()
        env = self.env
        total = formatLang(env, claim.total or 0.0,
                           currency_obj=claim.currency_id)
        first = claim.employee_id.name or ''
        receipts = claim.receipt_count or len(claim.expense_ids)
        what = _('1 receipt') if receipts == 1 else \
            _('%s receipts', receipts)
        if result == 'approved':
            title = _('Your claim was approved')
            lines = [
                _('Your expense claim %(ref)s for %(total)s (%(what)s) was '
                  'approved.', ref=claim.name, total=total, what=what),
                _('Finance pays it next. We will email you again when it '
                  'has been paid.'),
            ]
            reason = ''
        elif result == 'refused':
            title = _('Your claim was refused')
            lines = [
                _('Your expense claim %(ref)s for %(total)s (%(what)s) was '
                  'refused.', ref=claim.name, total=total, what=what),
                _('You can fix it and send it again from your claim.'),
            ]
            reason = claim.refusal_reason or _('No reason was given.')
        elif result == 'returned':
            title = _('Your claim was sent back')
            lines = [
                _('Your expense claim %(ref)s for %(total)s (%(what)s) was '
                  'sent back to you.', ref=claim.name, total=total,
                  what=what),
                _('Change what is asked below, then send it again from your '
                  'claim.'),
            ]
            reason = claim.refusal_reason or _('No reason was given.')
        else:
            title = _('Your claim was paid')
            day = format_date(env, claim.paid_on) if claim.paid_on \
                else format_date(env, fields.Date.context_today(claim))
            lines = [
                _('Your expense claim %(ref)s was paid: %(total)s on '
                  '%(day)s.', ref=claim.name, total=total, day=day),
            ]
            reason = ''
        hello = _('Hello %s,', first) if first else _('Hello,')
        parts = [
            Markup('<div style="margin:0;padding:24px 0;font-family:'
                   '-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;'
                   'color:#1f2430;font-size:15px;line-height:1.55;">'),
            Markup('<div style="max-width:520px;margin:0 auto;">'),
            Markup('<p style="margin:0 0 6px;font-size:13px;color:#6b6f80;">'
                   '%s</p>') % escape(claim.name or ''),
            Markup('<h2 style="margin:0 0 16px;font-size:20px;'
                   'font-weight:600;color:#1f2430;">%s</h2>') % escape(title),
            Markup('<p style="margin:0 0 12px;">%s</p>') % escape(hello),
        ]
        for line in lines:
            parts.append(Markup('<p style="margin:0 0 12px;">%s</p>')
                         % escape(line))
        if reason:
            parts.append(Markup(
                '<div style="margin:4px 0 16px;padding:12px 14px;'
                'border-left:3px solid %s;background:#f4f2fb;'
                'border-radius:6px;"><div style="font-size:12px;'
                'color:#6b6f80;margin-bottom:2px;">%s</div>'
                '<div>%s</div></div>') % (
                    BRAND, escape(_('The reason given')), escape(reason)))
        parts.append(Markup(
            '<p style="margin:20px 0 8px;"><a href="%s" style="display:'
            'inline-block;background:%s;color:#ffffff;text-decoration:none;'
            'padding:10px 18px;border-radius:8px;font-weight:600;">%s</a>'
            '</p>') % (escape(self._pb_mail_url()), BRAND,
                       escape(_('Open your claim'))))
        parts.append(Markup('</div></div>'))
        return Markup('').join(parts)

    @api.model
    def _workflow_capabilities(self):
        """Studio's "already happens": the three messages Expenses now sends
        to the employee (so a repeat email step is warned about)."""
        caps = super()._workflow_capabilities()
        _ = self.env._
        area = caps.get('area') or _('Expenses')
        settings = {'action': 'pb_expenses_hub.action_pb_expenses_hub'}
        caps.setdefault('effects', [])
        caps['effects'] += [
            {'stage': 'approved', 'kind': 'message', 'audience': 'requester',
             'owner': area, 'settings': settings,
             'text': _('The employee gets an email that their claim was '
                       'approved, with a link to it.')},
            {'stage': 'refused', 'kind': 'message', 'audience': 'requester',
             'owner': area, 'settings': settings,
             'text': _('The employee gets an email that their claim was '
                       'refused, with the reason and a link to fix it.')},
            {'stage': 'paid', 'kind': 'message', 'audience': 'requester',
             'owner': area, 'settings': settings,
             'text': _('The employee gets an email that their claim was '
                       'paid, with the amount and the date.')},
            {'stage': 'draft', 'kind': 'message', 'audience': 'requester',
             'owner': area, 'settings': settings,
             'text': _('When a claim is sent back, the employee gets an '
                       'email with the reason and a link to fix it.')},
        ]
        return caps
