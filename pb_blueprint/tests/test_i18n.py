# -*- coding: utf-8 -*-
"""The Vietnamese catalogue, and the two ways it silently goes wrong.

A `.po` file is the one artefact in this programme that can take a DATABASE
down: `odoo/tools/translate.py` reads `#. module: <name>` off every entry with
no guard at all, and an entry without one is an `AttributeError` during install
that stops the registry from loading (GR5). So the first test here is the one
that matters most, and it runs against the file on disk rather than against
anything a database has already accepted.

The rest is about strings that quietly stay English:

* a `_t()` literal that is not in the catalogue is a string nobody translated,
  usually because it was added after the catalogue was built;
* a literal split across two lines is worse than untranslated — it is a
  JavaScript syntax error that takes the whole backend bundle with it, and the
  extractor would only ever have seen its first half anyway (BP26, BP47).
"""
import os
import re

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PO = os.path.join(HERE, 'i18n', 'vi_VN.po')

#: GR5's own regex, from `odoo/tools/translate.py`.
MODULE_RE = re.compile(r"(module[s]?): (\w+)")

#: A `_t("…")` on ONE line. Anything built from a variable is not a literal and
#: is not extractable in any language.
T_RE = re.compile(r"""_t\(\s*(["'])((?:\\.|(?!\1).)*)\1""")

#: `"…"` followed by a newline and another `"…"` — Python's implicit
#: concatenation, which is a SYNTAX ERROR in JavaScript.
SPLIT_RE = re.compile(r'"[ \t]*\n[ \t]*"')

BANNED_IN_TRANSLATION = ('odoo', 'blueprint')


def js_files():
    out = []
    for folder in ('static/src/js', 'static/tests'):
        base = os.path.join(HERE, folder)
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.endswith('.js'):
                out.append(os.path.join(base, name))
    return out


def entries():
    """`msgid -> msgstr` plus the raw comment, without needing polib."""
    if not os.path.exists(PO):
        return None
    rows, current = [], {}
    key = None
    with open(PO, encoding='utf-8') as handle:
        for line in handle:
            line = line.rstrip('\n')
            if line.startswith('#. '):
                current.setdefault('comment', []).append(line[3:])
            elif line.startswith('msgid '):
                key = 'msgid'
                current[key] = [line[7:-1]]
            elif line.startswith('msgstr '):
                key = 'msgstr'
                current[key] = [line[8:-1]]
            elif line.startswith('"') and key:
                current[key].append(line[1:-1])
            elif not line.strip():
                if current.get('msgid') is not None:
                    rows.append(current)
                current, key = {}, None
    if current.get('msgid') is not None:
        rows.append(current)
    out = []
    for row in rows:
        msgid = ''.join(row.get('msgid') or [])
        if not msgid:
            continue                       # the header
        out.append({
            'msgid': msgid.replace('\\"', '"').replace('\\n', '\n'),
            'msgstr': ''.join(row.get('msgstr') or []),
            'comment': '\n'.join(row.get('comment') or []),
        })
    return out


@tagged('post_install', '-at_install')
class TestVietnamese(TransactionCase):

    def test_every_entry_names_its_module(self):
        """GR5 — the one that takes a database down."""
        rows = entries()
        self.assertIsNotNone(rows, "pb_blueprint/i18n/vi_VN.po is missing")
        self.assertTrue(rows, "the catalogue is empty")
        bad = [r['msgid'][:60] for r in rows
               if not MODULE_RE.match(r['comment'] or '')]
        self.assertFalse(
            bad, "%s entries carry no “#. module:” comment: %s" % (len(bad), bad[:5]))

    def test_no_translation_says_a_word_a_user_may_never_read(self):
        rows = entries() or []
        for row in rows:
            low = (row['msgstr'] or '').lower()
            for word in BANNED_IN_TRANSLATION:
                self.assertNotIn(
                    word, low,
                    "the Vietnamese for “%s” says “%s”" % (row['msgid'][:40], word))

    def test_every_literal_on_screen_has_a_translation(self):
        """A `_t()` literal with no entry is a screen that stays English.

        Only single-line JS literals: a Python `_()` written across two lines is
        legal and the exporter joins it, and QWeb text is extracted from the
        template rather than from anything a regex here could see. Both of those
        are the POT export's job; this catches the case that actually happens —
        a string added after the catalogue was last built.
        """
        rows = entries()
        if rows is None:
            self.skipTest("no catalogue on disk")
        known = {r['msgid'] for r in rows}
        missing = []
        for path in js_files():
            if os.sep + 'tests' + os.sep in path:
                continue               # a test's own words are never on screen
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
            for _quote, literal in T_RE.findall(source):
                text = literal.replace('\\"', '"').replace("\\'", "'")
                if not text.strip() or text in known:
                    continue
                missing.append((os.path.basename(path), text[:60]))
        self.assertFalse(
            missing,
            "%s strings are not in the Vietnamese catalogue — re-run "
            "tools/refresh_pb_vi.py: %s" % (len(missing), missing[:6]))

    def test_no_javascript_string_is_split_across_two_lines(self):
        """BP26/BP47 — and `node --check` will not tell you.

        Two adjacent string literals are Python's implicit concatenation and
        JavaScript's syntax error, and the failure is a BLANK BACKEND rather
        than a broken component. `node --check file.js` passes it anyway on
        Node 24 (the ambiguous CommonJS/ESM retry swallows the error); the same
        bytes in a `.mjs` file are refused. This scan is the guard that does not
        depend on which extension somebody checked.
        """
        broken = []
        for path in js_files():
            with open(path, encoding='utf-8') as handle:
                source = handle.read()
            for match in SPLIT_RE.finditer(source):
                line = source[:match.start()].count('\n') + 1
                broken.append('%s:%s' % (os.path.basename(path), line))
        self.assertFalse(
            broken, "string literals split across lines (a syntax error that "
                    "blanks the whole backend): %s" % broken[:8])
