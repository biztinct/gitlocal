# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P3a — WP-1: the embeddability sweep, as a static gate.

Mission Control hosts the seven cockpits as lenses. W17 says that is done with
one prop on the existing component — never a fork, never a copy of its body into
the shell — so the gate that keeps the seam honest is: *does every lens
component still declare `embedded`, default it to false, and actually branch on
it in its template?*

Three things are asserted, and each has a failure mode that ships silently:

  * a MISSING declaration. Every cockpit also declares `"*": true`, so OWL
    accepts an undeclared `embedded` prop without a word — the shell would look
    correct in review and render a doubled title and a second context bar live.
  * a MISSING `defaultProps`. `props.embedded` would then be `undefined`
    standalone, which is falsy and works — until someone writes
    `t-att-class="{ 'x': props.embedded }"` somewhere that needs a boolean.
  * a MISSING template branch: a prop nothing reads is a prop that does nothing.

W17's other half — "standalone rendering must stay byte-identical" — is the
reason each template branch is a `t-if="!props.embedded"` on chrome rather than
a rewrite: with the default false, the standalone DOM is what it was. The live
proof is P3a's T13 (both standalone actions still render their own heroes).

This lives in pb_wf_kit because that is the one module the whole Workforce
program depends on, so the gate runs wherever the redesign is installed without
adding a tests/ package to five unrelated modules (test_p0.py precedent).
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

# component -> (module, js path, xml path). The seven lenses of the shell.
_LENSES = {
    'PbToday': ('pb_today', ('static', 'src', 'js', 'pb_today.js'),
                ('static', 'src', 'xml', 'pb_today.xml')),
    'PbSchedule': ('pb_schedule', ('static', 'src', 'js', 'pb_schedule.js'),
                   ('static', 'src', 'xml', 'pb_schedule.xml')),
    'PbTimeHub': ('pb_time_hub', ('static', 'src', 'js', 'time_hub.js'),
                  ('static', 'src', 'xml', 'time_hub.xml')),
    'PbTimeoff': ('pb_timeoff', ('static', 'src', 'js', 'pb_timeoff.js'),
                  ('static', 'src', 'xml', 'pb_timeoff.xml')),
    'PbOtDesk': ('pb_hr_workforce', ('static', 'src', 'js', 'pb_ot_desk.js'),
                 ('static', 'src', 'xml', 'pb_ot_desk.xml')),
    'PbTrips': ('pb_business_trip', ('static', 'src', 'js', 'pb_trips.js'),
                ('static', 'src', 'xml', 'pb_trips.xml')),
    'PbTeamCockpit': ('pb_team', ('static', 'src', 'js', 'pb_team.js'),
                      ('static', 'src', 'xml', 'pb_team.xml')),
}

