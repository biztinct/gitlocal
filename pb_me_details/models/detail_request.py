# -*- coding: utf-8 -*-
"""A change an employee proposes to their own details on My Payobook.

ONE request, one change: a family member added, changed or removed; an ID
paper (with its scan); a new photo; a marital status. Nothing on the
employee record moves until the request is approved through the one
Approvals inbox (`detail_approval.py`); then `_pb_apply` writes exactly what
was proposed, under sudo, as the system.

THE EMPLOYEE NEVER PICKS THE EMPLOYEE. Requests are created by
`pb_portal_create` for the caller's own employee only (the controller
resolves it from the session), from a whitelist of fields per kind.

WHAT THE PERSON SEES: Draft, Waiting for HR, Approved, Sent back (with the
reason, back to a draft they can change and send again), Turned down (with
the reason).
"""

import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .family import RELATIONSHIPS

_logger = logging.getLogger(__name__)

KINDS = [
    ('family_add', 'Add a family member'),
    ('family_change', 'Change a family member'),
    ('family_remove', 'Remove a family member'),
    ('id_paper', 'ID paper'),
    ('photo', 'Photo'),
    ('marital', 'Marital status'),
]
FAMILY_KINDS = ('family_add', 'family_change', 'family_remove')

PAPERS = [
    ('national_id', 'National ID card'),
    ('passport', 'Passport'),
    ('permit', 'Work permit'),
]
#: paper kind → (number field, expiry field or None, vault category xmlid)
PAPER_FIELDS = {
    'national_id': ('identification_id', None, 'pb_employee_vault.cat_id_document'),
    'passport': ('passport_id', 'passport_expiration_date',
                 'pb_employee_vault.cat_id_document'),
    'permit': ('permit_no', 'work_permit_expiration_date',
               'pb_employee_vault.cat_work_permit'),
}

MARITAL = [
    ('single', 'Single'),
    ('married', 'Married'),
    ('cohabitant', 'Living together'),
    ('widower', 'Widowed'),
    ('divorced', 'Divorced'),
]

#: What a form may set, per kind. Everything else is set by this module.
PORTAL_FIELDS = {
    'family_add': ('f_name', 'f_relationship', 'f_birthdate', 'f_id_number',
                   'f_counts_for_tax', 'f_insured'),
    'family_change': ('f_name', 'f_relationship', 'f_birthdate',
                      'f_id_number', 'f_counts_for_tax', 'f_insured'),
    'family_remove': (),
    'id_paper': ('paper_kind', 'paper_number', 'paper_expiry'),
    'photo': (),
    'marital': ('marital',),
}

IMAGE_MIMES = ('image/png', 'image/jpeg')
SCAN_MIMES = ('application/pdf', 'image/png', 'image/jpeg')
MAX_BYTES = 10 * 1024 * 1024


