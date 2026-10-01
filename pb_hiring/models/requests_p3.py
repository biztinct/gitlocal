# -*- coding: utf-8 -*-
"""RECRUIT phase 3 — roles without friction.

WHAT THIS FILE ADDS (register lines G-12…G-17, G-19, G-39, G-40, G-43):

  * **The request as a facet of the role** (RC-D6). `state` is the role's own
    life (being set up / open / filled / closed); `request_state` is the
    hiring request (none / asked / being written / sent in / Head of HR agreed
    / agreed / not approved). A role never waits for its request.
  * **Ask a manager** (G-13): a one-page request at `/hiring/r/<token>` that
    saves as they type, reminders on the recruiter's cadence in working days,
    and the talent lead told after three working days.
  * **Budget that tells and never blocks** (G-15, R2/R10): the manager types
    the expected figure, HR records the confirmed one, and over budget emails
    the company's budget-flag people. Nothing waits.
  * **The one hard rule** (RC-D5, G-43): no offer is SENT unless the role's
    request is agreed, and the sentence names who must press Agree.
  * **Confidential** (G-12): off referrals, off the careers page, off the
    "other roles" lists, and out of sight of everyone but the hiring team,
    the person it is for and who they would report to.
  * **Job descriptions shared, not signed** (G-17), from templates by role
    family, with a comment page for the manager.
  * **The background check and the papers run alongside** (G-39, G-40): an
    adverse result tells the Head of HR; the papers are asked for at the
    moment the company chose, and the talent lead hears when they are late.
  * **One sender address** for every hiring email (`_sender`).

Every piece of paperwork (a mail, a to-do, a note) runs in its own savepoint
(`leg`), so a broken template can never undo a decision somebody made (R104,
R131).
"""

import logging
import secrets
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import ENGINE_WRITE

