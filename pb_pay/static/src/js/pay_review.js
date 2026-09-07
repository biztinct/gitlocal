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
 * THE THIRD IS CALIBRATION. Every person is a dot — how well they did across,
 * the rise they are getting up. Drag a dot and its row follows. The dots that
 * are much higher than everybody who scored the same are ringed, because that
 * is the only question a calibration meeting is really asking.
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
    Component, onWillStart, useExternalListener, useState,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const REVIEWS = "pb.pay.reviews";

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

            calib: null,
            drag: null,
        });

        onWillStart(async () => {
            await this.load();
            if (this.props.focus === "awaiting") { this.state.view = "list"; }
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
            this.state.calib = await this.orm.call(
                REVIEWS, "calibration", [this.card.id]);
            this.state.view = "calibration";
        } catch (error) {
            this._fail(error, _t("The picture could not be drawn."));
        }
        this.state.busy = false;
    }

    backToWorksheet() {
        this.state.view = "review";
        this.state.calib = null;
        this.reopen();
    }

    /** Where one dot sits: its rating across, its rise up, spread sideways.
     *
     *  The sideways spread is the whole reason this picture is readable. A
     *  thousand people on four ratings land on four coordinates and the
     *  screen shows four dots; the jitter the server hands over — a number
     *  derived from the row's own id, so it never moves between reads — turns
     *  each stack back into the cloud a calibration meeting is looking at.
     */
    dotStyle(dot) {
        const calib = this.state.calib || {};
        const levels = calib.levels || 4;
        const top = calib.max_pct || 1;
        const drag = this.state.drag;
        const pct = drag && drag.lineId === dot.line_id ? drag.pct : dot.pct;
        const band = 88 / levels;
        const column = (dot.column || 1) - 1;
        const across = 6 + column * band + (dot.jitter || 0.5) * band * 0.86;
        const up = Math.max(0, Math.min(96, (pct / top) * 92));
        return "left:" + across.toFixed(2) + "%;bottom:" + up.toFixed(2) + "%";
    }

    /** The four numbers up the side, so a height means something. */
    get scatterTicks() {
        const top = (this.state.calib || {}).max_pct || 1;
        return [1, 0.75, 0.5, 0.25, 0].map((share) => ({
            pct: (top * share).toFixed(1),
            style: "bottom:" + (share * 92).toFixed(2) + "%",
        }));
    }

    dotClass(dot) {
        return dot.outlier ? "pay-dot is-out" : "pay-dot";
    }

    startDrag(dot, ev) {
        if (!this.canWrite) { return; }
        ev.preventDefault();
        this.state.drag = { lineId: dot.line_id, pct: dot.pct,
                            name: dot.name };
    }

    onDrag(ev) {
        const drag = this.state.drag;
        if (!drag) { return; }
        const plot = document.querySelector(".pay-scatter");
        if (!plot) { return; }
        const box = plot.getBoundingClientRect();
        if (!box.height) { return; }
        const calib = this.state.calib || {};
        const ratio = Math.max(0, Math.min(
            1, (box.bottom - ev.clientY) / box.height));
        this.state.drag = { ...drag,
                            pct: Math.round(ratio * (calib.max_pct || 1)
                                            * 100) / 100 };
    }

    async endDrag() {
        const drag = this.state.drag;
        if (!drag) { return; }
        this.state.drag = null;
        try {
            const answer = await this.orm.call(REVIEWS, "set_proposals", [
                this.card.id, [{ line_id: drag.lineId, pct: drag.pct }]]);
            this._merge(answer);
            this.state.calib = await this.orm.call(
                REVIEWS, "calibration", [this.card.id]);
        } catch (error) {
            this._fail(error, _t("That change could not be saved."));
        }
    }

    get dragLabel() {
        const drag = this.state.drag;
        if (!drag) { return ""; }
        return _t("%(who)s · %(pct)s%%",
                  { who: drag.name, pct: drag.pct });
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
            if (this.anyDrawer) { this.closeDrawers(); ev.stopPropagation(); }
            else if (this.state.editing) { this.cancelEdit(); }
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
