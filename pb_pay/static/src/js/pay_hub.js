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
    Component, onWillStart, useExternalListener, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { PbPayReview, PbPayChanges } from "@pb_pay/js/pay_review";

const BANDS = "pb.pay.bands";
const FAIRNESS = "pb.pay.fairness";

/** How long a drag waits before asking the server for the exact cost. */
const DRAG_SETTLE = 160;

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

    /** Where a value sits on a lane's axis, as a percentage of its width. */
    axisPct(lane, value) {
        const top = (lane.axis && lane.axis.max) || 1;
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

    rangeStyle(lane, band) {
        const now = this.live(band);
        const left = this.axisPct(lane, now.min);
        const right = this.axisPct(lane, now.max);
        return "left:" + left + "%;width:" + Math.max(0.4, right - left) + "%";
    }

    midStyle(lane, band) {
        return "left:" + this.axisPct(lane, this.live(band).mid) + "%";
    }

    gripStyle(lane, band, side) {
        const now = this.live(band);
        return "left:" + this.axisPct(lane, side === "min" ? now.min : now.max)
            + "%";
    }

    dotStyle(lane, dot) {
        return "left:" + this.axisPct(lane, dot.wage) + "%";
    }

    /** A dot's standing against the edges being held RIGHT NOW, so the picture
     *  answers while the mouse is still down. */
    dotClass(band, dot) {
        const now = this.live(band);
        if (dot.wage < now.min) { return "pay-dot is-out"; }
        if (dot.wage > now.max) { return "pay-dot is-over"; }
        return "pay-dot";
    }

    dotTitle(dot) {
        return [dot.name, dot.job, dot.wage_label].filter(Boolean).join(" · ");
    }

    setTrack(band, element) {
        if (element) { this.trackRefs[band.id] = element; }
    }

    // --------------------------------------------------------------- the drag
    startDrag(lane, band, side, ev) {
        if (!this.state.board || !this.state.board.can_write) { return; }
        if (!band.id) {
            this.notif.add(_t(
                "These bands are a suggestion. Press “Use these” "
                + "first and then you can move them."), { type: "info" });
            return;
        }
        ev.preventDefault();
        this.state.drag = {
            bandId: band.id, side, laneMax: (lane.axis && lane.axis.max) || 1,
            min: band.min, mid: band.mid, max: band.max,
            before: { min: band.min, mid: band.mid, max: band.max },
        };
        this.state.preview = null;
    }

    onDrag(ev) {
        const drag = this.state.drag;
        if (!drag || !drag.bandId) { return; }
        const track = this.trackRefs[drag.bandId];
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
    onGripKey(lane, band, side, ev) {
        const step = (lane.axis && lane.axis.max ? lane.axis.max : 1)
            * (ev.shiftKey ? 0.05 : 0.01);
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
                bandId: band.id, side,
                laneMax: (lane.axis && lane.axis.max) || 1,
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
        if (this.state.health || this.state.place || this.state.importing) {
            this.closeDrawers();
            ev.stopPropagation();
            return;
        }
        if (this.state.undo) { this.state.undo = null; ev.stopPropagation(); }
    }
}

registry.category("actions").add("pb_pay", PbPayScreen);
