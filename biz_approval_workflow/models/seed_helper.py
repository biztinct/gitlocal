# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Laying one company's default route, once, from any adapter module.

WHY THIS IS IN THE ENGINE. By Phase 5 there are eight adapters that each need
the same forty lines: find the catalogue row, find the responsibilities it
names, make the workflow, make the first draft, validate it, publish it as a
real person, bind it to the whole company. Copied eight times it is eight
places for the publisher rule (ledger AM26) or the "already there?" check to
drift. The engine owns no business meaning here — the caller supplies the
process key, the name, the definition document and the sentence explaining the
binding.

IDEMPOTENT. Every step asks the database what is already there first, so the
install hook, a migration and a company created later can all call it in a row
and exactly one of everything exists afterwards.
"""

import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)


class BizApprovalSeed(models.AbstractModel):
    _name = 'biz.approval.seed'
    _description = 'Approval Default Route Seeder'

    # ------------------------------------------------------------- publisher
    @api.model
    def publisher_for(self, company):
        """Whose name the trail carries. Never a background account (AM26)."""
        user = self.env.user
        if (user and not user.share and user.active
                and company.id in user.company_ids.ids
                and user.id != SUPERUSER_ID):
            return user
        candidates = self.env['res.users'].sudo().search([
            ('share', '=', False), ('active', '=', True),
            ('company_ids', 'in', company.id), ('id', '!=', SUPERUSER_ID),
        ], order='id')
        for candidate in candidates:
            if candidate._is_admin():
                return candidate
        if candidates:
            return candidates[0]
        return self.env.ref('base.user_admin', raise_if_not_found=False) \
            or self.env['res.users'].browse(SUPERUSER_ID)

    # --------------------------------------------------------- the catalogue
    @api.model
    def point_process(self, process_key, model_name):
        """Make a catalogue row name the record that can actually hold a
        request. Done here rather than in the configuration module's data file
        because that file is ``noupdate`` and an existing database would keep
        the old name for ever (ledger AM45)."""
        process = self.env['biz.approval.process']._by_key(process_key)
        if process and model_name and process.model_name != model_name:
            process.sudo().write({'model_name': model_name})
        return process

    @api.model
    def roles_exist(self, keys):
        """Every responsibility key a definition names, or False."""
        Role = self.env['biz.approval.role'].sudo()
        found = {}
        for key in keys or ():
            role = Role.search([('key', '=', key)], limit=1)
            if not role:
                return False
            found[key] = role
        return found

    # --------------------------------------------------------------- the lay
    @api.model
    def lay(self, company, process_key, workflow_name, definition,
            binding_note='', model_name=None, role_keys=(), reason=''):
        """Give one company its published default route for one process.

        Returns True when the company ends up with a published, bound route —
        including when it already had one. False (with a log line, never an
        exception) when something it depends on is not loaded yet: the
        catalogue row, a responsibility the definition names, or a structural
        error in the definition itself.
        """
        process = self.point_process(process_key, model_name) \
            if model_name else self.env['biz.approval.process']._by_key(
                process_key)
        if not process:
            _logger.info('approval seed: no "%s" row in the catalogue yet',
                         process_key)
            return False
        if role_keys and not self.roles_exist(role_keys):
            _logger.info('approval seed: the responsibility catalogue is not '
                         'loaded yet for "%s"', process_key)
            return False

        publisher = self.publisher_for(company)
        Workflow = self.env['biz.approval.workflow'].sudo()
        Version = self.env['biz.approval.workflow.version'].sudo()
        Binding = self.env['biz.approval.binding'].sudo()

        workflow = Workflow.search([('company_id', '=', company.id),
                                    ('process_id', '=', process.id)], limit=1)
        if not workflow:
            workflow = Workflow.create({
                'name': workflow_name,
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
                    'definition': definition,
                })
            # `with_user(...).sudo()` and not one or the other: a company made a
            # moment ago has no members at all, so the company record rule would
            # refuse that person their own default route, while sudo() lifts the
            # rule WITHOUT changing env.uid — so the trail keeps the honest name
            # rather than a background account's (ledger AM26).
            engine = self.env['biz.approval.engine'].with_user(publisher).sudo()
            checks = engine.validate_for_publish(version.id)
            if checks['errors']:
                _logger.warning('approval seed: the default "%s" route was '
                                'refused: %s', process_key,
                                [e['code'] for e in checks['errors']])
                return False
            engine.publish(
                version.id, version.draft_revision, None,
                reason or 'Set up when approvals were switched on',
                [w['code'] for w in checks['warnings']])

        binding = Binding.search([
            ('company_id', '=', company.id),
            ('process_id', '=', process.id),
            ('scope_key', '=', ''), ('active', '=', True)], limit=1)
        if not binding:
            Binding.create({
                'company_id': company.id,
                'process_id': process.id,
                'scope_key': '',
                'scope_label': company.name,
                'kind_key': 'any',
                'workflow_id': workflow.id,
                'mode': 'follow',
                'note': binding_note or '',
            })
        return True
