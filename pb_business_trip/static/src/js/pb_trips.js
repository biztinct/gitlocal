/** @odoo-module **/
/**
 * Business Trips cockpit — a kanban pipeline (Draft · Manager · Finance · HR ·
 * Authorized) under a quiet numbers line and a numbered step strip, with per-card approve/refuse affordances and a New-trip
 * composer. RPC facade: pb.trips (get_trips_head + get_trip_page, on the shared
 * filter panel); approvals go straight to the pb.business.trip action methods.
 * pbim-tokenized (.pbim.pbtr).
 *
 * FILTER wave 7 (2026-10-31): the board sits on the shared filter panel
 * (pb_filter_kit). The five lanes stay; they ARE the panel's "Where the trip
 * is" section — a lane's count is the panel's count (it follows every other
 * filter), a lane the filters leave out folds to a slim column that still
 * says how many it would hold, and pressing it adds it back. The cards come
 * one page at a time for all lanes together; the refused / cancelled footer
 * is the view "Refused or cancelled".
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.trips";
const TRIP = "pb.business.trip";
const PAGE = 120;
const LANES = ["draft", "submitted", "manager_approved", "finance_approved", "approved"];
const OPEN = ["draft", "submitted", "manager_approved", "finance_approved"];
const CLOSED = ["refused", "cancelled"];

// which action + toast advances a given pending state
const ADVANCE = {
    submitted: { method: "action_manager_approve", label: _t("Approve as Manager") },
    manager_approved: { method: "action_finance_approve", label: _t("Approve as Finance") },
    finance_approved: { method: "action_hr_approve", label: _t("Authorize") },
};

export class PbTrips extends Component {
    static template = "pb_business_trip.PbTrips";
    static components = { PbFilterLayout };
    static props = {
        action: { type: Object, optional: true },
        // W17 (P3a): Mission Control owns the page identity, so `embedded`
        // suppresses the toolbar's title only. The trips facade takes no
        // scope arguments from the shared context — binding it is explicitly
        // out of P3a's scope; the filter panel is the board's own.
        embedded: { type: Boolean, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            loaded: false,
            head: { kpis: {}, mine_by_state: {} },
            currency: "",
            currency_position: "after",
            // the cards the panel produced, one page at a time
            cards: [],
            total: 0,
            laneAdvance: {},
            listLoaded: false,
            loadingMore: false,
            refuseCard: null,
            refuseNote: "",
        });
        // The shared filter panel: it owns the filters, the counts and the
        // views. "step" is counted on every refresh, folded or not, because
        // the lane heads and the step strip read it (kit 1.2.0 `always`).
        this.kit = useFilterKit({
            model: MODEL,
            noun: _t("trips"),
            always: ["step"],
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.loadHead(); });
    }

    // ------------------------------------------------------------------ read
    async loadHead() {
        try {
            const d = await this.orm.call(MODEL, "get_trips_head", []);
            this.state.head = d;
            this.state.currency = d.currency || "";
            this.state.currency_position = d.currency_position || "after";
        } catch (e) {
            this.notif.add(_t("The trip numbers could not be read. Try again in a moment."), { type: "warning" });
        } finally {
            this.state.loaded = true;
        }
    }

    /** One page of cards for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.failed) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.cards.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(MODEL, "get_trip_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.cards = more ? [...this.state.cards, ...d.cards] : d.cards;
            this.state.total = d.total;
            if (!more) { this.state.laneAdvance = d.lane_advance || {}; }
            this.state.listLoaded = true;
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The trips could not be listed. Try again in a moment."), { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    /** After an approval, a refusal or the form: numbers, counts and cards. */
    async reload() {
        await Promise.all([this.loadHead(), this.kit.refresh()]);
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() { return this.state.cards.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.cards.length); }

    // ------------------------------------------------------------ formatting
    money(v) {
        const n = Math.round(v || 0).toLocaleString();
        return this.state.currency_position === "before"
            ? `${this.state.currency}${n}` : `${n} ${this.state.currency}`;
    }
    advanceLabel(method) {
        const a = ADVANCE[method];
        return a ? a.label : _t("Approve");
    }
    laneAdvanceLabel(card) {
        const a = ADVANCE[card.state];
        return a ? a.label : _t("Approve");
    }
    agingTone(card) {
        return card.waiting_days > 3 ? "warn" : "";
    }

    // --------------------------------------------------------------- compose
    _openForm(resId) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: TRIP,
                res_id: resId || false,
                views: [[false, "form"]],
                target: "new",
            },
            { onClose: () => this.reload() },
        );
    }
    newTrip() { this._openForm(false); }
    openTrip(card) { this._openForm(card.id); }

    // --------------------------------------------------------------- approve
    async approve(card) {
        const a = ADVANCE[card.state];
        if (!a) { return; }
        try {
            await this.orm.call(TRIP, a.method, [[card.id]]);
            const msg = card.state === "finance_approved"
                ? _t("Trip authorized — attendance will be marked automatically.")
                : _t("Approved.");
            this.notif.add(msg, { type: "success" });
            await this.reload();
        } catch (e) {
            this.notif.add(e.data ? e.data.message : (e.message || _t("Action failed.")),
                { type: "danger" });
        }
    }

    // ---------------------------------------------------------------- refuse
    askRefuse(card) { this.state.refuseCard = card; this.state.refuseNote = ""; }
    cancelRefuse() { this.state.refuseCard = null; this.state.refuseNote = ""; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }
    async confirmRefuse() {
        const card = this.state.refuseCard;
        if (!card) { return; }
        try {
            await this.orm.call(TRIP, "action_refuse_chain", [[card.id]],
                { note: this.state.refuseNote || false });
            this.notif.add(_t("Trip refused."), { type: "warning" });
            this.cancelRefuse();
            await this.reload();
        } catch (e) {
            this.notif.add(e.data ? e.data.message : (e.message || _t("Refuse failed.")),
                { type: "danger" });
        }
    }

    // ------------------------------------------------------ the quiet board
    //
    // The Hiring look: one slim line of numbers instead of the KPI band, and
    // a numbered strip of the five steps a trip moves through. A trip is at
    // EXACTLY one step (its lane); the counts are the panel's, so they follow
    // the other filters (ruling R1).
    get stepTitles() {
        return {
            draft: _t("Draft"),
            submitted: _t("With the manager"),
            manager_approved: _t("With finance"),
            finance_approved: _t("With HR"),
            approved: _t("Authorized"),
        };
    }
    get laneLabels() {
        return {
            draft: _t("Draft"),
            submitted: _t("Manager"),
            manager_approved: _t("Finance"),
            finance_approved: _t("HR"),
            approved: _t("Authorized"),
        };
    }

    /** The panel's count for one state (0 while it is still counting). */
    stepCount(key) {
        const c = this.kit.counts.step;
        const row = c && (c.values || []).find((r) => r.v === key);
        return row ? row.n : 0;
    }
    get countsReady() {
        const c = this.kit.counts.step;
        return !!(c && c.values);
    }
    get ticked() { return this.kit.values("step"); }

    get steps() {
        const titles = this.stepTitles;
        const mineBy = (this.state.head && this.state.head.mine_by_state) || {};
        const ticked = this.ticked;
        return LANES.map((key, i) => {
            const count = this.stepCount(key);
            const mine = mineBy[key] || 0;
            return {
                key,
                n: String(i + 1).padStart(2, "0"),
                title: titles[key],
                count,
                countLabel: count === 1 ? _t("1 trip") : _t("%s trips", count),
                sub: "",
                flag: mine ? _t("%s waiting on you", mine) : "",
                mine: !!mine,
                on: ticked.length === 1 && ticked[0] === key,
            };
        });
    }

    /** Press a step: that lane only, the other filters kept. Press the lit
     *  step again: every open lane, as the board starts. */
    pickStep(key) {
        const ticked = this.ticked;
        const next = { ...this.kit.filters };
        next.step = ticked.length === 1 && ticked[0] === key ? [...OPEN] : [key];
        this.kit.setFilters(next, { search: this.kit.search });
    }

    // ---------------------------------------------------------- the numbers
    viewFilters(key) {
        const v = this.kit.views.find((x) => x.key === key);
        return v ? v.filters : null;
    }
    /** What each figure means as a filter (the same filters as its view). */
    get glanceFilters() {
        return {
            open: { step: [...OPEN] },
            mine: { mine: ["yes"] },
            advance: this.viewFilters("advance"),
        };
    }
    glancePick(key) {
        const f = this.glanceFilters[key];
        return f && this.kit.loaded && !this.kit.failed ? () => this.kit.toggleFilters(f) : null;
    }
    get glance() {
        const k = (this.state.head && this.state.head.kpis) || {};
        return [
            { key: "open", n: k.open || 0, label: _t("Open trips"), tone: "", run: this.glancePick("open") },
            { key: "mine", n: k.awaiting_me || 0, label: _t("Awaiting my approval"), tone: k.awaiting_me ? "amber" : "",
              run: this.glancePick("mine") },
            { key: "days", n: k.days_mtd || 0, label: _t("Days travelled this month"), tone: "", run: null },
            { key: "advance", n: k.advance_outstanding ? this.money(k.advance_outstanding) : 0, label: _t("Advance outstanding"), tone: "",
              run: this.glancePick("advance") },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters)) {
            if (f && this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ------------------------------------------------------------- the lanes
    /** The five lanes. A lane the step filter leaves out folds to a slim
     *  column with its count (what it WOULD hold under the other filters). */
    get lanes() {
        const labels = this.laneLabels;
        const ticked = this.ticked;
        return LANES.map((key) => {
            const cards = this.state.cards.filter((c) => c.state === key);
            const count = this.stepCount(key);
            const on = !ticked.length || ticked.includes(key);
            return {
                key,
                label: labels[key],
                on,
                count,
                cards,
                advance: on ? (this.state.laneAdvance[key] || 0) : 0,
                // cards of this lane further down the order (next pages)
                below: on ? Math.max(0, count - cards.length) : 0,
            };
        });
    }
    laneTitle(lane) {
        return lane.count === 1
            ? _t("%s: 1 trip with these filters. Press to add this step.", lane.label)
            : _t("%(lane)s: %(n)s trips with these filters. Press to add this step.", { lane: lane.label, n: lane.count });
    }
    addLane(key) {
        this.kit.toggle("step", key);
    }

    /** The footer: refused and cancelled trips. */
    get closedOn() {
        const t = this.ticked;
        return !t.length || CLOSED.some((s) => t.includes(s));
    }
    get closedCards() {
        return this.closedOn ? this.state.cards.filter((c) => CLOSED.includes(c.state)) : [];
    }
    get closedCount() {
        return CLOSED.reduce((sum, s) => sum + this.stepCount(s), 0);
    }
    get closedLabel() {
        const n = this.closedCount;
        return n === 1 ? _t("Show the 1 refused or cancelled trip") : _t("Show the %s refused or cancelled trips", n);
    }
    showClosed() {
        const v = this.kit.views.find((x) => x.key === "closed");
        if (v) {
            this.kit.useView("closed");
        } else {
            this.kit.setFilters({ ...this.kit.filters, step: [...CLOSED] }, { search: this.kit.search });
        }
    }
    stateWord(s) {
        return { refused: _t("Refused"), cancelled: _t("Cancelled") }[s] || s;
    }

    // ------------------------------------------------------- empty states
    /** "" (cards to show) · "none" (no trip at all yet) · "search" · "filters". */
    get emptyKind() {
        if (!this.state.listLoaded || this.state.total) { return ""; }
        if (!this.kit.total && !this.kit.search) { return "none"; }
        if (this.kit.search && !this.kit.activeCount) { return "search"; }
        return "filters";
    }
    startAgain() { this.kit.home(); }
    clearAll() { this.kit.clearAll(); }

    /** A key that changes with the filters, so the board slides in once. */
    get boardKey() {
        return JSON.stringify(this.kit.filters) + ":" + this.kit.search + ":" + this.kit.sort;
    }
}

registry.category("actions").add("pb_trips", PbTrips);
