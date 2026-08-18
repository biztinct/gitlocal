# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P5 — T4: the static gates the redesign has to keep passing.

The headline one is `test_no_rate_ever_reaches_a_cell`. The owner's complaint
about the old grid was one sentence — *"the % pills are very confusing"* — and
the fix is not "I removed them", it is "nothing in this component can put a rate
in a cell again". A grep over the CELL REGION of the template is the only form
of that promise a future contributor trips over.

Two rails learned the expensive way and applied here (W48's corollary):
  * a word-shaped gate fails on the DOCUMENTATION that explains the rule, so the
    region walked is bounded by explicit markers rather than the whole file;
  * every gate names the file and the offending line in its failure message —
    a bare assertFalse on a regex tells the next person nothing.
"""

import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_JS = ('static/src/js/week_grid.js', 'static/src/js/week_cell_editor.js')
_XML = ('static/src/xml/week_grid.xml', 'static/src/xml/week_cell_editor.xml')
_SCSS = ('static/src/scss/week_grid.scss', 'static/src/scss/week_cell_editor.scss')

# The cell region of the grid template: everything between the anatomy marker
# and the row-total that closes it. This is the span a cell actually renders.
_CELL_START = '<!-- ==== day cells ==== -->'
_CELL_END = '<!-- row total -->'

# pictographs + dingbats + the emoji variation selector, written as escapes so
# this file cannot trip its own gate (the pb_time_hub precedent).
_RE_EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿️]')
_RE_GRADIENT = re.compile(r'(linear|radial|conic)-gradient')
_RE_FA = re.compile(r'\bfa-[a-z]')


def _read(rel):
    path = os.path.join(get_module_path('biz_week_grid'), rel)
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestWeekGridStatic(TransactionCase):

    # ==================================================================
    #  the cell region
    # ==================================================================
    def _cell_region(self):
        src = _read('static/src/xml/week_grid.xml')
        self.assertIn(_CELL_START, src, 'the cell-region marker moved')
        self.assertIn(_CELL_END, src, 'the cell-region end marker moved')
        start = src.index(_CELL_START)
        end = src.index(_CELL_END, start)
        return src[start:end]

    def test_no_rate_ever_reaches_a_cell(self):
        """§3.1, T-gated. `measureName` / `measureRate` are the only readers of
        a measure's human identity, and neither may appear in the cell region;
        nor may a literal per cent sign, nor `m.label`, which IS the rate on
        the consumer that started this."""
        region = self._cell_region()
        for needle in ('m.label', 'measureRate', 'measureName', '.rate', '%'):
            self.assertNotIn(
                needle, region,
                "a cell may not render %r — rates live in the legend and the "
                "cell editor, once each (P5 §3.1/§3.4)" % needle)

    def test_the_cell_region_still_renders_the_things_it_must(self):
        """The complement of the gate above: a region that renders NOTHING
        would pass it too. These are the outcomes §3.1 lists."""
        region = self._cell_region()
        for needle in ('bwg-prim__v', 'enteredMeasures', 'bwg-sdot',
                       'bwg-badge', 'bwg-mark--lock'):
            self.assertIn(needle, region,
                          'the cell no longer renders %r' % needle)

    def test_a_chip_is_drawn_from_entered_measures_not_from_applicable_ones(self):
        """The actual defect: the old grid looped `chipMeasures` and drew one
        pill per APPLICABLE type. If that loop ever comes back the cells fill
        with empty pills again and every other gate here still passes."""
        region = self._cell_region()
        self.assertNotIn('t-foreach="chipMeasures"', region)
        self.assertIn('t-foreach="enteredMeasures(row, day.iso)"', region)

    # ==================================================================
    #  the adapter contract (binding non-goal)
    # ==================================================================
    def test_the_adapter_contract_is_untouched(self):
        src = _read('static/src/js/week_grid.js')
        for hook in ('adapter:', 'params:', 'onData:', 'onDirty:',
                     'onFocus:', 'onSaved:', 'onRowOpen:'):
            self.assertIn(hook, src,
                          'the adapter/prop contract lost %r' % hook)
        for call in ('this.props.adapter.fetch(', 'this.props.adapter.save(',
                     'this.props.adapter.validate'):
            self.assertIn(call, src, 'the adapter call %r is gone' % call)

    def test_the_grid_is_still_product_neutral(self):
        """C18.1: biz_week_grid is reusable for timesheets and meal counts, so
        it may import `web` and itself and nothing else."""
        for rel in _JS:
            for line in _read(rel).splitlines():
                m = re.search(r'from\s+"([^"]+)"', line)
                if not m:
                    continue
                mod = m.group(1)
                self.assertTrue(
                    mod.startswith('@odoo/') or mod.startswith('@web/')
                    or mod.startswith('@biz_week_grid/'),
                    '%s imports %r — the engine must stay product-neutral'
                    % (rel, mod))

    # ==================================================================
    #  no autosave, and staging only from handlers (W21)
    # ==================================================================
    def test_the_editor_stages_and_never_saves(self):
        """§3.2: the editor stages, the tray commits. A `save()` reachable from
        the panel would make the tray a decoration and re-introduce the exact
        thing the handover forbids."""
        src = _read('static/src/js/week_cell_editor.js')
        for banned in ('adapter', 'rpc(', '.save(', 'orm'):
            self.assertNotIn(banned, src,
                             'the cell editor must not be able to write (%r)'
                             % banned)

    def test_nothing_stages_from_a_lifecycle_hook(self):
        """W21/W21.1: mount hooks READ, event handlers WRITE. `_applyEdit` and
        `_commitEditor` are the two staging paths; neither may be reachable
        from setup()."""
        src = _read('static/src/js/week_grid.js')
        start = src.index('    setup() {')
        end = src.index('\n    // ---------------------------------------------------------------- display')
        setup_body = src[start:end]
        for banned in ('_applyEdit(', '_commitEditor(', 'this.save('):
            self.assertNotIn(banned, setup_body,
                             'setup() may not reach %r' % banned)

    def test_the_editor_mounts_through_the_overlay_service(self):
        """W43: not by winning a z-index argument, and not `position: absolute`
        inside a scroller that clips horizontally (W34)."""
        src = _read('static/src/js/week_grid.js')
        self.assertIn('useService("overlay")', src)
        self.assertIn('this.overlay.add(', src)
        scss = _read('static/src/scss/week_cell_editor.scss')
        self.assertIn('position: fixed', scss)
        self.assertNotIn('position: absolute', scss)

    def test_the_overlaid_panel_carries_real_fallbacks(self):
        """W14/W43.1: mounted in `.o-overlay-container` the panel sees neither
        `--pbim-*` nor `--bwg-*`, so a `var()` fallback is what PAINTS. A
        fallback-less var() in that file is a colour that will not exist."""
        scss = _read('static/src/scss/week_cell_editor.scss')
        body = scss[scss.index('.bwgx {'):]
        # skip the block's own token declarations, which are the source values
        checked = 0
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith('--bwg-'):
                continue
            for m in re.finditer(r'var\((--[a-z0-9-]+)([^)]*)\)', stripped):
                checked += 1
                self.assertTrue(
                    m.group(2).strip().startswith(','),
                    'week_cell_editor.scss: `%s` has no fallback, and the '
                    'overlay is where a missing fallback is not a colour at '
                    'all (W14)' % m.group(0))
        self.assertGreater(checked, 10, 'the fallback walk found nothing')

    # ==================================================================
    #  design-system gates (W1/W2/W3)
    # ==================================================================
    def test_no_gradients_no_emoji_no_fontawesome(self):
        for rel in _JS + _XML + _SCSS:
            src = _read(rel)
            self.assertFalse(_RE_GRADIENT.search(src),
                             'W3: %s ships a gradient' % rel)
            self.assertFalse(_RE_EMOJI.search(src),
                             'W2: %s ships an emoji' % rel)
            self.assertFalse(_RE_FA.search(src),
                             'W2: %s ships a FontAwesome class' % rel)

    def test_no_alpha_suffixed_var_and_no_fake_tokens(self):
        """W15 (`var(--x, #abc)33` is silently dropped) and W19 (a token that
        does not exist renders permanently from its fallback)."""
        for rel in _SCSS:
            src = _read(rel)
            self.assertFalse(
                re.search(r'var\([^)]*\)[0-9a-fA-F]{2}\b', src),
                'W15: %s alpha-suffixes a var()' % rel)
            self.assertNotIn('--pbim-pill', src, 'W19: --pbim-pill does not exist')
            self.assertNotIn('--pbim-primary-soft', src,
                             'W14: the soft indigo token is --pbim-soft')

    def test_no_mixed_unit_min_max_in_scss(self):
        """Dart Sass evaluates `min()`/`max()` itself and throws on mixed units
        — the failure only surfaces when the bundle is built, i.e. at page
        load, long after `-u` says EXIT 0."""
        for rel in _SCSS:
            for i, line in enumerate(_read(rel).splitlines(), 1):
                self.assertFalse(
                    re.search(r'[^-a-z](min|max)\([^)]*\d(px|rem|em)[^)]*\d%',
                              line),
                    '%s:%d mixes units inside min()/max()' % (rel, i))

    # ==================================================================
    #  templates
    # ==================================================================
    def test_no_double_hyphen_in_any_xml_comment(self):
        """W22: `<!-- ---- x ---- -->` is a parse error that takes the WHOLE
        template file down, and the failure points at a component that is
        perfectly fine ("Missing template")."""
        for rel in _XML:
            for m in re.finditer(r'<!--(.*?)-->', _read(rel), re.S):
                self.assertNotIn('--', m.group(1),
                                 '%s: a comment contains a double hyphen' % rel)

    def test_no_element_carries_both_t_att_class_and_t_attf_class(self):
        """W23.1: they compile to the SAME attribute and the last one wins."""
        for rel in _XML:
            src = _read(rel)
            for m in re.finditer(r'<[a-zA-Z][^>]*>', src, re.S):
                tag = m.group(0)
                self.assertFalse(
                    't-att-class' in tag and 't-attf-class' in tag,
                    '%s: an element carries both class bindings:\n%s'
                    % (rel, tag[:200]))
