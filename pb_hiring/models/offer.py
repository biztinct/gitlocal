# -*- coding: utf-8 -*-
"""`pb.hiring.offer` — the money, the letter, and the answer.

AN OFFER IS THE ONE DOCUMENT IN HIRING THAT BINDS THE COMPANY, and until now
this product had nowhere to write one down. A pay package (`pb.employee.comp`)
says what somebody who works here is paid; a candidate does not work here yet,
and half of them never will. So an offer carries its OWN lines, is agreed on
its own route, is printed from the company's own letter library, and becomes a
pay package only at the moment somebody actually joins.

THREE THINGS THIS MODEL IS CAREFUL ABOUT.

  1. **The number an approver agreed to.** The lines and the start date are in
     the revision stamp, so changing a figure after the hiring manager has
     agreed sends it round again. An approval given to 25 million is not an
     approval of 30 million, and the engine's revision doctrine (AM32) exists
     for exactly this case.
  2. **The letter is TEMPLATES, not `pb.hr.letter`.** The letter engine's
     letter requires an `hr.employee` and reads the employee for every
     placeholder (`pb_lifecycle/models/letter.py:91,133`), and a candidate has
     no employee record — that is the whole point of a candidate. So the
     TEMPLATE side is reused (one library, one place a company rewords its
     letters) and the rendering is done here against the offer's own facts.
  3. **"Signed" is a human act.** No e-signature is connected (ruling D12), so
     signing is a recruiter uploading the copy the candidate sent back and
     saying so. Nothing pretends otherwise anywhere on the screen.
"""

import base64
import logging
import secrets
from string import Template

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, formatLang

from .hiring_common import (
    CANDIDATE_DECISIONS, GROUP_MANAGER, GROUP_USER, OFFER_KINDS,
    OFFER_LETTER_TYPE, OFFER_PERIOD_MONTH, OFFER_PERIOD_YEAR, OFFER_PERIODS,
    OFFER_STATES, P_OFFER_MAIL, UPLOAD_MAX_BYTES, UPLOAD_MIME_OK, as_id,
    counted, flag, leg, slug_filename,
)

_logger = logging.getLogger(__name__)

_TODO = 'mail.mail_activity_data_todo'

#: A public comment box must never be usable to post a book.
_MAX_COMMENT = 4000


class PbLetterTemplateOffer(models.Model):
    """One more kind of letter in the library everybody already edits.

    `selection_add` rather than a second template model: a company that
    rewords its offer letter expects to find it beside its probation letters
    and its experience letters, not in a hiring screen it has to be told
    about.
    """
    _inherit = 'pb.letter.template'

    letter_type = fields.Selection(
        selection_add=[(OFFER_LETTER_TYPE, 'Offer letter')],
        ondelete={OFFER_LETTER_TYPE: 'set default'})


# A RELATED SELECTION NEEDS NO `selection_add` AND MUST NOT BE GIVEN ONE.
# `pb.hr.letter.letter_type` is `related='template_id.letter_type'` and
# re-declares the list for documentation, but Odoo 19 takes a related field's
# selection from the SOURCE field and says so in the log:
#     "selection attribute will be ignored as the field is related"
# Extending it therefore achieves nothing — and it is not merely useless: an
# `ondelete` spec on a field with no default of its own trips a hard assertion
# in `fields_selection.py:149` that FAILS THE WHOLE REGISTRY LOAD, with the
# real error only in the server log. Adding the value to the TEMPLATE is the
# whole of the change; the letter follows it for free.


