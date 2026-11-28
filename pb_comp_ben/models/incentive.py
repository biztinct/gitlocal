# -*- coding: utf-8 -*-
"""`pb.incentive` — a one-off amount somebody decided to pay, and its paper trail.

FOUR THINGS HAPPEN TO AN AWARD and they are deliberately kept apart:

  1. somebody **asks** for it (draft → waiting for approval);
  2. somebody **agrees** to it (`biz.approval.chain.mixin` — the generic ladder,
     not a fourth hand-rolled state machine);
  3. the person is **told** (P0's letter engine, the `incentive` template it
     already seeds);
  4. the money **moves** (the one-off pay-run lane, `pb.oneoff.feed`).

`state` answers (2) and `fulfilment` answers (3) and (4). One column trying to
say both is how a board ends up unable to show an approved award that has not
been paid — which is the single most useful row on the screen.

THE CHAIN GUARDS THE MONEY. `biz.approval.chain.mixin.write` refuses any write
to `state` that did not come through a transition, so a raw `call_kw` cannot
mark an award approved and let the feed pay it.
"""

import json
import logging

from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .comp_common import (
    FULFILMENT, GROUP_HEAD, GROUP_USER, INCENTIVE_KINDS, INCENTIVE_STATES,
    LETTER_TYPE, P_LETTER_SEND, flag,
)

_logger = logging.getLogger(__name__)


