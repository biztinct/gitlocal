# -*- coding: utf-8 -*-
"""Guards on the shipped frontend assets.

These check the SOURCE for hazards that only appear after Odoo's asset
pipeline has run — the class of bug you cannot see in development and cannot
see in a code review either.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged

from .common import load_content

# `${...}` followed by a literal space. The minifier eats that space, inside
# template literals included.
BRACE_SPACE_RE = re.compile(r"\$\{[^{}]*\}[ ]+(?=\S)")

# EVERY directory that builds HTML from template literals. `static/src/
# scenario` arrived in LEARNOS Phase 1b and the overlay it holds is mounted
# on every screen in the product — a minifier-eaten space there is visible
# to every user, not only to a learner who opened the Journey.
JS_DIRS = ('static/src/engine', 'static/src/journey', 'static/src/coach',
           'static/src/scenario', 'static/src/live')


@tagged('post_install', '-at_install')
class TestAssets(TransactionCase):

    def _js_files(self):
        base = get_module_path('pb_learn')
        for rel in JS_DIRS:
            folder = os.path.join(base, rel)
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder)):
                if name.endswith('.js'):
                    yield os.path.join(rel, name), os.path.join(folder, name)

    def test_01_no_space_after_a_closing_interpolation(self):
        """Odoo's JS minifier deletes whitespace directly after `}`.

        Measured on UAT: `${esc(T("fullLesson"))} · ${mins} ${esc(T("min"))}`
        arrives in the browser as "Full lesson· 7min". The non-minified bundle
        is correct, so this is invisible in development — which is exactly why
        it needs a test rather than a code-review habit.

        The fix is to put the space in its own interpolation: `${" "}`.
        """
        offenders = []
        for rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            for m in BRACE_SPACE_RE.finditer(src):
                line = src[:m.start()].count('\n') + 1
                offenders.append('%s:%d  %s' % (rel, line, m.group(0).strip()[-40:]))
        self.assertFalse(offenders,
                         "%d place(s) where the minifier will silently delete a space. "
                         "Write `}${\" \"}` instead:\n  %s"
                         % (len(offenders), "\n  ".join(offenders[:25])))

    def test_01c_no_quoted_space_inside_an_interpolation(self):
        """`${" "}` fixes one minifier bug and causes a worse one.

        The quote inside the braces makes rjsmin lose track of the enclosing
        template literal, and it then strips whitespace in the REST of that
        string as if it were code — "13 visits across 4 people. The one"
        shipped as "…people.The one". MEASURED in the served bundle.

        Use the bare identifier SP instead: no quote, so the parser stays
        oriented.
        """
        offenders = []
        for rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            for n, line in enumerate(src.split('\n'), 1):
                if '${"' in line or "${'" in line:
                    if line.strip().startswith('*') or line.strip().startswith('//'):
                        continue
                    offenders.append('%s:%d %s' % (rel, n, line.strip()[:70]))
        self.assertFalse(offenders,
                         "Quoted string inside a template interpolation — use SP:\n  "
                         + "\n  ".join(offenders))

    def test_01b_no_sass_hostile_min_max(self):
        """`min(400px, calc(100vw - 44px))` takes the WHOLE bundle down.

        Bootstrap's Sass min()/max() intercept the CSS function and fail with
        "calc(...) is not a number for min". Odoo then keeps serving the
        PREVIOUS stylesheet, so the only symptom is that a new screen looks
        unstyled — no error in the console, nothing in the page. It is in this
        repo's ledger and it still caught this module, which is the argument
        for a test rather than a note.

        The fix is a CSS custom property: Sass passes those through verbatim.
        """
        base = get_module_path('pb_learn')
        pattern = re.compile(r'(?<!var\()\b(min|max)\(\s*[^;]*calc\(', re.I)
        offenders = []
        for root, _dirs, files in os.walk(os.path.join(base, 'static/src')):
            for name in files:
                if not name.endswith('.scss'):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding='utf-8') as fh:
                    src = fh.read()
                # Comments explain the hazard by quoting it, so scanning them
                # makes the guard fail on its own documentation — the same
                # false positive the anchor lint hit. Blank them out, keeping
                # the line count so the reported line number is still right.
                src = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'),
                             src, flags=re.S)
                src = re.sub(r'//[^\n]*', '', src)
                for n, line in enumerate(src.split('\n'), 1):
                    # A declaration OF a custom property is exactly the fix,
                    # so only flag ordinary properties.
                    if line.strip().startswith('--'):
                        continue
                    if pattern.search(line):
                        offenders.append('%s:%d %s' % (name, n, line.strip()[:70]))
        self.assertFalse(offenders,
                         "min()/max() wrapping a calc() in a normal property. This "
                         "silently kills the whole asset bundle:\n  " + "\n  ".join(offenders))

    def test_02_every_icon_referenced_exists_in_the_sprite(self):
        """A missing symbol renders as nothing at all — no error, no fallback,
        just a label with a gap where its icon should be."""
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/journey/icons.xml'), encoding='utf-8') as fh:
            sprite = fh.read()
        available = set(re.findall(r'symbol id="lrn-i-([a-z0-9-]+)"', sprite))
        self.assertTrue(available, "the icon sprite is empty")

        used = set()
        for _rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            used |= set(re.findall(r'\bic\("([a-z0-9-]+)"', src))
            # block(icon, ...), kpiTile(icon, ...) and the other helpers that
            # take a bare name. Each one added here is a name the direct
            # `ic("…")` scan cannot see, and a missed one renders as a gap.
            used |= set(re.findall(r'\bblock\("([a-z0-9-]+)"', src))
            used |= set(re.findall(r'\bkpiTile\("([a-z0-9-]+)"', src))
        for tmpl in ('static/src/journey/journey.xml', 'static/src/coach/coach.xml',
                     'static/src/scenario/scenario_overlay.xml'):
            with open(os.path.join(base, tmpl), encoding='utf-8') as fh:
                used |= set(re.findall(r'href="#lrn-i-([a-z0-9-]+)"', fh.read()))

        missing = sorted(used - available)
        self.assertFalse(missing, "Icons referenced but not in the sprite: %s" % missing)

    def test_02b_every_icon_a_RECORD_names_exists_in_the_sprite(self):
        """The regex scan above cannot see these at all.

        A station's icon is a content value chosen by an author, not a literal
        in the source — so a typo in it passes every source-level check and
        renders as a card with a hole where its icon should be. Read from the
        content plane instead of guessing at the call sites.
        """
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/journey/icons.xml'), encoding='utf-8') as fh:
            available = set(re.findall(r'symbol id="lrn-i-([a-z0-9-]+)"', fh.read()))
        content = load_content()
        named = {s['icon'] for s in content['stations'] if s['icon']}
        named |= {m['icon'] for m in content['missions'] if m['icon']}
        # A SCENARIO's icon is the same kind of value for the same reason: an
        # author chose it, no source literal carries it, and a typo renders as a
        # card with a hole where its icon should be.
        named |= {c['icon'] for c in (content.get('scenarios') or []) if c['icon']}
        missing = sorted(named - available)
        self.assertFalse(missing,
                         "Content names icons the sprite does not have: %s" % missing)

    def test_03_every_surface_carries_its_own_icon_sprite(self):
        """A surface that uses the sprite must inject it.

        The Coach mounts on EVERY screen, including ones where the Journey is
        not rendered — and there it drew a blank circle with no icon, because
        it was relying on the Journey's copy of the sprite. Symptom: a launcher
        that looks broken, no error anywhere.
        """
        base = get_module_path('pb_learn')
        surfaces = ('static/src/journey/journey.xml', 'static/src/coach/coach.xml',
                    'static/src/scenario/scenario_overlay.xml')
        missing = []
        for rel in surfaces:
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                src = fh.read()
            if '#lrn-i-' in src and 'pb_learn.IconSprite' not in src:
                missing.append(rel)
        self.assertFalse(missing,
                         "Templates using the sprite without injecting it: %s" % missing)

    def test_04_an_authored_body_is_inserted_through_gtx(self):
        """`gtx` is the ONE raw-insertion wrapper in this module, and "are all
        raw positions covered" is meant to be answerable by grepping for it.

        Every surface that prints an authored BODY — a lesson step, a mission
        step's detail, a scenario card, a live capstone's card — has to go
        through it, or that surface prints its `<b>` as text and reaches none
        of the glossary hovercards the same sentence gets everywhere else.
        The live capstone shipped `esc(tx(step.detail))` from Phase B until
        LEARNOS Phase 5; it was on the ledger as an accepted nit for two
        phases, which is exactly how long an accepted nit survives without a
        test under it.

        A TITLE is not a body and stays escaped — journey.js escapes
        `step.instruction` and glosses `step.detail`, and this asserts the same
        pair rather than a blanket rule.
        """
        base = get_module_path('pb_learn')
        pairs = (
            ('static/src/journey/journey.js', 'gtx(step.detail)'),
            ('static/src/journey/journey.js', 'gtx(step.body)'),
            ('static/src/live/live_mission.js', 'gtx(step.detail)'),
            ('static/src/scenario/scenario_overlay.js', 'gtx(step.body)'),
        )
        for rel, want in pairs:
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                src = fh.read()
            self.assertIn(want, src, "%s no longer inserts %s" % (rel, want))
        with open(os.path.join(base, 'static/src/live/live_mission.js'),
                  encoding='utf-8') as fh:
            live = fh.read()
        self.assertNotIn('esc(tx(step.detail))', live,
                         "the live card escapes an authored body again")

    def test_05_every_keydown_listener_is_document_capture(self):
        """"document, not window" is necessary and NOT sufficient.

        Odoo's hotkey service stops propagation at document-BUBBLE, so a
        bubble listener on `document` is silently dead in real Chrome while a
        synthetic dispatch in a test still runs it. Measured on the Phase 2+3
        deploy — the welcome card's Escape — and `first_login.js` has bound
        capture ever since while three other surfaces did not. The rule is
        now a test rather than a paragraph in the ledger, which is what this
        repository does with a convention it has broken three times.

        The REMOVAL has to carry the flag too: `removeEventListener` matches on
        the phase, so a capture listener removed without it is never removed.
        """
        base = get_module_path('pb_learn')
        bad = []
        for rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
            src = re.sub(r'(?<!:)//[^\n]*', '', src)
            if 'window.addEventListener("keydown"' in src:
                bad.append('%s binds keydown on window' % rel)
            for verb in ('addEventListener', 'removeEventListener'):
                # A HANDLER BODY CONTAINS SEMICOLONS AND PARENTHESES, so the
                # call's own closing bracket has to be FOUND rather than
                # guessed at: the first version stopped at the first `;`,
                # which for the glossary's inline arrow function is inside the
                # handler, and reported a capture listener as a bubble one.
                needle = 'document.%s("keydown"' % verb
                at = src.find(needle)
                while at != -1:
                    depth, i = 0, at + needle.index('(')
                    while i < len(src):
                        if src[i] == '(':
                            depth += 1
                        elif src[i] == ')':
                            depth -= 1
                            if depth == 0:
                                break
                        i += 1
                    tail = src[max(at, i - 8):i]
                    if 'true' not in tail:
                        bad.append('%s %s("keydown") is not capture phase'
                                   % (rel, verb))
                    at = src.find(needle, i)
        self.assertFalse(bad, "\n  ".join(bad))
        # And the scan found something: four surfaces bind this key.
        binds = 0
        for _rel, path in self._js_files():
            with open(path, encoding='utf-8') as fh:
                binds += fh.read().count('document.addEventListener("keydown"')
        self.assertGreaterEqual(binds, 4,
                                "only %d keydown listeners found — the scan has "
                                "stopped finding them" % binds)

    def test_06_only_a_closing_branch_swallows_the_key(self):
        """A transient layer that closes on a key must swallow it, or one
        Escape closes the hovercard AND exits the lesson. The converse matters
        as much: a branch that only MOVES the reader — the arrow keys — must
        leave the key alone, or the walkthrough starts eating keystrokes the
        product needs.
        """
        base = get_module_path('pb_learn')
        for rel in ('static/src/journey/journey.js',
                    'static/src/scenario/scenario_overlay.js',
                    'static/src/coach/coach.js'):
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                src = re.sub(r'/\*.*?\*/', '', fh.read(), flags=re.S)
            src = re.sub(r'(?<!:)//[^\n]*', '', src)
            key = src.split('_onKey(ev)', 1)[1].split('\n    }', 1)[0]
            self.assertIn('glossaryOpen()', key,
                          "%s acts on Escape without standing down for an open "
                          "hovercard" % rel)
            self.assertIn('stopPropagation', key,
                          "%s closes on a key without swallowing it" % rel)
            # Every stopPropagation is in a branch that also closes something.
            for chunk in key.split('stopPropagation')[1:]:
                head = chunk[:220]
                self.assertTrue(
                    any(w in head for w in ('Exit(', 'exitLesson(', 'onLeave(',
                                            'close(')),
                    "%s swallows a key in a branch that closes nothing:\n%s"
                    % (rel, head[:120]))

    def test_06b_the_hovercard_swallows_the_key_from_its_own_siblings(self):
        """The other half of the ladder, and the half that was WRONG on live.

        The surfaces stand down for an open card (test_06). That covers the
        order where a surface's listener runs first. In the other order the
        card's own listener runs first, hides the card, and every surface
        listener runs AFTERWARDS on the same `document` node — where
        `stopPropagation()` is a no-op — and each one asks `glossaryOpen()`,
        gets False because the card is already gone, and closes. One Escape
        took the hovercard and the Coach on apex.

        `stopImmediatePropagation` is the only call that stops a sibling
        listener on the same node, so the card's handler owes that one
        specifically. Asserted as an absence too: a bare `stopPropagation()`
        here reads as protection and is not.
        """
        base = get_module_path('pb_learn')
        with open(os.path.join(base, 'static/src/engine/glossary.js'),
                  encoding='utf-8') as fh:
            src = fh.read()
        src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
        src = re.sub(r'(?<!:)//[^\n]*', '', src)
        handler = src.split('addEventListener("keydown"', 1)
        self.assertEqual(len(handler), 2,
                         "the hovercard no longer binds a key — this ladder is "
                         "about nothing")
        body = handler[1].split('}, true);', 1)[0]
        self.assertIn('stopImmediatePropagation', body,
                      "the hovercard's Escape does not stop the surface "
                      "listeners beside it on document — one Escape will take "
                      "both rungs of the ladder")
        self.assertNotIn('ev.stopPropagation()', body,
                         "a bare stopPropagation() here protects nothing: "
                         "every other Escape listener is on the same node")
