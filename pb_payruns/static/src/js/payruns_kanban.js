/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onMounted, useState } from "@odoo/owl";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanController } from "@web/views/kanban/kanban_controller";

function fmt(d) {
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// Hybrid Pay Runs board: native kanban + KPI hero band + health19-style
// status tabs and date chips (applied through the native searchModel).
export class PbPayrunsKanbanController extends KanbanController {
    static template = "pb_payruns.KanbanView";

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.pbOrm = useService("orm");
        this.pbState = useState({
            loaded: false, currency: "", kpis: {}, tabCounts: {},
            activeTab: "all", dateFilter: "all_dates", customFrom: "", customTo: "",
        });
        this._tabGroupId = null;
        this._dateGroupId = null;
        onWillStart(async () => { await this.pbLoad(); });
        onMounted(() => { this._applyStatus(); });   // hide cancelled by default via "All"
    }

    async pbLoad() {
        try {
            const d = await this.pbOrm.call("pb.payruns", "get_board_data", []);
            const col = {};
            (d.columns || []).forEach(c => { col[c.key] = c.count; });
            Object.assign(this.pbState, {
                loaded: true, currency: d.currency, kpis: d.kpis || {},
                tabCounts: {
                    draft: col.draft || 0,
                    pending: (col.level1 || 0) + (col.level2 || 0),
                    done: col.done || 0,
                    rejected: d.rejected_count || 0,
                },
            });
        } catch (e) {
            this.pbState.loaded = true;
        }
    }

    // -------- tab / chip definitions --------
    get pbStatusTabs() {
        const c = this.pbState.tabCounts || {};
        return [
            { id: "all", label: "All" },
            { id: "draft", label: "Draft", count: c.draft, tone: "slate" },
            { id: "pending", label: "Pending approval", count: c.pending, tone: "amber" },
            { id: "done", label: "Done", count: c.done, tone: "green" },
            { id: "rejected", label: "Rejected", count: c.rejected, tone: "rose" },
        ];
    }
    get pbDateTabs() {
        return [
            { id: "all_dates", label: "All periods" },
            { id: "this_month", label: "This month" },
            { id: "this_quarter", label: "This quarter" },
            { id: "this_year", label: "This year" },
        ];
    }

    // -------- domains --------
    _statusDomain(id) {
        switch (id) {
            case "draft": return [["state", "=", "draft"]];
            case "pending": return [["state", "in", ["level1", "level2"]]];
            case "done": return [["state", "=", "done"]];
            case "rejected": return [["state", "=", "cancel"]];
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
        const pre = { description: "Status: " + (this.pbStatusTabs.find(t => t.id === id)?.label || id), domain: this._statusDomain(id) };
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
            ? `Period ${this.pbState.customFrom || "…"} → ${this.pbState.customTo || "…"}`
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