class PbHiringOffer(models.Model):
    _name = 'pb.hiring.offer'
    _description = 'Offer'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    _order = 'id desc'

    #: The ladder the record keeps for itself when no route is published.
    #: Under a published route the shim takes every press and the route
    #: decides the order (AM84).
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'manager_ok'): None,
        ('manager_ok', 'hr_ok'): GROUP_MANAGER,
        ('submitted', 'refused'): None,
        ('manager_ok', 'refused'): GROUP_MANAGER,
        ('draft', 'refused'): GROUP_USER,
    }

    # ------------------------------------------------------- what it is about
    name = fields.Char(string='Reference', copy=False, readonly=True,
                       index=True, default=lambda self: _('New'))
    requisition_id = fields.Many2one(
        'pb.hiring.requisition', string='Hiring request', required=True,
        index=True, ondelete='cascade')
    applicant_id = fields.Many2one(
        'hr.applicant', string='Candidate', required=True, index=True,
        ondelete='cascade')
    bgv_id = fields.Many2one('pb.hiring.bgv', string='Background check',
                             ondelete='set null')
    docreq_ids = fields.One2many('pb.hiring.docreq', 'offer_id',
                                 string='Document requests')
    #: THE ONE REQUEST, as a field rather than a slice of a list. The child
    #: carries a unique constraint on `offer_id`, so "the document request"
    #: has exactly one answer — and a later phase reading `offer.docreq_id`
    #: should get a record, not a recordset it has to remember to index.
    docreq_id = fields.Many2one('pb.hiring.docreq', string='Document request',
                                compute='_compute_docreq', store=True,
                                readonly=True, ondelete='set null')
    job_title = fields.Char(string='The job title on the letter', required=True)
    start_date = fields.Date(string='Starting on', required=True,
                             tracking=True)
    location = fields.Char(string='Where they will be based')
    reporting_manager_id = fields.Many2one(
        'hr.employee', string='Who they will report to')

    # R56 — one field of an applicant reads the lot, some of it group-gated.
    candidate_name = fields.Char(string='Their name', compute='_compute_who',
                                 compute_sudo=True, store=True, readonly=True)
    candidate_email = fields.Char(string='Their email', compute='_compute_who',
                                  compute_sudo=True, store=True, readonly=True)

    # ------------------------------------------------------------- the money
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    line_ids = fields.One2many('pb.hiring.offer.line', 'offer_id',
                               string='What is being offered', copy=True)
    monthly_total = fields.Monetary(
        string='A month of this', currency_field='currency_id',
        compute='_compute_totals', store=True, readonly=True)
    annual_total = fields.Monetary(
        string='A year of this', currency_field='currency_id',
        compute='_compute_totals', store=True, readonly=True)

    # ------------------------------------------------------------ the letter
    letter_template_id = fields.Many2one(
        'pb.letter.template', string='Which letter',
        domain=[('letter_type', '=', OFFER_LETTER_TYPE)],
        help='The wording the company uses. Change it here and the letter is '
             'written again the next time it is prepared.')
    rendered_html = fields.Html(string='The letter', sanitize=False,
                                readonly=True, copy=False)
    attachment_id = fields.Many2one('ir.attachment', string='The letter as a '
                                    'PDF', readonly=True, copy=False,
                                    ondelete='set null')
    signed_attachment_id = fields.Many2one(
        'ir.attachment', string='The signed copy', readonly=True, copy=False,
        ondelete='set null')
    signed_on = fields.Date(string='Signed on', readonly=True, copy=False)
    signed_by_id = fields.Many2one('res.users', string='Recorded by',
                                   readonly=True, copy=False)

    # --------------------------------------------------------- the candidate
    # NO FIELD-LEVEL `groups=` ON THE TOKEN (R13).
    token = fields.Char(string='Link key', index=True, copy=False,
                        readonly=True)
    sent_on = fields.Datetime(string='Sent on', readonly=True, copy=False)
    candidate_decision = fields.Selection(
        CANDIDATE_DECISIONS, string='What they said', default='pending',
        readonly=True, copy=False, tracking=True)
    candidate_comment = fields.Text(string='What they said in their own words',
                                    readonly=True, copy=False)
    decided_on = fields.Datetime(string='They answered on', readonly=True,
                                 copy=False)

    # ------------------------------------------------------ what it produces
    state = fields.Selection(OFFER_STATES, string='How far it has got',
                             default='draft', required=True, index=True,
                             tracking=True, copy=False)
    employee_id = fields.Many2one('hr.employee', string='The employee record',
                                  readonly=True, copy=False,
                                  ondelete='set null')
    contract_id = fields.Many2one('hr.contract', string='Their contract',
                                  readonly=True, copy=False,
                                  ondelete='set null')
    comp_id = fields.Many2one('pb.employee.comp', string='Their pay package',
                              readonly=True, copy=False, ondelete='set null')
    case_id = fields.Many2one('pb.journey.case', string='Joining checklist',
                              readonly=True, copy=False, ondelete='set null')
    login_user_id = fields.Many2one('res.users', string='Their login',
                                    readonly=True, copy=False,
                                    ondelete='set null')
    closed_on = fields.Datetime(string='Closed on', readonly=True, copy=False)

    company_id = fields.Many2one(
        'res.company', related='requisition_id.company_id', store=True,
        index=True, readonly=True)

    _token_uniq = models.Constraint(
        'unique(token)', 'Two offer links cannot share the same key.')

    # =====================================================================
    #  Names and small computes
    # =====================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('token'):
                vals['token'] = secrets.token_urlsafe(24)
            if not vals.get('name') or vals['name'] == _('New'):
                seq = self.env['ir.sequence'].sudo().next_by_code(
                    'pb.hiring.offer')
                vals['name'] = seq or _('New')
        return super().create(vals_list)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _('%(ref)s · %(who)s', ref=rec.name or '',
                                 who=rec.candidate_name or '').strip(' ·')

    @api.depends('applicant_id', 'applicant_id.partner_name',
                 'applicant_id.email_from')
    def _compute_who(self):
        for rec in self:
            app = rec.applicant_id
            rec.candidate_name = (app.partner_name or app.email_from
                                  or '') if app else ''
            rec.candidate_email = (app.email_from or '') if app else ''

    @api.depends('docreq_ids')
    def _compute_docreq(self):
        for rec in self:
            rec.docreq_id = rec.docreq_ids[:1]

    @api.depends('line_ids.amount', 'line_ids.period', 'currency_id')
    def _compute_totals(self):
        for rec in self:
            currency = rec.currency_id
            month = sum((ln.amount or 0.0)
                        * OFFER_PERIOD_MONTH.get(ln.period or 'monthly', 1.0)
                        for ln in rec.line_ids)
            year = sum((ln.amount or 0.0)
                       * OFFER_PERIOD_YEAR.get(ln.period or 'monthly', 12.0)
                       for ln in rec.line_ids)
            # ROUNDED TO THE CURRENCY BEFORE IT IS STORED (R90). Dong keeps no
            # cents, and a figure that is written unrounded reads back
            # different from what was written — which turns an idempotent
            # comparison into a change every time.
            rec.monthly_total = currency.round(month) if currency else month
            rec.annual_total = currency.round(year) if currency else year

    @api.constrains('start_date')
    def _check_start(self):
        for rec in self:
            if rec.start_date and rec.start_date < fields.Date.context_today(
                    rec) and rec.state in ('draft', 'submitted'):
                raise ValidationError(_(
                    "The starting date has already gone. Pick a day in the "
                    "future — this is the date the letter promises."))

    # =====================================================================
    #  R56 / R43
    # =====================================================================
    @api.model
    def _person(self, employee):
        emp_id = as_id(employee)
        if not emp_id:
            return self.env['hr.employee'].sudo().browse()
        return self.env['hr.employee'].sudo().browse(emp_id).exists()

    def _money(self, amount):
        """An amount as a PERSON reads it, and never as markup (R137)."""
        self.ensure_one()
        try:
            return formatLang(self.env, amount or 0.0,
                              currency_obj=self.currency_id)
        except Exception:               # noqa: BLE001 — never fail a sentence
            return '%s %s' % (amount, self.currency_id.name or '')

    # =====================================================================
    #  Drafting one
    # =====================================================================
    @api.model
    def draft_for(self, requisition_id, values=None):
        """The offer for the person the panel picked.

        THE BACKGROUND CHECK IS THE DOOR and it is checked here rather than on
        the button, because "draft an offer" is reachable from the board, from
        the form and from a test, and a rule enforced in one of three places
        is a rule enforced nowhere.
        """
        values = values or {}
        req = self.env['pb.hiring.requisition'].browse(
            as_id(requisition_id)).exists()
        if not req:
            raise UserError(_("That hiring request is no longer there."))
        applicant = req.sudo().selected_applicant_id
        if not applicant:
            raise UserError(_(
                "Nobody has been picked for this role yet. An offer starts "
                "from the panel's decision on the last round — record the "
                "debrief and the offer opens from there."))
        live = self.sudo().search([
            ('requisition_id', '=', req.id),
            ('applicant_id', '=', applicant.id),
            ('state', 'not in', ('declined', 'refused')),
        ], limit=1)
        if live:
            return live

        bgv = self.env['pb.hiring.bgv'].open_for(req.id, applicant.id)
        ready, why = bgv.check_ready()
        if not ready:
            raise UserError(why)

        # THE WANTED-BY DATE IS A WISH AND THE START DATE IS A PROMISE. A
        # request raised in June asking for somebody by August is perfectly
        # ordinary, and so is an offer written in September — so the date the
        # letter carries is never allowed to be in the past, whatever the
        # request hoped for.
        today = fields.Date.context_today(self)
        wanted = values.get('start_date') or req.target_start_date or today
        wanted = fields.Date.to_date(wanted)
        offer = self.sudo().create({
            'requisition_id': req.id,
            'applicant_id': applicant.id,
            'bgv_id': bgv.id,
            'job_title': values.get('job_title') or req.title or '',
            'start_date': max(wanted, today),
            'location': values.get('location') or req.location or '',
            'reporting_manager_id': req.reporting_manager_id.id or False,
            'currency_id': req.currency_id.id or self.env.company.currency_id.id,
            'letter_template_id': self._pick_template(req).id or False,
        })
        offer.sudo().message_post(body=_(
            "Offer opened for %s.", offer.candidate_name or ''))
        return offer

    @api.model
    def _pick_template(self, requisition):
        """The letter this country uses, or the one everybody uses.

        A country template beats the generic one and a company template beats
        a shared one, which is the order somebody would say it out loud. No
        match is not an error — the offer is drafted and the screen says a
        letter has not been chosen.
        """
        Template = self.env['pb.letter.template'].sudo()
        country = requisition.country_id or requisition.company_id.country_id
        base = [('letter_type', '=', OFFER_LETTER_TYPE)]
        for domain in (
            base + [('company_id', '=', requisition.company_id.id),
                    ('name', 'ilike', country.name or '~none~')],
            base + [('company_id', '=', requisition.company_id.id)],
            base + [('company_id', '=', False),
                    ('name', 'ilike', country.name or '~none~')],
            base + [('company_id', '=', False)],
        ):
            hit = Template.search(domain, order='sequence, id', limit=1)
            if hit:
                return hit
        return Template.browse()

    def action_add_line(self, values=None):
        self.ensure_one()
        values = values or {}
        return self.env['pb.hiring.offer.line'].sudo().create({
            'offer_id': self.id,
            'name': (values.get('name') or '').strip() or _('Basic pay'),
            'kind': values.get('kind') or 'earning',
            'amount': float(values.get('amount') or 0.0),
            'period': values.get('period') or 'monthly',
            'note': (values.get('note') or '').strip(),
        })

    # =====================================================================
    #  The letter
    # =====================================================================
    def _placeholder_values(self):
        """What each hole in the letter is filled with, ESCAPED for HTML.

        Substitution and never evaluation, exactly as the letter engine does
        it (`letter.py:133`): the worst thing an HR administrator can do to a
        `${...}` is misspell it, which leaves the placeholder on the page
        instead of running something.
        """
        self.ensure_one()
        req = self.requisition_id.sudo()
        manager = self._person(self.reporting_manager_id
                               or req.reporting_manager_id)
        values = {
            'candidate_name': self.candidate_name or '',
            'job_title': self.job_title or req.title or '',
            'department': req.department_id.name or '',
            'company': self.company_id.name or '',
            'location': self.location or req.location or '',
            'start_date': format_date(self.env, self.start_date,
                                      date_format='d MMM y')
            if self.start_date else '',
            'monthly_total': self._money(self.monthly_total),
            'annual_total': self._money(self.annual_total),
            'currency': self.currency_id.name or '',
            'manager': manager.name or '',
            'date': format_date(self.env, fields.Date.context_today(self),
                                date_format='d MMM y'),
        }
        return {k: str(escape(v)) for k, v in values.items()}

    def _lines_table(self):
        """The money, as a table the letter can print.

        Built here and not in the template, because a company that rewords
        its offer letter must not have to rewrite an HTML table to keep the
        figures in it — `${lines}` is one placeholder and this is what fills
        it.
        """
        self.ensure_one()
        rows = [Markup(
            '<tr><td style="padding:4px 12px 4px 0;">%(what)s</td>'
            '<td style="padding:4px 0; text-align:right;">%(amount)s</td>'
            '<td style="padding:4px 0 4px 12px; color:#64748B;">%(when)s</td>'
            '</tr>') % {
                'what': ln.name or '',
                'amount': self._money(ln.amount),
                'when': dict(OFFER_PERIODS).get(ln.period, ''),
            } for ln in self.line_ids.sorted(lambda r: (r.sequence, r.id))]
        return Markup(
            '<table style="border-collapse:collapse; margin:10px 0;">'
            '%s</table>') % Markup('').join(rows)

    def action_prepare_letter(self):
        """Fill the holes and render the PDF. Safe to press twice."""
        self.ensure_one()
        # THE WORDING IS READ AS THE SYSTEM, and the boundary is the offer's
        # own record rule — which has already decided that this person may
        # see this offer. Found live on 2026-09-15: a recruiter pressing
        # "Read the letter" got an AccessError naming five groups they have
        # no business holding, on a library of company letters that is not a
        # secret. (A recruiter is also given read on the library in this
        # module's access list, so the native form can draw the picker; this
        # is the belt to that pair of braces.)
        template = self.letter_template_id.sudo()
        if not template:
            raise UserError(_(
                "No offer letter has been chosen yet. Pick one — the company's "
                "letters are all in one list under Lifecycle, and an offer "
                "letter can be worded per country."))
        if not template.body_html:
            raise UserError(_(
                "“%s” has no wording in it yet, so there is nothing to print.",
                template.name))
        if not self.line_ids:
            raise UserError(_(
                "There is nothing in this offer yet. Add what is being "
                "offered — the basic pay at least — before the letter is "
                "written."))
        values = self._placeholder_values()
        values['lines'] = str(self._lines_table())
        body = Template(str(template.body_html)).safe_substitute(values)
        self.sudo().write({'rendered_html': Markup(body)})
        self._make_pdf()
        return True

    def _make_pdf(self):
        """The letter as a PDF, rendered AS THE CALLER.

        NOT `report.sudo()` (R89): a report rendered as the superuser re-reads
        its own data seeing every company, which is a leak the moment the
        template calls anything. The render carries the caller's company set
        explicitly instead.
        """
        self.ensure_one()
        report = self.env.ref('pb_hiring.action_report_hiring_offer',
                              raise_if_not_found=False)
        if not report:
            _logger.warning('pb_hiring: the offer letter report is missing')
            return False
        pdf, _ext = report.with_context(
            allowed_company_ids=self.env.companies.ids,
        )._render_qweb_pdf('pb_hiring.report_hiring_offer_document',
                           res_ids=self.ids)
        filename = '%s.pdf' % slug_filename(
            _('Offer %(who)s', who=self.candidate_name or self.name or ''),
            fallback='offer')
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': 'pb.hiring.offer',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        old = self.attachment_id
        self.sudo().write({'attachment_id': attachment.id})
        if old:
            # A re-prepared letter supersedes the old PDF rather than keeping
            # it: two downloadable offers to one person is one too many.
            old.sudo().unlink()
        return attachment

    # =====================================================================
    #  The route
    # =====================================================================
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_("This offer has already been sent in."))
            if not rec.line_ids:
                raise UserError(_(
                    "Say what is being offered before you send it for "
                    "sign-off. Nobody can agree to a number that is not "
                    "there."))
            if not rec.start_date:
                raise UserError(_("Say when they would start."))
            rec._advance_state('submitted')
            rec.sudo().message_post(body=_(
                "Sent for sign-off — %(month)s a month, %(year)s a year.",
                month=rec._money(rec.monthly_total),
                year=rec._money(rec.annual_total)))
        return True

    def action_manager_agree(self, note=False):
        for rec in self:
            rec._advance_state('manager_ok', note=note or False)
        return True

    def action_hr_agree(self, note=False):
        for rec in self:
            rec._advance_state('hr_ok', note=note or False)
        return True

    def action_refuse(self, note=False):
        return self.action_refuse_chain(note=note or False)

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'hr_ok':
            self._on_approved()
        return res

    def _on_approved(self):
        """Agreed. Prepare the letter and tell the recruiter it may go.

        Both legs in a SAVEPOINT (R131): a letter template with a broken hole
        in it must not be able to undo the approval that has just been given.
        """
        self.ensure_one()
        leg(self.env, 'the offer letter for %s' % self.name,
            self.action_prepare_letter)
        leg(self.env, 'the recruiter to-do for offer %s' % self.name,
            self._tell_recruiter_it_is_agreed)
        return True

    def _tell_recruiter_it_is_agreed(self):
        self.ensure_one()
        recruiter = self.requisition_id.sudo().recruiter_id
        if not recruiter:
            return False
        self.sudo().activity_schedule(
            _TODO,
            summary=_('Send the offer: %s', self.candidate_name or ''),
            note=_("The offer has been agreed. Check the papers are in, then "
                   "send it — the candidate gets the letter and a page to "
                   "accept it on."),
            user_id=recruiter.id,
            date_deadline=fields.Date.context_today(self))
        return True

    # =====================================================================
    #  Sending it
    # =====================================================================
    def action_request_documents(self):
        """Ask the candidate for their papers."""
        self.ensure_one()
        docreq = self.env['pb.hiring.docreq'].open_for(self.id)
        docreq.action_send()
        return docreq

    def _documents_ready(self):
        """`(ok, sentence)` — is everything the company asked for in?"""
        self.ensure_one()
        docreq = self.docreq_id
        if not docreq:
            return False, _(
                "Nobody has asked this candidate for their papers yet. Send "
                "the document request first — it is one press and they get "
                "two working days.")
        if docreq.state == 'complete':
            return True, ''
        missing = docreq.item_ids.filtered(
            lambda i: i.required and not i.received_at)
        return False, _(
            "%(n)s %(word)s still missing: %(names)s. Send the offer anyway "
            "if you are happy to chase them afterwards — the HR lead can do "
            "that from here.",
            n=len(missing),
            word=counted(len(missing), _('document is'), _('documents are')),
            names=', '.join(i.name or '' for i in missing))

    def action_send_to_candidate(self, force=False):
        """The letter and the link, to the person it is about.

        FORCING IS THE HR LEAD'S and not the recruiter's, because "send it
        before the papers are in" is a decision to carry a risk, and the
        person carrying it should be the person who owns it.
        """
        self.ensure_one()
        if self.state not in ('hr_ok', 'sent'):
            raise UserError(_(
                "An offer goes to the candidate once it has been agreed. "
                "This one is “%s”.",
                dict(OFFER_STATES).get(self.state, self.state)))
        ok, why = self._documents_ready()
        if not ok:
            if not force:
                raise UserError(why)
            if not (self.env.su or self.env.user.has_group(GROUP_MANAGER)):
                raise UserError(_(
                    "Sending an offer before the papers are in is the HR "
                    "lead's call. Ask them, or chase the candidate — their "
                    "link is still live."))
        if not self.candidate_email:
            raise UserError(_(
                "There is no email address for this candidate, so there is "
                "nowhere to send the offer."))
        if not self.attachment_id:
            self.action_prepare_letter()
        if not flag(self.env, P_OFFER_MAIL):
            _logger.info('pb_hiring: offer mail is switched off; %s would '
                         'have gone to %s', self.name, self.candidate_email)
        else:
            self._mail('pb_hiring.mail_template_offer_candidate',
                       self.candidate_email, with_pdf=True)
        self.sudo().write({'state': 'sent',
                           'sent_on': fields.Datetime.now(),
                           'candidate_decision': 'pending'})
        self.sudo().message_post(body=_(
            "Offer sent to %(who)s%(note)s.", who=self.candidate_name or '',
            note=_(' before every document was in') if not ok else ''))
        return True

    def _mail(self, xmlid, to, with_pdf=False):
        """One mail, addressed EXPLICITLY (R6)."""
        self.ensure_one()
        if not to:
            return False
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.info('pb_hiring: the mail template %s is not in this '
                         'build', xmlid)
            return False
        email_values = {'email_to': to, 'auto_delete': False}
        if with_pdf and self.attachment_id:
            email_values['attachment_ids'] = [(4, self.attachment_id.id)]
        template.sudo().send_mail(self.id, force_send=False,
                                  email_values=email_values)
        return True

    # =====================================================================
    #  The candidate's own page
    # =====================================================================
    def _token_url(self):
        self.ensure_one()
        base = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url', '')
        return '%s/hiring/o/%s' % (base.rstrip('/'), self.sudo().token)

    @api.model
    def _request_for_token(self, token):
        """`(record, status)` — a stranger probing the URL space learns
        nothing from the difference between a wrong key and a spent one."""
        blank = self.browse()
        if not token or len(token) < 12:
            return blank, 'invalid'
        row = self.sudo().search([('token', '=', token)], limit=1)
        if not row:
            return blank, 'invalid'
        if row.state in ('draft', 'submitted', 'manager_ok', 'hr_ok',
                         'refused'):
            return row, 'closed'
        if row.candidate_decision in ('accepted', 'declined'):
            return row, 'used'
        return row, 'ok'

    def page_facts(self):
        """What the candidate sees, and nothing else.

        The role, the day, the money and the letter. Not an id, not who else
        applied, not what the panel said, not a link into the backend.
        """
        self.ensure_one()
        return {
            'candidate': self.candidate_name or '',
            'role': self.job_title or '',
            'company': self.company_id.name or '',
            'department': self.requisition_id.sudo().department_id.name or '',
            'location': self.location or '',
            'start_date': format_date(self.env, self.start_date,
                                      date_format='d MMMM y')
            if self.start_date else '',
            'monthly_total': self._money(self.monthly_total),
            'annual_total': self._money(self.annual_total),
            'lines': [{'name': ln.name or '',
                       'amount': self._money(ln.amount),
                       'period': dict(OFFER_PERIODS).get(ln.period, '')}
                      for ln in self.line_ids.sorted(
                          lambda r: (r.sequence, r.id))],
            'has_pdf': bool(self.attachment_id),
            'decision': self.candidate_decision or 'pending',
            'decision_label': dict(CANDIDATE_DECISIONS).get(
                self.candidate_decision or 'pending', ''),
            'comment': self.candidate_comment or '',
        }

    def record_decision(self, decision, comment=None):
        """The candidate's answer. Called from the public route only."""
        self.ensure_one()
        if decision not in ('accepted', 'declined'):
            return False
        if self.candidate_decision in ('accepted', 'declined'):
            return False
        self.sudo().write({
            'candidate_decision': decision,
            'candidate_comment': (comment or '').strip()[:_MAX_COMMENT],
            'decided_on': fields.Datetime.now(),
            'state': 'accepted' if decision == 'accepted' else 'declined',
        })
        self.sudo().message_post(body=_(
            "%(who)s %(what)s. %(note)s", who=self.candidate_name or '',
            what=_('accepted the offer') if decision == 'accepted'
            else _('turned the offer down'),
            note=(comment or '').strip()))
        leg(self.env, 'telling the recruiter about offer %s' % self.name,
            self._tell_recruiter_the_answer)
        return True

    def _tell_recruiter_the_answer(self):
        """A DECLINE IS THE ONE THAT MATTERS MOST, and it changes nothing
        about the candidate: they stay exactly where they are on the board,
        because a person who says no to one offer is often the person who
        says yes to the next role."""
        self.ensure_one()
        recruiter = self.requisition_id.sudo().recruiter_id
        accepted = self.candidate_decision == 'accepted'
        if recruiter and recruiter.email:
            self._mail('pb_hiring.mail_template_offer_answered',
                       recruiter.email)
        if not recruiter:
            return False
        self.sudo().activity_schedule(
            _TODO,
            summary=(_('Offer accepted: %s', self.candidate_name or '')
                     if accepted else
                     _('Offer turned down: %s', self.candidate_name or '')),
            note=(_("Get the signed copy back and record it here, then close "
                    "the offer — that is what makes them a joiner.")
                  if accepted else
                  _("They said no. Nothing has changed on the board: the role "
                    "is still open and they are still a candidate. Worth "
                    "asking why — it is usually the money or the notice "
                    "period.")),
            user_id=recruiter.id,
            date_deadline=fields.Date.context_today(self))
        return True

    # =====================================================================
    #  Signed (by hand — ruling D12)
    # =====================================================================
    def action_record_signed(self, filename=None, content=None, mimetype=None,
                             signed_on=None):
        """"They have signed it", said by a person, with the copy attached."""
        self.ensure_one()
        if self.state not in ('accepted', 'sent'):
            raise UserError(_(
                "An offer is signed after the candidate has accepted it. This "
                "one is “%s”.",
                dict(OFFER_STATES).get(self.state, self.state)))
        attachment = self.signed_attachment_id
        if content:
            if len(content) > UPLOAD_MAX_BYTES:
                raise UserError(_(
                    "That file is bigger than 5 MB. A scan of a signed letter "
                    "is usually well under that."))
            if (mimetype or '') not in UPLOAD_MIME_OK:
                raise UserError(_(
                    "Attach a PDF, a Word document or a photograph of the "
                    "signed letter."))
            attachment = self.env['ir.attachment'].sudo().create({
                'name': slug_filename(filename or 'signed-offer.pdf',
                                      fallback='signed-offer'),
                'datas': base64.b64encode(content),
                'mimetype': mimetype,
                'res_model': 'pb.hiring.offer',
                'res_id': self.id,
            })
        if not attachment:
            raise UserError(_(
                "Attach the copy they signed. Recording a signature with "
                "nothing behind it is the one thing this screen must never "
                "let anybody do."))
        self.sudo().write({
            'signed_attachment_id': attachment.id,
            'signed_on': signed_on or fields.Date.context_today(self),
            'signed_by_id': self.env.uid,
            'state': 'signed',
            # An offer can be signed without the page ever being opened — a
            # candidate who replied to the email and posted the letter back.
            # That IS an acceptance and the record should say so.
            'candidate_decision': 'accepted',
        })
        self.sudo().message_post(body=_(
            "Signed copy recorded. %s is a joiner.", self.candidate_name or ''))
        return True

    # ------------------------------------------------------------- the doors
    def action_open_pdf(self):
        self.ensure_one()
        if not self.attachment_id:
            self.action_prepare_letter()
        return {'type': 'ir.actions.act_url', 'target': 'new',
                'url': '/web/content/%s?download=true' % self.attachment_id.id}

    def action_open_requisition(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window',
                'res_model': 'pb.hiring.requisition',
                'res_id': self.requisition_id.id, 'view_mode': 'form',
                'views': [[False, 'form']],
                'name': self.requisition_id.display_name}

    def action_copy_link(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'info', 'sticky': True,
                       'title': _('Their own link'),
                       'message': self._token_url()},
        }


