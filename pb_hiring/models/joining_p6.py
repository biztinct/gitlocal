# -*- coding: utf-8 -*-
"""RECRUIT P6 — from signed to joined (G-42, G-44, G-55, G-56, G-57, G-58).

RULING R8, IN ONE SENTENCE: a signed offer keeps the person a CANDIDATE in
Post-offer with an expected joining date, and nothing on the employee side
exists until somebody presses "Confirm they joined".

WHAT THIS FILE ADDS, in the order a recruiter meets it:

  * **Signed** (`action_record_signed`, extended): the copy becomes the first
    of several signed documents (`pb.hiring.offer.document`, a kind each,
    the country's expected set as a hint), the candidate moves to Post-offer,
    the expected date is the offer's start date, the company's "Before they
    join" list is laid out, and the hiring manager and the talent lead are
    told. No employee, contract, login, checklist or vault row.
  * **Before they join** (`pb.hiring.prejoin`): a buddy named by the manager
    from their own link, laptop preferences from the new joiner's own link
    (in the language they applied in), meet-the-team chats (a diary entry
    through the one helper interviews use, `.ics` mails, a Meet link when the
    organiser has connected Google) and free to-dos. Each item has an owner,
    a due date relative to the joining date, and one button.
  * **The joining date**: the recruiter's to change until they start; every
    change is a `pb.hiring.join.change` row on the timeline and the hiring
    manager and HR are told. A week before, one email to the recruiter, the
    manager and HR with three answers on a page (`pb.hiring.join.ask`).
  * **Confirm they joined** (`offer_closure.action_confirm_joined`) and
    **Did not join** (`action_did_not_join`: an offer drop with its reason,
    the headcount not filled, the chats called off).
  * **A declined offer** now lands the candidate in Offer drop too, so the
    numbers can count it (G-58).
"""

import base64
import json
import logging
import secrets
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date

from odoo.addons.pb_lifecycle.models.ics import build_ics

