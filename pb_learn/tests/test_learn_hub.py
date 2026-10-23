# -*- coding: utf-8 -*-
"""RIZE W2 E1 — the Learn mission is a hub, and its seam is a soft registry.

Three of the four promises in this file are ABSENCES, and an absence cannot be
seen by a behaviour test: that the Journey's own client action was not renamed,
that the registry category name is exported so another module can say it, and
that the lens list is resolved once rather than in a getter. Only reading the
source tells those apart from silence (W79), so half of this file is greps with
a paragraph each — the shape `pb_home_hub/tests/test_home_hub.py` set when P8
gave Home the same seam (R83).
"""
import os
import re

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as fh:
        return fh.read()


def _code(src):
    """The file with its COMMENTS removed — both `//` and `/* … */`.

    A word-shaped gate fails on the documentation that explains the rule
    (R118), and the paragraph that stops the next contributor deleting the
    registry has to be able to name it.
    """
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif src.startswith('//', i):
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif src[i] in '"\'`':
            q = src[i]
            out.append(q)
            i += 1
            while i < n and src[i] != q:
                if src[i] == '\\':
                    out.append(src[i:i + 2])
                    i += 2
                    continue
                out.append(src[i])
                i += 1
            out.append(q)
            i += 1
        else:
            out.append(src[i])
            i += 1
    return ''.join(out)


@tagged('post_install', '-at_install')
class TestLearnHub(TransactionCase):

    def test_a_later_module_can_bolt_a_lens_on_without_editing_this_hub(self):
        """The soft registry, and the three pieces that make it one.

        A module that mounts a lens here DEPENDS on this one, so this one can
        never import it back — the registry is what lets the dependency run
        one way only. Three things have to be true together and each fails
        silently on its own: the category name is EXPORTED so the other module
        can name it, the config SPREADS the resolved list, and the resolution
        happens once in `extraLenses()` rather than in a getter — a fresh array
        per render recreates every lens on every keystroke (W21).
        """
        src = _code(_read('static', 'src', 'hub', 'learn_hub.js'))
        self.assertIn('export const LEARN_LENSES = "pb_learn_lens"', src,
                      'the lens registry category must be exported by name')
        self.assertIn('...this.extraLenses()', src,
                      'the config must spread the registered lenses')
        self.assertIn('extraLenses() {', src,
                      'lenses are resolved ONCE in a method, never in a getter')
        self.assertNotIn('get extraLenses', src,
                         'a getter would rebuild the lens list on every render')

    def test_the_config_is_built_once_and_the_key_is_namespaced(self):
        src = _code(_read('static', 'src', 'hub', 'learn_hub.js'))
        self.assertIn('this.config = {', src,
                      'the config is built once in setup, never in a getter')
        self.assertNotIn('get config()', src)
        self.assertIn('key: "learn"', src,
                      'the hub needs its own localStorage namespace')
        shell = _read('..', 'pb_hub', 'static', 'src', 'js', 'hub_shell.js')
        self.assertIn('`pbhub.${key}.lens.v1`', shell)

    def test_the_journey_is_the_first_lens_and_is_not_rebuilt(self):
        """The Journey is MOUNTED, not forked. A copy of it would drift from
        the one the Coach, PayAI and the scenario runner still open."""
        src = _code(_read('static', 'src', 'hub', 'learn_hub.js'))
        self.assertIn('import { LearnJourney } from "@pb_learn/journey/journey"',
                      src, 'the hub must mount the existing Journey component')
        self.assertIn('defaultLens: "lessons"', src)
        self.assertIn('Component: LearnJourney', src)

    def test_both_doors_exist_and_both_are_named(self):
        """A bare tag reaches the shell with no action NAME and anything
        returning through a breadcrumb reads "Unnamed" (W98). And the OLD
        action must still be there: a dozen callers name it by its xml-id."""
        hub = self.env.ref('pb_learn.action_learn_hub')
        self.assertEqual(hub.tag, 'learn_hub')
        self.assertTrue(hub.name)
        journey = self.env.ref('pb_learn.action_learn_journey')
        self.assertEqual(journey.tag, 'learn_journey')

    def test_the_rail_opens_the_hub_and_still_lights_for_the_journey(self):
        """`_openedFromOurs` judges the whole stack by the tags a rail item
        claims (R126), so an item that opens the hub and does not claim the
        Journey's tag would drop the Payobook rail the moment the Coach or
        PayAI opened a lesson."""
        item = self.env.ref('pb_learn.item_learn_journey')
        self.assertEqual(item.action_xmlid, 'pb_learn.action_learn_hub')
        self.assertEqual(item.action_tag, 'learn_hub')
        claimed = [t.strip() for t in (item.match_action_tags or '').split(',')
                   if t.strip()]
        self.assertEqual(claimed, ['learn_hub', 'learn_journey'])

    def test_the_generated_data_file_and_its_author_source_agree(self):
        """`data/learn_sidebar_item.xml` is GENERATED. A hand edit that is not
        also made in the authoring source is erased by the next run, silently
        and a long time later."""
        author = os.path.join(HERE, '..', 'docs', 'tutorial_poc', 'author',
                              'data.js')
        if not os.path.exists(author):
            self.skipTest('the authoring source is not deployed beside the '
                          'module')
        with open(author, encoding='utf-8') as fh:
            src = fh.read()
        leaf = re.search(r'leaf:\s*\{(.*?)\n  \},', src, re.S)
        self.assertTrue(leaf, 'the sidebar leaf block moved in data.js')
        block = leaf.group(1)
        self.assertIn('"pb_learn.action_learn_hub"', block)
        self.assertIn('"learn_hub"', block)
        self.assertIn('"learn_hub,learn_journey"', block)

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JS SyntaxError, and the asset pipeline
        concatenates without ever parsing — so one of these blanks
        `web.assets_backend` for every user with a clean server log (R2)."""
        src = _read('static', 'src', 'hub', 'learn_hub.js')
        self.assertFalse(re.search(r"""["']\s*\n\s*["']""", src),
                         'learn_hub.js has two adjacent string literals')
