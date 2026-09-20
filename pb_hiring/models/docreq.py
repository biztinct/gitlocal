# -*- coding: utf-8 -*-
"""`pb.hiring.docreq` — asking a candidate for their papers, once, by link.

THE PERSON WE ARE ASKING DOES NOT WORK HERE. They have no login, they are
probably doing this on a phone between two other jobs, and they have been
asked for the same six documents by three other companies this month. So:

  * ONE link, unguessable, that opens a page listing exactly what is wanted
    and shows what has already landed. No account, no password, no app.
  * A DEADLINE IN WORKING DAYS. Two plain days from a Friday afternoon is a
    Sunday, which is a deadline that exists only to be missed (R149, reached
    from the candidate's side rather than the panel's).
  * ONE reminder a day while something is outstanding, and never two. The
    stamp is a date and not a count, so a job that runs twice in a morning
    sends nothing the second time.
  * The recruiter gets a to-do at the deadline, because a candidate who has
    gone quiet is a person to ring, not a row to expire.

WHAT IT DELIBERATELY DOES NOT DO. It does not verify anything — that is the
background check, and a passport scan landing here says nothing about whether
anybody looked at it.
"""

import base64
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .hiring_common import (
    DOCREQ_STATES, P_DOC_DEADLINE_DAYS, UPLOAD_MAX_BYTES, UPLOAD_MIME_OK,
    as_id, counted, leg, number, slug_filename,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'


class PbHiringDocTemplate(models.Model):
    """What a company asks a joiner for, as an editable list."""
    _name = 'pb.hiring.doc.template'
    _description = 'Joining document'
    _order = 'sequence, id'

    name = fields.Char(string='What is asked for', required=True,
                       translate=True)
    sequence = fields.Integer(string='Order', default=10)
    required = fields.Boolean(
        string='Must be sent', default=True,
        help='On, the offer is not sent to the candidate until this one is '
             'in — unless the HR lead says to send it anyway.')
    help_text = fields.Char(
        string='What we need exactly', translate=True,
        help='One sentence on the candidate\'s page. "A photograph of the '
             'page with your picture on it" saves a week of emails.')
    active = fields.Boolean(string='In use', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty and every company uses it.')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Joining document')

    @api.model
    def lines_for(self, company=None):
        company_id = as_id(company) or self.env.company.id
        return self.sudo().search(
            ['|', ('company_id', '=', False), ('company_id', '=', company_id)])


class PbHiringDocreq(models.Model):
    _name = 'pb.hiring.docreq'
    _description = 'Document request'
    _inherit = ['mail.thread']
    _order = 'id desc'

    offer_id = fields.Many2one('pb.hiring.offer', string='Offer',
                               required=True, index=True, ondelete='cascade')
    applicant_id = fields.Many2one(
        'hr.applicant', related='offer_id.applicant_id', store=True,
        index=True, readonly=True, string='Candidate')
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', related='offer_id.requisition_id', store=True,
        index=True, readonly=True, string='Hiring request')
    candidate_name = fields.Char(related='offer_id.candidate_name',
                                 readonly=True, string='Their name')
    candidate_email = fields.Char(related='offer_id.candidate_email',
                                  readonly=True, string='Their email')

    # NO FIELD-LEVEL `groups=` ON THE TOKEN (R13). It is resolved at registry
    # load, which on a fresh install runs before this module's security data
    # exists, and it refuses the very `create` that mints the value. The
    # access list, the record rule and never putting it in a view or a
    # payload are what protect it.
    token = fields.Char(string='Link key', index=True, copy=False,
                        readonly=True)
    sent_on = fields.Datetime(string='Asked on', readonly=True, copy=False)
    deadline = fields.Date(string='Wanted by', readonly=True, copy=False)
    last_reminder_on = fields.Date(string='Last reminded', readonly=True,
                                   copy=False)
    deadline_todo_on = fields.Date(string='Recruiter told on', readonly=True,
                                   copy=False)
    state = fields.Selection(DOCREQ_STATES, string='How it stands',
                             compute='_compute_state', store=True,
                             readonly=True, index=True, tracking=True)
    item_ids = fields.One2many('pb.hiring.docreq.item', 'docreq_id',
                               string='What is asked for')
    in_count = fields.Integer(compute='_compute_state', store=True,
                              string='In')
    wanted_count = fields.Integer(compute='_compute_state', store=True,
                                  string='Asked for')
    company_id = fields.Many2one(
        'res.company', related='offer_id.company_id', store=True, index=True,
        readonly=True)

    _token_uniq = models.Constraint(
        'unique(token)', 'Two document links cannot share the same key.')
    _one_per_offer = models.Constraint(
        'unique(offer_id)', 'An offer has one document request.')

    # =====================================================================
    #  Names, computes, creation
    # =====================================================================
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('Documents · %s',
                                 rec.candidate_name or _('a candidate'))

    @api.depends('item_ids', 'item_ids.received_at', 'item_ids.required',
                 'deadline')
    def _compute_state(self):
        today = fields.Date.context_today(self)
        for rec in self:
            items = rec.item_ids
            wanted = items.filtered(lambda i: i.required)
            missing = wanted.filtered(lambda i: not i.received_at)
            rec.wanted_count = len(items)
            rec.in_count = len(items.filtered(lambda i: i.received_at))
            if not missing:
                rec.state = 'complete'
            elif rec.deadline and rec.deadline < today:
                rec.state = 'expired'
            elif rec.in_count:
                rec.state = 'partial'
            else:
                rec.state = 'sent'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(24)
        return super().create(vals_list)

    # =====================================================================
    #  Asking
    # =====================================================================
    @api.model
    def open_for(self, offer):
        """The request for one offer, made once and seeded from the list."""
        offer = self.env['pb.hiring.offer'].browse(as_id(offer)).exists()
        if not offer:
            raise UserError(_("That offer is no longer there."))
        existing = self.sudo().search([('offer_id', '=', offer.id)], limit=1)
        if existing:
            return existing
        req = self.sudo().create({'offer_id': offer.id})
        req._seed_items()
        return req

    def _seed_items(self):
        self.ensure_one()
        Item = self.env['pb.hiring.docreq.item'].sudo()
        made = 0
        for line in self.env['pb.hiring.doc.template'].lines_for(
                self.company_id):
            if Item.search_count([('docreq_id', '=', self.id),
                                  ('name', '=', line.name)]):
                continue
            Item.create({'docreq_id': self.id, 'name': line.name,
                         'sequence': line.sequence, 'required': line.required,
                         'help_text': line.help_text or ''})
            made += 1
        return made

    def _due_date(self):
        """Two WORKING days from now, on the company's own calendar.

        A company with no working calendar is answered honestly with plain
        days AND a log line (R149): guessing somebody's working week is worse
        than admitting it is not configured.
        """
        self.ensure_one()
        days = max(1, number(self.env, P_DOC_DEADLINE_DAYS, 2))
        now = fields.Datetime.now()
        calendar = self.company_id.sudo().resource_calendar_id
        if calendar:
            try:
                return calendar.plan_days(days, now,
                                          compute_leaves=True).date()
            except Exception:           # noqa: BLE001 — never fail an ask
                _logger.warning(
                    'pb_hiring: the working-day deadline could not be worked '
                    'out for document request %s', self.id, exc_info=True)
        else:
            _logger.info(
                'pb_hiring: %s has no working calendar, so the document '
                'deadline on request %s is a plain %s days rather than %s '
                'working ones', self.company_id.name, self.id, days, days)
        return (now + timedelta(days=days)).date()

    def action_send(self):
        """Ask the candidate, with the deadline and the link in the mail."""
        self.ensure_one()
        if not self.candidate_email:
            raise UserError(_(
                "There is no email address for this candidate, so there is "
                "nowhere to send the request. Add one on the candidate first."))
        first = not self.sent_on
        self.sudo().write({'sent_on': fields.Datetime.now(),
                           'deadline': self._due_date()})
        self._mail('pb_hiring.mail_template_docreq_ask')
        self.sudo().message_post(body=_(
            "Asked %(who)s for %(n)s %(word)s by %(when)s.",
            who=self.candidate_name or '', n=len(self.item_ids),
            word=counted(len(self.item_ids), _('document'), _('documents')),
            when=self.deadline or ''))
        if first:
            _logger.info('pb_hiring: document request %s sent', self.id)
        return True

    def action_remind(self):
        """One nudge, and never two in a day."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        if self.last_reminder_on == today:
            return False
        if self.state == 'complete':
            return False
        self._mail('pb_hiring.mail_template_docreq_remind')
        self.sudo().write({'last_reminder_on': today})
        return True

    def _mail(self, xmlid):
        """One mail, addressed EXPLICITLY (R6)."""
        self.ensure_one()
        if not self.candidate_email:
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.info('pb_hiring: the mail template %s is not in this '
                         'build', xmlid)
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': self.candidate_email,
                          'auto_delete': False})
        return True

    # =====================================================================
    #  The link
    # =====================================================================
    def _token_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/hiring/d/%s' % (base.rstrip('/'), self.sudo().token)

    @api.model
    def _request_for_token(self, token):
        """`(record, status)` — and a stranger probing the URL space learns
        nothing from the difference between a wrong key and a finished one."""
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        row = self.sudo().search([('token', '=', token)], limit=1)
        if not row:
            return blank, 'invalid'
        # A CLOSED OFFER CLOSES THE PAGE and a late one does NOT. Being past
        # the date is exactly when we most want the papers; the link staying
        # open is the whole reason the reminder is worth sending.
        if row.offer_id.state in ('closed', 'declined', 'refused'):
            return row, 'closed'
        if row.state == 'complete':
            return row, 'done'
        return row, 'ok'

    def page_facts(self):
        """The little a candidate needs, and nothing else.

        No id, no salary, no link into the backend, nothing about anybody
        else. A person asked for their passport should not learn what the
        role pays from the page they are asked on.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        return {
            'candidate': self.candidate_name or '',
            'role': self.requisition_id.sudo().title or '',
            'company': self.company_id.name or '',
            'deadline': str(self.deadline or ''),
            'late': bool(self.deadline and self.deadline < today),
            'in': self.in_count,
            'total': len(self.item_ids),
            'items': [{
                'id': i.id,
                'name': i.name or '',
                'help': i.help_text or '',
                'required': bool(i.required),
                'received': bool(i.received_at),
                'filename': i.attachment_id.sudo().name or '',
            } for i in self.item_ids.sorted(lambda r: (r.sequence, r.id))],
        }

    # =====================================================================
    #  Receiving one
    # =====================================================================
    def receive(self, item_id, filename, content, mimetype=None):
        """One file against one line. Called from the public route only.

        EVERY LIMIT IS CHECKED HERE and not only in the controller, because
        the controller is one caller and this is the rule. A file that is too
        big, of a kind we do not take, or against a line of somebody else's
        request is refused with a sentence rather than a traceback.
        """
        self.ensure_one()
        item = self.item_ids.filtered(lambda i: i.id == as_id(item_id))[:1]
        if not item:
            raise UserError(_("That is not one of the documents you were "
                              "asked for."))
        if not content:
            raise UserError(_("The file did not arrive. Try it again."))
        if len(content) > UPLOAD_MAX_BYTES:
            raise UserError(_(
                "That file is bigger than 5 MB. A photograph taken on a phone "
                "is usually well under that — try again, or reply to the "
                "email and send it that way."))
        if (mimetype or '') not in UPLOAD_MIME_OK:
            raise UserError(_(
                "Send a PDF, a Word document or a photograph (JPG or PNG). "
                "Anything else we cannot open."))
        name = slug_filename(filename or item.name,
                             fallback='document')
        attachment = self.env['ir.attachment'].sudo().create({
            'name': '%s — %s' % (item.name or '', name),
            'datas': base64.b64encode(content),
            'mimetype': mimetype,
            'res_model': 'pb.hiring.docreq',
            'res_id': self.id,
        })
        old = item.attachment_id
        item.sudo().write({'attachment_id': attachment.id,
                           'received_at': fields.Datetime.now()})
        if old:
            # A replacement is a correction, not history: leaving the first
            # file downloadable would mean two answers to one question.
            old.sudo().unlink()
        self.invalidate_recordset(['state', 'in_count'])
        if self.state == 'complete':
            # A SAVEPOINT, because this runs inside a PUBLIC upload (R131). A
            # chatter line or an activity that failed in the database would
            # abort the whole transaction and take the candidate's file with
            # it — and the page would tell them it had not arrived.
            leg(self.env, 'the everything-is-in note on request %s' % self.id,
                self._all_in)
        return True

    def _all_in(self):
        """Everything is in — tell the recruiter once."""
        self.ensure_one()
        self.sudo().message_post(body=_(
            "%s has sent everything that was asked for.",
            self.candidate_name or ''))
        recruiter = self.requisition_id.sudo().recruiter_id
        if not recruiter:
            return False
        self.sudo().activity_schedule(
            _TODO,
            summary=_('Papers are in: %s', self.candidate_name or ''),
            note=_("Everything asked for has arrived. The offer can go out "
                   "as soon as it has been agreed."),
            user_id=recruiter.id,
            date_deadline=fields.Date.context_today(self))
        return True

    def _raise_deadline_todo(self):
        """One to-do for the recruiter on the day the window shuts."""
        self.ensure_one()
        if self.deadline_todo_on:
            return False
        recruiter = self.requisition_id.sudo().recruiter_id
        self.sudo().write({
            'deadline_todo_on': fields.Date.context_today(self)})
        if not recruiter:
            _logger.info('pb_hiring: document request %s is past its date and '
                         'nobody is recruiting the role', self.id)
            return False
        missing = self.item_ids.filtered(
            lambda i: i.required and not i.received_at)
        self.sudo().activity_schedule(
            _TODO,
            summary=_('Chase the papers: %s', self.candidate_name or ''),
            note=_("%(who)s was asked by %(when)s and %(n)s %(word)s still "
                   "missing: %(names)s. Their link still works — a phone call "
                   "usually settles it.",
                   who=self.candidate_name or '', when=self.deadline or '',
                   n=len(missing),
                   word=counted(len(missing), _('thing is'), _('things are')),
                   names=', '.join(i.name or '' for i in missing)),
            user_id=recruiter.id,
            date_deadline=fields.Date.context_today(self))
        return True

    # ------------------------------------------------------------- the door
    def action_copy_link(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'info', 'sticky': True,
                       'title': _('Their own link'),
                       'message': self._token_url()},
        }


class PbHiringDocreqItem(models.Model):
    _name = 'pb.hiring.docreq.item'
    _description = 'Document asked for'
    _order = 'sequence, id'

    docreq_id = fields.Many2one('pb.hiring.docreq', string='Document request',
                                required=True, index=True, ondelete='cascade')
    name = fields.Char(string='What is asked for', required=True)
    sequence = fields.Integer(string='Order', default=10)
    required = fields.Boolean(string='Must be sent', default=True)
    help_text = fields.Char(string='What we need exactly')
    received_at = fields.Datetime(string='Arrived on', readonly=True,
                                  copy=False)
    attachment_id = fields.Many2one('ir.attachment', string='The file',
                                    readonly=True, copy=False,
                                    ondelete='set null')
    company_id = fields.Many2one(
        'res.company', related='docreq_id.company_id', store=True, index=True,
        readonly=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Document')
