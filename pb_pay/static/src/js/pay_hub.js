/** @odoo-module **/
/**
 * "Pay" — bands drawn as a picture, and an honest answer about fairness.
 *
 * THE HERO IS THE BAND PICTURE. Every band is a range on a shared money axis
 * with every person in it as a dot. Grab an edge and drag: the dots that fall
 * outside light up as you move, and a bar at the foot of the screen says
 * "₫184M a year to bring 7 people back in" while you are still holding the
 * mouse. Let go and it saves; Undo puts the three numbers back exactly as they
 * were, because the server handed them over before it wrote anything.
 *
 * THE SECOND HERO IS ONE HONEST NUMBER PER QUESTION. Fairness prints a
 * sentence, not a dashboard: "Women earn 3.6% less than men doing work at the
 * same level", with the people it was measured on underneath and the method in
 * one line beside it. Every card that cannot answer says why in the same
 * voice — "not enough people to compare fairly" is an answer.
 *
 * THE EMPTY STATE IS A PROPOSAL, NOT A TUTORIAL. A company that has never
 * written a band opens this screen and sees its OWN bands already drawn, from
 * the wages it already pays, marked as suggestions with a dashed edge. Press
 * "Use these" and they become real. Nobody has to invent a job family before
 * they can see anything.
 *
 * THE RULES THIS FILE KEEPS
 *   * Every icon comes from the shared `ic()` set — no emoji, no glyph arrows.
 *   * Every sentence is ONE expression: JavaScript has no implicit string
 *     concatenation and a Python habit here kills the whole asset bundle.
 *   * Escape is registered with `{ capture: true }`, because the platform's
 *     own hotkey service listens on `window` and stops propagation for the
 *     keys it claims — Escape among them (WFPLAN WF4).
 *   * The refusal ladder is `error.data.message` → `error.message.data.message`
 *     → OUR OWN sentence. `error.message` is not a rung: on this platform it
 *     is the literal words this product may never say (ledger GR17).
 *   * Everything the template reads lives in `useState` (ledger GR26).
 */