from .hiring_common import (
    COUNTRY_DOC_SETS, DEFAULT_DOC_SET, DROP_REASONS, GROUP_MANAGER,
    JOIN_STATUS, OFFER_DOC_KINDS, P_CANDIDATE_MAIL, P_CLOSURE_MAIL,
    P_NOTIFY_MAIL, P_REMINDERS, P_WEEK_BEFORE_DAYS, PREJOIN_KINDS, PREJOIN_OWNERS,
    PREJOIN_STATES, UPLOAD_MAX_BYTES, UPLOAD_MIME_OK, as_id, counted, flag,
    leg, number, slug_filename,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'

#: The company's starting "Before they join" list (the talent lead edits it in
#: Hiring set-up). `{manager}` and `{name}` are filled in per offer.
DEFAULT_PREJOIN = [
    (10, 'buddy', 'Ask {manager} to name a buddy', 'manager', -10),
    (20, 'laptop', 'Ask {name} for their laptop preferences', 'candidate', -10),
    (30, 'chat', 'Set up a meet-the-team chat', 'recruiter', -5),
    (40, 'todo', 'Send the first-day details', 'recruiter', -2),
]

#: What the laptop page asks, in its order. The words on the page are
#: translated in the controller (`joining_pages.py`); these keys are the
#: stored answer.
LAPTOP_KINDS = ('mac', 'windows', 'any')
LAPTOP_KEYBOARDS = ('us', 'uk', 'vi', 'id', 'other')
LAPTOP_SCREENS = ('small', 'large', 'any')
LAPTOP_EXTRAS = ('mouse', 'headset', 'monitor', 'stand')

#: Never more buddies than a manager can sensibly ask of a team.
MAX_BUDDIES = 5
_MAX_TEXT = 2000


def _token():
    return secrets.token_urlsafe(24)


def _words(env, day, fmt='EEE d MMM'):
    """A date as a person reads it ("Mon 3 Nov")."""
    if not day:
        return ''
    try:
        return format_date(env, day, date_format=fmt)
    except Exception:                   # noqa: BLE001 — never fail a sentence
        return str(day)


def _laptop_lines(prefs):
    """The laptop answers as English lines for the people who prepare the
    machine (IT and HR read English; the candidate answered in theirs)."""
    if not prefs:
        return []
    kinds = {'mac': 'Mac', 'windows': 'Windows', 'any': 'No preference'}
    boards = {'us': 'English (US)', 'uk': 'English (UK)',
              'vi': 'Vietnamese', 'id': 'Indonesian', 'other': 'Other'}
    screens = {'small': '13 to 14 inch', 'large': '15 to 16 inch',
               'any': 'No preference'}
    extras = {'mouse': 'a mouse', 'headset': 'a headset',
              'monitor': 'a second screen', 'stand': 'a laptop stand'}
    out = []
    if prefs.get('kind'):
        out.append(('Laptop', kinds.get(prefs['kind'], prefs['kind'])))
    if prefs.get('keyboard'):
        out.append(('Keyboard', boards.get(prefs['keyboard'], prefs['keyboard'])))
    if prefs.get('screen'):
        out.append(('Screen', screens.get(prefs['screen'], prefs['screen'])))
    picked = [extras[e] for e in prefs.get('extras') or [] if e in extras]
    if picked:
        out.append(('Also', ', '.join(picked)))
    if (prefs.get('note') or '').strip():
        out.append(('Anything else', prefs['note'].strip()))
    return out


# =========================================================================
#  Signed documents (G-42)
# =========================================================================
class PbHiringOfferDocument(models.Model):
    """One signed document on an offer. Several per candidate: Vietnam signs
    the offer and a probation letter later, India and Indonesia the offer and
    an employment agreement. All of them are filed to the vault on join."""
    _name = 'pb.hiring.offer.document'
    _description = 'Signed document on an offer'
    _order = 'sequence, id'

    offer_id = fields.Many2one('pb.hiring.offer', string='Offer', required=True,
                               index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    kind = fields.Selection(OFFER_DOC_KINDS, string='What it is', required=True,
                            default='offer_letter')
    label = fields.Char(string='Name on screen')
    attachment_id = fields.Many2one('ir.attachment', string='The file',
                                    required=True, ondelete='cascade')
    signed_on = fields.Date(string='Signed on')
    recorded_by_id = fields.Many2one('res.users', string='Recorded by')
    vault_doc_id = fields.Many2one('pb.employee.document', string='Filed as',
                                   ondelete='set null', copy=False)
    company_id = fields.Many2one(related='offer_id.company_id', store=True,
                                 index=True, readonly=True)

    def _compute_display_name(self):
        kinds = dict(OFFER_DOC_KINDS)
        for rec in self:
            rec.display_name = rec.label or kinds.get(rec.kind, '')

    def _vault_name(self):
        """The name it is filed under. The offer letter keeps the wave-2
        name ("Signed offer OF-2026-0106"), so a joiner filed by the old
        closure is found rather than filed twice."""
        self.ensure_one()
        ref = self.offer_id.name or ''
        if self.kind == 'offer_letter':
            return _('Signed offer %(ref)s', ref=ref)
        what = self.label or dict(OFFER_DOC_KINDS).get(self.kind, '')
        return _('%(what)s %(ref)s', what=what, ref=ref)


# =========================================================================
#  Before they join — the company's list, and the items on one offer
# =========================================================================
class PbHiringPrejoinTemplate(models.Model):
    """The company's "Before they join" list, laid out on every signed offer.
    The talent lead edits it in Hiring set-up."""
    _name = 'pb.hiring.prejoin.template'
    _description = 'Before they join: the company list'
    _order = 'sequence, id'

    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda self: self.env.company)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(PREJOIN_KINDS, required=True, default='todo')
    title = fields.Char(required=True,
                        help='{manager} and {name} are filled in per person.')
    owner = fields.Selection(PREJOIN_OWNERS, required=True, default='recruiter')
    due_offset_days = fields.Integer(
        string='Days before joining', default=-5,
        help='Negative is before the joining date; 0 is the day itself.')
    active = fields.Boolean(default=True)

    @api.model
    def _ensure_defaults(self):
        """The starting list, once per company. Idempotent: a company that
        has a list (even an emptied one) keeps it."""
        Tpl = self.sudo().with_context(active_test=False)
        made = 0
        for company in self.env['res.company'].sudo().search([]):
            if Tpl.search_count([('company_id', '=', company.id)]):
                continue
            Tpl.create([{'company_id': company.id, 'sequence': seq, 'kind': kind,
                         'title': title, 'owner': owner, 'due_offset_days': days}
                        for seq, kind, title, owner, days in DEFAULT_PREJOIN])
            made += 1
        return made

    def _payload(self):
        self.ensure_one()
        return {'id': self.id, 'kind': self.kind, 'title': self.title or '',
                'owner': self.owner, 'days': self.due_offset_days,
                'sequence': self.sequence}


class PbHiringPrejoin(models.Model):
    """One thing to do before a new joiner's first day."""
    _name = 'pb.hiring.prejoin'
    _description = 'Before they join'
    _order = 'sequence, id'

    offer_id = fields.Many2one('pb.hiring.offer', string='Offer', required=True,
                               index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    kind = fields.Selection(PREJOIN_KINDS, required=True, default='todo')
    title = fields.Char(required=True)
    owner = fields.Selection(PREJOIN_OWNERS, required=True, default='recruiter')
    due_offset_days = fields.Integer(default=-5)
    due_date = fields.Date(compute='_compute_due', store=True, readonly=True)
    state = fields.Selection(PREJOIN_STATES, required=True, default='open',
                             index=True)
    done_on = fields.Datetime(readonly=True, copy=False)
    answered_by = fields.Char(string='Who answered', readonly=True, copy=False)
    answer_json = fields.Text(readonly=True, copy=False)
    note = fields.Text()
    # NO FIELD-LEVEL `groups=` ON A TOKEN (R13); it never reaches a payload.
    token = fields.Char(index=True, copy=False, readonly=True)
    sent_at = fields.Datetime(string='Asked on', readonly=True, copy=False)
    reminded_at = fields.Datetime(readonly=True, copy=False)
    chased_at = fields.Datetime(readonly=True, copy=False)
    # ---- meet-the-team chats
    event_id = fields.Many2one('calendar.event', string='Diary entry',
                               ondelete='set null', copy=False)
    chat_start = fields.Datetime(string='When')
    chat_minutes = fields.Integer(string='How long', default=30)
    chat_mode = fields.Selection([('video', 'On a video call'),
                                  ('in_person', 'In person')],
                                 default='video')
    chat_where = fields.Char(string='Where, or the video link')
    chat_people_ids = fields.Many2many(
        'hr.employee', 'pb_hiring_prejoin_people_rel', 'prejoin_id',
        'employee_id', string='Who they meet')
    videocall_url = fields.Char(readonly=True, copy=False)
    invites_pending = fields.Boolean(readonly=True, copy=False)
    invites_sent_at = fields.Datetime(readonly=True, copy=False)

    company_id = fields.Many2one(related='offer_id.company_id', store=True,
                                 index=True, readonly=True)
    applicant_id = fields.Many2one(related='offer_id.applicant_id', store=True,
                                   index=True, readonly=True)
    # Public fields for the mail templates (RC49).
    pb_link_url = fields.Char(compute='_compute_mail_words')
    pb_due_words = fields.Char(compute='_compute_mail_words')
    pb_join_words = fields.Char(compute='_compute_mail_words')
    pb_answer_words = fields.Text(compute='_compute_mail_words')
    pb_when_words = fields.Char(compute='_compute_mail_words')

    _token_uniq = models.Constraint('unique(token)',
                                    'Two links cannot share the same key.')

    @api.depends('offer_id.expected_join_date', 'offer_id.start_date',
                 'due_offset_days')
    def _compute_due(self):
        for rec in self:
            anchor = rec.offer_id.expected_join_date or rec.offer_id.start_date
            rec.due_date = (anchor + timedelta(days=rec.due_offset_days or 0)) \
                if anchor else False

    def _compute_mail_words(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').rstrip('/')
        for rec in self:
            path = {'buddy': 'b', 'laptop': 'l'}.get(rec.kind)
            rec.pb_link_url = '%s/hiring/%s/%s' % (base, path, rec.sudo().token) \
                if (path and rec.sudo().token) else ''
            rec.pb_due_words = _words(rec.env, rec.due_date, 'EEEE d MMMM')
            rec.pb_join_words = _words(
                rec.env, rec.offer_id.expected_join_date or rec.offer_id.start_date,
                'EEEE d MMMM y')
            rec.pb_answer_words = rec._answer_text()
            rec.pb_when_words = rec._chat_when_words()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('kind') in ('buddy', 'laptop') and not vals.get('token'):
                vals['token'] = _token()
        return super().create(vals_list)

    # ------------------------------------------------------------- reading
    def _answer(self):
        self.ensure_one()
        try:
            return json.loads(self.answer_json or '{}') or {}
        except (TypeError, ValueError):
            return {}

    def _answer_text(self):
        """What was answered, in one or two plain English lines."""
        self.ensure_one()
        ans = self._answer()
        if self.kind == 'buddy':
            names = ans.get('names') or []
            if not names:
                return ''
            text = _('%(who)s named %(names)s as buddy.',
                     who=self.answered_by or _('The manager'),
                     names=', '.join(names))
            if ans.get('why'):
                text += ' ' + _('Why: %s', ans['why'])
            return text
        if self.kind == 'laptop':
            lines = _laptop_lines(ans)
            return '\n'.join('%s: %s' % (k, v) for k, v in lines)
        if self.kind == 'chat' and self.chat_start:
            return self._chat_when_words()
        return self.note or ''

    def _chat_when_words(self):
        self.ensure_one()
        if not self.chat_start:
            return ''
        tz = self._tz()
        local = fields.Datetime.context_timestamp(self.with_context(tz=tz),
                                                  self.chat_start)
        return '%s, %s' % (_words(self.env, local.date(), 'EEEE d MMMM'),
                           local.strftime('%H:%M'))

    def _tz(self):
        self.ensure_one()
        user = self.offer_id.requisition_id.sudo().recruiter_id
        return (user.tz if user else '') or self.env.user.tz or 'UTC'

    def is_late(self):
        self.ensure_one()
        return bool(self.state == 'open' and self.due_date
                    and self.due_date < fields.Date.context_today(self))

    @api.model
    def _request_for_token(self, token, kind):
        """`(record, status)` — `invalid`, `closed` (the person joined, did not
        join, or the item was called off), `used` (answered) or `ok`."""
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        row = self.sudo().search([('token', '=', token), ('kind', '=', kind)],
                                 limit=1)
        if not row:
            return blank, 'invalid'
        if row.state in ('cancelled', 'skipped') or row.offer_id.state != 'signed':
            return row, 'closed'
        if row.state == 'done':
            return row, 'used'
        return row, 'ok'

    def page_facts(self):
        """What the buddy and laptop pages show — and nothing else."""
        self.ensure_one()
        offer = self.offer_id.sudo()
        req = offer.requisition_id
        manager = offer._person(offer.reporting_manager_id or req.reporting_manager_id)
        recruiter = req.recruiter_id
        return {
            'candidate': offer.candidate_name or '',
            'role': offer.job_title or req.title or '',
            'company': offer.company_id._hiring_brand()
            if hasattr(offer.company_id, '_hiring_brand') else offer.company_id.name,
            'department': req.department_id.name or '',
            'join_date': offer.expected_join_date or offer.start_date,
            'manager': manager.name or '',
            'recruiter': recruiter.name or '',
            'recruiter_email': recruiter.email or '',
            'answer': self._answer(),
            'answered_by': self.answered_by or '',
            'done_on': self.done_on,
        }

    # ------------------------------------------------------------- sending
    def _manager_address(self):
        self.ensure_one()
        offer = self.offer_id.sudo()
        manager = offer._person(offer.reporting_manager_id
                                or offer.requisition_id.reporting_manager_id)
        return ((manager.user_id.email if manager else '') or
                (manager.work_email if manager else '') or '').strip(), manager

    def action_send(self):
        """Send the ask: the manager's buddy email, or the new joiner's laptop
        email in the language they applied in. Returns a sentence."""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_("This one is already done."))
        if self.offer_id.state != 'signed':
            raise UserError(_("This only applies while they are waiting to join."))
        if self.kind == 'buddy':
            address, manager = self._manager_address()
            if not address:
                raise UserError(_(
                    "There is no email address for the hiring manager, so the "
                    "buddy question cannot go. Add one on their employee record, "
                    "or mark this done once they tell you."))
            template = self.env.ref('pb_hiring.mail_template_prejoin_buddy',
                                    raise_if_not_found=False)
            if not template:
                raise UserError(_("The buddy email is not in this build."))
            template.sudo().send_mail(self.id, force_send=False, email_values={
                'email_to': address, 'auto_delete': False})
            first = self.sent_at is False or not self.sent_at
            self.sudo().write({'sent_at': fields.Datetime.now()} if first
                              else {'reminded_at': fields.Datetime.now()})
            self._log(_("Asked %s to name a buddy.", manager.name or address))
            return _("%s has the buddy question, with their own link.",
                     manager.name or address)
        if self.kind == 'laptop':
            status = self._send_laptop_mail()
            if status == 'no_email':
                raise UserError(_("There is no email address for them, so the "
                                  "laptop question cannot go."))
            if status == 'mail_off':
                raise UserError(_(
                    "Candidate emails are switched off in Hiring set-up, so "
                    "nothing was sent. Copy their link and send it yourself."))
            if status != 'sent':
                raise UserError(_(
                    "The laptop email is not set up for this company yet. Look "
                    "in Hiring set-up → Emails and languages."))
            name = self.offer_id.candidate_name or ''
            self._log(_("Asked %s for their laptop preferences.", name))
            return _("%s has the laptop question, in the language they applied in.",
                     name)
        raise UserError(_("This kind of item has nothing to send."))

    def _send_laptop_mail(self):
        """The candidate email, from the company's own "Before you join: your
        laptop" template in the language they applied in (the P5 "Let's chat"
        pattern)."""
        self.ensure_one()
        offer = self.offer_id.sudo()
        app = offer.applicant_id.sudo()
        if not offer.candidate_email:
            return 'no_email'
        if not flag(self.env, P_CANDIDATE_MAIL):
            return 'mail_off'
        template = self.env['pb.hiring.message.template'].sudo().search([
            ('company_id', '=', offer.company_id.id), ('key', '=', 'laptop')],
            limit=1)
        if not template:
            return 'no_template'
        from .forms_p2 import _raw
        lang = app.pb_lang or 'en_US'
        if lang != 'en_US':
            raw = _raw(template, 'body').get(template.id) or {}
            if not (raw.get(lang) or '').strip():
                lang = 'en_US'
        recruiter = offer.requisition_id.recruiter_id or self.env.user
        join = offer.expected_join_date or offer.start_date
        values = {'laptop_link': self.pb_link_url,
                  'join_date': _words(self.with_context(lang=lang).env, join,
                                      'EEEE d MMMM'),
                  'hr_name': recruiter.name or '', 'sender_name': recruiter.name or ''}
        try:
            rendered = template.with_context(lang=lang)._render(app, values)
        except UserError:
            _logger.info('pb_hiring: the laptop email for offer %s is missing a '
                         'detail', offer.id, exc_info=True)
            return 'no_template'
        from .journey import text_html
        self.env['mail.mail'].sudo().create({
            'subject': rendered['subject'], 'body_html': text_html(rendered['body']),
            'email_to': offer.candidate_email,
            'email_from': self.env['pb.hiring']._sender(offer.company_id),
            'reply_to': recruiter.email_formatted or False,
            'model': 'hr.applicant', 'res_id': app.id, 'auto_delete': False})
        app.message_post(subject=rendered['subject'], body=text_html(rendered['body']),
                         message_type='comment', subtype_xmlid='mail.mt_note')
        first = not self.sent_at
        self.sudo().write({'sent_at': fields.Datetime.now()} if first
                          else {'reminded_at': fields.Datetime.now()})
        return 'sent'

    def _log(self, text):
        """One line on the candidate's timeline (a note on the applicant)."""
        self.ensure_one()
        app = self.offer_id.applicant_id.sudo()
        if app:
            app.message_post(body=Markup('<p>%s</p>') % text,
                             message_type='comment', subtype_xmlid='mail.mt_note')

    # ------------------------------------------------------------ answering
    def _finish(self, by_name=None, note=None, answer=None):
        self.ensure_one()
        vals = {'state': 'done', 'done_on': fields.Datetime.now(),
                'answered_by': by_name or self.env.user.name or ''}
        if note is not None:
            vals['note'] = note
        if answer is not None:
            vals['answer_json'] = json.dumps(answer, default=str)
        self.sudo().write(vals)
        return True

    def submit_buddy(self, employee_ids, why='', by_name=None):
        """The manager's answer from their link: one or more buddies."""
        self.ensure_one()
        if self.kind != 'buddy':
            raise UserError(_("This link is not for naming a buddy."))
        ids = [as_id(i) for i in (employee_ids or []) if as_id(i)]
        ids = list(dict.fromkeys(ids))[:MAX_BUDDIES]
        if not ids:
            raise UserError(_("Choose at least one person."))
        offer = self.offer_id.sudo()
        people = self.env['hr.employee'].sudo().browse(ids).exists().filtered(
            lambda e: e.company_id == offer.company_id and e.active)
        if not people:
            raise UserError(_("Choose people who work here."))
        # Keep the manager's order: the first named is the buddy on day one.
        order = {eid: n for n, eid in enumerate(ids)}
        people = people.sorted(lambda e: order.get(e.id, 99))
        why = (why or '').strip()[:_MAX_TEXT]
        _addr, manager = self._manager_address()
        who = by_name or manager.name or _('The manager')
        offer.write({'buddy_employee_ids': [(6, 0, people.ids)]})
        self._finish(by_name=who, note=why or None,
                     answer={'ids': people.ids, 'names': people.mapped('name'),
                             'why': why})
        self._log(_("%(who)s named %(names)s as buddy.", who=who,
                    names=', '.join(people.mapped('name'))))
        leg(self.env, 'telling the recruiter about the buddy on %s' % self.id,
            self._tell_recruiter_answered)
        return people

    def submit_laptop(self, values):
        """The new joiner's answer from their link."""
        self.ensure_one()
        if self.kind != 'laptop':
            raise UserError(_("This link is not for laptop preferences."))
        values = values or {}
        prefs = {
            'kind': values.get('kind') if values.get('kind') in LAPTOP_KINDS else '',
            'keyboard': values.get('keyboard')
            if values.get('keyboard') in LAPTOP_KEYBOARDS else '',
            'screen': values.get('screen') if values.get('screen') in LAPTOP_SCREENS else '',
            'extras': [e for e in (values.get('extras') or []) if e in LAPTOP_EXTRAS],
            'note': (values.get('note') or '').strip()[:_MAX_TEXT],
        }
        if not prefs['kind']:
            raise UserError(_("Choose Mac, Windows or no preference."))
        offer = self.offer_id.sudo()
        offer.write({'laptop_prefs_json': json.dumps(prefs)})
        self._finish(by_name=offer.candidate_name or '', answer=prefs)
        self._log(_("%s sent their laptop preferences.", offer.candidate_name or ''))
        leg(self.env, 'telling the recruiter about the laptop on %s' % self.id,
            self._tell_recruiter_answered)
        return prefs

    def _tell_recruiter_answered(self):
        """One short email to the recruiter: the list ticked itself."""
        self.ensure_one()
        if not flag(self.env, P_NOTIFY_MAIL):
            return False
        recruiter = self.offer_id.requisition_id.sudo().recruiter_id
        if not recruiter or not recruiter.email:
            return False
        template = self.env.ref('pb_hiring.mail_template_prejoin_answered',
                                raise_if_not_found=False)
        if not template:
            return False
        template.sudo().send_mail(self.id, force_send=False, email_values={
            'email_to': recruiter.email, 'auto_delete': False})
        return True

    def action_done(self, note=None):
        for rec in self:
            if rec.state == 'done':
                continue
            rec._finish(note=note)
        return True

    def action_skip(self):
        self.sudo().write({'state': 'skipped', 'done_on': fields.Datetime.now(),
                           'answered_by': self.env.user.name or ''})
        return True

    def action_reopen(self):
        self.sudo().write({'state': 'open', 'done_on': False, 'answered_by': False})
        return True

    # --------------------------------------------------------------- chats
    def schedule_chat(self, values):
        """A meet-the-team chat: a diary entry through the shared helper,
        `.ics` mails to the new joiner and the people they meet.

        `values`: {start (UTC 'YYYY-MM-DD HH:MM:SS'), minutes, mode, where,
        people_ids}."""
        self.ensure_one()
        if self.kind != 'chat':
            raise UserError(_("Only a meet-the-team chat goes in the diary."))
        if self.offer_id.state != 'signed':
            raise UserError(_("Chats are set up while they are waiting to join."))
        start = fields.Datetime.to_datetime(values.get('start'))
        if not start:
            raise UserError(_("Say when the chat is."))
        if start < fields.Datetime.now() - timedelta(minutes=5):
            raise UserError(_("That time has already gone. Pick a time ahead."))
        people = self.env['hr.employee'].sudo().browse(
            [as_id(i) for i in values.get('people_ids') or [] if as_id(i)]).exists()
        if not people:
            raise UserError(_("Say who they will meet."))
        minutes = max(10, min(240, int(values.get('minutes') or 30)))
        mode = values.get('mode') if values.get('mode') in ('video', 'in_person') \
            else 'video'
        where = (values.get('where') or '').strip()[:500]
        self.sudo().write({
            'chat_start': start, 'chat_minutes': minutes, 'chat_mode': mode,
            'chat_where': where, 'chat_people_ids': [(6, 0, people.ids)],
            'videocall_url': where if (mode == 'video' and where.lower().startswith(
                ('https://', 'http://'))) else False,
        })
        if self.event_id:
            self.event_id._pb_quiet_write({'active': False})
            self.sudo().write({'event_id': False})
        event = self._make_chat_event()
        waits = bool(event and self._google_meet() and not self.videocall_url)
        self.sudo().write({'invites_pending': waits,
                           'title': _('Meet the team: %s',
                                      ', '.join(people.mapped('name')))
                           if self.title in (_('Set up a meet-the-team chat'),
                                             'Set up a meet-the-team chat')
                           else self.title})
        sent = 0 if waits else self._send_chat_invites()
        self._log(_("Meet-the-team chat set for %(when)s with %(who)s.",
                    when=self._chat_when_words(), who=', '.join(people.mapped('name'))))
        return {'sent': sent, 'waits': waits}

    def _organiser(self):
        self.ensure_one()
        return self.offer_id.requisition_id.sudo().recruiter_id or self.env.user

    def _google_meet(self):
        self.ensure_one()
        return bool(self.chat_mode == 'video' and not self.chat_where
                    and self.env['pb.hiring.interview']._pb_google_connected(
                        self._organiser()))

    def _make_chat_event(self):
        """THROUGH THE SHARED HELPER (`calendar.event._pb_quiet_create`), the
        one every interview entry is made through too."""
        self.ensure_one()
        organiser = self._organiser()
        partners = self.env['res.partner'].sudo().browse()
        for emp in self.chat_people_ids.sudo():
            if emp.user_id and emp.user_id.partner_id:
                partners |= emp.user_id.partner_id
        if organiser.partner_id:
            partners |= organiser.partner_id
        google = self.env['pb.hiring.interview']._pb_google_connected(organiser)
        app = self.offer_id.applicant_id.sudo()
        if google and app.partner_id:
            partners |= app.partner_id
        meet = self._google_meet()
        vals = {
            'name': self._chat_title(),
            'start': self.chat_start,
            'stop': self.chat_start + timedelta(minutes=self.chat_minutes or 30),
            'allday': False,
            'duration': (self.chat_minutes or 30) / 60.0,
            'location': '' if meet else (self.chat_where or ''),
            'description': self._chat_agenda(),
            'partner_ids': [(6, 0, partners.ids)],
            'user_id': organiser.id,
            'pb_prejoin_id': self.id,
        }
        if self.videocall_url:
            vals['videocall_location'] = self.videocall_url
        event = self.env['calendar.event']._pb_quiet_create(vals)
        self.sudo().write({'event_id': event.id})
        return event

    def _chat_title(self):
        self.ensure_one()
        return _('Meet the team: %(who)s — %(role)s',
                 who=self.offer_id.candidate_name or '',
                 role=self.offer_id.job_title or '')

    def _chat_agenda(self):
        self.ensure_one()
        offer = self.offer_id
        return _("A first hello before %(who)s starts as %(role)s on %(when)s. "
                 "Nothing to prepare: tell them about the team and what their "
                 "first weeks look like.",
                 who=offer.candidate_name or '', role=offer.job_title or '',
                 when=_words(self.env, offer.expected_join_date or offer.start_date,
                             'EEEE d MMMM'))

    def _join_link(self):
        self.ensure_one()
        if self.videocall_url:
            return self.videocall_url
        return self.chat_where if self.chat_mode == 'video' else ''

    def _ics(self):
        self.ensure_one()
        organiser = (self._organiser().email or '').strip() or None
        attendees = [e.work_email for e in self.chat_people_ids.sudo() if e.work_email]
        if self.offer_id.candidate_email:
            attendees.append(self.offer_id.candidate_email)
        link = self._join_link()
        description = self._chat_agenda()
        if link:
            description = _("Video link: %s", link) + '\n\n' + description
        return build_ics(
            summary=self._chat_title(), dt_start=self.chat_start,
            dt_end=self.chat_start + timedelta(minutes=self.chat_minutes or 30),
            organizer=organiser, attendees=attendees, description=description,
            location=link or self.chat_where or '',
            uid='pbhiring-chat-%s@payobook' % self.id)

    def _send_chat_invites(self):
        """One mail per person, each with the calendar file (R6)."""
        self.ensure_one()
        template = self.env.ref('pb_hiring.mail_template_prejoin_chat',
                                raise_if_not_found=False)
        if not template:
            return 0
        addresses = []
        if flag(self.env, P_CANDIDATE_MAIL) and self.offer_id.candidate_email:
            addresses.append(self.offer_id.candidate_email)
        for emp in self.chat_people_ids.sudo():
            addr = (emp.work_email or (emp.user_id.email if emp.user_id else '') or '').strip()
            if addr:
                addresses.append(addr)
        recruiter = self._organiser()
        if recruiter.email:
            addresses.append(recruiter.email)
        sent = 0
        for addr in dict.fromkeys(addresses):
            att = self.env['ir.attachment'].sudo().create({
                'name': 'meet-the-team.ics', 'datas': base64.b64encode(self._ics()),
                'mimetype': 'text/calendar', 'res_model': 'pb.hiring.prejoin',
                'res_id': self.id})
            template.sudo().send_mail(self.id, force_send=False, email_values={
                'email_to': addr, 'auto_delete': False,
                'attachment_ids': [(6, 0, att.ids)]})
            sent += 1
        self.sudo().write({'invites_pending': False,
                           'invites_sent_at': fields.Datetime.now()})
        return sent

    def _pb_meet_arrived(self, url):
        """Google answered with a Meet link for a chat: on the item, and the
        invitations that waited for it go out with it in."""
        self.ensure_one()
        if not url:
            return False
        rec = self.sudo()
        if not rec.videocall_url:
            rec.write({'videocall_url': url})
        if rec.invites_pending and rec.state == 'open':
            rec._send_chat_invites()
        return True

    def _cancel(self):
        """Called off with the person (Did not join): the item and its diary
        entry, quietly."""
        for rec in self.sudo():
            if rec.event_id:
                rec.event_id._pb_quiet_write({'active': False})
            if rec.state == 'open':
                rec.write({'state': 'cancelled'})
        return True


# =========================================================================
#  The joining date: every change, and the week-before ask
# =========================================================================
class PbHiringJoinChange(models.Model):
    """One change to an expected joining date — who, when, why."""
    _name = 'pb.hiring.join.change'
    _description = 'A change to the joining date'
    _order = 'id desc'

    offer_id = fields.Many2one('pb.hiring.offer', required=True, index=True,
                               ondelete='cascade')
    old_date = fields.Date()
    new_date = fields.Date()
    reason = fields.Text()
    by_name = fields.Char(string='Changed by')
    source = fields.Selection([('drawer', 'On the hiring board'),
                               ('email', 'From the week-before email')],
                              default='drawer')
    company_id = fields.Many2one(related='offer_id.company_id', store=True,
                                 index=True, readonly=True)


class PbHiringJoinAsk(models.Model):
    """The week-before email, one row per person asked, each with their own
    link — so the answer says WHO answered."""
    _name = 'pb.hiring.join.ask'
    _description = 'Still joining? — the week-before ask'
    _order = 'id desc'

    offer_id = fields.Many2one('pb.hiring.offer', required=True, index=True,
                               ondelete='cascade')
    name = fields.Char(string='Asked')
    email = fields.Char()
    role = fields.Selection([('recruiter', 'Recruiter'), ('manager', 'Hiring manager'),
                             ('hr', 'HR')])
    token = fields.Char(index=True, copy=False, readonly=True)
    round_date = fields.Date(string='For the date',
                             help='The joining date this ask was about.')
    sent_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one(related='offer_id.company_id', store=True,
                                 index=True, readonly=True)
    pb_link_url = fields.Char(compute='_compute_link')
    pb_join_words = fields.Char(compute='_compute_link')

    _token_uniq = models.Constraint('unique(token)',
                                    'Two links cannot share the same key.')

    def _compute_link(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').rstrip('/')
        for rec in self:
            rec.pb_link_url = '%s/hiring/w/%s' % (base, rec.sudo().token or '')
            rec.pb_join_words = _words(rec.env, rec.round_date, 'EEEE d MMMM')

    @api.model
    def _request_for_token(self, token):
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        row = self.sudo().search([('token', '=', token)], limit=1)
        if not row:
            return blank, 'invalid'
        offer = row.offer_id
        if offer.state != 'signed':
            return row, 'closed'
        if offer.week_answered_at and offer.week_answered_at >= row.sent_at:
            return row, 'used'
        return row, 'ok'


# =========================================================================
#  The offer: signed, the date, joined, did not join
# =========================================================================
class HiringOfferJoining(models.Model):
    _inherit = 'pb.hiring.offer'

    expected_join_date = fields.Date(string='Expected to join on', tracking=True,
                                     copy=False)
    joined_on = fields.Date(string='Started on', readonly=True, copy=False)
    join_status = fields.Selection(JOIN_STATUS, string='Joining', copy=False,
                                   readonly=True)
    join_date_reason = fields.Char(string='Why the date moved', readonly=True,
                                   copy=False)
    document_ids = fields.One2many('pb.hiring.offer.document', 'offer_id',
                                   string='Signed documents')
    prejoin_ids = fields.One2many('pb.hiring.prejoin', 'offer_id',
                                  string='Before they join')
    join_change_ids = fields.One2many('pb.hiring.join.change', 'offer_id',
                                      string='Joining date changes')
    join_ask_ids = fields.One2many('pb.hiring.join.ask', 'offer_id',
                                   string='Week-before asks')
    buddy_employee_ids = fields.Many2many(
        'hr.employee', 'pb_hiring_offer_buddy_rel', 'offer_id', 'employee_id',
        string='Buddies the manager named', copy=False)
    laptop_prefs_json = fields.Text(string='Laptop preferences', copy=False)
    week_before_sent_at = fields.Datetime(readonly=True, copy=False)
    week_answer = fields.Selection([('still_on', 'Still on'),
                                    ('changed', 'The date changed'),
                                    ('dropped', 'They will not join')],
                                   readonly=True, copy=False)
    week_answered_by = fields.Char(readonly=True, copy=False)
    week_answered_at = fields.Datetime(readonly=True, copy=False)
    drop_reason = fields.Selection(DROP_REASONS, string='Why they did not join',
                                   readonly=True, copy=False)
    drop_note = fields.Text(readonly=True, copy=False)
    dropped_on = fields.Date(readonly=True, copy=False)
    # Public fields for the mail templates (RC49).
    pb_join_words = fields.Char(compute='_compute_join_words')
    pb_old_join_words = fields.Char(compute='_compute_join_words')
    pb_drop_words = fields.Char(compute='_compute_join_words')
    pb_board_url = fields.Char(compute='_compute_join_words')

    def _compute_join_words(self):
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '').rstrip('/')
        reasons = dict(DROP_REASONS)
        for rec in self:
            rec.pb_join_words = _words(
                rec.env, rec.joined_on if rec.state == 'joined'
                else (rec.expected_join_date or rec.start_date), 'EEEE d MMMM y')
            last = rec.join_change_ids[:1]
            rec.pb_old_join_words = _words(rec.env, last.old_date, 'EEEE d MMMM') \
                if last else ''
            rec.pb_drop_words = ' — '.join(x for x in (
                reasons.get(rec.drop_reason, ''), rec.drop_note or '') if x)
            rec.pb_board_url = '%s/bizapp/action-pb_hiring.action_pb_hiring_board' % base

    # -------------------------------------------------------------- helpers
    def _talent_leads(self):
        self.ensure_one()
        return self.requisition_id.sudo()._talent_leads()

    def _hr_lead_users(self):
        """The Head of HR seat for the company, else the talent leads. Never a
        portal login (a demo seat can be one, RC45)."""
        self.ensure_one()
        company = self.company_id
        users = self.env['res.users']
        role = self.env['biz.approval.role'].sudo().search(
            [('key', '=', 'hr_lead')], limit=1) \
            if 'biz.approval.role' in self.env else False
        if role:
            rows = self.env['biz.approval.responsibility'].sudo().search([
                ('company_id', '=', company.id), ('role_id', '=', role.id),
                ('active', '=', True)])
            users = rows.mapped('user_id').filtered(
                lambda u: u.active and not u.share)
        return users or self._talent_leads()

    def _manager(self):
        self.ensure_one()
        return self._person(self.reporting_manager_id
                            or self.requisition_id.reporting_manager_id)

    def _manager_email(self):
        self.ensure_one()
        manager = self._manager()
        return ((manager.user_id.email if manager else '') or
                (manager.work_email if manager else '') or '').strip()

    def _addresses(self, *who):
        """Unique addresses for the named groups: 'manager', 'talent',
        'hr', 'recruiter'."""
        self.ensure_one()
        out = []
        for key in who:
            if key == 'manager':
                out.append(self._manager_email())
            elif key == 'talent':
                out += [u.email for u in self._talent_leads()]
            elif key == 'hr':
                out += [u.email for u in self._hr_lead_users()]
            elif key == 'recruiter':
                out.append(self.requisition_id.sudo().recruiter_id.email or '')
        return [a.strip() for a in dict.fromkeys(out) if a and a.strip()]

    def _mail_many(self, xmlid, addresses, switch=P_NOTIFY_MAIL):
        self.ensure_one()
        if switch and not flag(self.env, switch):
            return 0
        sent = 0
        for address in addresses:
            if leg(self.env, 'mail %s to %s' % (xmlid, address),
                   lambda a=address: self._mail(xmlid, a)):
                sent += 1
        return sent

    def _log_candidate(self, text):
        self.ensure_one()
        app = self.applicant_id.sudo()
        if app:
            app.message_post(body=Markup('<p>%s</p>') % text,
                             message_type='comment', subtype_xmlid='mail.mt_note')

    def _laptop_prefs(self):
        self.ensure_one()
        try:
            return json.loads(self.laptop_prefs_json or '{}') or {}
        except (TypeError, ValueError):
            return {}

    def _doc_set(self):
        """The documents this market usually signs, each with whether it is
        on the offer yet (a hint, never a gate)."""
        self.ensure_one()
        req = self.requisition_id.sudo()
        country = req.country_id or self.company_id.country_id
        code = (country.code or '').upper()
        rows = COUNTRY_DOC_SETS.get(code, DEFAULT_DOC_SET)
        have = set(self.document_ids.mapped('kind'))
        kinds = dict(OFFER_DOC_KINDS)
        return {'country': country.name or '', 'code': code,
                'rows': [{'kind': k, 'label': kinds.get(k, k), 'when': when,
                          'have': k in have} for k, when in rows]}

    # --------------------------------------------------------- signed
    def action_record_signed(self, filename=None, content=None, mimetype=None,
                             signed_on=None, kind=None, label=None):
        res = super().action_record_signed(filename=filename, content=content,
                                           mimetype=mimetype, signed_on=signed_on)
        self._on_signed(kind=kind, label=label)
        return res

    def _on_signed(self, kind=None, label=None, quiet=False):
        """Signed: the document row, the expected date, Post-offer, the list,
        and who is told. NOTHING on the employee side (R8)."""
        self.ensure_one()
        att = self.signed_attachment_id
        Doc = self.env['pb.hiring.offer.document'].sudo()
        if att and not Doc.search_count([('offer_id', '=', self.id),
                                          ('attachment_id', '=', att.id)]):
            Doc.create({'offer_id': self.id, 'attachment_id': att.id,
                        'kind': kind if kind in dict(OFFER_DOC_KINDS) else 'offer_letter',
                        'label': (label or '').strip()[:120] or False,
                        'signed_on': self.signed_on,
                        'recorded_by_id': self.signed_by_id.id or self.env.uid})
        vals = {}
        if not self.expected_join_date:
            vals['expected_join_date'] = self.start_date
        if not self.join_status:
            vals['join_status'] = 'pending'
        if vals:
            self.sudo().write(vals)
        leg(self.env, 'Post-offer for offer %s' % self.name, self._move_to_post_offer)
        leg(self.env, 'the Before they join list on offer %s' % self.name,
            self._lay_out_prejoin)
        if not quiet:
            leg(self.env, 'telling them %s signed' % self.name,
                lambda: self._mail_many('pb_hiring.mail_template_offer_signed',
                                        self._addresses('manager', 'talent')))
            self._log_candidate(_("Signed the offer. Joining on %s.",
                                  _words(self.env, self.expected_join_date,
                                         'EEE d MMM y')))
        return True

    def _move_to_post_offer(self):
        self.ensure_one()
        stage = self.env['hr.recruitment.stage']._pb_stage('post_offer')
        app = self.applicant_id.sudo()
        if stage and app and app.stage_id != stage and app.stage_id.pb_key != 'joined':
            vals = {'stage_id': stage.id}
            if not app.active:
                vals.update({'active': True, 'refuse_reason_id': False})
            app.with_context(just_moved=True).write(vals)
        return True

    def _lay_out_prejoin(self):
        """The company's list, once per offer."""
        self.ensure_one()
        if self.prejoin_ids:
            return self.prejoin_ids
        Tpl = self.env['pb.hiring.prejoin.template'].sudo()
        tpls = Tpl.search([('company_id', '=', self.company_id.id)])
        if not tpls and not Tpl.with_context(active_test=False).search_count(
                [('company_id', '=', self.company_id.id)]):
            Tpl._ensure_defaults()
            tpls = Tpl.search([('company_id', '=', self.company_id.id)])
        manager = self._manager()
        short = (manager.name or _('the hiring manager')) if manager else _('the hiring manager')
        name = self.candidate_name or _('them')
        rows = []
        for tpl in tpls:
            title = (tpl.title or '').replace('{manager}', short).replace('{name}', name)
            rows.append({'offer_id': self.id, 'sequence': tpl.sequence,
                         'kind': tpl.kind, 'title': title, 'owner': tpl.owner,
                         'due_offset_days': tpl.due_offset_days})
        return self.env['pb.hiring.prejoin'].sudo().create(rows)

    # ------------------------------------------------- the joining date
    def action_change_join_date(self, new_date, reason=None, source='drawer',
                                by_name=None):
        """The recruiter's to change until they start (R8). Recorded, told,
        and the week-before email re-arms when the new date is more than a
        week away."""
        self.ensure_one()
        if self.state != 'signed':
            raise UserError(_("The joining date can change until they start. "
                              "This offer is “%s”.",
                              dict(self._fields['state'].selection).get(self.state, '')))
        new = fields.Date.to_date(new_date) if new_date else False
        if not new:
            raise UserError(_("Pick the new joining date."))
        old = self.expected_join_date or self.start_date
        if new == old:
            raise UserError(_("That is the date they already have."))
        reason = (reason or '').strip()[:_MAX_TEXT]
        who = by_name or self.env.user.name or ''
        self.env['pb.hiring.join.change'].sudo().create({
            'offer_id': self.id, 'old_date': old, 'new_date': new,
            'reason': reason or False, 'by_name': who, 'source': source})
        vals = {'expected_join_date': new, 'join_status': 'changed',
                'join_date_reason': reason or False}
        days = number(self.env, P_WEEK_BEFORE_DAYS, 7)
        if new > fields.Date.context_today(self) + timedelta(days=days):
            vals.update({'week_before_sent_at': False, 'week_answer': False,
                         'week_answered_by': False, 'week_answered_at': False})
        self.sudo().write(vals)
        # the items' due dates are a stored compute on the date: they move.
        self._log_candidate(_("Joining date moved from %(old)s to %(new)s%(why)s.",
                              old=_words(self.env, old, 'EEE d MMM'),
                              new=_words(self.env, new, 'EEE d MMM y'),
                              why=(' — ' + reason) if reason else ''))
        self._mail_many('pb_hiring.mail_template_join_date_changed',
                        self._addresses('manager', 'hr'))
        return True

    # ---------------------------------------------------- did not join
    def action_did_not_join(self, reason=None, note=None, source='drawer',
                            by_name=None):
        """An offer drop with its reason (G-58): the candidate to Offer drop,
        the items and chats called off, the headcount not filled, and the
        hiring manager, the talent lead and HR told."""
        self.ensure_one()
        if self.state == 'dropped':
            return True
        if self.state != 'signed':
            raise UserError(_("“Did not join” is for a signed offer. This one is "
                              "“%s”.",
                              dict(self._fields['state'].selection).get(self.state, '')))
        reason = reason if reason in dict(DROP_REASONS) else 'other'
        note = (note or '').strip()[:_MAX_TEXT]
        self.sudo().write({'state': 'dropped', 'join_status': 'dropped',
                           'drop_reason': reason, 'drop_note': note or False,
                           'dropped_on': fields.Date.context_today(self)})
        leg(self.env, 'the candidate on offer %s' % self.name,
            lambda: self._drop_candidate(
                'pb_hiring.refuse_reason_did_not_join',
                ' — '.join(x for x in (dict(DROP_REASONS)[reason], note) if x)))
        leg(self.env, 'calling off the list on offer %s' % self.name,
            lambda: self.prejoin_ids._cancel())
        who = by_name or self.env.user.name or ''
        self.sudo().message_post(body=_(
            "%(who)s will not join (%(why)s). Recorded by %(by)s.",
            who=self.candidate_name or '', why=dict(DROP_REASONS)[reason], by=who))
        self._mail_many('pb_hiring.mail_template_did_not_join',
                        self._addresses('manager', 'talent', 'hr'))
        return True

    def _drop_candidate(self, reason_xmlid, words):
        """Offer drop, with the seeded reason and the words; archived like
        every other outcome (moving them back reactivates them)."""
        self.ensure_one()
        stage = self.env['hr.recruitment.stage']._pb_stage('offer_drop_out')
        app = self.applicant_id.sudo()
        if not stage or not app:
            return False
        reason = self.env.ref(reason_xmlid, raise_if_not_found=False)
        vals = {'stage_id': stage.id, 'pb_stage_reason': words or False}
        if reason:
            vals['refuse_reason_id'] = reason.id
        app.with_context(just_moved=True).write(vals)
        if app.active:
            app.with_context(just_moved=True, pb_no_stage_log=True).write(
                {'active': False})
        return True

    # ------------------------------------------- a declined offer (G-58)
    def record_decision(self, decision, comment=None):
        res = super().record_decision(decision, comment=comment)
        if res and decision == 'declined':
            leg(self.env, 'Offer drop on offer %s' % self.name,
                lambda: self._drop_candidate(
                    'pb_hiring.refuse_reason_declined_offer',
                    (comment or '').strip() or _('Declined the offer')))
        return res

    # ------------------------------------------------ the week before
    def _week_before_send(self):
        """One email to the recruiter, the hiring manager and HR, each with
        their own link to three answers."""
        self.ensure_one()
        if self.state != 'signed' or self.week_before_sent_at:
            return 0
        req = self.requisition_id.sudo()
        people = []
        if req.recruiter_id and req.recruiter_id.email:
            people.append(('recruiter', req.recruiter_id.name, req.recruiter_id.email))
        manager = self._manager()
        if self._manager_email():
            people.append(('manager', manager.name, self._manager_email()))
        for user in self._hr_lead_users():
            if user.email:
                people.append(('hr', user.name, user.email))
        seen, rows = set(), []
        now = fields.Datetime.now()
        for role, name, email in people:
            key = email.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            rows.append({'offer_id': self.id, 'role': role, 'name': name,
                         'email': email.strip(), 'token': _token(),
                         'round_date': self.expected_join_date, 'sent_at': now})
        asks = self.env['pb.hiring.join.ask'].sudo().create(rows)
        template = self.env.ref('pb_hiring.mail_template_join_week',
                                raise_if_not_found=False)
        sent = 0
        if template and flag(self.env, P_NOTIFY_MAIL):
            for ask in asks:
                if leg(self.env, 'the week-before mail to %s' % ask.email,
                       lambda a=ask: template.sudo().send_mail(
                           a.id, force_send=False,
                           email_values={'email_to': a.email, 'auto_delete': False})):
                    sent += 1
        self.sudo().write({'week_before_sent_at': now, 'week_answer': False,
                           'week_answered_by': False, 'week_answered_at': False})
        self._log_candidate(_("The week-before email went to %s.",
                              ', '.join(a.name or a.email for a in asks) or _('nobody')))
        return sent

    def answer_week(self, ask, answer, new_date=None, reason=None, drop_reason=None):
        """An answer from the week-before page."""
        self.ensure_one()
        who = ask.name or ask.email or ''
        if answer == 'still_on':
            self._log_candidate(_("Still joining on %(when)s — confirmed by %(who)s.",
                                  when=_words(self.env, self.expected_join_date, 'EEE d MMM'),
                                  who=who))
        elif answer == 'changed':
            self.action_change_join_date(new_date, reason=reason, source='email',
                                         by_name=who)
        elif answer == 'dropped':
            self.action_did_not_join(reason=drop_reason, note=reason,
                                     source='email', by_name=who)
        else:
            raise UserError(_("Choose one of the three answers."))
        if self.state == 'signed' or answer == 'dropped':
            self.sudo().write({'week_answer': answer, 'week_answered_by': who,
                               'week_answered_at': fields.Datetime.now()})
        return True

    # ------------------------------------------------ handing over on join
    def _hand_over_buddy(self):
        """The first buddy the manager named becomes the buddy on day one,
        and the onboarding "Choose their buddy" step ticks. Skipped cleanly
        where the onboarding module is not installed."""
        self.ensure_one()
        self = self.sudo()              # the recruiter pressing has no read on employees
        employee = self.employee_id.sudo()
        buddies = self.buddy_employee_ids.sudo()
        if not employee or not buddies:
            return 'nothing'
        if not self._onboarding_ready(employee):
            _logger.info('pb_hiring: onboarding is not installed; the buddy on '
                         'offer %s stays on the offer', self.name)
            self.sudo().message_post(body=_(
                "%s was named as buddy. The onboarding module is not installed "
                "here, so it stays on this offer.", ', '.join(buddies.mapped('name'))))
            return 'skipped'
        first = buddies[0]
        if first == employee:
            return 'nothing'
        nomination = self.env['pb.buddy.nomination'].sudo().open_for(
            employee.id, self.case_id.id or None)
        try:
            with self.env.cr.savepoint():
                nomination.choose(first.id)
        except Exception:               # noqa: BLE001 — the eligibility rule refused
            _logger.info('pb_hiring: the onboarding rule refused %s as buddy on '
                         'offer %s; set directly', first.name, self.name,
                         exc_info=True)
            employee.write({'buddy_id': first.id})
            nomination._tick_step()
        if self.case_id and len(buddies) > 1:
            self.case_id.sudo().message_post(body=_(
                "The hiring manager named %(names)s as buddies before %(who)s "
                "joined; %(first)s is the buddy on day one.",
                names=', '.join(buddies.mapped('name')), who=employee.name or '',
                first=first.name or ''))
        return 'done'

    def _onboarding_ready(self, employee):
        """Is the onboarding module here (the buddy field and the
        nomination that ticks its step)? pb_hiring does not depend on it."""
        return 'buddy_id' in employee._fields and 'pb.buddy.nomination' in self.env

    def _hand_over_laptop(self):
        """Laptop preferences reach the people who prepare the machine: the
        laptop step's note and the equipment request's justification."""
        self.ensure_one()
        self = self.sudo()
        lines = _laptop_lines(self._laptop_prefs())
        if not lines or not self.case_id:
            return False
        text = _("Laptop preferences from %s:", self.candidate_name or '') + '\n' + \
            '\n'.join('%s: %s' % (k, v) for k, v in lines)
        case = self.case_id.sudo()
        steps = case.task_ids.filtered(lambda t: getattr(t, 'automation_key', '') == 'asset_laptop')
        for step in steps:
            step.write({'note': ((step.note + '\n\n') if step.note else '') + text})
        if 'pb.asset.request' in self.env and steps:
            requests = self.env['pb.asset.request'].sudo().search(
                [('journey_task_id', 'in', steps.ids)])
            for request in requests:
                if 'justification' in request._fields:
                    request.write({'justification': ((request.justification + '\n\n')
                                                     if request.justification else '') + text})
        if not steps:
            case.message_post(body=Markup('<p>%s</p>') % text)
        return True


# =========================================================================
#  The applicant: a dropped offer's reasons are kept on it
# =========================================================================
class HiringApplicantJoining(models.Model):
    _inherit = 'hr.applicant'

    def _pb_retention_protected(self):
        """P4's rule, plus: somebody whose offer says they STARTED is hired
        whatever column their card was dragged to later (after the P6 split
        the stage alone no longer proves it)."""
        res = super()._pb_retention_protected()
        if res:
            return res
        if self.env['pb.hiring.offer'].sudo().search_count([
                ('applicant_id', '=', self.id), ('state', '=', 'joined')]):
            return 'hired'
        return res


class HiringMessageTemplateLaptop(models.Model):
    """The new joiner's laptop email is a company email like "Let's chat":
    editable in Candidate emails, one text per language (P5 pattern)."""
    _inherit = 'pb.hiring.message.template'

    key = fields.Selection(selection_add=[('laptop', 'Before you join: your laptop')],
                           ondelete={'laptop': 'cascade'})


# =========================================================================
#  The daily step and the ten-minute step
# =========================================================================
class HiringAutomationJoining(models.AbstractModel):
    _inherit = 'pb.hiring.automation'

    @api.model
    def run_now(self):
        counts = super().run_now()
        for key, fn in (('week_before', self._week_before_join),
                        ('prejoin', self._prejoin_reminders)):
            try:
                counts[key] = fn()
            except Exception:           # noqa: BLE001 — a job never raises
                _logger.warning('pb_hiring: the %s step failed', key, exc_info=True)
                counts[key] = 0
        return counts

    @api.model
    def describe(self, counts):
        text = super().describe(counts)
        parts = []
        n = (counts or {}).get('week_before') or 0
        if n:
            parts.append(_("%(n)s week-before %(word)s sent.", n=n,
                           word=counted(n, _('email was'), _('emails were'))))
        m = (counts or {}).get('prejoin') or 0
        if m:
            parts.append(_("%(n)s Before they join %(word)s nudged.", n=m,
                           word=counted(m, _('item was'), _('items were'))))
        return ' '.join([text] + parts) if parts else text

    @api.model
    def _week_before_join(self):
        """Offers signed with a joining date inside the next week and no
        week-before email yet — at seven days, and at once for a date set
        inside the window later."""
        today = fields.Date.context_today(self)
        days = number(self.env, P_WEEK_BEFORE_DAYS, 7)
        offers = self.env['pb.hiring.offer'].sudo().search([
            ('state', '=', 'signed'), ('week_before_sent_at', '=', False),
            ('expected_join_date', '>', today),
            ('expected_join_date', '<=', today + timedelta(days=days))], limit=200)
        made = 0
        for offer in offers:
            if leg(self.env, 'the week-before email on %s' % offer.name,
                   offer._week_before_send):
                made += 1
        return made

    @api.model
    def _prejoin_reminders(self):
        """Due tomorrow and still open: the owner is reminded once (the
        manager and the new joiner get their link again; the recruiter and HR
        a to-do). Two days late on the manager's or the new joiner's side:
        the recruiter gets a to-do to pick up the phone."""
        today = fields.Date.context_today(self)
        Item = self.env['pb.hiring.prejoin'].sudo()
        made = 0
        tomorrow = Item.search([('state', '=', 'open'), ('offer_id.state', '=', 'signed'),
                                ('due_date', '=', today + timedelta(days=1)),
                                ('reminded_at', '=', False)], limit=300)
        for item in tomorrow:
            if leg(self.env, 'the reminder on item %s' % item.id,
                   lambda i=item: self._remind_item(i)):
                made += 1
        late = Item.search([('state', '=', 'open'), ('offer_id.state', '=', 'signed'),
                            ('owner', 'in', ('manager', 'candidate')),
                            ('due_date', '<=', today - timedelta(days=2)),
                            ('chased_at', '=', False)], limit=300)
        for item in late:
            if leg(self.env, 'the chase on item %s' % item.id,
                   lambda i=item: self._chase_item(i)):
                made += 1
        return made

    @api.model
    def _remind_item(self, item):
        if item.kind in ('buddy', 'laptop') and item.sent_at:
            item.action_send()
        else:
            offer = item.offer_id
            users = offer._hr_lead_users() if item.owner == 'hr' else \
                offer.requisition_id.sudo().recruiter_id
            for user in users:
                if user and not user.share:
                    offer.applicant_id.sudo().activity_schedule(
                        _TODO, summary=_('Before %(who)s joins: %(what)s',
                                         who=offer.candidate_name or '',
                                         what=item.title or ''),
                        note=_("Due %s.", item.pb_due_words), user_id=user.id,
                        date_deadline=item.due_date)
        item.write({'reminded_at': fields.Datetime.now()})
        return True

    @api.model
    def _chase_item(self, item):
        offer = item.offer_id
        recruiter = offer.requisition_id.sudo().recruiter_id
        if recruiter and not recruiter.share:
            who = offer._manager().name if item.owner == 'manager' else offer.candidate_name
            offer.applicant_id.sudo().activity_schedule(
                _TODO, summary=_('%(who)s has not answered: %(what)s',
                                 who=who or _('Somebody'), what=item.title or ''),
                note=_("It was due %s. A call usually does it — or mark it done "
                       "on the Before they join list once you have the answer.",
                       item.pb_due_words),
                user_id=recruiter.id, date_deadline=fields.Date.context_today(self))
        item.write({'chased_at': fields.Datetime.now()})
        return True

    @api.model
    def run_reminders(self):
        counts = super().run_reminders()
        if not flag(self.env, P_REMINDERS):
            return counts               # the switch silences the whole job
        counts['chats'] = 0
        try:
            counts['chats'] = self._chats_tick()
        except Exception:               # noqa: BLE001 — a job never raises
            _logger.warning('pb_hiring: the chats step failed', exc_info=True)
        return counts

    @api.model
    def _chats_tick(self):
        """Every ten minutes: a chat whose time has passed is done; a chat
        whose Meet link never came sends its invitations without it."""
        now = fields.Datetime.now()
        Item = self.env['pb.hiring.prejoin'].sudo()
        made = 0
        for item in Item.search([('kind', '=', 'chat'), ('state', '=', 'open'),
                                 ('chat_start', '!=', False),
                                 ('offer_id.state', '=', 'signed')], limit=300):
            end = item.chat_start + timedelta(minutes=item.chat_minutes or 30)
            if end <= now:
                item._finish(by_name=_('The diary'))
                made += 1
        cutoff = now - timedelta(minutes=10)
        for item in Item.search([('invites_pending', '=', True), ('state', '=', 'open'),
                                 ('write_date', '<=', cutoff)], limit=100):
            if leg(self.env, 'the waiting chat invitations on %s' % item.id,
                   item._send_chat_invites) is not False:
                made += 1
        return made


def seed_p6(env):
    """Idempotent seeds: the company lists and the laptop email."""
    env['pb.hiring.prejoin.template']._ensure_defaults()
    from .form_seed_i18n import LAPTOP_I18N, LAPTOP_EMAIL
    from .forms_p2 import seed_message_i18n
    Tpl = env['pb.hiring.message.template'].sudo().with_context(
        active_test=False, lang='en_US')
    for company in env['res.company'].sudo().search([]):
        if not Tpl.search_count([('company_id', '=', company.id), ('key', '=', 'laptop')]):
            Tpl.create(dict(LAPTOP_EMAIL, company_id=company.id, sequence=60))
    seed_message_i18n(env, 'laptop', LAPTOP_I18N)
