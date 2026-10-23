/** @odoo-module **/
/**
 * "Review" and "Changes" — the second half of Pay.
 *
 * THE HERO IS THAT IT OPENS FULL. A new review for nine hundred people arrives
 * with a suggested rise already on every row, the budget meter already moving,
 * the fairness line already saying what this review would do to the gap, and
 * every row that breaks a limit already marked with the sentence that says
 * why. Nobody stares at an empty worksheet.
 *
 * THE SECOND HERO IS THE BLOCK GESTURE. Click a row, shift-click another, type
 * "+1" and press Enter: every row in between moves, and the meter, the
 * blockers and the fairness line move with them in one round trip. A pay
 * review is bulk work and a screen that makes you edit nine hundred boxes one
 * at a time is a screen nobody finishes.
 *
 * THE THIRD IS CALIBRATION, AND EVERYBODY IS ON IT. Each score is a column and
 * each column is the shape of its own rises: bins a few pixels tall, drawn one
 * mark per person where there are a handful and as a bar that says how many
 * where there are hundreds. The middle of each score is marked, every limit is
 * a line across the whole picture, and the handful of rises worth arguing
 * about are ringed on top and can be dragged. Nothing is ever left out and
 * nothing hides behind anything else: at four and a half thousand people the
 * picture changes shape rather than dropping anybody (LOOK rule 16).
 *
 * THE RULES THIS FILE KEEPS (the same five `pay_hub.js` keeps)
 *   * every icon from the shared `ic()` set — no emoji, no glyph arrows;
 *   * every sentence is ONE expression — adjacent string literals are a
 *     SyntaxError that takes the whole asset bundle with it;
 *   * Escape with `{ capture: true }`, because the platform's hotkey service
 *     claims it on `window` and stops propagation (WFPLAN WF4);
 *   * the refusal ladder is `error.data.message` → `error.message.data.message`
 *     → our own sentence; `error.message` is never a rung (ledger GR17);
 *   * everything the template reads lives in `useState` (ledger GR26).
 */
