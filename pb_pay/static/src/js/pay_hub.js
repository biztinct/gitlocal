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
import {
    axisSpan, bandAxis, binPeople, busiestBin, dodgeDots,
} from "@pb_pay/js/band_picture";

const BANDS = "pb.pay.bands";
const FAIRNESS = "pb.pay.fairness";

/** How long a drag waits before asking the server for the exact cost. */
const DRAG_SETTLE = 160;

/**
 * OPENING A BAND OUT, in milliseconds and fractions.
 *
 * The two hover delays are what stop the picture flickering as a reader
 * sweeps down a list of thirty bands: nothing opens until the cursor has
 * settled, and nothing closes the instant it leaves. `ZOOM_SETTLE` is how
 * long the row wears `.is-zooming` — a little longer than the 260 ms unroll
 * in the stylesheet, so the class outlives the transition it is guarding.
 */
const HOVER_IN = 180;
const HOVER_OUT = 140;
const ZOOM_SETTLE = 320;
/** How much further than the picture shows a drag may travel. Without it an
 *  edge dragged to the end of its own zoom hits an invisible wall, which is a
 *  dead end and the design bar forbids those. */
const DRAG_HEADROOM = 0.3;
/** A zoom narrower than about 1.5% of the shared axis would draw a locator
 *  segment nobody can see, so it never draws thinner than this. */
const LOCATOR_MIN_PX = 2;
/** Rounded money can only carry so many figures before it stops meaning
 *  anything; past this the ruler stops rounding instead of repeating itself. */
const RULER_MAX_DECIMALS = 4;

/**
 * How the picture is drawn, in pixels. Two sets of numbers, because dense
 * mode is not a smaller version of the same drawing — it is the same drawing
 * with the secondary lines dropped and the track halved, and a pip that
 * cannot fit six of itself into the track has stopped saying "six people".
 */
