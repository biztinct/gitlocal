/** @odoo-module **/
/**
 * Business Trips cockpit — a kanban pipeline (Draft · Manager · Finance · HR ·
 * Authorized) under a quiet numbers line and a numbered step strip, with per-card approve/refuse affordances and a New-trip
 * composer. RPC facade: pb.trips.get_pipeline_data(); approvals go straight to
 * the pb.business.trip action methods. pbim-tokenized (.pbim.pbtr).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const MODEL = "pb.trips";
const TRIP = "pb.business.trip";

// which action + toast advances a given pending state
const ADVANCE = {
    submitted: { method: "action_manager_approve", label: _t("Approve as Manager") },
    manager_approved: { method: "action_finance_approve", label: _t("Approve as Finance") },
    finance_approved: { method: "action_hr_approve", label: _t("Authorize") },
};

export class PbTrips extends Component {
    static template = "pb_business_trip.PbTrips";
    static props = {
        action: { type: Object, optional: true },
        // W17 (P3a): Mission Control owns the page identity, so `embedded`
        // suppresses the toolbar's title only. `get_pipeline_data()` takes no
        // scope arguments at all, so there is nothing here for the shared
        // context to drive yet — binding it is explicitly out of P3a's scope.
        embedded: { type: Boolean, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            lanes: [],
            closed: [],
            kpis: { open: 0, awaiting_me: 0, days_mtd: 0, advance_outstanding: 0 },
            currency: "",
            currency_position: "after",
            showClosed: false,
            refuseCard: null,
            refuseNote: "",
            // the quiet board: the step being shown, and "waiting on me"
            step: "",
            mine: false,
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call(MODEL, "get_pipeline_data", []);
        this.state.lanes = d.lanes || [];
        this.state.closed = d.closed || [];
        this.state.kpis = d.kpis || this.state.kpis;
        this.state.currency = d.currency || "";
        this.state.currency_position = d.currency_position || "after";
        this.state.loaded = true;
    }

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
            { onClose: () => this.load() },
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
            await this.load();
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
            await this.load();
        } catch (e) {
            this.notif.add(e.data ? e.data.message : (e.message || _t("Refuse failed.")),
                { type: "danger" });
        }
    }

    toggleClosed() { this.state.showClosed = !this.state.showClosed; }

    // ------------------------------------------------------ the quiet board
    //
    // The Hiring look: one slim line of numbers instead of the KPI band, and
    // a numbered strip of the five steps a trip moves through. A trip is at
    // EXACTLY one step (its lane), so the counts add up to the trips on the
    // board; refused and cancelled ones stay in the footer below.
    get stepTitles() {
        return {
            draft: _t("Draft"),
            submitted: _t("With the manager"),
            manager_approved: _t("With finance"),
            finance_approved: _t("With HR"),
            approved: _t("Authorized"),
        };
    }

    get steps() {
        const titles = this.stepTitles;
        return this.state.lanes.map((lane, i) => {
            const mine = lane.cards.filter((c) => c.can_act).length;
            return {
                key: lane.key,
                n: String(i + 1).padStart(2, "0"),
                title: titles[lane.key] || lane.label,
                count: lane.count,
                countLabel: lane.count === 1 ? _t("1 trip") : _t("%s trips", lane.count),
                sub: "",
                flag: mine ? _t("%s waiting on you", mine) : "",
                on: this.state.step === lane.key,
            };
        });
    }

    pickStep(key) {
        this.state.step = this.state.step === key ? "" : key;
    }

    get glance() {
        const k = this.state.kpis || {};
        return [
            { key: "open", n: k.open || 0, label: _t("Open trips"), tone: "", run: null },
            { key: "mine", n: k.awaiting_me || 0, label: _t("Awaiting my approval"), tone: k.awaiting_me ? "amber" : "",
              run: () => { this.state.mine = !this.state.mine; } },
            { key: "days", n: k.days_mtd || 0, label: _t("Days travelled this month"), tone: "", run: null },
            { key: "advance", n: k.advance_outstanding ? this.money(k.advance_outstanding) : 0, label: _t("Advance outstanding"), tone: "", run: null },
        ];
    }

    /** The lanes on screen: one lane when a step is picked, and only the
     *  trips waiting on the reader when that number is pressed. */
    get visibleLanes() {
        return this.state.lanes
            .filter((lane) => !this.state.step || lane.key === this.state.step)
            .map((lane) => {
                if (!this.state.mine) { return lane; }
                const cards = lane.cards.filter((c) => c.can_act);
                return { ...lane, cards, count: cards.length };
            });
    }

    get showingLine() {
        const all = this.state.lanes.reduce((sum, lane) => sum + lane.count, 0);
        if (!this.state.step && !this.state.mine) {
            return { all: true, text: !all ? _t("No trips on the board yet")
                : all === 1 ? _t("Showing the 1 trip · press a step or a number to narrow it")
                : _t("Showing all %s trips · press a step or a number to narrow it", all) };
        }
        const shown = this.visibleLanes.reduce((sum, lane) => sum + lane.cards.length, 0);
        const where = this.state.step ? (this.stepTitles[this.state.step] || "") : "";
        return { all: false, text: where
            ? _t("Showing %s of %s trips at %s", shown, all, where)
            : _t("Showing %s of %s trips", shown, all) };
    }

    showAll() {
        this.state.step = "";
        this.state.mine = false;
    }
}

registry.category("actions").add("pb_trips", PbTrips);
