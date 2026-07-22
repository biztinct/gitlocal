# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee bank-change history + the manual-edit audit hook (Phase D §3.3).

Clones the contract.component.change shape. Every change to the four
vietnam_bank_* master fields is captured: the approval path logs an
'ocr_request' row explicitly; a DIRECT edit on the employee (no from_bank_request
context) logs a 'manual' row here.
"""

from odoo import api, fields, models

_BANK_FIELDS = ('vietnam_bank_name', 'vietnam_bank_branch',
                'vietnam_bank_account_name', 'vietnam_bank_account_number')


class PbEmployeeBankHistory(models.Model):
    _name = 'pb.employee.bank.history'
    _description = 'Employee Bank Change History'
    _order = 'changed_at desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True, ondelete='cascade')
    change_source = fields.Selection([
        ('ocr_request', 'OCR Request'),
        ('manual', 'Manual Edit'),
    ], string='Source', required=True, default='manual')
    request_id = fields.Many2one('pb.bank.change.request', string='Request', index=True)

    old_bank_name = fields.Char(string='Old Bank')
    new_bank_name = fields.Char(string='New Bank')
    old_bank_branch = fields.Char(string='Old Branch')
    new_bank_branch = fields.Char(string='New Branch')
    old_account_name = fields.Char(string='Old Holder')
    new_account_name = fields.Char(string='New Holder')
    old_account_number = fields.Char(string='Old Account')
    new_account_number = fields.Char(string='New Account')

    changed_by = fields.Many2one(
        'res.users', string='Changed By', readonly=True,
        default=lambda self: self.env.user, index=True)
    changed_at = fields.Datetime(
        string='Changed At', readonly=True, default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', index=True,
                                 default=lambda self: self.env.company)


class HrEmployeeBankAudit(models.Model):
    _inherit = 'hr.employee'

    def write(self, vals):
        touched = [f for f in _BANK_FIELDS if f in vals]
        # The approval path writes with from_bank_request=True and logs its own
        # 'ocr_request' row — skip the manual audit there to avoid double rows.
        if not touched or self.env.context.get('from_bank_request'):
            return super().write(vals)

        before = {rec.id: {f: rec[f] for f in _BANK_FIELDS} for rec in self}
        res = super().write(vals)
        History = self.env['pb.employee.bank.history'].sudo()
        for rec in self:
            old = before.get(rec.id, {})
            if all((old.get(f) or '') == (rec[f] or '') for f in _BANK_FIELDS):
                continue  # nothing actually changed
            History.create({
                'employee_id': rec.id,
                'change_source': 'manual',
                'old_bank_name': old.get('vietnam_bank_name') or '',
                'new_bank_name': rec.vietnam_bank_name or '',
                'old_bank_branch': old.get('vietnam_bank_branch') or '',
                'new_bank_branch': rec.vietnam_bank_branch or '',
                'old_account_name': old.get('vietnam_bank_account_name') or '',
                'new_account_name': rec.vietnam_bank_account_name or '',
                'old_account_number': old.get('vietnam_bank_account_number') or '',
                'new_account_number': rec.vietnam_bank_account_number or '',
                'company_id': rec.company_id.id or self.env.company.id,
            })
        return res