from .hiring_common import (
    BUDGET_AGREEMENT, GROUP_ADMIN, GROUP_MANAGER,
    P_ASK_ESCALATE_DAYS, P_DOCREQ_TRIGGER, P_NOTIFY_MAIL, P_REFERRAL_ANNOUNCE,
    P_REMINDER_CAP, REQUEST_STATES, REQUEST_WAITING, REQUEST_WITH_HR,
    ROLE_TYPES, as_id, counted, flag, leg, number, text,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'

#: "Remind now" never sends twice inside this window (blueprint rule).
REMIND_NOW_WINDOW = timedelta(hours=1)

#: The request states after which the manager's page is read-only.
SENT_STATES = ('sent_in', 'hr_ok', 'agreed', 'not_approved')

#: What the manager's page may write, and nothing else.
PAGE_TEXT_LIMITS = {
    'title': 120, 'location': 120, 'pb_role_level': 120,
    'requirements': 6000, 'remarks': 2000,
}


def _todo(record, user, summary, note):
    """One to-do, never two with the same summary, never for a portal user."""
    if not user or user.share or not user.active:
        return False
    Activity = record.env['mail.activity'].sudo()
    if Activity.search_count([('res_model', '=', record._name),
                              ('res_id', '=', record.id),
                              ('user_id', '=', user.id),
                              ('summary', '=', summary)]):
        return False
    record.sudo().activity_schedule(
        _TODO, summary=summary, note=note, user_id=user.id,
        date_deadline=fields.Date.context_today(record))
    return True


def _mail(record, xmlid, email_to, ctx=None):
    """One mail, addressed explicitly (R6), queued, never fatal."""
    if not email_to:
        return False
    template = record.env.ref(xmlid, raise_if_not_found=False)
    if not template:
        _logger.info('pb_hiring: the mail template %s is not in this build',
                     xmlid)
        return False
    template.sudo().with_context(**(ctx or {})).send_mail(
        record.id, force_send=False,
        email_values={'email_to': email_to, 'auto_delete': False})
    return True


def _email_of(user=None, employee=None):
    user = user.sudo() if user else user
    employee = employee.sudo() if employee else employee
    return ((user.email if user else '') or
            (employee.work_email if employee else '') or
            (employee.user_id.email if employee else '') or '').strip()


# =========================================================================
#  Job description templates and comments
# =========================================================================
class PbHiringJdTemplate(models.Model):
    """A starting point for an advert, by role family (G-17).

    The family is a word (Field, Sales, Tech, Finance…), not a link to a
    department: most companies name their departments differently from the
    kind of role, and the recruiter picks the template in one click anyway.
    """
    _name = 'pb.hiring.jd.template'
    _description = 'Job description template'
    _order = 'sequence, name, id'

    name = fields.Char(string='Name', required=True, translate=True)
    family = fields.Char(string='Role family',
                         help='The kind of role this suits, in a word.')
    body = fields.Html(string='The advert', translate=True,
                       sanitize_attributes=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, index=True,
                                 default=lambda self: self.env.company)
    seed_key = fields.Char(readonly=True, copy=False, index=True,
                           help='Which product template this was seeded from.')

    @api.model
    def _for_role(self, req):
        """The template whose family word appears in the role's department,
        else the company's first."""
        req = req.sudo()
        rows = self.sudo().search([('company_id', '=', req.company_id.id)])
        dept = (req.department_id.name or '').lower()
        title = (req.title or '').lower()
        for row in rows:
            word = (row.family or '').strip().lower()
            if word and (word in dept or word in title):
                return row
        return rows[:1]


class PbHiringJdComment(models.Model):
    """What the manager said about a draft, from the shared page."""
    _name = 'pb.hiring.jd.comment'
    _description = 'Comment on a job description'
    _order = 'id desc'

    jd_id = fields.Many2one('pb.hiring.jd', required=True, index=True,
                            ondelete='cascade')
    requisition_id = fields.Many2one(related='jd_id.requisition_id',
                                     store=True, index=True)
    company_id = fields.Many2one(related='jd_id.company_id', store=True,
                                 index=True)
    employee_id = fields.Many2one('hr.employee', string='From',
                                  ondelete='set null')
    author_name = fields.Char(string='Name')
    body = fields.Text(string='Comment', required=True)


class PbHiringJdShare(models.Model):
    _inherit = 'pb.hiring.jd'

    pb_share_url = fields.Char(compute='_compute_pb_share_url',
                               compute_sudo=True)

    def _compute_pb_share_url(self):
        for rec in self:
            rec.pb_share_url = rec._share_url() \
                if rec.sudo().share_token else ''

    def _share_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/hiring/j/%s' % (base.rstrip('/'), self.sudo().share_token)

    def _ensure_share_token(self):
        self.ensure_one()
        if not self.sudo().share_token:
            self.sudo().write({'share_token': secrets.token_urlsafe(24)})
        return self.sudo().share_token

    @api.model
    def _for_share_token(self, token):
        """`(jd, status)` — a wrong key and a closed role look the same."""
        if not token or len(token) < 12:
            return self.browse(), 'invalid'
        jd = self.sudo().search([('share_token', '=', token)], limit=1)
        if not jd:
            return self.browse(), 'invalid'
        if jd.requisition_id.state in ('closed', 'filled'):
            return jd, 'closed'
        return jd, 'ok'

    def action_share(self, employee=None):
        """Email the draft with its comment link to the manager (G-17)."""
        self.ensure_one()
        employee = employee or self._jd_manager()
        employee = employee.sudo() if employee else employee
        if not employee:
            raise UserError(_(
                "Nobody is named on this role to share it with. Ask a "
                "manager for the request first, or say who they would report "
                "to on the role."))
        self._ensure_share_token()
        self.sudo().write({'shared_with_id': employee.id,
                           'shared_on': fields.Datetime.now()})
        address = _email_of(employee.user_id, employee)
        mailed = bool(address) and bool(leg(
            self.env, 'sharing advert %s' % self.id,
            lambda: _mail(self, 'pb_hiring.mail_template_jd_share', address)))
        leg(self.env, 'the advert to-do for %s' % employee.name,
            lambda: _todo(self, employee.user_id,
                          _('Read the advert for %s', self.title or ''),
                          _("The recruiter would like your input on the "
                            "advert. Read it and leave a comment on its "
                            "page.")))
        self.requisition_id._log_role(_(
            "Version %(n)s of the advert was shared with %(who)s for input.",
            n=self.version or 1, who=employee.name or ''))
        return {'mailed': mailed, 'who': employee.name or '',
                'link': self._share_url()}

    def _receive_comment(self, body, name=None):
        """A comment from the shared page: kept, on the timeline, and a
        to-do for the recruiter."""
        self.ensure_one()
        body = (body or '').strip()[:4000]
        if not body:
            return False
        jd = self.sudo()
        who = jd.shared_with_id
        author = (name or '').strip()[:120] or who.name or _('The manager')
        row = self.env['pb.hiring.jd.comment'].sudo().create({
            'jd_id': jd.id, 'employee_id': who.id or False,
            'author_name': author, 'body': body})
        line = Markup('<p><b>%s</b> %s</p><p>%s</p>') % (
            author, _('commented on version %s of the advert:',
                      jd.version or 1), body)
        leg(self.env, 'the advert comment note',
            lambda: jd.message_post(body=line, message_type='comment',
                                    subtype_xmlid='mail.mt_note'))
        req = jd.requisition_id
        leg(self.env, 'the advert comment on the role',
            lambda: req.message_post(body=line, message_type='comment',
                                     subtype_xmlid='mail.mt_note'))
        leg(self.env, 'the advert comment to-do',
            lambda: _todo(req, req.recruiter_id,
                          _('%(who)s commented on the advert for %(role)s',
                            who=author, role=req.title or ''),
                          body[:400]))
        return row


# =========================================================================
#  The company: who is told about money, and who hiring email comes from
# =========================================================================
class HiringCompanyP3(models.Model):
    _inherit = 'res.company'

    pb_budget_flag_user_ids = fields.Many2many(
        'res.users', 'pb_hiring_company_budget_flag_rel', 'company_id',
        'user_id', string='Told when a request is over budget',
        help='The CEO, the Head of HR and Finance, usually. They get an email '
             'and a to-do when a hiring request asks for more than the '
             'budget. Nothing waits for them.')
    pb_hiring_sender = fields.Char(
        string='Hiring emails come from', compute='_compute_pb_hiring_sender',
        compute_sudo=True)

    def _compute_pb_hiring_sender(self):
        Hiring = self.env['pb.hiring']
        for company in self:
            company.pb_hiring_sender = Hiring._sender(company)


# =========================================================================
#  The role and its request
# =========================================================================
class HiringRequestP3(models.Model):
    _inherit = 'pb.hiring.requisition'

    request_state = fields.Selection(
        REQUEST_STATES, string='The request', default='none', required=True,
        tracking=True, copy=False, index=True)
    asked_employee_id = fields.Many2one(
        'hr.employee', string='Asked of', copy=False, ondelete='set null',
        help='The manager asked to complete the hiring request.')
    asked_user_id = fields.Many2one(
        'res.users', string='Asked of (login)', copy=False, index=True,
        ondelete='set null')
    asked_by_id = fields.Many2one('res.users', string='Asked by', copy=False,
                                  ondelete='set null')
    asked_on = fields.Datetime(string='Asked on', copy=False)
    ask_message = fields.Text(string='The line sent with it', copy=False)
    remind_every_days = fields.Integer(
        string='Remind every (working days)', default=2,
        help='How often the manager is reminded until they send it in.')
    last_reminded_on = fields.Datetime(string='Last reminded', copy=False)
    remind_count = fields.Integer(string='Reminders sent', copy=False)
    escalated_on = fields.Datetime(string='Talent lead told on', copy=False)
    request_token = fields.Char(copy=False, readonly=True, index=True,
                                groups='base.group_system')
    request_saved_on = fields.Datetime(string='Last saved by the manager',
                                       copy=False)
    manager_agreed_on = fields.Datetime(string='Sent in on', copy=False)
    manager_agreed_by_id = fields.Many2one(
        'hr.employee', string='Sent in by the manager', copy=False,
        ondelete='set null')
    sent_in_by_id = fields.Many2one('res.users', string='Sent in by',
                                    copy=False, ondelete='set null')
    agreed_on = fields.Datetime(string='Agreed on', copy=False)
    not_approved_reason = fields.Text(string='Why it was not approved',
                                      copy=False)

    budget_confirmed = fields.Monetary(
        string='Confirmed budget', currency_field='currency_id',
        tracking=True, copy=False,
        help='Entered by the recruiter or HR after checking with Finance. The '
             'expected figure is compared with it.')
    budget_agreement = fields.Selection(
        BUDGET_AGREEMENT, string='Budget', default='not_yet', copy=False,
        tracking=True, help='A tag for tracking the conversation. It blocks '
                            'nothing.')
    budget_flag_sig = fields.Char(copy=False, readonly=True)
    budget_flagged_on = fields.Datetime(string='Budget watchers told on',
                                        copy=False, readonly=True)

    is_confidential = fields.Boolean(
        string='Confidential', tracking=True, copy=False,
        help='Off referrals, off the careers page and out of every list, and '
             'seen only by the hiring team, the person it is for and who they '
             'would report to.')
    jd_template_id = fields.Many2one('pb.hiring.jd.template',
                                     string='Advert template',
                                     ondelete='set null')
    advert_stale = fields.Boolean(
        string='The advert changed since it was published', copy=False)

    request_is_agreed = fields.Boolean(compute='_compute_request_is_agreed')
    # PUBLIC url for the mail templates: a template must not call a private
    # method, and the token itself never leaves the server otherwise.
    pb_request_url = fields.Char(compute='_compute_pb_request_url',
                                 compute_sudo=True)

    def _compute_pb_request_url(self):
        for rec in self:
            rec.pb_request_url = rec._request_url() \
                if rec.sudo().request_token else ''

    @api.depends('request_state')
    def _compute_request_is_agreed(self):
        for rec in self:
            rec.request_is_agreed = rec.request_state == 'agreed'

    # =====================================================================
    #  The write guard and the reactions
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            # G-16: the recruiter comes from the country's rule the moment
            # the role exists, not when somebody agrees it.
            if not rec.recruiter_id:
                rec._leg('the hiring rule on a new role',
                         lambda r=rec: r._assign_recruiter(tell=True))
        return records

    def write(self, vals):
        # STRICT: only a write made as the system passes. The engine's own
        # context flag is not a permission (a browser can send any context
        # key), and this field is what the one hard gate reads (RC-D5).
        if 'request_state' in vals and not self.env.su:
            raise AccessError(_(
                "The request's status moves with its buttons — Ask, Send in, "
                "Agree — never by editing it."))
        res = super().write(vals)
        if {'budget_cost', 'budget_confirmed', 'currency_id'} & set(vals):
            for rec in self:
                if rec.request_state in SENT_STATES:
                    rec._leg('the budget flag on %s' % rec.name,
                             rec._flag_budget)
        if vals.get('is_confidential'):
            for rec in self:
                rec._leg('hiding confidential role %s' % rec.name,
                         rec._apply_confidential)
        return res

    def _request_write(self, state):
        """The one sanctioned write of `request_state` outside the route."""
        return self.sudo().with_context(**{ENGINE_WRITE: True}).write(
            {'request_state': state})

    def _chain_engine_write(self, to_state):
        """The route's own write of the request status, as the system."""
        self.ensure_one()
        return self._request_write(to_state)

    # =====================================================================
    #  The recruiter (G-16)
    # =====================================================================
    def _assign_recruiter(self, tell=False):
        """The country's rule names the recruiter; they (and their manager)
        are told. The person who opened the role naming themselves is not
        told about their own role."""
        self.ensure_one()
        before = self.recruiter_id
        rule = self._apply_country_rule()
        if not rule or self.recruiter_id == before:
            return False
        if tell and self.recruiter_id.id != self.env.uid:
            self._notify_recruiters()
        return True

    # =====================================================================
    #  Opening the role (G-14)
    # =====================================================================
    def _open_for_candidates(self):
        """"Open for candidates": any recruiter, any time, request or not."""
        self.ensure_one()
        if self.state == 'open':
            return False
        if self.state != 'setup':
            raise UserError(_(
                "This role is %s. Open it again first.",
                dict(self._fields['state'].selection).get(self.state)))
        self._chain_state_write('open')
        self._on_opened()
        self._log_role(_("Open for candidates."))
        if self.referral_open:
            self._leg('the referral announcement for %s' % self.name,
                      self._announce_referrals)
        return True

    def _announce_referrals(self):
        """G-19: employees hear that a role is open to referrals — the people
        who can open the referral page, capped, queued, counted."""
        self.ensure_one()
        if not flag(self.env, P_REFERRAL_ANNOUNCE) or self.is_confidential \
                or not self.referral_open:
            return 0
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        employees = self.env['hr.employee'].sudo().search([
            ('company_id', '=', self.company_id.id),
            ('user_id', '!=', False), ('user_id.active', '=', True)],
            limit=cap)
        sent = 0
        seen = set()
        for emp in employees:
            address = _email_of(emp.user_id, emp)
            if not address or address in seen:
                continue
            seen.add(address)
            if _mail(self, 'pb_hiring.mail_template_referral_open', address):
                sent += 1
        self._log_role(_(
            "%(n)s %(word)s told this role is open to referrals.", n=sent,
            word=counted(sent, _('colleague was'), _('colleagues were'))))
        return sent

    def _ensure_advert(self):
        """Publishing a role with no advert in use: the newest draft becomes
        final, or one is written from the role family's template (G-17). A
        recruiter who presses Publish is never told to go and write something
        first — the words are on the role's Details tab to change."""
        self.ensure_one()
        Jd = self.env['pb.hiring.jd'].sudo()
        draft = self.jd_ids.filtered(lambda j: j.state == 'draft').sorted(
            'version', reverse=True)[:1]
        if draft and (draft.body or '').strip():
            draft.action_make_final()
            return draft
        tpl = self.jd_template_id or self.env[
            'pb.hiring.jd.template']._for_role(self)
        body = tpl.body if tpl else ''
        if self.requirements:
            body = (body or '') + str(Markup('<h2>%s</h2><p>%s</p>') % (
                _('What the person needs to be able to do'),
                self.requirements))
        if not (body or '').strip():
            body = str(Markup('<p>%s</p>') % (self.title or ''))
        jd = Jd.create({'requisition_id': self.id, 'title': self.title,
                        'body': body, 'template_id': tpl.id or False})
        jd.action_make_final()
        self._log_role(_(
            "The advert was written from the %s template. Change it on the "
            "role's Details tab — Advert & publishing.",
            tpl.name if tpl else _('standard')))
        return jd

    # =====================================================================
    #  Confidential (G-12)
    # =====================================================================
    def _apply_confidential(self):
        self.ensure_one()
        vals = {}
        if self.referral_open:
            vals['referral_open'] = False
        if self.published:
            vals['published'] = False
        if vals:
            self.sudo().write(vals)
        if self.job_id:
            self._close_job()
        self._log_role(_(
            "Made confidential: off referrals and the careers page, and seen "
            "only by the hiring team, the person it is for and who they "
            "would report to."))
        return True

    # =====================================================================
    #  Asking a manager (G-13)
    # =====================================================================
    def _request_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/hiring/r/%s' % (base.rstrip('/'),
                                   self.sudo().request_token)

    def _ensure_request_token(self):
        self.ensure_one()
        if not self.sudo().request_token:
            self.sudo().write({'request_token': secrets.token_urlsafe(24)})
        return self.sudo().request_token

    @api.model
    def _for_request_token(self, token):
        """`(role, status)` — status ok / sent / closed / invalid. A wrong key
        and a closed role read the same to a stranger."""
        if not token or len(token) < 12:
            return self.browse(), 'invalid'
        rec = self.sudo().search([('request_token', '=', token)], limit=1)
        if not rec:
            return self.browse(), 'invalid'
        if rec.state == 'closed':
            return rec, 'closed'
        if rec.request_state in SENT_STATES:
            return rec, 'sent'
        return rec, 'ok'

    def _ask(self, employee, message='', every=2):
        """Ask one manager to complete this role's request."""
        self.ensure_one()
        employee = employee.sudo().exists() if employee else employee
        if not employee:
            raise UserError(_("Choose the manager to ask."))
        if employee.company_id and employee.company_id != self.company_id:
            raise UserError(_(
                "%s works for another company. Ask somebody in this role's "
                "company.", employee.name))
        if self.request_state in SENT_STATES \
                and self.request_state != 'not_approved':
            raise UserError(_(
                "The request for this role is already sent in. There is "
                "nothing left for a manager to fill in."))
        if self.state == 'closed':
            raise UserError(_("This role is closed."))
        every = max(1, min(int(every or 2), 10))
        self._ensure_request_token()
        user = employee.user_id
        self.sudo().with_context(tracking_disable=True).write({
            'asked_employee_id': employee.id,
            'asked_user_id': user.id or False,
            'asked_by_id': self.env.uid,
            'asked_on': fields.Datetime.now(),
            'ask_message': (message or '').strip()[:2000] or False,
            'remind_every_days': every,
            'last_reminded_on': False,
            'remind_count': 0,
            'escalated_on': False,
            'requested_by_id': employee.id,
        })
        self._request_write('asked')
        address = _email_of(user, employee)
        mailed = bool(address) and bool(self._leg(
            'the request email to %s' % employee.name,
            lambda: _mail(self, 'pb_hiring.mail_template_request_ask',
                          address, {'pb_reminder': 0})))
        self._leg('the request to-do for %s' % employee.name,
                  lambda: _todo(self, user,
                                _('Complete the hiring request: %s',
                                  self.title or ''),
                                _("Open the link in the email, or the role, "
                                  "and fill in the one-page request. It "
                                  "saves as you type.")))
        self._log_role(_(
            "%(by)s asked %(who)s to complete the hiring request%(how)s.",
            by=self.env.user.name, who=employee.name,
            how=_(' by email') if mailed else ''))
        return {'mailed': mailed, 'who': employee.name,
                'link': self._request_url()}

    def _remind(self, manual=False):
        """One reminder to the manager, counted and stamped."""
        self.ensure_one()
        if self.request_state not in REQUEST_WAITING \
                or not self.asked_employee_id:
            return False
        now = fields.Datetime.now()
        if manual and self.last_reminded_on \
                and now - self.last_reminded_on < REMIND_NOW_WINDOW:
            mins = int((REMIND_NOW_WINDOW - (now - self.last_reminded_on))
                       .total_seconds() // 60) + 1
            raise UserError(_(
                "%(who)s was reminded less than an hour ago. Remind now works "
                "again in %(m)s minutes.",
                who=self.asked_employee_id.name, m=mins))
        employee = self.asked_employee_id.sudo()
        address = _email_of(self.asked_user_id, employee)
        count = (self.remind_count or 0) + 1
        if address:
            _mail(self, 'pb_hiring.mail_template_request_ask', address,
                  {'pb_reminder': count})
        self.sudo().with_context(tracking_disable=True).write(
            {'last_reminded_on': now, 'remind_count': count})
        self._log_role(_("%(who)s was reminded (reminder %(n)s).",
                         who=employee.name, n=count))
        return bool(address)

    def _escalate(self):
        """After N working days, the talent lead hears about it (G-13)."""
        self.ensure_one()
        if self.escalated_on or self.request_state not in REQUEST_WAITING:
            return False
        people = self._talent_leads()
        who = self.asked_employee_id.name or _('The manager')
        days = number(self.env, P_ASK_ESCALATE_DAYS, 3)
        summary = _('%(who)s has not completed the request for %(role)s',
                    who=who, role=self.title or '')
        note = _("%(who)s was asked %(n)s working days ago and has not sent "
                 "the request in. A call usually settles it.", who=who,
                 n=days)
        for user in people:
            self._leg('the escalation to-do for %s' % user.login,
                      lambda u=user: _todo(self, u, summary, note))
            self._leg('the escalation email to %s' % user.login,
                      lambda u=user: _mail(
                          self, 'pb_hiring.mail_template_request_escalated',
                          _email_of(u)))
        self.sudo().with_context(tracking_disable=True).write(
            {'escalated_on': fields.Datetime.now()})
        self._log_role(_("The talent lead was told: %s", summary))
        return True

    def _talent_leads(self):
        """Talent lead and Head of hiring members of this role's company."""
        group = self.env.ref(GROUP_MANAGER, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        company = self.company_id
        return group.sudo().all_user_ids.filtered(
            lambda u: u.active and not u.share
            and company.id in u.company_ids.ids).sorted('id')

    @api.model
    def _working_days_between(self, company, start, end):
        """Working days after `start` up to and including `end`, on the
        company's calendar week (Monday to Friday when it has none)."""
        if not start or not end or end <= start:
            return 0
        days = {0, 1, 2, 3, 4}
        calendar = company.sudo().resource_calendar_id
        if calendar and calendar.attendance_ids:
            days = {int(a.dayofweek) for a in calendar.attendance_ids} or days
        count, day = 0, start.date()
        stop = end.date()
        while day < stop:
            day += timedelta(days=1)
            if day.weekday() in days:
                count += 1
        return count

    # =====================================================================
    #  The request page (what the manager fills in)
    # =====================================================================
    def _page_questions(self):
        """The nine things a request answers, and whether each is answered."""
        self.ensure_one()
        rec = self.sudo()
        return [
            ('role', bool(rec.title and rec.department_id and rec.country_id)),
            ('why', bool(rec.role_type)),
            ('headcount', bool(rec.headcount and rec.headcount >= 1)),
            ('city', bool((rec.location or '').strip())),
            ('reports_to', bool(rec.reporting_manager_id)),
            ('level', bool((rec.pb_role_level or '').strip())),
            ('needs', bool((rec.requirements or '').strip() or rec.pb_jd_file)),
            ('budget', bool(rec.budget_cost and rec.budget_cost > 0)),
            ('close_by', bool(rec.pb_target_close_date)),
        ]

    def _missing_for_send_in(self):
        self.ensure_one()
        rec = self.sudo()
        names = []
        if not (rec.title or '').strip():
            names.append(_("the role's name"))
        if not rec.department_id:
            names.append(_('the department'))
        if not rec.country_id:
            names.append(_('the country'))
        if not rec.headcount or rec.headcount < 1:
            names.append(_('how many people'))
        if not rec.reporting_manager_id:
            names.append(_('who they would report to'))
        if not (rec.budget_cost and rec.budget_cost > 0):
            names.append(_('the expected budget'))
        if not rec.pb_target_close_date:
            names.append(_('the date you want the role filled by'))
        if not ((rec.requirements or '').strip() or rec.pb_jd_file):
            names.append(_('what the person needs to be able to do (or a '
                           'job description file)'))
        return names

    def _page_save(self, values):
        """Autosave from the manager's page: whitelisted fields only, typed
        at the door, no tracking noise (one summary at send-in)."""
        self.ensure_one()
        if self.request_state in SENT_STATES \
                and self.request_state != 'not_approved':
            raise UserError(_("This request has been sent in already."))
        rec = self.sudo()
        vals = {}
        for key, limit in PAGE_TEXT_LIMITS.items():
            if key in values:
                vals[key] = str(values.get(key) or '').strip()[:limit] or False
        if 'title' in vals and not vals['title']:
            vals.pop('title')
        if 'role_type' in values and values['role_type'] in dict(ROLE_TYPES):
            vals['role_type'] = values['role_type']
        if 'headcount' in values:
            try:
                vals['headcount'] = max(1, min(500, int(values['headcount'])))
            except (TypeError, ValueError):
                pass
        if 'department_id' in values:
            dept = self.env['hr.department'].sudo().browse(
                as_id(values['department_id'])).exists()
            if dept and dept.company_id in (rec.company_id, self.env[
                    'res.company']):
                vals['department_id'] = dept.id
        if 'country_id' in values:
            country = self.env['res.country'].sudo().browse(
                as_id(values['country_id'])).exists()
            if country:
                vals['country_id'] = country.id
        if 'reporting_manager_id' in values:
            emp = self.env['hr.employee'].sudo().browse(
                as_id(values['reporting_manager_id'])).exists()
            if emp and emp.company_id in (rec.company_id,
                                          self.env['res.company']):
                vals['reporting_manager_id'] = emp.id
            elif not values['reporting_manager_id']:
                vals['reporting_manager_id'] = False
        if 'budget_cost' in values:
            try:
                raw = str(values['budget_cost'] or '0').replace(',', '')
                vals['budget_cost'] = max(0.0, float(raw))
            except (TypeError, ValueError):
                pass
        if 'currency_id' in values:
            cur = self.env['res.currency'].sudo().browse(
                as_id(values['currency_id'])).exists()
            if cur and cur.active:
                vals['currency_id'] = cur.id
        if 'pb_target_close_date' in values:
            try:
                vals['pb_target_close_date'] = fields.Date.to_date(
                    values['pb_target_close_date'] or False) or False
            except (TypeError, ValueError):
                pass
        if 'is_confidential' in values:
            vals['is_confidential'] = str(values['is_confidential']).lower() \
                in ('1', 'true', 'on', 'yes')
        focus = {k: str(values[k] or '').strip()[:600]
                 for k in ('focus_1', 'focus_2', 'focus_3') if k in values}
        vals['request_saved_on'] = fields.Datetime.now()
        rec.with_context(tracking_disable=True, mail_notrack=True).write(vals)
        if focus:
            rec._save_focus(focus)
        if self.request_state == 'asked':
            self._request_write('writing')
        return True

    def _save_focus(self, focus):
        """What each discussion round should focus on, as the role's steps."""
        self.ensure_one()
        Step = self.env['pb.hiring.step'].sudo()
        Stage = self.env['hr.recruitment.stage']
        for key, value in focus.items():
            n = int(key[-1])
            name = 'Discussion %s' % n
            step = self.step_ids.filtered(lambda s: s.name == name)[:1]
            if step:
                step.write({'notes': value or False})
            elif value:
                Step.create({'requisition_id': self.id, 'name': name,
                             'sequence': n * 10, 'kind': 'interview',
                             'notes': value,
                             'stage_id': Stage._pb_stage(
                                 'discussion_%s' % n).id or False})
        return True

    def _page_focus(self):
        self.ensure_one()
        out = {}
        for n in (1, 2, 3):
            step = self.sudo().step_ids.filtered(
                lambda s, n=n: s.name == 'Discussion %s' % n)[:1]
            out['focus_%s' % n] = step.notes or ''
        return out

    # =====================================================================
    #  Sending it in, agreeing it, turning it down
    # =====================================================================
    def _request_send_in(self, by_employee=None):
        """The manager's "Send in" IS their agreement (RC-D5). Raises the
        sentence naming what is missing."""
        self.ensure_one()
        if self.state == 'closed':
            raise UserError(_("This role is closed, so its request cannot be "
                              "sent in."))
        if self.request_state in SENT_STATES \
                and self.request_state != 'not_approved':
            raise UserError(_("This request has been sent in already."))
        if not self.env.su and not self._may_send_in():
            raise AccessError(_(
                "Sending a request in is for the manager it was asked of, the "
                "person it is for, or the hiring team."))
        missing = self._missing_for_send_in()
        if missing:
            raise UserError(_("Before it can be sent in, add %s.",
                              self._join_words(missing)))
        rec = self.sudo()
        me = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        manager = by_employee or (
            me if me and me in (rec.asked_employee_id | rec.requested_by_id)
            else self.env['hr.employee'])
        rec.with_context(tracking_disable=True).write({
            'manager_agreed_on': fields.Datetime.now(),
            'manager_agreed_by_id': manager.id or False,
            'sent_in_by_id': self.env.uid,
            'requested_by_id': rec.requested_by_id.id or manager.id or False,
            'not_approved_reason': False,
        })
        self._refresh_budget(silent=True)
        if self._engine_managed():
            self.with_context(chain_note=_('Sent in')).action_approval_submit()
        else:
            self._request_write('sent_in')
            self._after_approval_transition('sent_in')
        # Paperwork, each in its own savepoint.
        self._leg('the recruiter on send-in', lambda: self._assign_recruiter(
            tell=True))
        self._leg('the sent-in email', self._tell_recruiter_sent_in)
        self._leg('the budget flag at send-in', self._flag_budget)
        self._log_role(self._send_in_summary(manager))
        return True

    @api.model
    def _join_words(self, words):
        words = [w for w in words if w]
        if len(words) <= 1:
            return ''.join(words)
        return _('%(first)s and %(last)s', first=', '.join(words[:-1]),
                 last=words[-1])

    def _send_in_summary(self, manager):
        self.ensure_one()
        rec = self.sudo()
        money = self._money(rec.budget_cost, rec.currency_id)
        if manager:
            head = _("%s sent the request in. Sending it in is their "
                     "agreement.", manager.name)
        else:
            head = _("%(by)s sent the request in for %(who)s.",
                     by=self.env.user.name,
                     who=rec.requested_by_id.name or rec.department_id.name
                     or '')
        return _("%(head)s %(n)s × %(title)s, expected %(money)s a year, "
                 "wanted by %(when)s.", head=head, n=rec.headcount or 1,
                 title=rec.title or '', money=money,
                 when=rec.pb_target_close_date or '')

    def _tell_recruiter_sent_in(self):
        self.ensure_one()
        user = self.recruiter_id
        if not user or user.id == self.env.uid or not flag(self.env,
                                                            P_NOTIFY_MAIL):
            return False
        return _mail(self, 'pb_hiring.mail_template_request_sent_in',
                     _email_of(user))

    def _request_agree(self, note=False):
        """Agree from the role's Details tab or the inbox (a seat holder), or
        — with no route published — the talent lead."""
        self.ensure_one()
        if self.request_state not in REQUEST_WITH_HR:
            raise UserError(_("There is nothing waiting to be agreed on this "
                              "request."))
        if self._engine_managed() and self._chain_open_request():
            self._chain_decide('approve', note)
            return True
        if not (self.env.su or self.env.user.has_group(GROUP_MANAGER)):
            raise AccessError(_("Agreeing a hiring request is for the Head of "
                                "HR or the talent lead."))
        self._request_write('agreed')
        self._after_approval_transition('agreed')
        return True

    def _request_decline(self, note=False):
        self.ensure_one()
        if self.request_state not in REQUEST_WITH_HR:
            raise UserError(_("There is nothing waiting to be decided on this "
                              "request."))
        note = (note or '').strip()
        if self._engine_managed() and self._chain_open_request():
            self._chain_decide('reject', note or _("Not approved"))
            return True
        if not (self.env.su or self.env.user.has_group(GROUP_MANAGER)):
            raise AccessError(_("Turning a hiring request down is for the "
                                "Head of HR or the talent lead."))
        self.sudo().write({'not_approved_reason': note or False})
        self._request_write('not_approved')
        self._after_approval_transition('not_approved')
        return True

    def _request_withdraw(self, reason):
        """The role closed: whatever is waiting in an inbox goes away."""
        self.ensure_one()
        request = self._chain_open_request()
        if request:
            self._leg('withdrawing the request of %s' % self.name,
                      lambda: self.env['biz.approval.engine'].sudo().cancel(
                          request.id, reason))
            self.invalidate_recordset(['approval_request_id',
                                       'approval_state'])
        if self.request_state in REQUEST_WITH_HR:
            self._request_write('writing')
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().with_context(tracking_disable=True).write(
            {'not_approved_reason': reason or False})
        return super()._approval_reject(request, reason)

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'agreed':
            self._leg('the request agreed notice', self._on_request_agreed)
        elif to_state == 'not_approved':
            self._leg('the not-approved notice', self._on_request_declined)
        elif to_state == 'hr_ok':
            self._log_role(_("The Head of HR agreed the request."))
        return res

    def _on_request_agreed(self):
        self.ensure_one()
        self.sudo().with_context(tracking_disable=True).write(
            {'agreed_on': fields.Datetime.now()})
        self._log_role(_("The request is agreed. An offer can be sent."))
        user = self.recruiter_id
        if user and flag(self.env, P_NOTIFY_MAIL):
            _mail(self, 'pb_hiring.mail_template_request_agreed',
                  _email_of(user))
        return True

    def _on_request_declined(self):
        self.ensure_one()
        self._log_role(_("The request was not approved. %s",
                         self.not_approved_reason or ''))
        user = self.recruiter_id
        if user:
            _todo(self, user, _('Request not approved: %s', self.title or ''),
                  self.not_approved_reason or _(
                      "Talk to the manager, change the request and send it "
                      "in again. The role itself carries on."))
        return True

    # =====================================================================
    #  Budget (G-15, R2)
    # =====================================================================
    def _read_budget(self):
        """The department's answer, then the confirmed figure's. With no
        expected figure yet there is nothing to compare: it says so, rather
        than "this role asks for 0 of it"."""
        status, remaining, currency, note = super()._read_budget()
        if not (self.budget_cost or 0.0) > 0:
            return 'unknown', remaining, currency, _(
                "No expected figure yet. The manager types it on the "
                "request, and it is compared with the budget then.")
        confirmed = self.budget_confirmed or 0.0
        if confirmed <= 0:
            return status, remaining, currency, note
        asked = self.budget_cost or 0.0
        cur = self.currency_id
        if asked > confirmed:
            extra = _("The expected %(asked)s is above the confirmed "
                      "%(conf)s by %(over)s.",
                      asked=self._money(asked, cur),
                      conf=self._money(confirmed, cur),
                      over=self._money(asked - confirmed, cur))
            if status == 'over':
                return 'over', remaining, currency, '%s %s' % (note, extra)
            return 'over', confirmed, cur, extra
        if status == 'over':
            return status, remaining, currency, note
        return 'within', confirmed, cur, _(
            "The expected %(asked)s is within the confirmed %(conf)s.",
            asked=self._money(asked, cur), conf=self._money(confirmed, cur))

    def _budget_people(self):
        return self.company_id.sudo().pb_budget_flag_user_ids.filtered(
            lambda u: u.active)

    def _flag_budget(self):
        """Over budget TELLS the budget-flag people, once per change of the
        figures. Nothing waits (R2)."""
        self.ensure_one()
        rec = self.sudo()
        if rec.budget_status != 'over':
            return False
        sig = '%s|%s|%s' % (rec.budget_cost or 0, rec.budget_confirmed or 0,
                            rec.currency_id.id or 0)
        if rec.budget_flag_sig == sig:
            return False
        rec.with_context(tracking_disable=True).write(
            {'budget_flag_sig': sig,
             'budget_flagged_on': fields.Datetime.now()})
        people = self._budget_people()
        summary = _('Over budget: %s', rec.title or '')
        if not people:
            self._log_role(_(
                "Over budget. Nobody is set to be told about over-budget "
                "requests, so the Head of hiring was given a to-do. Name the "
                "people in Hiring set-up → Who does what."))
            admins = self.env.ref(GROUP_ADMIN).sudo().all_user_ids.filtered(
                lambda u: u.active and not u.share
                and rec.company_id.id in u.company_ids.ids)
            for user in admins:
                _todo(self, user, summary, _(
                    "%(note)s Nobody is named to be told about over-budget "
                    "requests. Name them in Hiring set-up → Who does what.",
                    note=rec.budget_note or ''))
            return True
        for user in people:
            self._leg('the budget email to %s' % user.login,
                      lambda u=user: _mail(
                          self, 'pb_hiring.mail_template_budget_flag',
                          _email_of(u)))
            self._leg('the budget to-do for %s' % user.login,
                      lambda u=user: _todo(self, u, summary,
                                           rec.budget_note or ''))
        self._log_role(_("Over budget. %(who)s %(verb)s told. %(note)s",
                         who=', '.join(people.mapped('name')),
                         verb=counted(len(people), _('was'), _('were')),
                         note=rec.budget_note or ''))
        return True

    def _page_budget_note(self):
        """The one gentle sentence under the money on the manager's page."""
        self.ensure_one()
        rec = self.sudo()
        sent = rec.request_state in SENT_STATES
        if rec.budget_status == 'over' and rec.budget_cost:
            people = self._budget_people()
            who = ', '.join(people.mapped('name')) if people \
                else _('The hiring team')
            what = _("the confirmed budget") if rec.budget_confirmed \
                and rec.budget_cost > rec.budget_confirmed \
                else _("the department's budget")
            over = self._money(rec.budget_over_by, rec.budget_currency_id
                               or rec.currency_id)
            if sent:
                return 'over', _(
                    "This is above %(what)s by %(over)s. %(who)s %(verb)s "
                    "told. Nothing stops.", what=what, over=over, who=who,
                    verb=counted(len(people) or 1, _('was'), _('were')))
            return 'over', _(
                "This is above %(what)s by %(over)s. %(who)s will be told "
                "when you send it in. Nothing stops.", what=what, over=over,
                who=who)
        if rec.budget_status == 'within' and rec.budget_cost:
            return 'within', _("This fits within the budget.")
        return 'unknown', _(
            "No budget to compare with; the people who watch the budget will "
            "still see this figure.")

    # =====================================================================
    #  The one hard rule (RC-D5, G-43)
    # =====================================================================
    def _agree_holders_names(self):
        """Who presses Agree: the open seats now, else the Head of HR role's
        holders, else the words "the Head of HR"."""
        self.ensure_one()
        names = []
        try:
            step = self._chain_active_step()
            if step:
                names = sorted({s.acting_user_id.name for s in
                                step.sudo().seat_ids.filtered(
                                    lambda s: s.status == 'open')
                                if s.acting_user_id})
        except Exception:               # noqa: BLE001 — a name, never a crash
            _logger.warning('pb_hiring: could not read the seats of %s',
                            self.id, exc_info=True)
        if not names:
            role = self.env['biz.approval.role'].sudo().search(
                [('key', '=', 'hr_lead')], limit=1)
            if role:
                rows = self.env['biz.approval.responsibility'].sudo().search([
                    ('company_id', '=', self.company_id.id),
                    ('role_id', '=', role.id), ('active', '=', True)])
                names = sorted({r.user_id.name for r in rows if r.user_id})
        if not names:
            return _('the Head of HR')
        return self._join_words(names)

    def _offer_block_reason(self):
        """'' when an offer may be sent, else the sentence with the fix."""
        self.ensure_one()
        rec = self.sudo()
        state = rec.request_state
        if state == 'agreed':
            return ''
        if state in REQUEST_WITH_HR:
            return _("The request for this role is not agreed yet. Ask "
                     "%s to press Agree.", self._agree_holders_names())
        if state in REQUEST_WAITING and rec.asked_employee_id:
            return _("The request for this role is not agreed yet: it is "
                     "still with %s to fill in and send. Remind them from the "
                     "role's Details tab.", rec.asked_employee_id.name)
        if state == 'writing':
            return _("The request for this role is not agreed yet: it has "
                     "not been sent in. Finish it on the role's Details tab.")
        if state == 'not_approved':
            return _("The request for this role was not approved, so the "
                     "offer cannot be sent. Change the request and send it "
                     "in again.")
        return _("This role has no agreed hiring request, so the offer "
                 "cannot be sent. Ask the manager for one on the role's "
                 "Details tab.")

    # =====================================================================
    #  What the board shows about the request
    # =====================================================================
    def _request_chip(self):
        self.ensure_one()
        rec = self.sudo()
        state = rec.request_state
        who = rec.asked_employee_id.name or ''
        if state == 'none':
            return _('No request yet'), 'amber'
        if state in REQUEST_WAITING and who:
            return _('Waiting on %s', who), 'amber'
        if state == 'writing':
            return _('Request being written'), 'amber'
        if state == 'sent_in':
            return _('Sent in'), 'info'
        if state == 'hr_ok':
            return _('Head of HR agreed'), 'info'
        if state == 'agreed':
            return _('Request agreed'), 'green'
        return _('Not approved'), 'rose'

    def _ago(self, stamp):
        if not stamp:
            return ''
        days = (fields.Datetime.now() - stamp).days
        if days <= 0:
            return _('today')
        if days == 1:
            return _('yesterday')
        return _('%s days ago', days)

    def _reminded_line(self):
        """"reminded 2 days ago" or "asked yesterday"."""
        self.ensure_one()
        rec = self.sudo()
        if rec.request_state not in REQUEST_WAITING or not rec.asked_on:
            return ''
        if rec.last_reminded_on:
            return _('reminded %s', self._ago(rec.last_reminded_on))
        return _('asked %s', self._ago(rec.asked_on))

    def _request_facts(self):
        """The small set every row carries (home card, role header)."""
        self.ensure_one()
        rec = self.sudo()
        label, tone = self._request_chip()
        block = self._offer_block_reason()
        return {
            'request_state': rec.request_state,
            'request_label': label,
            'request_tone': tone,
            'asked_name': rec.asked_employee_id.name or '',
            'reminded_ago': self._reminded_line(),
            'remind_every': rec.remind_every_days or 2,
            'budget_flag': (rec.budget_note or '') if rec.budget_status == 'over'
            else '',
            'is_confidential': bool(rec.is_confidential),
            'offer_block_reason': block,
            'can_send_offer': not block,
            'advert_stale': bool(rec.advert_stale),
        }


# =========================================================================
#  The offer, the background check and the papers (G-39, G-40, G-43)
# =========================================================================
class HiringOfferP3(models.Model):
    _inherit = 'pb.hiring.offer'

    @api.model
    def draft_for(self, requisition_id, values=None):
        offer = super().draft_for(requisition_id, values)
        leg(self.env, 'the papers before the offer',
            lambda: offer._docreq_fire('before_offer'))
        bgv = offer.bgv_id
        if bgv and bgv.check_ready()[0]:
            leg(self.env, 'the papers on a clear check',
                lambda: offer._docreq_fire('on_check_clear'))
        return offer

    def _docreq_fire(self, moment):
        """Ask for the papers at the moment the company chose. Never a gate,
        never twice."""
        self.ensure_one()
        if text(self.env, P_DOCREQ_TRIGGER, 'on_check_clear') != moment:
            return False
        if self.state in ('closed', 'declined', 'refused'):
            return False
        if self.docreq_id and self.docreq_id.sent_on:
            return False
        if not self.candidate_email:
            return False
        self.action_request_documents()
        return True

    def record_decision(self, decision, comment=None):
        res = super().record_decision(decision, comment=comment)
        if decision == 'accepted':
            leg(self.env, 'the papers on acceptance',
                lambda: self._docreq_fire('on_accept'))
        return res


class HiringBgvP3(models.Model):
    _inherit = 'pb.hiring.bgv'

    def _live_offer(self):
        self.ensure_one()
        return self.env['pb.hiring.offer'].sudo().search([
            ('requisition_id', '=', self.requisition_id.id),
            ('applicant_id', '=', self.applicant_id.id),
            ('state', 'not in', ('declined', 'refused', 'closed'))],
            order='id desc', limit=1)

    def _after_answer(self):
        self.ensure_one()
        if self.check_ready()[0]:
            offer = self._live_offer()
            if offer:
                leg(self.env, 'the papers on a clear check',
                    lambda: offer._docreq_fire('on_check_clear'))
        return True

    def action_override(self, note=None):
        res = super().action_override(note=note)
        for rec in self:
            rec._after_answer()
        return res

    def _flag_adverse(self, item):
        """An adverse result tells the Head of HR — once per line. It gates
        nothing (G-39)."""
        self.ensure_one()
        if item.adverse_told_on:
            return False
        item.sudo().write({'adverse_told_on': fields.Datetime.now()})
        req = self.requisition_id.sudo()
        people = self._hr_lead_users()
        summary = _('Background check: %(what)s came back for %(who)s',
                    what=item.name or '', who=self.candidate_name or '')
        note = item.note or _("Read the line on the role's Offer & joining "
                              "tab. Nothing is blocked; it is your call.")
        for user in people:
            leg(self.env, 'the adverse to-do for %s' % user.login,
                lambda u=user: _todo(req, u, summary, note))
            leg(self.env, 'the adverse email to %s' % user.login,
                lambda u=user: _mail(self,
                                     'pb_hiring.mail_template_bgv_adverse',
                                     _email_of(u), {'pb_item': item.name}))
        req._log_role(summary)
        return True

    def _hr_lead_users(self):
        """The Head of HR role's holders for the company, else the talent
        leads."""
        company = self.company_id or self.requisition_id.company_id
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', 'hr_lead')], limit=1)
        users = self.env['res.users']
        if role:
            rows = self.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', company.id), ('role_id', '=', role.id),
                ('active', '=', True)])
            users = rows.mapped('user_id').filtered(lambda u: u.active)
        if not users:
            users = self.requisition_id._talent_leads()
        return users


