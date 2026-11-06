# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P1a — T4: the design-system and context-law gates, as tests.

A grep is only a gate if something runs it, so the handover's static checks live
here rather than in a shell history:

  * W16 — `wf_context.set()` is the only write door; no surface assigns to the
    shared reactive directly.
  * W1/W2/W3 — the hub invents no hex, ships no gradient chrome, no FontAwesome
    and no emoji.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# Every module that consumes wf_context (present ones are scanned, absent ones
# skipped — the suite must not depend on which cockpits are installed).
_CTX_CONSUMERS = (
    'pb_wf_kit', 'pb_time_hub', 'pb_hr_workforce', 'pb_attendance_flow',
    'pb_timeoff', 'pb_team', 'pb_business_trip', 'pb_driver_checkin',
)

# `ctx.state.x =` / `ctxSvc.state.x =` — writing through the service handle
_RE_CTX_STATE = re.compile(r'\bctx(?:Svc)?\.state\.\w+\s*=(?!=)')
# `this.wf.weekStart =` / `this.ctx.personId =` — writing through a bound alias
_RE_CTX_ALIAS = re.compile(
    r'\bthis\.(?:wf|ctx)\.(?:departmentId|weekStart|personId|search|day)\s*=(?!=)')

_RE_HEX = re.compile(r'#[0-9a-fA-F]{3,8}\b')
_RE_TOKEN_HEX = re.compile(r'#[0-9a-fA-F]{3,8}')
# pictographs + dingbats + the emoji variation selector; written as escapes so
# this file can never trip its own gate.
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')


def _walk(module, suffixes, skip_tests=False):
    """Yield source files of `module`. `skip_tests` keeps the gates from
    matching the patterns spelled out inside the gates themselves."""
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


@tagged('post_install', '-at_install')
class TestWorkforceStaticGates(TransactionCase):

    # ------------------------------------------------------------------ W16
    def test_nothing_writes_the_shared_context_directly(self):
        """Only `set()` may write wf_context (W16).

        Direct assignment skips normalization, the day-inside-the-week
        invariant, localStorage persistence AND the onChange fan-out — so the
        surface that did it looks correct while every other cockpit silently
        desyncs and a reload throws the change away.
        """
        offenders = []
        scanned = 0
        for module in _CTX_CONSUMERS:
            for path in _walk(module, ('.js',)):
                # the service itself is the one place that owns the state
                if path.endswith('wf_context_service.js'):
                    continue
                scanned += 1
                with open(path, encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        if _RE_CTX_STATE.search(line) or _RE_CTX_ALIAS.search(line):
                            offenders.append('%s:%s: %s' % (path, n, line.strip()))
        self.assertTrue(scanned, 'no JS was scanned — the walk is broken')
        self.assertFalse(offenders, 'W16 violated — use ctxSvc.set({...}):\n%s'
                         % '\n'.join(offenders))

    # ------------------------------------------------------- W1 / W2 / W3
    def test_time_hub_invents_no_hex(self):
        """Every colour in pb_time_hub is a pbim token value or its fallback."""
        tokens_path = os.path.join(
            get_module_path('pb_import_kit'), 'static', 'src', 'scss', 'import_tokens.scss')
        with open(tokens_path, encoding='utf-8') as fh:
            allowed = {h.lower() for h in _RE_TOKEN_HEX.findall(fh.read())}
        # white/black shorthands the token file spells out in long form
        allowed |= {'#fff', '#ffffff', '#000', '#000000'}

        bad = []
        for path in _walk('pb_time_hub', ('.scss', '.js', '.xml', '.css'), skip_tests=True):
            with open(path, encoding='utf-8') as fh:
                for n, line in enumerate(fh, 1):
                    for hexval in _RE_HEX.findall(line):
                        if hexval.lower() not in allowed:
                            bad.append('%s:%s: %s' % (path, n, hexval))
        self.assertFalse(bad, 'W1 violated — never invent a hex:\n%s' % '\n'.join(bad))

    def test_time_hub_has_no_gradients_fontawesome_or_emoji(self):
        bad = []
        for path in _walk('pb_time_hub', ('.scss', '.js', '.xml', '.css', '.py'), skip_tests=True):
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

    # -------------------------------------------------------------- W5 doors
    def test_no_surface_dead_ends_on_target_current(self):
        """W5: a native-form escape uses target:"new" (a dialog you can close),
        never target:"current", which replaces the cockpit with no way back."""
        bad = []
        for module in ('pb_time_hub', 'pb_attendance_flow'):
            for path in _walk(module, ('.js',), skip_tests=True):
                with open(path, encoding='utf-8') as fh:
                    for n, line in enumerate(fh, 1):
                        stripped = line.strip()
                        # the rule is allowed to be NAMED in a comment
                        if stripped.startswith(('//', '*', '/*')):
                            continue
                        if re.search(r'target:\s*["\']current["\']', line):
                            bad.append('%s:%s: %s' % (path, n, stripped))
        self.assertFalse(bad, 'W5 violated — use target:"new":\n%s' % '\n'.join(bad))

    def test_every_hub_lens_is_handed_the_person_door(self):
        """Each lens the hub mounts must receive `onPerson`, or its avatars/rows
        become dead ends the moment they are embedded (W5/WP-6)."""
        tpl = os.path.join(get_module_path('pb_time_hub'),
                           'static', 'src', 'xml', 'time_hub.xml')
        with open(tpl, encoding='utf-8') as fh:
            body = fh.read()
        # Each mounted lens component WITH its attributes, up to the closing />.
        # The group is non-capturing on purpose: re.findall returns the GROUPS
        # when there are any, so a capturing group here would hand back bare
        # component names and the 'onPerson' check below would inspect the wrong
        # string entirely (it did, on the first live run — the gate caught it).
        mounts = re.findall(r'<(?:TimelineLens|AttendanceWeekGrid|PbAttendanceFlow)\b[^>]*?/>',
                            body, re.S)
        self.assertGreaterEqual(len(mounts), 4, 'expected four lens mounts')
        missing = [m.split()[0].lstrip('<') for m in mounts if 'onPerson' not in m]
        self.assertFalse(missing, 'lens mounts without a person door: %s' % missing)
