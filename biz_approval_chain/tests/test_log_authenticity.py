# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Security-guard test for the ea775321 log-authenticity fix.

Every internal user may CREATE a biz.approval.step.log (the mixin logs as the
clicking user, no sudo). So a crafted call_kw create must NOT be able to forge a
trail row in another user's name or back-date one — create() forces
user_id/stamp server-side.
"""

from datetime import datetime

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLogAuthenticity(TransactionCase):

    def test_forged_log_gets_real_user_and_server_stamp(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        g_user = self.env.ref('base.group_user')
        actor = Users.create({'name': 'Actor', 'login': 'bac_actor',
                              'group_ids': [(6, 0, [g_user.id])]})
        victim = Users.create({'name': 'Victim', 'login': 'bac_victim',
                               'group_ids': [(6, 0, [g_user.id])]})

        # a plain user crafts a log claiming to be someone else, back-dated
        log = self.env['biz.approval.step.log'].with_user(actor).create({
            'res_model': 'res.partner', 'res_id': 1,
            'from_state': 'draft', 'to_state': 'approved',
            'user_id': victim.id,                        # forged actor
            'stamp': datetime(2000, 1, 1, 0, 0, 0),      # back-dated
        })
        # the server overrides both — the trail is truthful
        self.assertEqual(log.user_id, actor,
                         "create() must force user_id to the acting user")
        self.assertGreater(log.stamp.year, 2000,
                           "create() must drop a forged/back-dated stamp")
