# -*- coding: utf-8 -*-
"""R7 — a renewal ALWAYS carries the administrator's contract fields.

Both renewal paths build the new contract through ONE method,
`pb.people.contract.wizard.create_contract` (FS_HOST_FACTS §B.3):
the Renew button (Contracts page → `pb_contract_wizard`, `renew_from`) and
the contract lifecycle's "Extend" / "Make it permanent"
(`pb_contract_lifecycle` `_build_new_contract` → the same method, same
`renew_from`). That method copies an explicit list of standard terms and
nothing else, so custom fields were NOT carried. Here they are, after the
stock method has done everything it does — the trial / probation rules, the
Vietnam kind and treatment, the pay lines are all untouched.

The third path, the pay-data import's replacement contract
(`contract.copy(...)`, pb_hr_payroll_formula/models/payroll_import_batch.py),
already carries them: the contract host creates its fields `copied=True`.
Test 3 proves the two agree.

Copied with elevated rights on purpose: carrying is a rule of the system, not
an edit by the person renewing — a field they may not see is carried too.
"""
import logging

from odoo import api, models

from .form_studio_host import MODEL

_logger = logging.getLogger(__name__)


class PbContractWizard(models.AbstractModel):
    _inherit = 'pb.people.contract.wizard'

    @api.model
    def _fs3_carry_custom(self, old, new):
        """Write `old`'s custom field values onto `new`. → names written."""
        names = self.env['pb.form.studio'].sudo().copy_field_names(MODEL)
        if not names or not old or not new:
            return []
        old, new = old.sudo(), new.sudo()
        vals = {}
        for name in names:
            field = old._fields.get(name)
            if field is None:
                continue
            value = old[name]
            if field.type == 'many2one':
                value = value.id or False
            elif field.type in ('one2many', 'many2many'):
                continue
            if value in (False, None, '') and field.type != 'boolean':
                continue
            if field.type == 'boolean' and not value:
                continue
            vals[name] = value
        if vals:
            new.write(vals)
        return sorted(vals)

    @api.model
    def create_contract(self, vals):
        res = super().create_contract(vals)
        try:
            new_id = (res or {}).get('contract_id')
            old_id = (vals or {}).get('renew_from')
            if new_id and old_id and not (res or {}).get('error'):
                Contract = self.env['hr.contract'].sudo()
                new = Contract.browse(int(new_id)).exists()
                old = Contract.browse(int(old_id)).exists()
                if new and old and new != old and new.employee_id == old.employee_id:
                    with self.env.cr.savepoint():
                        self._fs3_carry_custom(old, new)
        except Exception:                               # noqa: BLE001
            # Never undo a renewal over a custom field: the new contract
            # stands and the log says what was not carried.
            _logger.exception('Form builder: custom fields not carried to the renewal of %s',
                              (vals or {}).get('renew_from'))
        return res
