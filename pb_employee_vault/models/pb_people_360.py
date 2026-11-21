# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee 360 RPC facade — extends the People cockpit model (Phase H §3).

Adds one bundled read (``get_employee_360``) plus the vault mutations the drawer
drives (upload / verify / delete) and timeline paging. Every method is HR-gated
here (Phase H is an HR surface); the own-employee variant arrives in Phase I. All
document rules are ALSO enforced at the ORM layer (C18.32) — this facade is the
convenience gate, not the only one.
"""

import base64
import binascii
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

_HR_GROUP = 'om_hr_payroll.group_hr_payroll_user'
_HR_CORE_GROUP = 'hr.group_hr_user'
_MGR_GROUP = 'om_hr_payroll.group_hr_payroll_manager'
_HR_MGR_GROUP = 'hr.group_hr_manager'
_MIME_OK = ('image/png', 'image/jpeg', 'application/pdf')
_TIMELINE_PAGE = 100


class PbPeople(models.AbstractModel):
    _inherit = 'pb.people'

    # ------------------------------------------------------------------ gates
    def _vault_is_hr(self):
        u = self.env.user
        return (u.has_group(_HR_GROUP) or u.has_group(_HR_CORE_GROUP)
                or u._is_admin())

    def _vault_can_manage(self):
        u = self.env.user
        return (u.has_group(_MGR_GROUP) or u.has_group(_HR_MGR_GROUP)
                or u._is_admin())

    def _vault_unmask_wage(self):
        return self.env.user.has_group(_MGR_GROUP) or self.env.user._is_admin()

    def _require_hr(self):
        if not self._vault_is_hr():
            raise AccessError(_("Only HR can open the Employee 360 vault."))

    def _emp(self, employee_id):
        return self.env['hr.employee'].browse(int(employee_id)).exists()

    # ------------------------------------------------------------ serializers
    def _doc_payload(self, doc):
        today = date.today()
        dte = (doc.expiry_date - today).days if doc.expiry_date else None
        att = doc.attachment_id
        return {
            'id': doc.id,
            'name': doc.name,
            'category_id': doc.category_id.id,
            'category': doc.category_id.name,
            'category_code': doc.category_id.code,
            'requires_expiry': doc.category_id.requires_expiry,
            'issue_date': str(doc.issue_date) if doc.issue_date else '',
            'expiry_date': str(doc.expiry_date) if doc.expiry_date else '',
            'expiry_state': doc.expiry_state,
            'days_to_expiry': dte,
            'verified': doc.verified,
            'verified_by': doc.verified_by.name if doc.verified_by else '',
            'verified_at': (doc.verified_at
                            and doc.verified_at.strftime('%Y-%m-%d %H:%M') or ''),
            'note': doc.note or '',
            'file_url': ('/web/content/ir.attachment/%s/datas?download=true'
                         % att.id) if att else '',
            'view_url': ('/web/content/ir.attachment/%s/datas' % att.id)
            if att else '',
            'mimetype': att.mimetype if att else '',
            'file_name': att.name if att else '',
        }

    def _documents_for(self, emp):
        docs = self.env['pb.employee.document'].search(
            [('employee_id', '=', emp.id)], order='category_id, expiry_date, id')
        return [self._doc_payload(d) for d in docs]

    def _legacy_documents_for(self, emp):
        """Link old binary fields without moving or copying customer files."""
        result = []
        visible = emp.fields_get(['id_card', 'driving_license'])
        for name, label in [('id_card', _('ID card copy')), ('driving_license', _('Driving licence'))]:
            if name in visible and emp.with_context(bin_size=True)[name]:
                result.append({'field': name, 'label': label,
                               'url': '/web/content/hr.employee/%s/%s?download=true' % (emp.id, name)})
        return result

    def _categories(self):
        cats = self.env['pb.employee.document.category'].search([])
        return [{'id': c.id, 'name': c.name, 'code': c.code,
                 'requires_expiry': c.requires_expiry} for c in cats]

    def _costcenter(self, emp):
        c = emp.contract_id
        Contract = self.env['hr.contract']
        if c and 'costcenter' in Contract._fields:
            return getattr(c, 'costcenter', '') or ''
        return ''

    # ------------------------------------------------------------ bundled read
    @api.model
    def get_employee_documents(self, employee_id):
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            return {'error': _('Employee not found.')}
        emp.check_access('read')
        return {'documents': self._documents_for(emp), 'categories': self._categories(),
                'legacy_documents': self._legacy_documents_for(emp),
                'can_manage': self._vault_can_manage()}

    @api.model
    def get_employee_360(self, employee_id):
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            return {'error': _("Employee not found.")}
        unmask = self._vault_unmask_wage()
        profile = self.get_employee_detail(emp.id)
        vietnam = self._e360_vietnam(emp, unmask)
        if vietnam:
            profile['statutory'].update({k: vietnam[k] for k in (
                'tax', 'tax_label', 'insurance', 'insurance_label')})
        # safety rail 4: wage is manager-only — scrub the number from the payload
        # itself (two-tier serialization, NOT CSS hiding) so a non-manager's
        # browser never receives it.
        if not unmask and isinstance(profile, dict) and profile.get('contract'):
            profile['contract']['wage'] = False
            profile['contract']['wage_masked'] = True
        timeline = self.env['pb.employee.timeline']._collect(emp, unmask)
        return {
            'profile': profile,
            'details': self._e360_details(emp, unmask, vietnam=vietnam),
            'costcenter': self._costcenter(emp),
            'documents': self._documents_for(emp),
            'legacy_documents': self._legacy_documents_for(emp),
            'categories': self._categories(),
            'timeline': timeline[:_TIMELINE_PAGE],
            'timeline_total': len(timeline),
            'timeline_shown': min(len(timeline), _TIMELINE_PAGE),
            'can_manage': self._vault_can_manage(),
            'unmask_wage': unmask,
            'is_hr': True,
        }

    # --------------------------------------------- FILLIN P2 B4: the chip
    @api.model
    def fillin_pending(self, employee_id):
        """`{n, contract_id}` — answers Payobook filled in on this person's
        draft or running contracts that nobody has checked yet. A read: it
        writes nothing, and answers `n: 0` wherever the marks do not exist
        (FILLIN P1 lives in `pb_hr_payroll_formula`, not a dependency)."""
        blank = {'n': 0, 'contract_id': False}
        if not self._vault_is_hr():
            return blank
        emp = self._emp(employee_id or 0)
        Line = self.env.get('hr.contract.advantage')
        if not emp or Line is None or 'pb_fill' not in Line._fields:
            return blank
        contracts = self.env['hr.contract'].search(
            [('employee_id', '=', emp.id), ('state', 'in', ('draft', 'open'))])
        if not contracts:
            return blank
        lines = Line.sudo().search([
            ('contract_id', 'in', contracts.ids), ('pb_fill', '=', 'auto'),
            ('pb_checked_at', '=', False)])
        if not lines:
            return blank
        # the contract with the most to check opens; a running one wins a tie
        counts = {}
        for line in lines:
            counts[line.contract_id] = counts.get(line.contract_id, 0) + 1
        best = max(counts, key=lambda c: (counts[c], c.state == 'open', c.id))
        return {'n': len(lines), 'contract_id': best.id}

    @api.model
    def get_timeline_page(self, employee_id, offset=0):
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            return {'items': [], 'total': 0, 'shown': 0}
        items = self.env['pb.employee.timeline']._collect(
            emp, self._vault_unmask_wage())
        offset = max(int(offset or 0), 0)
        page = items[offset:offset + _TIMELINE_PAGE]
        return {'items': page, 'total': len(items),
                'shown': min(len(items), offset + len(page))}

    # --------------------------------------------------------- vault mutations
    @api.model
    def vault_upload(self, employee_id, category_id, payload,
                     issue_date=False, expiry_date=False, note=False):
        return self.vault_upload_batch(employee_id, category_id, [{
            'payload': payload, 'issue_date': issue_date,
            'expiry_date': expiry_date, 'note': note}])

    @api.model
    def vault_upload_batch(self, employee_id, category_id, documents):
        """One transaction per selection, with individual dates and private files."""
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            raise AccessError(_("Employee not found."))
        category = self.env['pb.employee.document.category'].browse(int(category_id)).exists()
        if not category or not category.active:
            raise ValidationError(_("Choose an active document category."))
        category.check_access('read')
        if not isinstance(documents, list) or not 1 <= len(documents) <= 20:
            raise ValidationError(_("Select between 1 and 20 files."))
        total = 0
        prepared = []
        for row in documents:
            payload = row.get('payload') or {}
            if payload.get('mime') not in _MIME_OK:
                raise AccessError(_("Only JPG, PNG or PDF documents are accepted."))
            data = payload.get('data') or ''
            if len(data) > 14 * 1024 * 1024:
                raise ValidationError(_("Each file must be 10 MB or smaller."))
            try:
                raw = base64.b64decode(data, validate=True)
            except (ValueError, TypeError, binascii.Error):
                raise ValidationError(_("The selected file could not be read."))
            if not raw or len(raw) > 10 * 1024 * 1024:
                raise ValidationError(_("Choose a non-empty file up to 10 MB."))
            total += len(raw)
            if total > 50 * 1024 * 1024:
                raise ValidationError(_("The selected files must total 50 MB or less."))
            issued = fields.Date.to_date(row.get('issue_date') or False)
            expires = fields.Date.to_date(row.get('expiry_date') or False)
            if category.requires_expiry and not expires:
                raise ValidationError(_("An expiry date is required for every '%s' file.", category.name))
            if issued and expires and expires < issued:
                raise ValidationError(_("Expiry must be on or after the issue date."))
            prepared.append((payload, issued, expires, row.get('note') or False))
        # All rows are validated before any file is saved; a later access/ORM
        # failure also rolls the entire batch back, including attachments.
        with self.env.cr.savepoint():
            for payload, issued, expires, note in prepared:
                att = self.env['ir.attachment'].create({
                    'name': payload.get('name') or _('document'),
                    'datas': payload['data'], 'mimetype': payload['mime'],
                })
                doc = self.env['pb.employee.document'].create({
                    'employee_id': emp.id, 'category_id': category.id,
                    'name': payload.get('title') or payload.get('name') or _('Document'),
                    'attachment_id': att.id, 'issue_date': issued,
                    'expiry_date': expires, 'note': note,
                    'company_id': emp.company_id.id or self.env.company.id,
                })
                att.write({'res_model': doc._name, 'res_id': doc.id})
        return self.get_employee_360(emp.id)

    @api.model
    def vault_verify(self, document_id, verified=True):
        self._require_hr()
        doc = self.env['pb.employee.document'].browse(int(document_id)).exists()
        if not doc:
            raise AccessError(_("Document not found."))
        if verified:
            doc.action_verify()
        else:
            doc.action_unverify()
        return self.get_employee_360(doc.employee_id.id)

    @api.model
    def vault_delete(self, document_id):
        self._require_hr()
        doc = self.env['pb.employee.document'].browse(int(document_id)).exists()
        if not doc:
            raise AccessError(_("Document not found."))
        emp_id = doc.employee_id.id
        # the ORM unlink rule enforces manager-only; a non-manager HR raises here
        doc.unlink()
        return self.get_employee_360(emp_id)
