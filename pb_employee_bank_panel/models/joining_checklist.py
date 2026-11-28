# -*- coding: utf-8 -*-
"""FS-9 follow-on A — the joining checklist's "Bank account" reads the
approved account.

`pb_onboarding` (`models/hr_employee.py` `PROFILE_FIELDS`,
`_compute_profile_complete`) counted "Bank account" as done when the old
free-text Account Number box was filled. That box is off every screen now, and
on rize / sudima nobody has it while 194 / 642 people have an approved account
— so every checklist listed "Bank account" as still to fill in.

Now "Bank account" follows the SAME rules as the side panel and Payroll-ready:

* done     — an approved account is on record (`hr.employee.pb_bank_on_record`);
* waiting  — a change is waiting for approval (the payment list's own rule,
  `pb.payment.list._pb_waiting_changes`): the person did their part, so it is
  NOT "still to fill in" and it counts as done in the percentage; it is said
  separately as "Sent, waiting for HR" (`pb_profile_waiting`);
* missing  — neither.

Every other line of the list is untouched: the loop below is pb_onboarding's,
over pb_onboarding's own `PROFILE_FIELDS` (imported, not re-typed), with the
one bank line swapped. Non-stored fields only — nothing is written.
"""

from odoo import api, fields, models

from odoo.addons.pb_onboarding.models.hr_employee import PROFILE_FIELDS

#: the line of PROFILE_FIELDS this module answers differently
BANK_LINE = 'account_number'


class HrEmployeeJoiningBank(models.Model):
    _inherit = 'hr.employee'

    pb_profile_waiting = fields.Char(
        compute='_compute_profile_complete', string='Sent, waiting for HR',
        help="Details this person has sent that are waiting for HR to approve.")

    def _pb_bank_profile_state(self):
        """'done' | 'waiting' | 'missing' for the checklist's bank line."""
        self.ensure_one()
        person = self.sudo()
        if person.pb_bank_on_record:
            return 'done'
        PL = self.env['pb.payment.list'].sudo()
        if (PL._pb_waiting_changes(person) or {}).get(person.id):
            return 'waiting'
        return 'missing'

    @api.depends('image_1920', 'birthday', 'sex', 'private_street',
                 'private_city', 'private_phone', 'emergency_contact',
                 'emergency_phone', 'identification_id',
                 'bank_account_ids', 'vietnam_bank_account_number')
    def _compute_profile_complete(self):
        for rec in self:
            filled, present, missing, waiting = 0, 0, [], []
            for fname, label in PROFILE_FIELDS:
                if fname == BANK_LINE:
                    present += 1
                    state = rec._pb_bank_profile_state() if rec.id else 'missing'
                    if state == 'missing':
                        missing.append(label)
                    else:
                        filled += 1
                        if state == 'waiting':
                            waiting.append(label)
                    continue
                if fname not in rec._fields:
                    continue
                present += 1
                try:
                    value = rec[fname]
                except Exception:       # noqa: BLE001 — a field-level ACL (as upstream)
                    present -= 1
                    continue
                if value:
                    filled += 1
                else:
                    missing.append(label)
            rec.profile_complete_pct = int(round(filled * 100.0 / present)) if present else 100
            rec.profile_missing = ', '.join(missing)
            rec.pb_profile_waiting = ', '.join(waiting)


class PbOnboardingJoiningBank(models.AbstractModel):
    _inherit = 'pb.onboarding'

    @api.model
    def _row(self, case, today=None):
        row = super()._row(case, today=today)
        emp = case.employee_id
        row['waiting'] = self._safe(lambda: emp.pb_profile_waiting, default='') or '' \
            if emp else ''
        return row
