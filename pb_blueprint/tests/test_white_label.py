# -*- coding: utf-8 -*-
"""The words on the screen, gated.

Two standing rules, and both fail silently — a screen that says the wrong word
still works, so nothing but a test catches it:

  * the product is white-labelled: "Odoo" may never appear in anything a person
    reads (ledger rule 1);
  * the product says "configuration". Never "schema", never "blueprint", never
    "config" as a word on screen (owner's vocabulary ruling, 2026-09-10).
    "Blueprint" is the ENGINEERING name for this module and belongs in
    docstrings, comments, model names and commit messages.

The gate therefore reads WHAT A PERSON READS and nothing else:

  * in a template, the text between tags plus the handful of attributes that
    carry words (`title`, `placeholder`, `aria-label`, `alt`);
  * in JavaScript and Python, string LITERALS only.

An earlier, broader version of this test read whole files and flagged
`blueprint="state.blueprint"` — a prop name. A gate that cries wolf on
identifiers is a gate somebody deletes, so it looks only where labels live.

Source assertions, in the shape `pb_formula_studio/tests/test_one_mapping_home.py`
established: a naming decision has no runtime handle to grab.
"""
import ast
import os
import re
import xml.etree.ElementTree as ET

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

MODULE = 'pb_blueprint'

#: On-screen words the product does not use. `config` is matched as a whole word
#: only, so "configuration" and "configurations" — which the product DOES say —
#: are never flagged.
BANNED = {
    'Odoo': r'\bodoo\b',
    'schema': r'\bschemas?\b',
    'blueprint': r'\bblueprints?\b',
    'config': r'\bconfigs?\b',
    'rule set': r'\brule sets?\b',
}

#: Attributes whose value is read by a person rather than by the framework.
WORD_ATTRS = ('title', 'placeholder', 'aria-label', 'alt', 'label')

#: A string that is plainly an identifier — a technical name, a template name, a
#: model, a field, a CSS class, a module path — is code, not a label. A label
#: has a space in it or is a single ordinary word.
_IDENTISH = re.compile(r'^[\w./@-]+$')

#: Template/JS expression strings inside attributes: `t-*` attributes hold code.
_QUOTED = re.compile(r'"([^"\n]*)"|\'([^\'\n]*)\'')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _walk(root, suffix):
    for base, _dirs, files in os.walk(root):
        if '__pycache__' in base:
            continue
        for name in sorted(files):
            if name.endswith(suffix):
                yield os.path.join(base, name)


def _is_label(text):
    """True when this string is something a person reads."""
    text = (text or '').strip()
    if not text or _IDENTISH.match(text):
        return False
    return True


def _template_words(path):
    """Every word a person reads in one QWeb template file."""
    out = []
    root = ET.parse(path).getroot()
    for el in root.iter():
        for part in (el.text, el.tail):
            if part and part.strip():
                out.append(part.strip())
        for attr in WORD_ATTRS:
            value = el.get(attr)
            if value and _is_label(value):
                out.append(value)
        # `t-att-title="'Open ' + c.name"` and friends: the literal halves of a
        # dynamic label are still read by somebody.
        for name, value in el.attrib.items():
            if not name.startswith('t-att') or not value:
                continue
            for a, b in _QUOTED.findall(value):
                piece = a or b
                if _is_label(piece):
                    out.append(piece)
    return out


def _js_strings(path):
    """Every string literal in one JavaScript file, comments removed first."""
    src = _read(path)
    src = re.sub(r'/\*(?:.|\n)*?\*/', '', src)
    src = re.sub(r'^\s*//.*$', '', src, flags=re.M)
    out = []
    for pattern in (r'"((?:[^"\\\n]|\\.)*)"', r"'((?:[^'\\\n]|\\.)*)'",
                    r'`((?:[^`\\]|\\.)*)`'):
        for hit in re.findall(pattern, src):
            if _is_label(hit):
                out.append(hit)
    return out


def _py_strings(path):
    """Every string literal in one Python file that a PERSON could read.

    Docstrings are out (engineering prose, and the ledger keeps the real names
    there), and so is everything inside a `_logger.*` call: a log line is read
    by an engineer in `/var/log`, never by a payroll manager, and the
    white-label rule explicitly exempts it.
    """
    tree = ast.parse(_read(path))
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                skip.add(doc)
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == '_logger'):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    skip.add(inner.value)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in skip:
                continue
            if _is_label(node.value):
                out.append(node.value)
    return out


