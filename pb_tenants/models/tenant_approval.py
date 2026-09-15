# -*- coding: utf-8 -*-
"""What happens to a customer's own space is two people's decision.

WHAT WAS TRUE BEFORE. Pausing a customer, setting the clock that ends their
data, decommissioning them, starting or aborting a rollout to everybody,
changing what they pay for, switching a feature on across the estate — each of
those was one system administrator, one typed slug, one press. The typed slug
is a good rail against the WRONG customer. It is no rail at all against the
wrong DECISION.

WHAT IS TRUE NOW. Each writes a proposal (`pb.tenant.proposal`) and it happens
when the route says yes. The default route is the only one in the whole
product that asks for TWO of the same responsibility — two platform owners —
because these presses cannot be undone by pressing the button again. A
platform that is not ready for that sets the process to "No approval needed"
and gets its old behaviour back, press for press, with every use recorded.

THE TYPED SLUG STAYS, AND MOVES. It is still required, and it is still checked
against the tenant it names — at the moment the proposal is MADE, so a typo
never becomes a request about the wrong customer. It is carried on the
proposal so the request drawer can show what was typed.

PLATFORM ONLY. `pb_tenants` is never installed on a tenant database (the
tenant-module rule), so this route exists only where the fleet does.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

TENANT_PROCESS_KEY = 'tenant'

#: What any of these has always needed.
TENANT_GROUP = 'base.group_system'

#: "This write IS the approved change."
TENANT_WRITE = 'pb_tenant_approved_write'

#: The kinds that cannot be undone by pressing the button again. The typed
#: confirmation is required for these and only these.
DESTRUCTIVE = ('suspend', 'schedule_deletion', 'offboard', 'rollout_abort',
               'restore_staging')


class PbTenantProposal(models.Model):
    _name = 'pb.tenant.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed platform change'

    _approval_process_key = TENANT_PROCESS_KEY
    _proposal_prefix = 'PLT'
    _proposal_gate_groups = (TENANT_GROUP,)
    _proposal_kind_labels = {
        'suspend': 'Pause a customer',
        'schedule_deletion': 'Set the day their data may go',
        'offboard': 'Close a customer down',
        'rollout_start': 'Start a rollout',
        'rollout_abort': 'Stop a rollout',
        'set_plan': 'Change what a customer pays for',
        'features_bulk': 'Switch a feature across customers',
        'feature_save': 'Change a feature',
        'restore_staging': 'Restore a customer from a backup',
    }
    _proposal_fact_specs = {
        'kind': {'type': 'selection', 'label': 'What is being asked for'},
        'tenants_affected': {'type': 'int', 'label': 'Customers affected'},
        'destructive': {'type': 'bool', 'label': 'Cannot be undone'},
    }

    def _live_snapshot(self):
        """Where each customer this is about stands, right now.

        THE SHAPE IS THE SAME WHETHER OR NOT THERE ARE ANY. A snapshot is
        compared key by key, so an empty answer of `{}` beside a stored
        `{'states': []}` reads as "somebody changed `states` from nothing to
        nothing" and the change is refused. Two presses are about no customer
        in particular — editing the feature catalogue, and rolling a release
        out on a platform with no live customers yet — and both were quietly
        blocked by their own empty list.
        """
        self.ensure_one()
        Tenant = self.env.get('pb.tenant')
        if Tenant is None:
            return {}
        ids = [int(i) for i in ((self.payload() or {}).get('tenant_ids') or [])]
        rows = Tenant.sudo().browse(ids).exists() if ids else Tenant
        return {'states': sorted('%s:%s' % (t.slug, t.state) for t in rows)}

    # --------------------------------------------------------- the applies
    def _svc(self, model):
        if model not in self.env:
            raise UserError(_(
                "The fleet screens are not installed on this database."))
        return self.env[model].with_context(**{TENANT_WRITE: True})

    def _args(self):
        return (self.payload() or {}).get('args') or {}

    def _apply_suspend(self):
        return self._svc('pb.tenants').tenant_suspend(**self._args())

    def _apply_schedule_deletion(self):
        return self._svc('pb.tenants').tenant_schedule_deletion(**self._args())

    def _apply_offboard(self):
        return self._svc('pb.tenants').offboard(**self._args())

    def _apply_rollout_start(self):
        return self._svc('pb.tenants').rollout_start(**self._args())

    def _apply_rollout_abort(self):
        return self._svc('pb.tenants').rollout_abort(**self._args())

    def _apply_set_plan(self):
        return self._svc('pb.tenants').tenant_set_plan(**self._args())

    def _apply_features_bulk(self):
        return self._svc('pb.tenants').features_bulk(**self._args())

    def _apply_feature_save(self):
        return self._svc('pb.tenants').feature_save(**self._args())

    def _apply_restore_staging(self):
        return self._svc('pb.tenants').restore_staging(**self._args())

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        if 'pb.tenant' not in self.env:
            # Not a platform database. A tenant never gets this row.
            return False
        Seed = self.env['biz.approval.seed']
        Seed.fill_role_from_group(company, 'platform_owner',
                                  ('base.group_system',))
        return Seed.lay(
            company, TENANT_PROCESS_KEY, 'Customer accounts and rollouts',
            route(role_step(_('Platform owner'), 'platform_owner',
                            key='owner1'),
                  role_step(_('Platform owner'), 'platform_owner',
                            key='owner2')),
            binding_note='Two platform owners agree before a customer is '
                         'paused, closed or re-planned.',
            model_name='pb.tenant.proposal',
            role_keys=('platform_owner',),
            reason='Set up when platform approvals were switched on')


def propose_platform(env, kind, title, args, tenants=(), typed='',
                     reason=''):
    """Write a platform press down and ask. None means "carry on and do it".

    `tenants` is the recordset the press is about; its slugs go on the
    proposal so the drawer can name who this is about without the approver
    having to open another screen.
    """
    if env.context.get(TENANT_WRITE) or 'pb.tenant.proposal' not in env:
        return None
    rows = list(tenants or [])
    return env['pb.tenant.proposal'].propose(
        kind, title,
        payload={'args': args, 'tenant_ids': [t.id for t in rows],
                 'typed': typed},
        snapshot={'states': sorted('%s:%s' % (t.slug, t.state)
                                   for t in rows)},
        facts={'kind': {'value': kind, 'unit': ''},
               'tenants_affected': {'value': len(rows) or 1, 'unit': ''},
               'destructive': {'value': kind in DESTRUCTIVE, 'unit': ''}},
        scope_label=', '.join(t.slug for t in rows[:3]) or None,
        note=reason,
    ).answer()


def pending_answer(answer, what):
    """What a fleet screen says back when the press became a request."""
    return {
        'ok': True,
        'pending': True,
        'proposal_id': answer.get('proposal_id'),
        'reference': answer.get('reference'),
        'request_id': answer.get('request_id'),
        'with_whom': answer.get('with_whom'),
        'route': answer.get('route'),
        'message': _("%(what)s was sent for approval — it is with %(who)s.",
                     what=what,
                     who=answer.get('with_whom') or _('your approver')),
    }


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.tenant.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('platform: %s has no route yet', company.name)
    return done


def post_init_hook(env):
    seed_all(env)


class ResCompanyTenantSeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.tenant.proposal']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company is still created
                _logger.exception('platform: %s has no route yet',
                                  company.name)
        return companies
