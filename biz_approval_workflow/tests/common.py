# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Shared fixtures: one company, five people, and helpers to build a route.

Every case runs against biz.approval.generic.request — the reference adapter
that ships — so the tests prove the contract a later adapter has to meet, not a
stub written to make them pass.
"""

from odoo.tests import TransactionCase


def role_step(key, role_key, kind='approve', scope='area', title=None,
              min_amount=0, condition=None):
    return {
        'key': key, 'kind': kind, 'title': title or key,
        'who': {'mode': 'role', 'role': role_key, 'scope': scope},
        'min_amount': min_amount, 'condition': condition,
    }


def people_step(key, user_ids, kind='approve', all_required=True, title=None,
                min_amount=0, condition=None):
    return {
        'key': key, 'kind': kind, 'title': title or key,
        'who': {'mode': 'people', 'user_ids': list(user_ids),
                'all': all_required},
        'min_amount': min_amount, 'condition': condition,
    }


def team_step(key, user_ids, title=None, label='the desk'):
    return {
        'key': key, 'kind': 'any', 'title': title or key,
        'who': {'mode': 'team', 'user_ids': list(user_ids), 'label': label},
        'min_amount': 0, 'condition': None,
    }


def notify_step(key, title=None):
    return {'key': key, 'kind': 'notify', 'title': title or key,
            'who': {'mode': 'preparer'}, 'min_amount': 0, 'condition': None}


def fast_step(key='fast', title='No approval needed'):
    return {'key': key, 'kind': 'fast', 'title': title,
            'who': {'mode': 'people', 'user_ids': []}, 'min_amount': 0,
            'condition': None}


def build(steps, tiers=None, safeguards=None):
    doc = {
        'schema_version': 1,
        'steps': steps,
        'tiers': tiers or {'enabled': False, 'fact': None},
        'safeguards': {
            'independent': True,
            'self_exception': {'enabled': False},
            'repeated': 'different',
            'evidence': [],
            'due': {'kind': 'none', 'days': 1, 'day': 15, 'calendar_id': None},
            'late': {'remind_days': 1, 'escalate_days': 2, 'reassign': False},
        },
    }
    if safeguards:
        doc['safeguards'].update(safeguards)
    return doc


class ApprovalCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['biz.approval.engine']
        cls.Request = cls.env['biz.approval.request']
        cls.Generic = cls.env['biz.approval.generic.request']
        cls.process = cls.env.ref('biz_approval_workflow.process_generic')
        cls.role_reviewer = cls.env.ref('biz_approval_workflow.role_reviewer')
        cls.role_approver = cls.env.ref('biz_approval_workflow.role_approver')
        cls.company = cls.env['res.company'].create({'name': 'AW Alpha'})
        cls.other_company = cls.env['res.company'].create({'name': 'AW Beta'})
        # A COMPANY THAT HAS NOT BEEN SET UP YET, WHICH IS WHAT THESE CASES
        # ARE ABOUT.
        #
        # These fixtures are older than the product around them. A product
        # INSTALLED BESIDE this engine gives every company a published default
        # route and a first responsibility the moment it is created — that is
        # what `pb_approval_config`'s seed is for, and it is right: nobody
        # should meet a company that cannot approve anything. But every case
        # below builds its own route and then binds it, and "this company
        # already has a route for that" is exactly the tie the engine refuses;
        # while a seeded company-wide responsibility fills in the very gaps
        # the coverage cases exist to find.
        #
        # So the two fixture companies are put back to the state the suite has
        # always assumed. Ending rather than deleting, because that is what a
        # business does with a route it no longer wants, and it is what the
        # engine is built to read.
        for company in (cls.company, cls.other_company):
            cls._clear_seeded(company)
        cls.currency = cls.company.currency_id
        # the test env's own user must be allowed into both, or every company
        # rule below would simply hide the fixtures from the fixture builder
        cls.env.user.write({'company_ids': [(4, cls.company.id),
                                            (4, cls.other_company.id)]})

        cls.preparer = cls._user('aw_preparer', 'Preparer Pat')
        cls.alice = cls._user('aw_alice', 'Alice Reviewer')
        cls.bob = cls._user('aw_bob', 'Bob Approver')
        cls.carol = cls._user('aw_carol', 'Carol Backup')
        cls.dave = cls._user('aw_dave', 'Dave Third')
        cls.outsider = cls._user('aw_outsider', 'Olive Outsider',
                                 company=cls.other_company)

        cls.admin_user = cls._user(
            'aw_admin', 'Amy Admin',
            groups=['base.group_user',
                    'biz_approval_workflow.group_approval_admin'])

    @classmethod
    def _clear_seeded(cls, company):
        """End every route and responsibility a product seeded for a company.

        Not a delete: a binding that is `active = False` is a route that was
        ended, which is a state the engine understands and a business really
        produces. Deleting would also take the trail of it with it.
        """
        cls.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', company.id)]).write({'active': False})
        cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', company.id)]).write({'active': False})

    @classmethod
    def _user(cls, login, name, company=None, groups=('base.group_user',)):
        company = company or cls.company
        group_ids = [cls.env.ref(g).id for g in groups]
        return cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': name, 'login': login, 'email': '%s@example.com' % login,
                'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, group_ids)],
            })

    # ------------------------------------------------------------- fixtures
    def hold(self, role, user, scope_key='', backup=None, company=None,
             pool=None):
        return self.env['biz.approval.responsibility'].create({
            'company_id': (company or self.company).id,
            'role_id': role.id,
            'scope_key': scope_key,
            'scope_label': scope_key or 'the whole company',
            'user_id': user.id if user else False,
            'backup_user_id': backup.id if backup else False,
            'pool_user_ids': [(6, 0, pool.ids)] if pool else False,
        })

    def workflow(self, definition, name='Route', company=None, publish=True,
                 owner=None):
        company = company or self.company
        flow = self.env['biz.approval.workflow'].create({
            'name': name, 'company_id': company.id,
            'process_id': self.process.id,
            'owner_user_id': (owner or self.admin_user).id,
        })
        version = self.env['biz.approval.workflow.version'].create({
            'workflow_id': flow.id, 'revision': 1, 'status': 'draft',
            'definition': definition,
        })
        if publish:
            self.publish(version)
        return flow, version

    def publish(self, version, **kwargs):
        checks = self.engine.validate_for_publish(version.id)
        codes = [w['code'] for w in checks['warnings']]
        return self.engine.publish(
            version.id, version.draft_revision, None,
            kwargs.get('reason', 'test'), codes)

    def bind(self, flow, scope_key='', kind_key='any', mode='follow',
             company=None, pinned=None):
        return self.env['biz.approval.binding'].create({
            'company_id': (company or self.company).id,
            'process_id': self.process.id,
            'scope_key': scope_key,
            'scope_label': scope_key or 'the whole company',
            'kind_key': kind_key,
            'workflow_id': flow.id,
            'mode': mode,
            'pinned_version_id': pinned.id if pinned else False,
        })

    def ask(self, user=None, area=None, amount=0.0, urgent=False,
            kind='any', name='A sign-off please', company=None):
        user = user or self.preparer
        return self.Generic.with_user(user).with_company(
            company or self.company).create({
                'name': name,
                'company_id': (company or self.company).id,
                'requester_user_id': user.id,
                'amount': amount,
                'currency_id': self.currency.id,
                'area_key': area or False,
                'area_label': area or False,
                'kind_key': kind,
                'urgent': urgent,
            })

    def submit(self, record, user=None, key=None):
        user = user or self.preparer
        return self.engine.with_user(user).submit(
            record.with_user(user), idempotency_key=key)

    def decide(self, request, user, step_key, action='approve', **kwargs):
        return self.engine.with_user(user).decide(
            request.id, step_key, action, **kwargs)

    def reload(self, request_id):
        return self.Request.browse(request_id)