class PbHiringOfferLine(models.Model):
    """One number on the offer, with the word a candidate would use for it.

    The same shape as a pay-package line on purpose: at closure each of these
    becomes one, and a line that had to be re-typed on the way through would
    be a line somebody re-types wrongly.
    """
    _name = 'pb.hiring.offer.line'
    _description = 'Offer line'
    _order = 'sequence, id'

    offer_id = fields.Many2one('pb.hiring.offer', string='Offer',
                               required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(string='Order', default=10)
    name = fields.Char(string='What it is', required=True)
    kind = fields.Selection(OFFER_KINDS, string='Kind', default='earning',
                            required=True)
    amount = fields.Monetary(
        string='Amount', currency_field='currency_id',
        help='What the person gets. Enter a NEGATIVE amount for anything that '
             'comes off their pay — their own share of social insurance, for '
             'example — so the total is what they actually receive.')
    period = fields.Selection(OFFER_PERIODS, string='How often',
                              default='monthly', required=True)
    note = fields.Char(string='Note')
    annual_amount = fields.Monetary(
        string='A year of it', currency_field='currency_id',
        compute='_compute_annual', store=True, readonly=True)
    currency_id = fields.Many2one(related='offer_id.currency_id', store=True,
                                  readonly=True)
    company_id = fields.Many2one(related='offer_id.company_id', store=True,
                                 index=True, readonly=True)

    @api.depends('amount', 'period')
    def _compute_annual(self):
        for line in self:
            line.annual_amount = (line.amount or 0.0) * OFFER_PERIOD_YEAR.get(
                line.period or 'monthly', 12.0)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Offer line')
