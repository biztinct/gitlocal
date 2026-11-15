# -*- coding: utf-8 -*-
"""WDGAP S6-A — an employee changes their own bank account from My Payobook.

THE SAME CHECK, A DIFFERENT DOOR. The request is the ordinary bank-document
check (`pb.bank.change.request`): the document is read, the number, the bank
and the holder's name are checked, duplicates are looked for in BOTH places
bank details are kept, and the approved change is written by the one path
that writes them (`_apply_to_master`).

THE SAME PEOPLE AS THE UPDATES SHEET (FACTS §10 design default; UPDATES
D13–D15; owner ruling BK1, 2026-11-16: "nobody can change where pay goes
alone, whichever screen they use"). EVERY bank change — started on My
Payobook or typed by HR on the staff bank screen — travels the "Bank details
from Records and Updates" route (`records_bank`, pb_records) when it exists:
ONE second person, never the person who proposed (typed) it nor the person
it is about, never a self-service, support or demo login, on rize the
people that route names, and the route's own independence setting as each
database has it. Without pb_records the record keeps its own route.
Fail-closed: a change is never written without a second person's yes, even
on a route that says "No approval needed".

ALREADY ON THEIR WAY. A request sent in before BK1 travels the old two-step
`bankchange` route; it keeps the rules it was sent under
(`_pb_second_person_rule`). Bank details already on record are untouched.

THE PORTAL ENTRY. `pb_portal_start` is the only way in for an employee login
(which holds no right on this model): the caller passes the SESSION's
employee and the uploaded bytes; this method makes the attachment itself (so
no attachment id ever comes from a browser — `_extract` reads attachments as
superuser), forces the employee and the company, and reads the document.
"""

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

RECORDS_BANK_KEY = 'records_bank'
NAMED_WHO_MODES = ('people', 'team')

#: What an employee may type on their own request while it is a draft.
PORTAL_FIELDS = ('x_bank_name', 'x_bank_branch', 'x_account_name',
                 'x_account_number', 'doc_kind')
UPLOAD_MIMES = ('application/pdf', 'image/png', 'image/jpeg')
UPLOAD_MAX = 10 * 1024 * 1024


