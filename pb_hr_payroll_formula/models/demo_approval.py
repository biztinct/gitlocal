# -*- coding: utf-8 -*-
"""Demo data is only harmless on a demo database.

WHAT WAS TRUE BEFORE. "Load demo data" and "Generate the demo world" wrote
hundreds — on the big generator, tens of thousands — of employees, contracts
and payslips into whatever database they were pressed on. On a demo or a
template database that is the point. On a customer's own database it is a mess
somebody has to unpick by hand.

WHAT IS TRUE NOW. Pressing either writes a proposal where the database is NOT
a demo or template one, and the seeding happens when the route says yes. On a
demo or template database nothing changes: `is_demo_db` is a fact the route
can condition on and the default route waves it straight through.

WHERE THIS LIVES. The two doors are in `pb_demo_seed` and `pb_demo`, and
neither module depends on the other. A catalogue row names ONE model, so the
proposal sits in the only module both of them reach. The route is seeded only
where one of those doors actually exists — a customer database that has never
had a demo module installed gets no row it can do nothing with.
"""

import logging

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    role_step, route,
)

_logger = logging.getLogger(__name__)

DEMO_PROCESS_KEY = 'demo'

DEMO_GROUP = 'base.group_system'

#: "This write IS the approved change."
DEMO_WRITE = 'pb_demo_approved_write'

#: A database whose name ends one of these is a place demo data belongs.
DEMO_DB_MARKERS = ('_template', 'template', 'demo', 'test', 'walk', 'tpl')


def is_demo_db(env):
    """Is this a database demo data belongs on?

    Two answers, and the cheap one first: a database Odoo itself flagged as a
    demo install, then the name. Deliberately generous — the fact only decides
    whether the press is checked, and a route that stops somebody seeding a
    scratch database is a route nobody keeps.
    """
    if env['ir.module.module'].sudo().search_count(
            [('demo', '=', True)]):
        return True
    name = (env.cr.dbname or '').lower()
    return any(marker in name for marker in DEMO_DB_MARKERS)


class PbDemoProposal(models.Model):
    _name = 'pb.demo.proposal'
    _inherit = ['biz.approval.proposal.mixin']
    _description = 'Proposed demo data change'

    _approval_process_key = DEMO_PROCESS_KEY
    _proposal_prefix = 'DEM'
    _proposal_gate_groups = (DEMO_GROUP,)
    _proposal_kind_labels = {
        'load': 'Load a demo world',
        'remove': 'Remove a demo world',
        'generate': 'Generate the full demo world',
    }
    _proposal_fact_specs = {
        'records': {'type': 'int', 'label': 'Records'},
        'is_demo_db': {'type': 'bool', 'label': 'A demo database'},
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
        if target is not None and 'state' in target._fields:
            return {'state': target.state}
        return {}

    def _proposal_rows(self):
        self.ensure_one()
        target = self._target()
        rows = [(_('What'), '', self._proposal_kind_label())]
        if target is not None:
            rows.append((_('Demo world'), '', target.display_name or ''))
        rows.append((_('Is this a demo database?'), '', _('No')))
        rows.append((_('What happens'), '',
                     _('Demo people, contracts and payslips are written into '
                       'this database') if self.kind != 'remove'
                     else _('Every record that demo world made is removed')))
        return rows

    def _apply_load(self):
        target = self._target()
        if not target:
            raise UserError(_("That demo world no longer exists."))
        target.with_context(**{DEMO_WRITE: True}).action_load()
        return {'seed_id': target.id, 'state': target.state}

    def _apply_remove(self):
        target = self._target()
        if not target:
            raise UserError(_("That demo world no longer exists."))
        target.with_context(**{DEMO_WRITE: True}).action_remove()
        return {'seed_id': target.id, 'state': target.state}

    def _apply_generate(self):
        if 'pb.demo.generator' not in self.env:
            raise UserError(_(
                "The demo world builder is not installed any more."))
        self.env['pb.demo.generator'].with_context(
            **{DEMO_WRITE: True}).action_generate_all()
        return {'generated': True}

    # ------------------------------------------------------------- the seed
    @api.model
    def _approval_seed_default(self, company):
        Seed = self.env['biz.approval.seed']
        # THE ROW NAMES ITS RECORD EVEN WHERE NO ROUTE IS LAID.
        #
        # "Wired up" and "somebody has set a route up" are two different
        # questions, and the catalogue answers the first. This adapter is in
        # the registry on every payroll database, so the row can hold a
        # request — it simply has nothing to hold one ABOUT until a demo
        # module is installed. Pointing it only when the route is laid made
        # the Matrix say "Not connected yet", which says nobody is checking
        # it, about a row that is wired up and unused.
        Seed.point_process(DEMO_PROCESS_KEY, 'pb.demo.proposal')
        if 'pb.demo.seed' not in self.env \
                and 'pb.demo.generator' not in self.env:
            # Nothing on this database can make demo data, so a ROUTE for it
            # would be one the business can never use.
            return False
        Seed.fill_role_from_group(company, 'director', ('base.group_system',))
        return Seed.lay(
            company, DEMO_PROCESS_KEY, 'Demo data',
            route(role_step(_('Country director'), 'director')),
            binding_note='The route loading or removing demo data follows on '
                         'a database that is not a demo one.',
            model_name='pb.demo.proposal',
            role_keys=('director',),
            reason='Set up when demo-data approvals were switched on')


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.demo.proposal']._approval_seed_default(company):
                done += 1
        except Exception:       # noqa: BLE001 — an upgrade must not die here
            _logger.exception('demo: %s has no route yet', company.name)
    return done
