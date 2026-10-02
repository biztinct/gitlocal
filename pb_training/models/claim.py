# -*- coding: utf-8 -*-
"""`pb.training.claim` — "I paid for a course, please pay me back".

THE ONE MONEY DOOR (ledger A2). A claim NEVER writes a payslip line and never
goes near one. When the HR lead agrees it, the claim raises a `pb.incentive` of
kind `training`, already approved, and stops — and that award rides the same
one-off pay-run lane (`pb.oneoff.feed`) every bonus and every recognition award
in this product rides, with the same refusal when the run's scheme has no
`INCENTV` component to put it on (R72). There is exactly one way money reaches
a payslip in Payobook and this is not a second one.

WHY THE AWARD IS CREATED ALREADY APPROVED. The claim IS the approval. It went
through the Approval Matrix, an HR lead put their name on it, and asking the
head of pay to agree the same amount a second time would be a route people
learn to click through. What is still a human act is PAYING it: somebody has to
put it into a pay run from the Awards lens, exactly like any other award, and
this phase never does that on anybody's behalf.

THE ALLOWANCE IS A RULE WITH A NAMED WAY ROUND IT. A claim over what is left of
the person's allowance is refused with the arithmetic in the sentence — how
much the allowance is, how much is already agreed, how much is left. A business
that wants to say yes anyway turns on `pb_training.claim_over_allowance`, and
the claim then carries a line in its own chatter saying that is what happened.
A rule with no exception is a rule people route around in email.

WHAT IS FROZEN WHEN IT IS AGREED (AM32): the amount and the two files. Never
`write_date`, and never the allowance — that is true of the world rather than
of the request, and a stamp over it would refuse a perfectly good approval the
day somebody raised next year's budget.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .training_common import (
    CLAIM_FULFILMENT, CLAIM_FULFILMENT_LABEL, CLAIM_STATES, CLAIM_STATE_LABEL,
    GROUP_MANAGER, INCENTIVE_KIND_TRAINING, P_CLAIM_OVER, as_id, flag, leg,
    money_words,
)

_logger = logging.getLogger(__name__)


class PbTrainingClaim(models.Model):
    _name = 'pb.training.claim'
    _description = 'Training cost claim'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'biz.approval.chain.mixin']
    #: PROBLEM FIRST (R113): what somebody is waiting on, newest first.
    _order = 'id desc'

    #: The ladder the record keeps for itself when no route is published. Under
    #: a published route the shim takes every press and the route decides the
    #: order (AM84); with nothing published this small ladder keeps the record
    #: usable, which is what makes the module installable on a database where
    #: training approvals were never switched on.
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): GROUP_MANAGER,
        ('submitted', 'refused'): GROUP_MANAGER,
        ('draft', 'refused'): None,
    }

    # ------------------------------------------------------------ what it is
    name = fields.Char(string='Reference', compute='_compute_name',
                       store=True, readonly=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Who paid for it', required=True, index=True,
        ondelete='cascade', tracking=True)
    assignment_id = fields.Many2one(
        'pb.training.assignment', string='The course they were put on',
        index=True, ondelete='set null',
        help='Only when the course was one of ours. A course somebody found '
             'and paid for themselves has no assignment, and that is the '
             'ordinary case for an outside course.')
    course_name = fields.Char(string='What the course was', required=True,
                              tracking=True)
    provider = fields.Char(string='Who ran it', tracking=True)
    amount = fields.Monetary(string='What it cost', required=True,
                             currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    paid_on = fields.Date(
        string='Paid on', required=True, tracking=True,
        default=fields.Date.context_today,
        help='The day they paid for it. This is what decides which year the '
             'claim counts against.')
    year = fields.Integer(string='Counts against', compute='_compute_year',
                          store=True, index=True, readonly=True)
    note = fields.Text(string='Anything they want to add')

    invoice_attachment_id = fields.Many2one(
        'ir.attachment', string='The receipt', ondelete='restrict',
        copy=False)
    certificate_attachment_id = fields.Many2one(
        'ir.attachment', string='The certificate', ondelete='restrict',
        copy=False)

    # THE UPLOAD BOXES ON THE BACKEND FORM, AND NOTHING MORE. The claim itself
    # is keyed on an ATTACHMENT (the employee's own page uploads one, the vault
    # copies one, and an attachment is what a file has to be to have a download
    # URL); a plain Many2one renders as a record selector, which asks somebody
    # in HR with a pile of receipts to create an attachment record by hand
    # before they can pick it. So these two are non-stored Binary fields with
    # an inverse that makes the attachment — the widget people expect, over the
    # storage the rest of the module needs.
    #
    # NON-STORED, so the bytes are not written twice, and `_compute` is only
    # ever asked for one record at a time on a form.
    invoice_file = fields.Binary(
        string='Receipt', compute='_compute_files', inverse='_inverse_invoice')
    invoice_filename = fields.Char(
        string='Receipt name', compute='_compute_files',
        inverse='_inverse_invoice')
    certificate_file = fields.Binary(
        string='Certificate', compute='_compute_files',
        inverse='_inverse_certificate')
    certificate_filename = fields.Char(
        string='Certificate name', compute='_compute_files',
        inverse='_inverse_certificate')

    state = fields.Selection(
        CLAIM_STATES, string='How far it has got', default='draft',
        required=True, index=True, tracking=True, copy=False)
    #: A SECOND COLUMN AND NOT MORE STATES (see the header): `state` answers
    #: "was it agreed", this answers "has the money moved". It follows the
    #: award rather than guessing, and it is stored so a board can search it.
    fulfilment = fields.Selection(
        CLAIM_FULFILMENT, string='Where the money has got to', copy=False,
        index=True, tracking=True)
    incentive_id = fields.Many2one(
        'pb.incentive', string='The award it became', readonly=True,
        copy=False, ondelete='set null', index=True)
    over_allowance = fields.Boolean(
        string='Agreed over the allowance', readonly=True, copy=False,
        help='Ticked when this claim was allowed through even though it is '
             'more than the person had left. The chatter says who allowed it.')
    refuse_note = fields.Text(string='Why it was turned down', copy=False)
    decided_on = fields.Datetime(string='Answered on', readonly=True,
                                 copy=False)
    submitted_on = fields.Datetime(string='Sent in on', readonly=True,
                                   copy=False)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)

    # =====================================================================
    #  computes
    # =====================================================================
    @api.depends('paid_on')
    def _compute_year(self):
        for rec in self:
            rec.year = rec.paid_on.year if rec.paid_on \
                else fields.Date.today().year

    @api.depends('employee_id', 'course_name', 'paid_on')
    def _compute_name(self):
        for rec in self:
            who = rec.employee_id.sudo().name or _('Somebody')
            rec.name = '%s — %s' % (who, rec.course_name or _('a course'))

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Training claim')

    @api.depends('invoice_attachment_id', 'certificate_attachment_id')
    def _compute_files(self):
        """Read the two attachments back into the upload boxes.

        AS THE SYSTEM. The person reading their own claim on the backend form
        holds no permission on this table's attachments and is not going to be
        given one; the narrowing is that the attachment is the one this claim
        points at.
        """
        for rec in self:
            invoice = rec.invoice_attachment_id.sudo()
            certificate = rec.certificate_attachment_id.sudo()
            rec.invoice_file = invoice.datas if invoice else False
            rec.invoice_filename = invoice.name if invoice else False
            rec.certificate_file = certificate.datas if certificate else False
            rec.certificate_filename = certificate.name if certificate \
                else False

    def _inverse_invoice(self):
        for rec in self:
            rec._store_file('invoice_attachment_id', rec.invoice_file,
                            rec.invoice_filename, _('Receipt'))

    def _inverse_certificate(self):
        for rec in self:
            rec._store_file('certificate_attachment_id',
                            rec.certificate_file, rec.certificate_filename,
                            _('Certificate'))

    def _store_file(self, field, data, filename, fallback):
        """One uploaded file, as an attachment bound to this claim.

        A NEW ATTACHMENT EACH TIME AND THE OLD ONE LEFT ALONE. Rewriting the
        existing row's bytes would silently change what an approver already
        agreed to — the approval's own revision stamp names the attachment id
        (AM32), so replacing the file must produce a new id and re-open the
        decision rather than quietly swapping the evidence underneath it.
        """
        self.ensure_one()
        if not data:
            return
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename or fallback,
            'datas': data,
            'res_model': self._name,
            'res_id': self.id,
        })
        self.sudo().write({field: attachment.id})

    # =====================================================================
    #  sanity
    # =====================================================================
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_(
                    "A claim needs an amount above zero."))

    @api.constrains('paid_on')
    def _check_paid_on(self):
        """A receipt from next March is a typo, not a claim.

        THE SERVER'S CLOCK AND NEVER `context_today` (R154): a date that
        decides whether something is allowed must not change with the time
        zone of whoever is looking at it.
        """
        today = fields.Date.today()
        for rec in self:
            if rec.paid_on and rec.paid_on > today:
                raise ValidationError(_(
                    "That date is in the future. Claim for a course after you "
                    "have paid for it."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('company_id') and vals.get('employee_id'):
                emp = self.env['hr.employee'].sudo().browse(
                    vals['employee_id'])
                vals['company_id'] = (emp.company_id or self.env.company).id
            if not vals.get('currency_id') and vals.get('company_id'):
                company = self.env['res.company'].sudo().browse(
                    vals['company_id'])
                vals['currency_id'] = company.currency_id.id
        return super().create(vals_list)

    # =====================================================================
    #  the allowance arithmetic — ONE answer, used everywhere
    # =====================================================================
    def _allowance_facts(self, extra=None):
        """(allowance, agreed, left, currency) for this claim's person/year.

        `extra` is the claim being weighed, which is deliberately NOT counted
        as already agreed: the question is "would this fit", and a claim that
        counted itself would always be over.

        AS THE SYSTEM. The person whose allowance it is holds no training
        permission and has to see their own remaining budget on their own
        page; every search below names the employee and the year explicitly,
        so the narrowing is visible rather than assumed.
        """
        self.ensure_one()
        return self._facts_for(self.employee_id, self.year,
                               skip_claim=self, currency=self.currency_id)

    @api.model
    def _facts_for(self, employee, year, skip_claim=None, currency=None):
        emp_id = as_id(employee)
        Allowance = self.env['pb.training.allowance']
        allowance, cur = Allowance.amount_for(emp_id, year)
        currency = currency or cur
        domain = [
            ('employee_id', '=', emp_id),
            ('year', '=', int(year or fields.Date.today().year)),
            ('state', '=', 'approved'),
        ]
        if skip_claim:
            domain.append(('id', '!=', skip_claim.id))
        agreed = sum(self.sudo().search(domain).mapped('amount'))
        return {
            'allowance': allowance,
            'agreed': agreed,
            'left': max(allowance - agreed, 0.0),
            'over': agreed > allowance,
            'currency': currency,
            'year': int(year or fields.Date.today().year),
        }

    def _allowance_problem(self):
        """The sentence that refuses this claim, or ''.

        THE WHOLE SENTENCE WITH THE ARITHMETIC IN IT (R117). "Over your
        allowance" is a refusal somebody has to email about; "your allowance
        for 2026 is 5,000,000 ₫, 4,000,000 ₫ is already agreed, so there is
        1,000,000 ₫ left" is a refusal they can act on.
        """
        self.ensure_one()
        if flag(self.env, P_CLAIM_OVER):
            return ''
        facts = self._allowance_facts()
        env = self.env
        cur = facts['currency']
        if not facts['allowance']:
            return _(
                "No training allowance has been set for %(year)s, so there is "
                "nothing to claim against yet. Ask the training team to set "
                "one.", year=facts['year'])
        if self.amount <= facts['left']:
            return ''
        return _(
            "That is more than is left. The allowance for %(year)s is "
            "%(allowance)s, %(agreed)s of it is already agreed, so %(left)s is "
            "left and this claim is %(asked)s.",
            year=facts['year'],
            allowance=money_words(env, facts['allowance'], cur),
            agreed=money_words(env, facts['agreed'], cur),
            left=money_words(env, facts['left'], cur),
            asked=money_words(env, self.amount, cur))

    # =====================================================================
    #  the ladder
    # =====================================================================
    def _before_approval_transition(self, to_state):
        res = super()._before_approval_transition(to_state)
        if to_state == 'submitted':
            self._check_ready()
            problem = self._allowance_problem()
            if problem:
                raise UserError(problem)
        return res

    def _check_ready(self):
        """BOTH FILES OR IT DOES NOT GO IN.

        A claim with no receipt is a number somebody typed, and a claim with no
        certificate is a course nobody can say was finished. The refusal names
        which one is missing — "attachments required" is a sentence written by
        a programme.
        """
        self.ensure_one()
        if not self.invoice_attachment_id and not self.certificate_attachment_id:
            raise UserError(_(
                "Attach the receipt and the certificate before you send it "
                "in. Without them there is nothing to agree to."))
        if not self.invoice_attachment_id:
            raise UserError(_(
                "The receipt is missing. Attach what you paid — an invoice, a "
                "card receipt or the confirmation email will do."))
        if not self.certificate_attachment_id:
            raise UserError(_(
                "The certificate is missing. Attach the certificate or the "
                "letter that says you finished the course."))
        return True

    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        for rec in self:
            if to_state == 'submitted':
                rec.sudo().write({'submitted_on': fields.Datetime.now()})
            elif to_state == 'approved':
                # EACH PIECE OF PAPERWORK INSIDE ITS OWN SAVEPOINT (R131). A
                # try/except is not enough when the thing that failed reached
                # the database: Postgres aborts the whole transaction and the
                # approval itself would be undone by a failing email.
                rec.sudo().write({'decided_on': fields.Datetime.now()})
                leg(self.env, 'note an over-allowance approval',
                    rec._note_over_allowance)
                leg(self.env, 'raise the award', rec._make_award)
                leg(self.env, 'file the certificate', rec._file_certificate)
                leg(self.env, 'tell them it was agreed',
                    lambda rec=rec: rec._tell(
                        'pb_training.mail_template_claim_approved'))
            elif to_state == 'refused':
                rec.sudo().write({'decided_on': fields.Datetime.now()})
                leg(self.env, 'tell them it was turned down',
                    lambda rec=rec: rec._tell(
                        'pb_training.mail_template_claim_refused'))
        return res

    def _note_over_allowance(self):
        """Say, on the record, that a rule was set aside and by whom."""
        self.ensure_one()
        if not flag(self.env, P_CLAIM_OVER):
            return False
        facts = self._facts_for(self.employee_id, self.year, skip_claim=self,
                                currency=self.currency_id)
        if self.amount <= facts['left']:
            return False
        self.sudo().write({'over_allowance': True})
        self.message_post(body=_(
            "Agreed even though it is over the allowance. %(left)s was left "
            "of %(allowance)s for %(year)s and this claim is %(asked)s.",
            left=money_words(self.env, facts['left'], facts['currency']),
            allowance=money_words(self.env, facts['allowance'],
                                  facts['currency']),
            year=facts['year'],
            asked=money_words(self.env, self.amount, self.currency_id)))
        _logger.info('pb_training: claim %s was agreed over the allowance '
                     '(%s of %s left) by uid %s', self.id, facts['left'],
                     facts['allowance'], self.env.uid)
        return True

    # =====================================================================
    #  the money door
    # =====================================================================
    def _make_award(self):
        """Turn an agreed claim into ONE award on the one-off pay-run lane.

        `period_month` IS THE MONTH IT WAS AGREED IN, and that is the rule the
        awards lane already keeps (R81): the lane's own "Put this month into a
        pay run" dialog picks by the RUN's month, so an award dated the month
        it was decided is the one that turns up in the dialog people press.
        The claim's own `paid_on` can be nine months old and is not a pay
        instruction.

        IDEMPOTENT. A claim that already has an award never raises a second
        one — an approval that ran twice is an approval, not two payments.
        """
        self.ensure_one()
        if self.incentive_id:
            return False
        if 'pb.incentive' not in self.env:
            _logger.info('pb_training: claim %s was agreed but the awards '
                         'lane is not installed on this database', self.id)
            return False
        today = fields.Date.today()
        award = self.env['pb.incentive'].sudo().create({
            'employee_id': self.employee_id.id,
            'kind': INCENTIVE_KIND_TRAINING,
            'amount': self.amount,
            'currency_id': self.currency_id.id,
            'period_month': today.replace(day=1),
            'reason': _("Training claim #%(n)s — %(course)s%(who)s",
                        n=self.id, course=self.course_name or '',
                        who=(', %s' % self.provider) if self.provider else ''),
            # CREATED ALREADY AGREED, and the mixin allows it because this runs
            # as the system: `biz.approval.chain.mixin.create` strips `state`
            # from anybody else's hands, so no browser can mint an approved
            # award by calling create. The claim IS the approval (see header).
            'state': 'approved',
            'fulfilment': 'pending',
            'company_id': self.company_id.id,
        })
        self.sudo().write({'incentive_id': award.id, 'fulfilment': 'pending'})
        award.message_post(body=_(
            "Raised from training claim #%(n)s: %(course)s.", n=self.id,
            course=self.course_name or ''))
        self.message_post(body=_(
            "Agreed. It is now an award waiting for a pay run — the pay team "
            "puts it into one from the Awards screen."))
        _logger.info('pb_training: claim %s became award %s (%s %s)', self.id,
                     award.id, self.amount, self.currency_id.name)
        return True

    def refresh_fulfilment(self):
        """Follow the award: agreed → in a pay run → paid.

        THE CLAIM NEVER DECIDES THIS. The awards lane flips its own rows to
        `queued` when somebody puts them into a run and to `paid` when the
        payment release goes through (R70) — this copies the answer across so
        the person's own page can say "paid" without a second opinion about
        what paid means.
        """
        moved = 0
        for rec in self:
            award = rec.incentive_id.sudo()
            if not award:
                continue
            want = award.fulfilment if award.fulfilment in \
                dict(CLAIM_FULFILMENT) else 'pending'
            if want != rec.fulfilment:
                rec.sudo().with_context(
                    tracking_disable=True, mail_notrack=True).write(
                    {'fulfilment': want})
                moved += 1
        return moved

    # =====================================================================
    #  the certificate
    # =====================================================================
    def _file_certificate(self):
        """Put the uploaded certificate in the employee's own document vault.

        FILED AS THE SYSTEM, and that is the only way it can be done: the
        vault gates a self-served create on an attachment the CALLER owns
        (`employee_document.py:114-135`), and the person filing this is the HR
        lead rather than the person who uploaded it. Idempotent per claim, so
        an approval that ran twice files one document.
        """
        self.ensure_one()
        return self.env['pb.training.certificate'].file_claim_certificate(self)

    # =====================================================================
    #  telling people
    # =====================================================================
    def _tell(self, xmlid):
        """Queue one email, addressed EXPLICITLY (R6).

        A template's own rendered `email_to` can reach `mail.mail` empty, with
        no error anywhere — the message is created, queued and addressed to
        nobody, and the count claims somebody was told.
        """
        self.ensure_one()
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            _logger.warning('pb_training: %s is missing', xmlid)
            return False
        emp = self.employee_id.sudo()
        to = (emp.work_email or '').strip() or (emp.user_id.email or '').strip()
        if not to:
            _logger.info('pb_training: claim %s has nobody to write to',
                         self.id)
            return False
        template.sudo().send_mail(
            self.id, force_send=False,
            email_values={'email_to': to, 'auto_delete': False})
        return True

    # =====================================================================
    #  the buttons on the record's own form
    # =====================================================================
    # UNDER A PUBLISHED ROUTE THESE SAY WHAT SOMEBODY MEANS AND THE ENGINE
    # SAYS WHETHER IT MAY HAPPEN (AM84).
    def action_submit(self):
        for rec in self:
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

    def action_open_invoice(self):
        self.ensure_one()
        return self._attachment_door(self.invoice_attachment_id)

    def action_open_certificate(self):
        self.ensure_one()
        return self._attachment_door(self.certificate_attachment_id)

    def _attachment_door(self, attachment):
        if not attachment:
            raise UserError(_("There is no file on this claim."))
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }

    # =====================================================================
    #  the door the employee's own page uses
    # =====================================================================
    @api.model
    def raise_claim(self, values, invoice=None, certificate=None):
        """Make one and send it in, in a single press.

        A DRAFT NOBODY SENDS IN IS A CLAIM THAT WAS NEVER MADE — the same rule
        the request for more time keeps. The employee page has one form and
        one button, so the record is created and submitted in the same call,
        and a refusal (no files, over the allowance) leaves NOTHING behind:
        the whole thing is inside one savepoint, so a half-made claim can
        never sit on somebody's page waiting for an answer nobody was asked
        for.

        `invoice` / `certificate` are `(filename, bytes)` pairs. They are
        written as attachments bound to the claim, as the system, because the
        person claiming holds no permission on this table's attachments and
        should not be given one.
        """
        emp = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if not emp:
            raise AccessError(_(
                "You do not have an employee record yet, so there is nothing "
                "to pay a claim into. Tell your HR team."))
        vals = dict(values or {})
        vals.update({
            'employee_id': emp.id,
            'company_id': (emp.company_id or self.env.company).id,
        })
        # NOTHING THE FORM SENDS DECIDES WHO IT IS FOR OR WHAT STATE IT IS IN.
        for forbidden in ('state', 'fulfilment', 'incentive_id',
                          'over_allowance', 'assignment_id'):
            vals.pop(forbidden, None)
        assignment = self._own_assignment(emp, values.get('assignment_id'))
        if assignment:
            vals['assignment_id'] = assignment.id
        with self.env.cr.savepoint():
            claim = self.sudo().create(vals)
            claim._attach(invoice, 'invoice_attachment_id')
            claim._attach(certificate, 'certificate_attachment_id')
            claim._advance_state('submitted')
        return {'id': claim.id, 'state': claim.state,
                'message': _("Sent in. The HR lead sees it now, and you will "
                             "get an email either way.")}

    @api.model
    def _own_assignment(self, employee, assignment_id):
        """An assignment id from a form buys nothing unless it is theirs."""
        row = self.env['pb.training.assignment'].sudo().browse(
            as_id(assignment_id)).exists()
        if row and row.employee_id.id == employee.id:
            return row
        return self.env['pb.training.assignment'].sudo().browse()

    def _attach(self, upload, field):
        """One uploaded file, bound to this claim, as the system."""
        self.ensure_one()
        if not upload:
            return False
        name, content = upload
        if not content:
            return False
        attachment = self.env['ir.attachment'].sudo().create({
            'name': name or _('File'),
            'raw': content,
            'res_model': self._name,
            'res_id': self.id,
        })
        self.sudo().write({field: attachment.id})
        return attachment

    # =====================================================================
    #  what a screen reads
    # =====================================================================
    def _payload(self):
        """One claim, as a row on a board or a card on a phone."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        return {
            'id': self.id,
            'who': emp.name or '',
            'employee_id': emp.id,
            'department': emp.department_id.name or '',
            'course': self.course_name or '',
            'provider': self.provider or '',
            'amount': self.amount or 0.0,
            'amount_words': money_words(self.env, self.amount,
                                        self.currency_id),
            'currency': self.currency_id.name or '',
            'paid_on': fields.Date.to_string(self.paid_on) or '',
            'year': self.year,
            'note': self.note or '',
            'state': self.state,
            'state_word': CLAIM_STATE_LABEL.get(self.state, ''),
            'fulfilment': self.fulfilment or '',
            'fulfilment_word': CLAIM_FULFILMENT_LABEL.get(
                self.fulfilment or '', ''),
            'over_allowance': bool(self.over_allowance),
            'refuse_note': self.refuse_note or '',
            'has_invoice': bool(self.invoice_attachment_id),
            'has_certificate': bool(self.certificate_attachment_id),
            'invoice_url': '/web/content/%s?download=true'
                           % self.invoice_attachment_id.id
                           if self.invoice_attachment_id else '',
            'certificate_url': '/web/content/%s?download=true'
                               % self.certificate_attachment_id.id
                               if self.certificate_attachment_id else '',
            'incentive_id': self.incentive_id.id,
            'submitted_on': fields.Datetime.to_string(self.submitted_on) or '',
        }
