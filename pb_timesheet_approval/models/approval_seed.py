# -*- coding: utf-8 -*-
"""Day one signs a week off the way a business already does it.

"Their manager, then the HR lead" is what almost every timesheet approval is,
and it is what this module publishes for every company on install. It is a
ROUTE like any other from the moment it exists: changing it is a press in the
Matrix, not a code change.

IDEMPOTENT, three ways over, for the three moments it has to happen at — the
install hook, the migration (`post_init_hook` does NOT run on `-u`) and a
company created later. Each asks the database what is already there first.

IT ALSO REPOINTS THE CATALOGUE ROW. `biz.approval.process` "timesheet" shipped
naming `hr.attendance.weekentry`, which is a TransientModel — a screen's API
with no stored rows. A request has to point at a record that still exists next
month, so the row is repointed at `pb.timesheet.packet` here rather than in the
configuration module's data file: that file is `noupdate`, and an existing
database would keep the old name forever.
"""

import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)

#: The route every company gets, and the name it wears on the Matrix.
TIMESHEET_WORKFLOW_NAME = 'Weekly timesheet'

#: The model the catalogue row must name for the engine to call this adapter.
PACKET_MODEL = 'pb.timesheet.packet'


def _timesheet_definition():
    """Their manager reviews it, the HR lead approves it."""
    return {
        'schema_version': 1,
        'steps': [
            {'key': 's1', 'kind': 'review', 'title': 'Their manager',
             'who': {'mode': 'manager'}, 'min_amount': 0, 'condition': None},
            {'key': 's2', 'kind': 'approve', 'title': 'HR lead',
             'who': {'mode': 'role', 'role': 'hr_lead', 'scope': 'area'},
             'min_amount': 0, 'condition': None},
        ],
        'tiers': {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': True,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'working_days', 'days': 2, 'day': 15,
                    'calendar_id': None},
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


class PbTimesheetPacketSeed(models.Model):
    _inherit = 'pb.timesheet.packet'

    @api.model
    def _repoint_process(self):
        """Make the catalogue row name the record, not the screen."""
        process = self.env['biz.approval.process']._by_key('timesheet')
        if process and process.model_name != PACKET_MODEL:
            process.sudo().write({'model_name': PACKET_MODEL})
        return process

    @api.model
    def _approval_seed_default(self, company):
        """Give one company its published weekly-timesheet route."""
        process = self._repoint_process()
        if not process:
            _logger.info('pb_timesheet_approval: no timesheet process in the '
                         'catalogue yet')
            return False
        Role = self.env['biz.approval.role'].sudo()
        hr_lead = Role.search([('key', '=', 'hr_lead')], limit=1)
        if not hr_lead:
            _logger.info('pb_timesheet_approval: the responsibility catalogue '
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
                'name': TIMESHEET_WORKFLOW_NAME,
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
                    'definition': _timesheet_definition(),
                })
            # `with_user(...).sudo()` and not one or the other — AM26.
            engine = self.env['biz.approval.engine'].with_user(publisher).sudo()
            checks = engine.validate_for_publish(version.id)
            if checks['errors']:
                _logger.warning('pb_timesheet_approval: the default weekly '
                                'route was refused: %s',
                                [e['code'] for e in checks['errors']])
                return False
            engine.publish(
                version.id, version.draft_revision, None,
                'Set up when weekly timesheet approvals were switched on',
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
                'note': 'The route every week follows unless a part of the '
                        'business is given its own.',
            })
        return True


def seed_all(env):
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['pb.timesheet.packet']._approval_seed_default(company):
                done += 1
        except Exception:   # noqa: BLE001 — an install must not die on a seed
            _logger.exception('pb_timesheet_approval: %s has no weekly route '
                              'yet', company.name)
    _logger.info('pb_timesheet_approval: %s companies have a weekly route',
                 done)
    return done


def post_init_hook(env):
    seed_all(env)


class ResCompanySeed(models.Model):
    _inherit = 'res.company'

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        for company in companies:
            try:
                self.env['pb.timesheet.packet']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company must still be created
                _logger.exception('pb_timesheet_approval: %s has no weekly '
                                  'route yet', company.name)
        return companies
