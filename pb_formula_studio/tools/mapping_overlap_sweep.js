/**
 * The mapping boards' bounding-box overlap sweep — JOURNEY J7.
 *
 * Paste into a Chrome-MCP `evaluate_script` (or the console) with a mapping
 * board on screen; it returns `{pairs, overlaps, [...]}`. `overlaps: []` is the
 * only passing result.
 *
 * ===================================================================
 * WHY THIS FILE EXISTS AT ALL
 * ===================================================================
 *
 * This sweep has been retyped from memory once per phase since MJ7, and each
 * time it was retyped it carried the same misclassification forward. J7's D1 —
 * the amber "↑ 11 hidden by filter above" chip painted over the top card of the
 * right column — is a defect the sweep RAN OVER, in the exact state that
 * renders it, and passed.
 *
 * The misclassification, precisely:
 *
 *   MJ7 taught the sweep to skip pairs that "do not share a layer", because a
 *   dropdown is SUPPOSED to cover the chips beneath it. That lesson is right.
 *   The IMPLEMENTATION of "layer" was the nearest positioned ancestor's
 *   `z-index` — and `.mc-docks` is `z-index: 4` while `.mc-cols` is `2`. So a
 *   dock chip and a card were, by that definition, on different layers, and
 *   every dock-versus-card pair on both boards was skipped as an intentional
 *   overlay for five phases.
 *
 *   A dock chip is not an overlay. It is in-flow furniture: nobody opened it,
 *   nothing dismisses it, there is no scrim under it, and it carries a count
 *   the reader is meant to be able to read AT THE SAME TIME as the cards it sits
 *   beside. Its z-index is a PAINTING decision (it has to sit above the wire
 *   SVG), and a painting decision is not a permission to occlude.
 *
 * So `layerOf` no longer asks the stylesheet. It asks a NAMED LIST of things a
 * user opens — and everything not on that list is content, tested against all
 * other content. The list is short, closed, and every entry has a scrim or a
 * dismiss gesture. Adding to it is a decision, not an accident of a z-index.
 *
 * There was a SECOND way this sweep invented and hid defects, found in the same
 * run and fixed in `clip()` below: it clipped to `.mc-board`, which is not what
 * clips a card. See the note there — the short version is that a clip box has
 * to be DERIVED from the element, never named.
 *
 * The other two lessons are kept, because both were paid for:
 *   * MJ7  — a card scrolled past the edge still reports a rect; compare each
 *            rect INTERSECTED with what actually clips it.
 *   * MJ12 — exclude SVG internals. Two `<path>`s of one Lucide glyph overlap
 *            because that is what a drawing is.
 * And MJ30's corollary: the sweep is therefore structurally blind to wires.
 * `wireEndpointError()` below is the check that covers them; run both.
 */