const SHAPE = {
    normal: { bin: 8, pip: 5, pipGap: 1, base: 24, lift: 14, cap: 42,
              dot: 9, gap: 10, labels: true, ruler: 5 },
    dense: { bin: 6, pip: 3, pipGap: 0, base: 12, lift: 8, cap: 20,
             dot: 7, gap: 8, labels: false, ruler: 3 },
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
        // Opening a band out on hover is a POINTING DEVICE'S gesture. A touch
        // screen has no hover to speak of — a tap would fire it and then fire
        // the tap as well — so the button is the only door there (ruling R2).
        this.canHover = Boolean(
            window.matchMedia
            && window.matchMedia("(hover: hover) and (pointer: fine)").matches);
        this._hoverIn = null;
        this._hoverOut = null;
        this._unroll = null;
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

            // ONE band drawn on its own money scale, and only ever one.
            // Deliberately NOT remembered between visits (ruling R3): fitting
            // a family is a preference, opening a band is a moment, and
            // re-opening a band somebody has long forgotten is a surprise
            // rather than a convenience.
            open: "",        // the key of the band that is open
            pinned: false,   // pressed open, so leaving with the mouse keeps it
            zoom: null,      // { key, axis, below, above }
            zooming: "",     // the key that is mid-unroll, for one motion

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
            this._clearHoverTimers();
            if (this._unroll) { clearTimeout(this._unroll); this._unroll = null; }
            if (this._settle) { clearTimeout(this._settle); this._settle = null; }
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
        // The board is a new set of objects, so an opened band's own ruler is
        // worked out again from the numbers that have just arrived — and a
        // band that is no longer on the board closes rather than leaving a
        // zoom pointing at nothing.
        this._refreshZoom();
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
                    // The SHARED axis, carried down whatever this family is
                    // set to, because the locator over an opened band has to
                    // say where the zoom sits on the ruler everybody shares.
                    laneAxis: lane.axis,
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

    /**
     * Where a value sits on an axis, as a percentage of its width.
     *
     * Handed a lane, a family group or an OPENED BAND — all three carry the
     * `axis` this measures against, and a band's own axis is the only one of
     * the three that does not start at zero. Every position on a band row
     * goes through this one function (the range, the middle mark, the two
     * grips, the median tick, the ruler and the locator), so an axis with a
     * left-hand end is honoured everywhere or nowhere.
     */
    axisPct(scope, value) {
        const axis = (scope && scope.axis) || {};
        const low = Number(axis.min) || 0;
        const pct = ((Number(value || 0) - low) / axisSpan(axis)) * 100;
        return Math.max(0, Math.min(100, pct));
    }

    // ------------------------------------------------- open this band out
    /**
     * ONE BAND, ON ITS OWN MONEY SCALE.
     *
     * "Construction · level 2 · Vietnam" runs 6.6M to 11M ₫ on an axis that
     * reaches 136M ₫, so five hundred and forty-four people are drawn inside
     * about forty pixels. Every count is right, every colour is right, and
     * nobody can read any of it. Opening the band out unrolls that sliver
     * across the whole track: the marks spread into people you can tell apart
     * and press, a second ruler underneath says what the new width is worth,
     * and a hairline above shows which slice of the shared axis you are now
     * looking at, so nobody loses their bearings.
     *
     * IT IS A WAY OF LOOKING, NEVER A WAY OF EDITING (ledger rule 17). No
     * stored number changes, nothing is saved, and while it is open the row
     * says out loud that its width no longer compares with its neighbours.
     */
    isOpen(band) {
        return Boolean(this.state.open)
            && this.state.open === this.bandKey(band);
    }

    /**
     * The ruler a row is ACTUALLY drawn on — the one thing every drawing
     * function on the row asks, so none of them can work it out differently.
     *
     * Three rulers, narrowest first: this band's own when it is open, then
     * the family's when that family is fitted, then the lane's. Closing an
     * opened band therefore returns it to whatever the family was set to,
     * rather than always to the shared axis (ruling R5).
     */
    rowScope(group, band) {
        const zoom = this.state.zoom;
        if (zoom && zoom.key === this.bandKey(band)) {
            return {
                key: group.key, name: group.name, fitted: group.fitted,
                laneAxis: group.laneAxis, axis: zoom.axis, zoomed: true,
            };
        }
        return group;
    }

    /** Find a band on the board by the name the picture calls it. */
    _bandByKey(key) {
        for (const lane of this.lanes) {
            for (const band of (lane.bands || [])) {
                if (this.bandKey(band) === key) { return band; }
            }
        }
        return null;
    }

    /** Work out one band's own axis from numbers the browser already holds —
     *  no server call, because every band payload carries its complete list
     *  of wages already. */
    _setZoom(band, headroom) {
        const axis = bandAxis(
            { min: band.min, max: band.max, wages: band.wages || [] },
            { headroom: headroom || 0 });
        this.state.zoom = {
            key: this.bandKey(band), axis,
            below: axis.below, above: axis.above,
            people: (band.wages || []).length,
        };
    }

    /** The board has just been read again, so the open band is a NEW object:
     *  its ruler is worked out afresh, or the band has gone and so does the
     *  zoom. Never while a gesture is in flight — that axis is frozen. */
    _refreshZoom() {
        const key = this.state.open;
        if (!key || this.state.drag) { return; }
        const band = this._bandByKey(key);
        if (!band) { this.closeBand(); return; }
        this._setZoom(band, 0);
        this._markUnrolling(key);
    }

    /**
     * A zoom changes where every mark belongs, so OWL rebuilds them and would
     * replay their fade-in as a shimmer underneath the unroll. This class
     * says "one motion is happening here" for as long as it lasts, and the
     * stylesheet uses it to travel the marks and silence their entry.
     */
    _markUnrolling(key) {
        this.state.zooming = key;
        if (this._unroll) { clearTimeout(this._unroll); }
        this._unroll = setTimeout(() => {
            this._unroll = null;
            if (this.state.zooming === key) { this.state.zooming = ""; }
        }, ZOOM_SETTLE);
    }

    _clearHoverTimers() {
        if (this._hoverIn) { clearTimeout(this._hoverIn); this._hoverIn = null; }
        if (this._hoverOut) {
            clearTimeout(this._hoverOut);
            this._hoverOut = null;
        }
    }

    openBand(band, pinned) {
        this._clearHoverTimers();
        const key = this.bandKey(band);
        if (this.state.open !== key) { this.state.pop = null; }
        this.state.open = key;
        this.state.pinned = Boolean(pinned);
        this._setZoom(band, 0);
        this._markUnrolling(key);
    }

    /**
     * THE RULER A GESTURE IS MEASURED ON, worked out once at the press and
     * then frozen — with room to spare at both ends, and ANCHORED so the grip
     * that was grabbed does not move at the moment of grabbing it.
     *
     * Two things have to be true at once and neither is optional. An axis
     * recomputed under the moving hand makes the grip run away from the
     * cursor; an axis frozen with no room to spare means an edge dragged to
     * the end of its own picture hits a wall nobody can see. So the gesture
     * gets a WIDER ruler (30% at each end) whose position is chosen to keep
     * the held edge at exactly the fraction of the track it was already at —
     * the picture makes room around the hand rather than sliding under it.
     */
    _openForDrag(band, scope, side) {
        this._clearHoverTimers();
        const key = this.bandKey(band);
        if (this.state.open !== key) { this.state.pop = null; }
        this.state.open = key;
        this.state.pinned = true;

        const wide = bandAxis(
            { min: band.min, max: band.max, wages: band.wages || [] },
            { headroom: DRAG_HEADROOM });
        const span = (wide.max - wide.min) || 1;
        const drawn = (scope && scope.axis) || {};
        const drawnLow = Number(drawn.min) || 0;
        const held = Number(side === "min" ? band.min : band.max) || 0;
        // Where the held edge sits on the ruler it is drawn on RIGHT NOW,
        // kept off the very ends so the anchoring cannot divide by nothing.
        const share = Math.max(0.02, Math.min(
            0.98, (held - drawnLow) / axisSpan(drawn)));
        let low = held - (share * span);
        if (low < 0) { low = 0; }
        const axis = { min: low, max: low + span };
        let below = 0;
        let above = 0;
        for (const wage of (band.wages || [])) {
            if (wage < axis.min) { below += 1; }
            else if (wage > axis.max) { above += 1; }
        }
        this.state.zoom = { key, axis, below, above,
                            people: (band.wages || []).length };
        // Deliberately NO unrolling class: for the length of a gesture the
        // picture has to answer the hand on the same frame, and a 260 ms
        // travel on the grip is a grip lagging behind the mouse.
        this.state.zooming = "";
        return axis;
    }

    closeBand() {
        if (!this.state.open) { return; }
        const key = this.state.open;
        this._clearHoverTimers();
        this.state.open = "";
        this.state.pinned = false;
        this.state.zoom = null;
        this._markUnrolling(key);
    }

    /** The button: press to pin it open, press again to put it back. */
    toggleBand(band) {
        if (this.isOpen(band) && this.state.pinned) {
            this.closeBand();
            return;
        }
        this.openBand(band, true);
    }

    /** One whole sentence per state, never a label glued out of template
     *  nodes (ledger GR22). */
    openLabel(band) {
        return this.isOpen(band)
            ? _t("Back to the shared scale") : _t("Open out");
    }

    get openHint() {
        return _t(
            "Draw this band on its own money scale, so the people in it can "
            + "be told apart. Nothing anybody is paid changes.");
    }

    /** The id the sentence carries and the track points at, so a screen
     *  reader is told the ruler under this band has changed. */
    zoomNoteId(band) {
        return "pay-zoom-" + this.bandKey(band).replace(/[^A-Za-z0-9]+/g, "-");
    }

    // ----------------------------------------------------- hover and touch
    onTrackEnter(band) {
        if (!this.canHover || this.state.drag) { return; }
        // A band somebody has PINNED is theirs until they say otherwise; a
        // cursor crossing another row does not take it away from them.
        if (this.state.pinned) { return; }
        if (this._hoverOut) {
            clearTimeout(this._hoverOut);
            this._hoverOut = null;
        }
        if (this.isOpen(band)) { return; }
        if (this._hoverIn) { clearTimeout(this._hoverIn); }
        this._hoverIn = setTimeout(() => {
            this._hoverIn = null;
            if (this.state.drag || this.state.pinned) { return; }
            this.openBand(band, false);
        }, HOVER_IN);
    }

    onTrackLeave() {
        if (!this.canHover) { return; }
        if (this._hoverIn) { clearTimeout(this._hoverIn); this._hoverIn = null; }
        if (!this.state.open || this.state.pinned || this.state.drag) { return; }
        if (this._hoverOut) { clearTimeout(this._hoverOut); }
        this._hoverOut = setTimeout(() => {
            this._hoverOut = null;
            if (this.state.pinned || this.state.drag) { return; }
            this.closeBand();
        }, HOVER_OUT);
    }

    // ------------------------------------------- the ruler and the locator
    /** B, M or K — whichever unit the top of this ruler is written in. */
    _rulerUnit(value) {
        const size = Math.abs(Number(value) || 0);
        if (size >= 1e9) { return { div: 1e9, suffix: _t("B") }; }
        if (size >= 1e6) { return { div: 1e6, suffix: _t("M") }; }
        if (size >= 1e3) { return { div: 1e3, suffix: _t("K") }; }
        return { div: 1, suffix: "" };
    }

    _unitMoney(value, band, unit, decimals) {
        const body = (Number(value) / unit.div).toFixed(decimals) + unit.suffix;
        const symbol = (band && band.symbol) || "";
        if (!symbol) { return body; }
        return band.symbol_before ? symbol + body : body + " " + symbol;
    }

    _rulerSet(scope, band, count, plain) {
        const axis = (scope && scope.axis) || {};
        const low = Number(axis.min) || 0;
        const span = axisSpan(axis);
        const step = span / (count - 1);
        const unit = plain ? { div: 1, suffix: "" }
            : this._rulerUnit(low + span);
        // The number of figures comes from the SPAN, not from the magnitude:
        // a ruler over 6.60M to 6.68M has to print five different labels, and
        // one decimal at millions would print "6.6M" five times.
        const decimals = plain ? 0 : Math.max(0, Math.min(
            RULER_MAX_DECIMALS,
            Math.ceil(-Math.log10(step / unit.div)) + 1));
        const ticks = [];
        for (let i = 0; i < count; i += 1) {
            const value = low + (step * i);
            ticks.push({
                value,
                pct: (i / (count - 1)) * 100,
                label: this._unitMoney(value, band, unit, decimals),
                first: i === 0,
                last: i === count - 1,
            });
        }
        return ticks;
    }

    /**
     * The ruler under an opened band, in the band's own money.
     *
     * IT MAY NOT PRINT THE SAME LABEL TWICE. Five ticks are tried first (three
     * in dense rows), and if two of them would read the same the ruler drops
     * to fewer ticks rather than tell the reader that two different amounts
     * are the same amount. If even two ends cannot be told apart in rounded
     * money, it stops rounding and prints them in full.
     */
    rulerTicks(scope, band) {
        const wanted = this.shape.ruler;
        for (const count of [wanted, 3, 2]) {
            if (count > wanted) { continue; }
            const ticks = this._rulerSet(scope, band, count, false);
            if (new Set(ticks.map((t) => t.label)).size === ticks.length) {
                return ticks;
            }
        }
        return this._rulerSet(scope, band, 2, true);
    }

    /**
     * The hairline above an opened band: the whole shared axis, with the
     * slice this zoom covers filled in.
     *
     * This is the cheapest thing on the screen and it is what makes the zoom
     * feel honest — a reader can always see how much of the company's pay
     * they are looking at. A very narrow zoom would draw a segment nobody can
     * see, so it never draws thinner than two pixels.
     */
    locatorStyle(group, band) {
        const zoom = this.state.zoom;
        const lane = (group && group.laneAxis) || (group && group.axis);
        if (!zoom || !lane) { return "left:0%;width:100%"; }
        const shared = { axis: lane };
        const left = this.axisPct(shared, zoom.axis.min);
        const right = this.axisPct(shared, zoom.axis.max);
        const width = this.state.widths[this.bandKey(band)] || 0;
        const least = width ? (LOCATOR_MIN_PX / width) * 100 : 0.4;
        return "left:" + left + "%;width:"
            + Math.min(100 - left, Math.max(least, right - left)) + "%";
    }

    locatorTitle(group) {
        const lane = (group && group.laneAxis) || (group && group.axis) || {};
        return _t(
            "Where this band sits on the shared money scale, which runs to "
            + "%(top)s.", { top: (lane.ticks && lane.ticks.length
                ? lane.ticks[lane.ticks.length - 1].label : "") });
    }

    // ------------------------------------------------------ what it all says
    /** Said out loud while the ruler is this band's own, in the same voice
     *  the family warning already uses. */
    zoomSentence(group) {
        if (group && group.fitted) {
            return _t(
                "This band is drawn on its own money scale, narrower than "
                + "this family's, so its width no longer compares with the "
                + "other bands.");
        }
        return _t(
            "This band is drawn on its own money scale, so its width no "
            + "longer compares with the others.");
    }

    /**
     * The tails, in the voice of the lane's own axis note.
     *
     * A zoom has a LEFT-hand tail as well as a right-hand one, which the
     * shared axis never does, and a picture that stands somebody on an edge
     * has to say how many it put there.
     */
    zoomTails(band) {
        const zoom = this.state.zoom;
        if (!zoom) { return ""; }
        const said = [];
        if (zoom.below) {
            const edge = this.shortMoney(zoom.axis.min, band);
            said.push(zoom.below === 1
                ? _t("1 person is paid less than %(edge)s and sits on the "
                     + "left-hand edge. Their own pay is on their label.",
                     { edge })
                : _t("%(count)s people are paid less than %(edge)s and sit "
                     + "on the left-hand edge. Their own pay is on their "
                     + "label.", { count: zoom.below, edge }));
        }
        if (zoom.above) {
            const edge = this.shortMoney(zoom.axis.max, band);
            said.push(zoom.above === 1
                ? _t("1 person is paid more than %(edge)s and sits on the "
                     + "right-hand edge. Their own pay is on their label.",
                     { edge })
                : _t("%(count)s people are paid more than %(edge)s and sit "
                     + "on the right-hand edge. Their own pay is on their "
                     + "label.", { count: zoom.above, edge }));
        }
        return said.join(" ");
    }

    /** A band with nobody on it still opens, still draws its range on its own
     *  scale, and says which of the two empty things it is. */
    zoomEmpty(band) {
        return (band.wages || []).length ? "" : _t("Nobody is on this band yet.");
    }

    /** Everything the opened row says AFTER the warning, as ONE string.
     *  Two adjacent template nodes are read out as one run-on word by a
     *  screen reader even when the eye sees a gap (ledger GR22). */
    zoomExtra(band) {
        return [this.zoomEmpty(band), this.zoomTails(band)]
            .filter(Boolean).join(" ");
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
        // The axis OBJECT, not just its top: an opened band's ruler does not
        // start at zero, and a mark measured from zero on it lands nowhere
        // near the person it is drawing.
        const axis = (scope && scope.axis) || {};
        const now = this.live(band);
        if (!width) { return { kind: "waiting", key, parts: [], dots: [] }; }
        const dots = band.dots || [];
        if (dots.length && dots.length <= 24) {
            return {
                kind: "dots", key, parts: [],
                dots: dodgeDots(dots, axis, width, shape.gap),
            };
        }
        const bins = binPeople(band.wages || [], axis, width, shape.bin, now);
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
        // The two figures come from the BIN's own width, not from the size of
        // the money. On a lane axis a bin is a million dong wide and "9.0M ₫"
        // is exactly right; on an opened band it is fifty thousand, and
        // "9.0M ₫ to 9.0M ₫" is a picture telling a reader that two different
        // amounts are the same amount.
        const spread = part.bin.high - part.bin.low;
        return [
            part.count === 1 ? _t("1 person")
                : _t("%(count)s people", { count: part.count }),
            _t("%(low)s to %(high)s", {
                low: this.fineMoney(part.bin.low, band, spread),
                high: this.fineMoney(part.bin.high, band, spread),
            }),
            this.stateWord(part.state),
        ].join(" · ");
    }

    /** Short money with enough figures to tell two amounts `spread` apart. */
    fineMoney(value, band, spread) {
        const unit = this._rulerUnit(value);
        if (unit.div === 1) { return this.shortMoney(value, band); }
        const step = Math.abs(Number(spread) || 0);
        const decimals = step > 0
            ? Math.max(1, Math.min(RULER_MAX_DECIMALS,
                                   Math.ceil(-Math.log10(step / unit.div)) + 1))
            : 1;
        return this._unitMoney(value, band, unit, decimals);
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
        // Dragging an edge inside a forty-pixel sliver is the exact thing
        // this phase exists to stop, so a drag OPENS the row and pins it —
        // and the ruler it opens on carries headroom at both ends, because an
        // edge that cannot be dragged past the end of its own picture is a
        // wall the reader cannot see (ruling R2, deliverable 2e).
        const before = this.state.zoom;
        const axis = this._openForDrag(band, scope, side);
        const low = Number(axis.min) || 0;
        const high = Number(axis.max);
        const track = this.trackRefs[this.bandKey(band)];
        const box = track ? track.getBoundingClientRect() : null;
        const held = side === "min" ? band.min : band.max;
        let grab = 0;
        if (box && box.width && high > low) {
            // How far the cursor is from the grip ON THE NEW RULER. The
            // gesture then moves the edge by how far the HAND moves, never to
            // wherever the cursor happens to sit — so re-scaling the row at
            // the moment of the press cannot change anybody's band before a
            // person has dragged anything at all.
            const at = box.left + (((held - low) / (high - low)) * box.width);
            grab = ev.clientX - at;
        }
        this.state.drag = {
            bandId: band.id, key: this.bandKey(band), side,
            lo: low, hi: high, grab, zoomBefore: before,
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
        const at = (ev.clientX - (drag.grab || 0)) - box.left;
        const ratio = Math.max(0, Math.min(1, at / box.width));
        // The axis was worked out ONCE, at the press, and is frozen for the
        // gesture: an axis recomputed under the moving hand makes the grip
        // run away from the cursor.
        this._applyEdge(drag, drag.lo + (ratio * ((drag.hi - drag.lo) || 1)));
    }

    /** Escape during a gesture puts the numbers back and returns the row to
     *  the ruler it was on before the press. */
    _cancelDrag() {
        const drag = this.state.drag;
        if (!drag) { return; }
        this.state.drag = null;
        this.state.preview = null;
        if (drag.zoomBefore) {
            this.state.zoom = drag.zoomBefore;
            this.state.open = drag.zoomBefore.key;
            this._markUnrolling(drag.key);
        } else {
            this.closeBand();
        }
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
        if (!moved) {
            this.state.preview = null;
            // Nothing moved, so nothing is read again — but the ruler this row
            // is drawn on still has to lose the gesture's headroom.
            this._refreshZoom();
            return;
        }
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

    /** Arrows nudge an edge by a hundredth of the ruler the band is DRAWN on;
     *  Shift by a twentieth. On an opened band that is a far finer nudge than
     *  on the shared axis, which is exactly what somebody who has zoomed in
     *  is asking for. Enter saves, Escape puts it back — the keyboard reaches
     *  the hero and reaches it at the same resolution as the mouse. */
    onGripKey(scope, band, side, ev) {
        if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight"
                && ev.key !== "Enter" && ev.key !== "Escape") {
            return;
        }
        if (ev.key === "Escape") {
            if (this.state.drag) { this._cancelDrag(); ev.stopPropagation(); }
            return;
        }
        if (ev.key === "Enter") { this.endDrag(); return; }
        ev.preventDefault();
        let drag = this.state.drag;
        if (!drag || drag.bandId !== band.id) {
            const before = this.state.zoom;
            const axis = this._openForDrag(band, scope, side);
            drag = {
                bandId: band.id, key: this.bandKey(band), side, grab: 0,
                lo: Number(axis.min) || 0, hi: Number(axis.max),
                zoomBefore: before,
                min: band.min, mid: band.mid, max: band.max,
                before: { min: band.min, mid: band.mid, max: band.max },
            };
        }
        const step = ((drag.hi - drag.lo) || 1) * (ev.shiftKey ? 0.05 : 0.01);
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
        // This listener is registered in the CAPTURE phase (WFPLAN WF4), so
        // it runs BEFORE the grip's own handler — which means a gesture in
        // flight has to be the first rung, or a grip could never be let go
        // of with the keyboard once a band was open underneath it.
        if (this.state.drag) {
            this._cancelDrag();
            ev.stopPropagation();
            return;
        }
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
        if (this.state.undo) {
            this.state.undo = null;
            ev.stopPropagation();
            return;
        }
        // The opened band is the OUTERMOST thing this ladder closes: it is
        // the widest change to the screen and the last one a reader wants
        // taken away from them.
        if (this.state.open) { this.closeBand(); ev.stopPropagation(); }
    }
}

registry.category("actions").add("pb_pay", PbPayScreen);
