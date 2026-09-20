# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1b — T4: the design-system, context-law and shared-constant gates.

P1a's gates (pb_time_hub/tests/test_static.py) cover W16 across every context
consumer and W1/W2/W3 for the Time hub. These extend them to `pb_today`, and
add the two P1b-specific ones:

  * every Today row and tile is a DOOR (W5) — a triage board of dead ends is
    the Live Attendance feed it replaces;
  * `WF_ROW_CAP` is ONE number. It is declared in JS and mirrored in three
    Python facades; a constant duplicated in four files is a constant that
    drifts, so the gate reads all four and compares them.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
_RE_TOKEN_HEX = re.compile(r'#[0-9a-fA-F]{3,8}')
# pictographs + dingbats + the emoji variation selector; written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')

# `ctx.state.x =` / `ctxSvc.state.x =` — writing through the service handle
_RE_CTX_STATE = re.compile(r'\bctx(?:Svc)?\.state\.\w+\s*=(?!=)')
# `this.wf.weekStart =` / `this.ctx.personId =` — writing through a bound alias
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
class TestTodayStaticGates(TransactionCase):

    # ------------------------------------------------------------- W1/W2/W3
    def test_today_invents_no_hex(self):
        tokens = _read('pb_import_kit', 'static', 'src', 'scss', 'import_tokens.scss')
        self.assertTrue(tokens, 'the pbim token file must be readable')
        allowed = {h.lower() for h in _RE_TOKEN_HEX.findall(tokens)}
        allowed |= {'#fff', '#ffffff', '#000', '#000000'}

        bad = []
        for path in _walk('pb_today', ('.scss', '.js', '.xml', '.css'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for hexval in _RE_HEX.findall(line):
                        if hexval.lower() not in allowed:
                            bad.append('%s:%s: %s' % (path, n, hexval))
        self.assertFalse(bad, 'W1 violated — never invent a hex:\n%s' % '\n'.join(bad))

    def test_today_has_no_gradients_fontawesome_or_emoji(self):
        bad = []
        for path in _walk('pb_today', ('.scss', '.js', '.xml', '.css', '.py'),
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

    def test_today_ships_no_charts(self):
        """A binding non-goal: the old dashboard's Chart.js analytics die with
        it. Deep analytics belong to Insights / the Analytics Explorer — Today
        is triage, and a chart on it is scope creep with a legend.

        The needles are CODE, not the words. An earlier version of this gate
        looked for the string "Chart.js" and duly failed on its own docstring
        and on the manifest paragraph explaining that the charts were dropped —
        a gate that forbids naming the thing it forbids is a gate nobody can
        document around.
        """
        bad = []
        for path in _walk('pb_today', ('.js', '.xml', '.py'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                body = fh.read()
            for needle in ('new Chart(', 'loadBundle(', 'Chart.register',
                           'chart.umd', 'chartjs'):
                if needle in body:
                    bad.append('%s: %s' % (path, needle))
        self.assertFalse(bad, 'Today must ship no charts:\n%s' % '\n'.join(bad))

    # ------------------------------------------------------------------ W16
    def test_today_never_writes_the_shared_context_directly(self):
        offenders = []
        scanned = 0
        for path in _walk('pb_today', ('.js',)):
            scanned += 1
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    if _RE_CTX_STATE.search(line) or _RE_CTX_ALIAS.search(line):
                        offenders.append('%s:%s: %s' % (path, n, line.strip()))
        self.assertTrue(scanned, 'no JS was scanned — the walk is broken')
        self.assertFalse(offenders, 'W16 violated — use ctxSvc.set({...}):\n%s'
                         % '\n'.join(offenders))

    # ------------------------------------------------------------- W5 doors
    def test_every_today_row_and_tile_is_a_door(self):
        """Tiles filter, avatars open the drawer, late/missing rows hand over to
        the Time hub. A board you can only look at is the surface this one
        replaces."""
        tpl = _read('pb_today', 'static', 'src', 'xml', 'pb_today.xml')
        self.assertTrue(tpl, 'the Today template must be readable')

        # Anchor + window, NOT `<button[^>]*>`. An OWL tag routinely contains a
        # `>` that does not close it — every inline handler is an arrow function
        # (`t-on-click="() => this.setFilter(...)"`), so a `[^>]*` tag match
        # stops dead at the fat arrow and silently inspects half an attribute.
        # That is not a hypothetical: it is what the first live run of this gate
        # did, and it reported a missing door on a template that had one.
        # Generous window: the anchors are followed by comments explaining the
        # markup, and a tight budget makes the gate fail on documentation
        # rather than on a missing door (it did, at 400 chars).
        def window(anchor, size=1500):
            i = tpl.find(anchor)
            self.assertNotEqual(i, -1, 'no %s in the Today template' % anchor)
            return tpl[i:i + size]

        tiles = window('class="pbtd-tiles"')
        self.assertIn('<button', tiles, 'the tile strip must be made of buttons')
        self.assertIn('setFilter', tiles, 'a tile must filter the list')

        row = window('class="pbtd-who"')
        self.assertIn('openPerson', row, 'the avatar must open the person drawer')

        self.assertIn('fileCorrection', tpl,
                      'a late/missing row must hand over to the Time hub')
        self.assertIn('WfPersonWeek', tpl,
                      'the drawer body must be the KIT panel, not a local fork (W6)')

    def test_no_surface_dead_ends_on_target_current(self):
        """W5: a native-form escape is a DIALOG you can close, never a
        target:"current" that replaces the cockpit with no way back."""
        bad = []
        for path in _walk('pb_today', ('.js',), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if stripped.startswith(('//', '*', '/*')):
                        continue
                    if re.search(r'target:\s*["\']current["\']', line):
                        bad.append('%s:%s: %s' % (path, n, stripped))
        self.assertFalse(bad, 'W5 violated — use target:"new":\n%s' % '\n'.join(bad))

    # ----------------------------------------------------------- WF_ROW_CAP
    def test_the_row_cap_is_one_number_everywhere(self):
        """§2.6 — one shared budget. The JS export is the declaration; every
        capping facade mirrors it. The Timeline's old 120 must be gone."""
        js = _read('pb_wf_kit', 'static', 'src', 'js', 'wf_rows.js')
        m = re.search(r'WF_ROW_CAP\s*=\s*(\d+)', js)
        self.assertTrue(m, 'pb_wf_kit must export WF_ROW_CAP')
        cap = int(m.group(1))
        self.assertEqual(cap, 200, 'the agreed budget is 200 rows')

        mirrors = {
            'pb_today': ('models', 'pb_today.py', r'WF_ROW_CAP\s*=\s*(\d+)'),
            'pb_time_hub': ('models', 'time_hub.py', r'_TIMELINE_MAX_ROWS\s*=\s*(\d+)'),
            'pb_hr_workforce': ('models', 'attendance_weekentry.py',
                                r'_MAX_ROWS\s*=\s*(\d+)'),
        }
        for module, (folder, fname, pattern) in mirrors.items():
            body = _read(module, folder, fname)
            if not body:
                continue
            hit = re.search(pattern, body)
            self.assertTrue(hit, 'no row cap found in %s/%s' % (module, fname))
            self.assertEqual(
                int(hit.group(1)), cap,
                '%s caps at %s while WF_ROW_CAP is %s — the shared budget has '
                'drifted (§2.6)' % (module, hit.group(1), cap))

    def test_the_today_board_writes_nothing(self):
        """`pb.today` is a strictly READ-ONLY facade.

        A triage board is polled every 30 s and clicked reflexively; P1a proved
        how fast a write reachable from a hot surface turns into junk rows. The
        correction is minted one click later, by the Exceptions composer.
        """
        body = _read('pb_today', 'models', 'pb_today.py')
        self.assertTrue(body)
        for needle in ('.create(', '.write(', '.unlink('):
            self.assertNotIn(needle, body,
                             'pb.today must not %s anything' % needle.strip('.('))