class PbMeDetailRequest(models.Model):
    _name = 'pb.me.detail.request'
    _description = 'Change to my details'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Reference', required=True, readonly=True,
                       copy=False, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                  required=True, index=True, readonly=True,
                                  ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, readonly=True)
    kind = fields.Selection(KINDS, string='What', required=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('hr_review', 'Waiting for HR'),
        ('approved', 'Approved'),
        ('refused', 'Turned down'),
    ], string='Status', default='draft', index=True, readonly=True, copy=False,
        tracking=True)

    # --- family ---
    member_id = fields.Many2one('pb.employee.family', string='Family member',
                                readonly=True, ondelete='set null')
    f_name = fields.Char(string='Name', readonly=True)
    f_relationship = fields.Selection(RELATIONSHIPS, string='Relationship',
                                      readonly=True)
    f_birthdate = fields.Date(string='Date of birth', readonly=True)
    f_id_number = fields.Char(string='ID or birth certificate number',
                              readonly=True)
    f_counts_for_tax = fields.Boolean(string='Counts for tax', readonly=True)
    f_insured = fields.Boolean(string='Covered by insurance', readonly=True)

    # --- ID paper ---
    paper_kind = fields.Selection(PAPERS, string='Paper', readonly=True)
    paper_number = fields.Char(string='Number', readonly=True)
    paper_expiry = fields.Date(string='Valid until', readonly=True)

    # --- marital status ---
    marital = fields.Selection(MARITAL, string='Marital status', readonly=True)

    # --- the scan or the new photo ---
    attachment_id = fields.Many2one('ir.attachment', string='File',
                                    readonly=True, copy=False)

    # --- the record before (the "now" column), taken when it is sent ---
    before_json = fields.Text(readonly=True, copy=False)

    note = fields.Text(string='Note from the employee', readonly=True)
    decision_note = fields.Text(string='Reason given', readonly=True, copy=False)
    submitted_on = fields.Datetime(string='Sent on', readonly=True, copy=False)
    decided_on = fields.Datetime(string='Decided on', readonly=True, copy=False)
    document_id = fields.Many2one('pb.employee.document', string='Filed as',
                                  readonly=True, copy=False)

    _approval_transitions = {
        ('draft', 'hr_review'): None,
        ('hr_review', 'approved'): 'hr.group_hr_user',
    }

    # ================================================================ create
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("A change to somebody's details is proposed on "
                                "My Payobook."))
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'pb.me.detail.request') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self._chain_write_allowed() \
                and set(vals) - {'message_main_attachment_id'}:
            raise AccessError(_("A proposed change cannot be edited here. The "
                                "employee changes it on My Payobook."))
        return super().write(vals)

    # ============================================================ the portal
    @api.model
    def _pb_clean(self, kind, values):
        allowed = PORTAL_FIELDS.get(kind, ())
        vals = {}
        for key in allowed:
            if key not in values:
                continue
            raw = values.get(key)
            field = self._fields[key]
            if field.type == 'boolean':
                vals[key] = bool(raw) and raw not in ('0', 'false', 'off')
            elif field.type == 'date':
                vals[key] = fields.Date.to_date(raw) if raw else False
            elif field.type == 'selection':
                options = dict(field._description_selection(self.env))
                vals[key] = raw if raw in options else False
            else:
                vals[key] = (raw or '').strip()[:200] or False
        return vals

    @api.model
    def _pb_check(self, kind, vals, member=None, attachment=None):
        """Plain sentences for what is missing; nothing is saved on a refusal."""
        if kind in ('family_add', 'family_change'):
            if not vals.get('f_name'):
                raise UserError(_("Write the family member's name."))
            if not vals.get('f_relationship'):
                raise UserError(_("Choose how they are related to you."))
            born = vals.get('f_birthdate')
            if born and born > fields.Date.context_today(self):
                raise UserError(_("The date of birth cannot be in the future."))
        if kind in ('family_change', 'family_remove') and not member:
            raise UserError(_("Choose the family member to change."))
        if kind == 'id_paper':
            if not vals.get('paper_kind'):
                raise UserError(_("Choose which paper this is."))
            if not vals.get('paper_number'):
                raise UserError(_("Write the number printed on the paper."))
            if not attachment:
                raise UserError(_("Add a photo or scan of the paper, so HR can "
                                  "check it."))
        if kind == 'photo' and not attachment:
            raise UserError(_("Choose the photo to use."))
        if kind == 'marital' and not vals.get('marital'):
            raise UserError(_("Choose your marital status."))

    @api.model
    def _pb_file(self, upload, kind):
        """`(bytes, filename, mimetype)` checked, or None when no file."""
        if not upload:
            return None
        data, filename, mimetype = upload
        if not data:
            return None
        if len(data) > MAX_BYTES:
            raise UserError(_("The file is larger than 10 MB. Try a smaller "
                              "copy, or a photo of the page."))
        allowed = IMAGE_MIMES if kind == 'photo' else SCAN_MIMES
        if (mimetype or '') not in allowed:
            raise UserError(_("The photo can be a JPG or PNG.") if kind == 'photo'
                            else _("The file can be a PDF, JPG or PNG."))
        return data, filename, mimetype

    @api.model
    def pb_portal_create(self, employee, kind, values, member=None, upload=None,
                         request_id=None):
        """Make (or, for a draft that was sent back, change) a request for the
        caller's OWN employee and send it. `upload` is `(bytes, filename,
        mimetype)` read by the controller; the attachment is made here."""
        employee = employee.sudo()
        if not employee or employee.user_id != self.env.user:
            raise AccessError(_("You can only change your own details."))
        if kind not in dict(KINDS):
            raise UserError(_("That kind of change is not offered here."))
        Family = self.env['pb.employee.family'].sudo().with_context(
            active_test=False)
        if member is not None:
            member = Family.browse(int(member)).exists() if member else Family
            if member and member.employee_id != employee:
                raise AccessError(_("That family member is not on your record."))
        vals = self._pb_clean(kind, values or {})
        req = self.sudo().browse()
        if request_id:
            req = self.sudo().browse(int(request_id)).exists()
            if not req or req.employee_id != employee or req.state != 'draft' \
                    or req.kind != kind:
                raise AccessError(_("That change is not yours to edit."))
            member = member or req.member_id
        if kind == 'family_remove' and member:
            vals = {'f_name': member.name, 'f_relationship': member.relationship,
                    'f_birthdate': member.birthdate,
                    'f_id_number': member.id_number,
                    'f_counts_for_tax': member.counts_for_tax,
                    'f_insured': member.insured}
        file = self._pb_file(upload, kind)
        attachment = req.attachment_id if req else None
        self._pb_check(kind, vals, member=member,
                       attachment=bool(file) or bool(attachment))
        open_same = self.sudo().search_count([
            ('employee_id', '=', employee.id), ('kind', '=', kind),
            ('state', '=', 'hr_review'),
            ('member_id', '=', member.id if member else False),
        ]) if kind not in ('family_add', 'id_paper') else 0
        if open_same:
            raise UserError(_("The same change is already waiting for HR. Take "
                              "it back first if you want to send a different "
                              "one."))
        vals.update({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'kind': kind,
            'member_id': member.id if member else False,
            'note': ((values or {}).get('note') or '').strip()[:500] or False,
        })
        with self.env.cr.savepoint():
            if req:
                req.write(vals)
            else:
                req = self.sudo().create(vals)
            if file:
                data, filename, mimetype = file
                old = req.attachment_id
                att = self.env['ir.attachment'].sudo().create({
                    'name': filename or _('File'),
                    'datas': base64.b64encode(data),
                    'mimetype': mimetype,
                    'res_model': req._name,
                    'res_id': req.id,
                })
                req.write({'attachment_id': att.id})
                if old:
                    old.unlink()
            req._pb_send()
        return req

    def _pb_ensure_route(self):
        self.ensure_one()
        if self._engine_managed():
            return
        try:
            with self.env.cr.savepoint():
                self.sudo()._approval_seed_default(self.company_id)
        except Exception:                   # noqa: BLE001 — never block a send
            _logger.warning('pb_me_details: no route could be laid for %s',
                            self.company_id.name, exc_info=True)

    def _pb_send(self):
        self.ensure_one()
        rec = self.sudo()
        rec._pb_ensure_route()
        rec.write({'decision_note': False, 'submitted_on': fields.Datetime.now(),
                   'before_json': json.dumps(rec._pb_now(), default=str)})
        rec._advance_state('hr_review')
        rec.invalidate_recordset()
        return rec

    def pb_portal_withdraw(self):
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'hr_review':
            raise UserError(_("Only a change that is waiting for HR can be "
                              "taken back."))
        request = rec._chain_open_request()
        if request:
            self.env['biz.approval.engine'].sudo().cancel(
                request, _("Taken back by %s", rec.employee_id.name or ''))
        else:
            rec._approval_withdraw(None, '')
        rec.invalidate_recordset()
        return True

    # ====================================================== what it changes
    def _pb_now(self):
        """The record as it is now, for the "Now" column."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        if self.kind in ('family_change', 'family_remove') and self.member_id:
            m = self.member_id.sudo()
            return {'f_name': m.name, 'f_relationship': m.relationship,
                    'f_birthdate': m.birthdate, 'f_id_number': m.id_number,
                    'f_counts_for_tax': m.counts_for_tax,
                    'f_insured': m.insured}
        if self.kind == 'id_paper' and self.paper_kind:
            number_f, expiry_f, _cat = PAPER_FIELDS[self.paper_kind]
            return {'paper_number': emp[number_f] if number_f in emp._fields else '',
                    'paper_expiry': emp[expiry_f] if expiry_f and expiry_f in emp._fields else ''}
        if self.kind == 'marital':
            return {'marital': emp.marital if 'marital' in emp._fields else ''}
        return {}

    def _pb_apply(self):
        """Write exactly what was approved. Sudo: the approver may hold no
        right on family members, documents or the employee's private fields;
        `sudo()` keeps the uid, so the trail names them."""
        self.ensure_one()
        rec = self.sudo()
        emp = rec.employee_id.sudo()
        approver = self.env.user
        Family = self.env['pb.employee.family'].sudo()
        kind = rec.kind
        if kind == 'family_add':
            member = Family.create({
                'employee_id': emp.id, 'name': rec.f_name,
                'relationship': rec.f_relationship or 'other',
                'birthdate': rec.f_birthdate, 'id_number': rec.f_id_number,
                'counts_for_tax': rec.f_counts_for_tax, 'insured': rec.f_insured,
            })
            rec.write({'member_id': member.id})
            if member.counts_for_tax:
                member._pb_mark_for_tax('add', approver)
        elif kind == 'family_change':
            member = rec.member_id.sudo()
            if not member:
                raise UserError(_("The family member no longer exists."))
            was_counted = member.counts_for_tax
            tax_fields_before = (member.name, member.birthdate, member.id_number,
                                 member.relationship)
            member.write({
                'name': rec.f_name, 'relationship': rec.f_relationship or 'other',
                'birthdate': rec.f_birthdate, 'id_number': rec.f_id_number,
                'counts_for_tax': rec.f_counts_for_tax, 'insured': rec.f_insured,
            })
            tax_fields_after = (member.name, member.birthdate, member.id_number,
                                member.relationship)
            if member.counts_for_tax and (not was_counted
                                          or tax_fields_before != tax_fields_after):
                member._pb_mark_for_tax('add', approver)
            elif was_counted and not member.counts_for_tax:
                member._pb_mark_for_tax('end', approver)
        elif kind == 'family_remove':
            member = rec.member_id.sudo()
            if member:
                counted = member.counts_for_tax or member.vn_dependent_id
                member.write({'active': False})
                if counted:
                    member._pb_mark_for_tax('end', approver)
        elif kind == 'id_paper':
            number_f, expiry_f, cat_xmlid = PAPER_FIELDS[rec.paper_kind]
            vals = {}
            if number_f in emp._fields:
                vals[number_f] = rec.paper_number
            if expiry_f and expiry_f in emp._fields and rec.paper_expiry:
                vals[expiry_f] = rec.paper_expiry
            if vals:
                emp.write(vals)
            rec._pb_file_paper(cat_xmlid)
        elif kind == 'photo':
            if not rec.attachment_id:
                raise UserError(_("The photo is missing."))
            emp.write({'image_1920': rec.attachment_id.datas})
        elif kind == 'marital':
            if 'marital' in emp._fields and rec.marital:
                emp.write({'marital': rec.marital})
        rec.message_post(body=_("Approved and written to the employee record."))
        return True

    def _pb_file_paper(self, cat_xmlid):
        """The scan goes into the person's documents, verified by the
        approver (their approval IS the check)."""
        self.ensure_one()
        rec = self.sudo()
        if not rec.attachment_id:
            return False
        category = self.env.ref(cat_xmlid, raise_if_not_found=False) \
            or self.env.ref('pb_employee_vault.cat_other', raise_if_not_found=False)
        if not category:
            return False
        label = rec._pb_paper_label()
        copy = rec.attachment_id.copy({'res_model': 'pb.employee.document',
                                       'res_id': 0})
        doc_vals = {
            'employee_id': rec.employee_id.id,
            'category_id': category.id,
            'name': '%s %s' % (label, rec.paper_number or ''),
            'attachment_id': copy.id,
            'company_id': rec.company_id.id,
        }
        if rec.paper_expiry:
            doc_vals['expiry_date'] = rec.paper_expiry
        doc = self.env['pb.employee.document'].sudo().create(doc_vals)
        copy.write({'res_id': doc.id})
        doc.sudo().write({'verified': True, 'verified_by': self.env.uid,
                          'verified_at': fields.Datetime.now()})
        rec.write({'document_id': doc.id})
        return doc

    # ======================================================= the chain hooks
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'approved':
            for rec in self:
                rec._pb_apply()
                rec.sudo().write({'decided_on': fields.Datetime.now()})
        if to_state == 'refused':
            self.sudo().write({'decided_on': fields.Datetime.now()})
        return res

    def _approval_apply(self, request):
        """Carried out under sudo (ledger W2B-2): the engine runs this as the
        last approver, who may hold no right on family members, documents or
        this model; `sudo()` keeps the uid."""
        self.ensure_one()
        return super(PbMeDetailRequest, self.sudo())._approval_apply(request)

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'decision_note': reason or _("Sent back")})
        return super(PbMeDetailRequest, self.sudo())._approval_return(
            request, reason)

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'decision_note': reason or False})
        return super(PbMeDetailRequest, self.sudo())._approval_reject(
            request, reason)

    def _approval_withdraw(self, request, reason):
        """Taken back by the employee: a draft again. Its own savepoint
        (ledger QF3-6); the shim does not mirror a withdrawal."""
        self.ensure_one()
        rec = self.sudo()
        with self.env.cr.savepoint():
            if rec.state == 'hr_review':
                rec._chain_engine_write('draft')
                rec._chain_log('hr_review', 'draft', reason or '')
        return True

    # ============================================== what the person reads
    def _pb_paper_label(self):
        self.ensure_one()
        options = dict(self._fields['paper_kind']._description_selection(self.env))
        return options.get(self.paper_kind, '')

    def pb_portal_state(self):
        self.ensure_one()
        if self.state == 'draft' and self.decision_note:
            return 'sent_back'
        return self.state

    def pb_label(self):
        """A one-line title, in the reader's language."""
        self.ensure_one()
        _t = self.env._
        kind = self.kind
        if kind == 'family_add':
            return _t("Add %s to my family", self.f_name or '')
        if kind == 'family_change':
            return _t("Change %s", self.f_name or self.member_id.name or '')
        if kind == 'family_remove':
            return _t("Remove %s", self.f_name or self.member_id.name or '')
        if kind == 'id_paper':
            return self._pb_paper_label() or _t("ID paper")
        if kind == 'photo':
            return _t("New photo")
        return _t("Marital status")
