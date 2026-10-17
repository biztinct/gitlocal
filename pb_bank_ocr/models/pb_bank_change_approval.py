# -*- coding: utf-8 -*-
"""Where somebody's pay is sent is its own question, with its own route.

WHAT WAS TRUE BEFORE. Two rungs in code: an HR payroll user, then somebody in
finance. The catalogue had no row for it at all — a bank-account change was
counted as an "employee record change", beside a new phone number.

WHAT IS TRUE NOW. Its own catalogue row, its own route, and the same two rungs
as the default: **HR lead, then the Finance approver**. The facts a route can
condition on are the ones that matter here — whether the name on the account
matches the employee's, and whether the account already belongs to somebody
else.

THE MASTER IS STILL WRITTEN BY ONE PATH. `_apply_to_master` runs from
`_after_approval_transition('approved')`, exactly as before; under a route it
is reached only when the whole route has said yes.
"""

import logging

from odoo import _, api, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_chain, role_step, route,
)

_logger = logging.getLogger(__name__)

BANKCHANGE_PROCESS_KEY = 'bankchange'

register_chain(
    'pb.bank.change.request', BANKCHANGE_PROCESS_KEY,
    submit_state='hr_review',
    driven=('finance_review', 'approved'),
)


class PbBankChangeRequestApproval(models.Model):
    _inherit = 'pb.bank.change.request'

    _approval_process_key = BANKCHANGE_PROCESS_KEY

    def _chain_title(self):
        self.ensure_one()
        return _("Bank account · %s", self.employee_id.name or '')

    def _chain_facts(self):
        self.ensure_one()
        return {
            'bank': {'value': self.x_bank_name or '', 'unit': ''},
            'name_match': {'value': float(self.name_match_score or 0.0),
                           'unit': '%'},
            'name_match_band': {'value': self.name_match_band or '',
                                'unit': ''},
            'duplicate': {'value': bool(self.duplicate_ids), 'unit': ''},
            'format_ok': {'value': bool(self.v_format_ok), 'unit': ''},
        }

    @api.model
    def _chain_fact_specs(self):
        return {
            'bank': {'type': 'char', 'label': _('Bank')},
            'name_match': {'type': 'percent',
                           'label': _('How well the name matches')},
            'name_match_band': {'type': 'selection',
                                'label': _('Name match')},
            'duplicate': {'type': 'bool',
                          'label': _('Somebody else already uses this '
                                     'account')},
            'format_ok': {'type': 'bool',
                          'label': _('The account number looks right')},
        }

    def _chain_revision_values(self):
        """The account is the thing being agreed, so the account is stamped.

        If a digit of it changes after the HR lead has said yes, the approval
        no longer covers what would be written to the employee's record — and
        this is the one door in the product where that means pay going to a
        different bank account.
        """
        self.ensure_one()
        return {
            'employee': self.employee_id.id,
            'bank': self.x_bank_name or '',
            'branch': self.x_bank_branch or '',
            'holder': self.x_account_name or '',
            'number': self.x_account_number or '',
            'iban': self.x_iban or '',
            'swift': self.x_swift or '',
        }

    def _approval_detail(self, request):
        """What is there now, and what it would become."""
        self.ensure_one()
        pairs = [
            (_('Bank'), self.cur_bank_name, self.x_bank_name),
            (_('Branch'), self.cur_bank_branch, self.x_bank_branch),
            (_('Account holder'), self.cur_account_name, self.x_account_name),
            (_('Account number'), self.cur_account_number,
             self.x_account_number),
        ]
        rows = [{'head': label, 'sub': '',
                 'cells': [old or _('Empty'), new or _('Empty')],
                 'tone': 'on' if (old or '') != (new or '') else 'off'}
                for label, old, new in pairs]
        chips = []
        if self.name_match_band:
            chips.append({'label': _('Name match'),
                          'value': dict(self._fields['name_match_band']
                                        .selection or []).get(
                              self.name_match_band,
                              self.name_match_band)})
        if self.duplicate_ids:
            chips.append({'label': _('Also used by'),
                          'value': str(len(self.duplicate_ids))})
        return {'title': _('The account'),
                'columns': [_('Now'), _('Proposed')],
                'rows': rows, 'chips': chips, 'note': ''}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead',
                                  'om_hr_payroll.group_hr_payroll_user')
        Seed.fill_role_from_group(company, 'finance',
                                  'om_hr_payroll.group_hr_payroll_manager')
        return Seed.lay(
            company, BANKCHANGE_PROCESS_KEY, 'Bank account changes',
            route(role_step(_('HR lead'), 'hr_lead'),
                  role_step(_('Finance approver'), 'finance')),
            binding_note='Two people look at a change to where pay is sent, '
                         'which is what the old two-step check did.',
            model_name='pb.bank.change.request',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when bank-change approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.bank.change.request']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('pb_bank_ocr: %s has no bank-change route',
                              company.name)
    return done
