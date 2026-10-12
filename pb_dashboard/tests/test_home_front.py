# -*- coding: utf-8 -*-
"""HOME P2 — the new Home front end, tests 1–7 of the handover (source tests)
plus the one server touch P2 made (`months[].foreign_runs`, H21).

Source tests read the FILES, so they run on any database. Every absence check
below spells its token by concatenation or builds it from a range, so a comment
naming the token cannot defeat its own grep (the ledger's six-times lesson).
"""
import ast
import os
import re
from unittest.mock import patch

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_dashboard.models import home_data as home_module

JS = 'static/src/js/pb_dashboard.js'
TPL = 'static/src/xml/pb_dashboard.xml'
SCSS = 'static/src/scss/pb_dashboard.scss'

#: The five Learn anchors (H9) — each exactly once in the template.
ANCHORS = ('dash-hero', 'dash-runpayroll', 'dash-period', 'dash-kpis',
           'dash-formula')

#: The activation checklist block as it stood before P2 (pb_dashboard.xml at
#: 292231339, lines 40–65). P2 moved it, it may not change a byte.
ACTIVATION_BLOCK = """            <div class="pbd-act" t-if="activation">
                <div class="pbd-act-head">
                    <span class="pbd-act-hic"><t t-out="icon('flag',18)"/></span>
                    <div class="pbd-act-hx">
                        <div class="pbd-act-t">Get your first payroll out</div>
                        <div class="pbd-act-s">Each step opens the screen it talks about. Come back here any time.</div>
                    </div>
                    <div class="pbd-act-count"><t t-esc="activation.doneCount"/> of <t t-esc="activation.items.length"/> done</div>
                </div>
                <ol class="pbd-acts">
                    <li t-foreach="activation.items" t-as="it" t-key="it.key"
                        class="pbd-act-i"
                        t-att-class="{ 'is-done': it.done, 'is-next': it_index === activation.next }">
                        <span class="pbd-act-mark">
                            <t t-if="it.done"><t t-out="icon('check',14)"/></t>
                            <t t-else=""><t t-out="icon(it.icon,15)"/></t>
                        </span>
                        <div class="pbd-act-x">
                            <div class="pbd-act-n" t-esc="it.title"/>
                            <div class="pbd-act-d" t-esc="it.desc"/>
                        </div>
                        <button class="pbd-btn" t-att-class="{ ghost: it_index !== activation.next }"
                                t-on-click="() => this.runStep(it)"><t t-esc="it.cta"/></button>
                    </li>
                </ol>
            </div>
"""


def _read(module, rel):
    with open(os.path.join(get_module_path(module), rel), encoding='utf-8') as fh:
        return fh.read()


def _table_keys(js, name):
    """Top-level keys of `const NAME = { ... };` in the script."""
    table = re.search(r'const %s = \{(.*?)\n\};' % name, js, re.S)
    if not table:
        return None
    return set(re.findall(r'^    ([a-z_]+): \{', table.group(1), re.M))


def _camel(name):
    return re.sub(r'-([a-z])', lambda m: m.group(1).upper(), name)