class HiringBgvItemP3(models.Model):
    _inherit = 'pb.hiring.bgv.item'

    adverse_told_on = fields.Datetime(string='Head of HR told on',
                                      readonly=True, copy=False)

    def action_set(self, result, note=None):
        res = super().action_set(result, note=note)
        if result == 'flag':
            leg(self.env, 'the adverse flag on %s' % self.id,
                lambda: self.bgv_id._flag_adverse(self))
        leg(self.env, 'after the check answer',
            lambda: self.bgv_id._after_answer())
        return res


class HiringDocreqP3(models.Model):
    _inherit = 'pb.hiring.docreq'

    escalated_on = fields.Datetime(string='Talent lead told on',
                                   readonly=True, copy=False)

    def _escalate(self):
        """Two working days and still missing: the talent lead hears."""
        self.ensure_one()
        if self.escalated_on:
            return False
        req = self.requisition_id
        summary = _('Papers still missing: %s', self.candidate_name or '')
        note = _("%(who)s was asked for their papers and the window has "
                 "passed. The recruiter has a to-do too.",
                 who=self.candidate_name or '')
        for user in req._talent_leads():
            leg(self.env, 'the papers escalation to %s' % user.login,
                lambda u=user: _todo(self, u, summary, note))
            leg(self.env, 'the papers escalation email to %s' % user.login,
                lambda u=user: _mail(
                    self, 'pb_hiring.mail_template_docreq_escalated',
                    _email_of(u)))
        self.sudo().write({'escalated_on': fields.Datetime.now()})
        return True