@tagged('post_install', '-at_install')
class TestWhiteLabel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = get_module_path(MODULE)

    def _assert_clean(self, label, pieces):
        for text in pieces:
            for word, pattern in BANNED.items():
                hit = re.search(pattern, text, flags=re.I)
                self.assertIsNone(hit, (
                    "%s says “%s” where a person can read it:\n    %r\n"
                    "The product says “configuration”, and never “Odoo”."
                    % (label, word, text)))

    # ---- what the templates say -------------------------------------
    def test_templates_say_configuration(self):
        base = os.path.join(self.root, 'static', 'src', 'xml')
        seen = 0
        for path in _walk(base, '.xml'):
            words = _template_words(path)
            seen += len(words)
            self._assert_clean(os.path.basename(path), words)
        self.assertGreater(seen, 60, "the gate read almost nothing — check it "
                                     "is still finding the templates")

    # ---- what the JavaScript says -----------------------------------
    def test_javascript_strings_say_configuration(self):
        base = os.path.join(self.root, 'static', 'src', 'js')
        for path in _walk(base, '.js'):
            self._assert_clean(os.path.basename(path), _js_strings(path))

    # ---- what the server says ---------------------------------------
    def test_server_messages_say_configuration(self):
        for path in _walk(os.path.join(self.root, 'models'), '.py'):
            self._assert_clean(os.path.basename(path), _py_strings(path))

    # ---- the manifest is read in Apps -------------------------------
    def test_manifest_is_white_labelled(self):
        manifest = self.env['ir.module.module'].sudo().search(
            [('name', '=', MODULE)], limit=1)
        self.assertTrue(manifest, "%s is not installed" % MODULE)
        for field in ('shortdesc', 'summary', 'description'):
            self._assert_clean('manifest %s' % field, [manifest[field] or ''])

    # ---- the action name is the breadcrumb --------------------------
    def test_action_name_is_plain(self):
        action = self.env.ref('%s.action_pb_blueprint' % MODULE)
        self.assertEqual(action.name, 'New configuration')
        self.assertEqual(action.tag, 'pb_blueprint')

    # ---- icons come from the one registry ---------------------------
    def test_icons_come_from_the_kit_registry(self):
        """No local icon file, and the `js/` segment is not optional (W17.4)."""
        base = os.path.join(self.root, 'static', 'src', 'js')
        for path in _walk(base, '.js'):
            for line in _read(path).splitlines():
                if 'import_icons' not in line:
                    continue
                self.assertIn('@pb_import_kit/js/import_icons', line,
                              "%s imports the icon registry without the `js/` "
                              "segment — the bundle resolves it to nothing "
                              "(W17.4)" % os.path.basename(path))
        self.assertFalse(
            list(_walk(os.path.join(self.root, 'static', 'src'), 'icons.js')),
            "icons live in pb_import_kit's single registry, never in a local file (W2)")

    # ---- Lucide, never emoji ----------------------------------------
    def test_no_emoji(self):
        # The emoji planes only: the dingbat block would flag typographic marks
        # the product does use (a real minus sign, the command key).
        emoji = re.compile('[\U0001F000-\U0001FAFF\U00002B00-\U00002BFF]')
        for folder, suffix in (('xml', '.xml'), ('js', '.js')):
            base = os.path.join(self.root, 'static', 'src', folder)
            for path in _walk(base, suffix):
                hit = emoji.search(_read(path))
                self.assertIsNone(
                    hit, "%s uses an emoji (%s). Lucide icons only (rule 5)."
                    % (os.path.basename(path), hit.group(0) if hit else ''))

    # ---- the steps a person walks -----------------------------------
    def test_step_keys_match_the_server(self):
        """The rail and the server agree on the six steps, or a resume lands
        on a step the other one has never heard of."""
        from odoo.addons.pb_blueprint.models.blueprint import STEPS
        src = _read(os.path.join(
            self.root, 'static', 'src', 'js', 'blueprint_steps.js'))
        hit = re.search(r'export const STEPS = \[(.*?)\];', src, flags=re.S)
        self.assertTrue(hit, "blueprint_steps.js no longer declares STEPS")
        client = [s.strip().strip('"\'') for s in hit.group(1).split(',') if s.strip()]
        self.assertEqual(client, list(STEPS))