@tagged('post_install', '-at_install')
class TestHomeFrontSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js = _read('pb_dashboard', JS)
        cls.tpl = _read('pb_dashboard', TPL)
        cls.scss = _read('pb_dashboard', SCSS)
        cls.py = _read('pb_dashboard', 'models/home_data.py')
        cls.icons = _read('pb_import_kit', 'static/src/js/import_icons.js')

    # ------------------------------------------------------------ test 1
    def test_01_the_five_learn_anchors_are_there_once_each(self):
        for anchor in ANCHORS:
            self.assertEqual(self.tpl.count('data-coach="%s"' % anchor), 1,
                             'anchor %s is not in the template exactly once'
                             % anchor)

    # ------------------------------------------------------------ test 2
    def test_02_every_icon_name_is_in_the_kit_registry(self):
        """`ic()` draws a tick for a name it does not know, with no error
        (H7) — so every name is checked here instead."""
        block = re.search(r'export const IC = \{(.*?)\n\};', self.icons, re.S)
        self.assertTrue(block, 'the kit registry moved')
        known = set(re.findall(r'^\s+([A-Za-z0-9]+):', block.group(1), re.M))
        for name in ('fileCheck', 'layoutGrid', 'moveRight', 'chartColumn',
                     'triangleAlert', 'flame'):
            self.assertIn(name, known, 'the kit lacks %s' % name)
        used = set()
        for src in (self.tpl, self.js):
            used |= set(re.findall(r"\bic\(\s*['\"]([\w-]+)['\"]", src))
            used |= {_camel(n) for n in re.findall(
                r"\bicon\(\s*['\"]([\w-]+)['\"]", src)}
        # names carried by the word tables and getters: `icon: "x"`
        used |= {_camel(n) for n in re.findall(r'\bicon: "([\w-]+)"', self.js)}
        self.assertTrue(used, 'no icon names found — the scan is broken')
        missing = sorted(n for n in used if n not in known)
        self.assertFalse(missing, 'icons not in the kit: %s' % missing)

    # ------------------------------------------------------------ test 3
    def test_03_every_server_key_has_words_and_the_reverse(self):
        needs = _table_keys(self.js, 'NEEDS')
        self.assertEqual(needs, set(home_module.NEEDS_ORDER),
                         'NEEDS and the server disagree: %s'
                         % sorted((needs or set()) ^ set(home_module.NEEDS_ORDER)))
        steps = _table_keys(self.js, 'STEPS')
        self.assertEqual(steps, set(home_module.STEP_KEYS),
                         'STEPS and the server disagree')
        kinds = set(re.findall(r"'kind': '([a-z_]+)'", self.py))
        self.assertEqual(kinds, {'cutoff', 'payday', 'contracts_end',
                                 'holiday', 'interviews'})
        upcoming = _table_keys(self.js, 'UPCOMING')
        self.assertEqual(upcoming, kinds, 'UPCOMING and the server disagree')

    # ------------------------------------------------------------ test 4
    def test_04_no_brand_no_emoji_no_old_indigo_no_fades(self):
        emoji = re.compile('[%s-%s%s-%s]' % (chr(0x1F300), chr(0x1FAFF),
                                            chr(0x2600), chr(0x27BF)))
        for name, src in (('template', self.tpl), ('script', self.js),
                          ('styles', self.scss)):
            self.assertNotIn('Od' + 'oo', src, '%s names the platform' % name)
            self.assertFalse(emoji.search(src), '%s carries an emoji' % name)
            self.assertNotIn('#4F46' + 'E5', src.upper(),
                             '%s uses the retired indigo' % name)
            self.assertNotIn('grad' + 'ient', src.lower(),
                             '%s carries a colour fade' % name)
        self.assertIn('#5A4BB0', self.scss, 'the locked indigo is not the brand')

    # ------------------------------------------------------------ test 5
    def test_05_one_call_and_the_checklist_unchanged(self):
        self.assertIn('"get_home_data"', self.js)
        self.assertNotIn('get_dash' + 'board_data', self.js,
                         'the script still calls the old payload')
        self.assertIn(ACTIVATION_BLOCK, self.tpl,
                      'the activation checklist markup changed')

    # ------------------------------------------------------------ test 6
    def test_06_the_money_formatter_rules(self):
        body = re.search(r'function compact\(v\) \{(.*?)\n\}', self.js, re.S)
        self.assertTrue(body, 'the compact formatter moved')
        for threshold in ('1e9', '1e6', '1e3'):
            self.assertIn('a >= %s' % threshold, body.group(1),
                          'the %s threshold is gone' % threshold)
        # the unit always follows the number after ONE space
        self.assertIn('p.n + " " + p.u', self.js)
        self.assertIn('[c.unit, sym].filter(Boolean).join(" ")', self.js)
        full = re.search(r'fullMoney\(v\) \{(.*?)\n    \}', self.js, re.S)
        self.assertTrue(full and 'toLocaleString' in full.group(1),
                        'full figures do not use the reader\'s locale')

    # ------------------------------------------------------------ test 7
    def test_07_manifests_fonts_and_versions(self):
        manifest = ast.literal_eval(_read('pb_dashboard', '__manifest__.py'))
        self.assertIn('pb_import_kit', manifest['depends'])
        self.assertEqual(manifest['version'], '19.0.2.1.0')
        kit = ast.literal_eval(_read('pb_import_kit', '__manifest__.py'))
        major = tuple(int(x) for x in kit['version'].split('.')[2:5])
        self.assertGreaterEqual(major, (1, 21, 0), 'the kit was not bumped')
        bundle = kit['assets']['web.assets_backend']
        self.assertEqual(bundle[0], 'pb_import_kit/static/src/scss/fonts.scss',
                         'the font face does not load first')
        fonts = os.path.join(get_module_path('pb_import_kit'), 'static', 'fonts')
        self.assertTrue(any(f.endswith('.woff2') for f in os.listdir(fonts)),
                        'no WOFF2 under static/fonts')
        face = _read('pb_import_kit', 'static/src/scss/fonts.scss')
        for decl in ('font-family: "Inter"', 'font-weight: 100 900',
                     'font-display: swap'):
            self.assertIn(decl, face)


@tagged('post_install', '-at_install')
class TestHomeForeignRuns(TransactionCase):
    """H21: a run in another currency counts in `runs`, never in the money,
    and the month says how many were left out."""

    def test_foreign_runs_are_counted_and_left_out_of_the_money(self):
        Run = self.env['hr.payslip.run']
        if 'pb_total_net' not in Run._fields:
            self.skipTest('pb_payruns (the stored run totals) is not installed')
        D = self.env['pb.dashboard']
        data = D.get_home_data()
        for month in data['months']:
            self.assertIsInstance(month['foreign_runs'], int)
        first = data['period']['date_start']
        run = Run.create({'name': 'Home foreign run', 'date_start': first,
                          'date_end': data['period']['date_end']})
        real = home_module.PbDashboardHome._home_money

        def money(self_, runs):
            out = real(self_, runs)
            if run.id in out:
                out[run.id] = dict(out[run.id], money=False, net=999.0)
            else:
                out[run.id] = {'money': False, 'net': 999.0, 'gross': 999.0,
                               'ded': 0.0, 'er': 0.0, 'people': 0,
                               'balance_ok': True, 'unsourced': 0}
            return out

        before = data['months'][-1]
        with patch.object(home_module.PbDashboardHome, '_home_money', money):
            after = D.get_home_data()['months'][-1]
        self.assertEqual(after['runs'], before['runs'] + 1)
        self.assertEqual(after['foreign_runs'], before['foreign_runs'] + 1)
        self.assertEqual(after['net'], before['net'],
                         'a run in another currency was added to the money')
