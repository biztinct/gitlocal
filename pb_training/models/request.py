# -*- coding: utf-8 -*-
"""LEARNING L5 — `pb.training.request`: "I would like to take this course".

An employee asks for one of our courses, one from the outside list, or
something they found themselves. Their manager decides; when it costs money
the HR lead decides after them (`request_approval.py`). What an agreement
does depends on what was asked for:

  * ONE OF OURS — the course is put on them at once (an assignment, reason
    One-off, linked back to this request). Finishing it makes the request
    "Taken".
  * OUTSIDE / SOMETHING ELSE — they get an email with the link and how to
    claim it back. The amount is PRE-BOOKED against their training
    allowance from that moment (`committed`), so the same money cannot be
    promised twice; when the claim with the receipt and the certificate is
    agreed, the request becomes "Claimed back" and the money moves from
    pre-booked to agreed in the same transaction — never in neither, never
    in both.

A REQUEST NEVER WRITES MONEY ANYWHERE (handover §5.2). Only the claim → award
lane does (ledger L6). The state is driven by the approval chain for
`submitted → approved / refused`; `taken`, `claimed` and `cancelled` are the
request's own and are written through `_chain_state_write` (the mixin's
token), which also withdraws an open approval when somebody cancels.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .training_common import (
    GROUP_USER, P_CLAIM_OVER, P_DEFAULT_DUE, REQUEST_KIND_LABEL, REQUEST_KINDS,
    REQUEST_OPEN, REQUEST_STATE_LABEL, REQUEST_STATES, as_id, flag, leg,
    money_words, number, tr,
)

_logger = logging.getLogger(__name__)


class PbTrainingRequest(models.Model):
    _name = 'pb.training.request'
    _description = 'Course request'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'id desc'

    #: The small ladder the record keeps when no route is published (the
    #: route is seeded on every company, so this is the fallback only). A
    #: decision without a route is the training team's.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): GROUP_USER,
        ('submitted', 'refused'): GROUP_USER,
        ('draft', 'refused'): None,
    }

    name = fields.Char(string='Request', compute='_compute_name', store=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Who is asking', required=True, index=True,
        ondelete='cascade', tracking=True)
    kind = fields.Selection(REQUEST_KINDS, string='What they are asking for',
                            required=True, default='ours', tracking=True)
    channel_id = fields.Many2one(
        'slide.channel', string='Our course', index=True, ondelete='set null')
    outside_course_id = fields.Many2one(
        'pb.training.outside.course', string='Outside course', index=True,
        ondelete='set null')
    course_name = fields.Char(string='Course', required=True, tracking=True)
    provider = fields.Char(string='Who runs it')
    url = fields.Char(string='Link')
    amount = fields.Monetary(string='What it costs',
                             currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    year = fields.Integer(string='Counts against',
                          default=lambda self: fields.Date.today().year,
                          index=True)
    when_words = fields.Char(string='When they would take it')
    why = fields.Text(string='Why', required=True)
    state = fields.Selection(REQUEST_STATES, string='How far it has got',
                             default='draft', required=True, index=True,
                             tracking=True, copy=False)
    assignment_id = fields.Many2one(
        'pb.training.assignment', string='The course put on them',
        ondelete='set null', copy=False, index=True)
    claim_id = fields.Many2one('pb.training.claim', string='The claim',
                               ondelete='set null', copy=False, index=True)
    decided_on = fields.Datetime(string='Answered on', readonly=True,
                                 copy=False)
    submitted_on = fields.Datetime(string='Sent in on', readonly=True,
                                   copy=False)
    refuse_note = fields.Text(string='Why it was turned down', copy=False)
    put_on_by_id = fields.Many2one(
        'res.users', string='Put on by the training team', readonly=True,
        copy=False,
        help='Set when the training team agreed it on the person\'s behalf '
             '("Put someone on it").')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    allowance_left_words = fields.Char(
        string='Allowance left', compute='_compute_left_words')

    # =====================================================================
    #  computes and sanity
    # =====================================================================
    @api.depends('employee_id', 'course_name')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (rec.employee_id.sudo().name
                                     or _('Somebody'),
                                     rec.course_name or _('a course'))

    def _compute_left_words(self):
        for rec in self:
            try:
                facts = rec._facts()
                rec.allowance_left_words = money_words(
                    rec.env, facts['left'], facts['currency'])
            except Exception:           # noqa: BLE001 — a word is not fatal
                rec.allowance_left_words = ''

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("The cost cannot be below zero."))

    @api.constrains('kind', 'channel_id', 'outside_course_id')
    def _check_target(self):
        for rec in self:
            if rec.kind == 'ours' and not rec.channel_id:
                raise ValidationError(_("Pick which of our courses."))
            if rec.kind == 'outside' and not rec.outside_course_id:
                raise ValidationError(_("Pick the outside course."))

    @api.constrains('employee_id', 'channel_id', 'outside_course_id',
                    'course_name', 'state')
    def _check_one_open(self):
        """ONE OPEN REQUEST PER PERSON PER COURSE — two answers to one
        question is how the same course gets paid for twice."""
        for rec in self:
            if rec.state not in REQUEST_OPEN:
                continue
            domain = [('id', '!=', rec.id),
                      ('employee_id', '=', rec.employee_id.id),
                      ('state', 'in', REQUEST_OPEN)]
            if rec.kind == 'ours':
                domain.append(('channel_id', '=', rec.channel_id.id))
            elif rec.kind == 'outside':
                domain.append(('outside_course_id', '=',
                               rec.outside_course_id.id))
            else:
                domain += [('kind', '=', 'other'),
                           ('course_name', '=ilike', rec.course_name)]
            if self.sudo().search_count(domain):
                raise ValidationError(_(
                    "%(who)s has already asked for %(course)s and that "
                    "request is still open.",
                    who=rec.employee_id.sudo().name or '',
                    course=rec.course_name or ''))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            emp = self.env['hr.employee'].sudo().browse(
                vals.get('employee_id') or 0).exists()
            if emp and not vals.get('company_id'):
                vals['company_id'] = (emp.company_id or self.env.company).id
            if not vals.get('currency_id') and vals.get('company_id'):
                vals['currency_id'] = self.env['res.company'].sudo().browse(
                    vals['company_id']).currency_id.id
        return super().create(vals_list)

    # =====================================================================
    #  the allowance — pre-booked
    # =====================================================================
    def _facts(self):
        """The allowance as THIS request sees it: everything agreed and
        pre-booked for this person and year, without itself."""
        self.ensure_one()
        return self.env['pb.training.claim'].sudo()._facts_for(
            self.employee_id, self.year, currency=self.currency_id,
            skip_request=self)

    @api.model
    def _committed(self, employee, year, skip=None):
        """Agreed requests that cost money and have not been claimed back
        yet — what is pre-booked against the allowance."""
        domain = [('employee_id', '=', as_id(employee)),
                  ('year', '=', int(year or fields.Date.today().year)),
                  ('state', 'in', ('approved', 'taken')),
                  ('amount', '>', 0)]
        if skip:
            domain.append(('id', '!=', as_id(skip)))
        return sum(self.sudo().search(domain).mapped('amount'))

    def _request_problem(self):
        """The sentence that refuses this request on money, or ''.

        The same rule and the same switch as a claim (`P_CLAIM_OVER`): over
        what is left is refused with the arithmetic in the sentence.
        """
        self.ensure_one()
        if self.amount <= 0 or flag(self.env, P_CLAIM_OVER):
            return ''
        facts = self._facts()
        cur = facts['currency']
        env = self.env
        if not facts['allowance']:
            return _(
                "No training allowance has been set for %(year)s, so a course "
                "that costs money cannot be agreed yet. Ask the training team "
                "to set one.", year=facts['year'])
        if self.amount <= facts['left']:
            return ''
        return _(
            "That is more than is left. The allowance for %(year)s is "
            "%(allowance)s; %(agreed)s is already agreed and %(committed)s is "
            "set aside for courses agreed but not claimed yet, so %(left)s is "
            "left and this course is %(asked)s.",
            year=facts['year'],
            allowance=money_words(env, facts['allowance'], cur),
            agreed=money_words(env, facts['agreed'], cur),
            committed=money_words(env, facts.get('committed', 0.0), cur),
            left=money_words(env, facts['left'], cur),
            asked=money_words(env, self.amount, cur))

    # =====================================================================
    #  the ladder
    # =====================================================================
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        for rec in self:
            if to_state == 'submitted':
                rec.sudo().write({'submitted_on': fields.Datetime.now()})
            elif to_state == 'approved':
                rec.sudo().write({'decided_on': fields.Datetime.now()})
                leg(self.env, 'act on an agreed course request',
                    rec._on_approved)
            elif to_state == 'refused':
                rec.sudo().write({'decided_on': fields.Datetime.now()})
                leg(self.env, 'tell them the request was turned down',
                    lambda rec=rec: rec._tell(
                        'pb_training.mail_template_request_refused'))
        return res

    def _approval_reject(self, request, reason):
        """The Inbox's reason is the one the person reads in the email."""
        for rec in self:
            if reason and not rec.refuse_note:
                rec.sudo().write({'refuse_note': reason})
        return super()._approval_reject(request, reason)

    def _on_approved(self):
        """Ours: put the course on them now. Outside: tell them how to go
        about it and how to claim it back."""
        self.ensure_one()
        if self.kind == 'ours':
            return self._assign_ours()
        return self._tell('pb_training.mail_template_request_approved')

    def _assign_ours(self):
        self.ensure_one()
        if self.assignment_id or not self.channel_id:
            return False
        emp = self.employee_id.sudo()
        Assignment = self.env['pb.training.assignment'].sudo().with_context(
            allowed_company_ids=[(emp.company_id or self.env.company).id])
        open_row = Assignment.search([
            ('channel_id', '=', self.channel_id.id),
            ('employee_id', '=', emp.id),
            ('state', 'in', ('assigned', 'in_progress', 'overdue',
                             'excused'))], limit=1)
        if open_row:
            # Already on it (somebody else put them on it in the meantime):
            # link that one rather than refuse an agreed request.
            self.sudo().write({'assignment_id': open_row.id})
            return True
        days = number(self.env, P_DEFAULT_DUE, 14)
        res = Assignment.assign_many(
            self.channel_id.id, [emp.id], reason='adhoc',
            due_date=fields.Date.today() + timedelta(days=max(days, 1)),
            extra={'request_id': self.id})
        made = res.get('made') or []
        if made:
            self.sudo().write({'assignment_id': made[0]})
            return True
        self.message_post(body=_(
            "Agreed, but the course could not be put on them: %s",
            res.get('message') or ''))
        return False

    def _mark_taken(self):
        """They did it (our course finished, or the training team says so
        for an outside one)."""
        for rec in self:
            if rec.state in ('approved',):
                rec.sudo()._chain_state_write('taken')
                rec.message_post(body=_("Marked as taken."))
                leg(rec.env, 'what finishing a requested course does',
                    rec._after_taken)
        return True

    def _mark_claimed(self, claim):
        """The claim with the receipt and the certificate was agreed: the
        pre-booked money is now agreed money (it leaves `committed` in the
        same transaction the claim enters `agreed`)."""
        for rec in self:
            if rec.state in ('approved', 'taken'):
                was_taken = rec.state == 'taken'
                rec.sudo().write({'claim_id': claim.id})
                rec.sudo()._chain_state_write('claimed')
                rec.message_post(body=_("Claimed back: the claim was agreed."))
                if not was_taken:
                    leg(rec.env, 'what finishing a requested course does',
                        rec._after_taken)
        return True

    def _after_taken(self):
        """Hook: skills and feedback ride on this (skill_grant.py,
        feedback.py). Outside courses only — ours ride the assignment."""
        return True

    # =====================================================================
    #  telling people (English bodies, ledger LD10 / LN47)
    # =====================================================================
    def _tell(self, xmlid):
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_training: %s is missing', xmlid)
            return False
        emp = self.employee_id.sudo()
        to = (emp.work_email or '').strip() or (emp.user_id.email or '').strip()
        if not to:
            return False
        template.sudo().with_context(lang='en_US').send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True

    def claim_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/my/training/claims?request=%s' % (base.rstrip('/'),
                                                     self.id)

    def amount_words(self):
        self.ensure_one()
        if not self.amount:
            return _("No cost")
        return money_words(self.env, self.amount, self.currency_id)

    # =====================================================================
    #  the buttons
    # =====================================================================
    def action_submit(self):
        for rec in self:
            problem = rec._request_problem()
            if problem:
                raise UserError(problem)
            rec._advance_state('submitted')
        return True

    def action_approve(self):
        for rec in self:
            rec._advance_state('approved')
        return True

    def action_refuse(self):
        for rec in self:
            rec.action_refuse_chain(rec.refuse_note or False)
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'submitted', 'approved'):
                raise UserError(_("That request is already closed."))
            if rec.state == 'approved' and (rec.assignment_id or rec.claim_id):
                raise UserError(_(
                    "That request is already under way, so it cannot be "
                    "cancelled from here. Ask the training team."))
            rec.sudo()._chain_state_write('cancelled')
        return True

    # =====================================================================
    #  what a screen reads
    # =====================================================================
    def _target_words(self):
        self.ensure_one()
        return tr(self.env, REQUEST_KIND_LABEL.get(self.kind, ''))

    def _payload(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        claim = self.claim_id.sudo()
        return {
            'id': self.id,
            'who': emp.name or '',
            'employee_id': emp.id,
            'department': emp.department_id.name or '',
            'manager': emp.parent_id.name or '',
            'kind': self.kind,
            'kind_word': self._target_words(),
            'course': self.course_name or '',
            'channel_id': self.channel_id.id,
            'outside_course_id': self.outside_course_id.id,
            'provider': self.provider or '',
            'url': self.url or '',
            'amount': self.amount or 0.0,
            'amount_words': self.amount_words(),
            'currency': self.currency_id.name or '',
            'year': self.year,
            'when_words': self.when_words or '',
            'why': self.why or '',
            'state': self.state,
            'state_word': tr(self.env, REQUEST_STATE_LABEL.get(self.state,
                                                               '')),
            'refuse_note': self.refuse_note or '',
            'assignment_id': self.assignment_id.id,
            'claim_id': claim.id,
            'claim_state': claim.state or '',
            'put_on_by': self.put_on_by_id.name or '',
            'can_claim': self.state in ('approved', 'taken')
            and self.amount > 0 and not (claim and claim.state in (
                'submitted', 'approved')),
            'can_cancel': self.state in ('draft', 'submitted')
            or (self.state == 'approved' and not self.assignment_id
                and not claim),
            'submitted_on': fields.Datetime.to_string(self.submitted_on) or '',
            'decided_on': fields.Datetime.to_string(self.decided_on) or '',
        }

    # =====================================================================
    #  the door the learner uses (My learning and /my/training/requests)
    # =====================================================================
    @api.model
    def ask(self, values):
        """Make one and send it in, in a single press (the delay/claim
        rule: a draft nobody sends in is a request that was never made).
        Everything inside one savepoint: a refusal leaves nothing behind."""
        emp = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if not emp:
            raise AccessError(_(
                "You do not have an employee record yet, so there is nobody "
                "to ask for. Tell your HR team."))
        vals = self._values_from_form(emp, values or {})
        with self.env.cr.savepoint():
            rec = self.sudo().create(vals)
            problem = rec._request_problem()
            if problem:
                raise UserError(problem)
            rec._advance_state('submitted')
        manager = emp.parent_id.name
        if rec.amount > 0:
            message = _("Asked. %(who)s decides first, then the HR lead, "
                        "because it costs money. You get an email either way.",
                        who=manager) if manager else _(
                "Asked. Your manager decides first, then the HR lead, because "
                "it costs money. You get an email either way.")
        else:
            message = _("Asked. %(who)s decides, and you get an email either "
                        "way.", who=manager) if manager else _(
                "Asked. Your manager decides, and you get an email either "
                "way.")
        return {'id': rec.id, 'state': rec.state, 'message': message}

    @api.model
    def _values_from_form(self, emp, values):
        kind = values.get('kind') or 'ours'
        if kind not in dict(REQUEST_KINDS):
            raise UserError(_("Say what you would like to take."))
        why = (values.get('why') or '').strip()[:2000]
        if not why:
            raise UserError(_(
                "Say in a line why — what it will help you do. Your manager "
                "reads it."))
        vals = {
            'employee_id': emp.id,
            'kind': kind,
            'why': why,
            'when_words': (values.get('when_words') or '').strip()[:200],
            'company_id': (emp.company_id or self.env.company).id,
        }
        if kind == 'ours':
            channel = self.env['slide.channel'].sudo().browse(
                as_id(values.get('channel_id'))).exists()
            if not channel or not channel.active or not channel.is_published \
                    or not channel.pb_requestable:
                raise UserError(_("Pick one of the courses on the list."))
            vals.update({'channel_id': channel.id,
                         'course_name': channel.name, 'amount': 0.0})
        elif kind == 'outside':
            course = self.env['pb.training.outside.course'].sudo().browse(
                as_id(values.get('outside_course_id'))).exists()
            if not course or not course.active or course.company_id.id not in (
                    emp.company_id | self.env.companies).ids:
                raise UserError(_("Pick one of the outside courses on the "
                                  "list."))
            vals.update({'outside_course_id': course.id,
                         'course_name': course.name,
                         'provider': course.provider or '',
                         'url': course.url or '',
                         'amount': course.cost or 0.0,
                         'currency_id': course.currency_id.id})
        else:
            name = (values.get('course_name') or '').strip()[:200]
            if not name:
                raise UserError(_("Say what the course is called."))
            try:
                amount = float(values.get('amount') or 0)
            except (TypeError, ValueError):
                amount = -1
            if amount < 0:
                raise UserError(_("The cost is a number — 0 if it is free."))
            url = (values.get('url') or '').strip()[:500]
            if url and not url.lower().startswith(('http://', 'https://')):
                url = 'https://' + url
            vals.update({'course_name': name,
                         'provider': (values.get('provider') or '').strip()
                         [:200],
                         'url': url, 'amount': amount})
        return vals


class PbTrainingClaimCommitted(models.Model):
    """The allowance arithmetic learns about pre-booked money.

    `left = allowance − agreed − committed`, where committed is every agreed
    request that costs money and has not been claimed back yet. A claim
    raised FROM a request does not count that request against itself (its
    money is the same money), and `skip_request` lets a request weigh itself
    the same way.
    """
    _inherit = 'pb.training.claim'

    @api.model
    def _facts_for(self, employee, year, skip_claim=None, currency=None,
                   skip_request=None):
        facts = super()._facts_for(employee, year, skip_claim=skip_claim,
                                   currency=currency)
        if skip_request is None and skip_claim:
            skip_request = skip_claim.sudo().request_id
        committed = self.env['pb.training.request']._committed(
            employee, year, skip=skip_request)
        facts['committed'] = committed
        facts['left'] = max(facts['allowance'] - facts['agreed'] - committed,
                            0.0)
        return facts


class PbTrainingAssignmentRequest(models.Model):
    """An agreed request for one of our courses is an assignment; finishing
    it makes the request "Taken"."""
    _inherit = 'pb.training.assignment'

    request_id = fields.Many2one(
        'pb.training.request', string='From a course request', index=True,
        ondelete='set null', readonly=True, copy=False)

    def _refresh_one(self, today=None):
        was = self.state
        state = super()._refresh_one(today)
        if state == 'done' and was != 'done' and self.request_id:
            leg(self.env, 'the course request is taken',
                lambda: self.request_id.sudo()._mark_taken())
        return state
