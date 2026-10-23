# -*- coding: utf-8 -*-
"""S12 — the promises this module keeps in its FILES rather than its behaviour.

A grep is the only thing that can tell "we did not do that" from "we did it and
it happens to look the same".
"""
import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
# pictographs + dingbats + the emoji variation selector, written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')


def _read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as handle:
        return handle.read()


def _strip_comments(text):
    """XML and block comments out — an engineering note is not a screen."""
    out = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    out = re.sub(r'/\*.*?\*/', '', out, flags=re.S)
    return re.sub(r'^\s*//.*$', '', out, flags=re.M)


def _walk(root, suffixes):
    for base, _dirs, files in os.walk(root):
        if '__pycache__' in base or os.sep + 'tests' in base + os.sep:
            continue
        for name in sorted(files):
            if name.endswith(suffixes):
                yield os.path.join(base, name)


@tagged('post_install', '-at_install')
class StaticContractCase(TransactionCase):

    def test_no_vendor_name_in_anything_a_person_reads(self):
        """The white-label rule. Technical identifiers and engineering
        COMMENTS are never touched — the rule binds what a person can read on
        a screen — so both are stripped before the scan."""
        offenders = []
        for path in _walk(HERE, ('.py', '.js', '.xml', '.scss', '.csv')):
            if path.endswith('.py'):
                # `from odoo import` and friends are identifiers, not copy.
                text = '\n'.join(
                    line for line in _read(path).splitlines()
                    if 'odoo' in line.lower()
                    and 'import' not in line
                    and not line.strip().startswith('#'))
            else:
                text = _strip_comments(_read(path))
            if 'Odoo' in text:
                offenders.append(os.path.relpath(path, HERE))
        self.assertFalse(offenders, 'the vendor name is readable in %s'
                                    % offenders)

    def test_no_emoji_anywhere(self):
        offenders = [os.path.relpath(path, HERE)
                     for path in _walk(HERE, ('.py', '.js', '.xml', '.scss'))
                     if _RE_EMOJI.search(_read(path))]
        self.assertFalse(offenders, 'emoji in %s' % offenders)

    def test_the_stylesheet_invents_no_colour(self):
        """Every colour comes from the kit's tokens."""
        scss = _read(HERE, 'static', 'src', 'scss', 'week_approval.scss')
        self.assertFalse(_RE_HEX.findall(scss),
                         'a hard-coded colour in week_approval.scss')

    def test_the_grid_is_patched_and_not_forked(self):
        """The weekly grid stays in the module that owns it."""
        js = _read(HERE, 'static', 'src', 'js', 'week_approval.js')
        self.assertIn('patch(AttendanceWeekGrid.prototype', js)
        xml = _read(HERE, 'static', 'src', 'xml', 'week_approval.xml')
        self.assertIn('t-inherit="pb_hr_workforce.AttendanceWeekGrid"', xml)
        self.assertIn('t-inherit-mode="extension"', xml)

    def test_every_user_facing_string_goes_through_translation(self):
        """A raise or a notification with a bare string is untranslatable."""
        offenders = []
        for path in _walk(HERE, ('.py',)):
            for number, line in enumerate(_read(path).splitlines(), start=1):
                stripped = line.strip()
                if not (stripped.startswith('raise UserError(')
                        or stripped.startswith('raise AccessError(')
                        or stripped.startswith('raise ValidationError(')):
                    continue
                # A raise whose argument is a call — `_frozen_message(...)`
                # — carries no string of its own to translate; the message it
                # builds is translated where it is written. Only a raise with a
                # LITERAL in it can be an untranslated message.
                if '"' not in line and "'" not in line:
                    continue
                if '_(' not in line:
                    offenders.append('%s:%s' % (
                        os.path.relpath(path, HERE), number))
        self.assertFalse(offenders, 'untranslated message at %s' % offenders)

    def test_the_module_never_depends_on_a_hub(self):
        """Hubs depend on approvals, never the other way round (ledger)."""
        manifest = _read(HERE, '__manifest__.py')
        for forbidden in ('pb_home_hub', 'pb_mission', 'pb_approval',
                          'pb_payruns'):
            self.assertNotIn("'%s'" % forbidden, manifest,
                             '%s must not be a dependency' % forbidden)
