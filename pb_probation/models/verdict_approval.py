# -*- coding: utf-8 -*-
"""A verdict that ends somebody's job is somebody else's decision too.

WHAT WAS TRUE BEFORE. A probation review and a performance plan both ended in
one press by one manager. "Pass" was that manager's to make and always should
be. "Fail", "extend" and "terminate" are the three that change what happens to
a person's employment, and they were exactly as easy to press.

WHAT IS TRUE NOW. `pass` is immediate, as it was. The other three write a
proposal (`pb.verdict.proposal`) and the verdict is recorded when the route
says yes. The default route is their manager and then the HR lifecycle team,
with a condition on the second step so a business that only wants the second
pair of eyes on a fail can say exactly that.

WHERE THIS LIVES. Two models can end this way — `pb.probation.review` and
`pb.pip.case` — and a catalogue row names ONE model, so the proposal sits in
`pb_probation`, which `pb_pip` already depends on.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    manager_step, role_step, route,
)

_logger = logging.getLogger(__name__)

VERDICT_PROCESS_KEY = 'verdict'

#: "This write IS the approved verdict."
VERDICT_WRITE = 'pb_verdict_approved_write'

#: The verdicts that are a decision about a person's employment. `pass` is
#: not one of them and never travels a route unless the business asks.
HELD_VERDICTS = ('fail', 'extend', 'terminate')


class PbVerdictProposal(models.Model):
    _name = 'pb.verdict.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed verdict'

    _approval_process_key = VERDICT_PROCESS_KEY
    _proposal_prefix = 'VER'
    _proposal_gate_groups = ()
    _proposal_kind_labels = {
        'fail': 'Not passed',
        'extend': 'Extended',
        'terminate': 'Closed because they are leaving',
    }
    _proposal_fact_specs = {
        'verdict': {'type': 'selection', 'label': 'The verdict'},
        'tenure_months': {'type': 'int', 'label': 'Months with the company'},
    }

    def _target(self):
        self.ensure_one()
        if not self.target_model or not self.target_id \
                or self.target_model not in self.env:
            return None
        record = self.env[self.target_model].sudo().browse(
            self.target_id).exists()
        return record or None

    def _live_snapshot(self):
        self.ensure_one()
        target = self._target()
        if target is None:
            return {}
        return {'state': target.state}

    def _approval_manager_uids(self):
        """Their own manager, read off the record.

        The mixin's default goes `subject_uids` → `hr.employee` → manager, and
        most people on a probation review have no login at all (ledger AM50).
        """
        self.ensure_one()
        target = self._target()
        if target is None or 'employee_id' not in target._fields:
            return []
        manager = target.employee_id.sudo().parent_id.user_id
        return manager.ids

    # --------------------------------------------------------- the applies
    def _carry_out(self):
        target = self._target()
        if not target:
            raise UserError(_("That review is no longer here."))
        payload = self.payload()
        record = target.with_context(**{VERDICT_WRITE: True})
        if self.kind == 'terminate':
            record.action_terminate(payload.get('reason'))
        else:
            record.action_verdict(**(payload.get('args') or {}))
        return {'record': target.display_name, 'verdict': self.kind}

    def _apply_fail(self):
        return self._carry_out()

    def _apply_extend(self):
        return self._carry_out()

    def _apply_terminate(self):
        return self._carry_out()

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'lifecycle',
                                  ('hr.group_hr_manager',))
        return Seed.lay(
            company, VERDICT_PROCESS_KEY, 'Probation and plan verdicts',
            route(manager_step(_('Their manager')),
                  role_step(
                      _('HR lifecycle team'), 'lifecycle',
                      condition={'fact': 'verdict', 'op': 'in',
                                 'value': ['fail', 'terminate']})),
            binding_note='The route a verdict that ends or extends somebody\'s '
                         'probation or plan follows.',
            model_name='pb.verdict.proposal',
            role_keys=('lifecycle',),
            reason='Set up when verdict approvals were switched on')


class ResCompanyVerdictSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.verdict.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('verdict: %s has no route yet', company.name)
        return companies


def propose_verdict(record, verdict, payload, tenure_months=0):
    """Write a verdict down and ask. None means "carry on and record it".

    Shared by the probation review and the performance plan, which are the
    same decision about two different kinds of record.
    """
    env = record.env
    if env.context.get(VERDICT_WRITE) or 'pb.verdict.proposal' not in env:
        return None
    if verdict not in HELD_VERDICTS:
        return None
    employee = record.employee_id if 'employee_id' in record._fields \
        else env['hr.employee']
    answer = env['pb.verdict.proposal'].propose(
        verdict,
        _("%(what)s · %(who)s",
          what=env['pb.verdict.proposal']._proposal_kind_labels.get(
              verdict, verdict),
          who=employee.display_name or record.display_name or ''),
        payload=payload,
        snapshot={'state': record.state},
        facts={'verdict': {'value': verdict, 'unit': ''},
               'tenure_months': {'value': int(tenure_months or 0),
                                 'unit': ''}},
        target=record,
        subject_uids=employee.user_id.ids,
    ).answer()
    if answer.get('applied'):
        return None
    return answer


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.verdict.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('verdict: %s has no route yet', company.name)
    return done


def post_init_hook(env):
    seed_all(env)
