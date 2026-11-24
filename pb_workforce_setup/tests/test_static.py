# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Static gates for the Workforce setup screen (WFSETUP P1, case 18).

S1  no "Odoo" in anything a person can read (templates, JS strings, views,
    manifest name and summary, Python messages)
S2  every icon name the screen asks for exists in the shared Lucide registry
    (an unknown name silently renders a tick — facts K7)
S3  no emoji characters in js / xml / scss (Lucide only)
S4  the client action tag is the NEW one, never the old workspace tag
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


# Emoji and pictographs (incl. variation selector), not ordinary punctuation
# such as the en dash, the ellipsis or the arrows a sentence may use.
EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️⬀-⯿]')


@tagged('post_install', '-at_install', 'wfsetup')
class TestSetupStatic(TransactionCase):

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
        for name in sorted(os.listdir(os.path.join(HERE, 'models'))):
            if not name.endswith('.py'):
                continue
            py = _src(HERE, 'models', name)
            for msg in re.findall(r'_\(\s*"([^"]+)"', py):
                self.assertNotRegex(msg, bad, '%s: %s' % (name, msg))

    def test_s2_every_icon_exists(self):
        registry = _src(ADDONS, 'pb_import_kit', 'static', 'src', 'js', 'import_icons.js')
        body = registry.split('export const IC = {', 1)[1].split('\n};', 1)[0]
        known = set(re.findall(r'^\s{4}([A-Za-z0-9]+):', body, flags=re.M))
        self.assertIn('check', known)
        used = set()
        for root, name in _files('.js', '.xml'):
            text = _src(root, name)
            used |= set(re.findall(r"\b(?:ic|icon)\(\s*['\"]([A-Za-z0-9]+)['\"]", text))
            # icon names kept in data (step list, preview) are spelled icon: "x"
            used |= set(re.findall(r"\bicon:\s*['\"]([A-Za-z0-9]+)['\"]", text))
        self.assertGreater(len(used), 10, 'the scan found the icon calls')
        missing = sorted(used - known)
        self.assertFalse(missing, 'unknown icon names render a tick: %s' % missing)

    def test_s3_no_emoji(self):
        for root, name in _files('.js', '.xml', '.scss'):
            for n, line in enumerate(_src(root, name).splitlines(), 1):
                self.assertFalse(EMOJI.search(line), '%s:%s has an emoji: %s' % (name, n, line.strip()))

    def test_s4_new_action_tag(self):
        xml = _src(HERE, 'views', 'setup_action.xml')
        self.assertIn('<field name="tag">pb_workforce_setup_studio</field>', xml)
        js = _code(_src(HERE, 'static', 'src', 'js', 'setup_studio.js'))
        self.assertIn('registry.category("actions").add("pb_workforce_setup_studio"', js)
        self.assertNotIn('add("pb_workforce_setup",', js)
