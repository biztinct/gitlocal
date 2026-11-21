# -*- coding: utf-8 -*-
"""NAV P2 — the Lifecycle entry is off the menu and its hub is a redirector.

Read from the database where the answer lives there (the entry), and from
the source where only the source can say it (the redirector's table: the
web client's action service is what runs it).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


def _hub_js():
    path = os.path.join(get_module_path('pb_lifecycle'), 'static', 'src', 'js',
                        'lifecycle_hub.js')
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestLifecycleRetired(TransactionCase):

    def test_the_entry_is_off_the_menu_and_kept(self):
        item = self.env.ref('pb_lifecycle.item_lifecycle')
        self.assertFalse(item.active, 'Lifecycle must be off the left menu')
        self.assertEqual(item.sequence, 982, 'a retirement moves to the 900 band')
        served = {i['id'] for s in self.env['pb.sidebar.item'].get_sidebar_data()
                  for i in s['items']}
        self.assertNotIn(item.id, served)
        self.assertFalse(item.match_models, 'a retired entry claims no model')

    def test_the_ask_hr_entry_is_off_the_menu_too(self):
        item = self.env.ref('pb_ask_hr.item_ask_hr', raise_if_not_found=False)
        if not item:
            self.skipTest('pb_ask_hr is not installed')
        self.assertFalse(item.active)
        self.assertEqual(item.sequence, 983)

    def test_the_hub_action_still_exists_for_old_links(self):
        act = self.env.ref('pb_lifecycle.action_pb_lifecycle_hub')
        self.assertEqual(act.tag, 'pb_lifecycle_hub')
        self.assertTrue(self.env.ref('pb_lifecycle.action_pb_journeys'))

    def test_the_redirector_sends_every_old_tab_to_its_new_home(self):
        src = _hub_js()
        self.assertIn('registry.category("actions").add("pb_lifecycle_hub", '
                      'lifecycleRedirect);', src)
        table = src.split('export const LIFECYCLE_REDIRECTS = {', 1)[1]
        table = table.split('\n};', 1)[0]
        rows = dict((k, (x, l)) for k, x, l in re.findall(
            r'(\w+): \{ xmlid: (?:"([\w.]+)"|JOURNEYS_XMLID), lens: "(\w*)" \}',
            table))
        expected = {
            'hiring': ('pb_hiring.action_pb_hiring_hub', 'overview'),
            'newjoiners': ('pb_people_hub.action_pb_people_hub', 'newjoiners'),
            'probation': ('pb_people_hub.action_pb_people_hub', 'probation'),
            'exits': ('pb_people_hub.action_pb_people_hub', 'exits'),
            'contracts': ('pb_people_hub.action_pb_people_hub', 'contracts'),
            'pip': ('pb_talent_hub.action_pb_talent_hub', 'pip'),
            'journeys': ('', ''),
        }
        self.assertEqual(rows, expected)
        # Every target that is installed here resolves.
        for key, (xmlid, _lens) in expected.items():
            if not xmlid:
                continue
            module = xmlid.split('.')[0]
            if self.env['ir.module.module'].sudo().search_count(
                    [('name', '=', module), ('state', '=', 'installed')]):
                self.assertTrue(self.env.ref(xmlid, raise_if_not_found=False),
                                '%s -> %s does not resolve' % (key, xmlid))
        # The resume-bank arrival and the fallback.
        self.assertIn('ctx.pb_focus === "bank"', src)
        self.assertIn('return { xmlid: JOURNEYS_XMLID, lens: "" };', src)

    def test_no_board_registers_into_the_retired_hub(self):
        installed = self.env['ir.module.module'].sudo().search(
            [('state', '=', 'installed'), ('name', 'like', 'pb_%')]).mapped('name')
        offenders = []
        for module in installed:
            path = get_module_path(module)
            if not path:
                continue
            js_dir = os.path.join(path, 'static', 'src', 'js')
            if not os.path.isdir(js_dir):
                continue
            for f in os.listdir(js_dir):
                if not f.endswith('.js'):
                    continue
                with open(os.path.join(js_dir, f), encoding='utf-8') as fh:
                    if 'registry.category(LIFECYCLE_LENSES).add(' in fh.read():
                        offenders.append('%s/%s' % (module, f))
        self.assertFalse(offenders, 'still a Lifecycle tab: %s' % offenders)
