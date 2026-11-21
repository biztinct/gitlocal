# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P3b — T2 for the shared ⌘K palette (`<WfCommandPalette/>`).

The palette is a KIT component (W6): Mission Control mounts it, but so may any
future workspace, so its invariants belong here rather than in pb_mission's
gates. Four of them, and every one has a failure mode that ships silently:

  * it must render through the OVERLAY, not inside a host. A palette that lives
    in the workspace has to out-stack a lens's `position: fixed` modal, which
    means shell chrome above 1050 — the fight W37 exists to prevent.
  * the flat row list and the grouped render must be THE SAME list. Sorting them
    separately is how a keyboard highlight starts jumping between sections
    (the Formula Studio palette's own W99 fix, imported as a rule).
  * `name_search` must use Odoo 19's `domain` kwarg, and the catch must narrow
    the control only for an AccessError (W40 — the bug that deleted the context
    bar's person search for three phases lived in exactly this call).
  * nothing may write from a lifecycle hook (W21): the palette's only mount-time
    work is focusing its input.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


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
class TestP3bCommandPalette(TransactionCase):

    def _js(self):
        return _read('pb_wf_kit', 'static', 'src', 'js', 'wf_command_palette.js')

    def _xml(self):
        return _read('pb_wf_kit', 'static', 'src', 'xml', 'wf_kit.xml')

    def _scss(self):
        return _read('pb_wf_kit', 'static', 'src', 'scss', 'wf_kit.scss')

    def test_the_component_exists_and_is_in_the_backend_bundle(self):
        self.assertIn('export class WfCommandPalette', self._js())
        manifest = _read('pb_wf_kit', '__manifest__.py')
        self.assertIn('wf_command_palette.js', manifest,
                      'a component nobody bundles is a component nobody has')
        self.assertIn('pb_wf_kit.WfCommandPalette', self._xml())

    def test_the_palette_owns_no_position_of_its_own_inside_a_host(self):
        """It is mounted by the overlay service, so its scrim is `position:
        fixed` against the VIEWPORT and it needs no z-index at all — the overlay
        container already sits above everything the workspace can produce."""
        scss = self._scss()
        block = re.search(r'\.wfcp-scrim \{(.*?)\n\}', scss, re.S)
        self.assertTrue(block, 'no .wfcp-scrim block in wf_kit.scss')
        self.assertIn('position: fixed', block.group(1))
        self.assertNotIn('z-index', block.group(1),
                         'the overlay container already provides the stacking; '
                         'a z-index here would be a number nobody can reason about')

    def test_the_keyboard_index_and_the_render_share_one_list(self):
        """`groups` must be DERIVED from `rows`, carrying each row's flat index.
        Two independent orderings is how the highlight starts jumping between
        sections while the arrow keys walk a different sequence."""
        js = self._js()
        block = re.search(r'get groups\(\) \{(.*?)\n    \}', js, re.S)
        self.assertTrue(block, 'no groups getter found')
        self.assertIn('this.rows', block.group(1),
                      'groups must be built from rows, not rebuilt beside it')
        self.assertIn('idx', block.group(1),
                      'each rendered row must carry its FLAT index')
        self.assertRegex(js, r'get count\(\) \{ return this\.rows\.length; \}')

    def test_enter_runs_the_row_the_arrows_highlighted(self):
        js = self._js()
        self.assertRegex(js, re.compile(
            r'ev\.key === "Enter".*?this\.rows\[this\.state\.active\]', re.S))
        for key in ('ArrowDown', 'ArrowUp', 'Escape'):
            self.assertIn('ev.key === "%s"' % key, js)

    def test_the_accent_hint_is_the_empty_state_not_an_annotation(self):
        """§2a, measured live: this database has NO `unaccent`, so "Bui Anh"
        matches nothing while "Bùi Anh" matches. Folding client-side would lie
        about what the server can find, so the palette SAYS so instead.

        But it is the EMPTY STATE, not a note on the side. The first version
        fired on "no people matched", so typing "sched" — four good lens and
        action hits on screen — printed "Nobody matched. Names are matched
        exactly…" underneath them. A hint that contradicts the list above it is
        worse than no hint. One empty state, and only when the list is empty:
        `!this.count` in the getter, and the generic line stands down for it.
        """
        js, xml = self._js(), self._xml()
        block = re.search(r'get showAccentHint\(\) \{(.*?)\n    \}', js, re.S)
        self.assertTrue(block, 'no showAccentHint getter')
        body = block.group(1)
        for needle in ('searched', 'searching', 'people.length', '!this.count'):
            self.assertIn(needle, body)
        self.assertIn('showAccentHint', xml, 'the hint must be rendered')
        self.assertIn('!count and !state.searching and !showAccentHint', xml,
                      'the generic empty state must stand down for the hint')

    def test_nothing_writes_from_a_lifecycle_hook(self):
        """W21: the palette's only mount-time work is focusing its input. Every
        outcome — a lens, a person, an action — runs from a click or an Enter."""
        js = self._js()
        block = re.search(r'onMounted\((.*?)\}\);', js, re.S)
        self.assertTrue(block, 'no onMounted found')
        self.assertIn('focus()', block.group(1))
        for writer in ('onPickLens', 'onPickPerson', 'onRunAction', '_remember'):
            self.assertNotIn(writer, block.group(1),
                             '%s must not run from a mount hook' % writer)
        # …and `run` is the single funnel, which records the recent and closes
        self.assertRegex(js, re.compile(
            r'run\(row\) \{\s*this\._remember\(row\);', re.S))

    def test_recents_are_capped_and_survive_private_mode(self):
        js = self._js()
        self.assertIn('const RECENTS_KEY = "pbwf.palette.v1"', js,
                      'the handover names this key')
        self.assertIn('const RECENTS_MAX = 5', js)
        self.assertEqual(js.count('} catch { return []; }')
                         + js.count('} catch { /* private mode */ }'), 2,
                         'both localStorage doors must survive a throwing store')

    def test_the_palette_and_the_context_bar_agree_on_the_typeahead(self):
        """One person-search behaviour in Workforce, not two: same debounce,
        same limit, same model, same call shape."""
        palette = self._js()
        bar = _read('pb_wf_kit', 'static', 'src', 'js', 'wf_context_bar.js')
        for needle in ('const PERSON_LIMIT = 8', 'const TYPEAHEAD_MS = 220'):
            self.assertIn(needle, palette, needle)
            self.assertIn(needle, bar, needle)
