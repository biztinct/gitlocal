# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""MEHOME M1 — source gates (handover tests 1, 10-source, 11, 12; M2 adds its
three card templates to every gate here, M2 tests 7 and 8).

These read files, not the database. Test 1 walks every addons directory on the
server (not just this module's parent): on the bench only two modules are
staged next to this one, and the tiles it must cover live in the others.
"""
import glob
import os
import re

import odoo.addons
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import xml_translate

from odoo.addons.pb_me_portal.models import pb_me_home

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TEMPLATES = os.path.join(_HERE, 'views', 'portal_templates.xml')
_SCSS = os.path.join(_HERE, 'static', 'src', 'scss', 'me_portal.scss')
_JS = os.path.join(_HERE, 'static', 'src', 'interactions', 'me_home.js')
_MODEL = os.path.join(_HERE, 'models', 'pb_me_home.py')
_PO = os.path.join(_HERE, 'i18n', 'vi_VN.po')

#: The templates this program added (their xml ids in this module).
NEW_TEMPLATES = ('portal_my_home_ess', 'portal_docs_entry_pbme', 'pbme_top',
                 'pbme_need_sentence', 'pbme_bento', 'pbme_need_row',
                 # M2: the three hero cards
                 'pbme_card_pay', 'pbme_card_leave', 'pbme_card_week',
                 # TIERS T3a: My requests
                 'portal_my_requests')

#: Every model the home reads softly (M-R3) — none is a dependency.
OPTIONAL_MODELS = ('pb.ess.workforce', 'pb.payroll.calendar', 'pb.my.training',
                   'pb.my.goals', 'pb.pay.apply')

#: The stock tiles the registry names too.
STOCK_TILE_URLS = ('/my/addresses', '/my/security', '/my/invoices',
                   '/my/projects', '/my/tasks', '/my/timesheets')

_TILE_URL = re.compile(r"""t-set="url" t-value="'(/my/[^'"]*)'\"""")
_OURS = ('pb_', 'om_', 'biz_')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _strip_xml_comments(src):
    return re.sub(r'<!--.*?-->', '', src, flags=re.S)


def _new_template_source():
    """Only the MEHOME templates (and not the older pages in the file)."""
    src = _strip_xml_comments(_read(_TEMPLATES))
    blocks = []
    for xmlid in NEW_TEMPLATES:
        m = re.search(r'<template id="%s".*?</template>' % xmlid, src, re.S)
        assert m, xmlid
        blocks.append(m.group(0))
    return '\n'.join(blocks)


def _mehome_scss():
    src = _read(_SCSS)
    return src[src.index('MEHOME'):]


def _addon_dirs():
    """module name → directory, first addons path wins (as the server loads)."""
    seen = {}
    for root in odoo.addons.__path__:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name)
            if name not in seen and os.path.isfile(os.path.join(path, '__manifest__.py')):
                seen[name] = path
    return seen


