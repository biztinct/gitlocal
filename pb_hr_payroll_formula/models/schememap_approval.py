# -*- coding: utf-8 -*-
"""Who is paid by which scheme is a decision, not a drag.

WHAT WAS TRUE BEFORE. The "Who is paid by what" board wired a team or a
division to a pay scheme the moment somebody pressed Attach, and unwired it
the moment they pressed the cross. Accepting the drafted map moved hundreds of
people between schemes in one press. Each of those changes what those people
are paid the very next run.

WHAT IS TRUE NOW. Every one of them writes a proposal (`pb.schememap.proposal`)
and the move happens when the route says yes. The default is the payroll
manager, because the question "should Retail be paid by the Retail scheme?" is
a payroll question and not a finance one.

`pb.scheme.map.accept_draft` itself has no gate and keeps none: it is private
to the board, which is the only thing that calls it, and the board is what
this holds.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

SCHEMEMAP_PROCESS_KEY = 'schememap'

#: What moving people between schemes has always needed.
SCHEMEMAP_GROUP = 'pb_hr_payroll_formula.group_formula_manager'

#: "This write IS the approved change."
SCHEMEMAP_WRITE = 'pb_schememap_approved_write'


class PbSchemeMapProposal(models.Model):
    _name = 'pb.schememap.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed change to who is paid by what'

    _approval_process_key = SCHEMEMAP_PROCESS_KEY
    _proposal_prefix = 'SM'
    _proposal_gate_groups = (SCHEMEMAP_GROUP,)
    _proposal_kind_labels = {
        'attach': 'Wire a team to a scheme',
        'detach': 'Take a team off a scheme',
        'accept_draft': 'Accept the drafted map',
        'map_create': 'Add a scheme mapping',
        'map_delete': 'Remove a scheme mapping',
    }
    _proposal_fact_specs = {
        'employees_moved': {'type': 'int', 'label': 'People moved'},
        'schemes': {'type': 'int', 'label': 'Schemes involved'},
    }

    def _live_snapshot(self):
        self.ensure_one()
        payload = self.payload()
        Assign = self.env.get('hr.formula.scheme.assignment')
        if self.kind == 'detach' and Assign is not None:
            row = Assign.sudo().browse(
                int(payload.get('assignment_id') or 0)).exists()
            return {'exists': bool(row),
                    'config_id': row.config_id.id if row else 0}
        return {}

    # --------------------------------------------------------- the applies
    def _board(self):
        if 'pb.scheme.board' not in self.env:
            raise UserError(_(
                "The board that answers this is not installed any more."))
        return self.env['pb.scheme.board'].with_context(
            **{SCHEMEMAP_WRITE: True})

    def _apply_attach(self):
        payload = self.payload()
        self._board().attach(
            payload.get('segment'), payload.get('config_id'),
            payload.get('cycle_type') or 'any', payload.get('company_id'))
        return {'segment': payload.get('segment'),
                'config_id': payload.get('config_id')}

    def _apply_detach(self):
        payload = self.payload()
        self._board().detach(payload.get('assignment_id'),
                             payload.get('company_id'))
        return {'assignment_id': payload.get('assignment_id')}

    def _apply_accept_draft(self):
        payload = self.payload()
        result = self._board().accept_draft(payload.get('rows') or [],
                                            payload.get('company_id'))
        result.pop('board', None)
        return result

    def _apply_map_create(self):
        payload = self.payload()
        return self.env['pb.formula.studio'].with_context(
            **{SCHEMEMAP_WRITE: True}).scheme_mapping_create(
                *(payload.get('args') or []))

    def _apply_map_delete(self):
        payload = self.payload()
        return self.env['pb.formula.studio'].with_context(
            **{SCHEMEMAP_WRITE: True}).scheme_mapping_delete(
                *(payload.get('args') or []))

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(
            company, 'payroll_mgr',
            ('pb_hr_payroll_base.group_payroll_base_manager',
             'pb_hr_payroll_formula.group_formula_manager'))
        return Seed.lay(
            company, SCHEMEMAP_PROCESS_KEY, 'Who is paid by what',
            route(role_step(_('Payroll manager'), 'payroll_mgr')),
            binding_note='The route a change to which scheme pays which '
                         'people follows.',
            model_name='pb.schememap.proposal',
            role_keys=('payroll_mgr',),
            reason='Set up when scheme-map approvals were switched on')


class ResCompanySchemeMapSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.schememap.proposal']._approval_seed_default(
                    company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('scheme map: %s has no route yet',
                                  company.name)
        return companies


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.schememap.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('scheme map: %s has no route yet', company.name)
    return done