(() => {
    // ---- the closed list of things a USER OPENS -------------------------
    // Every one of these has a scrim, an Escape rung or a dismiss button. A
    // chip, a card, a hub, a dock, a group heading and a column note are NOT
    // here, and must never be added: they are the board.
    const OVERLAY = [
        ".mc-menu", ".mc-menu-scrim", ".mc-tf-pop", ".mc-tf-scrim",
        ".mc-drawhint", ".mc-reveal", ".mc-gesture",
        ".tfb-menu", ".tfb-reveal", ".tfb-wireact", ".tfb-drawhint",
        "[role='dialog']", "[role='menu']", ".o_popover", ".o-overlay-item",
    ].join(",");

    const layerOf = (el) => (el.closest(OVERLAY) ? "overlay" : "board");

    /**
     * The rect this element is actually PAINTED in.
     *
     * MJ7 said "compare each card's rect intersected with the clip box" and
     * named `.mc-board` as the clip box. `.mc-board` is not the clipper of a
     * CARD — `.mc-col-body` is, and its scrollport is its PADDING box. Two
     * consequences, and J7 met both in one run:
     *
     *   * a card at the top or bottom of a scrolled column reports a layout
     *     rect that runs past the scrollport, so it "overlapped" the column's
     *     filter chips and its own dock chip while being invisible there;
     *   * J7's dock strip is a 30px BORDER on that scroller, so the padding box
     *     is 30px shorter than the border box at each end — exactly the band
     *     the chips live in. A sweep clipping to the border box says every chip
     *     covers the nearest card, forever, in every state.
     *
     * So: walk the ancestors, and for each one that is not `overflow: visible`,
     * intersect with its padding box. That is the rule rather than a list of
     * element names, which is what stopped it transferring the first time.
     */
    const clip = (el) => {
        const r = el.getBoundingClientRect();
        const out = { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
        for (let p = el.parentElement; p; p = p.parentElement) {
            const cs = getComputedStyle(p);
            if (cs.overflow === "visible" && cs.overflowX === "visible"
                && cs.overflowY === "visible") { continue; }
            const pr = p.getBoundingClientRect();
            out.left = Math.max(out.left, pr.left + (parseFloat(cs.borderLeftWidth) || 0));
            out.right = Math.min(out.right, pr.right - (parseFloat(cs.borderRightWidth) || 0));
            out.top = Math.max(out.top, pr.top + (parseFloat(cs.borderTopWidth) || 0));
            out.bottom = Math.min(out.bottom, pr.bottom - (parseFloat(cs.borderBottomWidth) || 0));
        }
        return out;
    };

    const SELECT = [
        ".mc-item", ".mc-dock", ".mc-hub", ".mc-group", ".mc-chip",
        ".mc-col-hid", ".mc-col-add", ".mc-gone", ".mc-item-note",
        ".tfb-item", ".tfb-dock", ".tfb-chip", ".tfb-col-h",
    ].join(",");

    const nodes = [...document.querySelectorAll(SELECT)]
        // MJ12 — a Lucide glyph is not a layout
        .filter((e) => !(e instanceof SVGElement))
        .filter((e) => { const r = e.getBoundingClientRect();
                         return r.width > 1 && r.height > 1; })
        .map((e) => ({ el: e, r: clip(e),
                       layer: layerOf(e), name: e.className }));

    const overlaps = [];
    let pairs = 0;
    for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
            const a = nodes[i], b = nodes[j];
            if (a.layer !== b.layer) { continue; }          // MJ7, honestly
            if (a.el.contains(b.el) || b.el.contains(a.el)) { continue; }
            pairs++;
            const ox = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
            const oy = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
            if (ox > 0.5 && oy > 0.5) {
                overlaps.push({ a: a.name, b: b.name,
                                ox: +ox.toFixed(1), oy: +oy.toFixed(1),
                                at: a.el.innerText.split("\n")[0],
                                with: b.el.innerText.split("\n")[0] });
            }
        }
    }

    // ---- J7 D1 — the pair the sweep must never skip again ---------------
    // Stated separately as well as swept, so that a future refactor of
    // `layerOf` cannot quietly stop testing it. Both columns, both variants.
    const docks = [...document.querySelectorAll(".mc-dock, .tfb-dock")];
    const cards = [...document.querySelectorAll(".mc-item, .tfb-item")];
    const dockOverCard = [];
    for (const d of docks) {
        const a = clip(d);
        for (const c of cards) {
            const b = clip(c);
            const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
            const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
            if (ox > 0.5 && oy > 0.5) {
                dockOverCard.push({ chip: d.innerText.trim(),
                                    card: c.innerText.split("\n")[0],
                                    ox: +ox.toFixed(1), oy: +oy.toFixed(1) });
            }
        }
        // MJ7's own disproof, kept as a positive check: whatever the rects
        // say, ask the browser what is painted at the chip's centre. Anything
        // inside a card there is a real occlusion.
        const hit = document.elementFromPoint((a.left + a.right) / 2,
                                              (a.top + a.bottom) / 2);
        if (hit && hit.closest(".mc-item, .tfb-item")) {
            dockOverCard.push({ chip: d.innerText.trim(), paintedOver: true,
                                card: hit.closest(".mc-item, .tfb-item")
                                        .innerText.split("\n")[0] });
        }
    }

    return {
        w: innerWidth, h: innerHeight,            // MJ13 — assert the width
        pairs, overlaps,
        docks: docks.map((d) => d.innerText.trim()),
        dockOverCard,
        bodyScrollsX: document.body.scrollWidth > document.body.clientWidth + 1,
    };
})();