import {
    Component, onMounted, onPatched, onWillStart, onWillUnmount,
    useExternalListener, useRef, useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { binValues } from "@pb_pay/js/band_picture";

const REVIEWS = "pb.pay.reviews";

/**
 * THE CALIBRATION PICTURE, in pixels. Two sets, because a phone is not a
 * smaller desktop: the bins are shorter, the marks are smaller and fewer of
 * them fit side by side before a bin becomes a bar.
 *
 *   bin   how tall one bin of the rise axis is
 *   few   up to this many people in a bin, every one of them is drawn
 *   dot   how big one person's mark is
 *   gap   how far apart two marks in the same bin are placed
 *   base  the shortest a bar is drawn, in pixels either side of the centre
 *   lift  how much longer the busiest bin's bar is than the shortest
 *   room  how much of half a column a bar may fill
 */
const CAL = {
    normal: { bin: 7, few: 4, dot: 9, gap: 12, base: 7, lift: 40, room: 0.86 },
    phone: { bin: 6, few: 3, dot: 7, gap: 9, base: 5, lift: 22, room: 0.86 },
};

/** The plot leaves this much of its own height above the highest rise, so a
 *  mark at the top of the axis is not drawn half outside the picture. The
 *  ticks up the side use the same figure, or the numbers and the marks would
 *  disagree about what a height means. */
const PLOT_HEAD = 0.92;
/** How much of the axis a drag may travel INTO that headroom, so a rise can
 *  always be pushed past the top of the picture rather than hitting a wall
 *  nobody can see. The axis is worked out again on release. */
const DRAG_ROOM = 1 / PLOT_HEAD;
/** A column narrower than this cannot hold "middle of this score 5%" without
 *  writing it over its own people, so it keeps the tick and drops the words. */
const MEDIAN_LABEL_ROOM = 130;
/** Phones get the smaller picture whatever the screen is called. */
const PHONE_PX = 480;
/** Arrow keys move a rise by this much, and by five times as much with Shift. */
const KEY_STEP = 0.1;

/** Enough decimals to tell two percentages `spread` apart — a bin here is
 *  about a tenth of a point wide, and one decimal prints "7.0% to 7.0%" for
 *  two figures that are not the same figure (LOOK L4). */
function finePct(value, spread) {
    const step = Math.abs(Number(spread) || 0);
    const decimals = step > 0
        ? Math.max(0, Math.min(3, Math.ceil(-Math.log10(step)) + 1)) : 1;
    return (Number(value) || 0).toFixed(decimals);
}

/** The filters over the worksheet, in the order they are offered. */
export function filterDefs() {
    return [
        { key: "all", label: _t("Everybody") },
        { key: "mine", label: _t("My team") },
        { key: "unrated", label: _t("Not scored") },
        { key: "blocked", label: _t("Stops approval") },
        { key: "below_band", label: _t("Paid below the band") },
        { key: "no_rise", label: _t("No rise") },
    ];
}

/** The four things a manager does to a block of rows. */
export function bulkDefs() {
    return [
        { key: "guidance", icon: "sparkles", label: _t("Use the guidance") },
        { key: "nudge_up", icon: "arrowUp", label: _t("Add 1%") },
        { key: "nudge_down", icon: "arrowDown", label: _t("Take off 1%") },
        { key: "spread", icon: "sigma", label: _t("Share out what is left") },
    ];
}

export class PbPayReview extends Component {
    static template = "pb_pay.PbPayReview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this._settle = null;
        // The picture is MEASURED, never assumed: this screen sits inside a
        // hub whose rail can be collapsed, and the plot's height changes with
        // the viewport (WFPLAN W20).
        this.scatterRef = useRef("scatter");
        this._resize = null;
        // The shape, worked out once per set of numbers rather than on every
        // repaint: at four and a half thousand people a drag repaints on
        // every mouse move, and binning them thirty times a second for a
        // picture that has not changed is pure cost.
        this._plot = null;
        this._plotSig = "";
        // Which bins have already been asked who is standing in them, so a
        // cursor sweeping the picture asks once and not once a frame.
        this._asked = {};

        this.state = useState({
            loaded: false,
            busy: false,
            failed: "",
            dialogError: "",

            board: null,
            open: null,
            view: "list",

            // the new-review drawer
            drafting: null,
            // the paste drawer, the guidance drawer, the limits drawer
            pasting: null,
            guidance: null,
            limits: null,
            preview: null,
            sendBack: null,

            selection: [],
            anchor: 0,
            cursor: 0,
            editing: 0,
            editValue: "",
            nudge: "1",
            filters: { which: "all", text: "" },

            // ---- the calibration picture
            calib: null,
            // bumped whenever the picture's numbers are replaced, so the
            // shape is rebuilt then and not on every repaint
            calibRev: 0,
            calibBusy: false,
            // how big the plot really is, measured on paint and on resize
            plotW: 0,
            plotH: 0,
            // line_id → name, filled in for one bin at a time on demand: the
            // payload that draws the shape carries no names at all (R4)
            names: {},
            // the people standing in one bin, by name
            pop: null,
            drag: null,
        });

        onWillStart(async () => {
            await this.load();
            if (this.props.focus === "awaiting") { this.state.view = "list"; }
        });

        onMounted(() => {
            this._measurePlot();
            if (window.ResizeObserver) {
                this._resize = new ResizeObserver(() => this._measurePlot());
                if (this.scatterRef.el) { this._resize.observe(this.scatterRef.el); }
            }
            this._watchWindow = () => this._measurePlot();
            window.addEventListener("resize", this._watchWindow);
        });
        // A repaint can put the plot on screen for the first time, so it is
        // measured again — but only WRITTEN when a number really moved, or
        // the write patches, the patch measures, and the screen spins.
        onPatched(() => this._measurePlot());
        onWillUnmount(() => {
            if (this._hover) { clearTimeout(this._hover); this._hover = null; }
            if (this._resize) { this._resize.disconnect(); this._resize = null; }
            if (this._watchWindow) {
                window.removeEventListener("resize", this._watchWindow);
            }
        });

        useExternalListener(window, "keydown", (ev) => this.onKey(ev),
                            { capture: true });
        useExternalListener(window, "mousemove", (ev) => this.onDrag(ev));
        useExternalListener(window, "mouseup", () => this.endDrag());
    }

    ic(name, size = 16) { return ic(name, size); }

    get filterDefs() { return filterDefs(); }
    get bulkDefs() { return bulkDefs(); }

    // ================================================================ errors
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
            this.state.board = await this.orm.call(REVIEWS, "get_board", []);
            this.state.failed = "";
        } catch (error) {
            this.state.failed = this._msg(error, _t(
                "The pay reviews could not be read just now. Try again in a "
                + "moment."));
        }
        this.state.loaded = true;
    }

    get reviews() {
        const board = this.state.board;
        return (board && board.reviews) || [];
    }

    get awaiting() {
        const board = this.state.board;
        return (board && board.awaiting) || { count: 0, rows: [] };
    }

    get card() {
        const open = this.state.open;
        return (open && open.card) || null;
    }

    get rows() {
        const open = this.state.open;
        return (open && open.rows) || [];
    }

    get canWrite() {
        const open = this.state.open;
        return Boolean(open && open.can_write);
    }

    get actions() {
        const open = this.state.open;
        return (open && open.actions) || {};
    }

    async openReview(id, page = 0) {
        this.state.busy = true;
        try {
            this.state.open = await this.orm.call(REVIEWS, "open_review", [
                id, page, this.state.filters,
            ]);
            this.state.view = "review";
            this.state.selection = [];
            this.state.cursor = 0;
            this.state.anchor = 0;
        } catch (error) {
            this._fail(error, _t("That review could not be opened."));
        }
        this.state.busy = false;
    }

    async reopen(page) {
        const card = this.card;
        if (!card) { return; }
        await this.openReview(card.id, page === undefined
            ? this.state.open.page : page);
    }

    backToList() {
        this.state.open = null;
        this.state.calib = null;
        this.state.view = "list";
        this.load();
    }

    async setFilter(which) {
        this.state.filters = { ...this.state.filters, which };
        await this.reopen(0);
    }

    async setSearch(value) {
        this.state.filters = { ...this.state.filters, text: value || "" };
        await this.reopen(0);
    }

    // ============================================================ new review
    openDraft() {
        const board = this.state.board || {};
        const scopes = board.scopes || [];
        const guidance = board.guidance || [];
        this.state.drafting = {
            scope: scopes.length ? this.scopeValue(scopes[0]) : "",
            name: "",
            budget: "",
            guidance_id: guidance.length ? guidance[0].id : 0,
            effective_date: board.today || "",
        };
        this.state.dialogError = "";
    }

    scopeValue(scope) { return scope.kind + ":" + scope.ref; }

    setDraft(field, value) {
        this.state.drafting = { ...this.state.drafting, [field]: value };
    }

    async createReview() {
        const draft = this.state.drafting;
        if (!draft || !draft.scope) {
            this.state.dialogError = _t("Pick who the review covers first.");
            return;
        }
        const parts = String(draft.scope).split(":");
        this.state.busy = true;
        try {
            const answer = await this.orm.call(REVIEWS, "create_review", [{
                scope_kind: parts[0],
                scope_ref: parseInt(parts[1], 10) || 0,
                name: draft.name || "",
                budget_amount: parseFloat(draft.budget) || 0,
                guidance_id: draft.guidance_id || 0,
                effective_date: draft.effective_date || false,
            }]);
            this.state.drafting = null;
            await this.load();
            await this.openReview(answer.id);
            this.notif.add(answer.sentence, { type: "success" });
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That review could not be started."));
        }
        this.state.busy = false;
    }

    async makeGuidance() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "make_default_guidance", []);
            await this.load();
            this.state.guidance = answer.grid;
            this.notif.add(_t("Guidance created. Change any square you like."),
                           { type: "success" });
        } catch (error) {
            this._fail(error, _t("The guidance could not be created."));
        }
        this.state.busy = false;
    }

    // ============================================================= the grid
    isSelected(row) { return this.state.selection.includes(row.id); }

    rowClass(row, index) {
        const bits = ["pay-wsrow"];
        if (this.isSelected(row)) { bits.push("is-picked"); }
        if (index === this.state.cursor) { bits.push("is-here"); }
        if (row.blocked) { bits.push("is-stopped"); }
        return bits.join(" ");
    }

    pick(row, index, ev) {
        this.state.cursor = index;
        if (ev && ev.shiftKey) {
            const from = Math.min(this.state.anchor, index);
            const to = Math.max(this.state.anchor, index);
            this.state.selection = this.rows.slice(from, to + 1)
                .map((r) => r.id);
            return;
        }
        this.state.anchor = index;
        if (ev && (ev.ctrlKey || ev.metaKey)) {
            const already = this.state.selection.includes(row.id);
            this.state.selection = already
                ? this.state.selection.filter((id) => id !== row.id)
                : this.state.selection.concat([row.id]);
            return;
        }
        this.state.selection = [row.id];
    }

    selectAll() {
        this.state.selection = this.rows.map((r) => r.id);
    }

    clearSelection() { this.state.selection = []; }

    get selectionLabel() {
        const count = this.state.selection.length;
        if (!count) { return _t("Nothing selected"); }
        if (count === 1) { return _t("1 person selected"); }
        return _t("%s people selected", count);
    }

    startEdit(row, index) {
        if (!this.canWrite) { return; }
        this.state.cursor = index;
        this.state.editing = row.id;
        this.state.editValue = String(row.proposal_pct || 0);
    }

    onEditInput(value) { this.state.editValue = value; }

    async commitEdit(row) {
        const value = parseFloat(this.state.editValue);
        this.state.editing = 0;
        if (Number.isNaN(value)) { return; }
        await this.write([{ line_id: row.id, pct: value }]);
    }

    cancelEdit() { this.state.editing = 0; }

    // ------------------------------------------------------------ the writes
    async write(rows) {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "set_proposals", [this.card.id, rows]);
            this._merge(answer);
            const ids = rows.map((r) => r.line_id);
            const fresh = await this.orm.call(REVIEWS, "rows",
                                              [this.card.id, ids]);
            this._patchRows(fresh);
        } catch (error) {
            this._fail(error, _t("That change could not be saved."));
        }
        this.state.busy = false;
    }

    _merge(answer) {
        if (!answer || !this.state.open) { return; }
        this.state.open = {
            ...this.state.open,
            card: answer.card || this.state.open.card,
            blockers: answer.blockers || [],
            fairness_line: answer.fairness_line
                || this.state.open.fairness_line,
            actions: answer.actions || this.state.open.actions,
        };
    }

    _patchRows(fresh) {
        if (!fresh || !this.state.open) { return; }
        const byId = {};
        fresh.forEach((row) => { byId[row.id] = row; });
        this.state.open = {
            ...this.state.open,
            rows: this.state.open.rows.map((row) => byId[row.id] || row),
        };
    }

    async bulk(key) {
        const ids = this.state.selection.length
            ? this.state.selection : this.rows.map((r) => r.id);
        if (!ids.length) { return; }
        const step = parseFloat(this.state.nudge) || 1;
        this.state.busy = true;
        try {
            let answer = null;
            if (key === "guidance") {
                answer = await this.orm.call(
                    REVIEWS, "apply_guidance", [this.card.id, ids]);
            } else if (key === "spread") {
                answer = await this.orm.call(
                    REVIEWS, "spread_remaining", [this.card.id, ids,
                                                  "rating"]);
            } else {
                answer = await this.orm.call(REVIEWS, "nudge", [
                    this.card.id, ids,
                    key === "nudge_down" ? -step : step]);
            }
            this._merge(answer);
            const fresh = await this.orm.call(REVIEWS, "rows",
                                              [this.card.id, ids]);
            this._patchRows(fresh);
            if (answer && answer.sentence) {
                this.notif.add(answer.sentence, { type: "success" });
            }
        } catch (error) {
            this._fail(error, _t("That could not be done to those rows."));
        }
        this.state.busy = false;
    }

    // ============================================================= guidance
    async openGuidance() {
        const open = this.state.open;
        this.state.guidance = (open && open.guidance) || null;
        this.state.dialogError = "";
        if (!this.state.guidance) {
            this.state.dialogError = _t(
                "This review has no guidance behind it, so every row started "
                + "at nothing. Create one and the whole review fills in.");
        }
    }

    async saveCell(cell, value) {
        const pct = parseFloat(value);
        if (Number.isNaN(pct)) { return; }
        try {
            this.state.guidance = await this.orm.call(
                REVIEWS, "save_guidance_cell", [cell.id, pct]);
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That square could not be saved."));
        }
    }

    cellStyle(cell) {
        const pct = Math.max(0, Math.min(100, (cell.pct || 0) * 6));
        return "opacity:" + (0.12 + pct / 140);
    }

    // ================================================================ paste
    openPaste() {
        this.state.pasting = { text: "", answer: null };
        this.state.dialogError = "";
    }

    setPaste(value) {
        this.state.pasting = { ...this.state.pasting, text: value };
    }

    async checkPaste() {
        const job = this.state.pasting;
        if (!job || !job.text.trim()) { return; }
        try {
            const answer = await this.orm.call(REVIEWS, "paste_ratings", [
                this.card.id, job.text, true]);
            this.state.pasting = { ...job, answer };
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That list could not be read."));
        }
    }

    async commitPaste() {
        const job = this.state.pasting;
        if (!job || !job.answer || !job.answer.good) { return; }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(REVIEWS, "paste_ratings", [
                this.card.id, job.text, false]);
            this.state.pasting = null;
            await this.reopen();
            this.notif.add(answer.sentence, { type: "success" });
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "Those scores could not be saved."));
        }
        this.state.busy = false;
    }

    async syncRatings() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "sync_ratings", [this.card.id]);
            await this.reopen();
            this.notif.add(answer.sentence, { type: "info" });
        } catch (error) {
            this._fail(error, _t("The scores could not be read in."));
        }
        this.state.busy = false;
    }

    get pasteLabel() {
        const job = this.state.pasting;
        const answer = job && job.answer;
        return _t("Save the %(count)s good rows",
                  { count: (answer && answer.good) || 0 });
    }

    // =========================================================== calibration
    async openCalibration() {
        this.state.busy = true;
        try {
            this._setCalib(await this.orm.call(
                REVIEWS, "calibration", [this.card.id]));
            this.state.view = "calibration";
        } catch (error) {
            this._fail(error, _t("The picture could not be drawn."));
        }
        this.state.busy = false;
    }

    /** New numbers for the picture. The shape is rebuilt from them once,
     *  the names read back so far are kept (they cannot go stale — a name is
     *  not a figure), and the bins that were asked are asked again. */
    _setCalib(payload) {
        this.state.calib = payload;
        this.state.calibRev += 1;
        this._asked = {};
    }

    backToWorksheet() {
        this.state.view = "review";
        this.state.calib = null;
        this.state.pop = null;
        this.state.drag = null;
        this.reopen();
    }

    /** Which set of pixel sizes the picture is being drawn with. */
    get shape() {
        const narrow = window.innerWidth && window.innerWidth <= PHONE_PX;
        return narrow ? CAL.phone : CAL.normal;
    }

    /**
     * How big the plot really is.
     *
     * Written back into state only when a number actually changed:
     * `onPatched` runs after every render, and a state write that always
     * happens is a render that always happens again.
     */
    _measurePlot() {
        const el = this.scatterRef.el;
        if (!el) { return; }
        if (this.state.drag) { return; }
        const box = el.getBoundingClientRect();
        const width = Math.round(box.width);
        const height = Math.round(box.height);
        if (!width || !height) { return; }
        if (this.state.plotW !== width || this.state.plotH !== height) {
            this.state.plotW = width;
            this.state.plotH = height;
        }
        if (this._resize && this._resize.observe) {
            // The plot only exists while the picture is on screen, so the
            // observer is pointed at it the first time it appears.
            this._resize.observe(el);
        }
    }

    /**
     * THE SHAPE. Every person in the review, in whichever form draws them all.
     *
     * Per score column, the rise axis is cut into bins a few pixels tall by
     * the same arithmetic the band picture uses (`binValues`). A bin holding a
     * handful of people draws one mark each; a busier one draws a bar out
     * either side of the column's centre line whose length says how many, and
     * pressing it names the people standing in it. Every rise that stands out
     * or breaks a limit is ringed on top and can be dragged.
     *
     * NOBODY IS DROPPED, and the picture says so in a way a test can check:
     * every drawn element carries how many people it accounts for, a bar its
     * whole bin and a mark either one person or — when the same person is
     * also inside a bar — none. Those figures always add up to the number of
     * people in the review.
     */
    get plot() {
        const signature = [
            this.state.calibRev, this.state.plotW, this.state.plotH,
            window.innerWidth <= PHONE_PX ? "p" : "n",
            this.state.drag ? this.state.drag.lineId : 0,
            this.state.drag ? this.state.drag.pct : 0,
        ].join("|");
        if (this._plotSig !== signature || !this._plot) {
            this._plot = this._buildPlot();
            this._plotSig = signature;
        }
        return this._plot;
    }

    _buildPlot() {
        const calib = this.state.calib;
        const blank = { ready: false, columns: [], limits: [], drawn: 0,
                        total: 0, busiest: 0 };
        if (!calib) { return blank; }
        const width = this.state.plotW;
        const height = this.state.plotH;
        const people = calib.people || [];
        if (!width || !height) {
            return { ...blank, total: people.length };
        }
        const shape = this.shape;
        const levels = calib.levels || 4;
        const top = calib.max_pct || 1;
        const track = height * PLOT_HEAD;
        const bandPct = 88 / levels;
        const drag = this.state.drag;

        // One pass to split the people by column, with the person under the
        // hand carrying the figure the hand is holding rather than the one
        // that is saved.
        const byColumn = new Map();
        for (const person of people) {
            const column = Math.min(Math.max(person.column || 1, 1), levels);
            if (!byColumn.has(column)) { byColumn.set(column, []); }
            const pct = drag && drag.lineId === person.line_id
                ? drag.pct : person.pct;
            byColumn.get(column).push({ ...person, value: pct, pct });
        }

        const binned = new Map();
        let busiest = 0;
        for (const [column, list] of byColumn) {
            const bins = binValues(list, { min: 0, max: top }, track,
                                   shape.bin, (item) => item.state);
            binned.set(column, bins);
            for (const bin of bins) { busiest = Math.max(busiest, bin.count); }
        }

        const halfMax = (((bandPct / 100) * width) / 2) * shape.room;
        const span = Math.max(1, busiest - shape.few);
        const columns = [];
        let drawn = 0;
        for (let index = 1; index <= levels; index += 1) {
            const meta = (calib.columns || []).find(
                (one) => one.column === index) || {};
            const centre = 6 + ((index - 0.5) * bandPct);
            const bins = binned.get(index) || [];
            const bars = [];
            const marks = [];
            for (const bin of bins) {
                const spread = bin.high - bin.low;
                const exact = (person) => (drag && drag.lineId
                    === person.line_id ? (person.pct / top) * track : null);
                if (bin.count <= shape.few) {
                    bin.items.forEach((person, at) => marks.push(this._mark(
                        person, bin, index, centre, at, bin.items.length,
                        shape, width, 1, spread, exact(person))));
                    drawn += bin.count;
                    continue;
                }
                const half = Math.min(halfMax, shape.base + (shape.lift
                    * Math.sqrt((bin.count - shape.few) / span)));
                const halfPct = (half / width) * 100;
                const stands = bin.items.filter(
                    (person) => person.state !== "normal");
                bars.push({
                    // Keyed by WHERE it is, never by what it holds: a key
                    // that carries the count makes every change a new
                    // element, and a new element replays its own arrival —
                    // the picture would flicker under the dragging hand.
                    key: "b" + index + ":" + bin.index,
                    column: index, count: bin.count,
                    // A STRING, deliberately. OWL drops an attribute whose
                    // value is boolean false (L1) and a number is one
                    // careless truthiness test away from the same fate — and
                    // this attribute is how "nobody was left out" is proved.
                    people: "" + bin.count,
                    low: bin.low, high: bin.high,
                    stands: stands.length,
                    style: "left:" + (centre - halfPct).toFixed(3)
                        + "%;width:" + (halfPct * 2).toFixed(3)
                        + "%;bottom:" + bin.x0.toFixed(1) + "px;height:"
                        + Math.max(2, bin.x1 - bin.x0).toFixed(1) + "px",
                    title: this._barTitle(bin, index, spread),
                });
                drawn += bin.count;
                // The rises worth arguing about are ringed on top of the bar
                // they are already counted in, so they carry no count of
                // their own and the arithmetic still adds up. A bin seven
                // pixels tall can only hold a few rings before they draw over
                // each other, so it rings the first few.
                const pins = stands.slice(0, shape.few);
                // THE ONE UNDER THE HAND IS ALWAYS DRAWN, wherever the
                // gesture has taken it. Without this, dragging a mark into a
                // busy bin that already has its few rings takes the mark out
                // of the picture mid-gesture — the hand is still moving
                // something and there is nothing on the screen to see.
                if (drag) {
                    const held = bin.items.find(
                        (person) => person.line_id === drag.lineId);
                    if (held && !pins.includes(held)) { pins.unshift(held); }
                }
                pins.forEach((person, at) => marks.push(
                    this._mark(person, bin, index, centre, at, pins.length,
                               shape, width, 0, spread, exact(person))));
            }
            const medianTop = ((meta.median || 0) / top) * track;
            columns.push({
                index,
                key: "c" + index,
                word: meta.word || String(index),
                scored: meta.scored || 0,
                drawn: (byColumn.get(index) || []).length,
                unscored: meta.unscored || 0,
                hasMedian: Boolean(meta.has_median),
                medianLabel: meta.median_label || "",
                medianStyle: "left:" + (centre - (bandPct / 2)).toFixed(3)
                    + "%;width:" + bandPct.toFixed(3) + "%;bottom:"
                    + medianTop.toFixed(1) + "px",
                roomy: ((bandPct / 100) * width) >= MEDIAN_LABEL_ROOM,
                style: "left:" + (6 + ((index - 1) * bandPct)).toFixed(3)
                    + "%;width:" + bandPct.toFixed(3) + "%",
                centreStyle: "left:" + centre.toFixed(3) + "%",
                bars, marks,
            });
        }

        const limits = (calib.limits || []).map((one) => ({
            ...one,
            style: "bottom:" + (((one.value || 0) / top) * track).toFixed(1)
                + "px",
        }));
        let standsOut = 0;
        let blocked = 0;
        for (const person of people) {
            if (person.state === "outlier") { standsOut += 1; }
            if (person.state === "blocked") { blocked += 1; }
        }
        return { ready: true, columns, limits, drawn, busiest, standsOut,
                 blocked, total: people.length, track };
    }

    /** One person, drawn as their own mark. `counted` is 1 when this mark is
     *  the only thing on the picture standing for them, and 0 when they are
     *  also inside the bar underneath it. */
    _mark(person, bin, column, centre, at, of, shape, width, counted, spread,
          exact) {
        const step = (shape.gap / width) * 100;
        const offset = (at - ((of - 1) / 2)) * step;
        // A mark sits at the middle of its own bin — except the one under the
        // hand, which sits at the exact figure the hand is holding. A bin is
        // seven pixels tall, and a gesture that answers in seven-pixel steps
        // reads as a mark that will not follow.
        const up = exact === null || exact === undefined
            ? bin.x0 + ((bin.x1 - bin.x0) / 2) : exact;
        return {
            key: "m" + person.line_id,
            lineId: person.line_id,
            column, counted,
            people: counted ? "1" : "0",
            state: person.state,
            pct: person.pct,
            low: bin.low, high: bin.high, binIndex: bin.index,
            style: "left:" + (centre + offset).toFixed(3) + "%;bottom:"
                + up.toFixed(1) + "px",
            spread,
        };
    }

    _barTitle(bin, column, spread) {
        const word = this.columnWord(column);
        // WF24: the platform's own sprintf escapes `%%` for a POSITIONAL
        // substitution and NOT for a keyed one, so a sentence handed a
        // dictionary writes ONE per cent sign. Written with two it renders
        // "0.00%% to 0.30%%" on the screen, and nothing warns.
        return _t("%(count)s people scored %(word)s, rising %(low)s% to "
                  + "%(high)s% · press to see who", {
            count: bin.count, word,
            low: finePct(bin.low, spread), high: finePct(bin.high, spread),
        });
    }

    /** WHAT THIS PICTURE PROMISES, and it has to be true at every size. The
     *  old sentence — "every person is a dot, drag one and its row follows" —
     *  stopped being true the moment there were more people than dots. */
    get calibPromise() {
        if (!this.canWrite) {
            return _t(
                "Every person in this review is on the picture. Each score is "
                + "a column and the shape is how its rises are spread; press "
                + "a bar to see who is standing there.");
        }
        return _t(
            "Every person in this review is on the picture. Each score is a "
            + "column and the shape is how its rises are spread. Press a bar "
            + "to see who is standing there, and drag a ringed mark to change "
            + "that rise.");
    }

    /** Said out loud under the picture, because "nobody was left out" is the
     *  whole point and a reader should not have to take it on trust. */
    get drawnSentence() {
        const pic = this.plot;
        if (!pic.ready) { return ""; }
        if (pic.total === 1) {
            return _t("The one person in this review is on the picture.");
        }
        return _t("All %(count)s people in this review are on the picture.",
                  { count: pic.total });
    }

    /** The legend beside the picture, in words and with the count, because a
     *  ring on its own is not a message anybody is obliged to be able to
     *  read. */
    get standsOutLabel() {
        const count = this.plot.standsOut;
        return count === 1
            ? _t("1 rise stands out from the others who scored the same")
            : _t("%(count)s rises stand out from the others who scored the "
                 + "same", { count });
    }

    get blockedLabel() {
        const count = this.plot.blocked;
        return count === 1
            ? _t("1 rise breaks a limit")
            : _t("%(count)s rises break a limit", { count });
    }

    isHeld(mark) {
        const drag = this.state.drag;
        return Boolean(drag && drag.lineId === mark.lineId);
    }

    columnWord(column) {
        const words = (this.state.calib || {}).words || [];
        return words[column - 1] || String(column);
    }

    stateWord(state) {
        if (state === "blocked") { return _t("breaks a limit"); }
        if (state === "outlier") { return _t("stands out"); }
        return _t("in line with the others");
    }

    markClass(mark) {
        const known = this.state.drag && this.state.drag.lineId === mark.lineId;
        return "pay-cdot is-" + mark.state + (known ? " is-held" : "");
    }

    markTitle(mark) {
        const name = this.state.names[mark.lineId];
        return [name || _t("Reading who this is…"),
                _t("%(pct)s% rise", { pct: mark.pct }),
                this.stateWord(mark.state)].join(" · ");
    }

    /** A cursor sweeping the picture crosses dozens of marks; only the one it
     *  SETTLES on is worth a round trip. Same reasoning, and the same
     *  settling time, as opening a band out on hover. */
    hoverMark(mark) {
        if (this._hover) { clearTimeout(this._hover); }
        this._hover = setTimeout(() => {
            this._hover = null;
            this.nameMark(mark);
        }, 220);
    }

    leaveMark() {
        if (this._hover) { clearTimeout(this._hover); this._hover = null; }
    }

    /** A mark under the cursor or the keyboard says who it is. The shape
     *  itself carries no names at all, so the bin it belongs to is asked
     *  once — and only once, however long the cursor rests on it. */
    async nameMark(mark) {
        const key = mark.column + ":" + mark.binIndex;
        if (this._asked[key] || this.state.names[mark.lineId]) { return; }
        this._asked[key] = true;
        try {
            const answer = await this.orm.call(REVIEWS, "calibration_people", [
                this.card.id, mark.column, mark.low, mark.high]);
            const found = { ...this.state.names };
            (answer.rows || []).forEach((row) => { found[row.id] = row.name; });
            this.state.names = found;
        } catch (error) {
            // The mark keeps its figure and its state word; it simply does
            // not learn a name. Nothing on the picture is lost.
            this._asked[key] = false;
        }
    }

    /** The numbers up the side, so a height means something. */
    get scatterTicks() {
        const top = (this.state.calib || {}).max_pct || 1;
        const step = top / 4;
        return [1, 0.75, 0.5, 0.25, 0].map((share) => ({
            pct: finePct(top * share, step),
            style: "bottom:" + (share * PLOT_HEAD * 100).toFixed(2) + "%",
        }));
    }

    /** The count under each column, in words rather than a bare figure. */
    columnCount(column) {
        if (!column.drawn) { return _t("nobody scored this"); }
        if (column.unscored) {
            return column.drawn === 1
                ? _t("1 person, nobody scored them")
                : _t("%(count)s people, %(unscored)s not scored", {
                    count: column.drawn, unscored: column.unscored });
        }
        return column.drawn === 1
            ? _t("1 person") : _t("%(count)s people", { count: column.drawn });
    }

    // -------------------------------------------------- who is standing here
    async openBin(bar) {
        this.state.pop = { busy: true, rows: [], total: bar.count, more: 0,
                           more_label: "", failed: "",
                           title: this._barTitle(
                               { count: bar.count, low: bar.low,
                                 high: bar.high },
                               bar.column, bar.high - bar.low),
                           column: bar.column, low: bar.low, high: bar.high };
        try {
            const answer = await this.orm.call(REVIEWS, "calibration_people", [
                this.card.id, bar.column, bar.low, bar.high]);
            const found = { ...this.state.names };
            (answer.rows || []).forEach((row) => { found[row.id] = row.name; });
            this.state.names = found;
            if (!this.state.pop) { return; }
            this.state.pop = { ...this.state.pop, ...answer, busy: false };
        } catch (error) {
            if (!this.state.pop) { return; }
            this.state.pop = {
                ...this.state.pop, busy: false,
                failed: this._msg(error, _t(
                    "Those people could not be read just now. Close this and "
                    + "press the bar again.")),
            };
        }
    }

    closeBin() { this.state.pop = null; }

    /** One row of the panel, adjusted in place. The picture and the meters
     *  both follow, because they are read again from the same write. */
    async setFromBin(row, value) {
        const pct = parseFloat(value);
        if (Number.isNaN(pct) || pct === row.pct) { return; }
        await this._saveRise(row.id, pct);
        const open = this.state.pop;
        if (open) { await this.openBin(open); }
    }

    // ---------------------------------------------------------- the gesture
    startDrag(mark, ev) {
        if (!this.canWrite) { return; }
        if (ev) { ev.preventDefault(); }
        // The bar at the foot has to say WHO is being moved, so a mark that
        // has not been asked its name yet is asked now.
        this.nameMark(mark);
        this.state.drag = { lineId: mark.lineId, pct: mark.pct,
                            was: mark.pct, keys: false };
    }

    onDrag(ev) {
        const drag = this.state.drag;
        if (!drag || drag.keys) { return; }
        const el = this.scatterRef.el;
        if (!el) { return; }
        const box = el.getBoundingClientRect();
        if (!box.height) { return; }
        const top = (this.state.calib || {}).max_pct || 1;
        // The marks are drawn inside 92% of the plot, so a hand that has
        // moved a tenth of the picture has to move the rise by a tenth of the
        // axis — and it may travel INTO the headroom above the highest rise,
        // because a picture with a wall in it is a dead end (P1's R5).
        const ratio = (box.bottom - ev.clientY) / box.height / PLOT_HEAD;
        const pct = Math.max(0, Math.min(DRAG_ROOM, ratio)) * top;
        this.state.drag = { ...drag, pct: Math.round(pct * 100) / 100 };
    }

    async endDrag() {
        const drag = this.state.drag;
        if (!drag || drag.keys) { return; }
        this.state.drag = null;
        if (drag.pct === drag.was) { return; }
        await this._saveRise(drag.lineId, drag.pct);
    }

    /**
     * ONE WRITE, AND THE PICTURE FOLLOWS IT.
     *
     * The changed figure is put into the loaded payload first so the mark
     * does not jump back to where it was while the round trip happens, and
     * the whole picture is then read again — the medians, the limits and what
     * counts as standing out all move when one rise does, and a picture that
     * showed the new mark against the old middle would be lying about the
     * only comparison it exists to make.
     */
    async _saveRise(lineId, pct) {
        this._patchPerson(lineId, pct);
        this.state.calibBusy = true;
        try {
            const answer = await this.orm.call(REVIEWS, "set_proposals", [
                this.card.id, [{ line_id: lineId, pct }]]);
            this._merge(answer);
            this._setCalib(await this.orm.call(
                REVIEWS, "calibration", [this.card.id]));
        } catch (error) {
            this._fail(error, _t("That change could not be saved."));
            try {
                this._setCalib(await this.orm.call(
                    REVIEWS, "calibration", [this.card.id]));
            } catch (again) {
                // The picture keeps what it had; the sentence above already
                // said what went wrong and the worksheet is one press away.
            }
        }
        this.state.calibBusy = false;
    }

    _patchPerson(lineId, pct) {
        const calib = this.state.calib;
        if (!calib) { return; }
        this.state.calib = {
            ...calib,
            people: (calib.people || []).map((person) => person.line_id
                === lineId ? { ...person, pct } : person),
        };
        this.state.calibRev += 1;
    }

    /** The keyboard reaches the picture at the same resolution as the mouse:
     *  arrows move a rise by a tenth of a point, Shift by half a point, Enter
     *  saves it and Escape puts it back. */
    onMarkKey(mark, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            if (this.state.drag && this.state.drag.lineId === mark.lineId) {
                ev.preventDefault();
                const held = this.state.drag;
                this.state.drag = null;
                if (held.pct !== held.was) {
                    this._saveRise(held.lineId, held.pct);
                }
                return;
            }
            return;
        }
        if (ev.key === "Escape") {
            if (this.state.drag) {
                this.state.drag = null;
                ev.stopPropagation();
            }
            return;
        }
        if (ev.key !== "ArrowUp" && ev.key !== "ArrowDown") { return; }
        if (!this.canWrite) { return; }
        ev.preventDefault();
        const step = (ev.shiftKey ? KEY_STEP * 5 : KEY_STEP)
            * (ev.key === "ArrowUp" ? 1 : -1);
        const drag = this.state.drag && this.state.drag.lineId === mark.lineId
            ? this.state.drag
            : { lineId: mark.lineId, pct: mark.pct, was: mark.pct,
                keys: true };
        this.state.drag = { ...drag, keys: true,
                            pct: Math.max(0, Math.round(
                                (drag.pct + step) * 100) / 100) };
    }

    get dragLabel() {
        const drag = this.state.drag;
        if (!drag) { return ""; }
        const name = this.state.names[drag.lineId];
        return name
            ? _t("%(who)s · %(pct)s%", { who: name, pct: drag.pct })
            : _t("This rise · %(pct)s%", { pct: drag.pct });
    }

    get dragNote() {
        return this.state.drag && this.state.drag.keys
            ? _t("Enter to save it, Escape to put it back.")
            : _t("Let go to save it. Nothing has changed yet.");
    }

    // ============================================================= the chain
    async act(what) {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "act", [this.card.id, what]);
            this._merge(answer);
            this.state.open = { ...this.state.open,
                                trail: answer.trail || [] };
            this.notif.add(answer.sentence, { type: "success" });
        } catch (error) {
            this._fail(error, _t("That step could not be taken."));
        }
        this.state.busy = false;
    }

    openSendBack() {
        this.state.sendBack = { note: "", what: "send_back" };
        this.state.dialogError = "";
    }

    /** Drop a review nobody is going to run. Same drawer, same reason box. */
    openDrop() {
        this.state.sendBack = { note: "", what: "drop" };
        this.state.dialogError = "";
    }

    get sendBackTitle() {
        const back = this.state.sendBack;
        return back && back.what === "drop"
            ? _t("Drop this review") : _t("Send it back");
    }

    get sendBackNote() {
        const back = this.state.sendBack;
        return back && back.what === "drop"
            ? _t("Say why it is being dropped. Nothing anybody proposed is "
                 + "deleted; the review simply stops here.")
            : _t("Say what has to change. Whoever wrote it sees this "
                 + "sentence.");
    }

    setSendBack(value) {
        this.state.sendBack = { ...this.state.sendBack, note: value };
    }

    async commitSendBack() {
        const back = this.state.sendBack;
        if (!back || !back.note.trim()) {
            this.state.dialogError = _t(
                "Say why it is going back. A review that comes back with no "
                + "reason cannot be acted on.");
            return;
        }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "act", [this.card.id, back.what || "send_back",
                                 back.note]);
            this._merge(answer);
            this.state.sendBack = null;
            this.notif.add(answer.sentence, { type: "success" });
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That review could not be sent back."));
        }
        this.state.busy = false;
    }

    // ======================================================= apply and undo
    async openPreview() {
        this.state.busy = true;
        this.state.dialogError = "";
        try {
            this.state.preview = await this.orm.call(
                REVIEWS, "preview_apply", [this.card.id]);
        } catch (error) {
            this._fail(error, _t("The preview could not be worked out."));
        }
        this.state.busy = false;
    }

    async confirmApply() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "apply", [this.card.id]);
            this.state.preview = null;
            this._merge(answer);
            await this.reopen();
            this.notif.add(answer.sentence, { type: "success" });
            if (answer.note) {
                this.notif.add(answer.note, { type: "info" });
            }
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "The new pay could not be written."));
        }
        this.state.busy = false;
    }

    async undoApply() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "undo", [this.card.id]);
            this._merge(answer);
            await this.reopen();
            this.notif.add(answer.sentence, { type: "success" });
        } catch (error) {
            this._fail(error, _t("That could not be taken back."));
        }
        this.state.busy = false;
    }

    closeDrawers() {
        this.state.drafting = null;
        this.state.pasting = null;
        this.state.guidance = null;
        this.state.limits = null;
        this.state.preview = null;
        this.state.sendBack = null;
        this.state.dialogError = "";
    }

    get anyDrawer() {
        return Boolean(this.state.drafting || this.state.pasting
                       || this.state.guidance || this.state.limits
                       || this.state.preview || this.state.sendBack);
    }

    // ============================================================== keyboard
    onKey(ev) {
        if (ev.key === "Escape") {
            // THE LADDER, innermost first. This listener is registered in the
            // CAPTURE phase (WFPLAN WF4), so it runs BEFORE the focused
            // element's own handler — which means a gesture in flight has to
            // be the first rung, or a mark being moved with the keyboard
            // could never be let go of (LOOK L5).
            if (this.state.drag) {
                this.state.drag = null;
                ev.stopPropagation();
            } else if (this.state.pop) {
                this.closeBin();
                ev.stopPropagation();
            } else if (this.anyDrawer) {
                this.closeDrawers();
                ev.stopPropagation();
            } else if (this.state.editing) {
                this.cancelEdit();
            } else if (this.state.view === "calibration") {
                this.backToWorksheet();
                ev.stopPropagation();
            }
            return;
        }
        if (this.state.view !== "review" || this.state.editing) { return; }
        if (this.anyDrawer) { return; }
        const rows = this.rows;
        if (!rows.length) { return; }
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const next = Math.max(0, Math.min(
                rows.length - 1,
                this.state.cursor + (ev.key === "ArrowDown" ? 1 : -1)));
            this.state.cursor = next;
            if (ev.shiftKey) {
                const from = Math.min(this.state.anchor, next);
                const to = Math.max(this.state.anchor, next);
                this.state.selection = rows.slice(from, to + 1)
                    .map((r) => r.id);
            } else {
                this.state.anchor = next;
                this.state.selection = [rows[next].id];
            }
            return;
        }
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.startEdit(rows[this.state.cursor], this.state.cursor);
            return;
        }
        if (ev.key === "+" || ev.key === "=") {
            ev.preventDefault();
            this.bulk("nudge_up");
            return;
        }
        if (ev.key === "-") {
            ev.preventDefault();
            this.bulk("nudge_down");
        }
    }
}

