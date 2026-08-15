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

JS_DIRS = ('static/src/engine', 'static/src/journey', 'static/src/coach')


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
        for tmpl in ('static/src/journey/journey.xml', 'static/src/coach/coach.xml'):
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
        surfaces = ('static/src/journey/journey.xml', 'static/src/coach/coach.xml')
        missing = []
        for rel in surfaces:
            with open(os.path.join(base, rel), encoding='utf-8') as fh:
                src = fh.read()
            if '#lrn-i-' in src and 'pb_learn.IconSprite' not in src:
                missing.append(rel)
        self.assertFalse(missing,
                         "Templates using the sprite without injecting it: %s" % missing)
