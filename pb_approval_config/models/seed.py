# -*- coding: utf-8 -*-
"""Day one behaves the same as day zero.

Installing this module must not leave a company unable to ask for anything.
So every company gets, once and idempotently:

  * a published workflow called "Other request" — one approval step, decided by
    whoever holds the generic **Approver** responsibility for the company;
  * a binding that makes it the company default for the ``generic`` process;
  * that responsibility filled by the company's own administrator, so the very
    first request routes to a real person rather than blocking.

IDEMPOTENT, three times over. The hook runs on install; the migration mirrors
it for an upgrade (`post_init_hook` does NOT run on ``-u`` — ledger); and
``res.company.create`` runs it for a company made later. Each one asks the
database what is already there before writing, so running all three in a row
creates exactly one of everything.

WHY THE ADMINISTRATOR AND NOT A GROUP. The engine never falls back to "anybody
in that group": an unresolved seat is a stuck request with a named fix. A
default route therefore needs a NAMED person, and the only person this module
can know about at install time is whoever installed it (or the base
administrator). Changing it is the first thing People & backups is for.
"""

import logging

from odoo import SUPERUSER_ID, _, api, fields, models

from odoo.addons.biz_approval_workflow.models.chain_shim import (
    register_scope_catalogue, register_scope_resolver,
)

_logger = logging.getLogger(__name__)


# ======================================================================
# WHICH PART OF THE BUSINESS A REQUEST IS ABOUT
#
# The engine never parses a scope key (ledger AM2), so it cannot know that
# Payobook divides a company into divisions — and it must not, or it stops
# being able to run in a product that has never heard of one. It holds a hook
# instead; this is the Payobook answer to it, registered at import time.
#
# `pb.division` HAS NO `company_id` (ledger AM72): which companies a division
# belongs to is computed from its department links, so it cannot be searched
# on. Search them all and filter in Python, exactly as the Matrix's own
# division picker does.
# ======================================================================
def _division_scope(env, employee, on_date):
    """The division the person this request is about works in."""
    Division = env.get('pb.division')
    if Division is None or not employee:
        return []
    department = employee.sudo().department_id
    if not department:
        return []
    division = Division.sudo().division_for(department, on_date)
    if not division:
        return []
    return [{'key': 'division:%s' % division.id,
             'label': division.name or ''}]


def _division_catalogue(env, company):
    """Every division a request of this kind could come from."""
    Division = env.get('pb.division')
    if Division is None:
        return []
    rows = []
    for division in Division.sudo().search([], limit=200, order='name'):
        companies = division.company_ids
        if companies and company not in companies:
            continue
        rows.append({'key': 'division:%s' % division.id,
                     'label': division.name or '', 'headcount': 0})
    return rows


register_scope_resolver(_division_scope)
register_scope_catalogue(_division_catalogue)

#: The workflow every company gets, in the definition document's own shape.
GENERIC_WORKFLOW_NAME = 'Other request'


