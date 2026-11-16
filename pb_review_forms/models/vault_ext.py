# -*- coding: utf-8 -*-
"""Owner ruling RV1 (2026-11-16): a finished review is for the employee, their
manager and the HR team who run reviews — NOT for payroll staff.

THE LEAK THIS CLOSES (ledger S9-F2). The documents vault lets every payroll
officer and every HR officer read every document (`pb_employee_vault`
`document_rule_hr_all`), and a payroll officer IS an HR officer here
(`om_hr_payroll.group_hr_payroll_user` implies `hr.group_hr_user`). A review
PDF filed there would therefore be readable by the whole payroll team.

HOW, FROM THIS MODULE ONLY (no edit of the vault's files):

  * a flag on the document, `pb_rf_private`, set by this module when it files
    a review PDF. Only the system (sudo) may set or clear it, so nobody can
    hide another document or un-hide a review;
  * a GLOBAL rule (`rule_review_document_private`, security file) — global
    rules are ANDed with every group's rules — that lets a private document
    through only for the person it is about, their direct manager, or a
    holder of the Goals HR rights (Goals administrator and up);
  * the PDF's file follows its document: an attachment linked to a record is
    readable only by somebody who may read that record.

Payroll keeps the NUMBER the pay review starts from: `pb.goal.set._pay_score`
works under sudo and returns only the overall result, never a comment.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class PbEmployeeDocumentReview(models.Model):
    _inherit = 'pb.employee.document'

    pb_rf_private = fields.Boolean(
        string='Private review', readonly=True, copy=False, index=True,
        help='A finished performance review. Only the person, their manager '
             'and the HR team who run reviews can open it.')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            for vals in vals_list:
                vals.pop('pb_rf_private', None)
        return super().create(vals_list)

    def write(self, vals):
        if 'pb_rf_private' in vals and not self.env.su:
            raise AccessError(_(
                "Whether a document is a private review is set by the "
                "system."))
        return super().write(vals)