# The root-scroller three (P2's warning): standalone their ROOT is the scrollport
# and their `position: sticky` chrome is calibrated to it, so embedded they MUST
# move the scrollport inside or the sticky header hangs in mid-air (W20).
_ROOT_SCROLLERS = {
    'pb_timeoff': (('static', 'src', 'scss', 'pb_timeoff.scss'), 'pbto--embedded'),
    'pb_hr_workforce': (('static', 'src', 'scss', 'pb_ot_desk.scss'), 'pbot--embedded'),
    'pb_team': (('static', 'src', 'scss', 'pb_team.scss'), 'pbteam--embedded'),
}


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
class TestP3aEmbeddability(TransactionCase):

    def test_every_lens_component_declares_the_embedded_prop(self):
        """W17 rule 1: one component, two mount points — declared, not implied.

        `"*": true` means an undeclared prop is accepted in silence, so the
        declaration is the only thing that records the seam's existence.
        """
        checked = 0
        missing = []
        for cls, (module, js, _xml) in _LENSES.items():
            body = _read(module, *js)
            if not body:
                continue
            checked += 1
            if not re.search(r'embedded:\s*\{\s*type:\s*Boolean', body):
                missing.append('%s (%s): no typed `embedded` prop' % (cls, module))
            if not re.search(r'defaultProps\s*=\s*\{[^}]*embedded:\s*false', body):
                missing.append('%s (%s): `embedded` does not default to false — '
                               'standalone must be unchanged' % (cls, module))
        self.assertTrue(checked, 'no lens module is installed')
        self.assertFalse(missing, 'W17 violated:\n%s' % '\n'.join(missing))

    def test_every_lens_template_branches_on_embedded(self):
        """A prop nothing reads is a prop that does nothing.

        Each template must suppress its own title/hero chrome — and ONLY that —
        behind `!props.embedded`.
        """
        checked = 0
        missing = []
        for cls, (module, _js, xml) in _LENSES.items():
            body = _read(module, *xml)
            if not body:
                continue
            checked += 1
            if 'props.embedded' not in body:
                missing.append('%s (%s): the template never reads props.embedded'
                               % (cls, module))
            elif '!props.embedded' not in body:
                missing.append('%s (%s): nothing is suppressed when embedded'
                               % (cls, module))
        self.assertTrue(checked, 'no lens module is installed')
        self.assertFalse(missing, 'W17 violated:\n%s' % '\n'.join(missing))

    def test_the_root_scrollers_move_their_scrollport_inside(self):
        """W20 / P2's warning, as a gate.

        pb_timeoff, pb_ot_desk and pb_team make their ROOT the scroller and pin
        sticky chrome to it. Embedded they are flex children of a canvas that
        does not scroll, so the scroller has to become an inner box — otherwise
        nothing errors, the surface simply renders a header stuck in mid-air.
        """
        checked = 0
        bad = []
        for module, (scss, marker) in _ROOT_SCROLLERS.items():
            body = _read(module, *scss)
            if not body:
                continue
            checked += 1
            block = re.search(
                r'&\.%s\s*\{(.*?)\n    \}' % re.escape(marker), body, re.S)
            if not block:
                bad.append('%s: no `&.%s` block in %s' % (module, marker, scss[-1]))
                continue
            rules = block.group(1)
            # the root must stop scrolling ...
            if 'overflow: hidden' not in rules:
                bad.append('%s: the embedded root still scrolls itself' % module)
            # ... and hand a definite box to an inner scrollport
            if 'overflow: auto' not in rules:
                bad.append('%s: no inner scrollport when embedded' % module)
            if 'min-height: 0' not in rules:
                bad.append('%s: a flex scroll child without `min-height: 0` '
                           'grows to content instead of scrolling (W20)' % module)
            # W39: pb_timeoff and pb_ot_desk both cap their wrap with
            # `max-width` + `margin: 0 auto`, and an auto CROSS-AXIS margin
            # cancels a flex item's stretch — so the wrap sizes to its cap and
            # hangs past a narrower lens. Only pb_team's body has no such cap.
            if module != 'pb_team' and 'width: 100%' not in rules:
                bad.append('%s: the embedded scrollport needs `width: 100%%` — '
                           'its `margin: 0 auto` cancels the flex stretch and it '
                           'sizes to its max-width instead (W39)' % module)
        self.assertTrue(checked, 'none of the root-scroller modules is installed')
        self.assertFalse(bad, 'W20 violated:\n%s' % '\n'.join(bad))

    def test_the_seven_client_actions_are_all_still_registered(self):
        """P3a is a W18 retirement of RAIL ENTRIES, not of actions.

        Embedding a cockpit must not cost it its standalone door: a bookmark, a
        stray doAction and the shell's own Today->Time fallback all still resolve
        these, and P3b/P4 inherit that promise.
        """
        expected = {
            'pb_today.action_pb_today': 'pb_today',
            'pb_schedule.action_pb_schedule': 'pb_schedule',
            'pb_time_hub.action_pb_time_hub': 'pb_time_hub',
            'pb_timeoff.action_pb_timeoff': 'pb_timeoff',
            'pb_hr_workforce.action_pb_ot_desk': 'pb_ot_desk',
            'pb_business_trip.action_pb_trips': 'pb_trips',
            'pb_team.action_pb_team': 'pb_team',
        }
        checked = 0
        for xmlid, tag in expected.items():
            act = self.env.ref(xmlid, raise_if_not_found=False)
            if not act:
                continue
            checked += 1
            self.assertEqual(act._name, 'ir.actions.client', xmlid)
            self.assertEqual(act.tag, tag, '%s must keep its client tag' % xmlid)
        self.assertTrue(checked, 'no cockpit module is installed')

    def test_the_today_hand_off_keeps_its_standalone_fallback(self):
        """P3a §3.5. Embedded, "File correction" is a lens switch; standalone it
        is still the P1b doAction into the Time hub — one method, two routes, and
        the W26 arrival payload written once so they cannot drift.

        It is also the W21.1 rail: the hand-off is a CLICK handler, never a mount
        hook, because it changes host state.
        """
        body = _read('pb_today', 'static', 'src', 'js', 'pb_today.js')
        if not body:
            self.skipTest('pb_today is not installed')
        self.assertIn('onHandOff', body, 'the host callback prop must exist')
        self.assertIn('pb_time_hub.action_pb_time_hub', body,
                      'the standalone doAction fallback must survive')
        self.assertIn('pb_focus', body,
                      'the pinned person is a FILTER over there, not a drawer (W26)')
        # the payload is built once and shared by both routes
        self.assertEqual(
            body.count('pb_lens:'), 1,
            'the arrival payload must be written ONCE and used by both routes')
