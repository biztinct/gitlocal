/** @odoo-module **/
/**
 * Leave Command Center — a bespoke HR cockpit over core hr.leave. One board with
 * on-leave-today strip + KPIs, an approval queue (one-click ✓/✗, required note on
 * refuse), a department×day month heatmap, and a paged balance board; plus an
 * apply-on-behalf drawer. RPC facade: pb.timeoff (facade-only, acts as the real
 * user — no sudo, no leave logic). pbim-tokenized (.pbto.pbim), fresh-green tint.
 */
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_timeoff/js/pbto_icons";

const MODEL = "pb.timeoff";

export class PbTimeoff extends Component {
    static template = "pb_timeoff.PbTimeoff";
    static props = {
        action: { type: Object, optional: true },
        // W17 (P3a): Mission Control owns the page identity, so `embedded`
        // suppresses the hero's eyebrow/title/subtitle and nothing else. The
        // MONTH NAV STAYS (P3a §3.4): the month is this cockpit's own dimension,
        // not a duplicate of the shared context's week — the shell has no
        // opinion about it and taking it away would make the board unusable.
        embedded: { type: Boolean, optional: true },
        // P3b §3.6 — one palette instruction, consumed by nonce. Always an
        // object, never null: a TYPED optional prop rejects null (W35).
        pbCmd: { type: Object, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false, pbCmd: { name: "", nonce: 0 } };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.state = useState({
            loaded: false,
            busy: false,
            data: null,
            month: false,
            balancePage: 0,
            refuseId: null,
            refuseNote: "",
            applyOpen: false,
            apply: { employee_id: "", employee_name: "", type_id: "", date_from: "", date_to: "", note: "" },
            empQuery: "",
            empResults: [],
        });
        this._empTimer = null;
        this._cmdNonce = 0;
        onWillUpdateProps((next) => { this._applyPbCmd(next.pbCmd); });
        onWillStart(async () => {
            await this.load();
            this._applyPbCmd(this.props.pbCmd);
        });
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(
                MODEL, "get_board", [this.state.month, this.state.balancePage]);
            this.state.month = this.state.data.month;
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- getters
    get d() { return this.state.data || {}; }
    get kpis() { return this.d.kpis || {}; }
    get queue() { return this.d.queue || []; }
    get heatmap() { return this.d.heatmap || { days: [], rows: [], max: 0 }; }
    get balances() { return this.d.balances || { rows: [], types: [] }; }

    fmtDays(n) {
        const v = Number(n || 0);
        return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
    }

    // ------------------------------------------------------------- month nav
    _shiftMonth(delta) {
        const [y, m] = String(this.state.month).split("-").map(Number);
        const dt = new Date(y, (m - 1) + delta, 1);
        this.state.month = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
        this.state.balancePage = 0;
        this.state.heatDay = null;
        this.load();
    }
    prevMonth() { this._shiftMonth(-1); }
    nextMonth() { this._shiftMonth(1); }

    // ------------------------------------------------------------- queue
    async approve(id) { await this._act(id, "approve"); }
    openRefuse(id) { this.state.refuseId = id; this.state.refuseNote = ""; }
    cancelRefuse() { this.state.refuseId = null; this.state.refuseNote = ""; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }
    async confirmRefuse() {
        const id = this.state.refuseId;
        if (!(this.state.refuseNote || "").trim()) {
            this.notif.add(_t("A reason is required to refuse."), { type: "warning" });
            return;
        }
        this.state.refuseId = null;
        await this._act(id, "refuse", this.state.refuseNote);
    }
    async _act(id, action, note) {
        // optimistic removal from the queue
        const before = this.queue;
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "act", [id, action], { note: note || false });
            this.notif.add(
                action === "approve" ? _t("Leave approved.") : _t("Leave refused."),
                { type: "success" });
            await this.load();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            void before;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- heatmap
    cellTone(count) {
        const max = this.heatmap.max || 1;
        if (!count) { return 0; }
        return Math.min(4, Math.ceil((4 * count) / max));
    }
    openDayInLeaves(iso) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Time Off — %s", iso),
            res_model: "hr.leave",
            views: [[false, "list"], [false, "form"]],
            domain: [["request_date_from", "<=", iso], ["request_date_to", ">=", iso],
                     ["state", "in", ["confirm", "validate1", "validate"]]],
            target: "current",
        });
    }

    // ------------------------------------------------------------- balances
    async balancePage(delta) {
        const next = this.state.balancePage + delta;
        if (next < 0) { return; }
        this.state.balancePage = next;
        this.state.busy = true;
        try {
            this.d.balances = await this.orm.call(MODEL, "get_balances_page", [next]);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    prevBalance() { this.balancePage(-1); }
    nextBalance() { this.balancePage(1); }
    balCell(row, typeId) { return (row.cells || {})[typeId] || { balance: 0, allocated: 0, taken: 0 }; }

    // ------------------------------------------------------------- apply
    /**
     * The `pb_cmd` channel (P3b §3.6).
     *
     * Mission Control forwards ONE palette instruction as a prop with a NONCE,
     * and this lens tracks the last nonce it ran. That is the whole protocol,
     * and it is shaped that way on purpose: a "consumed" callback would be a
     * CHILD writing HOST state from a mount hook, which is the bug that cost
     * P1a 591 junk records and then bit a second time on a keyed child
     * (W21/W21.1). Nothing here writes anything but this component's own state,
     * and an unknown command is ignored — a lens that does not implement a verb
     * is not an error.
     */
    _applyPbCmd(cmd) {
        if (!cmd || !cmd.nonce || cmd.nonce === this._cmdNonce) { return; }
        this._cmdNonce = cmd.nonce;
        if (cmd.name === "apply") { this.openApply(); }
    }

    openApply() {
        this.state.apply = { employee_id: "", employee_name: "", type_id: "", date_from: "", date_to: "", note: "" };
        this.state.empQuery = "";
        this.state.empResults = [];
        this.state.applyOpen = true;
    }
    closeApply() { this.state.applyOpen = false; }
    onApplyField(f, ev) { this.state.apply[f] = ev.target.value; }
    onEmpQuery(ev) {
        const q = ev.target.value;
        this.state.empQuery = q;
        this.state.apply.employee_id = "";       // clears until a pick
        if (this._empTimer) { clearTimeout(this._empTimer); }
        this._empTimer = setTimeout(async () => {
            if (!q.trim()) { this.state.empResults = []; return; }
            try {
                this.state.empResults = await this.orm.call(MODEL, "search_employees", [q]);
            } catch (e) {
                this.state.empResults = [];
            }
        }, 220);
    }
    pickEmployee(emp) {
        this.state.apply.employee_id = emp.id;
        this.state.apply.employee_name = emp.name;
        this.state.empQuery = emp.name;
        this.state.empResults = [];
    }
    get canApply() {
        const a = this.state.apply;
        return !!(a.employee_id && a.type_id && a.date_from && a.date_to);
    }
    async submitApply() {
        const a = this.state.apply;
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "apply_on_behalf",
                [Number(a.employee_id), Number(a.type_id), a.date_from, a.date_to, a.note || false]);
            this.notif.add(_t("Leave filed — pending approval."), { type: "success" });
            this.state.applyOpen = false;
            await this.load();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_timeoff", PbTimeoff);
