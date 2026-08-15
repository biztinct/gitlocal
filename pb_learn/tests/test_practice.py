# -*- coding: utf-8 -*-
"""Practice mode — the free-roam sandbox (LEARNOS Phase 5).

TWO PROMISES, AND THE FIRST ONE IS NOT THE KIND OF PROMISE IT LOOKS LIKE
------------------------------------------------------------------------
1. **The sandbox's server calls are fenced by a TRIPWIRE, not by a proof.**
   The tests below walk the practice surface SYNTACTICALLY: `this.NAME(` call
   edges between methods of one file, and `this.orm.call("literal"` sites
   inside them. That is not containment. A reachability walk over literal
   forms can be defeated deliberately — an aliased `orm`, a model name in a
   constant, `this[k]()` dispatch, a helper handed `this.orm`, `const self =
   this` — and the review round that hardened this file defeated it five ways
   before the hardenings below existed.

   So the claim these tests actually support is narrower and worth having:
   **every ordinary way of growing this code into a server call trips a wire.**
   The wires are (a) the model must be a string literal in an allowlist,
   (b) `this.orm` may appear only as the receiver of its own `.call`, (c) no
   `.call(` in the surface may have any other receiver, (d) `this` may not be
   aliased to a local, and (e) `this[` dispatch is refused. Each of the five
   defeats now fails at least one of them, and each was executed.

   What is NOT claimed: that a determined author cannot write a server call
   the scan cannot see. Nothing short of running the browser can claim that,
   and a test whose docstring over-claims is worse than one that under-claims,
   because the next reader stops looking.

2. **The watermark cannot be switched off.** This one IS structural.
   `practiceShellHTML` contains no branch of any kind, so there is no state
   anywhere in this module that can produce a practice screen without it.
   Asserted on the SOURCE (no conditional in the function, and the mark is in
   the returned expression) and, in `tools/replay_tests.py`, by executing the
   builder for all twenty replicas in both languages. Deleting the mark, or
   building it and not returning it, fails both.

Everything here reads source or the shipped registry, so it executes in the
offline replay harness. The event kinds are asserted twice: as a source fact
here (which runs everywhere) and as a live selection in
`test_scenario::test_12`'s neighbour below, which needs a database.
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

JOURNEY = 'static/src/journey/journey.js'
SCREENS = 'static/src/engine/screens.js'
COACH = 'static/src/coach/coach.js'
PROGRESS = 'models/learn_progress.py'
REGISTRY = 'static/src/anchors.json'

# The two models a learner's own actions may write, and the whole list. Both
# are learner state: where they are and what they opened. Anything else — an
# intent, a payslip, a company — is a record the sandbox has no business
# naming, and a sandbox that named one would not be a sandbox.
PRACTICE_ORM_ALLOWLIST = ('learn.progress', 'learn.event')

# Where the walk starts. Every entry point into the practice view, plus the
# builder the view calls: if a future method is added to this surface it has to
# be reachable from one of these or it is dead code.
PRACTICE_ENTRIES = ('openPractice', 'pNav', 'pExit', '_practiceBody',
                    '_practiceClick', '_practiceCardHTML')

WATERMARK = 'data-coach="rep-watermark"'


def _read(rel):
    with open(os.path.join(get_module_path('pb_learn'), rel), encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(src):
    """Code only. Fifth occurrence of the trap in this repository: this file's
    own docstrings name the call it forbids."""
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'(?<!:)//[^\n]*', '', src)


def _method_bodies(src):
    """{name: body} for the ES class methods in a one-class module file.

    The same shallow parser `test_scenario.py` uses, and it carries the same
    self-check: `test_02b` there and `test_03` here both refuse an empty parse,
    because the failure mode of a shallow parser is a dict that makes every
    assertion above it vacuous.
    """
    out = {}
    lines = src.split('\n')
    start = None
    name = None
    for i, line in enumerate(lines):
        match = re.match(r'^    (?:async )?([A-Za-z_$][\w$]*)\(', line)
        if match and start is None:
            name, start = match.group(1), i
            continue
        if start is not None and line == '    }':
            out[name] = '\n'.join(lines[start:i + 1])
            start = None
    return out


def _reachable(bodies, entries):
    """Every method reachable from `entries` by a literal `this.NAME(` call.

    OVER-APPROXIMATE IN ONE DIRECTION AND BLIND IN ANOTHER, and both halves
    have to be said. It follows a name that merely appears as `this.NAME(`
    whether or not that call is on a path that runs, so it will report a call
    the sandbox would never make. It follows nothing else: not `this[k]()`,
    not `self.foo()` after `const self = this`, not a module-level function.
    Those are the holes the tests below close by REFUSING those forms outright
    rather than by trying to follow them — a scan that tries to chase every
    indirection is a scan that is wrong in a way nobody can see.
    """
    seen = set()
    queue = [e for e in entries if e in bodies]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        for call in re.findall(r'this\.([A-Za-z_$][\w$]*)\(', bodies[name]):
            if call in bodies and call not in seen:
                queue.append(call)
    return seen


@tagged('post_install', '-at_install')
class TestPracticeMode(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journey = _read(JOURNEY)
        cls.screens = _read(SCREENS)
        cls.coach = _read(COACH)
        cls.progress = _read(PROGRESS)
        cls.registry = json.loads(_read(REGISTRY))

    # -- 1. the tripwires around the sandbox's server calls ----------------
    def _surface(self):
        """The practice reachable set, as one blob of code. Shared by every
        tripwire below so they all fence the same region."""
        bodies = _method_bodies(_strip_comments(self.journey))
        for entry in PRACTICE_ENTRIES:
            self.assertIn(entry, bodies,
                          "%s is gone — this walk is now about nothing" % entry)
        reach = _reachable(bodies, PRACTICE_ENTRIES)
        return bodies, reach, '\n'.join(bodies[name] for name in sorted(reach))

    def test_01_every_model_the_surface_names_is_in_the_allowlist(self):
        """WIRE (a). Every `orm.call` in the reachable set names a model, as a
        string literal, from the allowlist.

        Finding NO orm call at all fails too: the practice methods log, so an
        empty scan means the walk is broken rather than the surface clean.
        """
        _bodies, _reach, blob = self._surface()
        models = re.findall(r'orm\.call\(\s*["\']([a-z_.]+)["\']', blob)
        self.assertTrue(
            models,
            "no orm.call found anywhere the practice view can reach. The "
            "practice methods log an event, so an empty scan means the walk "
            "is broken, not that the surface is clean.")
        outside = sorted({m for m in models if m not in PRACTICE_ORM_ALLOWLIST})
        self.assertFalse(
            outside,
            "practice mode can reach %s. Only %s may be written from a sandbox."
            % (outside, list(PRACTICE_ORM_ALLOWLIST)))

    def test_01b_no_call_in_the_surface_has_any_other_receiver(self):
        """WIRES (a) and (c), and the one that closes the ALIAS defeat.

        `const o = this.orm; o.call("learn.intent", …)` contains no
        `orm.call(`, so the model scan above never sees it. Rather than try to
        resolve aliases, every `.call(` in the surface must be spelled
        `this.orm.call(` and must be followed by a quoted model name. That
        refuses the alias, refuses `self.orm.call(` after `const self = this`,
        and refuses a model held in a constant — three defeats, one rule.

        The cost is that no other `.call(` may live here, which is why `pNav`
        uses `Object.hasOwn` rather than `hasOwnProperty.call`. An exemption
        list on a safety scan is where the scan stops meaning anything.
        """
        _bodies, _reach, blob = self._surface()
        bad = []
        for m in re.finditer(r'\.call\(', blob):
            before = blob[max(0, m.start() - 8):m.start()]
            after = blob[m.end():m.end() + 40]
            if not before.endswith('this.orm'):
                bad.append('receiver is %r' % (before[-20:] + '.call('))
            elif not re.match(r'\s*["\'][a-z_.]+["\']', after):
                bad.append('first argument is not a string literal: %r'
                           % after.strip()[:40])
        self.assertFalse(
            bad,
            "the practice surface makes a call the model scan cannot read:\n  "
            + "\n  ".join(bad))

    def test_01c_the_orm_is_never_handed_to_anything(self):
        """WIRE (b), and it closes the HELPER defeat.

        A module-level function given `this.orm` can call whatever it likes,
        outside every method body this file walks. So `this.orm` may appear in
        the surface only as the receiver of its own `.call` — never assigned,
        never passed as an argument, never returned.
        """
        _bodies, _reach, blob = self._surface()
        bad = []
        for m in re.finditer(r'this\.orm', blob):
            after = blob[m.end():m.end() + 6]
            if not after.startswith('.call('):
                bad.append(repr(blob[max(0, m.start() - 30):m.end() + 20]))
        self.assertFalse(
            bad,
            "`this.orm` escapes the practice surface, so what it is used for "
            "is no longer visible here:\n  " + "\n  ".join(bad))

    def test_01d_this_is_never_aliased_and_never_dispatched_dynamically(self):
        """WIRES (d) and (e), and they close the last two defeats.

        `const self = this` makes every later `self.foo()` invisible to a walk
        that follows `this.NAME(`; `this[k]()` makes the TARGET invisible even
        when the call site is not. Neither has a use in six short methods that
        render a replica and log three events, so both are refused rather than
        chased — chasing them is how a scan becomes wrong in a way nobody can
        see.
        """
        _bodies, _reach, blob = self._surface()
        aliases = re.findall(r'=\s*this\s*[;,)]', blob)
        self.assertFalse(
            aliases,
            "`this` is aliased inside the practice surface, so a call through "
            "the alias is invisible to the walk: %s" % aliases)
        dynamic = re.findall(r'this\[[^\]]*\]', blob)
        self.assertFalse(
            dynamic,
            "dynamic dispatch inside the practice surface hides its own "
            "target from the walk: %s" % dynamic)

    def test_02_the_walk_reaches_the_logger_it_claims_to_check(self):
        """The allowlist above is only meaningful if the walk actually leaves
        the entry points. `_log` is one hop out of all three."""
        bodies = _method_bodies(_strip_comments(self.journey))
        reach = _reachable(bodies, PRACTICE_ENTRIES)
        self.assertIn('_log', reach,
                      "the call-graph walk never leaves the practice methods, "
                      "so the allowlist is checking one hop of nothing")

    def test_03_the_method_parser_actually_parsed_something(self):
        bodies = _method_bodies(_strip_comments(self.journey))
        self.assertGreater(len(bodies), 20,
                           "the method parser found %d methods in journey.js — "
                           "it has stopped parsing" % len(bodies))

    # -- 2. the watermark cannot be switched off ---------------------------
    def test_04_the_practice_view_builder_has_no_branch_in_it(self):
        """`practiceShellHTML` is the last function in screens.js and contains
        no conditional of any kind, so the mark cannot be made optional by any
        state the Journey holds. Removing the mark, or wrapping it in a
        ternary, fails here.
        """
        src = _strip_comments(self.screens)
        i = src.find('export function practiceShellHTML(')
        self.assertNotEqual(i, -1, "the practice view builder is gone")
        body = src[i:]
        self.assertIn(WATERMARK, body,
                      "the practice view builder no longer draws the watermark")
        # DECLARING the mark is not drawing it. The first negative control ran
        # was `void mark; return shellHTML(…)`, which leaves the literal in the
        # file and the mark off the screen — the presence check passed and only
        # the executed check in replay_tests.py noticed. The RETURN is what the
        # promise is about, so the return is what is pinned.
        self.assertIn('return mark + shellHTML(', body,
                      "the watermark is built and then not returned")
        for token in ('if (', '?', '&&', '||', 'state'):
            self.assertNotIn(
                token, body,
                "the practice view builder contains %r. It must have no branch "
                "and read no state: the whole promise is that no arrangement of "
                "either can produce a sandbox with no watermark." % token)

    def test_05_the_watermark_is_a_declared_practice_anchor(self):
        """Practice-only by definition — no product screen has a watermark — so
        it lives in the `practice` block and nowhere else. A `product` entry
        would be the Coach claiming it can point at this on a live screen."""
        self.assertIn('rep-watermark', self.registry['practice'])
        for block in ('product', 'pattern', 'foreign'):
            self.assertNotIn('rep-watermark', self.registry.get(block) or {})

    def test_06_the_journey_draws_the_watermark_through_the_builder_only(self):
        """One writer. A second copy of the mark inside the Journey would be a
        second thing to delete, and the deletion nobody notices is the one that
        leaves a practice screen looking like a real one."""
        self.assertIn('practiceShellHTML(', self.journey)
        self.assertNotIn(WATERMARK, self.journey,
                         "the Journey builds its own watermark instead of "
                         "getting it from the view builder")

    # -- 3. the surface is wired at all ------------------------------------
    def test_07_the_three_event_kinds_are_declared(self):
        """An undeclared kind is DROPPED by `log`, silently — so the whole
        signal would be missing with nothing anywhere saying so."""
        for kind in ('practice_open', 'practice_nav', 'practice_exit'):
            self.assertIn("('%s'" % kind, self.progress,
                          "%s is not a declared learn.event kind" % kind)

    def test_08_both_doors_into_the_sandbox_exist(self):
        """The map card and the Coach entry. Two doors, ONE view: the Coach
        opens the same client action with a context key rather than growing a
        sandbox of its own."""
        self.assertIn('data-act="to-practice"', self.journey)
        self.assertIn('ctx.practice', self.journey)
        self.assertIn('data-act="c-practice"', self.coach)
        self.assertIn('additionalContext: { practice: 1 }', self.coach)
        self.assertIn('"c-practice"', self.coach,
                      "c-practice is not in COACH_ACTIONS, so the drawer's own "
                      "delegation will refuse the button it draws")

    def test_09_only_the_menu_is_live_in_the_sandbox(self):
        """`_practiceClick` handles `data-nav` and nothing else. A replica
        control that appeared to work would teach the wrong thing about the
        real one it is a picture of."""
        bodies = _method_bodies(_strip_comments(self.journey))
        body = bodies['_practiceClick']
        self.assertIn('data-nav', body)
        self.assertNotIn('data-coach', body,
                         "_practiceClick reacts to replica controls other than "
                         "the menu")

    def test_10_the_event_kinds_are_live_on_the_model(self):
        """The source assertion above runs offline; this one asks the model,
        because the selection is what `log` validates against."""
        kinds = {k for k, _label in self.env['learn.event']._selection_kind()}
        for kind in ('practice_open', 'practice_nav', 'practice_exit'):
            self.assertIn(kind, kinds)