@tagged('post_install', '-at_install')
class TestMeHomeSource(TransactionCase):

    # ------------------------------------------------------------ test 1
    def test_01_registry_covers_every_tile(self):
        found = {}
        for name, path in _addon_dirs().items():
            if not name.startswith(_OURS):
                continue
            for xml in glob.glob(os.path.join(path, 'views', '*portal*.xml')):
                for url in _TILE_URL.findall(_strip_xml_comments(_read(xml))):
                    found.setdefault(url.split('?', 1)[0], name)
        self.assertGreaterEqual(len(found), 3, "the walk must find the tiles")
        missing = {u: m for u, m in found.items() if u not in pb_me_home.TILES}
        self.assertEqual(missing, {}, "tiles with no registry entry (they would "
                                      "land in More with a plain icon)")
        for url in STOCK_TILE_URLS:
            self.assertIn(url, pb_me_home.TILES)

    # ------------------------------------------------------- test 10 (CSS)
    def test_10_employee_only_rule_still_hides_finance_tiles(self):
        scss = _read(_SCSS)
        rule = re.search(r'\.pbme-home\.pbme-employee \.o_portal_index_card:has\((.*?)\)\s*\{\s*'
                         r'display:\s*none !important;', scss, re.S)
        self.assertTrue(rule, "the employee-only rule must stay")
        for prefix in ('/my/invoices', '/my/projects', '/my/tasks', '/my/timesheets'):
            self.assertIn('a[href^="%s"]' % prefix, rule.group(1))

    # ------------------------------------------------------------ test 11
    def test_11_clean_sources(self):
        tpl = _new_template_source()
        sources = {'templates': tpl, 'scss': _mehome_scss(), 'js': _read(_JS)}
        emoji = re.compile('[\U0001F300-\U0001FAFF☀-➿️]')
        for label, src in sources.items():
            self.assertNotRegex(src.lower(), r'\bodoo\b', label)
            self.assertIsNone(emoji.search(src), label)
            self.assertNotRegex(src, r'\bfa-[a-z]|class="fa\b|\bfa fa\b', label)
            self.assertNotIn('#4f46e5', src.lower(), label)
            self.assertNotIn('linear-gradient', src, label)
        js = _read(_JS)
        self.assertNotIn('cloneNode', js)
        self.assertNotRegex(js, r'placeholder_count\s*=|dataset\.placeholder_count|'
                                r'setAttribute\(\s*["\']data-placeholder_count')

    def test_11_every_icon_name_is_drawn(self):
        src = _strip_xml_comments(_read(_TEMPLATES))
        drawn = set(re.findall(r"icon == '([a-z-]+)'", src))
        used = set(re.findall(r"""t-set="icon" t-value="'([a-z-]+)'\"""", _new_template_source()))
        used |= {m['icon'] for m in pb_me_home.TILES.values()}
        used.add(pb_me_home.TILE_DEFAULT['icon'])
        # 'file' is the else-branch on purpose (ess_icon's header comment)
        self.assertEqual(used - drawn - {'file'}, set())

    def test_11_registry_shape(self):
        for url, meta in pb_me_home.TILES.items():
            self.assertTrue(url.startswith('/my/'), url)
            self.assertNotIn('?', url)
            self.assertIn(meta['group'], pb_me_home.GROUPS, url)
            self.assertIn(meta['tone'], ('indigo', 'green', 'blue', 'amber',
                                         'rose', 'teal', 'pink', 'slate'), url)
        model_src = _read(_MODEL)
        for model in OPTIONAL_MODELS:
            self.assertIn("'%s'" % model, model_src, model)
        manifest = _read(os.path.join(_HERE, '__manifest__.py'))
        for model in OPTIONAL_MODELS:
            module = {'pb.ess.workforce': 'pb_ess_workforce',
                      'pb.payroll.calendar': 'pb_comp_ben',
                      'pb.my.training': 'pb_training',
                      'pb.my.goals': 'pb_goals',
                      'pb.pay.apply': 'pb_pay'}[model]
            self.assertNotIn("'%s'" % module, manifest, "no new dependency (M-R3)")

    # ------------------------------------------------------------ test 12
    def _po(self):
        try:
            import polib
        except ImportError:
            self.skipTest('polib is not installed on this server')
        return polib.pofile(_PO)

    def test_12_vi_po_parses_and_covers_the_new_words(self):
        po = self._po()
        empty = [e.msgid for e in po if not e.msgstr and not e.obsolete]
        self.assertEqual(empty, [], "untranslated entries in vi_VN.po")
        for e in po:
            if e.obsolete:
                continue
            comments = e.comment or ''
            self.assertTrue(comments.startswith('module: pb_me_portal')
                            or comments.startswith('module:'), e.msgid)
            if any(o[0].startswith('code:') for o in e.occurrences):
                self.assertTrue('odoo-python' in comments or 'odoo-javascript' in comments,
                                e.msgid)
        have = {e.msgid for e in po if not e.obsolete}
        terms = []
        for xmlid in NEW_TEMPLATES:
            view = self.env.ref('pb_me_portal.%s' % xmlid)
            xml_translate(lambda t: terms.append(t), view.with_context(lang='en_US').arch_db)
        terms = {t for t in terms if re.search(r'[A-Za-z]', t)}
        for meta in pb_me_home.TILES.values():
            for key in ('title', 'text'):
                if meta.get(key):
                    terms.add(meta[key]._source)
        missing = sorted(terms - have)
        self.assertEqual(missing, [], "new words with no Vietnamese line")
