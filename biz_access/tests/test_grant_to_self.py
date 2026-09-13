# -*- coding: utf-8 -*-
"""Giving yourself a role is a grant, not a hand-over, and it must go through.

WHAT THIS CAUGHT. The audit trail for the roles board and the record of one
person lending another their access are the SAME TABLE, on purpose — one place
to look for "how did this person come to hold that". But the two columns mean
different things in the two cases: for a hand-over they are the lender and the
borrower, and for a board grant they are who pressed the button and who it was
pressed against. The rule that a hand-over needs two different people was
applied to both, so an administrator giving THEMSELVES a role was refused —
with a sentence about lending, which is not what they had done.

And it failed in the worst possible shape: `grant` writes the permissions and
THEN writes the audit row, so the refusal rolled the whole transaction back. The
screen said "You cannot hand your access to yourself", nothing had changed, and
nothing said which of the two steps had objected.

The first two tests are the fix. The third is the rule the fix must not have
broken on the way past: lending yourself your own access is still meaningless
and is still refused.
"""

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


def _wave_role_changes_through(env):
    """Publish "No approval needed" for role changes, for these cases only.

    PHASE 6 made giving somebody a role something that can be ASKED for: where
    a company publishes a route, the press makes a request and the board says
    who is holding it. These cases are about what the board DOES — the bundle
    arithmetic, the audit row, the refusals — so the company they run in
    publishes the choice every company is allowed to make: nobody checks this
    before it happens, and every one is still recorded as a request.

    The phase's own suite (`test_access_request.py`) is where the asking is
    tested.
    """
    Seed = env.get('biz.approval.seed')
    if Seed is None:
        return False
    try:
        Seed.sudo().set_no_approval_needed(env.company, 'roles')
        return True
    except Exception:       # noqa: BLE001 — the catalogue may not be here
        return False


@tagged('post_install', '-at_install')
class TestGrantToSelf(TransactionCase):

    def setUp(self):
        super().setUp()
        _wave_role_changes_through(self.env)
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.group = self.env['res.groups'].create(
            {'name': 'ZZ Self grant %s' % stamp})
        self.ability = self.env['pb.role.ability'].create({
            'technical_key': 'zz-self-grant-%s' % stamp,
            'name': 'ZZ do the thing %s' % stamp,
            'description': 'A permission made for this test and nothing else.',
            'area': 'system',
            'group_ids': [(6, 0, self.group.ids)],
        })
        self.profile = self.env['pb.role.profile'].create({
            'name': 'ZZ Self grant role %s' % stamp,
            'description': 'A role made for this test and nothing else.',
            'area': 'system',
            'ability_ids': [(6, 0, self.ability.ids)],
        })

    def test_an_administrator_can_give_themselves_a_role(self):
        me = self.env.user
        self.assertNotIn(self.group.id, me.all_group_ids.ids,
                         'the fixture group was already held — bad fixture')
        res = self.env['pb.access'].grant(
            self.profile.id, me.id, reason='Test 1.')
        self.assertTrue(res.get('ok'))
        me.invalidate_recordset(['group_ids'])
        self.assertIn(
            self.group.id, me.all_group_ids.ids,
            'the permission was not written, so the audit row refused the '
            'grant and rolled the whole thing back')

    def test_the_audit_row_says_who_did_it_and_to_whom(self):
        me = self.env.user
        self.env['pb.access'].grant(self.profile.id, me.id, reason='Test 2.')
        row = self.env['pb.access.delegation'].sudo().search(
            [('profile_ids', 'in', self.profile.ids)], limit=1)
        self.assertTrue(row, 'a grant with no audit row is a grant nobody can '
                             'account for afterwards')
        self.assertEqual(row.origin, 'board')
        self.assertEqual(row.delegator_user_id, me)
        self.assertEqual(row.delegate_user_id, me)

    def test_a_real_hand_over_to_yourself_is_still_refused(self):
        with self.assertRaises(ValidationError):
            self.env['pb.access.delegation'].sudo().create({
                'delegator_user_id': self.env.uid,
                'delegate_user_id': self.env.uid,
                'profile_ids': [(6, 0, self.profile.ids)],
                'kind': 'permanent',
                'date_start': fields.Date.context_today(self),
                'origin': 'delegation',
            })

    def test_taking_a_role_off_yourself_works_too(self):
        me = self.env.user
        self.env['pb.access'].grant(self.profile.id, me.id, reason='Test 4.')
        me.invalidate_recordset(['group_ids'])
        res = self.env['pb.access'].remove(
            self.profile.id, me.id, reason='Test 4, back off again.')
        self.assertTrue(res.get('ok'))
        me.invalidate_recordset(['group_ids'])
        self.assertNotIn(self.group.id, me.all_group_ids.ids)
