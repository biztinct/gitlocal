/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onMounted, useState } from "@odoo/owl";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";

function fmt(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// Hybrid Pay Runs board: native kanban + quiet numbers line + numbered
// steps and date chips (applied through the native searchModel).
export class PbPayrunsKanbanController extends KanbanController {
    static template = "pb_payruns.KanbanView";

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.pbOrm = useService("orm");
        this.pbState = useState({
            loaded: false, currency: "", kpis: {}, tabCounts: {},
            activeTab: "all", dateFilter: "all_dates", customFrom: "", customTo: "",
            divisions: [], activeDivision: "all",
        });
        this._tabGroupId = null;
        this._dateGroupId = null;
        this._divGroupId = null;
        onWillStart(async () => { await this.pbLoad(); });
        onMounted(() => {
            this._applyStatus();   // hide cancelled by default via "All"
            // Demo users: pre-filter the board to the live demo month (June 2026).
            if (this._demoPeriod) {
                this.pbState.customFrom = this._demoPeriod.from;
                this.pbState.customTo = this._demoPeriod.to;
                this.pbState.dateFilter = "custom";
                this._applyDate();
            }
        });
    }

    async pbLoad() {
        try {
            const d = await this.pbOrm.call("pb.payruns", "get_board_data", []);
            const col = {};
            (d.columns || []).forEach(c => { col[c.key] = c.count; });
            this._demoPeriod = d.demo_period || null;
            Object.assign(this.pbState, {
                loaded: true, currency: d.currency, kpis: d.kpis || {},
                divisions: d.divisions || [],
                tabCounts: {
                    draft: col.draft || 0,
                    pending: col.approval_pending || 0,
                    done: col.done || 0,
                    rejected: d.rejected_count || 0,
                },
            });
        } catch (e) {
            this.pbState.loaded = true;
        }
    }

    // -------- quiet board: numbers line + numbered steps --------
    //
    // The old status tabs are the steps now. A run is at exactly one step
    // (its state), so the counts add up to every live run. "Rejected" is an
    // outcome, not a step: it is a figure in the numbers line instead. Every
    // step and figure applies the same searchModel filter the tabs applied;
    // pressing the lit one again goes back to "all".
    get pbStatusTabs() {
        return [
            { id: "all", label: _t("All") },
            { id: "draft", label: _t("Draft") },
            { id: "pending", label: _t("Waiting for approval") },
            { id: "done", label: _t("Done") },
            { id: "rejected", label: _t("Rejected") },
            { id: "pipeline", label: _t("In pipeline") },
            { id: "mine", label: _t("Waiting on you") },
        ];
    }
    _runsLabel(n) { return n === 1 ? _t("1 pay run") : _t("%s pay runs", n); }

    get pbSteps() {
        const c = this.pbState.tabCounts || {};
        const k = this.pbState.kpis || {};
        const defs = [
            { key: "draft", title: _t("Draft"), count: c.draft || 0 },
            { key: "pending", title: _t("Waiting for approval"), count: c.pending || 0 },
            { key: "done", title: _t("Done"), count: c.done || 0 },
        ];
        return defs.map((d, i) => {
            let flag = "";
            if (d.key === "pending") {
                const mine = k.my_pending || 0;
                if (mine) {
                    flag = mine === 1 ? _t("1 waiting on you") : _t("%s waiting on you", mine);
                } else if (d.count) {
                    flag = d.count === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", d.count);
                }
            }
            return {
                ...d,
                n: String(i + 1).padStart(2, "0"),
                countLabel: this._runsLabel(d.count),
                sub: "",
                flag,
                flagTone: "",
                on: this.pbState.activeTab === d.key,
            };
        });
    }
    pickStep(key) { this.setTab(this.pbState.activeTab === key ? "all" : key); }

    get pbGlanceOn() {
        const t = this.pbState.activeTab;
        return ["pipeline", "mine", "rejected"].includes(t) ? t : "";
    }
    get pbGlance() {
        const k = this.pbState.kpis || {};
        const c = this.pbState.tabCounts || {};
        const tone = (v, t) => (v ? t : "");
        const flip = (id) => () => this.setTab(this.pbState.activeTab === id ? "all" : id);
        return [
            { key: "total", n: k.total || 0, label: _t("Pay runs"), tone: "", run: null },
            { key: "pipeline", n: k.in_pipeline || 0, label: _t("In pipeline"), tone: "", run: flip("pipeline") },
            { key: "mine", n: k.my_pending || 0, label: _t("Awaiting your approval"), tone: tone(k.my_pending, "amber"), run: flip("mine") },
            { key: "rejected", n: c.rejected || 0, label: _t("Rejected"), tone: "", run: flip("rejected") },
            { key: "net", n: k.period_net ? this.pbMoney(k.period_net) : 0, label: _t("Net paid (done)"), tone: "", run: null },
        ];
    }

    /** How many runs the kanban is drawing now (after every filter). */
    _pbShownCount() {
        const r = this.model && this.model.root;
        if (!r) return 0;
        return (r.isGrouped ? r.recordCount : r.count) || 0;
    }
    get pbShowing() {
        const c = this.pbState.tabCounts || {};
        const all = (c.draft || 0) + (c.pending || 0) + (c.done || 0);
        const narrowed = this.pbState.activeTab !== "all"
            || this.pbState.dateFilter !== "all_dates"
            || this.pbState.activeDivision !== "all";
        if (!narrowed) {
            return { all: true, text: !all ? _t("no pay runs yet") : all === 1 ? _t("all 1 pay run") : _t("all %s pay runs", all) };
        }
        const tab = this.pbState.activeTab;
        const where = tab === "all" ? "" : ((this.pbStatusTabs.find(t => t.id === tab) || {}).label || "");
        return { all: false, text: _t("%s of %s pay runs", this._pbShownCount(), all), where };
    }
    pbShowAll() {
        this.setTab("all");
        this.setDateFilter("all_dates");
        this.setDivision("all");
    }
    get pbDateTabs() {
        return [
            { id: "all_dates", label: _t("All periods") },
            { id: "this_month", label: _t("This month") },
            { id: "this_quarter", label: _t("This quarter") },
            { id: "this_year", label: _t("This year") },
        ];
    }

    // -------- domains --------
    _statusDomain(id) {
        switch (id) {
            case "draft": return [["state", "=", "draft"]];
            case "pending": return [["state", "=", "approval_pending"]];
            case "done": return [["state", "=", "done"]];
            case "rejected": return [["state", "=", "cancel"]];
            case "pipeline": return [["state", "in", ["draft", "approval_pending"]]];
            case "mine": return [["pb_awaiting_me", "=", true]];
            default: return [["state", "!=", "cancel"]];   // all (active)
        }
    }
    _dateDomain(id) {
        const now = new Date();
        const y = now.getFullYear(), m = now.getMonth();
        const range = (a, b) => [["date_start", ">=", fmt(a)], ["date_start", "<=", fmt(b)]];
        switch (id) {
            case "this_month": return range(new Date(y, m, 1), new Date(y, m + 1, 0));
            case "this_quarter": {
                const q = Math.floor(m / 3) * 3;
                return range(new Date(y, q, 1), new Date(y, q + 3, 0));
            }
            case "this_year": return range(new Date(y, 0, 1), new Date(y, 11, 31));
            case "custom": {
                const dom = [];
                if (this.pbState.customFrom) dom.push(["date_start", ">=", this.pbState.customFrom]);
                if (this.pbState.customTo) dom.push(["date_start", "<=", this.pbState.customTo]);
                return dom;
            }
            default: return [];
        }
    }

    // -------- apply via searchModel --------
    _applyStatus() {
        const sm = this.env.searchModel;
        if (this._tabGroupId !== null) { sm.deactivateGroup(this._tabGroupId); this._tabGroupId = null; }
        const id = this.pbState.activeTab;
        const pre = { description: _t("Status: %(status)s", { status: this.pbStatusTabs.find(t => t.id === id)?.label || id }), domain: this._statusDomain(id) };
        sm.createNewFilters([pre]);
        this._tabGroupId = pre.groupId;
    }
    _applyDate() {
        const sm = this.env.searchModel;
        if (this._dateGroupId !== null) { sm.deactivateGroup(this._dateGroupId); this._dateGroupId = null; }
        const id = this.pbState.dateFilter;
        if (id === "all_dates") return;
        const dom = this._dateDomain(id);
        if (!dom.length) return;
        const label = id === "custom"
            ? _t("Period %(from)s → %(to)s", { from: this.pbState.customFrom || "…", to: this.pbState.customTo || "…" })
            : (this.pbDateTabs.find(t => t.id === id)?.label || id);
        const pre = { description: label, domain: dom };
        sm.createNewFilters([pre]);
        this._dateGroupId = pre.groupId;
    }

    setTab(id) {
        if (this.pbState.activeTab === id) return;
        this.pbState.activeTab = id;
        this._applyStatus();
    }
    setDateFilter(id) {
        if (id !== "custom" && this.pbState.dateFilter === id) return;
        this.pbState.dateFilter = id;
        this._applyDate();
    }
    onCustomDate(which, ev) {
        this.pbState[which === "from" ? "customFrom" : "customTo"] = ev.target.value;
        this.pbState.dateFilter = "custom";
        this._applyDate();
    }

    // -------- division chips --------
    get pbDivisionTabs() {
        return [{ key: "all", label: _t("All divisions") }, ...(this.pbState.divisions || [])];
    }
    _applyDivision() {
        const sm = this.env.searchModel;
        if (this._divGroupId !== null) { sm.deactivateGroup(this._divGroupId); this._divGroupId = null; }
        const id = this.pbState.activeDivision;
        if (id === "all") return;
        const label = (this.pbState.divisions.find(d => d.key === id) || {}).label || id;
        const pre = { description: _t("Division: %(division)s", { division: label }), domain: [["pb_division", "=", id]] };
        sm.createNewFilters([pre]);
        this._divGroupId = pre.groupId;
    }
    setDivision(id) {
        if (this.pbState.activeDivision === id) return;
        this.pbState.activeDivision = id;
        this._applyDivision();
    }

    pbIc(n, s = 20) { return ic(n, s); }
    pbMoney(n) {
        const cur = this.pbState.currency || "₫";
        if (n === null || n === undefined || isNaN(n)) return cur + "0";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(2) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    pbRunPayroll() { this.actionService.doAction("pb_payrun_wizard.action_pb_payrun_wizard"); }
}

registry.category("views").add("pb_payruns_kanban", {
    ...kanbanView,
    Controller: PbPayrunsKanbanController,
});