import {
    Component, onMounted, onPatched, onWillStart, onWillUnmount,
    useExternalListener, useRef, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { PbPayReview, PbPayChanges } from "@pb_pay/js/pay_review";
import { binPeople, busiestBin, dodgeDots } from "@pb_pay/js/band_picture";

const BANDS = "pb.pay.bands";
const FAIRNESS = "pb.pay.fairness";

/** How long a drag waits before asking the server for the exact cost. */
const DRAG_SETTLE = 160;

/**
 * How the picture is drawn, in pixels. Two sets of numbers, because dense
 * mode is not a smaller version of the same drawing — it is the same drawing
 * with the secondary lines dropped and the track halved, and a pip that
 * cannot fit six of itself into the track has stopped saying "six people".
 */
const SHAPE = {
    normal: { bin: 8, pip: 5, pipGap: 1, base: 24, lift: 14, cap: 42,
              dot: 9, gap: 10, labels: true },
    dense: { bin: 6, pip: 3, pipGap: 0, base: 12, lift: 8, cap: 20,
             dot: 7, gap: 8, labels: false },
};

/** Below this many people in one bin the picture draws each of them. */
const PIP_LIMIT = 6;
/** A column says how many only when the figure is worth reading. */
const COUNT_LABEL_FROM = 10;
/** …and only when it clears the last figure printed, or a wall of numbers
 *  eight pixels apart says less than no numbers at all. */
const LABEL_GAP_PX = 30;
/** A band narrower than this cannot hold "median 8.5M ₫" without writing it
 *  over its own people, so it keeps the tick and drops the words. */
const MEDIAN_LABEL_ROOM = 120;
/** …and the two edge figures need this much between them to be two figures. */
const EDGE_LABEL_ROOM = 96;
/** Phones get the dense bins whatever the reader chose on their desktop. */
const PHONE_PX = 480;

/**
 * Two per-reader conveniences, remembered in this browser and nowhere else.
 *
 * Namespaced, because one browser holds every cockpit this product has and an
 * un-namespaced key is one screen silently reading another's memory. Neither
 * is configuration: they change how the picture is DRAWN for one person and
 * nothing about what anybody is paid.
 */
const FIT_KEY = "pbpay.bands.fit.v1";
const DENSE_KEY = "pbpay.bands.dense.v1";

/** localStorage throws outright in some contexts (a private window, a browser
 *  told to block site data), so every touch of it answers rather than dies. */
function remembered(key, fallback) {
    try {
        const raw = window.localStorage.getItem(key);
        return raw === null ? fallback : JSON.parse(raw);
    } catch (error) {
        return fallback;
    }
}

function remember(key, value) {
    try {
        window.localStorage.setItem(key, JSON.stringify(value));
    } catch (error) {
        // A reader whose browser refuses to remember still gets the screen
        // they asked for; they just get the default again tomorrow.
    }
}

/** The four surfaces of the Pay area. All of them are live now. */
function tabDefs() {
    return [
        { key: "bands", icon: "sliders", label: _t("Bands"), ready: true },
        { key: "fairness", icon: "scale", label: _t("Fairness"), ready: true },
        { key: "review", icon: "checkCircle", label: _t("Review"),
          ready: true },
        { key: "changes", icon: "pencil", label: _t("Changes"), ready: true },
    ];
}

/** The word in the breadcrumb, per surface. */
function tabName(key) {
    if (key === "fairness") { return _t("Fairness"); }
    if (key === "review") { return _t("Pay review"); }
    if (key === "changes") { return _t("Pay changes"); }
    return _t("Pay bands");
}

export class PbPayScreen extends Component {
    static template = "pb_pay.PbPayScreen";
    static components = { HubBackChip, PbPayReview, PbPayChanges };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.back = hubBack(this.props);
        this.trackRefs = {};
        this._settle = null;
        // The picture is measured, never assumed: bins are pixels, and the
        // lens sits inside a hub whose rail can be collapsed (WFPLAN W20).
        this.bandsRef = useRef("bandsRoot");
        this._resize = null;

        const context = (this.props.action && this.props.action.context) || {};
        this.state = useState({
            loaded: false,
            busy: false,
            failed: "",
            tab: ["fairness", "review", "changes"].includes(context.pb_tab)
                ? context.pb_tab : "bands",
            focus: context.pb_focus || "",

            // ---- bands
            board: null,
            suggestion: null,
            suggesting: false,
            familyId: 0,
            country: "",
            companyId: 0,

            // the drag in progress, and what it would cost
            drag: null,
            preview: null,
            undo: null,

            // how this reader likes the picture drawn (their browser only)
            fit: remembered(FIT_KEY, {}) || {},
            dense: Boolean(remembered(DENSE_KEY, false)),

            // how wide each band's track actually is, measured on paint and
            // on every resize. In `useState` because the template reads it
            // (ledger GR26) and the whole picture moves when it changes.
            widths: {},
            // the people behind one column, read back by name on demand
            pop: null,

            // one drawer at a time, each one plain state
            health: null,
            place: null,
            importing: null,
            hover: null,
            dialogError: "",

            // ---- fairness
            fair: null,
            scopeKind: "company",
            scopeRef: 0,
            groupMoney: false,
            method: false,
        });

        // The props handed to a sub-screen are memoised: a getter returning a
        // fresh object makes OWL see the child's props as changed on every
        // repaint, and this child holds a nine-hundred-row worksheet (W21).
        this.reviewProps = { focus: context.pb_focus || "" };

        onWillStart(async () => {
            this.env.config.setDisplayName(tabName(this.state.tab));
            if (this.state.tab === "review" || this.state.tab === "changes") {
                this.state.loaded = true;
                return;
            }
            await this.load();
            if (context.pb_focus === "place") { await this.openPlace(); }
        });

        onMounted(() => {
            this._measureTracks();
            if (window.ResizeObserver && this.bandsRef.el) {
                this._resize = new ResizeObserver(() => this._measureTracks());
                this._resize.observe(this.bandsRef.el);
            }
        });
        // A repaint can change how many bands are on screen, so the widths
        // are taken again — but ONLY written when one of them really moved,
        // or the write patches, the patch measures, and the screen spins.
        onPatched(() => this._measureTracks());
        onWillUnmount(() => {
            if (this._resize) { this._resize.disconnect(); }
        });

        useExternalListener(window, "keydown", (ev) => this.onKey(ev),
                            { capture: true });
        useExternalListener(window, "mousemove", (ev) => this.onDrag(ev));
        useExternalListener(window, "mouseup", () => this.endDrag());
    }

    ic(name, size = 16) { return ic(name, size); }

    get tabs() { return tabDefs(); }

    // ================================================================ errors
    /**
     * The server's own sentence, or ours. `error.message` is never a rung:
     * on this platform it holds the other product's name (ledger GR17).
     */
    _msg(error, fallback) {
        const data = error && error.data;
        if (data && data.message) { return data.message; }
        const nested = error && error.message && error.message.data;
        if (nested && nested.message) { return nested.message; }
        return fallback;
    }

    _fail(error, fallback) {
        const text = this._msg(error, fallback);
        this.notif.add(text, { type: "warning" });
        return text;
    }

    // =============================================================== reading
    async load() {
        try {
            this.state.board = await this.orm.call(BANDS, "get_board", [
                this.state.companyId ? [this.state.companyId] : null,
                this.state.familyId || 0,
                this.state.country || "",
            ]);
            this.state.failed = "";
            if (this.state.board && !this.state.board.has_bands) {
                await this.loadSuggestion();
            }
        } catch (error) {
            this.state.failed = this._msg(error, _t(
                "The pay bands could not be read just now. Try again in a "
                + "moment."));
        }
        if (this.state.tab === "fairness") { await this.loadFairness(); }
        this.state.loaded = true;
    }

    async loadSuggestion() {
        this.state.suggesting = true;
        try {
            this.state.suggestion = await this.orm.call(
                BANDS, "suggest_bands",
                [this.state.companyId ? [this.state.companyId] : null]);
        } catch (error) {
            this.state.suggestion = null;
        }
        this.state.suggesting = false;
    }

    async loadFairness() {
        try {
            this.state.fair = await this.orm.call(FAIRNESS, "get_board", [
                this.state.scopeKind, this.state.scopeRef || 0,
                this.state.groupMoney,
            ]);
            if (this.state.fair && this.state.fair.scope) {
                this.state.scopeKind = this.state.fair.scope.kind;
                this.state.scopeRef = this.state.fair.scope.ref;
            }
        } catch (error) {
            this.state.failed = this._msg(error, _t(
                "The fairness figures could not be worked out just now."));
        }
    }

    async setTab(key) {
        const tab = this.tabs.find((t) => t.key === key);
        if (!tab || !tab.ready) { return; }
        this.state.tab = key;
        this.env.config.setDisplayName(tabName(key));
        if (key === "review" || key === "changes") { return; }
        if (!this.state.board) {
            this.state.busy = true;
            await this.load();
            this.state.busy = false;
            return;
        }
        if (key === "fairness" && !this.state.fair) {
            this.state.busy = true;
            await this.loadFairness();
            this.state.busy = false;
        }
    }

    async refilter(what, value) {
        if (what === "family") { this.state.familyId = parseInt(value, 10) || 0; }
        if (what === "country") { this.state.country = value || ""; }
        if (what === "company") { this.state.companyId = parseInt(value, 10) || 0; }
        this.state.busy = true;
        await this.load();
        this.state.busy = false;
    }

    // ============================================================ the picture
    /** The lanes on screen: the saved ones, or the suggestion when there are
     *  none saved at all. A company on day one sees a picture, not a page of
     *  instructions with a button at the bottom. */
    get lanes() {
        const board = this.state.board;
        if (board && board.lanes && board.lanes.length) { return board.lanes; }
        const suggested = this.state.suggestion;
        if (suggested && suggested.lanes) { return suggested.lanes; }
        return [];
    }

    get showingSuggestion() {
        const board = this.state.board;
        const saved = board && board.lanes && board.lanes.length;
        return Boolean(!saved && this.state.suggestion
                       && this.state.suggestion.lanes
                       && this.state.suggestion.lanes.length);
    }

    // ------------------------------------------------- one family at a time
    /**
     * The bands of one lane, gathered into their job families.
     *
     * The SHARED axis is still the default and still the point: a level 2
     * band and a level 8 band are meant to be comparable at a glance. But a
     * family of low-paid roles beside a family of directors is drawn as a
     * sliver of a picture, so each family may be asked to fit the axis to its
     * own bands instead. That is a per-reader convenience: it is remembered
     * in their browser, it changes nothing anybody is paid, and while it is
     * on the family says out loud that its widths no longer compare with the
     * rest.
     *
     * Every position on the screen — the ranges, the middle marks, the grips,
     * the dots, the ticks — is measured against the SCALE this returns, so a
     * fitted family and a shared one can sit in the same lane and both be
     * right.
     */
    familyGroups(lane) {
        const axes = {};
        (lane.families || []).forEach((family) => {
            axes[family.key] = family;
        });
        const groups = [];
        const seen = {};
        (lane.bands || []).forEach((band) => {
            const key = band.family || "";
            if (seen[key] === undefined) {
                const family = axes[key] || {};
                const fitted = Boolean(this.state.fit[key]);
                seen[key] = groups.length;
                groups.push({
                    key,
                    name: family.name || key || _t("No job family"),
                    fitted: fitted && Boolean(family.axis),
                    own: family.axis || lane.axis,
                    axis: fitted && family.axis ? family.axis : lane.axis,
                    bands: [],
                });
            }
            groups[seen[key]].bands.push(band);
        });
        return groups;
    }

    /** "Fit to this family" — on for one family, off again, remembered. */
    toggleFit(key) {
        const next = { ...this.state.fit };
        if (next[key]) {
            delete next[key];
        } else {
            next[key] = true;
        }
        this.state.fit = next;
        remember(FIT_KEY, next);
    }

    /** Half-height rows with the secondary lines dropped, so a company with
     *  many bands sees all of them without scrolling. */
    toggleDense() {
        this.state.dense = !this.state.dense;
        remember(DENSE_KEY, this.state.dense);
    }

    /** Where a value sits on an axis, as a percentage of its width. Handed a
     *  lane or a family group — both carry the `axis` this measures against. */
    axisPct(scope, value) {
        const top = (scope && scope.axis && scope.axis.max) || 1;
        const pct = (Number(value || 0) / top) * 100;
        return Math.max(0, Math.min(100, pct));
    }

    /** The three numbers a band is drawn with right now: the saved ones, or
     *  the ones the finger is currently holding. */
    live(band) {
        const drag = this.state.drag;
        if (drag && drag.bandId === band.id && band.id) {
            return { min: drag.min, mid: drag.mid, max: drag.max };
        }
        return { min: band.min, mid: band.mid, max: band.max };
    }

    rangeStyle(scope, band) {
        const now = this.live(band);
        const left = this.axisPct(scope, now.min);
        const right = this.axisPct(scope, now.max);
        return "left:" + left + "%;width:" + Math.max(0.4, right - left) + "%";
    }

    midStyle(scope, band) {
        return "left:" + this.axisPct(scope, this.live(band).mid) + "%";
    }

    gripStyle(scope, band, side) {
        const now = this.live(band);
        return "left:" + this.axisPct(scope, side === "min" ? now.min : now.max)
            + "%";
    }

    /** The tick at the middle of what this band's people are actually paid. */
    medianStyle(scope, band) {
        return "left:" + this.axisPct(scope, band.median || 0) + "%";
    }

    // ------------------------------------------------------- the two shapes
    /**
     * A band's own name for itself, stable across repaints.
     *
     * A saved band has an id. A SUGGESTED one has nothing but the bucket it
     * came from, and two suggestions can share a family and a level in two
     * companies — so the key is the bucket, and the widths, the tracks and the
     * open popover all agree about which band they are talking about.
     */
    bandKey(band) {
        if (band.id) { return "b" + band.id; }
        return ["s", band.family, band.level, band.company_id || 0].join("|");
    }

    /** Which set of pixel sizes this picture is being drawn with. */
    get shape() {
        const narrow = window.innerWidth && window.innerWidth <= PHONE_PX;
        return (this.state.dense || narrow) ? SHAPE.dense : SHAPE.normal;
    }

    /**
     * How wide every track on screen is, in pixels.
     *
     * Written back into state only when a number actually changed: `onPatched`
     * runs after every render, and a state write that always happens is a
     * render that always happens again.
     */
    _measureTracks() {
        const root = this.bandsRef.el;
        if (!root) { return; }
        // A drag repaints on every mouse move and cannot change how wide a
        // track is, so measuring thirty of them per frame is pure cost.
        if (this.state.drag) { return; }
        const found = {};
        root.querySelectorAll(".pay-track[data-band-key]").forEach((el) => {
            const key = el.dataset.bandKey;
            const width = Math.round(el.getBoundingClientRect().width);
            if (key && width) {
                found[key] = width;
                this.trackRefs[key] = el;
            }
        });
        const now = this.state.widths;
        const keys = Object.keys(found);
        let changed = keys.length !== Object.keys(now).length;
        if (!changed) {
            changed = keys.some((key) => now[key] !== found[key]);
        }
        if (changed) { this.state.widths = found; }
    }

    /**
     * THE PICTURE. Everybody on this band, in whichever shape draws them all.
     *
     * Up to two dozen people get a dot each with their name on it, dodged so
     * that no two ever touch. Above that the track is cut into bins a few
     * pixels wide and each bin is drawn as pips — one small square per person,
     * so six people READ as six — or, once a bin holds more than a handful, as
     * a solid column with its count printed above it. Nobody is ever dropped
     * (TIDY ledger rule 12): the picture changes shape instead.
     *
     * Every part is classed against the edges as they are being HELD, so the
     * colours sweep across the picture while the mouse is still down.
     */
    picture(scope, band) {
        const key = this.bandKey(band);
        const width = this.state.widths[key] || 0;
        const shape = this.shape;
        const top = (scope && scope.axis && scope.axis.max) || 1;
        const now = this.live(band);
        if (!width) { return { kind: "waiting", key, parts: [], dots: [] }; }
        const dots = band.dots || [];
        if (dots.length && dots.length <= 24) {
            return {
                kind: "dots", key, parts: [],
                dots: dodgeDots(dots, top, width, shape.gap),
            };
        }
        const bins = binPeople(band.wages || [], top, width, shape.bin, now);
        const busiest = Math.max(busiestBin(bins), PIP_LIMIT + 1);
        const parts = [];
        bins.forEach((bin) => {
            const pieces = [
                { state: "below", n: bin.below },
                { state: "inside", n: bin.inside },
                { state: "above", n: bin.above },
            ].filter((piece) => piece.n > 0);
            const each = (bin.x1 - bin.x0) / pieces.length;
            pieces.forEach((piece, index) => {
                parts.push({
                    // Keyed by WHERE it is, never by what colour it is: a
                    // key that carries the state makes every recolour a new
                    // element, and a new element plays the fade-in again —
                    // the picture would flicker under the dragging hand.
                    key: key + ":" + bin.index + ":" + index,
                    bin,
                    state: piece.state,
                    count: piece.n,
                    x: bin.x0 + (index * each),
                    width: each,
                    pips: piece.n <= PIP_LIMIT
                        ? Array.from({ length: piece.n }, (_v, i) => i)
                        : null,
                    height: this._columnHeight(piece.n, busiest, shape),
                    label: "",
                });
            });
        });
        this._labelColumns(parts, shape);
        return { kind: "bins", key, parts, dots: [] };
    }

    /**
     * The counts printed over the columns, spaced so they can be read.
     *
     * A bin is eight pixels wide and a three-digit figure is twenty, so
     * labelling every column produces a run of overlapping numbers that says
     * nothing at all — which is what the first build of this screen did. The
     * figure is printed left to right and only when it clears the last one
     * printed; every column still carries its exact count on its own label
     * and in the list it opens, so nothing is lost, only decluttered.
     */
    _labelColumns(parts, shape) {
        if (!shape.labels) { return; }
        let last = -1e9;
        parts.forEach((part) => {
            if (part.pips || part.count < COUNT_LABEL_FROM) { return; }
            const middle = part.x + (part.width / 2);
            if (middle - last < LABEL_GAP_PX) { return; }
            part.label = String(part.count);
            last = middle;
        });
    }

    /**
     * Is there room to write the median beside its tick?
     *
     * A band drawn forty pixels wide on a shared money axis cannot carry a
     * sixty-pixel label without printing it over the people. The tick is
     * always there and always carries the words on hover; the writing appears
     * once the band is wide enough to hold it.
     */
    medianRoomy(scope, band) {
        return this._bandPx(scope, band) >= MEDIAN_LABEL_ROOM;
    }

    /** The two figures at the ends of a band print each other over when the
     *  band is a sliver on a shared axis. Both are on the band's own line
     *  above ("6.6M ₫ to 11M ₫"), so the picture drops them rather than
     *  drawing two numbers on top of one another. */
    edgesRoomy(scope, band) {
        return this._bandPx(scope, band) >= EDGE_LABEL_ROOM;
    }

    _bandPx(scope, band) {
        const width = this.state.widths[this.bandKey(band)] || 0;
        const now = this.live(band);
        const span = this.axisPct(scope, now.max) - this.axisPct(scope, now.min);
        return (span / 100) * width;
    }

    /** A column's height: flat below the pip limit, then a square root of how
     *  busy it is against the busiest bin, capped short of the track. */
    _columnHeight(count, busiest, shape) {
        if (count <= PIP_LIMIT) {
            return (count * (shape.pip + shape.pipGap)) - shape.pipGap;
        }
        const span = Math.max(1, busiest - PIP_LIMIT);
        const share = Math.sqrt((count - PIP_LIMIT) / span);
        return Math.min(shape.cap, shape.base + (shape.lift * share));
    }

    partStyle(part) {
        return "left:" + part.x + "px;width:" + part.width + "px";
    }

    colStyle(part) {
        return "height:" + part.height + "px";
    }

    /** A pip is a person, and it never grows wider than the slice of the bin
     *  its own colour owns — a bin split three ways is only a few pixels. */
    pipStyle(part) {
        const shape = this.shape;
        const wide = Math.max(2, Math.min(shape.pip, part.width - 1));
        return "width:" + wide + "px;height:" + shape.pip
            + "px;margin-top:" + shape.pipGap + "px";
    }

    partClass(part) {
        return "pay-mark is-" + part.state;
    }

    /** "12 people · 6.6M ₫ to 6.9M ₫ · below the band" — the word is always
     *  there, because colour on its own is never the message. */
    partTitle(band, part) {
        return [
            part.count === 1 ? _t("1 person")
                : _t("%(count)s people", { count: part.count }),
            _t("%(low)s to %(high)s", {
                low: this.shortMoney(part.bin.low, band),
                high: this.shortMoney(part.bin.high, band),
            }),
            this.stateWord(part.state),
        ].join(" · ");
    }

    /** A bin edge is a pixel wide, not a payslip: it is written short, and
     *  in the money its own band is written in. */
    shortMoney(value, band) {
        const number = Number(value) || 0;
        let body = String(Math.round(number));
        if (number >= 1e9) { body = (number / 1e9).toFixed(1) + _t("B"); }
        else if (number >= 1e6) { body = (number / 1e6).toFixed(1) + _t("M"); }
        else if (number >= 1e3) { body = Math.round(number / 1e3) + _t("K"); }
        const symbol = (band && band.symbol) || "";
        if (!symbol) { return body; }
        return band.symbol_before ? symbol + body : body + " " + symbol;
    }

    stateWord(state) {
        if (state === "below") { return _t("below the band"); }
        if (state === "above") { return _t("above the band"); }
        return _t("in the band");
    }

    /**
     * "57 below" and "82 above", counted against the edges being HELD.
     *
     * The marks recolour under the hand, so a chip that still reports the
     * saved figure puts two different answers to the same question on one
     * row. Both are read from the same complete list of wages the picture is
     * drawn from, so they cannot disagree with it.
     */
    liveChip(band, side) {
        const now = this.live(band);
        const wages = band.wages || [];
        let count = 0;
        for (const wage of wages) {
            if (side === "below" ? wage < now.min : wage > now.max) {
                count += 1;
            }
        }
        return side === "below"
            ? _t("%(count)s below", { count })
            : _t("%(count)s above", { count });
    }

    liveOut(band, side) {
        const now = this.live(band);
        return (band.wages || []).some(
            (wage) => (side === "below" ? wage < now.min : wage > now.max));
    }

    /** Where a person stands against the edges being held RIGHT NOW. */
    dotState(band, dot) {
        const now = this.live(band);
        if (dot.wage < now.min) { return "below"; }
        if (dot.wage > now.max) { return "above"; }
        return "inside";
    }

    dotStyle(dot) {
        const shape = this.shape;
        return "left:" + dot.x + "px;top:calc(50% + " + (dot.row * shape.dot)
            + "px)";
    }

    dotClass(band, dot) {
        return "pay-dot is-" + this.dotState(band, dot);
    }

    dotTitle(band, dot) {
        return [dot.name, dot.job, dot.wage_label,
                this.stateWord(this.dotState(band, dot))]
            .filter(Boolean).join(" · ");
    }

    // ------------------------------------------------------- who is in there
    /** One person, straight from the dot that was pressed. */
    openDot(band, dot) {
        this.state.pop = {
            key: this.bandKey(band),
            title: this.dotTitle(band, dot),
            busy: false,
            total: 1,
            more: 0,
            more_label: "",
            rows: [{ id: dot.id, name: dot.name, job: dot.job,
                     wage_label: dot.wage_label,
                     state: this.dotState(band, dot) }],
        };
    }

    /** The people standing in one column, by name, read back on demand. */
    async openPart(band, part) {
        this.state.pop = {
            key: this.bandKey(band), title: this.partTitle(band, part),
            busy: true, rows: [], total: part.count, more: 0, more_label: "",
        };
        try {
            const answer = await this.orm.call(BANDS, "people_between", [
                band.people_scope || {}, part.bin.low, part.bin.high,
            ]);
            const open = this.state.pop;
            if (!open) { return; }
            this.state.pop = { ...open, ...answer, busy: false,
                               title: this.partTitle(band, part) };
        } catch (error) {
            this.state.pop = {
                ...this.state.pop, busy: false,
                failed: this._msg(error, _t(
                    "Those people could not be read just now. Close this and "
                    + "try again.")),
            };
        }
    }

    closePop() { this.state.pop = null; }

    popStateWord(state) { return this.stateWord(state); }

    setTrack(band, element) {
        if (element) { this.trackRefs[this.bandKey(band)] = element; }
    }

    // --------------------------------------------------------------- the drag
    startDrag(scope, band, side, ev) {
        if (!this.state.board || !this.state.board.can_write) { return; }
        if (!band.id) {
            this.notif.add(_t(
                "These bands are a suggestion. Press “Use these” "
                + "first and then you can move them."), { type: "info" });
            return;
        }
        ev.preventDefault();
        this.state.pop = null;
        this.state.drag = {
            bandId: band.id, key: this.bandKey(band), side,
            laneMax: (scope && scope.axis && scope.axis.max) || 1,
            min: band.min, mid: band.mid, max: band.max,
            before: { min: band.min, mid: band.mid, max: band.max },
        };
        this.state.preview = null;
    }

    onDrag(ev) {
        const drag = this.state.drag;
        if (!drag || !drag.bandId) { return; }
        const track = this.trackRefs[drag.key];
        if (!track) { return; }
        const box = track.getBoundingClientRect();
        if (!box.width) { return; }
        const ratio = Math.max(0, Math.min(1, (ev.clientX - box.left)
                                              / box.width));
        this._applyEdge(drag, ratio * drag.laneMax);
    }

    _applyEdge(drag, value) {
        const rounded = Math.max(0, Math.round(value));
        if (drag.side === "min") {
            drag.min = Math.min(rounded, drag.max);
        } else {
            drag.max = Math.max(rounded, drag.min);
        }
        drag.mid = Math.min(Math.max(drag.mid, drag.min), drag.max);
        this.state.drag = { ...drag };
        this._askCost();
    }

    /** The exact cost, from the server, once the finger settles. The dots
     *  recolour instantly from what is already loaded; the MONEY is the
     *  server's, because a band can hold more people than the picture draws. */
    _askCost() {
        const drag = this.state.drag;
        if (!drag) { return; }
        if (this._settle) { clearTimeout(this._settle); }
        this._settle = setTimeout(async () => {
            const asked = this.state.drag;
            if (!asked) { return; }
            try {
                this.state.preview = await this.orm.call(BANDS, "move_edge", [
                    asked.bandId, asked.side,
                    asked.side === "min" ? asked.min : asked.max, true,
                ]);
            } catch (error) {
                this.state.preview = null;
            }
        }, DRAG_SETTLE);
    }

    async endDrag() {
        const drag = this.state.drag;
        if (!drag || !drag.bandId) { return; }
        this.state.drag = null;
        const moved = drag.side === "min"
            ? drag.min !== drag.before.min : drag.max !== drag.before.max;
        if (!moved) { this.state.preview = null; return; }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(BANDS, "move_edge", [
                drag.bandId, drag.side,
                drag.side === "min" ? drag.min : drag.max, false,
            ]);
            this.state.undo = {
                bandId: drag.bandId, before: drag.before,
                sentence: answer.sentence, count: answer.count,
                cost: answer.cost_label,
            };
            this.state.preview = null;
            await this.load();
        } catch (error) {
            this._fail(error, _t("That band could not be moved."));
        }
        this.state.busy = false;
    }

    async undoEdge() {
        const undo = this.state.undo;
        if (!undo) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(BANDS, "set_band_range", [
                undo.bandId, undo.before.min, undo.before.mid,
                undo.before.max]);
            this.state.undo = null;
            await this.load();
            this.notif.add(_t("Put back the way it was."), { type: "success" });
        } catch (error) {
            this._fail(error, _t("That band could not be put back."));
        }
        this.state.busy = false;
    }

    dismissUndo() { this.state.undo = null; }

    /** Arrows nudge an edge by a hundredth of the axis; Shift by a twentieth.
     *  Enter saves, Escape puts it back — the keyboard reaches the hero. */
    onGripKey(scope, band, side, ev) {
        const top = scope && scope.axis && scope.axis.max ? scope.axis.max : 1;
        const step = top * (ev.shiftKey ? 0.05 : 0.01);
        if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight"
                && ev.key !== "Enter" && ev.key !== "Escape") {
            return;
        }
        if (ev.key === "Escape") {
            if (this.state.drag) { this.state.drag = null; ev.stopPropagation(); }
            return;
        }
        if (ev.key === "Enter") { this.endDrag(); return; }
        ev.preventDefault();
        let drag = this.state.drag;
        if (!drag || drag.bandId !== band.id) {
            drag = {
                bandId: band.id, key: this.bandKey(band), side, laneMax: top,
                min: band.min, mid: band.mid, max: band.max,
                before: { min: band.min, mid: band.mid, max: band.max },
            };
        }
        const current = side === "min" ? drag.min : drag.max;
        this._applyEdge(drag, current + (ev.key === "ArrowLeft" ? -step : step));
    }

    // ======================================================= the suggestion
    async acceptSuggestion() {
        const suggested = this.state.suggestion;
        if (!suggested || !suggested.lanes) { return; }
        const proposals = [];
        suggested.lanes.forEach((lane) => {
            (lane.bands || []).forEach((band) => proposals.push({
                family: band.family, level: band.level,
                country_code: band.country_code,
                currency_id: band.currency_id,
                min: band.min, mid: band.mid, max: band.max,
                jobs: band.jobs || [],
            }));
        });
        this.state.busy = true;
        try {
            const made = await this.orm.call(
                BANDS, "accept_suggestion", [proposals]);
            this.state.suggestion = null;
            await this.load();
            this.notif.add(_t(
                "%(bands)s bands and %(jobs)s jobs saved.",
                { bands: made.bands, jobs: made.jobs }), { type: "success" });
        } catch (error) {
            this._fail(error, _t("Those bands could not be saved."));
        }
        this.state.busy = false;
    }

    // ========================================================= health cards
    openHealth(card) {
        this.state.health = card;
        this.state.dialogError = "";
    }

    closeDrawers() {
        this.state.health = null;
        this.state.place = null;
        this.state.importing = null;
        this.state.pop = null;
        this.state.dialogError = "";
    }

    // ======================================================== place a hire
    async openPlace() {
        this.state.place = { loading: true, job_id: 0, experience_pct: 50,
                             answer: null, jobs: [] };
        try {
            const jobs = await this.orm.call(BANDS, "jobs_without_a_band", [
                this.state.companyId ? [this.state.companyId] : null]);
            const linked = [];
            this.lanes.forEach((lane) => (lane.bands || []).forEach(
                (band) => (band.jobs || []).forEach(
                    (job) => linked.push({ id: job.id, name: job.name,
                                           people: 0 }))));
            this.state.place = {
                loading: false, job_id: (linked[0] || jobs[0] || {}).id || 0,
                experience_pct: 50, answer: null,
                jobs: linked.concat(jobs),
            };
            if (this.state.place.job_id) { await this.askPlace(); }
        } catch (error) {
            this.state.place = { loading: false, job_id: 0, jobs: [],
                                 experience_pct: 50, answer: null };
            this.state.dialogError = this._msg(error, _t(
                "The jobs could not be read just now."));
        }
    }

    async askPlace() {
        const place = this.state.place;
        if (!place || !place.job_id) { return; }
        try {
            const answer = await this.orm.call(BANDS, "place_hire", [
                place.job_id, 0, place.experience_pct]);
            this.state.place = { ...place, answer };
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That job could not be placed just now."));
        }
    }

    async setPlaceJob(value) {
        this.state.place = { ...this.state.place,
                             job_id: parseInt(value, 10) || 0 };
        await this.askPlace();
    }

    async setPlaceExperience(value) {
        this.state.place = { ...this.state.place,
                             experience_pct: parseInt(value, 10) || 50 };
        await this.askPlace();
    }

    copyOffer() {
        const place = this.state.place;
        const answer = place && place.answer;
        if (!answer || !answer.offer_label) { return; }
        const text = answer.sentence || answer.offer_label;
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text);
            this.notif.add(_t("Copied."), { type: "success" });
        }
    }

    // ============================================== import, export, rebuild
    /** "Import the 12 good rows" as ONE string: a button label glued from
     *  three template nodes cannot be translated and may lose its spaces
     *  (ledger GR22). */
    get importLabel() {
        const job = this.state.importing;
        return _t("Import the %(count)s good rows",
                  { count: (job && job.good) || 0 });
    }

    openImport() {
        this.state.importing = { rows: [], good: 0, bad: 0, sentence: "",
                                 content: "", read: false };
        this.state.dialogError = "";
    }

    async onFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const raw = await file.arrayBuffer();
        let binary = "";
        const bytes = new Uint8Array(raw);
        for (let i = 0; i < bytes.length; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        const content = window.btoa(binary);
        try {
            const answer = await this.orm.call(
                BANDS, "import_bands", [content, true]);
            this.state.importing = { ...answer, content, read: true };
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That file could not be read."));
        }
    }

    async confirmImport() {
        const job = this.state.importing;
        if (!job || !job.content) { return; }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                BANDS, "import_bands", [job.content, false]);
            this.state.importing = null;
            await this.load();
            this.notif.add(answer.sentence, { type: "success" });
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "Those bands could not be saved."));
        }
        this.state.busy = false;
    }

    async exportBands() {
        try {
            const file = await this.orm.call(BANDS, "export_bands", []);
            const link = document.createElement("a");
            link.href = "data:text/csv;base64," + file.content;
            link.download = file.name;
            link.click();
        } catch (error) {
            this._fail(error, _t("The bands could not be exported."));
        }
    }

    async recompute() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                BANDS, "recompute_positions",
                [this.state.companyId ? [this.state.companyId] : null]);
            await this.load();
            this.notif.add(_t(
                "%(rows)s people placed in %(ms)s ms.",
                { rows: answer.rows, ms: answer.ms }), { type: "success" });
        } catch (error) {
            this._fail(error, _t("The pass could not be run just now."));
        }
        this.state.busy = false;
    }

    // ============================================================= fairness
    async setScope(value) {
        const parts = String(value || "").split(":");
        this.state.scopeKind = parts[0] || "company";
        this.state.scopeRef = parseInt(parts[1], 10) || 0;
        this.state.busy = true;
        await this.loadFairness();
        this.state.busy = false;
    }

    scopeValue(scope) { return scope.kind + ":" + scope.ref; }

    get scopeCurrent() {
        return this.state.scopeKind + ":" + (this.state.scopeRef || 0);
    }

    async toggleGroupMoney() {
        this.state.groupMoney = !this.state.groupMoney;
        this.state.busy = true;
        await this.loadFairness();
        this.state.busy = false;
    }

    toggleMethod() { this.state.method = !this.state.method; }

    async printStatement() {
        try {
            const html = await this.orm.call(FAIRNESS, "print_statement", [
                this.state.scopeKind, this.state.scopeRef || 0,
                this.state.groupMoney,
            ]);
            const tab = window.open("", "_blank");
            if (!tab) {
                this.notif.add(_t(
                    "Allow this site to open a new tab and press it again."),
                               { type: "warning" });
                return;
            }
            tab.document.write(html);
            tab.document.close();
        } catch (error) {
            this._fail(error, _t("The statement could not be prepared."));
        }
    }

    // ============================================================== keyboard
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        // The popover is the innermost thing on the screen, so it closes
        // first: Escape means "the last thing I opened", never "everything".
        if (this.state.pop) {
            this.closePop();
            ev.stopPropagation();
            return;
        }
        if (this.state.health || this.state.place || this.state.importing) {
            this.closeDrawers();
            ev.stopPropagation();
            return;
        }
        if (this.state.undo) { this.state.undo = null; ev.stopPropagation(); }
    }
}

registry.category("actions").add("pb_pay", PbPayScreen);
