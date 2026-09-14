# -*- coding: utf-8 -*-
"""The four Vietnam statutory doors, on the route the business chose.

WHAT WAS TRUE BEFORE.

  * `vietnam.tax.table.action_create_default_slabs` deleted every band in a
    tax table and wrote seven new ones. One press.
  * `vietnam.insurance.adjustment.action_apply` marked an adjustment applied
    to payroll, and an ordinary payroll USER could press it.
  * The insurance policy and the tax bands were plain forms: whoever could
    open one could change what the whole country pays.

WHAT IS TRUE NOW. Each of them writes a proposal (`pb.statutory.proposal`) and
the change happens when the route says yes — by the approver, as themselves,
who must hold the payroll manager permission.

THE `write` HOOKS ASK FIRST WHETHER ANYBODY IS CHECKING. A proposal made
inside `write()` would have to return True for a change that has not happened
yet, so where the company has published "No approval needed" — or has no route
at all — the write is left completely alone. That is the one place in the
programme where the door looks at the route before deciding what to do, and
`route_mode` exists for it.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import AccessError

from odoo.addons.pb_hr_payroll_formula.models.statutory_approval import (
    STATUTORY_GROUP, STATUTORY_WRITE,
)

_logger = logging.getLogger(__name__)

#: Fields on the insurance policy that decide what somebody is PAID. A name, a
#: note or an internal flag is not a statutory change and is not held.
POLICY_MONEY_FIELDS = (
    'si_employer_rate', 'si_employee_rate', 'si_max_salary_ceiling',
    'hi_employer_rate', 'hi_employee_rate', 'hi_max_salary_ceiling',
    'ui_employer_rate', 'ui_employee_rate', 'ui_max_salary_ceiling',
    'effective_date', 'end_date', 'active',
)

#: The same question for one band of the income-tax table.
SLAB_MONEY_FIELDS = ('income_from', 'income_to', 'tax_rate', 'fixed_amount')


class StatutoryGateMixin(models.AbstractModel):
    """Shared by the two records whose plain form is the door."""
    _name = 'pb.statutory.gate.mixin'
    _description = 'Statutory write gate'

    _statutory_kind = ''
    _statutory_money_fields = ()

    def _statutory_held(self, vals):
        """Is this write one the business has asked somebody to check?"""
        if self.env.context.get(STATUTORY_WRITE):
            return False
        if not self or self.env.context.get('install_mode'):
            return False
        if 'pb.statutory.proposal' not in self.env:
            return False
        touched = [f for f in (vals or {})
                   if f in self._statutory_money_fields]
        if not touched:
            return False
        Proposal = self.env['pb.statutory.proposal']
        return Proposal.route_mode(
            company=self.env.company, kind_key=self._statutory_kind) == 'route'

    def write(self, vals):
        if not self._statutory_held(vals):
            return super().write(vals)
        Proposal = self.env['pb.statutory.proposal']
        for record in self:
            held = {k: v for k, v in vals.items()
                    if k in self._statutory_money_fields}
            Proposal.propose(
                self._statutory_kind,
                _("%(what)s · %(who)s",
                  what=Proposal._proposal_kind_labels.get(
                      self._statutory_kind, self._statutory_kind),
                  who=record.display_name or ''),
                payload={'values': held},
                snapshot={k: record[k] for k in sorted(held)
                          if k in record._fields},
                facts={'rows_changed': {'value': len(held), 'unit': ''},
                       'effective_date': {
                           'value': str(held.get('effective_date') or ''),
                           'unit': ''},
                       'configs_affected': {'value': 0, 'unit': ''}},
                target=record,
            )
        rest = {k: v for k, v in (vals or {}).items()
                if k not in self._statutory_money_fields}
        if rest:
            return super().write(rest)
        return True


class VietnamInsurancePolicyApproval(models.Model):
    _name = 'vietnam.insurance.policy'
    _inherit = ['vietnam.insurance.policy', 'pb.statutory.gate.mixin']

    _statutory_kind = 'policy_edit'
    _statutory_money_fields = POLICY_MONEY_FIELDS


class VietnamTaxSlabApproval(models.Model):
    _name = 'vietnam.tax.slab'
    _inherit = ['vietnam.tax.slab', 'pb.statutory.gate.mixin']

    _statutory_kind = 'slab_edit'
    _statutory_money_fields = SLAB_MONEY_FIELDS


class VietnamTaxTableApproval(models.Model):
    _inherit = 'vietnam.tax.table'

    def action_create_default_slabs(self):
        """Rebuilding every band in a table is a statutory change.

        The method DELETES what is there before it writes, so an unapproved
        press is not a draft anybody can walk back.
        """
        self.ensure_one()
        if self.env.context.get(STATUTORY_WRITE) \
                or 'pb.statutory.proposal' not in self.env:
            return super().action_create_default_slabs()
        proposal = self.env['pb.statutory.proposal'].propose(
            'tax_slabs',
            _("Rebuild the tax bands · %s", self.display_name or ''),
            payload={'table_id': self.id},
            snapshot={'bands': len(self.slab_ids)},
            facts={'rows_changed': {'value': len(self.slab_ids), 'unit': ''},
                   'effective_date': {'value': str(self.tax_year or ''),
                                      'unit': ''},
                   'configs_affected': {'value': 0, 'unit': ''}},
            target=self,
        )
        return self._statutory_notice(proposal)

    @api.model
    def _statutory_notice(self, proposal):
        answer = proposal.answer()
        if answer.get('applied'):
            message = _("The tax bands were rebuilt.")
        elif answer.get('with_whom'):
            message = _("Sent for approval — %s", answer['with_whom'])
        else:
            message = _("Sent for approval.")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'message': message,
                       'type': 'success' if answer.get('applied')
                       else 'info'},
        }


class VietnamInsuranceAdjustmentApproval(models.Model):
    _inherit = 'vietnam.insurance.adjustment'

    def action_apply(self):
        """Applying an adjustment to payroll moves somebody's money.

        It used to need nothing at all — an ordinary payroll user could press
        it. Now it needs the payroll manager permission and, by default, the
        country director as well.
        """
        self.ensure_one()
        if self.env.context.get(STATUTORY_WRITE) \
                or 'pb.statutory.proposal' not in self.env:
            return super().action_apply()
        user = self.env.user
        if not (user._is_superuser() or user.has_group(STATUTORY_GROUP)):
            raise AccessError(_(
                "Applying an insurance adjustment is a payroll manager's "
                "decision. Ask somebody who looks after payroll to do this."))
        self.env['pb.statutory.proposal'].propose(
            'insurance_adjust',
            _("Insurance adjustment · %s", self.display_name or ''),
            payload={'adjustment_id': self.id},
            snapshot={'state': self.state, 'difference': self.difference},
            facts={'rows_changed': {'value': 1, 'unit': ''},
                   'effective_date': {'value': str(
                       getattr(self, 'adjustment_date', '') or ''), 'unit': ''},
                   'configs_affected': {'value': 0, 'unit': ''}},
            target=self,
            amount=abs(float(self.difference or 0.0)),
        )
        return True
