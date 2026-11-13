# -*- coding: utf-8 -*-
"""JOURNEY J7 — the two legibility defects reported against the live shared board.

Both are on the SHARED two-lane `MappingCanvas`, which is why they land here as
one file rather than as a second copy of J6's transform-board round: five
adapters mount that component, and a fix stated in it is a fix all five inherit.

  * **D1 — the dock chip covered the first card in the column.** The chip was
    placed at the CLAMP BAND edge, and the clamp band is a line INSIDE the
    column's scrollport: the exact place the first and last visible card sit.
    Measured live on abm before the fix: 167.9 x 23.8px of "Last Working Day"
    behind "4 hidden by filter above", and four chips over five cards in the
    plain scrolled state.
  * **D2 — component names truncated with no way to read them.** The measured
    cause was not `white-space: nowrap` on its own: a 142px "Contract component"
    source pill shares the name's flex line on a 252px label row, so the name
    was being offered 104px of it and 23 of the right column's 73 cards
    ellipsised. MF13/MF26, a third time, in its original form.

Everything here is a SOURCE assertion or an ORM fact, for MJ12's reason one step
further out: J7 moves rects, and the sweep that measures rects is the one thing
this codebase has already been shown to be blind in (MJ30). The rules that make
the defects impossible are stated in a stylesheet and in a pure kernel, and both
can be pinned exactly. MJ25's warning applies throughout — every anchor below is
the most specific string that can occur once.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip_js_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^\s*//.*$', '', src, flags=re.M)


def _strip_scss_comments(src):
    return re.sub(r'/\*.*?\*/', '', src, flags=re.S)


def _rule(scss, selector):
    """The declaration block of `selector`, or ''. Anchored on the WHOLE
    selector followed by `{`, so `.mc-item-label` cannot match
    `.mc-item-label > span` (MJ25 — an ambiguous anchor is the oracle lying)."""
    m = re.search(re.escape(selector) + r'\s*\{(.*?)\}', scss, flags=re.S)
    return m.group(1) if m else ''


@tagged('post_install', '-at_install')
class TestJourneyJ7Legibility(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.canvas_js = _strip_js_comments(_src(
            'pb_formula_studio', 'static', 'src', 'js', 'mapping',
            'mapping_canvas.js'))
        cls.geom_js = _strip_js_comments(_src(
            'pb_formula_studio', 'static', 'src', 'js', 'mapping',
            'mapping_geometry.js'))
        cls.tfb_js = _strip_js_comments(_src(
            'pb_formula_studio', 'static', 'src', 'js', 'mapping',
            'transform_flow_board.js'))
        cls.scss = _strip_scss_comments(_src(
            'pb_formula_studio', 'static', 'src', 'scss', 'mapping.scss'))
        cls.tfb_scss = _strip_scss_comments(_src(
            'pb_formula_studio', 'static', 'src', 'scss', 'transform_flow.scss'))
        # inside the module (so it ships and can be asserted on the server)
        # but outside `static/`, so no asset bundle ever loads an IIFE.
        cls.sweep = _src('pb_formula_studio', 'tools',
                         'mapping_overlap_sweep.js')

    # ================================================== D1 — the dock strip

    def test_01_the_strip_is_a_border_because_padding_scrolls_away(self):
        """A reservation that scrolls away is not a reservation.

        This is the whole of D1's design in one assertion. Padding on a
        scroller is INSIDE the scrollport: at rest it holds the first card
        down, and the moment the column moves — which is the only state in
        which an "N above" chip exists at all — the cards scroll straight
        through it. A border is outside the scrollport and no content can
        ever be painted in it, at any offset.
        """
        body = _rule(self.scss, '.mapping-canvas .mc-col-body')
        self.assertTrue(body, 'the column scroller must still be styled here')
        self.assertIn('border-top: 30px solid transparent', body)
        self.assertIn('border-bottom: 30px solid transparent', body)
        self.assertIn('overflow-y: auto', body)
        # and the strip is unconditional: a `.has-dock` variant would make the
        # placement feed back into its own predicate (chip -> cards move ->
        # different cards outside the band -> different chip).
        self.assertNotIn('has-dock', self.scss)

    def test_02_the_stylesheet_and_the_kernel_agree_on_the_strip(self):
        """Two files own one number, so the number is asserted in both.

        MJ30's shape: a component computing coordinates for a child it does not
        own. The chip's Y comes from `DOCK_RAIL` in the kernel; the space it
        hangs in comes from a border in the stylesheet. If they disagree the
        chip is outside its own strip and D1 is back.
        """
        m = re.search(r'export const DOCK_RAIL = (\d+);', self.geom_js)
        self.assertTrue(m, 'DOCK_RAIL must be a declared constant')
        rail = int(m.group(1))
        body = _rule(self.scss, '.mapping-canvas .mc-col-body')
        self.assertIn('border-top: %dpx solid transparent' % rail, body)
        self.assertIn('border-bottom: %dpx solid transparent' % rail, body)
        # a dock chip measures ~24px live; the strip must hold one with air
        self.assertGreaterEqual(rail, 28)

    def test_03_the_chip_hangs_on_the_strip_and_not_on_the_clamp_band(self):
        """The defect was that these were ONE number. They are now two.

        `bandTop`/`bandBot` are where a wire parks; `railTop`/`railBot` are
        where a chip hangs. The dock builder must read the second pair — if it
        ever reads the first again, the chip is back on the first card.
        """
        self.assertIn('dockAnchors', self.geom_js)
        self.assertIn('railTop, railBot } = dockAnchors(', self.canvas_js)
        m = re.search(r'return \{ \.\.\.d, x: col\.edge, y: ([^}]+)\};',
                      self.canvas_js)
        self.assertTrue(m, 'the dock chip must still be placed in _recompute')
        placement = m.group(1)
        self.assertIn('col.railTop', placement)
        self.assertIn('col.railBot', placement)
        self.assertNotIn('bandTop', placement)
        self.assertNotIn('bandBot', placement)

    def test_04_the_band_itself_was_not_moved(self):
        """J7 moves cards, never wires.

        A transparent border does not change a border box, and the band is
        measured from `getBoundingClientRect`. So the wire arithmetic is
        untouched BY CONSTRUCTION, and that is worth an assertion of its own:
        the day somebody "tidies" `BAND` into the rail, every wire on five
        boards moves 22px and MJ30 happens again.
        """
        self.assertIn('const BAND = 8;', self.canvas_js)
        self.assertIn('const bandTop = br.top - rb.top + BAND;', self.canvas_js)
        self.assertIn('const bandBot = br.bottom - rb.top - BAND;', self.canvas_js)

    def test_05_a_chip_is_repositioned_when_the_layout_moves_it(self):
        """The second cause, and the one that made D1 intermittent.

        `_sig` carried a dock's key, count and filtered count and NOT its
        coordinates, so a pure layout shift never reassigned `ui.docks`.
        Turning a filter on grows the column head by the "N wires hidden by
        this filter" row and moves the body ~31px down; the chip stayed where
        the previous layout had put it. Measured live on abm at exactly that:
        483.6px against a true 514.4px.
        """
        m = re.search(r'docks\.map\(\(d\) => `([^`]*)`\s*\+ `([^`]*)`\)',
                      self.canvas_js)
        self.assertTrue(m, 'the dock signature must still be built here')
        sig = m.group(1) + m.group(2)
        self.assertIn('${d.count}', sig)
        self.assertIn('${d.filtered}', sig)
        self.assertIn('Math.round(d.x)', sig)
        self.assertIn('Math.round(d.y)', sig)

    def test_06_the_chip_keeps_its_verbs(self):
        """MJ39's family: do not delete live-tested behaviour while re-placing it.

        CR21/F1 — the chip is the way back to a wire a filter is hiding. It
        looks up across BOTH sets (drawn and suppressed) and `jumpTo` clears
        the filter for the side it was pressed on.
        """
        self.assertIn('clickDock(d) {', self.canvas_js)
        click = self.canvas_js.split('clickDock(d) {')[1].split('\n    }')[0]
        self.assertIn('this.ui.geom.find', click)
        self.assertIn('this.ui.supp.find', click)
        self.assertIn('this.jumpTo(d.side, g)', click)
        jump = self.canvas_js.split('jumpTo(side, g) {')[1].split('\n    }')[0]
        self.assertIn('this.clearFilters(side)', jump)

    def test_07_the_four_chip_variants_are_centred_on_the_strip(self):
        """All four, because D1 was reported on one and true of all of them.

        The old pair hung the chip just below the top band edge and just above
        the bottom one — deliberately INTO the column, which is why it landed
        on a card. Centring is what makes "inside the strip" a fact of the
        stylesheet rather than a coincidence of two offsets.
        """
        for side in ('left', 'right'):
            for way in ('up', 'down'):
                rule = _rule(self.scss,
                             '.mapping-canvas .mc-dock.%s.%s' % (side, way))
                self.assertTrue(rule, '%s.%s must still be placed' % (side, way))
                self.assertIn('-50%', rule)
                self.assertNotIn('2px', rule)

    # ============================================ D2 — the whole name, on the card

    def test_08_the_name_no_longer_shares_its_line_when_it_cannot_fit(self):
        """MF13/MF26's rule, applied to the pill that actually caused it.

        `flex-wrap: wrap` is the fix and it works because flex wraps on BASE
        sizes before it shrinks anything: a name whose natural width plus its
        chips exceeds the row sends the chips to the next line and keeps the
        whole row, instead of being squeezed to 104px beside a 142px pill.
        """
        label = _rule(self.scss, '.mapping-canvas .mc-item-label')
        self.assertIn('flex-wrap: wrap', label)
        self.assertNotIn('white-space: nowrap', label)

    def test_09_the_name_may_take_two_lines_and_never_break_mid_word(self):
        """`break-word`, never `anywhere` — the road back to MF13.

        `overflow-wrap: anywhere` feeds into the min-content contribution, so a
        flex item carrying it can be shrunk to one character and still "fit".
        That is the one-character label, exactly, arriving by a new route.
        """
        span = _rule(self.scss, '.mapping-canvas .mc-item-label > span:first-child')
        self.assertIn('-webkit-line-clamp: 2', span)
        self.assertIn('-webkit-box-orient: vertical', span)
        self.assertIn('white-space: normal', span)
        self.assertIn('overflow-wrap: break-word', span)
        self.assertNotIn('overflow-wrap: anywhere', span)
        self.assertIn('min-width: 0', span)

    def test_10_the_residual_name_is_measured_never_guessed(self):
        """"Does this text fit" is not a property of the string.

        It depends on the font, on the chips beside it and on the column's
        width, and every character-count heuristic is wrong on the one name
        somebody complains about. The pass asks the browser the same question
        the browser answered when it clamped.
        """
        self.assertIn('_clipPass() {', self.canvas_js)
        pass_src = self.canvas_js.split('_clipPass() {')[1].split('\n    }\n')[0]
        self.assertIn('span.scrollHeight > span.clientHeight + 1', pass_src)
        self.assertIn("classList.toggle(\"is-clipped\", clipped)", pass_src)
        self.assertIn('span.title = span.textContent', pass_src)
        self.assertIn("removeAttribute(\"title\")", pass_src)
        # not on the scroll path: scrolling cannot change whether a name fits
        self.assertIn('if (this._clipDirty) { this._clipDirty = false; '
                      'this._clipPass(); }', self.canvas_js)

    def test_11_a_clamped_name_says_that_it_is_clamped(self):
        """MJ34 — an affordance nobody can find does not exist.

        A bare `title=` is invisible until you happen to rest a pointer on it.
        The clamped name carries a help cursor and a dotted underline, which is
        the conventional "there is more of this" marker, and it appears on
        exactly the cards that lost a word.
        """
        clip = _rule(self.scss, '.mapping-canvas .mc-item-label > span.is-clipped')
        self.assertIn('cursor: help', clip)
        self.assertIn('underline dotted', clip)

    def test_12_the_transform_board_inherits_the_same_rule(self):
        """Stated twice on purpose: the chrome is NOT shared.

        `.tfb-item-l` is the transform board's own class and `.mc-item-label`
        is the canvas', with different chips inside each. A shared helper would
        have to know both, which is the fork this programme keeps refusing —
        pointed the other way.
        """
        label = _rule(self.tfb_scss, '.tfb .tfb-item-l')
        self.assertIn('flex-wrap: wrap', label)
        span = _rule(self.tfb_scss, '.tfb .tfb-item-l > span:first-child')
        self.assertIn('-webkit-line-clamp: 2', span)
        self.assertIn('overflow-wrap: break-word', span)
        self.assertNotIn('white-space: nowrap', span)
        self.assertIn('_clipPass() {', self.tfb_js)
        self.assertIn('.tfb-item-l > span', self.tfb_js)

    # ================================================== the sweep that missed it

    def test_13_the_sweep_classifies_an_overlay_by_name_not_by_z_index(self):
        """Why five phases of sweeps never saw D1.

        MJ7 taught the sweep to skip pairs that do not share a layer, because a
        dropdown is SUPPOSED to cover what is under it. "Layer" was implemented
        as the nearest positioned ancestor's `z-index` — and `.mc-docks` is 4
        where `.mc-cols` is 2, so every dock-versus-card pair was skipped as an
        intentional overlay. A dock chip is not an overlay: nobody opened it,
        nothing dismisses it, there is no scrim under it. Its z-index is a
        PAINTING decision, and a painting decision is not permission to
        occlude.

        So the list of overlays is now NAMED and closed, and the dock-versus-
        card pair is additionally asserted on its own, so that a future
        refactor of `layerOf` cannot quietly stop testing it.
        """
        self.assertIn('const OVERLAY = [', self.sweep)
        overlays = self.sweep.split('const OVERLAY = [')[1].split('].join')[0]
        for opened in ('.mc-menu', '.mc-tf-pop', '.mc-drawhint', '.mc-reveal'):
            self.assertIn(opened, overlays)
        for furniture in ('.mc-dock', '.mc-item', '.mc-hub', '.tfb-item'):
            self.assertNotIn('"%s"' % furniture, overlays)
        self.assertNotIn('zIndex', self.sweep)
        self.assertIn('dockOverCard', self.sweep)
        # MJ12 is kept, because it was paid for
        self.assertIn('instanceof SVGElement', self.sweep)

    def test_13b_the_clip_box_is_derived_from_the_element_not_named(self):
        """The second way this sweep lied, found in the same run.

        MJ7's clip box was written as `.mc-board`, and `.mc-board` is not what
        clips a CARD — `.mc-col-body` is, and its scrollport is its PADDING
        box. A card at a column edge reports a layout rect that runs past the
        scrollport, so it "overlapped" the filter chips above it and its own
        dock chip while being invisible in both places. J7's 30px strip makes
        that gap exactly the band the chips live in, so a border-box sweep
        would have reported every chip as covering a card forever.

        The rule replaces the name: walk the ancestors, intersect with the
        padding box of every one that is not `overflow: visible`. And keep
        MJ7's own disproof — ask `elementFromPoint` what is actually painted.
        """
        self.assertIn('for (let p = el.parentElement; p; p = p.parentElement)',
                      self.sweep)
        self.assertIn('borderTopWidth', self.sweep)
        self.assertIn('borderBottomWidth', self.sweep)
        self.assertIn('document.elementFromPoint', self.sweep)
        self.assertIn('paintedOver', self.sweep)
        self.assertNotIn('clipBoxes', self.sweep)

    # ============================================ this phase writes nothing

    def test_14_no_new_write_path_was_opened(self):
        """J7 is presentation only, and says so where it can be checked.

        Neither board gained an ORM call, and the canvas still reaches the
        outside world only through its callback props.
        """
        self.assertNotIn('this.orm', self.canvas_js)
        self.assertNotIn('rpc(', self.canvas_js)
        self.assertNotIn('this.orm', self.tfb_js)

    def test_15_no_user_visible_string_names_the_platform(self):
        """The white-label absolute, over everything this phase touched."""
        for src in (self.canvas_js, self.tfb_js, self.geom_js,
                    self.scss, self.tfb_scss):
            self.assertNotIn('Odoo', src)
