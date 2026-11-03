# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrContractAdvantageChange(models.Model):
    _name = 'hr.contract.advantage.change'
    _description = 'Contract Component Change'
    _order = 'effective_date desc, id desc'

    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='contract_id.employee_id',
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='contract_id.company_id',
        store=True,
        readonly=True,
    )
    advantage_template_id = fields.Many2one(
        'hr.contract.advantage.template',
        string='Advantage Template',
        required=True,
    )
    advantage_template_code = fields.Char(
        string='Code',
        related='advantage_template_id.code',
        store=True,
        readonly=True,
    )
    old_amount = fields.Float(string='Old Amount')
    new_amount = fields.Float(string='New Amount')
    # Text-typed components (COLROLES) leave the two Floats at 0.0 and record the
    # before/after here instead, so one audit trail still covers both kinds.
    old_text_value = fields.Char(string='Old Text Value')
    new_text_value = fields.Char(string='New Text Value')
    effective_date = fields.Date(string='Effective Date', required=True)
    change_source = fields.Selection([
        ('import', 'Import'),
        ('import_default', 'Import Default'),
        ('manual', 'Manual'),
        # FILLIN P1 — a line Payobook wrote by itself from the paying scheme's
        # usual answer, and a person saying "that is right" without changing
        # it. Both are rows in the same trail so the History tab tells the
        # whole story of a value (FILLIN ledger D3).
        ('auto_default', "Filled in by Payobook from the scheme's usual answer"),
        ('checked', 'Checked, no change'),
    ], string='Source', default='import', required=True)
    import_batch_id = fields.Many2one(
        'hr.payroll.import.batch',
        string='Import Batch',
        readonly=True,
    )
    changed_by = fields.Many2one(
        'res.users',
        string='Changed By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    changed_at = fields.Datetime(
        string='Changed At',
        default=fields.Datetime.now,
        readonly=True,
    )
    notes = fields.Text(string='Notes')

    # ------------------------------------------------------------ the writer
    @api.model
    def log(self, contract, template, old, new, source, notes='', user=None,
            effective_date=None, import_batch=None, old_text=None,
            new_text=None):
        """One row of the trail, written the same way by every caller.

        FILLIN P1 — the import batch used to be the only writer of this shape
        (`_log_contract_component_change`); the fill-in and "Looks right" need
        the same row, so the shape lives on the model and the batch delegates.

        Runs in the CALLER's rights: the batch keeps exactly the access it
        always had, and the fill-in (which an HR user may trigger without
        rights on this model) calls it through `sudo()` on purpose.
        """
        user_id = user.id if isinstance(user, models.BaseModel) else (
            int(user) if user else self.env.uid)
        vals = {
            'contract_id': contract.id,
            'advantage_template_id': template.id,
            'old_amount': old or 0.0,
            'new_amount': new or 0.0,
            'effective_date': effective_date
            or fields.Date.context_today(self),
            'change_source': source,
            'import_batch_id': import_batch.id if import_batch else False,
            'notes': notes or False,
            'old_text_value': old_text or False,
            'new_text_value': new_text or False,
            'changed_by': user_id,
        }
        return self.create(vals)