/**
 * "Changes" — one person's pay, moved outside a review.
 *
 * A separate component rather than a fifth mode of the one above, because it
 * is a different shape of work: one person, one number, one reason. Sharing a
 * component would mean every getter asking "which of the two am I".
 */
export class PbPayChanges extends Component {
    static template = "pb_pay.PbPayChanges";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loaded: false,
            busy: false,
            failed: "",
            dialogError: "",
            changes: [],
            canWrite: false,
            canApply: false,
            open: null,
            drafting: null,
            people: [],
            search: "",
        });

        onWillStart(async () => {
            await this.load();
            if (this.props.focus === "new_change") { this.openDraft(); }
        });
        useExternalListener(window, "keydown", (ev) => this.onKey(ev),
                            { capture: true });
    }

    ic(name, size = 16) { return ic(name, size); }

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

    async load() {
        try {
            const board = await this.orm.call(REVIEWS, "get_board", []);
            this.state.changes = board.changes || [];
            this.state.canWrite = Boolean(board.can_write);
            this.state.canApply = Boolean(board.can_apply);
            this.state.failed = "";
        } catch (error) {
            this.state.failed = this._msg(error, _t(
                "The pay changes could not be read just now."));
        }
        this.state.loaded = true;
    }

    openDraft() {
        this.state.drafting = {
            employee_id: 0, employee: "", kind: "promotion",
            new_wage: "", effective_date: "", reason: "", ready: null,
        };
        this.state.dialogError = "";
        this.searchPeople("");
    }

    async searchPeople(text) {
        this.state.search = text || "";
        try {
            this.state.people = await this.orm.call(
                REVIEWS, "people_for_change", [text || ""]);
        } catch (error) {
            this.state.people = [];
        }
    }

    async choosePerson(person) {
        this.state.busy = true;
        try {
            const ready = await this.orm.call(
                REVIEWS, "prepare_change", [person.id]);
            this.state.drafting = {
                ...this.state.drafting,
                employee_id: person.id, employee: person.name,
                new_wage: String(ready.current_wage || 0),
                ready,
            };
            this.state.dialogError = ready.blocked_note || "";
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That person could not be read."));
        }
        this.state.busy = false;
    }

    setDraft(field, value) {
        this.state.drafting = { ...this.state.drafting, [field]: value };
    }

    get draftPct() {
        const draft = this.state.drafting;
        const ready = draft && draft.ready;
        if (!ready || !ready.current_wage) { return "0.0"; }
        const now = parseFloat(draft.new_wage) || 0;
        return ((now - ready.current_wage) / ready.current_wage * 100)
            .toFixed(1);
    }

    async createChange() {
        const draft = this.state.drafting;
        if (!draft || !draft.employee_id) {
            this.state.dialogError = _t("Pick the person first.");
            return;
        }
        this.state.busy = true;
        try {
            const made = await this.orm.call(REVIEWS, "create_change", [{
                employee_id: draft.employee_id,
                kind: draft.kind,
                new_wage: parseFloat(draft.new_wage) || 0,
                effective_date: draft.effective_date || false,
                reason: draft.reason || "",
            }]);
            this.state.drafting = null;
            await this.load();
            this.state.open = made;
            this.notif.add(_t("Pay change written. Send it for approval when "
                              + "you are ready."), { type: "success" });
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That pay change could not be written."));
        }
        this.state.busy = false;
    }

    openChange(change) { this.state.open = change; }

    closeDrawers() {
        this.state.drafting = null;
        this.state.open = null;
        this.state.dialogError = "";
    }

    async act(what) {
        const change = this.state.open;
        if (!change) { return; }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(
                REVIEWS, "change_act", [change.id, what]);
            this.state.open = answer;
            await this.load();
            if (answer.sentence) {
                this.notif.add(answer.sentence, { type: "success" });
            }
        } catch (error) {
            this.state.dialogError = this._msg(error, _t(
                "That step could not be taken."));
        }
        this.state.busy = false;
    }

    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.drafting || this.state.open) {
            this.closeDrawers();
            ev.stopPropagation();
        }
    }
}