class PbIncentive(models.Model):
    _name = 'pb.incentive'
    _description = 'Award'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'period_month desc, id desc'

    #: Who may move it along. Asking is open to anybody who can create one
    #: (the ACL decides that); AGREEING is the head of the pay team, because an
    #: award is money leaving the company.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): GROUP_HEAD,
        ('submitted', 'refused'): GROUP_HEAD,
        ('draft', 'refused'): GROUP_USER,
    }

    name = fields.Char(compute='_compute_name', store=True, string='Reference')
    employee_id = fields.Many2one(
        'hr.employee', string='Who it is for', required=True, index=True,
        ondelete='cascade', tracking=True)
    kind = fields.Selection(INCENTIVE_KINDS, string='Kind', default='bonus',
                            required=True, tracking=True)
    amount = fields.Monetary(string='Amount', required=True,
                             currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    period_month = fields.Date(
        string='Pay it in', required=True, tracking=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
        help='The month this should be paid in. Any day of the month will do — '
             'it is the month that matters.')
    reason = fields.Text(string='Why', tracking=True)
    state = fields.Selection(INCENTIVE_STATES, default='draft', required=True,
                             tracking=True, string='Approval')
    fulfilment = fields.Selection(
        FULFILMENT, string='Where it has got to', copy=False, tracking=True)
    letter_id = fields.Many2one('pb.hr.letter', string='Award letter',
                                readonly=True, copy=False, ondelete='set null')
    feed_batch_ref = fields.Char(string='Pay data reference', readonly=True,
                                 copy=False)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run', readonly=True,
                             copy=False, ondelete='set null', index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    source = fields.Selection(
        [('manual', 'Entered by hand'), ('rnr', 'Recognition')],
        string='Where it came from', default='manual', required=True,
        readonly=True,
        help='Recognition awards are raised by the recognition programme and '
             'arrive here already filled in.')
    requested_by_user_id = fields.Many2one(
        'res.users', string='Asked by', readonly=True, index=True,
        default=lambda self: self.env.user)

    @api.depends('employee_id', 'kind', 'period_month')
    def _compute_name(self):
        for rec in self:
            who = rec._person().name or _('Award')
            month = rec.period_month.strftime('%b %Y') if rec.period_month else ''
            rec.name = ('%s — %s' % (who, month)).strip(' —')

    # ------------------------------------------------------------------ R56
    def _person(self):
        """The employee, read as the system. See `pb.employee.comp._person` —
        one field of an `hr.employee` prefetches forty, and forty of those sit
        behind payroll groups this module's holders need not have (R56)."""
        self.ensure_one()
        return self.employee_id.sudo()

    # ---------------------------------------------------------- the buttons
    def action_submit(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError(_("An award needs an amount above zero."))
            rec._advance_state('submitted')
        return True

    def action_approve(self):
        for rec in self:
            rec._advance_state('approved')
        return True

    def action_refuse(self, note=False):
        return self.action_refuse_chain(note=note)

    def _after_approval_transition(self, to_state):
        """Approval is the moment the paper starts moving."""
        res = super()._after_approval_transition(to_state)
        if to_state != 'approved':
            return res
        for rec in self:
            rec.fulfilment = 'pending'
            try:
                rec._make_letter()
            except Exception:               # noqa: BLE001
                # A letter that will not print must never undo an approval that
                # a person has made.
                _logger.exception(
                    'pb_comp_ben: award %s approved but its letter failed',
                    rec.id)
                rec.message_post(body=_(
                    "Approved. The award letter could not be prepared just now "
                    "— it can be prepared again from this record."))
        return res

    # ---------------------------------------------------------- the letter
    def _letter_template(self):
        return self.env['pb.letter.template'].sudo().search(
            [('letter_type', '=', LETTER_TYPE), ('active', '=', True)],
            order='sequence, id', limit=1)

    def action_make_letter(self):
        """Prepare (or re-prepare) the award letter by hand."""
        for rec in self:
            rec._make_letter()
        return True

    def _make_letter(self):
        """Prepare the letter, file it in the person's documents, maybe send it.

        THE SEND IS BEHIND A SWITCH and the switch ships OFF. The first hour
        after an install must not email people about awards a test created.
        """
        self.ensure_one()
        template = self._letter_template()
        if not template:
            self.message_post(body=_(
                "There is no award letter set up yet, so nothing was printed."))
            return False
        emp = self._person()
        letter = self.letter_id
        if not letter:
            letter = self.env['pb.hr.letter'].sudo().create({
                'employee_id': emp.id,
                'template_id': template.id,
                'context_json': json.dumps(self._letter_extras()),
                'company_id': (self.company_id or emp.company_id
                               or self.env.company).id,
            })
            self.letter_id = letter.id
        else:
            letter.sudo().write({'context_json': json.dumps(self._letter_extras())})
        letter.sudo().action_generate()
        if self.fulfilment in (False, 'pending'):
            self.fulfilment = 'letter'
        if flag(self.env, P_LETTER_SEND):
            letter.sudo().action_send()
            self.message_post(body=_("Award letter emailed."))
        else:
            self.message_post(body=_(
                "Award letter prepared and filed. Emailing letters is switched "
                "off, so it was not sent."))
        return letter

    def _letter_extras(self):
        """The extra holes THIS letter fills.

        `amount` and `reason` are plain strings and the letter engine escapes
        every value it substitutes, which is correct and stays correct. The one
        value that carries markup is `extra` — the one hole P0's seeded incentive
        body actually prints — and it is built HERE with
        every interpolated piece `escape()`d on the way in — the narrow hatch
        P6 opened for its objectives list (`pb_pip/models/letter_ext.py`),
        copied rather than generalised, because a general "raw placeholders"
        mechanism hands every future phase a way to put unescaped strings into
        somebody's letter.
        """
        self.ensure_one()
        from .comp_common import INCENTIVE_KIND_LABEL, money
        amount = money(self.amount, self.currency_id)
        kind = INCENTIVE_KIND_LABEL.get(self.kind, self.kind or '')
        month = self.period_month.strftime('%B %Y') if self.period_month else ''
        rows = [
            (_('What'), kind),
            (_('Amount'), amount),
            (_('Paid with your salary for'), month),
        ]
        if self.reason:
            rows.append((_('Why'), self.reason))
        table = '<table class="pb-award"><tbody>%s</tbody></table>' % ''.join(
            '<tr><th style="text-align:left;padding:4px 16px 4px 0;">%s</th>'
            '<td style="padding:4px 0;">%s</td></tr>' % (escape(k), escape(v))
            for k, v in rows)
        return {
            'award_kind': kind,
            'award_amount': amount,
            'award_month': month,
            'award_reason': self.reason or '',
            # THE ONE MARKUP KEY. `letter_ext.py` un-escapes exactly this key on
            # exactly this letter type, and nothing else, anywhere.
            'extra': table,
        }

    # ------------------------------------------------------------ the reads
    @api.model
    def approved_for_month(self, month, company_id=False):
        """Approved awards whose month is `month` and that are not yet queued.

        `month` is a date string or a date; only the year and month are used.
        R43 — over JSON-RPC this arrives as a plain string, which is exactly
        what it is coerced from here.
        """
        day = fields.Date.to_date(month) if month else fields.Date.context_today(self)
        first = day.replace(day=1)
        last = (first.replace(year=first.year + 1, month=1) if first.month == 12
                else first.replace(month=first.month + 1))
        domain = [
            ('state', '=', 'approved'),
            ('fulfilment', 'in', (False, 'pending', 'letter')),
            ('period_month', '>=', first),
            ('period_month', '<', last),
        ]
        if company_id:
            domain.append(('company_id', '=', int(company_id)))
        return self.search(domain, order='employee_id, id')
