# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T34 — the Audit console reads the engine's trail, behind the same gate."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import ApprovalCase, build, people_step


@tagged('post_install', '-at_install')
class TestAuditSource(ApprovalCase):

    def test_t34_the_console_shows_approval_events(self):
        if 'pb.audit.console' not in self.env:
            self.skipTest('the Audit console is not installed here')
        flow, _v = self.workflow(
            build([people_step('s1', [self.alice.id])]), name='Audited')
        self.bind(flow)
        request = self.reload(self.submit(self.ask())['id'])
        self.decide(request, self.alice, 's1')

        console = self.env['pb.audit.console']
        self.assertTrue(console._source_available('workflow'))
        rows = console._fetch_workflow({}, 50)
        keys = {row['source'] for row in rows}
        self.assertEqual(keys, {'workflow'})
        titles = [row['title'] for row in rows]
        self.assertTrue(any('approved' in t for t in titles), titles)

        stream = console.get_stream({'source': 'workflow'})
        self.assertTrue(stream['rows'])

        with self.assertRaises(AccessError):
            console.with_user(self.dave).get_stream({})
