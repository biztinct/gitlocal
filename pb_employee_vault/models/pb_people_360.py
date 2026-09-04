# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee 360 RPC facade — extends the People cockpit model (Phase H §3).

Adds one bundled read (``get_employee_360``) plus the vault mutations the drawer
drives (upload / verify / delete) and timeline paging. Every method is HR-gated
here (Phase H is an HR surface); the own-employee variant arrives in Phase I. All
document rules are ALSO enforced at the ORM layer (C18.32) — this facade is the
convenience gate, not the only one.
"""

from datetime import date

from odoo import api, models, _
from odoo.exceptions import AccessError

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
    def get_employee_360(self, employee_id):
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            return {'error': _("Employee not found.")}
        unmask = self._vault_unmask_wage()
        profile = self.get_employee_detail(emp.id)
        # safety rail 4: wage is manager-only — scrub the number from the payload
        # itself (two-tier serialization, NOT CSS hiding) so a non-manager's
        # browser never receives it.
        if not unmask and isinstance(profile, dict) and profile.get('contract'):
            profile['contract']['wage'] = False
            profile['contract']['wage_masked'] = True
        timeline = self.env['pb.employee.timeline']._collect(emp, unmask)
        return {
            'profile': profile,
            'costcenter': self._costcenter(emp),
            'documents': self._documents_for(emp),
            'categories': self._categories(),
            'timeline': timeline[:_TIMELINE_PAGE],
            'timeline_total': len(timeline),
            'timeline_shown': min(len(timeline), _TIMELINE_PAGE),
            'can_manage': self._vault_can_manage(),
            'unmask_wage': unmask,
            'is_hr': True,
        }

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
        """C18.25 attachment order: attachment first (no res binding), then the
        document, then bind res_model/res_id back."""
        self._require_hr()
        emp = self._emp(employee_id)
        if not emp:
            raise AccessError(_("Employee not found."))
        payload = payload or {}
        mime = payload.get('mime')
        if mime not in _MIME_OK:
            raise AccessError(_("Only JPG, PNG or PDF documents are accepted."))
        att = self.env['ir.attachment'].create({
            'name': payload.get('name') or _('document'),
            'datas': payload.get('data') or '',
            'mimetype': mime,
        })
        doc = self.env['pb.employee.document'].create({
            'employee_id': emp.id,
            'category_id': int(category_id),
            'name': payload.get('title') or payload.get('name') or _('Document'),
            'attachment_id': att.id,
            'issue_date': issue_date or False,
            'expiry_date': expiry_date or False,
            'note': note or False,
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
