# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Bank-change request lifecycle (Phase D §3.3).

Upload a bank document → OCR extraction (advisory) → deterministic validation
(format, duplicates, name similarity) → Employee → HR → Finance approval → an
ATOMIC, context-flagged write to the employee master + a history row.

Human-in-the-loop absolutes (safety rail 1): nothing advances without a click;
extraction/validation NEVER writes the master; only the finance-tier approval
does, through the from_bank_request path.
"""

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .pb_employee_bank_history import _BANK_AUDIT_TOKEN
from .vn_bank_dictionary import (
    fold, name_similarity, extract_account_number, swift_ok, account_ok,
)

_logger = logging.getLogger(__name__)

# Finance tier resolution chain (env.ref fallback — same doctrine as Phase C
# tier 3; a demo must never dead-end because the ideal group isn't installed).
_FINANCE_GROUPS = ('account.group_account_invoice', 'account.group_account_user',
                   'om_hr_payroll.group_hr_payroll_manager')
_HR_GROUP = 'om_hr_payroll.group_hr_payroll_user'

_MASTER_FIELDS = (
    ('x_bank_name', 'vietnam_bank_name'),
    ('x_bank_branch', 'vietnam_bank_branch'),
    ('x_account_name', 'vietnam_bank_account_name'),
    ('x_account_number', 'vietnam_bank_account_number'),
)

# C18.24: readonly=True does NOT block call_kw writes, and the approvers
# approve exactly what these fields show — every system-derived field is
# sentinel-gated (a Python object() identity a JSON client cannot forge).
_BANK_SYS_TOKEN = object()

# System-computed: writable only via _sys_write (or su / admin).
_SYS_FIELDS = frozenset({
    'name', 'ocr_state', 'ocr_provider', 'ocr_raw', 'confidence_json',
    'cur_bank_name', 'cur_bank_branch', 'cur_account_name',
    'cur_account_number', 'v_format_ok', 'v_format_msg', 'name_match_score',
    'name_match_band', 'duplicate_ids', 'resolved_bank_id',
})
# What the approvers review: frozen to the owner once the request leaves
# draft (HR/finance may still correct the extraction during review), and
# immutable for everyone once decided.
_REVIEW_FIELDS = frozenset({
    'x_bank_name', 'x_bank_branch', 'x_account_name', 'x_account_number',
    'x_iban', 'x_swift', 'doc_kind', 'attachment_id', 'employee_id',
})


class PbBankChangeRequest(models.Model):
    _name = 'pb.bank.change.request'
    _description = 'Bank Account Change Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True,
        default=lambda self: self.env.user.employee_id)
    attachment_id = fields.Many2one(
        'ir.attachment', string='Document', required=True)
    doc_kind = fields.Selection([
        ('confirmation_letter', 'Bank Confirmation Letter'),
        ('statement', 'Bank Statement'),
        ('passbook', 'Passbook'),
        ('cheque', 'Cancelled Cheque'),
        ('other', 'Other'),
    ], string='Document Kind', default='other')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('hr_review', 'HR Review'),
        ('finance_review', 'Finance Review'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Status', default='draft', tracking=True, index=True, copy=False)

    # --- OCR ---
    ocr_state = fields.Selection([
        ('pending', 'Pending'), ('running', 'Running'),
        ('done', 'Done'), ('failed', 'Failed'),
    ], default='pending', string='OCR Status')
    ocr_provider = fields.Char(string='OCR Provider', readonly=True)
    ocr_raw = fields.Text(string='OCR Raw Text', readonly=True)
    confidence_json = fields.Text(string='Field Confidences', readonly=True)

    # --- extracted (editable, human verifies) ---
    x_bank_name = fields.Char(string='Bank')
    x_bank_branch = fields.Char(string='Branch')
    x_account_name = fields.Char(string='Account Holder')
    x_account_number = fields.Char(string='Account Number')
    x_iban = fields.Char(string='IBAN')
    x_swift = fields.Char(string='SWIFT / BIC')

    # --- snapshot of the master at submit (the diff basis) ---
    cur_bank_name = fields.Char(string='Current Bank', readonly=True)
    cur_bank_branch = fields.Char(string='Current Branch', readonly=True)
    cur_account_name = fields.Char(string='Current Holder', readonly=True)
    cur_account_number = fields.Char(string='Current Account', readonly=True)

    # --- validation results ---
    v_format_ok = fields.Boolean(string='Format OK', readonly=True)
    v_format_msg = fields.Char(string='Format Notes', readonly=True)
    name_match_score = fields.Float(string='Name Match %', readonly=True)
    name_match_band = fields.Selection([
        ('green', 'Strong'), ('amber', 'Review'), ('red', 'Mismatch'),
    ], string='Name Match', readonly=True)
    duplicate_ids = fields.Many2many(
        'hr.employee', 'pb_bank_request_dup_rel', 'request_id', 'employee_id',
        string='Possible Duplicates', readonly=True)
    duplicate_ack = fields.Boolean(
        string='Duplicate Verified',
        help='HR confirms this is not a duplicate payment target.')

    resolved_bank_id = fields.Many2one('pb.bank.registry', string='Resolved Bank', readonly=True)
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    approval_widget_json = fields.Char(compute='_compute_approval_widget')
    can_submit = fields.Boolean(compute='_compute_can')
    can_hr_approve = fields.Boolean(compute='_compute_can')
    can_finance_approve = fields.Boolean(compute='_compute_can')
    can_refuse = fields.Boolean(compute='_compute_can')

    # ------- the chain (Employee → HR → Finance → master) -------
    _approval_transitions = {
        ('draft', 'hr_review'): None,                 # submit — owner / HR
        ('hr_review', 'finance_review'): _HR_GROUP,   # HR tier
        ('finance_review', 'approved'): _FINANCE_GROUPS[-1],  # finance tier
    }

    # ------------------------------------------------------------- computes
    @api.depends('state')
    def _compute_approval_widget(self):
        steps = [
            {'state': 'draft', 'label': _('Request'), 'group_label': _('Employee')},
            {'state': 'hr_review', 'label': _('HR Review'), 'group_label': _('HR')},
            {'state': 'finance_review', 'label': _('Finance'), 'group_label': _('Finance')},
            {'state': 'approved', 'label': _('Master Updated'), 'group_label': _('System')},
        ]
        for rec in self:
            rec.approval_widget_json = rec._approval_widget_payload(steps) if rec.id else False

    @api.depends('state')
    def _compute_can(self):
        for rec in self:
            s = rec.state
            rec.can_submit = s == 'draft' and rec._approval_can('draft', 'hr_review')
            rec.can_hr_approve = s == 'hr_review' and rec._approval_can('hr_review', 'finance_review')
            rec.can_finance_approve = s == 'finance_review' and rec._approval_can('finance_review', 'approved')
            rec.can_refuse = s in ('hr_review', 'finance_review') and rec._approval_can_refuse(s)

    # --------------------------------------------------------- authorization
    def _user_in_any(self, xmlids):
        for x in xmlids:
            try:
                if self.env.user.has_group(x):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _is_reviewer(self):
        return self._user_in_any(
            (_HR_GROUP, 'hr.group_hr_user') + _FINANCE_GROUPS)

    # --------------------------------------------- forgery rails (C18.24)
    def _sys_allowed(self):
        return (self.env.su or self.env.user._is_admin()
                or self.env.context.get('bank_sys_write') is _BANK_SYS_TOKEN)

    def _sys_write(self, vals):
        return self.with_context(bank_sys_write=_BANK_SYS_TOKEN).write(vals)

    def write(self, vals):
        if not self._sys_allowed():
            forged = _SYS_FIELDS.intersection(vals)
            if forged:
                raise AccessError(_(
                    "The verification results of a bank change request are "
                    "system-computed and cannot be edited: %s.",
                    ', '.join(sorted(forged))))
            if 'duplicate_ack' in vals and not self._is_reviewer():
                raise AccessError(_(
                    "Only HR or Finance can confirm a duplicate account."))
            touched = _REVIEW_FIELDS.intersection(vals)
            if touched:
                is_reviewer = self._is_reviewer()
                for rec in self:
                    if rec.state in ('approved', 'refused'):
                        raise AccessError(_(
                            "A decided bank change request is immutable."))
                    if rec.state != 'draft' and not is_reviewer:
                        raise AccessError(_(
                            "This request is under review — only HR or Finance "
                            "may edit the submitted details now."))
                    if ('employee_id' in vals and not is_reviewer
                            and rec.employee_id.id != vals['employee_id']):
                        raise AccessError(_(
                            "Only HR can re-target a bank change request."))
        return super().write(vals)
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        user = self.env.user
        rec = self.sudo()
        pair = (from_state, to_state)
        if pair == ('draft', 'hr_review'):
            if rec.employee_id.user_id and rec.employee_id.user_id == user:
                return True
            if rec.create_uid == user:
                return True
            return self._user_in_any((_HR_GROUP, 'hr.group_hr_user'))
        if pair == ('hr_review', 'finance_review'):
            return self._user_in_any((_HR_GROUP, 'om_hr_payroll.group_hr_payroll_manager'))
        if pair == ('finance_review', 'approved'):
            return self._user_in_any(_FINANCE_GROUPS)
        return False

    # --------------------------------------------------------- lifecycle
    def _before_approval_transition(self, to_state):
        if to_state == 'hr_review':
            # sudo: snapshotting the master and reading the (other-employee)
            # duplicate set are system-derived validations, not the submitter
            # browsing HR private data — the one-permission-world rail (C18.17).
            rec = self.sudo()
            rec._snapshot_current()
            if rec.duplicate_ids and not rec.duplicate_ack:
                raise UserError(_(
                    "This account collides with another employee. HR must tick "
                    "'Duplicate Verified' before this request can be submitted."))
            if not rec.x_account_number:
                raise UserError(_("An account number is required to submit."))
        if to_state == 'approved':
            # TOCTOU rail: re-derive every advisory against the FINAL field
            # values, then re-raise the hard gates — the approver must never
            # apply numbers the validation no longer describes.
            rec = self.sudo()
            rec.action_validate()
            if not account_ok(rec.x_account_number):
                raise UserError(_(
                    "The account number must be 6-19 digits before approval."))
            if rec.duplicate_ids and not rec.duplicate_ack:
                raise UserError(_(
                    "This account collides with another employee. HR must tick "
                    "'Duplicate Verified' before approval."))

    def _after_approval_transition(self, to_state):
        if to_state == 'approved':
            self._apply_to_master()

    def action_submit(self):
        self.ensure_one()
        return self._advance_state('hr_review')

    def action_hr_approve(self):
        self.ensure_one()
        return self._advance_state('finance_review')

    def action_finance_approve(self):
        self.ensure_one()
        return self._advance_state('approved')

    # --------------------------------------------------- the master write
    def _snapshot_current(self):
        self.ensure_one()
        emp = self.employee_id
        self.write({
            'cur_bank_name': emp.vietnam_bank_name or '',
            'cur_bank_branch': emp.vietnam_bank_branch or '',
            'cur_account_name': emp.vietnam_bank_account_name or '',
            'cur_account_number': emp.vietnam_bank_account_number or '',
        })

    def _apply_to_master(self):
        """The ONLY path that writes the employee master — atomic, flagged,
        history-logged. Runs inside the approval transaction (safety rail 1)."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        old = {
            'vietnam_bank_name': emp.vietnam_bank_name or '',
            'vietnam_bank_branch': emp.vietnam_bank_branch or '',
            'vietnam_bank_account_name': emp.vietnam_bank_account_name or '',
            'vietnam_bank_account_number': emp.vietnam_bank_account_number or '',
        }
        new = {emp_field: (self[x_field] or '') for x_field, emp_field in _MASTER_FIELDS}
        # the sentinel routes AROUND the manual-audit override — this path
        # writes its OWN 'ocr_request' history row (no double-logging). A
        # client-sent truthy from_bank_request must NOT skip the audit (C18.24),
        # hence the object() identity, not a boolean.
        emp.with_context(from_bank_request=_BANK_AUDIT_TOKEN).write(new)
        self.env['pb.employee.bank.history'].sudo().create({
            'employee_id': emp.id,
            'change_source': 'ocr_request',
            'request_id': self.id,
            'old_bank_name': old['vietnam_bank_name'],
            'new_bank_name': new['vietnam_bank_name'],
            'old_bank_branch': old['vietnam_bank_branch'],
            'new_bank_branch': new['vietnam_bank_branch'],
            'old_account_name': old['vietnam_bank_account_name'],
            'new_account_name': new['vietnam_bank_account_name'],
            'old_account_number': old['vietnam_bank_account_number'],
            'new_account_number': new['vietnam_bank_account_number'],
        })
        self.message_post(body=_("Bank master updated from this request."))

    # --------------------------------------------------------- OCR run
    def _ocr_schema(self):
        return {
            'fields': [
                {'name': 'x_bank_name', 'label': 'Bank', 'type': 'char',
                 'hint': 'issuing bank name'},
                {'name': 'x_bank_branch', 'label': 'Branch', 'type': 'char',
                 'hint': 'branch / office'},
                {'name': 'x_account_name', 'label': 'Account holder', 'type': 'char',
                 'hint': 'full name on the account'},
                {'name': 'x_account_number', 'label': 'Account number', 'type': 'digits',
                 'hint': 'digits only, 6-19'},
                {'name': 'x_iban', 'label': 'IBAN', 'type': 'code', 'hint': 'if present'},
                {'name': 'x_swift', 'label': 'SWIFT/BIC', 'type': 'code',
                 'hint': 'bank BIC if present'},
            ],
            'doc_kinds': ['confirmation_letter', 'statement', 'passbook', 'cheque', 'other'],
        }

    def _ocr_post_process(self, result):
        """Deterministic layer — always runs last (Tesseract prose or AI JSON).

        Fills gaps from raw text, folds/normalizes the bank, upper-cases SWIFT.
        """
        fields_out = result.setdefault('fields', {})
        raw = result.get('raw_text') or ''

        def val(name):
            cell = fields_out.get(name)
            return (cell or {}).get('value') if isinstance(cell, dict) else cell

        # account number: regex-recover from prose when the provider missed it
        acct = val('x_account_number')
        if not acct:
            found = extract_account_number(raw)
            if found:
                fields_out['x_account_number'] = {'value': found, 'confidence': 0.4}
        # SWIFT upper-case
        sw = val('x_swift')
        if sw:
            fields_out['x_swift'] = {'value': fold(sw).replace(' ', ''),
                                     'confidence': (fields_out['x_swift'] or {}).get('confidence', 0.5)
                                     if isinstance(fields_out.get('x_swift'), dict) else 0.5}
        # bank normalization via the registry
        bank_name = val('x_bank_name') or ''
        match = self.env['pb.bank.registry'].match(bank_name or raw)
        if match:
            result['resolved_bank_id'] = match.id
            if bank_name:
                fields_out['x_bank_name'] = {'value': match.short_name or match.name,
                                             'confidence': 0.7}
        return result

    def _biz_doc_ocr_run(self, job):
        """biz.doc.ocr.job hook — extract, apply to x_* fields, return result."""
        self.ensure_one()
        self._sys_write({'ocr_state': 'running'})
        res = self.env['biz.doc.ocr']._extract(
            self._ocr_schema(), [self.attachment_id.id],
            post_processor=self._ocr_post_process)
        vals = {
            'ocr_provider': res.get('provider'),
            'ocr_raw': res.get('raw_text') or '',
            'confidence_json': json.dumps(
                {k: v.get('confidence') for k, v in (res.get('fields') or {}).items()}),
        }
        for name, cell in (res.get('fields') or {}).items():
            if name in self._fields and (cell or {}).get('value'):
                vals[name] = cell['value']
        if res.get('resolved_bank_id'):
            vals['resolved_bank_id'] = res['resolved_bank_id']
        if res.get('doc_kind') and res['doc_kind'] in dict(self._fields['doc_kind'].selection):
            vals['doc_kind'] = res['doc_kind']
        failed = bool(res.get('error')) and not res.get('fields')
        vals['ocr_state'] = 'failed' if failed else 'done'
        self._sys_write(vals)
        return res

    def action_run_ocr(self):
        """Synchronous run with a job wrapper (scan-shimmer covers the wait)."""
        self.ensure_one()
        if self.state in ('approved', 'refused'):
            raise UserError(_("A decided request cannot be re-scanned."))
        if not self.attachment_id:
            raise UserError(_("Upload a document first."))
        job = self.env['biz.doc.ocr.job'].create({
            'res_model': self._name, 'res_id': self.id,
            'payload': json.dumps({'attachment_id': self.attachment_id.id}),
        })
        job.run()
        self.action_validate()
        return True

    # --------------------------------------------------------- validation
    def action_validate(self):
        """Deterministic format / name-match / duplicate check. NEVER writes
        the master; advisory only (safety rail 1)."""
        for rec in self:
            msgs = []
            ok = True
            if not account_ok(rec.x_account_number):
                ok = False
                msgs.append(_("Account number must be 6-19 digits."))
            if rec.x_swift and not swift_ok(rec.x_swift):
                ok = False
                msgs.append(_("SWIFT/BIC format looks invalid."))
            bank = self.env['pb.bank.registry'].match(rec.x_bank_name or '')
            if not bank and rec.x_bank_name:
                msgs.append(_("Bank not recognised in the registry."))
            # name similarity vs the employee name (and current holder if set)
            score = name_similarity(rec.x_account_name, rec.employee_id.name)
            if rec.employee_id.vietnam_bank_account_name:
                score = max(score, name_similarity(
                    rec.x_account_name, rec.employee_id.vietnam_bank_account_name))
            band = 'green' if score >= 85 else ('amber' if score >= 60 else 'red')
            # duplicate detection: same normalized account + bank on another emp
            dups = rec._find_duplicates(bank)
            vals = {
                'v_format_ok': ok,
                'v_format_msg': ' '.join(msgs) or _("All format checks passed."),
                'name_match_score': score,
                'name_match_band': band,
                'resolved_bank_id': bank.id if bank else False,
                'duplicate_ids': [(6, 0, dups.ids)],
            }
            # an HR ack covers a SPECIFIC duplicate set — a changed set voids it
            if rec.duplicate_ack and set(dups.ids) != set(rec.duplicate_ids.ids):
                vals['duplicate_ack'] = False
            rec._sys_write(vals)
        return True

    def _find_duplicates(self, bank):
        """Other employees of THIS company sharing the normalized account
        number (+ bank) — company-scoped so the duplicate card never leaks
        another company's employees."""
        self.ensure_one()
        digits = ''.join(ch for ch in (self.x_account_number or '') if ch.isdigit())
        if not digits:
            return self.env['hr.employee']
        Emp = self.env['hr.employee'].sudo()
        candidates = Emp.search([
            ('id', '!=', self.employee_id.id),
            ('company_id', '=', self.company_id.id),
            ('vietnam_bank_account_number', '!=', False),
        ])
        want_bank = fold(bank.short_name) if bank else fold(self.x_bank_name)
        out = Emp.browse()
        for emp in candidates:
            emp_digits = ''.join(ch for ch in (emp.vietnam_bank_account_number or '')
                                 if ch.isdigit())
            if emp_digits != digits:
                continue
            if want_bank and emp.vietnam_bank_name and want_bank not in fold(emp.vietnam_bank_name):
                continue  # same number, different bank → not a dup
            out |= emp
        return out

    # ---------------------------------------------------- create / defaults
    @api.model_create_multi
    def create(self, vals_list):
        sys_ok = self._sys_allowed()
        for vals in vals_list:
            if not sys_ok:
                for f in _SYS_FIELDS.intersection(vals):
                    vals.pop(f)
                if 'duplicate_ack' in vals and not self._is_reviewer():
                    vals.pop('duplicate_ack')
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'pb.bank.change.request') or _('New')
        return super().create(vals_list)

    # masked helper for the UI (account rendered •••• 4321 everywhere but the
    # HR/finance verify view)
    def _masked_account(self, number):
        digits = ''.join(ch for ch in (number or '') if ch.isdigit())
        return ('•••• ' + digits[-4:]) if len(digits) >= 4 else (digits or '')
