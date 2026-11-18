# -*- coding: utf-8 -*-
"""Tax details proposed on My Payobook — new kinds of the ONE request model.

Reuses `pb.me.detail.request` (pb_me_details) and its approval chain through
its extension points: the kinds are added with `selection_add`, the portal
create, the "now" snapshot, the apply, the inbox rows and the title are
extended for those kinds only; every other kind runs exactly as before. The
process stays `me_details` (one route, the HR lead by default); a business
can condition a step on the kind in the route builder.

NOTHING CHANGES BEFORE HR APPROVES. The proposed value lives on the request.
On approval `_pb_apply` writes exactly that value into the one employee field
for the country the request was sent for (`t_country`, fixed when it was
sent) and files the proof in the person's documents, verified by the
approver. A refusal, a send-back or a take-back writes nothing.

PRIVACY. The request rules of pb_me_details apply unchanged: HR (and the pay
team, whose group implies HR) read requests; anybody else only what a route
asked them to decide. The proof file is attached to the request, so reading
it needs the right to read the request.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .tax_rules import (
    CHOICE_FIELD, KIND_SELECTION, KINDS_BY_COUNTRY, NUMBER_FIELD, PROOF_REQUIRED,
    PTKP, REGIMES, REQUEST_FIELD, SG_FUNDS, TAX_KINDS, mask, normalise_number,
)

_logger = logging.getLogger(__name__)

#: What the form may set, per tax kind (everything else is set here).
TAX_PORTAL_FIELDS = {
    'tax_number': ('t_number', 't_use_nik'),
    'tax_status': ('t_ptkp',),
    'tax_regime': ('t_regime',),
    'tax_fund': ('t_fund',),
}

TAX_CATEGORY = 'pb_me_tax.cat_tax_paper'


class PbMeDetailRequestTax(models.Model):
    _inherit = 'pb.me.detail.request'

    kind = fields.Selection(selection_add=KIND_SELECTION,
                            ondelete={k: 'cascade' for k in TAX_KINDS})

    t_country = fields.Char(string='Country', size=2, readonly=True)
    t_number = fields.Char(string='Tax number', readonly=True)
    t_use_nik = fields.Boolean(string='Use my NIK as my NPWP', readonly=True)
    t_ptkp = fields.Selection(PTKP, string='PTKP status', readonly=True)
    t_regime = fields.Selection(REGIMES, string='Tax regime', readonly=True)
    t_fund = fields.Selection(SG_FUNDS, string='Self-help group fund',
                              readonly=True)
    t_proof_file = fields.Binary(related='attachment_id.datas',
                                 string='Proof', groups='hr.group_hr_user')
    t_proof_name = fields.Char(related='attachment_id.name',
                               string='Proof file name',
                               groups='hr.group_hr_user')

    # ================================================================ portal
    @api.model
    def pb_portal_create(self, employee, kind, values, member=None, upload=None,
                         request_id=None):
        """Tax kinds: the country is the scheme's, fixed now, and the kind
        must be one that country offers. Then the shared create runs (own
        employee only, one savepoint, one open request per kind)."""
        if kind not in TAX_KINDS:
            return super().pb_portal_create(employee, kind, values, member=member,
                                            upload=upload, request_id=request_id)
        emp = employee.sudo()
        if not emp or emp.user_id != self.env.user:
            raise AccessError(_("You can only change your own details."))
        country = emp._pbtx_country()
        if kind not in KINDS_BY_COUNTRY.get(country, ()):
            raise UserError(_("This change is not offered for the country you "
                              "are paid in."))
        return super(PbMeDetailRequestTax, self.with_context(
            pbtx_country=country, pbtx_employee=emp.id)).pb_portal_create(
                employee, kind, values, member=None, upload=upload,
                request_id=request_id)

    @api.model
    def _pb_clean(self, kind, values):
        if kind not in TAX_KINDS:
            return super()._pb_clean(kind, values)
        vals = {}
        for key in TAX_PORTAL_FIELDS[kind]:
            if key not in values:
                continue
            raw = values.get(key)
            field = self._fields[key]
            if field.type == 'boolean':
                vals[key] = bool(raw) and raw not in ('0', 'false', 'off')
            elif field.type == 'selection':
                options = dict(field._description_selection(self.env))
                vals[key] = raw if raw in options else False
            else:
                vals[key] = (raw or '').strip()[:40] or False
        country = self.env.context.get('pbtx_country') or ''
        vals['t_country'] = country
        if kind == 'tax_number':
            if vals.get('t_use_nik') and country == 'ID':
                emp = self.env['hr.employee'].sudo().browse(
                    self.env.context.get('pbtx_employee') or 0)
                vals['t_number'] = emp.identification_id or False
            else:
                vals['t_use_nik'] = False
            if vals.get('t_number'):
                vals['t_number'] = normalise_number(country, vals['t_number'])[0]
        return vals

    @api.model
    def _pb_check(self, kind, vals, member=None, attachment=None):
        if kind not in TAX_KINDS:
            return super()._pb_check(kind, vals, member=member,
                                     attachment=attachment)
        country = vals.get('t_country') or ''
        emp = self.env['hr.employee'].sudo().browse(
            self.env.context.get('pbtx_employee') or 0)
        if kind == 'tax_number':
            if not vals.get('t_number'):
                if vals.get('t_use_nik'):
                    raise UserError(_("There is no national ID number (NIK) on "
                                      "your record. Type your NPWP instead."))
                raise UserError(_("Write your tax number."))
            _number, problem = normalise_number(country, vals['t_number'])
            if problem == 'vn':
                raise UserError(_("A personal tax code has 10 digits, or 12 "
                                  "when it is the number on your chip ID card."))
            if problem == 'id':
                if vals.get('t_use_nik'):
                    raise UserError(_("The national ID number on your record "
                                      "is not a 16-digit NIK. Type your NPWP "
                                      "instead."))
                raise UserError(_("An NPWP has 15 digits, or 16 when your NIK "
                                  "is used as your NPWP."))
            if problem == 'in':
                raise UserError(_("A PAN has 10 characters: 5 letters, 4 "
                                  "numbers and 1 letter, for example "
                                  "ABCDE1234F."))
            if problem:
                raise UserError(_("Write your tax number."))
            field = NUMBER_FIELD.get(country)
            if emp and field in emp._fields and emp[field] == vals['t_number']:
                raise UserError(_("That number is already on your record."))
        else:
            req_field = REQUEST_FIELD[kind]
            if not vals.get(req_field):
                raise UserError(_("Choose one of the options."))
            field = CHOICE_FIELD.get((kind, country))
            if emp and field in emp._fields and emp[field] == vals[req_field]:
                raise UserError(_("That is already what your record says."))
        if kind in PROOF_REQUIRED and not attachment:
            raise UserError(_("Add a photo or scan that shows it, so HR can "
                              "check it."))

    # ============================================== what it changes
    def _pbtx_target(self):
        """`(employee field, value)` this request writes when approved."""
        self.ensure_one()
        if self.kind == 'tax_number':
            return NUMBER_FIELD.get(self.t_country), self.t_number
        field = CHOICE_FIELD.get((self.kind, self.t_country))
        return field, self[REQUEST_FIELD[self.kind]] if field else False

    def _pb_now(self):
        self.ensure_one()
        if self.kind not in TAX_KINDS:
            return super()._pb_now()
        field, _value = self._pbtx_target()
        emp = self.employee_id.sudo()
        return {'value': emp[field] if field and field in emp._fields else ''}

    def _pb_apply(self):
        """Write exactly what was approved, under sudo (the approver may hold
        no right on the employee's tax fields — ledger W2B-2/S6A-1); `sudo()`
        keeps the uid, so the trail names them."""
        self.ensure_one()
        if self.kind not in TAX_KINDS:
            return super()._pb_apply()
        rec = self.sudo()
        emp = rec.employee_id.sudo()
        field, value = rec._pbtx_target()
        if not field or field not in emp._fields or not value:
            raise UserError(_("This tax detail cannot be kept for this person."))
        emp.write({field: value})
        rec._pbtx_file_proof()
        return super()._pb_apply()

    def _pbtx_file_proof(self):
        """The proof goes into the person's documents, verified by the
        approver (their approval IS the check). The SAME file record moves
        there — it is stored once."""
        self.ensure_one()
        rec = self.sudo()
        att = rec.attachment_id
        if not att:
            return False
        category = self.env.ref(TAX_CATEGORY, raise_if_not_found=False) \
            or self.env.ref('pb_employee_vault.cat_other', raise_if_not_found=False)
        if not category:
            return False
        doc = self.env['pb.employee.document'].sudo().create({
            'employee_id': rec.employee_id.id,
            'category_id': category.id,
            'name': rec.pb_label(),
            'attachment_id': att.id,
            'company_id': rec.company_id.id,
        })
        att.write({'res_model': 'pb.employee.document', 'res_id': doc.id})
        doc.write({'verified': True, 'verified_by': self.env.uid,
                   'verified_at': fields.Datetime.now()})
        rec.write({'document_id': doc.id})
        return doc

    # ======================================================== the inbox
    def _chain_revision_values(self):
        """The proposed tax value is part of what is agreed — added ONLY for
        tax kinds, so the fingerprint of every other request is unchanged
        (ledger W2A-2)."""
        res = super()._chain_revision_values()
        if self.kind in TAX_KINDS:
            rec = self.sudo()
            res['tax'] = [rec.t_country or '', rec.t_number or '',
                          rec.t_ptkp or '', rec.t_regime or '', rec.t_fund or '']
        return res

    def _pbtx_value_text(self, value, kind=None, full=True):
        kind = kind or self.kind
        if kind == 'tax_number':
            return (value or '') if full else mask(value)
        field = REQUEST_FIELD.get(kind)
        options = dict(self._fields[field]._description_selection(self.env))
        return options.get(value, value or '')

    def _pb_rows(self, full=True):
        """`[(label, now, proposed)]`. `full=False` masks numbers (the
        employee's own read-only page)."""
        self.ensure_one()
        if self.kind not in TAX_KINDS:
            return super()._pb_rows()
        rec = self.sudo()
        try:
            before = json.loads(rec.before_json or '{}')
        except (TypeError, ValueError):
            before = {}
        _field, proposed = rec._pbtx_target()
        return [(rec._pbtx_kind_label(),
                 rec._pbtx_value_text(before.get('value'), full=full),
                 rec._pbtx_value_text(proposed, full=full))]

    def _approval_detail(self, request):
        res = super()._approval_detail(request)
        rec = self.sudo()
        _ = self.env._
        chips = list(res.get('chips') or [])
        if rec.kind in TAX_KINDS:
            chips.insert(0, {'label': _('Country'),
                             'value': rec.employee_id._pbtx_country_name(
                                 rec.t_country)})
            if rec.kind in PROOF_REQUIRED and not rec.attachment_id:
                chips.append({'label': _('Proof'), 'value': _('Missing')})
            chips.append({'label': _('Pay'),
                          'value': _('Changes only if a pay rule reads it')})
        vietnam = rec.t_country == 'VN' or (
            rec.kind in ('family_add', 'family_change', 'family_remove')
            and (rec.company_id.country_id.code or '') == 'VN')
        if vietnam and rec.employee_id.sudo().pb_vn_dependants_check:
            chips.append({'label': _('Tax dependants'),
                          'value': _('Do not match the contract')})
        res['chips'] = chips
        return res

    # ============================================== what the person reads
    @api.model
    def _pb_page_domain(self):
        """Tax requests live on /my/tax, not on My details."""
        return super()._pb_page_domain() + [('kind', 'not in', list(TAX_KINDS))]

    def _pbtx_kind_label(self):
        self.ensure_one()
        if self.kind == 'tax_number':
            return self.employee_id._pbtx_number_label(self.t_country)
        return dict(self._fields['kind']._description_selection(self.env)).get(
            self.kind, '')

    def pb_label(self):
        self.ensure_one()
        if self.kind not in TAX_KINDS:
            return super().pb_label()
        _ = self.env._
        rec = self.sudo()
        _field, proposed = rec._pbtx_target()
        return _("%(what)s: %(value)s", what=rec._pbtx_kind_label(),
                 value=rec._pbtx_value_text(proposed, full=False))

    def _pbtx_portal_row(self):
        self.ensure_one()
        return {
            'id': self.id, 'title': self.pb_label(), 'state': self.pb_portal_state(),
            'kind': self.kind, 'note': self.decision_note or '',
            'when': self.submitted_on or self.create_date,
        }
