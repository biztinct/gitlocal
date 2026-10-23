# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T3a — an "Ask HR" question: a conversation, not an approval (D1).

The employee asks from `/my/ask-hr` (an employee login or a full account
alike); HR answers from the backend queue with the ordinary chatter "Send
message" (D4). The state follows the PUBLIC conversation only:

  * a public comment from HR (anyone who is not the employee) → ``answered``
    and stock mail e-mails the employee, who follows the ticket;
  * a reply from the employee → ``with_hr`` (a reply to a closed ticket
    reopens it);
  * notes (internal subtypes) and system messages change nothing and never
    reach the employee's page (`_portal_messages`).

PORTAL SEAMS (ledger T-R11, D3). An employee login holds no ACL on this model.
Every `_portal_*` method is called by the controller on a SUDO record, AFTER
the ownership guard ("the ticket's employee is the session's own employee").
`sudo()` keeps `env.uid`, so `create_uid` and the message author stay the
employee. No `base.group_portal` access row exists, on purpose.
"""

import logging
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext, plaintext2html

_logger = logging.getLogger(__name__)

#: How long after closing a question the employee may still reopen it.
REOPEN_DAYS = 14

#: (value, backend label) — the portal's chip words live in the template.
CATEGORIES = [
    ('pay', 'Pay & payslips'),
    ('leave', 'Leave & attendance'),
    ('documents', 'Documents & letters'),
    ('benefits', 'Benefits & insurance'),
    ('equipment', 'Equipment & access'),
    ('other', 'Something else'),
]

#: Lucide icon per category (names `pb_me_portal.ess_icon` draws).
CATEGORY_ICONS = {
    'pay': 'banknote',
    'leave': 'umbrella',
    'documents': 'file-text',
    'benefits': 'heart',
    'equipment': 'laptop',
    'other': 'message-circle-question',
}

STATES = [
    ('new', 'New'),
    ('with_hr', 'With HR'),
    ('answered', 'Answered'),
    ('closed', 'Closed'),
]

#: Open = the queue's default filter and the portal's "Open" tab.
OPEN_STATES = ('new', 'with_hr', 'answered')

#: The key of the per-company HR owner (D6: a parameter, not a column).
OWNER_PARAM = 'pb_ask_hr.owner_uid.%s'


class PbAskHrTicket(models.Model):
    _name = 'pb.ask.hr.ticket'
    _description = 'Ask HR question'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'last_activity_on desc, id desc'

    name = fields.Char(string='Subject', required=True, tracking=True)
    number = fields.Char(string='Number', readonly=True, copy=False,
                         index=True, default=lambda self: _('New'))
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        tracking=True, ondelete='cascade')
    employee_name = fields.Char(related='employee_id.name', string='Employee name')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True, store=True,
        readonly=False, precompute=True, compute='_compute_company_id')
    category = fields.Selection(CATEGORIES, string='Category', required=True,
                                default='other', tracking=True)
    description = fields.Html(string='What you need', sanitize=True)
    state = fields.Selection(STATES, string='Status', required=True,
                             default='new', index=True, tracking=True,
                             group_expand=True, copy=False)
    user_id = fields.Many2one(
        'res.users', string='HR owner', index=True, tracking=True,
        domain=[('share', '=', False)])
    last_activity_on = fields.Datetime(
        string='Last activity', index=True, copy=False,
        default=fields.Datetime.now)
    answered_on = fields.Datetime(string='Answered on', readonly=True, copy=False)
    closed_on = fields.Datetime(string='Closed on', readonly=True, copy=False)
    closed_by = fields.Selection([('employee', 'The employee'), ('hr', 'HR')],
                                 string='Closed by', readonly=True, copy=False)
    attachment_ids = fields.Many2many(
        'ir.attachment', 'pb_ask_hr_ticket_attachment_rel', 'ticket_id',
        'attachment_id', string='Files', copy=False)
    # not stored — read by the kanban card, the portal list and Needs you
    waiting_days = fields.Integer(string='Waiting (days)',
                                  compute='_compute_waiting_days')
    last_public_by = fields.Selection(
        [('employee', 'The employee'), ('hr', 'HR')],
        string='Last word from', compute='_compute_last_public_by')

    # ------------------------------------------------------------- computes
    @api.depends('employee_id')
    def _compute_company_id(self):
        for ticket in self:
            ticket.company_id = (ticket.employee_id.company_id
                                 or ticket.company_id or self.env.company)

    @api.depends('state', 'last_activity_on')
    def _compute_waiting_days(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.state in ('new', 'with_hr') and ticket.last_activity_on:
                ticket.waiting_days = max(0, (now - ticket.last_activity_on).days)
            else:
                ticket.waiting_days = 0

    @api.depends('message_ids', 'state', 'last_activity_on')
    def _compute_last_public_by(self):
        for ticket in self:
            last = ticket.sudo()._pb_public_messages()[-1:]
            if not last:
                ticket.last_public_by = False
            elif last.author_id & ticket._pb_employee_partners():
                ticket.last_public_by = 'employee'
            else:
                ticket.last_public_by = 'hr'

    def _compute_access_url(self):
        super()._compute_access_url()
        for ticket in self:
            ticket.access_url = '/my/ask-hr/%s' % ticket.id

    @api.depends('number', 'name')
    def _compute_display_name(self):
        for ticket in self:
            ticket.display_name = ('%s · %s' % (ticket.number, ticket.name)
                                   if ticket.number and ticket.name
                                   else ticket.name or ticket.number or '')

    # -------------------------------------------------------------- helpers
    def _pb_employee_partners(self):
        """Every partner that speaks AS the employee: their login's partner
        and the employee's work contact."""
        emp = self.employee_id.sudo()
        return emp.user_id.partner_id | emp.work_contact_id

    def _pb_employee_partner(self):
        """The partner the employee's messages are authored by and the one
        that follows the ticket: the login's partner first (that is the one
        the e-mail link signs in as), else the work contact."""
        emp = self.employee_id.sudo()
        return emp.user_id.partner_id or emp.work_contact_id

    def _pb_public_messages(self):
        """The public conversation: comments on a non-internal subtype, oldest
        first. Notes, tracking and system messages are never in it."""
        self.ensure_one()
        msgs = self.message_ids.filtered(
            lambda m: m.message_type == 'comment' and m.subtype_id
            and not m.subtype_id.internal)
        return msgs.sorted(lambda m: (m.date, m.id))

    @api.model
    def _pb_owner_for(self, company):
        """The company's HR owner from the parameter, when it names an active
        internal user; else an empty recordset (the queue is the discovery)."""
        raw = self.env['ir.config_parameter'].sudo().get_param(
            OWNER_PARAM % company.id)
        try:
            uid = int(raw or 0)
        except (TypeError, ValueError):
            uid = 0
        owner = self.env['res.users'].sudo().browse(uid).exists() if uid else \
            self.env['res.users']
        if owner and (owner.share or not owner.active):
            return self.env['res.users']
        return owner

    # ----------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        Emp = self.env['hr.employee'].sudo()
        now = fields.Datetime.now()
        for vals in vals_list:
            emp = Emp.browse(vals.get('employee_id')).exists()
            company = (self.env['res.company'].browse(vals['company_id'])
                       if vals.get('company_id') else
                       (emp.company_id or self.env.company))
            if not vals.get('number') or vals['number'] == _('New'):
                vals['number'] = self.env['ir.sequence'].sudo().with_company(
                    company).next_by_code('pb.ask.hr.ticket') or _('New')
            vals.setdefault('last_activity_on', now)
            if not vals.get('user_id'):
                owner = self._pb_owner_for(company)
                if owner:
                    vals['user_id'] = owner.id
        # the owner learns of it from the to-do below, not from a second
        # "you have been assigned" mail
        tickets = super(PbAskHrTicket, self.with_context(
            mail_auto_subscribe_no_notify=True)).create(vals_list)
        for ticket in tickets:
            rec = ticket.sudo()
            partners = rec._pb_employee_partner()
            if rec.user_id:
                partners |= rec.user_id.partner_id
            if partners:
                rec.message_subscribe(partner_ids=partners.ids)
            if rec.user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=rec.user_id.id,
                    summary=_('Answer %(number)s: %(subject)s',
                              number=rec.number, subject=rec.name))
        return tickets

    # ------------------------------------------------------------- the mail
    def message_post(self, **kwargs):
        """D4: a PUBLIC comment moves the state — from the employee → with HR,
        from anybody else → answered. Notes and system messages do not."""
        message = super().message_post(**kwargs)
        if (message and message.message_type == 'comment'
                and message.subtype_id and not message.subtype_id.internal):
            for ticket in self:
                author = message.author_id
                by_employee = bool(author & ticket._pb_employee_partners()) or (
                    not author and ticket.employee_id.sudo().user_id == self.env.user)
                ticket._pb_on_public_message(by_employee)
        return message

    def _pb_on_public_message(self, author_is_employee):
        """The state change one public message makes (kept apart so tests can
        call it without a message)."""
        now = fields.Datetime.now()
        for ticket in self.sudo():
            vals = {'last_activity_on': now}
            if author_is_employee:
                if ticket.state != 'with_hr':
                    vals['state'] = 'with_hr'
                if ticket.state == 'closed':
                    vals.update(closed_on=False, closed_by=False)
            else:
                vals.update(state='answered', answered_on=now)
            ticket.write(vals)
            if not author_is_employee:
                ticket._pb_finish_todo()

    def _pb_finish_todo(self):
        """The owner's to-do is done once the question is answered or closed."""
        for ticket in self.sudo():
            todo = ticket.activity_ids.filtered(
                lambda a: a.activity_type_id == self.env.ref(
                    'mail.mail_activity_data_todo', raise_if_not_found=False))
            if todo:
                todo.action_feedback()

    # ----------------------------------------------------------- HR actions
    def _pb_set_owner(self, user, remind=False):
        """The ONE way a question changes hands (NAV P3d): "Take it" on the
        form, and Take it / Hand to… on the Home board, all come here.

        The new owner follows the question; a new question moves to "With
        HR"; an open to-do moves to the new owner with it. ``remind`` puts a
        to-do on the new owner when there was none (a hand-over: the person
        receiving it learns of it from the to-do, as at creation — no second
        "you have been assigned" mail, hence the context key)."""
        todo_type = self.env.ref('mail.mail_activity_data_todo',
                                 raise_if_not_found=False)
        for ticket in self:
            vals = {'user_id': user.id}
            if ticket.state == 'new':
                vals['state'] = 'with_hr'
            ticket.with_context(mail_auto_subscribe_no_notify=True).write(vals)
            ticket.message_subscribe(partner_ids=user.partner_id.ids)
            if ticket.state not in ('new', 'with_hr') or not todo_type:
                continue
            todo = ticket.activity_ids.filtered(
                lambda a: a.activity_type_id == todo_type)
            if todo:
                todo.filtered(lambda a: a.user_id != user).write({'user_id': user.id})
            elif remind:
                ticket.activity_schedule(
                    'mail.mail_activity_data_todo', user_id=user.id,
                    summary=_('Answer %(number)s: %(subject)s',
                              number=ticket.number, subject=ticket.name))
        return True

    def action_take(self):
        """"Take it": the HR person pressing it becomes the owner and follows;
        a new question moves to "With HR"."""
        return self._pb_set_owner(self.env.user)

    def action_hand_to(self, user_id):
        """"Hand to…": somebody else in HR becomes the owner (NAV P3d). Only
        a person who can work the queue may receive it — handing a question
        to somebody who cannot even read it would lose it."""
        user = self.env['res.users'].browse(int(user_id or 0)).exists()
        if not user or user.share or not user.active or not (
                user.has_group('hr.group_hr_user')
                or user.has_group('base.group_system')):
            raise UserError(_('Pick somebody in the HR team.'))
        return self._pb_set_owner(user, remind=user != self.env.user)

    def action_close_with_note(self, note=None, tell_person=False):
        """Close, with a few words (NAV P3d). ``tell_person`` sends them to
        the person as a reply (by e-mail and on their page); otherwise they
        stay a private HR note. Then the ordinary :meth:`action_close`."""
        text = (note or '').strip()
        if text:
            for ticket in self.filtered(lambda t: t.state != 'closed'):
                ticket.message_post(
                    body=plaintext2html(text), message_type='comment',
                    subtype_xmlid='mail.mt_comment' if tell_person else 'mail.mt_note')
        return self.action_close()

    def action_answer_done(self):
        """HR marks it answered without writing (rare — e.g. answered by phone)."""
        now = fields.Datetime.now()
        for ticket in self.filtered(lambda t: t.state != 'answered'):
            ticket.write({'state': 'answered', 'answered_on': now,
                          'last_activity_on': now})
        self._pb_finish_todo()
        return True

    def action_close(self):
        now = fields.Datetime.now()
        for ticket in self.filtered(lambda t: t.state != 'closed'):
            ticket.write({'state': 'closed', 'closed_by': 'hr',
                          'closed_on': now, 'last_activity_on': now})
        self._pb_finish_todo()
        return True

    def action_reopen(self):
        now = fields.Datetime.now()
        for ticket in self.filtered(lambda t: t.state == 'closed'):
            ticket.write({'state': 'with_hr', 'closed_by': False,
                          'closed_on': False, 'last_activity_on': now})
        return True

    # ------------------------------------------- the employee (portal) side
    @api.model
    def _portal_create(self, employee, category, subject, text):
        """A new question for ``employee`` — the SESSION's own employee, which
        the controller resolved (never a form value). Called under sudo."""
        if category not in dict(CATEGORIES):
            category = 'other'
        subject = (subject or '').strip()
        if not subject:
            raise UserError(_('Add a subject so HR knows what this is about.'))
        return self.create({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'category': category,
            'name': subject[:200],
            'description': plaintext2html(text.strip()) if (text or '').strip() else False,
        })

    def _portal_can_reopen(self):
        self.ensure_one()
        return bool(self.state == 'closed' and self.closed_on
                    and fields.Datetime.now() - self.closed_on
                    <= timedelta(days=REOPEN_DAYS))

    def _portal_reply(self, body, attachments=None):
        """The employee's reply, authored by their own partner. A reply to a
        closed question reopens it (inside the reopen window)."""
        self.ensure_one()
        text = (body or '').strip()
        if not text and not attachments:
            raise UserError(_('Write a message, or attach a file, before sending.'))
        if self.state == 'closed' and not self._portal_can_reopen():
            raise UserError(_(
                'This question was closed more than %s days ago. Ask a new '
                'question instead.', REOPEN_DAYS))
        partner = self._pb_employee_partner()
        return self.message_post(
            body=plaintext2html(text) if text else Markup(''),
            author_id=partner.id if partner else None,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            attachment_ids=attachments.ids if attachments else [],
        )

    def _portal_close(self):
        """"That solved it" — returns False when it was already closed."""
        self.ensure_one()
        if self.state == 'closed':
            return False
        now = fields.Datetime.now()
        self.write({'state': 'closed', 'closed_by': 'employee',
                    'closed_on': now, 'last_activity_on': now})
        self._pb_finish_todo()
        return True

    def _portal_reopen(self):
        """Reopen within REOPEN_DAYS of closing; returns False when it was not
        closed."""
        self.ensure_one()
        if self.state != 'closed':
            return False
        if not self._portal_can_reopen():
            raise UserError(_(
                'This question was closed more than %s days ago. Ask a new '
                'question instead.', REOPEN_DAYS))
        self.write({'state': 'with_hr', 'closed_by': False, 'closed_on': False,
                    'last_activity_on': fields.Datetime.now()})
        return True

    @api.model
    def _pb_initials(self, name):
        words = [w for w in (name or '').split() if w[:1].isalnum()]
        if not words:
            return '?'
        if len(words) == 1:
            return words[0][:1].upper()
        return (words[0][:1] + words[-1][:1]).upper()

    def _pb_attachment_payload(self, attachments):
        """Tokened download links (ledger T20): an employee login has no ACL
        on `ir.attachment`; the token is what `/web/content` accepts."""
        out = []
        for att in attachments.sudo():
            token = att.generate_access_token()[0]
            out.append({
                'id': att.id,
                'name': att.name or _('File'),
                'mimetype': att.mimetype or '',
                'url': '/web/content/%s?download=true&access_token=%s' % (
                    att.id, token),
            })
        return out

    def _portal_messages(self):
        """The public thread for the employee's page, oldest first. Never a
        note (`subtype_id.internal`) and never a non-comment message."""
        self.ensure_one()
        partners = self._pb_employee_partners()
        out = []
        for msg in self.sudo()._pb_public_messages():
            author = msg.author_id
            name = author.name or msg.email_from or ''
            is_employee = bool(author & partners)
            if not html2plaintext(msg.body or '').strip() and not msg.attachment_ids:
                continue
            out.append({
                'id': msg.id,
                'author': name,
                'initials': self._pb_initials(name),
                'is_employee': is_employee,
                'body': msg.body or Markup(''),
                'date': msg.date,
                'attachments': self._pb_attachment_payload(msg.attachment_ids),
            })
        return out
