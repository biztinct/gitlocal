# -*- coding: utf-8 -*-
"""T15 — static gates for the New Hire Studio (cloned from
pb_workforce_setup/tests/test_static.py).

S1  no "Odoo" in anything a person can read (templates, JS strings, views,
    manifest name and summary, Python messages)
S2  every icon name the screen asks for exists in the shared Lucide registry
    (an unknown name silently renders a tick)
S3  no emoji characters in js / xml / scss (Lucide only)
S4  every `_t` import is exactly the form the translation export reads (WS40)
S5  the client action tag is the studio's, and the old tag is taken over
"""
import os
import re

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDONS = os.path.dirname(HERE)


def _src(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return f.read()


def _code(text):
    """JS / SCSS without comments, so a word in a comment proves nothing."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return re.sub(r'(^|\s)//[^\n]*', r'\1', text)


def _files(*exts):
    for folder in ('static', 'views'):
        for root, _dirs, files in os.walk(os.path.join(HERE, folder)):
            for name in files:
                if name.endswith(exts):
                    yield root, name


EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️⬀-⯿]')


@tagged('post_install', '-at_install', 'newhire')
class TestNewHireStatic(TransactionCase):

    def test_s1_no_vendor_name_on_screen(self):
        bad = re.compile(r'odoo', re.I)
        allowed = re.compile(r'@odoo-module|@odoo/owl|</?odoo[ >]|odoo-javascript|odoo-python|'
                             r'from odoo|import odoo|odoo\.|@web/')
        for root, name in _files('.js', '.xml', '.scss'):
            text = _src(root, name)
            if not name.endswith('.xml'):
                text = _code(text)
            else:
                text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
            for n, line in enumerate(text.splitlines(), 1):
                if bad.search(allowed.sub('', line)):
                    self.fail('%s:%s names the vendor: %s' % (name, n, line.strip()))
        man = _src(HERE, '__manifest__.py')
        name = re.search(r"'name': '([^']+)'", man).group(1)
        summary = re.search(r"'summary': ([^\n]+\n[^\n]+)", man).group(1)
        self.assertNotRegex(name + summary, bad)
        for fname in sorted(os.listdir(os.path.join(HERE, 'models'))):
            if not fname.endswith('.py'):
                continue
            py = _src(HERE, 'models', fname)
            for msg in re.findall(r'_\(\s*"([^"]+)"', py) + re.findall(r"_\(\s*'([^']+)'", py):
                self.assertNotRegex(msg, bad, '%s: %s' % (fname, msg))

    def test_s2_every_icon_exists(self):
        registry = _src(ADDONS, 'pb_import_kit', 'static', 'src', 'js', 'import_icons.js')
        body = registry.split('export const IC = {', 1)[1].split('\n};', 1)[0]
        known = set(re.findall(r'^\s{4}([A-Za-z0-9]+):', body, flags=re.M))
        self.assertIn('check', known)
        used = set()
        for root, name in _files('.js', '.xml'):
            text = _src(root, name)
            used |= set(re.findall(r"\b(?:ic|icon)\(\s*['\"]([A-Za-z0-9]+)['\"]", text))
            used |= set(re.findall(r"\bicon:\s*['\"]([A-Za-z0-9]+)['\"]", text))
        self.assertGreater(len(used), 10, 'the scan found the icon calls')
        missing = sorted(used - known)
        self.assertFalse(missing, 'unknown icon names render a tick: %s' % missing)

    def test_s3_no_emoji(self):
        for root, name in _files('.js', '.xml', '.scss'):
            for n, line in enumerate(_src(root, name).splitlines(), 1):
                self.assertFalse(EMOJI.search(line), '%s:%s has an emoji: %s' % (name, n, line.strip()))

    def test_s4_translation_import_form(self):
        for root, name in _files('.js'):
            text = _src(root, name)
            if '_t(' not in text:
                continue
            self.assertIn('import { _t } from "@web/core/l10n/translation";\n', text, name)
            # the export only reads a LITERAL first argument (WS39)
            for call in re.findall(r'\b_t\(\s*([^\s)])', _code(text)):
                self.assertIn(call, ('"', "'", '`'), '%s: _t() of a variable' % name)

    def test_s5_action_tags(self):
        xml = _src(HERE, 'views', 'studio_action.xml')
        self.assertIn('<field name="tag">pb_new_hire_studio</field>', xml)
        self.assertIn('<field name="name">Add employee</field>', xml)
        js = _code(_src(HERE, 'static', 'src', 'js', 'new_hire_studio.js'))
        self.assertIn('registry.category("actions").add("pb_new_hire_studio"', js)
        takeover = _code(_src(HERE, 'static', 'src', 'js', 'takeover.js'))
        self.assertIn('add("pb_onboard_wizard", NewHireDoor, { force: true })', takeover)
