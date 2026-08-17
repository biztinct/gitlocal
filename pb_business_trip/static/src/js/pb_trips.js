/** @odoo-module **/
/**
 * Business Trips cockpit — a kanban pipeline (Draft · Manager · Finance · HR ·
 * Authorized) with KPIs, per-card approve/refuse affordances and a New-trip
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
}

registry.category("actions").add("pb_trips", PbTrips);
