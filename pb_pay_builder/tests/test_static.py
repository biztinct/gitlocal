import os
import re

from odoo.tests import TransactionCase, tagged
from odoo.modules.module import get_module_path
import ast
import polib

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
    for folder in ('static', 'views', 'data'):
        for root, _dirs, files in os.walk(os.path.join(HERE, folder)):
            for name in files:
                if name.endswith(exts):
                    yield root, name


EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️⬀-⯿]')


@tagged('post_install', '-at_install', 'paybuilder')
class TestBuilderStatic(TransactionCase):

    def test_s1_no_vendor_name_on_screen(self):
        bad = re.compile(r'odoo', re.I)
        allowed = re.compile(r'@odoo-module|@odoo/owl|from "@odoo/hoot"|</?odoo[ >]|odoo-javascript|odoo-python|'
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
        manifest = ast.literal_eval(_src(HERE, '__manifest__.py'))
        self.assertNotRegex(manifest['name'] + manifest['summary'], bad)
        for fname in sorted(os.listdir(os.path.join(HERE, 'models'))):
            if not fname.endswith('.py'):
                continue
            py = _src(HERE, 'models', fname)
            for msg in re.findall(r'_\(\s*"([^"]+)"', py) + re.findall(r"_\(\s*'([^']+)'", py):
                self.assertNotRegex(msg, bad, '%s: %s' % (fname, msg))

    def test_s2_every_icon_exists(self):
        registry = _src(get_module_path('pb_import_kit'), 'static', 'src', 'js', 'import_icons.js')
        body = registry.split('export const IC = {', 1)[1].split('\n};', 1)[0]
        known = set(re.findall(r'^\s{4}([A-Za-z0-9]+):', body, flags=re.M))
        self.assertIn('check', known)
        used = set()
        for root, name in _files('.js', '.xml'):
            text = _src(root, name)
            used |= set(re.findall(r"\b(?:ic|icon)\(\s*['\"]([A-Za-z0-9]+)['\"]", text))
            used |= set(re.findall(r"\bicon:\s*['\"]([A-Za-z0-9]+)['\"]", text))
        self.assertGreater(len(used), 3, 'the scan found the icon calls')
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

    def test_s6_screen_translations(self):
        ids = {entry.msgid for entry in polib.pofile(os.path.join(HERE, 'i18n', 'pb_pay_builder.pot'))}
        calls = set()
        for root, name in _files('.js'):
            calls.update(re.findall(r'\b_t\(\s*"([^"]+)"', _code(_src(root, name))))
        self.assertGreater(len(calls), 5)
        self.assertFalse(calls - ids)
        for locale in ('vi_VN', 'id_ID'):
            translated = {entry.msgid for entry in polib.pofile(os.path.join(HERE, 'i18n', locale + '.po')) if entry.msgstr}
            self.assertFalse(ids - translated)