# =========================================================================
#  The jobs lists and the referral door respect Confidential
# =========================================================================
class HiringApplicantP3(models.Model):
    _inherit = 'hr.applicant'

    @api.model
    def pb_open_jobs(self, company_ids=None):
        rows = super().pb_open_jobs(company_ids=company_ids)
        hidden = set(self.env['pb.hiring.requisition'].sudo().search(
            [('is_confidential', '=', True), ('job_id', '!=', False)]
        ).mapped('job_id').ids)
        return [r for r in rows if r['id'] not in hidden]


class HiringReferralP3(models.Model):
    _inherit = 'pb.hiring.referral'

    @api.model
    def refer(self, requisition_id, employee_id, values):
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(requisition_id)).exists()
        if req and req.is_confidential:
            raise UserError(_('This role is not open to referrals.'))
        return super().refer(requisition_id, employee_id, values)


class HiringJobP3(models.Model):
    _inherit = 'hr.job'

    def pb_hiring_accepts_applications(self, website):
        if not super().pb_hiring_accepts_applications(website):
            return False
        req = self.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', self.sudo().id)], order='id desc', limit=1)
        return not (req and req.is_confidential)


# =========================================================================
#  The daily step
# =========================================================================
class HiringAutomationP3(models.AbstractModel):
    _inherit = 'pb.hiring.automation'

    @api.model
    def run_now(self):
        counts = super().run_now()
        for key, fn in (('request_reminders', self._remind_requests),
                        ('request_escalated', self._escalate_requests),
                        ('doc_escalated', self._escalate_documents)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — a job never raises
                _logger.warning('pb_hiring: the %s step failed', key,
                                exc_info=True)
                counts[key] = 0
        return counts

    @api.model
    def describe(self, counts):
        base = super().describe(counts)
        parts = []
        rem = counts.get('request_reminders', 0)
        if rem:
            parts.append(_("%(n)s %(word)s reminded about a hiring request.",
                           n=rem, word=counted(rem, _('manager was'),
                                               _('managers were'))))
        esc = counts.get('request_escalated', 0)
        if esc:
            parts.append(_("%(n)s %(word)s passed to the talent lead.", n=esc,
                           word=counted(esc, _('unfinished request was'),
                                        _('unfinished requests were'))))
        if not parts:
            return base
        if base == _("Nothing needed chasing today."):
            return ' '.join(parts)
        return base + ' ' + ' '.join(parts)

    @api.model
    def _waiting_requests(self):
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        return self.env['pb.hiring.requisition'].sudo().search([
            ('request_state', 'in', REQUEST_WAITING),
            ('asked_on', '!=', False), ('asked_employee_id', '!=', False),
            ('state', '!=', 'closed')], order='asked_on', limit=cap)

    @api.model
    def _remind_requests(self):
        """On each request's own cadence, in working days (G-13)."""
        now = fields.Datetime.now()
        Req = self.env['pb.hiring.requisition']
        made = 0
        for req in self._waiting_requests():
            since = req.last_reminded_on or req.asked_on
            due = Req._working_days_between(req.company_id, since, now)
            if due < max(1, req.remind_every_days or 2):
                continue
            if leg(self.env, 'the request reminder on %s' % req.id,
                   req._remind) is not False:
                made += 1
        return made

    @api.model
    def _escalate_requests(self):
        days = max(1, number(self.env, P_ASK_ESCALATE_DAYS, 3))
        now = fields.Datetime.now()
        Req = self.env['pb.hiring.requisition']
        made = 0
        for req in self._waiting_requests():
            if req.escalated_on:
                continue
            if Req._working_days_between(req.company_id, req.asked_on,
                                         now) < days:
                continue
            if leg(self.env, 'the request escalation on %s' % req.id,
                   req._escalate):
                made += 1
        return made

    @api.model
    def _escalate_documents(self):
        today = fields.Date.context_today(self)
        cap = max(1, number(self.env, P_REMINDER_CAP, 400))
        rows = self.env['pb.hiring.docreq'].sudo().search([
            ('deadline', '!=', False), ('deadline', '<', today),
            ('escalated_on', '=', False), ('state', '!=', 'complete'),
            ('offer_id.state', 'not in', ('closed', 'declined', 'refused')),
        ], order='deadline', limit=cap)
        made = 0
        for row in rows:
            if leg(self.env, 'the papers escalation on %s' % row.id,
                   row._escalate):
                made += 1
        return made

    @api.model
    def _nudge_adverts(self):
        """RECRUIT P3: an advert still a draft after N days on a live role
        with none in use — the talent lead gets the nudge (G-17)."""
        from .hiring_common import P_JD_REMINDER_DAYS
        days = max(1, number(self.env, P_JD_REMINDER_DAYS, 3))
        cutoff = fields.Datetime.now() - timedelta(days=days)
        rows = self.env['pb.hiring.jd'].sudo().search([
            ('state', '=', 'draft'), ('create_date', '<=', cutoff),
            ('requisition_id.state', 'in', ('setup', 'open')),
            ('requisition_id.jd_current_id', '=', False)])
        made = 0
        for jd in rows:
            req = jd.requisition_id
            leads = req._talent_leads()
            if not leads:
                continue
            if leg(self.env, 'the advert nudge on %s' % jd.id,
                   lambda jd=jd, u=leads[0]: _todo(
                       jd, u, _('Finish the advert: %s', jd.title or ''),
                       _("This advert has been a draft for %(n)s %(word)s "
                         "and the role has none in use. Make it final, or "
                         "ask the recruiter.", n=days,
                         word=counted(days, _('day'), _('days'))))):
                made += 1
        return made


# =========================================================================
#  Seeds
# =========================================================================
def seed_p3(env):
    """JD templates per company (four, three languages). Idempotent."""
    from .jd_templates_seed import JD_TEMPLATES
    Tpl = env['pb.hiring.jd.template'].sudo().with_context(
        active_test=False, lang='en_US')
    langs = set(env['res.lang'].sudo().search(
        [('active', '=', True)]).mapped('code'))
    made = 0
    for company in env['res.company'].sudo().search([]):
        for index, row in enumerate(JD_TEMPLATES):
            existing = Tpl.search([('company_id', '=', company.id),
                                   ('seed_key', '=', row['key'])], limit=1)
            if existing:
                continue
            tpl = Tpl.create({'name': row['name']['en_US'],
                              'family': row['family'],
                              'body': row['body']['en_US'],
                              'sequence': (index + 1) * 10,
                              'company_id': company.id,
                              'seed_key': row['key']})
            body_field = tpl._fields['body']
            en_terms = body_field.get_trans_terms(row['body']['en_US']) \
                if callable(body_field.translate) else None
            for lang in ('vi_VN', 'id_ID'):
                if lang not in langs:
                    continue
                tpl.update_field_translations(
                    'name', {lang: row['name'][lang]})
                if en_terms is None:
                    tpl.update_field_translations(
                        'body', {lang: row['body'][lang]})
                    continue
                # Term-based (html) translation: pair the terms in order.
                # The three bodies are built by the same `_body()`, so the
                # terms line up one to one; if they ever do not, English
                # stays rather than a scrambled advert.
                lang_terms = body_field.get_trans_terms(row['body'][lang])
                if len(lang_terms) == len(en_terms):
                    tpl.update_field_translations(
                        'body', {lang: dict(zip(en_terms, lang_terms))})
            made += 1
    return made