def _generic_definition():
    """One approval step, decided by the company-wide Approver."""
    return {
        'schema_version': 1,
        'steps': [{
            'key': 'approve',
            'kind': 'approve',
            'title': 'Approval',
            'who': {'mode': 'role', 'role': 'approver', 'scope': 'company'},
            'min_amount': 0,
            'condition': None,
        }],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': True,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }


def _admin_for(env, company):
    """The person a brand-new company's default route should reach.

    The installing user when they belong to the company, else any internal
    administrator of it, else the base administrator. Never a group.
    """
    user = env.user
    if (user and not user.share and user.active
            and company.id in user.company_ids.ids
            and user.id != SUPERUSER_ID):
        return user
    candidates = env['res.users'].sudo().search([
        ('share', '=', False), ('active', '=', True),
        ('company_ids', 'in', company.id),
        ('id', '!=', SUPERUSER_ID),
    ], order='id')
    for candidate in candidates:
        if candidate._is_admin():
            return candidate
    if candidates:
        return candidates[0]
    return env.ref('base.user_admin', raise_if_not_found=False) \
        or env['res.users'].browse(SUPERUSER_ID)


def seed_company(env, company):
    """Give one company its default route. Safe to run any number of times."""
    process = env['biz.approval.process']._by_key('generic')
    role = env['biz.approval.role'].sudo().search(
        [('key', '=', 'approver')], limit=1)
    if not process or not role:
        _logger.info('approval seed: the engine catalogue is not loaded yet')
        return False

    # WHO THE TRAIL SAYS DID THIS. Everything below is written during an
    # install, when the acting user is the platform's own background account —
    # so an unqualified publish writes "<that account> published Other
    # request" onto a screen a customer reads, under a name that is not the
    # product's. The company's own administrator is the honest answer and the
    # only person this module can know about, so the publish is made as them.
    publisher = _admin_for(env, company)

    Workflow = env['biz.approval.workflow'].sudo()
    Version = env['biz.approval.workflow.version'].sudo()
    Binding = env['biz.approval.binding'].sudo()
    Responsibility = env['biz.approval.responsibility'].sudo()

    # ------------------------------------------------------- the route
    workflow = Workflow.search([('company_id', '=', company.id),
                                ('process_id', '=', process.id)], limit=1)
    if not workflow:
        workflow = Workflow.create({
            'name': GENERIC_WORKFLOW_NAME,
            'company_id': company.id,
            'process_id': process.id,
            'owner_user_id': publisher.id,
        })
    version = workflow.version_ids.filtered(
        lambda v: v.status == 'published').sorted('revision')[-1:]
    if not version:
        version = workflow.version_ids.filtered(
            lambda v: v.status == 'draft').sorted('revision')[-1:]
        if not version:
            version = Version.create({
                'workflow_id': workflow.id,
                'revision': 1,
                'status': 'draft',
                'definition': _generic_definition(),
            })
        # Published as the company's administrator, confirming whatever the
        # engine says about a one-person route: that IS the choice being made
        # here, and it is theirs rather than a background account's.
        #
        # `with_user(...).sudo()` and not one or the other. A company created a
        # moment ago has NO members yet — not even an administrator — so the
        # company record rule would refuse that person their own default route
        # and the seed would leave the company unable to ask for anything.
        # `sudo()` lifts the rule without changing who `env.uid` is, so the
        # trail still says the administrator's name rather than a background
        # account's.
        # The whole-coverage scan is a publisher's question, not an install
        # hook's: it resolves every step against every place the process
        # happens, and this runs once per company per module. Skipped here and
        # recorded as skipped — the seed confirms every warning anyway.
        engine = env['biz.approval.engine'].with_user(publisher).sudo(
        ).with_context(approval_skip_coverage=True)
        checks = engine.validate_for_publish(version.id)
        if checks['errors']:
            _logger.warning('approval seed: default route refused: %s',
                            [e['code'] for e in checks['errors']])
            return False
        engine.publish(
            version.id, version.draft_revision, None,
            'Set up when approvals were switched on',
            [w['code'] for w in checks['warnings']])

    # ------------------------------------------------- where it applies
    binding = Binding.search([
        ('company_id', '=', company.id),
        ('process_id', '=', process.id),
        ('scope_key', '=', ''),
        ('active', '=', True),
    ], limit=1)
    if not binding:
        Binding.create({
            'company_id': company.id,
            'process_id': process.id,
            'scope_key': '',
            'scope_label': company.name,
            'kind_key': 'any',
            'workflow_id': workflow.id,
            'mode': 'follow',
            'note': 'The route every request follows unless a narrower one '
                    'is set up.',
        })

    # ------------------------------------------------------- the person
    held = Responsibility.search([
        ('company_id', '=', company.id),
        ('role_id', '=', role.id),
        ('scope_key', '=', ''),
        ('active', '=', True),
    ], limit=1)
    if not held:
        Responsibility.create({
            'company_id': company.id,
            'role_id': role.id,
            'scope_key': '',
            'scope_label': company.name,
            'user_id': publisher.id,
            'date_from': fields.Date.context_today(env['res.company']),
            'note': 'Chosen when approvals were switched on. Change it in '
                    'People & backups.',
        })

    seed_adapters(env, company)
    return True


def seed_adapters(env, company):
    """Let every business object that has a default route of its own lay it.

    WHY THIS IS A DUCK-TYPED LOOP AND NOT A LIST OF MODULES. A pay run's
    default route lives in `pb_payruns`, which this module must not depend on
    (the hubs depend on the configuration module, never the other way round).
    But which module installs FIRST is not something either of them chooses: if
    `pb_payruns` goes in before the process catalogue exists, its own hook finds
    no `payrun` row and correctly does nothing — and nothing would ever come
    back for it. So the catalogue's own seed asks, at the end, whether any model
    in the registry has a default route waiting to be laid.

    Every one of them is idempotent, which is what makes calling them from both
    ends safe.
    """
    laid = 0
    for name in list(env.registry.models):
        model = env[name]
        if not getattr(model, '_approval_process_key', None):
            continue
        if not hasattr(model, '_approval_seed_default'):
            continue
        try:
            if model._approval_seed_default(company):
                laid += 1
        except Exception:  # noqa: BLE001 — one adapter must not stop the rest
            _logger.exception('approval seed: %s has no default route for %s',
                              name, company.name)
    return laid


def seed_all(env):
    """Every company on the database, in id order."""
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        if seed_company(env, company):
            done += 1
    _logger.info('approval seed: %s companies have a default route', done)
    return done


def post_init_hook(env):
    seed_all(env)


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                seed_company(self.env, company)
            except Exception:  # noqa: BLE001 — a company must still be created
                _logger.exception(
                    'approval seed: %s has no default route yet', company.name)
        return companies


class BizApprovalProcessLabels(models.Model):
    """The catalogue, with the two words the screens need but the engine has
    no reason to hold: which icon a row wears, and what an area is called."""
    _inherit = 'biz.approval.process'

    #: Icon per area, from the shared `ic()` set. Held here rather than on the
    #: row so a new process never has to remember to pick one.
    AREA_ICONS = {
        'pay': 'zap',
        'money': 'banknote',
        'data': 'database',
        'people': 'users',
        'time': 'clock',
        'setup': 'sliders',
        'platform': 'server',
        'other': 'inbox',
    }

    def _area_icon(self):
        self.ensure_one()
        return self.AREA_ICONS.get(self.area or 'other', 'inbox')

    @api.model
    def _area_labels(self):
        return {
            'pay': _('Pay'),
            'money': _('Money out'),
            'data': _('Pay data'),
            'people': _('People'),
            'time': _('Time'),
            'setup': _('Setup & rules'),
            'platform': _('Platform'),
            'other': _('Other'),
        }
