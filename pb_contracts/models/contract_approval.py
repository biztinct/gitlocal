# -*- coding: utf-8 -*-
"""A contract's terms are money. Changing them is a decision.

WHAT WAS TRUE BEFORE. The contract drawer wrote. Somebody opened a person's
contract, typed a new wage or added an allowance, pressed Save, and the
contract changed — with a perfect per-value trail of a change nobody had
agreed to. The catalogue row that was supposed to cover it, "Salary and
contract changes", sat on the Matrix reading "Not connected yet" for two
phases.

WHAT IS TRUE NOW. Save evaluates, writes the plan down, and asks. The route
is the same one a pay change follows, because it is the same decision seen
from a different screen: the HR lead, then the finance approver when money
moves, then the country director.

THE SNAPSHOT IS THE TERMS THEMSELVES. At apply time the drawer re-reads the
contract and compares every value the proposal covers; a term somebody else
moved in between sends the whole thing back with that term named, rather than
half-writing a contract.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

CONTRACT_PROCESS_KEY = 'contract'

#: What changing a contract has always needed — the drawer's own write gate.
CONTRACT_GROUPS = ('hr_contract.group_hr_contract_manager',
                   'hr.group_hr_manager')

#: "This write IS the approved change."
CONTRACT_WRITE = 'pb_contract_approved_write'

#: The terms that move somebody's money. A note or a reference does not, and
#: a gate that held one would put a route in front of fixing a typo (the
#: narrowing AM53 already made for a live pay scheme).
MONEY_TERMS = ('wage', 'date_start', 'date_end', 'struct_id',
               'structure_type_id', 'resource_calendar_id', 'state')


class PbContractProposal(models.Model):
    _name = 'pb.contract.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed contract change'

    _approval_process_key = CONTRACT_PROCESS_KEY
    _proposal_prefix = 'CTR'
    _proposal_gate_groups = CONTRACT_GROUPS
    _proposal_manager_mode = True
    _proposal_kind_labels = {'terms': 'Change a contract'}
    _proposal_fact_specs = {
        'wage': {'type': 'decimal', 'label': 'New monthly pay'},
        'touches_pay': {'type': 'bool', 'label': 'Changes what they are paid'},
        'components': {'type': 'int', 'label': 'Components changed'},
    }

    # --------------------------------------------------------- the snapshot
    def _contract(self):
        self.ensure_one()
        if 'hr.contract' not in self.env or not self.target_id:
            return None
        record = self.env['hr.contract'].sudo().browse(
            self.target_id).exists()
        return record or None

    def _live_snapshot(self):
        """Every term this proposal covers, re-read from the contract."""
        self.ensure_one()
        contract = self._contract()
        if contract is None:
            return {}
        terms = (self.payload() or {}).get('terms') or {}
        return {key: contract[key] for key in sorted(terms)
                if key in contract._fields}

    def _approval_manager_uids(self):
        """Their own manager, read off the contract (ledger AM50)."""
        self.ensure_one()
        contract = self._contract()
        if contract is None:
            return []
        return contract.employee_id.sudo().parent_id.user_id.ids

    # ------------------------------------------------------------ the rows
    _TERM_WORDS = {
        'wage': 'Monthly pay', 'date_start': 'Starts', 'date_end': 'Ends',
        'struct_id': 'Salary structure', 'state': 'Status',
        'structure_type_id': 'Kind of contract',
        'resource_calendar_id': 'Working hours', 'name': 'Reference',
    }

    def _proposal_rows(self):
        self.ensure_one()
        payload = self.payload() or {}
        snapshot = self.snapshot() or {}
        contract = self._contract()
        rows = []
        if contract is not None:
            rows.append((_('Person'), '',
                         contract.employee_id.display_name or ''))
            rows.append((_('Contract'), '', contract.display_name or ''))
        for key, value in sorted((payload.get('terms') or {}).items()):
            rows.append((_(self._TERM_WORDS[key]) if key in self._TERM_WORDS
                         else str(key), snapshot.get(key, ''), value))
        for line in (payload.get('components') or [])[:20]:
            if not isinstance(line, dict):
                continue
            rows.append((str(line.get('label') or line.get('code') or ''),
                         line.get('old') if line.get('old') is not None else '',
                         line.get('new') if line.get('new') is not None
                         else line.get('amount', '')))
        return rows

    # ------------------------------------------------------------ the apply
    def _apply_terms(self):
        payload = self.payload()
        answer = self.env['pb.contracts'].with_context(
            **{CONTRACT_WRITE: True}).save_contract_360(
                payload.get('contract_id'), payload.get('terms'),
                payload.get('components'), payload.get('note'))
        if not (answer or {}).get('ok'):
            raise UserError((answer or {}).get('msg')
                            or _("The contract could not be changed."))
        return {'saved': answer.get('saved') or 0,
                'refusals': answer.get('refusals') or []}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'hr_lead', ('hr.group_hr_manager',))
        Seed.fill_role_from_group(
            company, 'finance', ('om_hr_payroll.group_hr_payroll_manager',))
        return Seed.lay(
            company, CONTRACT_PROCESS_KEY, 'Contract changes',
            route(role_step(_('HR lead'), 'hr_lead'),
                  role_step(_('Finance approver'), 'finance',
                            condition={'fact': 'touches_pay', 'op': 'eq',
                                       'value': True})),
            binding_note='The route a change to somebody\'s contract terms '
                         'follows.',
            model_name='pb.contract.proposal',
            role_keys=('hr_lead', 'finance'),
            reason='Set up when contract approvals were switched on')


class ResCompanyContractSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.contract.proposal']._approval_seed_default(
                    company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('contracts: %s has no route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.contract.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('contracts: %s has no route yet', company.name)
    return done


def post_init_hook(env):
    seed_all(env)
