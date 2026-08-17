# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — T7: the design-system, context-law and template-law gates.

P1a/P1b established these for pb_time_hub and pb_today; they extend to
pb_schedule here, plus the three P2-specific ones:

  * the ELEVEN template identities exist and are defined in SCSS out of pbim
    tokens, not as hexes in JavaScript (the legacy grid's `SHIFT_COLORS`);
  * no element carries both `t-att-class` and `t-attf-class`, and every OWL
    template file parses as XML (W22/W23 — both failures are silent at `-u`
    and only kill the cockpit at mount);
  * the shared row budget is still one number.
"""

import os
import re
import xml.dom.minidom

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_MODULE = 'pb_schedule'

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
_RE_TOKEN_HEX = re.compile(r'#[0-9a-fA-F]{3,8}')
# pictographs + dingbats + the emoji variation selector, written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')

_RE_CTX_STATE = re.compile(r'\bctx(?:Svc)?\.state\.\w+\s*=(?!=)')
_RE_CTX_ALIAS = re.compile(
    r'\bthis\.(?:wf|ctx)\.(?:departmentId|weekStart|personId|search|day)\s*=(?!=)')


def _walk(module, suffixes, skip_tests=False):
    path = get_module_path(module)
    if not path:
        return
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git')]
        if skip_tests and os.path.basename(root) == 'tests':
            dirs[:] = []
            continue
        for f in files:
            if f.endswith(suffixes):
                yield os.path.join(root, f)


def _read(module, *parts):
    path = get_module_path(module)
    if not path:
        return ''
    full = os.path.join(path, *parts)
    if not os.path.exists(full):
        return ''
    with open(full, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestScheduleStaticGates(TransactionCase):

    # ------------------------------------------------------------- W1/W2/W3
    def test_schedule_invents_no_hex(self):
        tokens = _read('pb_import_kit', 'static', 'src', 'scss', 'import_tokens.scss')
        self.assertTrue(tokens, 'the pbim token file must be readable')
        allowed = {h.lower() for h in _RE_TOKEN_HEX.findall(tokens)}
        allowed |= {'#fff', '#ffffff', '#000', '#000000'}

        bad = []
        for path in _walk(_MODULE, ('.scss', '.js', '.xml', '.css'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for hexval in _RE_HEX.findall(line):
                        if hexval.lower() not in allowed:
                            bad.append('%s:%s: %s' % (path, n, hexval))
        self.assertFalse(bad, 'W1 violated — never invent a hex:\n%s' % '\n'.join(bad))

    def test_schedule_has_no_gradients_fontawesome_or_emoji(self):
        """The legacy grid shipped `⚠️` as its conflict marker and `fa-*`
        everywhere. Both die here."""
        bad = []
        for path in _walk(_MODULE, ('.scss', '.js', '.xml', '.css', '.py'),
                          skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if 'linear-gradient' in line or 'radial-gradient' in line:
                        bad.append('%s:%s gradient chrome (W3)' % (path, n))
                    if re.search(r'\bfa-[a-z]', line) and not stripped.startswith('//'):
                        bad.append('%s:%s FontAwesome (W2)' % (path, n))
                    if _RE_EMOJI.search(line):
                        bad.append('%s:%s emoji (W2)' % (path, n))
        self.assertFalse(bad, '\n'.join(bad))

    # --------------------------------------------------- the eleven tones
    def test_the_template_palette_is_eleven_token_derived_tints(self):
        """§3.8: a FIXED 11-entry palette derived from pbim tones, mapped from
        `hr.shift.template.color`. The JS may only ever emit a class name — if
        a hex ever appears there again the gate above catches it, and this one
        catches a palette that has quietly grown or shrunk."""
        scss = _read(_MODULE, 'static', 'src', 'scss', 'pb_schedule.scss')
        self.assertTrue(scss)

        def keys(map_name):
            block = re.search(r'\$%s:\s*\((.*?)\n\);' % map_name, scss, re.S)
            self.assertTrue(block, 'no $%s map in pb_schedule.scss' % map_name)
            return sorted(int(n) for n in
                          re.findall(r'^\s*(\d+):', block.group(1), re.M))

        self.assertEqual(keys('pbsc-accent'), list(range(11)),
                         'the accent palette must define exactly tones 0..10')
        self.assertEqual(keys('pbsc-soft'), list(range(11)),
                         'the soft palette must mirror the accent palette')

        js = _read(_MODULE, 'static', 'src', 'js', 'pb_schedule.js')
        m = re.search(r'TEMPLATE_TONES\s*=\s*(\d+)', js)
        self.assertTrue(m, 'pb_schedule.js must declare TEMPLATE_TONES')
        self.assertEqual(int(m.group(1)), 11,
                         'the JS modulus and the SCSS palette must agree')

    # ------------------------------------------------------------------ W16
    def test_schedule_never_writes_the_shared_context_directly(self):
        offenders = []
        scanned = 0
        for path in _walk(_MODULE, ('.js',)):
            scanned += 1
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    if _RE_CTX_STATE.search(line) or _RE_CTX_ALIAS.search(line):
                        offenders.append('%s:%s: %s' % (path, n, line.strip()))
        self.assertTrue(scanned, 'no JS was scanned — the walk is broken')
        self.assertFalse(offenders, 'W16 violated — use ctxSvc.set({...}):\n%s'
                         % '\n'.join(offenders))

    def test_the_cockpit_ships_no_private_department_or_week_picker(self):
        """W4: the legacy grid had its OWN department dropdown, job dropdown
        and week nav. Three unsynchronized contexts on one screen is why the
        shared bar exists."""
        js = _read(_MODULE, 'static', 'src', 'js', 'pb_schedule.js')
        tpl = _read(_MODULE, 'static', 'src', 'xml', 'pb_schedule.xml')
        self.assertIn('WfContextBar', tpl,
                      'the cockpit must mount the shared context bar')
        self.assertNotIn('get_departments', js,
                         'department options come from the shared bar, not a '
                         'private RPC (W4)')
        self.assertNotIn('get_job_positions', js,
                         'the job filter was a second, unsynchronized context')

    # ------------------------------------------------------------ W5 doors
    def test_no_surface_dead_ends_on_target_current(self):
        """The legacy grid opened a shift with `target: "current"`, which
        replaced the whole roster with a form and left no way back."""
        bad = []
        for path in _walk(_MODULE, ('.js',), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith(('//', '*', '/*')):
                        continue
                    if re.search(r'target:\s*["\']current["\']', line):
                        bad.append('%s:%s: %s' % (path, n, stripped))
        self.assertFalse(bad, 'W5 violated — use target:"new":\n%s' % '\n'.join(bad))

    def test_every_row_is_a_door(self):
        tpl = _read(_MODULE, 'static', 'src', 'xml', 'pb_schedule.xml')
        self.assertIn('openPerson', tpl, 'an avatar must open the person drawer')
        self.assertIn('WfPersonWeek', tpl,
                      'the drawer body must be the KIT panel, not a fork (W6)')
        self.assertIn('openShift', tpl, 'a shift card must open its record')

    # ------------------------------------------------------------ W22/W23
    def test_every_template_file_parses_as_xml(self):
        """W22: a `--` inside an XML comment is a parse error that takes the
        WHOLE template file down, and the symptom is "Missing template" on a
        component that is perfectly fine."""
        seen = 0
        for path in _walk(_MODULE, ('.xml',)):
            seen += 1
            try:
                xml.dom.minidom.parse(path)
            except Exception as exc:                            # pragma: no cover
                self.fail('%s does not parse: %s' % (path, exc))
        self.assertTrue(seen, 'no XML was scanned — the walk is broken')

    def test_no_element_carries_both_class_bindings(self):
        """W23: `t-att-class` and `t-attf-class` compile to the SAME `class`
        attribute, so an element with both gets whichever the compiler wrote
        last. Pick one."""
        tpl = _read(_MODULE, 'static', 'src', 'xml', 'pb_schedule.xml')
        # split on '<' so each chunk is at most one tag's worth of attributes
        bad = [c[:80] for c in tpl.split('<')
               if 't-att-class' in c and 't-attf-class' in c]
        self.assertFalse(bad, 'W23 violated:\n%s' % '\n'.join(bad))

    # ----------------------------------------------------------- WF_ROW_CAP
    def test_the_row_cap_is_still_one_number(self):
        js = _read('pb_wf_kit', 'static', 'src', 'js', 'wf_rows.js')
        m = re.search(r'WF_ROW_CAP\s*=\s*(\d+)', js)
        self.assertTrue(m, 'pb_wf_kit must export WF_ROW_CAP')
        py = _read(_MODULE, 'models', 'schedule_grid.py')
        mine = re.search(r'WF_ROW_CAP\s*=\s*(\d+)', py)
        self.assertTrue(mine, 'pb_schedule must mirror the shared row budget')
        self.assertEqual(int(mine.group(1)), int(m.group(1)),
                         'the shared row budget has drifted (§2.6)')

    # --------------------------------------------------------- non-goals
    def test_pb_schedule_never_touches_the_hr_shift_module(self):
        """A binding non-goal: `hr_shift` declares a DIFFERENT model that is
        also called hr.shift.planning (hr_shift/models/shift_planning.py:15)."""
        manifest = _read(_MODULE, '__manifest__.py')
        self.assertNotIn("'hr_shift'", manifest)
        bad = []
        for path in _walk(_MODULE, ('.py', '.js', '.xml'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    if 'hr_shift.' in line or 'addons.hr_shift' in line:
                        bad.append('%s:%s' % (path, n))
        self.assertFalse(bad, 'pb_schedule must not reference hr_shift:\n%s'
                         % '\n'.join(bad))
