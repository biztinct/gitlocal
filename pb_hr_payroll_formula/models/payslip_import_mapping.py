# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# COLROLES P3 — the four things a bank destination can be handed. Kept as a module
# constant because the studio's synthetic `b:<role>` cards, the import batch and the
# constraint below must agree on the spelling exactly once.
BANK_ROLES = ('acc_number', 'bank_name', 'bank_bic', 'acc_holder_name')


class HrPayslipImportMapping(models.Model):
    _name = 'hr.payslip.import.mapping'
    _description = 'Payslip Import Mapping'
    _rec_name = 'target_field_id'
    _order = 'id desc'

    # ------------------------------------------------------------------
    # COLROLES P3 — where a mapped column LANDS.
    #
    # Until now every mapping meant one thing: copy this component's imported value
    # onto that employee/contract field. Bank details do not fit that shape — an
    # account number, the bank's name and the holder's name are three columns that
    # together make ONE `res.partner.bank` record, and there is no single scalar
    # field to point at. So the destination becomes a choice, and a bank row carries
    # a `bank_role` instead of a model/field pair.
    #
    # NO SQL uniqueness constraint anywhere in this model, deliberately: the live
    # databases predate every rule here and may hold duplicate rows, and an upgrade
    # that cannot install is a far worse outcome than a duplicate mapping. 1:1 is
    # enforced where it is actually created (the studio's create RPC), not by
    # bricking a running system.
    # ------------------------------------------------------------------
    destination_type = fields.Selection([
        ('field', 'Employee or contract field'),
        ('bank_account', 'Bank account'),
    ], string='Destination', default='field', required=True,
        help="Where the imported column lands. A field destination copies the value "
             "onto one employee or contract field; a bank destination builds the "
             "employee's bank account from several columns at once.")

    bank_role = fields.Selection([
        ('acc_number', 'Account number'),
        ('bank_name', 'Bank name'),
        ('bank_bic', 'SWIFT / BIC code'),
        ('acc_holder_name', 'Account holder name'),
    ], string='Bank Detail',
        help="Which part of the employee's bank account this column carries.")

    target_model_id = fields.Many2one(
        'ir.model',
        string='Model',
        ondelete='cascade',
        domain="[('model', 'in', ('hr.employee', 'hr.contract'))]"
    )
    target_field_id = fields.Many2one(
        'ir.model.fields',
        string='Field',
        ondelete='cascade',
        domain=(
            "[('model_id', '=', target_model_id),"
            " ('readonly', '=', False),"
            " ('ttype', 'not in', ('one2many', 'many2many'))]"
        )
    )
    salary_structure_id = fields.Many2one(
        'hr.formula.config',
        string='Salary Structure',
        required=True,
        # Setup metadata, not payroll history: these go with the configuration
        # rather than blocking its removal (required + no ondelete would have
        # defaulted to RESTRICT and made a merely-configured config undeletable).
        ondelete='cascade',
    )
    component_id = fields.Many2one(
        'hr.formula.rule',
        string='Component',
        domain="[('config_id', '=', salary_structure_id)]"
    )

    # ------------------------------------------------------------------
    # Requiredness moved OUT of the field definitions and into Python.
    #
    # `target_model_id`/`target_field_id` were `required=True`. They still are for a
    # field destination — but a NOT NULL column would make every bank row impossible
    # to store, and dropping the database constraint is the only way to have one
    # model serve both shapes. The messages below are what a person reads when they
    # get it wrong, so they say what to do rather than naming a column.
    # ------------------------------------------------------------------
    @api.constrains('destination_type', 'target_model_id', 'target_field_id', 'bank_role')
    def _check_destination(self):
        for mapping in self:
            if mapping.destination_type == 'bank_account':
                if not mapping.bank_role:
                    raise ValidationError(_(
                        "Choose which bank detail this column carries — the account "
                        "number, the bank name, the SWIFT/BIC code or the account "
                        "holder's name."))
            else:
                if not mapping.target_model_id or not mapping.target_field_id:
                    raise ValidationError(_(
                        "Choose the employee or contract field this column should be "
                        "copied onto."))
                if mapping.target_field_id.model_id != mapping.target_model_id:
                    raise ValidationError(_(
                        "The chosen field does not belong to the chosen record type."))

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._clean_destination_vals(v) for v in vals_list])

    def write(self, vals):
        # Only normalise when the destination itself is in play; a write that merely
        # touches `component_id` must not start clearing fields it was not asked about.
        if 'destination_type' in vals or 'bank_role' in vals:
            vals = self._clean_destination_vals(vals, partial=True)
        return super().write(vals)

    @api.model
    def _clean_destination_vals(self, vals, partial=False):
        """A bank row has no target field, and a field row has no bank role. Clearing
        the unused half here means every consumer can trust the shape rather than
        re-checking it — `_get_model_mappings` finds bank rows by their empty model,
        and the studio finds field rows by their empty bank role."""
        vals = dict(vals or {})
        destination = vals.get('destination_type')
        if destination == 'bank_account':
            vals['target_model_id'] = False
            vals['target_field_id'] = False
        elif destination == 'field' or (not partial and not destination):
            vals['bank_role'] = False
        return vals

    @api.depends('destination_type', 'bank_role', 'target_field_id', 'component_id')
    def _compute_display_name(self):
        """`_rec_name` is `target_field_id`, which a bank row does not have — without
        this every bank mapping would render as an empty name in a dropdown."""
        labels = dict(self._fields['bank_role'].selection)
        for mapping in self:
            if mapping.destination_type == 'bank_account':
                mapping.display_name = _("Bank account · %s") % (
                    labels.get(mapping.bank_role) or _("not chosen"))
            else:
                mapping.display_name = mapping.target_field_id.display_name or _("Unmapped")
