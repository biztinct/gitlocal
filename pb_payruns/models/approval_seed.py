# -*- coding: utf-8 -*-
"""Day one signs a pay run off exactly the way day zero did.

The ladder this phase removed was Payroll Officer → HR → Finance, and it was
the same on every database because it was written in the code. It is now a
published route like any other — so every company gets that route, published,
bound and filled with the people who hold those groups today. Nothing about who
approves a pay run changes on the day of the upgrade; what changes is that it
can now be changed.

IDEMPOTENT, three ways over, because there are three moments it has to happen
at: the install hook, the migration (a `post_init_hook` does NOT run on `-u` —
ledger), and a company created later. Each one asks the database what is
already there before it writes.

WHY THE PEOPLE ARE READ FROM THE OLD GROUPS. The engine never falls back to
"anybody in that group" — an unresolved seat is a stuck request with a named
fix. A route therefore needs NAMED people, and the only honest answer to "who
was the HR approver here yesterday?" is whoever held the group that used to
decide it. First holder becomes the person, second becomes their backup; where
a group is empty the seat is left empty and People & backups says so.
"""

import logging

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)

#: The route every company gets, and the name it wears on the Matrix.
PAYRUN_WORKFLOW_NAME = 'Pay run approval'

#: responsibility key -> (the group whose holders used to decide it, scope).
#: `area` means the person is looked up per part of the business, which is what
#: the HR lead has always been in practice.
SEED_ROLES = (
    ('payroll_mgr', 'pb_hr_payroll_base.group_payroll_base_officer'),
    ('hr_lead', 'pb_hr_payroll_base.group_payroll_base_manager'),
    ('finance', 'pb_hr_payroll_base.group_payroll_final_approver'),
)


def _payrun_definition():
    """Officer check → HR lead review → Finance approval."""
    def step(key, role, title, kind, scope):
        return {'key': key, 'kind': kind, 'title': title,
                'who': {'mode': 'role', 'role': role, 'scope': scope},
                'min_amount': 0, 'condition': None}

    return {
        'schema_version': 1,
        'steps': [
            step('s1', 'payroll_mgr', 'Payroll check', 'review', 'company'),
            step('s2', 'hr_lead', 'HR lead review', 'review', 'area'),
            step('s3', 'finance', 'Finance approval', 'approve', 'company'),
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
    """Whose name the trail carries. Never a background account (ledger AM26)."""
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


def _holders(env, company, xmlid):
    """The people who hold one of the old approval groups, in id order."""
    group = env.ref(xmlid, raise_if_not_found=False)
    if not group:
        return env['res.users']
    return env['res.users'].sudo().search([
        ('group_ids', 'in', group.id), ('active', '=', True),
        ('share', '=', False), ('company_ids', 'in', company.id),
        ('id', '!=', SUPERUSER_ID),
    ], order='id')


class HrPayslipRunSeed(models.Model):
    _inherit = 'hr.payslip.run'

    @api.model
    def _approval_seed_default(self, company):
        """Give one company its published pay-run route. Safe to repeat."""
        process = self.env['biz.approval.process']._by_key('payrun')
        if not process:
            # The catalogue lives in the configuration module. Without it there
            # is nothing to bind a route to, and saying so once is better than
            # inventing a process row this module does not own.
            _logger.info('pb_payruns: no pay-run process in the catalogue yet')
            return False
        Role = self.env['biz.approval.role'].sudo()
        roles = {key: Role.search([('key', '=', key)], limit=1)
                 for key, _xmlid in SEED_ROLES}
        if not all(roles.values()):
            _logger.info('pb_payruns: the responsibility catalogue is not '
                         'loaded yet')
            return False

        publisher = _publisher_for(self.env, company)
        Workflow = self.env['biz.approval.workflow'].sudo()
        Version = self.env['biz.approval.workflow.version'].sudo()
        Binding = self.env['biz.approval.binding'].sudo()
        Responsibility = self.env['biz.approval.responsibility'].sudo()

        workflow = Workflow.search([('company_id', '=', company.id),
                                    ('process_id', '=', process.id)], limit=1)
        if not workflow:
            workflow = Workflow.create({
                'name': PAYRUN_WORKFLOW_NAME,
                'company_id': company.id,
                'process_id': process.id,
                'owner_user_id': publisher.id,
            })

        # ------------------------------------------------------- the people
        # Before the publish, not after: the whole-coverage check runs at
        # publish time and a seat filled a second later would be reported as a
        # gap the publisher had to confirm.
        # Ever set up, held today or not: a seat the business ended is a
        # choice an upgrade must not undo (ledger AM101).
        for key, xmlid in SEED_ROLES:
            role = roles[key]
            held = Responsibility.with_context(active_test=False).search([
                ('company_id', '=', company.id), ('role_id', '=', role.id),
                ('scope_key', '=', '')], limit=1)
            if held:
                continue
            people = _holders(self.env, company, xmlid)
            if not people:
                continue
            Responsibility.create({
                'company_id': company.id,
                'role_id': role.id,
                'scope_key': '',
                'scope_label': company.name,
                'user_id': people[0].id,
                'backup_user_id': people[1].id if len(people) > 1 else False,
                'date_from': fields.Date.context_today(self),
                'note': 'Carried over from the old pay-run approval groups. '
                        'Change it in People & backups.',
            })

        # -------------------------------------------------------- the route
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
                    'definition': _payrun_definition(),
                })
            # `with_user(...).sudo()` and not one or the other: a company made
            # a moment ago has no members at all, so the company record rule
            # would refuse that person their own default route, while sudo()
            # lifts the rule WITHOUT changing env.uid — so the trail keeps the
            # honest name rather than a background account's (ledger AM26).
            engine = self.env['biz.approval.engine'].with_user(publisher).sudo()
            checks = engine.validate_for_publish(version.id)
            if checks['errors']:
                _logger.warning('pb_payruns: the default pay-run route was '
                                'refused: %s',
                                [e['code'] for e in checks['errors']])
                return False
            engine.publish(
                version.id, version.draft_revision, None,
                'Set up when pay-run approvals were switched on',
                [w['code'] for w in checks['warnings']])

        # ------------------------------------------------- where it applies
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
                'note': 'The route every pay run follows unless a pay scheme '
                        'or a part of the business is given its own.',
            })
        return True


def seed_all(env):
    """Every company on the database, in id order."""
    done = 0
    for company in env['res.company'].sudo().search([], order='id'):
        try:
            if env['hr.payslip.run']._approval_seed_default(company):
                done += 1
        except Exception:   # noqa: BLE001 — an install must not die on a seed
            _logger.exception('pb_payruns: %s has no pay-run route yet',
                              company.name)
    _logger.info('pb_payruns: %s companies have a pay-run route', done)
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
                self.env['hr.payslip.run']._approval_seed_default(company)
            except Exception:   # noqa: BLE001 — a company must still be created
                _logger.exception(
                    'pb_payruns: %s has no pay-run route yet', company.name)
        return companies