class PbBankChangeRequestSelfService(models.Model):
    _inherit = 'pb.bank.change.request'

    pb_origin = fields.Selection([
        ('staff', 'Staff screen'),
        ('self_service', 'My Payobook'),
    ], string='Started from', default='staff', readonly=True, copy=False)
    proposed_by_id = fields.Many2one(
        'res.users', string='Proposed by', readonly=True, copy=False,
        default=lambda self: self.env.user)
    pb_decision_note = fields.Text(
        string='Reason given', readonly=True, copy=False,
        help='What the approver wrote when they sent it back or turned it '
             'down. The employee sees it on My Payobook.')

    # ================================================================ route
    def _pb_self_service(self):
        self.ensure_one()
        return self.pb_origin == 'self_service'

    def _pb_records_bank_process(self):
        return self.env['biz.approval.process'].sudo()._by_key(RECORDS_BANK_KEY)

    def _pb_second_person_rule(self):
        """BK1: every bank change needs one second person — except a request
        already sent in on the old two-step `bankchange` route before the
        ruling, which keeps the rules it was sent under (a request is never
        changed under somebody's feet)."""
        self.ensure_one()
        request = self.sudo().approval_request_id
        if request and request.state in ('pending', 'blocked', 'approved', 'applied') \
                and request.process_id.key != RECORDS_BANK_KEY:
            return False
        return True

    def _approval_process_key_for(self):
        self.ensure_one()
        if self._pb_records_bank_process():
            return RECORDS_BANK_KEY
        return super()._approval_process_key_for()

    def _engine_managed(self):
        """The question is asked of the route the request actually travels
        (the Updates bank route), not of `bankchange`."""
        self.ensure_one()
        process = self._pb_records_bank_process()
        if not process:
            return super()._engine_managed()
        return bool(self.env['biz.approval.binding'].sudo().search_count([
            ('company_id', '=', self._chain_company().id),
            ('process_id', '=', process.id),
            ('active', '=', True),
        ]))

    # ======================================================= who never decides
    def _pb_proposer(self):
        self.ensure_one()
        return self.sudo().proposed_by_id or self.sudo().create_uid

    def _pb_never_decide(self):
        """The proposer and the person the account belongs to."""
        self.ensure_one()
        rec = self.sudo()
        return (rec._pb_proposer() | rec.employee_id.user_id).filtered('id')

    def _pb_excluded(self, user):
        """'' when `user` may decide a bank change; else why not. The
        Updates rule when pb_records is installed (self-service, support and
        demo logins); otherwise a self-service login never decides."""
        user = user.sudo()
        if not user:
            return ''
        if 'pb.records.apply' in self.env:
            return self.env['pb.records.apply']._bank_excluded(user)
        return 'self_service' if user.share else ''

    def _approval_step_people(self, step, people, issue, ctx, company):
        """Opt-in engine hook (pb_records/models/records_engine.py).

        Every bank change: a login that may never decide bank details is
        never seated. A My Payobook change: the proposer and the person it is
        about are never seated either (their backup stands in); when the
        route names nobody else the request waits and says why; when it
        names a role nobody else holds, the Updates rule finds the second
        person (Finance, else a records manager).
        """
        self.ensure_one()
        rec = self.sudo()
        engine = self.env['biz.approval.engine']
        rule = rec._pb_second_person_rule()
        never = rec._pb_never_decide() if rule else self.env['res.users']
        keep = []
        for person in people or []:
            uid = person.get('user_id')
            if uid not in never.ids:
                keep.append(person)
                continue
            backup = person.get('backup_user_id')
            if backup and backup not in never.ids:
                keep += engine._people_payload(
                    [backup], _("Backup for %s, who cannot approve their "
                                "own bank details", person.get('name') or ''))
        users = self.env['res.users'].sudo().browse(
            [p['user_id'] for p in keep]).exists()
        allowed = set(users.filtered(lambda u: not rec._pb_excluded(u)).ids)
        keep = [p for p in keep if p.get('active', True)
                and p['user_id'] in allowed]
        if keep or not rule:
            if keep:
                blocking = issue and issue.get('level') == 'block'
                return keep, (None if blocking else issue)
            return keep, issue
        if ((step or {}).get('who') or {}).get('mode') in NAMED_WHO_MODES:
            return [], {'level': 'block', 'code': 'no_second_person',
                        'msg': _("Waiting for a second person. Nobody else "
                                 "named to approve bank details in %s can "
                                 "approve this yet — add a person to the bank "
                                 "details route in Settings › Approval Matrix.",
                                 company.name),
                        'fixes': []}
        if 'pb.records.apply' in self.env:
            found, via = self.env['pb.records.apply'].sudo()._second_people(
                company, rec._pb_proposer())
            found = found - never
            if found:
                return engine._people_payload(found.ids, via), None
        return [], {'level': 'block', 'code': 'no_second_person',
                    'msg': _("Waiting for a second person. Nobody else in %s "
                             "can approve bank details yet — add one in "
                             "Access.", company.name),
                    'fixes': []}

    def _approval_may_decide(self, request, user):
        """Opt-in engine hook: a sentence when `user` may not APPROVE."""
        self.ensure_one()
        rec = self.sudo()
        if rec._pb_second_person_rule() and user in rec._pb_never_decide():
            return _("Bank details need a second person. You cannot approve a "
                     "change to your own bank account, or one you proposed.")
        if rec._pb_excluded(user):
            return _("This login cannot approve bank details. One of the "
                     "company's own people has to approve them.")
        return None

    def _pb_second_person_approved(self):
        """Somebody who may decide bank details, other than the proposer and
        the account's owner, approved the open (or last) request."""
        self.ensure_one()
        rec = self.sudo()
        never = rec._pb_never_decide()
        request = rec.approval_request_id
        if not request:
            # The record's own ladder (no route at all): the person pressing
            # the last button is the second person, if they may be one.
            user = self.env.user
            return bool(not self.env.su and user not in never
                        and not rec._pb_excluded(user))
        return bool(request.decision_ids.filtered(
            lambda d: d.action == 'approve' and d.user_id
            and d.user_id not in never and not rec._pb_excluded(d.user_id)))

    def _before_approval_transition(self, to_state):
        if to_state == 'approved':
            for rec in self:
                if rec._pb_second_person_rule() \
                        and not rec._pb_second_person_approved():
                    raise UserError(_(
                        "Bank details need a second person. Nobody other than "
                        "the person who asked for this change has approved "
                        "it, so nothing was written."))
        return super()._before_approval_transition(to_state)

    def _approval_apply(self, request):
        """Carried out under sudo (ledger W2B-2): the engine runs this as the
        person who decided last, and a named approver of the Updates bank
        route may hold no payroll group — reading the request and posting
        its note must not fail the change. `sudo()` keeps the uid, so the
        history row still names them."""
        self.ensure_one()
        return super(PbBankChangeRequestSelfService, self.sudo())._approval_apply(
            request)

    # ================================================= what the person reads
    # Sent back / turned down: the engine runs these as the deciding person,
    # who may hold only a READ seat (a named approver of the Updates bank
    # route) — so the record's own writes run under sudo (ledger W2B-2).
    def _approval_return(self, request, reason):
        self.ensure_one()
        rec = self.sudo()
        rec._sys_write({'pb_decision_note': reason or False})
        return super(PbBankChangeRequestSelfService, rec)._approval_return(
            request, reason)

    def _approval_reject(self, request, reason):
        self.ensure_one()
        rec = self.sudo()
        rec._sys_write({'pb_decision_note': reason or False})
        return super(PbBankChangeRequestSelfService, rec)._approval_reject(
            request, reason)

    def _approval_withdraw(self, request, reason):
        """Taken back by the employee: a draft again (the shim does not
        mirror a withdrawal on the record). Its own savepoint (QF3-6)."""
        self.ensure_one()
        rec = self.sudo()
        with self.env.cr.savepoint():
            if rec.state in ('hr_review', 'finance_review'):
                frm = rec.state
                rec._chain_engine_write('draft')
                rec._chain_log(frm, 'draft', reason or '')
        return True

    # ======================================================= the portal door
    @api.model
    def pb_portal_start(self, employee, data, filename, mimetype, doc_kind='other'):
        """Start a bank change for `employee` — the caller's OWN employee,
        resolved from the session. `data` is the uploaded file's bytes.
        Returns the request (sudo). Raises UserError with a plain sentence."""
        employee = employee.sudo()
        if not employee or employee.user_id != self.env.user:
            raise AccessError(_("You can only change your own bank details."))
        if not data:
            raise UserError(_("Choose the bank document to upload."))
        if len(data) > UPLOAD_MAX:
            raise UserError(_("The file is larger than 10 MB. Try a smaller "
                              "copy, or a photo of the page."))
        if (mimetype or '') not in UPLOAD_MIMES:
            raise UserError(_("The file can be a PDF, JPG or PNG."))
        if doc_kind not in dict(self._fields['doc_kind'].selection):
            doc_kind = 'other'
        open_one = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('pb_origin', '=', 'self_service'),
            ('state', 'in', ('hr_review', 'finance_review'))], limit=1)
        if open_one:
            raise UserError(_("A change to your bank account is already "
                              "waiting for approval. Take it back first if "
                              "you want to send a different one."))
        att = self.env['ir.attachment'].sudo().create({
            'name': filename or _('Bank document'),
            'datas': base64.b64encode(data),
            'mimetype': mimetype,
        })
        req = self.sudo().create({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'attachment_id': att.id,
            'doc_kind': doc_kind,
            'pb_origin': 'self_service',
            'proposed_by_id': self.env.uid,
        })
        att.write({'res_model': req._name, 'res_id': req.id})
        try:
            with self.env.cr.savepoint():
                req.action_run_ocr()
        except Exception:                   # noqa: BLE001 — typed by hand then
            _logger.info('pb_bank_ocr: the document of request %s could not be '
                         'read; the employee types the details', req.id,
                         exc_info=True)
            req._sys_write({'ocr_state': 'failed'})
            req.action_validate()
        return req

    def pb_portal_update(self, values):
        """The employee corrects what was read, while it is a draft."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'draft':
            raise UserError(_("This change is already sent. Take it back first "
                              "to change it."))
        vals = {}
        for key in PORTAL_FIELDS:
            if key in values:
                vals[key] = (values.get(key) or '').strip() or False
        if vals.get('doc_kind') and vals['doc_kind'] not in dict(
                self._fields['doc_kind'].selection):
            vals.pop('doc_kind')
        if vals:
            rec.write(vals)
            rec.action_validate()
        return rec

    def action_submit(self):
        """BK1: HR's staff bank screen sends through the same route; a
        company that has none yet gets the shipped "a second person" one."""
        for rec in self:
            rec._pb_ensure_route()
        return super().action_submit()

    def _pb_ensure_route(self):
        """A company with no Updates bank route yet gets the shipped one ("a
        second person") before the first change is sent."""
        self.ensure_one()
        if self._engine_managed() or 'pb.records.apply' not in self.env:
            return
        try:
            with self.env.cr.savepoint():
                self.env['pb.records.apply'].sudo()._approval_seed_bank(
                    self.company_id)
        except Exception:                   # noqa: BLE001 — never block a send
            _logger.warning('pb_bank_ocr: no bank route could be laid for %s',
                            self.company_id.name, exc_info=True)

    def pb_portal_send(self):
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'draft':
            raise UserError(_("This change is already sent."))
        if not rec.x_account_number:
            raise UserError(_("Type the account number before sending."))
        if rec.duplicate_ids and not rec.duplicate_ack:
            raise UserError(_("This account number is already on file for "
                              "somebody else, so it cannot be sent from here. "
                              "Ask HR to check it with you."))
        rec._pb_ensure_route()
        rec._sys_write({'pb_decision_note': False})
        rec.action_submit()
        rec.invalidate_recordset()
        return rec

    def pb_portal_withdraw(self):
        self.ensure_one()
        rec = self.sudo()
        if rec.state in ('approved', 'refused'):
            raise UserError(_("This change is already decided, so it cannot be "
                              "taken back."))
        if rec.state == 'draft':
            return False
        request = rec._chain_open_request()
        if request:
            self.env['biz.approval.engine'].sudo().cancel(
                request, _("Taken back by %s", rec.employee_id.name or ''))
        else:
            rec._approval_withdraw(None, '')
        rec.invalidate_recordset()
        return True

    def pb_portal_view(self):
        """What the employee's page shows — masked, in plain words."""
        self.ensure_one()
        rec = self.sudo()
        sent_back = rec.state == 'draft' and bool(rec.pb_decision_note)
        checks = []
        if rec.x_account_number:
            checks.append({'ok': bool(rec.v_format_ok),
                           'text': _("The account number looks right")
                           if rec.v_format_ok else (rec.v_format_msg or '')})
        if rec.name_match_band:
            checks.append({'ok': rec.name_match_band == 'green',
                           'text': {
                               'green': _("The name on the account matches "
                                          "yours"),
                               'amber': _("The name on the account is close to "
                                          "yours; the approver will look at it"),
                               'red': _("The name on the account does not look "
                                        "like yours; the approver will ask "
                                        "about it"),
                           }[rec.name_match_band]})
        if rec.duplicate_ids:
            checks.append({'ok': False,
                           'text': _("This account number is already on file "
                                     "for somebody else")})
        return {
            'id': rec.id,
            'name': rec.name,
            'state': 'sent_back' if sent_back else rec.state,
            'bank': rec.x_bank_name or '',
            'branch': rec.x_bank_branch or '',
            'holder': rec.x_account_name or '',
            'number': rec.x_account_number or '',
            'masked': rec._masked_account(rec.x_account_number),
            'current_masked': rec._masked_account(
                rec.cur_account_number or rec.employee_id.vietnam_bank_account_number),
            'read_ok': rec.ocr_state == 'done',
            'checks': checks,
            'note': rec.pb_decision_note or '',
            'doc_kind': rec.doc_kind,
            'created': rec.create_date,
        }
