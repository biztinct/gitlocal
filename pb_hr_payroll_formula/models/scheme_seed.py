# -*- coding: utf-8 -*-
"""Day one has a route for changing a pay scheme, and it is a published one.

"Scheme owner writes it, payroll manager checks it, the country director says
yes" is what a bureau does anyway; publishing it means it can be changed in the
Matrix rather than in code, and that every change is recorded.

IDEMPOTENT three ways over (install hook, migration, a company created later),
like every other seed in this programme. It also REPOINTS the catalogue row:
"Scheme change" shipped naming `hr.formula.config`, and what is approved is a
PROPOSAL to change one — the scheme itself is the subject, not the request.
"""

import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)

SCHEME_WORKFLOW_NAME = 'Scheme change'
PROPOSAL_MODEL = 'pb.scheme.proposal'


def _definition():
    """Scheme owner reviews, payroll manager approves, director signs."""
    def step(key, role, title, kind):
        return {'key': key, 'kind': kind, 'title': title,
                'who': {'mode': 'role', 'role': role, 'scope': 'company'},
                'min_amount': 0, 'condition': None}

    return {
        'schema_version': 1,
        'steps': [
            step('s1', 'scheme_owner', 'Scheme owner', 'review'),
            step('s2', 'payroll_mgr', 'Payroll manager', 'approve'),
            step('s3', 'director', 'Country director', 'approve'),
        ],
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


def _publisher_for(env, company):
    """Whose name the trail carries. Never a background account (AM26)."""
    user = env.user
    if (user and not user.share and user.active
            and company.id in user.company_ids.ids
            and user.id != SUPERUSER_ID):
        return user
    candidates = env['res.users'].sudo().search([
        ('share', '=', False), ('active', '=', True),
        ('company_ids', 'in', company.id), ('id', '!=', SUPERUSER_ID),
    ], order='id')
    for candidate in candidates:
        if candidate._is_admin():
            return candidate
    if candidates:
        return candidates[0]
    return env.ref('base.user_admin', raise_if_not_found=False) \
        or env['res.users'].browse(SUPERUSER_ID)


class PbSchemeProposalSeed(models.Model):
    _inherit = 'pb.scheme.proposal'

    @api.model
    def _repoint_process(self):
        process = self.env['biz.approval.process']._by_key('scheme')
        if process and process.model_name != PROPOSAL_MODEL:
            process.sudo().write({'model_name': PROPOSAL_MODEL})
        return process

    @api.model
    def _approval_seed_default(self, company):
        process = self._repoint_process()
        if not process:
            _logger.info('pb_hr_payroll_formula: no scheme-change process in '
                         'the catalogue yet')
            return False
        Role = self.env['biz.approval.role'].sudo()
        roles = {key: Role.search([('key', '=', key)], limit=1)
                 for key in ('scheme_owner', 'payroll_mgr', 'director')}
        if not all(roles.values()):
            _logger.info('pb_hr_payroll_formula: the responsibility catalogue '
                         'is not loaded yet')
            return False

        publisher = _publisher_for(self.env, company)
        Workflow = self.env['biz.approval.workflow'].sudo()
        Version = self.env['biz.approval.workflow.version'].sudo()
        Binding = self.env['biz.approval.binding'].sudo()

        workflow = Workflow.search([('company_id', '=', company.id),
                                    ('process_id', '=', process.id)], limit=1)
        if not workflow:
            workflow = Workflow.create({
                'name': SCHEME_WORKFLOW_NAME,
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
                    'workflow_id': workflow.id, 'revision': 1,
                    'status': 'draft', 'definition': _definition()})
            engine = self.env['biz.approval.engine'].with_user(publisher).sudo()
            checks = engine.validate_for_publish(version.id)
            if checks['errors']:
                _logger.warning('pb_hr_payroll_formula: the default scheme '
                                'route was refused: %s',
                                [e['code'] for e in checks['errors']])
                return False
            engine.publish(
                version.id, version.draft_revision, None,
                'Set up when scheme-change approvals were switched on',
                [w['code'] for w in checks['warnings']])

        binding = Binding.search([
            ('company_id', '=', company.id), ('process_id', '=', process.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        if not binding:
            Binding.create({
                'company_id': company.id, 'process_id': process.id,
                'scope_key': '', 'scope_label': company.name,
                'kind_key': 'any', 'workflow_id': workflow.id,
                'mode': 'follow',
                'note': 'The route every scheme change follows unless one '
                        'scheme is given its own.',
            })
        return True


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.scheme.proposal']._approval_seed_default(company):
                done += 1
        except Exception:   # noqa: BLE001 — an install must not die on a seed
            _logger.exception('pb_hr_payroll_formula: %s has no scheme-change '
                              'route yet', company.name)
    _logger.info('pb_hr_payroll_formula: %s companies have a scheme-change '
                 'route', done)
    return done
