# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T01–T02 — what a workflow document may and may not say."""

from odoo.tests import tagged

from ..models import definition as D
from .common import (ApprovalCase, build, fast_step, notify_step, people_step,
                     role_step, team_step)


@tagged('post_install', '-at_install')
class TestDefinition(ApprovalCase):

    def _caps(self):
        return self.Generic._approval_capabilities()

    def _codes(self, result, key='errors'):
        return {e['code'] for e in result[key]}

    # ------------------------------------------------------------------ T01
    def test_t01_structural_errors(self):
        caps = self._caps()

        good = build([role_step('s1', 'reviewer', kind='review'),
                      role_step('s2', 'approver')])
        result = D.validate(good, caps, env=self.env)
        self.assertFalse(result['errors'], result['errors'])

        unknown_role = build([role_step('s1', 'nobody_holds_this')])
        self.assertIn('unknown_role',
                      self._codes(D.validate(unknown_role, caps, env=self.env)))

        unknown_fact = build([role_step(
            's1', 'approver',
            condition={'fact': 'phase_of_the_moon', 'op': 'eq',
                       'value': True})])
        self.assertIn('unknown_fact',
                      self._codes(D.validate(unknown_fact, caps,
                                             env=self.env)))

        lonely_joint = build([people_step('s1', [self.alice.id],
                                          kind='joint')])
        self.assertIn('joint_needs_two',
                      self._codes(D.validate(lonely_joint, caps,
                                             env=self.env)))

        crowded_fast = build([fast_step(), role_step('s2', 'approver')])
        self.assertIn('fast_not_alone',
                      self._codes(D.validate(crowded_fast, caps,
                                             env=self.env)))

        bad_operator = build([role_step(
            's1', 'approver',
            condition={'fact': 'urgent', 'op': 'gt', 'value': 3})])
        self.assertIn('operator_type_mismatch',
                      self._codes(D.validate(bad_operator, caps,
                                             env=self.env)))

        tier_without_fact = build([role_step('s1', 'approver',
                                             min_amount=1000)])
        self.assertIn('tier_without_fact',
                      self._codes(D.validate(tier_without_fact, caps,
                                             env=self.env)))

        preparer_decides = build([{'key': 's1', 'kind': 'approve',
                                   'title': 'x',
                                   'who': {'mode': 'preparer'},
                                   'min_amount': 0, 'condition': None}])
        self.assertIn('preparer_decides',
                      self._codes(D.validate(preparer_decides, caps,
                                             env=self.env)))

        inactive = self._user('aw_ghost', 'Ghost')
        inactive.active = False
        named_ghost = build([people_step('s1', [inactive.id])])
        self.assertIn('inactive_person',
                      self._codes(D.validate(named_ghost, caps, env=self.env)))

        tiered = build(
            [role_step('s1', 'approver', min_amount=500)],
            tiers={'enabled': True, 'fact': 'amount'})
        self.assertFalse(D.validate(tiered, caps, env=self.env)['errors'])

    # ------------------------------------------------------------------ T02
    def test_t02_warning_codes(self):
        caps = self._caps()

        fast = build([fast_step()])
        self.assertIn('fast_lane',
                      self._codes(D.validate(fast, caps, env=self.env),
                                  'warnings'))

        single = build([role_step('s1', 'approver')])
        self.assertIn('single_person',
                      self._codes(D.validate(single, caps, env=self.env),
                                  'warnings'))

        two = build([role_step('s1', 'reviewer', kind='review'),
                     role_step('s2', 'approver')])
        self.assertNotIn('single_person',
                         self._codes(D.validate(two, caps, env=self.env),
                                     'warnings'))

        loose = build([role_step('s1', 'reviewer', kind='review'),
                       role_step('s2', 'approver')],
                      safeguards={'independent': False})
        self.assertIn('independence_off',
                      self._codes(D.validate(loose, caps, env=self.env),
                                  'warnings'))

        notify_only = build([notify_step('n1')])
        codes = self._codes(D.validate(notify_only, caps, env=self.env),
                            'warnings')
        self.assertIn('notify_only_route', codes)
        self.assertIn('fast_lane', codes)

        # money_single_person comes from the process, so it is the engine's
        # answer, not the document's
        self.process.sudo().money = True
        flow = self.env['biz.approval.workflow'].create({
            'name': 'Money route', 'company_id': self.company.id,
            'process_id': self.process.id})
        version = self.env['biz.approval.workflow.version'].create({
            'workflow_id': flow.id, 'revision': 1, 'definition': single})
        checks = self.engine.validate_for_publish(version.id)
        self.assertIn('money_single_person',
                      {w['code'] for w in checks['warnings']})
        self.process.sudo().money = False

    def test_t02b_any_step_needs_a_choice(self):
        caps = self._caps()
        alone = build([{'key': 's1', 'kind': 'any', 'title': 'x',
                        'who': {'mode': 'role', 'role': 'approver',
                                'scope': 'company'},
                        'min_amount': 0, 'condition': None}])
        self.assertIn('any_needs_pool',
                      self._codes(D.validate(alone, caps, env=self.env)))
        desk = build([team_step('s1', [self.alice.id, self.bob.id])])
        self.assertFalse(D.validate(desk, caps, env=self.env)['errors'])

    def test_t02c_fingerprint_is_order_stable(self):
        one = build([role_step('s1', 'approver')])
        two = build([role_step('s1', 'approver')])
        two['safeguards'] = dict(reversed(list(two['safeguards'].items())))
        self.assertEqual(D.fingerprint(one), D.fingerprint(two))
