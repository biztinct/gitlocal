# -*- coding: utf-8 -*-
"""PSCHEME P2a — static gates.

T13 every user-visible string this phase added (the list in
    `p2a_msgids.txt`, made from the catalogue export) is in the module's
    catalogue, has a Vietnamese and an Indonesian translation, and never says
    "Odoo", "rung", "config" or "cycle"; no translation says "Odoo"; the new
    source files' `_()` / `_t()` literals pass the same word check
T14 the dependency rail: the formula engine and the pay run never depend on
    this module (the P1 static contract keeps asserting it; repeated here so
    the phase's own run proves it)
"""

import ast
import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
ADDONS = os.path.dirname(ROOT)
BANNED = re.compile(r'\b(odoo|rung|rungs|config|configs|cycle|cycles)\b', re.I)
NEW_PY = ('pb_person_scheme_many.py', 'pb_person_scheme_fill.py',
          'pb_person_scheme_team.py', 'pb_person_scheme_follow.py')
NEW_JS = ('person_fill.js',)


def catalogue(path):
    text = open(path, encoding='utf-8').read()
    out = {}
    for block in re.split(r'\n\s*\n', text):
        mid = re.search(r'^msgid ((?:".*"\n?)+)', block, re.M)
        mstr = re.search(r'^msgstr ((?:".*"\n?)+)', block, re.M)
        if not mid:
            continue
        key = ''.join(re.findall(r'"(.*)"', mid.group(1)))
        if key:
            out[key] = ''.join(re.findall(r'"(.*)"', mstr.group(1))) if mstr else ''
    return out


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2a')
class TestP2aStatic(TransactionCase):

    def test_t13_words_and_translations(self):
        with open(os.path.join(HERE, 'p2a_msgids.txt'), encoding='utf-8') as handle:
            wanted = [line.rstrip('\n') for line in handle if line.strip()]
        self.assertGreater(len(wanted), 50)
        pot = catalogue(os.path.join(ROOT, 'i18n', 'pb_scheme_map.pot'))
        vi = catalogue(os.path.join(ROOT, 'i18n', 'vi_VN.po'))
        idn = catalogue(os.path.join(ROOT, 'i18n', 'id_ID.po'))
        for msgid in wanted:
            self.assertIn(msgid, pot, msgid)
            self.assertNotRegex(msgid, BANNED, msgid)
            self.assertTrue(vi.get(msgid), 'vi_VN: %s' % msgid)
            self.assertTrue(idn.get(msgid), 'id_ID: %s' % msgid)
            for lang, table in (('vi', vi), ('id', idn)):
                self.assertNotRegex(table[msgid], re.compile(r'\bodoo\b', re.I), lang)
                # every placeholder survives the translation
                self.assertEqual(sorted(re.findall(r'%\(\w+\)s|%s', msgid)),
                                 sorted(re.findall(r'%\(\w+\)s|%s', table[msgid])),
                                 '%s: %s' % (lang, msgid))

    def test_t13_source_literals(self):
        literals = []
        for name in NEW_PY:
            tree = ast.parse(open(os.path.join(ROOT, 'models', name), encoding='utf-8').read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, 'id', '') == '_' \
                        and node.args and isinstance(node.args[0], ast.Constant):
                    literals.append(node.args[0].value)
        for name in NEW_JS:
            text = open(os.path.join(ROOT, 'static', 'src', 'js', name), encoding='utf-8').read()
            literals += re.findall(r'_t\(\s*"((?:\\.|[^"\\])*)"', text)
        self.assertGreater(len(literals), 40)
        for text in literals:
            self.assertNotRegex(text, BANNED, text)

    def test_t14_dependency_rail(self):
        for module in ('pb_hr_payroll_formula', 'pb_payrun_wizard'):
            manifest = ast.literal_eval(open(os.path.join(
                ADDONS, module, '__manifest__.py'), encoding='utf-8').read())
            self.assertNotIn('pb_scheme_map', manifest.get('depends') or [], module)
