# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""What is left of Team Approvals, and what must stay left of it.

The cockpit and its `pb.team` model are retired (see the manifest). Three
things still have to be true, and they are exactly the three that would
silently rot: the saved link still exists, it still points at a registered
client action, and the model really is gone — because a half-removed model
whose Python is still imported is the shape of a screen nobody notices is
dead.
"""

import os

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPbTeamRetired(TransactionCase):

    def test_01_the_saved_link_still_opens_something(self):
        """A link somebody bookmarked must not land on nothing."""
        action = self.env.ref('pb_team.action_pb_team',
                              raise_if_not_found=False)
        self.assertTrue(action, "the Team Approvals action was deleted; a "
                                "saved link now goes nowhere")
        self.assertEqual(action.type, 'ir.actions.client')
        self.assertEqual(action.tag, 'pb_team')

    def test_02_the_model_is_really_gone(self):
        """`pb.team` must not be in the registry, and its file must not exist."""
        self.assertNotIn('pb.team', self.env,
                         "pb.team is still in the registry — a second "
                         "approvals queue is exactly what phase 6 removed")
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertFalse(
            os.path.exists(os.path.join(here, 'models', 'pb_team.py')),
            "models/pb_team.py is back")

    def test_03_the_rail_entry_stays_retired(self):
        """The sidebar row was retired long before this; it stays retired."""
        item = self.env.ref('pb_team.item_my_team', raise_if_not_found=False)
        if not item:
            self.skipTest('the sidebar row is not installed here')
        self.assertFalse(item.active,
                         "the retired Team Approvals rail entry came back")

    def test_04_the_redirect_names_the_lens_that_replaced_it(self):
        """The door must point at the Workforce Approvals lens, by name."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, 'static', 'src', 'js', 'pb_team.js')
        source = open(path, encoding='utf-8').read()
        self.assertIn('pb_mission.action_pb_workforce', source)
        self.assertIn('pb_shell_lens', source)
        self.assertIn('approvals', source)
        self.assertNotIn('pb.team', source,
                         "the redirect still talks to the retired model")
