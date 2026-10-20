# -*- coding: utf-8 -*-
"""pb_expenses_hub (NAV P2) — OPERATE › Expenses: Trips and Claims.

Trips left Workforce; the claims list had no place on the menu at all. What
can go wrong: Workforce still offering Trips, two entries lighting for the
Trips board, a Claims tab offered to people the list would refuse, or the
embedded list re-implementing a screen instead of mounting it.
"""
import ast
import os
import re
from xml.etree import ElementTree

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _js(name):
    return _read(os.path.join(HERE, 'static', 'src', 'js', name))


@tagged('post_install', '-at_install')
class TestExpensesHub(TransactionCase):

    def test_the_entry_sits_after_workforce_in_operate(self):
        item = self.env.ref('pb_expenses_hub.item_expenses')
        self.assertTrue(item.active)
        self.assertEqual(item.section_id, self.env.ref('pb_sidebar.sec_payrun'))
        self.assertEqual(item.sequence, 35)
        self.assertEqual(item.icon, 'wallet')
        self.assertEqual(item.action_tag, 'pb_expenses_hub')
        wf = self.env.ref('pb_mission.item_workforce', raise_if_not_found=False)
        if wf:
            self.assertGreater(item.sequence, wf.sequence)
            self.assertNotIn('pb_trips', (wf.match_action_tags or '').split(','),
                             'Workforce must not light for the Trips board')
        groups = item.groups_id
        self.assertIn(self.env.ref('hr.group_hr_user'), groups)
        self.assertIn(self.env.ref('hr_expense.group_hr_expense_team_approver'),
                      groups)

    def test_the_trips_board_lights_exactly_one_live_entry(self):
        live = self.env['pb.sidebar.item'].search([])
        claimers = live.filtered(lambda i: 'pb_trips' in [
            t.strip() for t in (i.match_action_tags or '').split(',')])
        self.assertEqual(claimers, self.env.ref('pb_expenses_hub.item_expenses'))

    def test_the_hub_action_exists(self):
        act = self.env.ref('pb_expenses_hub.action_pb_expenses_hub')
        self.assertEqual(act.tag, 'pb_expenses_hub')

    def test_the_two_tabs_and_their_gates(self):
        src = _js('expenses_hub.js')
        self.assertRegex(src, re.compile(
            r'key: "trips".*?Component: PbTrips, groups: \[\]', re.S))
        self.assertRegex(src, re.compile(
            r'key: "claims".*?Component: PbClaimsLens, groups: CLAIMS_GATE', re.S))
        self.assertIn('export const CLAIMS_GATE = '
                      '["hr_expense.group_hr_expense_team_approver"];', src)
        self.assertTrue(self.env.ref('hr_expense.group_hr_expense_team_approver'))
        self.assertIn('feature: "workforce"', src)

    def test_the_claims_tab_mounts_the_real_list(self):
        """W17: mount, never fork — the web client's own View over the
        model's own list and search views."""
        src = _js('claims_lens.js')
        self.assertIn('import { View } from "@web/views/view";', src)
        self.assertIn('resModel: MODEL', src)
        self.assertIn('const MODEL = "pb.expense.claim";', src)
        self.assertIn('type: "list"', src)
        self.assertTrue(self.env['ir.ui.view'].search(
            [('model', '=', 'pb.expense.claim'), ('type', '=', 'list')]))

    def test_workforce_no_longer_ships_a_trips_lens(self):
        js = _read(os.path.join(get_module_path('pb_mission'), 'static', 'src',
                                'js', 'pb_mission.js'))
        block = js[js.index('const LENSES = ['):]
        block = block[:block.index('\n];')]
        self.assertNotIn('key: "trips"', block)
        self.assertIn('pb_expenses_hub.action_pb_expenses_hub', js,
                      'an old Workforce › Trips link is handed on to Expenses')

    def test_every_asset_on_disk_is_in_the_bundle(self):
        manifest = ast.literal_eval(_read(os.path.join(HERE, '__manifest__.py')))
        bundle = set(manifest['assets']['web.assets_backend'])
        on_disk = set()
        for sub in ('js', 'xml', 'scss'):
            d = os.path.join(HERE, 'static', 'src', sub)
            for f in os.listdir(d):
                on_disk.add('pb_expenses_hub/static/src/%s/%s' % (sub, f))
        self.assertEqual(on_disk, bundle)

    def test_templates_parse_and_js_has_no_python_style_concatenation(self):
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'xml')):
            ElementTree.parse(os.path.join(HERE, 'static', 'src', 'xml', f))
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'js')):
            self.assertFalse(_RE_ADJACENT_STRINGS.search(_js(f)), f)

    def test_no_user_visible_string_says_odoo(self):
        for f in os.listdir(os.path.join(HERE, 'static', 'src', 'js')):
            for s in re.findall(r'_t\("([^"]*)"\)', _js(f)):
                self.assertNotIn('odoo', s.lower(), f)
