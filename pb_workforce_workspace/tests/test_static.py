"""WFSETUP P5c — the grouped Workforce tab bar and the overview are translated.

1. The `.pot` and the Vietnamese / Indonesian `.po` files load: they parse with
   the product's own reader (the parse gate), every sentence of the template
   has a translation in both, no translation names the vendor, placeholders
   survive, and every entry carries the three loading markers.
2. No label is translated at module load: a `_t` inside a module-level
   constant runs before the user's translations are there.
3. Every tab of both menus has a translated name.
"""
import os
import re

from odoo.tests.common import TransactionCase, tagged
from odoo.tools.translate import PoFileReader

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = 'pb_workforce_workspace'


def _src(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as f:
        return f.read()


def _placeholders(text):
    return sorted(re.findall(r'%\([a-z_]+\)[sd]|%[sd]', text or ''))


@tagged('post_install', '-at_install', 'wfsetup')
class TestWorkspaceStatic(TransactionCase):

    def test_01_translations_load(self):
        pot = set()
        with open(os.path.join(HERE, 'i18n', '%s.pot' % MODULE), 'rb') as f:
            for row in PoFileReader(f):
                pot.add(row['src'])
        for must in ('Overview', 'Roster', 'Timesheets', 'More', 'Workforce setup', 'Factory overview',
                     'Review roster', 'Every workplace. One view.', '%s people'):
            self.assertIn(must, pot)
        vendor = re.compile(r'odoo', re.I)
        for src in pot:
            self.assertNotRegex(src, vendor)
        for lang in ('vi_VN', 'id_ID'):
            path = os.path.join(HERE, 'i18n', '%s.po' % lang)
            with open(path, 'rb') as f:
                rows = list(PoFileReader(f))
            done = {}
            for row in rows:
                self.assertTrue((row['value'] or '').strip(), '%s: no translation for %r' % (lang, row['src']))
                self.assertNotRegex(row['value'], vendor, '%s: %r' % (lang, row['src']))
                self.assertEqual(_placeholders(row['src']), _placeholders(row['value']), '%s: %r' % (lang, row['src']))
                done[row['src']] = row['value']
            self.assertFalse(sorted(pot - set(done)), '%s lacks sentences' % lang)
            entries = [e.strip() for e in _src('i18n', '%s.po' % lang).split('\n\n') if 'msgid "' in e]
            for e in entries:
                if re.search(r'^msgid ""\nmsgstr ""', e, flags=re.M):
                    continue
                self.assertTrue(e.startswith('#. module: %s' % MODULE), e[:120])
                if 'code:addons/' in e:
                    self.assertRegex(e, r'#\. odoo-(python|javascript)', e[:160])
                self.assertRegex(e, r'#: (code|model|model_terms):', e[:160])

    def test_02_no_translation_at_module_load(self):
        js = _src('static', 'src', 'workspace.js')
        # the asset transpiler binds `_t` to THIS module's translations only for
        # this exact line (double quotes, nothing after the semicolon); any
        # other spelling falls back to whichever module's translation won
        self.assertIn('import { _t } from "@web/core/l10n/translation";\n', js)
        top = [line for line in js.splitlines() if re.match(r'(export )?const ', line) and '_t(' in line]
        self.assertFalse(top, top)
        self.assertNotIn('const LABELS', js)
        self.assertNotIn('const COPY =', js)
        # the lens names and the Settings card are getters, read when shown
        self.assertIn('get label(){return lensLabels()[key];}', js)
        self.assertIn('get label(){return _t("Set up Workforce");}', js)
        self.assertNotIn("toLocaleString", js)
        self.assertNotIn("toLocaleDateString", js)
        # no hard-coded English inside the template expressions
        xml = _src('static', 'src', 'workspace.xml')
        self.assertFalse(re.findall(r't-esc="[^"]*\'[A-Z][a-z]+ [^"]*\'', xml))

    def test_03_every_tab_has_a_translated_name(self):
        js = _src('static', 'src', 'workspace.js')
        names = set(re.findall(r"\{label:'([^']+)', keys:", js))
        self.assertEqual(len(names), 8)
        body = re.search(r'export function groupLabel\(label\)\{(.*?)\n\}', js, flags=re.S).group(1)
        for name in names:
            self.assertIn("'%s':_t(\"%s\")" % (name, name), body)
        self.assertIn('t-esc="g.title"', _src('static', 'src', 'workspace.xml'))
