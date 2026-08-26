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

    // ---- J8 D2 — an arrowhead is CONTENT, and the sweep never measured one ---
    //
    // MJ12 taught this sweep to drop every `SVGElement`, because two `<path>`s of
    // one Lucide glyph overlap by construction. That exclusion is correct, and
    // MJ30 already recorded its cost: the sweep has never once measured a wire.
    // It has therefore never been able to fire on a wire's ARROWHEAD either —
    // which is not a drawing's internals, it is the symbol that says where the
    // wire ends, and J8 D2 is a defect in exactly that.
    //
    // So heads are re-admitted BY NAME (`polygon.mc-head`, never `<path>`), and
    // tested against the two things that can eat one:
    //
    //   * CLIPPING — the derived clip box (same `clip()` as above) is smaller
    //     than the head's own rect;
    //   * OCCLUSION — the head is drawn in `.mc-wires` (`z-index: 1`) and the
    //     whole column layer `.mc-cols` is `2`, so ANY opaque box of that layer
    //     covering it wins. The boxes are named, not guessed: every card, every
    //     dock chip, and the SCROLLBAR GUTTER of every column body — the last of
    //     which is what J8 D2 actually was, and which no rect-versus-element
    //     sweep could ever have found, because a scrollbar is not an element.
    const gutters = [...document.querySelectorAll(".mc-col-body, .tfb-col-b")]
        .map((b) => {
            const r = b.getBoundingClientRect();
            const cs = getComputedStyle(b);
            const left = r.left + (parseFloat(cs.borderLeftWidth) || 0);
            const right = r.right - (parseFloat(cs.borderRightWidth) || 0);
            const top = r.top + (parseFloat(cs.borderTopWidth) || 0);
            const bottom = r.bottom - (parseFloat(cs.borderBottomWidth) || 0);
            const sbw = (right - left) - b.clientWidth;
            if (sbw <= 0.5) { return null; }
            // LTR: the vertical scrollbar sits at the right of the padding box.
            return { name: "scrollbar-gutter", left: right - sbw, right, top, bottom };
        })
        .filter(Boolean);

    const opaque = [
        ...[...document.querySelectorAll(".mc-item, .tfb-item, .mc-dock, .tfb-dock")]
            .map((e) => ({ name: e.className, ...clip(e) })),
        ...gutters,
    ];

    const headOcclusions = [];
    const heads = [...document.querySelectorAll(
        "polygon.mc-head, polygon.tfb-head, polygon.tfb-rh")];
    for (const h of heads) {
        const r = h.getBoundingClientRect();
        if (r.width < 0.5 || r.height < 0.5) { continue; }
        const c = clip(h);
        const lostX = (c.left - r.left) + (r.right - c.right);
        const lostY = (c.top - r.top) + (r.bottom - c.bottom);
        if (lostX > 0.5 || lostY > 0.5) {
            headOcclusions.push({ head: h.getAttribute("class"), reason: "clipped",
                                  lostX: +lostX.toFixed(1), lostY: +lostY.toFixed(1) });
        }
        for (const o of opaque) {
            const ox = Math.min(r.right, o.right) - Math.max(r.left, o.left);
            const oy = Math.min(r.bottom, o.bottom) - Math.max(r.top, o.top);
            if (ox > 0.5 && oy > 0.5) {
                headOcclusions.push({ head: h.getAttribute("class"),
                                      reason: "occluded", by: String(o.name),
                                      ox: +ox.toFixed(1), oy: +oy.toFixed(1) });
            }
        }
    }

    // ---- MJ30's check, finally a committed artefact ------------------------
    // How far is a wire's endpoint from the port it claims to end on? For a card
    // carrying ONE wire that port is its centre and 0 is the only right answer.
    // For a card carrying several (J8's arrival comb) the port is the card's EDGE
    // SEGMENT: the endpoint must still be inside the card, and `err` is how far
    // outside it is — which is 0 for a comb that is bounded by its card, and
    // large for any of the coordinate-space slips MJ30 is about.
    const endpointErrors = [];
    const cardCentres = (sel, side) => {
        const m = new Map();
        for (const el of document.querySelectorAll(sel)) {
            if (el.dataset && el.dataset.side === side && el.dataset.id) {
                m.set(String(el.dataset.id), el.getBoundingClientRect());
            }
        }
        return m;
    };
    const canvas = document.querySelector(".mapping-canvas .mc-board");
    if (canvas) {
        const cb = canvas.getBoundingClientRect();
        const lmap = cardCentres(".mc-col.left .mc-col-body > *", "left");
        const rmap = cardCentres(".mc-col.right .mc-col-body > *", "right");
        for (const g of document.querySelectorAll(".mc-w")) {
            const wid = g.getAttribute("data-wire");
            const path = g.querySelector("path.mc-wire");
            if (!path) { continue; }
            const len = path.getTotalLength();
            const p0 = path.getPointAtLength(0);
            const p1 = path.getPointAtLength(len);
            for (const [pt, map, key, docked] of [
                [p0, lmap, g.getAttribute("data-left"), g.getAttribute("data-dockl")],
                [p1, rmap, g.getAttribute("data-right"), g.getAttribute("data-dockr")]]) {
                if (docked && docked !== "0") { continue; }   // parked on the band
                const card = map.get(String(key));
                if (!card) { continue; }
                const y = pt.y + cb.top;
                const err = Math.max(0, card.top - y, y - card.bottom);
                if (err > 0.5) {
                    endpointErrors.push({ wire: wid, key, err: +err.toFixed(1) });
                }
            }
        }
    }

    return {
        w: innerWidth, h: innerHeight,            // MJ13 — assert the width
        pairs, overlaps,
        docks: docks.map((d) => d.innerText.trim()),
        dockOverCard,
        heads: heads.length, headOcclusions,
        endpoints: endpointErrors.length,
        maxErr: endpointErrors.reduce((m, e) => Math.max(m, e.err), 0),
        endpointErrors: endpointErrors.slice(0, 10),
        bodyScrollsX: document.body.scrollWidth > document.body.clientWidth + 1,
    };
})();
