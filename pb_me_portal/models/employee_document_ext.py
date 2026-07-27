# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ESS extensions to the Phase-H document vault.

Adds an `ess_uploadable` flag to the document CATEGORY so an admin controls which
categories an employee may self-upload into (e.g. certificates, IDs — but not,
say, disciplinary records). The employee own-CREATE record rule lives in
security/pb_me_portal_security.xml; `verified*` stay sentinel-guarded (Phase H).
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PbEmployeeDocumentCategory(models.Model):
    _inherit = 'pb.employee.document.category'

    ess_uploadable = fields.Boolean(
        string='Employee Self-Upload',
        help='Employees may upload documents in this category from the /my '
             'portal. HR-only categories leave this off.')

    def _ess_uploadable_categories(self):
        return self.search([('ess_uploadable', '=', True), ('active', '=', True)])


class PbEmployeeDocumentEss(models.Model):
    _inherit = 'pb.employee.document'

    @api.model_create_multi
    def create(self, vals_list):
        # Review I-M3: the self-upload category whitelist is enforced at the
        # MODEL, not only the portal route — a call_kw create into an
        # HR-authored category must not masquerade as HR filing.
        if not (self.env.su or self.env.user._is_admin() or self._is_hr()):
            Cat = self.env['pb.employee.document.category'].sudo()
            for vals in vals_list:
                cat = (Cat.browse(int(vals['category_id'])).exists()
                       if vals.get('category_id') else Cat)
                if not cat or not cat.ess_uploadable:
                    raise ValidationError(_(
                        "You can only self-upload documents in a category HR "
                        "has marked self-uploadable."))
        return super().create(vals_list)
