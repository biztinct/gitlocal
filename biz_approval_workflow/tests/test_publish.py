# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T03, T04, T30, T33 — publishing, and what a published version promises."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ApprovalCase, build, people_step, role_step


@tagged('post_install', '-at_install')
class TestPublish(ApprovalCase):

    def _draft(self, definition, name='Route'):
        flow = self.env['biz.approval.workflow'].create({
            'name': name, 'company_id': self.company.id,
            'process_id': self.process.id,
            'owner_user_id': self.admin_user.id,
        })
        version = self.env['biz.approval.workflow.version'].create({
            'workflow_id': flow.id, 'revision': 1, 'status': 'draft',
            'definition': definition,
        })
        return flow, version

    # ------------------------------------------------------------------ T03
    def test_t03_every_warning_must_be_confirmed(self):
        self.hold(self.role_approver, self.bob)
        _flow, version = self._draft(build([role_step('s1', 'approver')]))
        checks = self.engine.validate_for_publish(version.id)
        self.assertFalse(checks['errors'])
        codes = [w['code'] for w in checks['warnings']]
        self.assertIn('single_person', codes)

        with self.assertRaises(UserError) as caught:
            self.engine.publish(version.id, version.draft_revision, None,
                                'no confirmations', [])
        self.assertIn('confirm', str(caught.exception).lower())
        self.assertEqual(version.status, 'draft')

        self.engine.publish(version.id, version.draft_revision, None,
                            'confirmed', codes)
        self.env.invalidate_all()
        self.assertEqual(version.status, 'published')
        stored = {c['code'] for c in version.confirmations}
        self.assertEqual(stored, set(codes))
        self.assertTrue(version.fingerprint)

    # ------------------------------------------------------------------ T04
    def test_t04_a_stale_draft_cannot_be_published(self):
        self.hold(self.role_approver, self.bob)
        _flow, version = self._draft(build([role_step('s1', 'approver')]))
        codes = [w['code']
                 for w in self.engine.validate_for_publish(version.id)['warnings']]
        stale = version.draft_revision
        version.write({'definition': build([role_step('s1', 'approver'),
                                            role_step('s2', 'reviewer')])})
        with self.assertRaises(UserError):
            self.engine.publish(version.id, stale, None, 'stale', codes)
        self.env.invalidate_all()
        self.assertEqual(version.status, 'draft')

    # ------------------------------------------------------------------ T30
    def test_t30_published_is_frozen_and_in_flight_keeps_its_version(self):
        self.hold(self.role_approver, self.bob)
        flow, version = self.workflow(
            build([people_step('s1', [self.bob.id])]), name='Two versions')
        self.bind(flow, scope_key='')

        with self.assertRaises(UserError):
            version.write({'definition': build([])})

        record = self.ask()
        request = self.reload(self.submit(record)['id'])
        self.assertEqual(request.version_id, version)

        second = flow.action_new_draft()
        self.assertEqual(second.revision, 2)
        self.assertEqual(second.definition['steps'][0]['key'], 's1')
        second.write({'definition': build([people_step('s2', [self.carol.id])])})
        self.publish(second)
        self.env.invalidate_all()
        self.env.invalidate_all()
        self.assertEqual(version.status, 'superseded')
        self.assertEqual(flow.published_version_id, second)

        self.env.invalidate_all()
        self.assertEqual(request.version_id, version,
                         'a request under way keeps the version it was given')
        self.assertEqual(request.step_ids.filtered('included')[0].key, 's1')

    # ------------------------------------------------------------------ T33
    def test_t33_coverage_finds_the_gap_a_good_example_hides(self):
        # a holder for retail only; operations has nobody
        self.hold(self.role_approver, self.bob, scope_key='area:retail')
        self.ask(area='retail')
        self.ask(area='operations')
        _flow, version = self._draft(
            build([role_step('s1', 'approver', scope='area')]))

        scan = self.engine.coverage_scan(version.id)
        self.assertTrue(scan['ran'])
        gaps = {row['scope_key'] for row in scan['rows'] if row['issues']}
        self.assertIn('area:operations', gaps)
        self.assertNotIn('area:retail', gaps)

        codes = {w['code']
                 for w in self.engine.validate_for_publish(version.id)['warnings']}
        self.assertIn('coverage_gap:area:operations', codes)

        # and the example for retail is perfectly happy at the same time
        preview = self.engine.preview(version.id, {
            'company_id': self.company.id,
            'scope_keys': ['area:retail', ''],
            'scope_label': 'retail',
            'facts': {},
            'submitter_uid': self.preparer.id,
            'maker_uids': [self.preparer.id],
        })
        self.assertEqual(preview['level'], 'ready', preview['issues'])
