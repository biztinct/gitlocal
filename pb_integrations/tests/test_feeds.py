# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Integrations Cycle 1 — the feed scope and the board's feed summary.

Kept out of `test_one_door.py` on purpose: that file is about which DOORS
exist, and these are about what the board and the ledger COUNT. Two subjects in
one file is how a gate ends up being read as evidence for a claim it was never
making.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFeeds(TransactionCase):

    def test_a_feed_scope_is_validated_against_the_stores_own_selection(self):
        """`data_type` reaches a DOMAIN and it comes from the browser.

        The `kind` whitelist exists for exactly this reason and this is the
        second value with the same provenance. A junk type must return the
        UNSCOPED table rather than an error or, worse, a domain the ORM tries
        to make sense of.
        """
        P = self.env['pb.integrations']
        every = P.get_ledger('store')
        junk = P.get_ledger('store', None, 'res_users')
        self.assertEqual(junk['total'], every['total'])

        S = self.env['hr.api.data.store']
        present = [dt for dt, in S._read_group([], ['data_type']) if dt]
        if not present:
            self.skipTest("nothing in the data store on this database")
        dt = present[0]
        scoped = P.get_ledger('store', None, dt)
        self.assertLessEqual(scoped['total'], every['total'])
        for r in S.browse([x['id'] for x in scoped['rows']]):
            self.assertEqual(r.data_type, dt)

    def test_the_feed_scope_is_ignored_on_the_tables_that_have_no_data_type(self):
        # Switching to Field mappings with a feed scope still on must show the
        # mappings, not an empty grid — the tab strip has to stay usable.
        P = self.env['pb.integrations']
        self.assertEqual(P.get_ledger('mapping', None, 'employee')['total'],
                         P.get_ledger('mapping')['total'])

    def test_the_board_reports_feeds_beside_the_counts_it_always_had(self):
        board = self.env['pb.integrations'].get_board()
        self.assertIn('feeds', board['kpis'])
        self.assertIn('feeds_stale', board['kpis'])
        for row in board['connectors']:
            self.assertIn('feeds', row)
            self.assertIn('feeds_stale', row)
            self.assertLessEqual(
                row['feeds_stale'], row['feeds'],
                "more feeds are stale than exist on connector %s" % row['id'])
        self.assertEqual(board['kpis']['feeds'],
                         sum(r['feeds'] for r in board['connectors']))
