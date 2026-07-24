# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ESS extensions to the Phase-H document vault.

Adds an `ess_uploadable` flag to the document CATEGORY so an admin controls which
categories an employee may self-upload into (e.g. certificates, IDs — but not,
say, disciplinary records). The employee own-CREATE record rule lives in
security/pb_me_portal_security.xml; `verified*` stay sentinel-guarded (Phase H).
"""

from odoo import fields, models


class PbEmployeeDocumentCategory(models.Model):
    _inherit = 'pb.employee.document.category'

    ess_uploadable = fields.Boolean(
        string='Employee Self-Upload',
        help='Employees may upload documents in this category from the /my '
             'portal. HR-only categories leave this off.')

    def _ess_uploadable_categories(self):
        return self.search([('ess_uploadable', '=', True), ('active', '=', True)])
