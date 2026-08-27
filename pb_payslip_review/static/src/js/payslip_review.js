/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STATE_LABEL = { draft: _t("Draft"), verify: _t("Waiting"), level1: _t("HR Manager pending"),
                      level2: _t("GM pending"), done: _t("Done"), cancel: _t("Rejected") };
const STATE_CLASS = { draft: "s-draft", verify: "s-draft", level1: "s-amber",
                      level2: "s-indigo", done: "s-green", cancel: "s-red" };
const NEXT_LABEL = { draft: _t("Submit for HR review"), level1: _t("HR approve → GM"), level2: _t("GM approve → Done") };
const STATUS_FLOW = [["draft", _t("Draft")], ["level1", _t("HR Manager pending")], ["level2", _t("GM pending")], ["done", _t("Done")]];

export class PayslipReview extends Component {
    static template = "pb_payslip_review.PayslipReview";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, runId: null, run: null, runs: [], slips: [], totals: {},
            filter: "all", selId: null, detail: null,
        });
        onWillStart(async () => { await this.load(); });
    }

    async load(runId = null) {
        const d = await this.orm.call("pb.payslip.review", "get_review_data", [runId]);
        this.state.run = d.run; this.state.runs = d.runs; this.state.slips = d.slips;
        this.state.totals = d.totals; this.state.runId = d.run ? d.run.id : null;
        this.state.loaded = true;
        const first = d.slips.find(s => s.flag) || d.slips[0];
        if (first) await this.select(first.id);
        else { this.state.selId = null; this.state.detail = null; }
    }

    async onRunChange(ev) { await this.load(parseInt(ev.target.value)); }

    get filteredSlips() {
        const f = this.state.filter;
        if (f === "all") return this.state.slips;
        if (f === "flag") return this.state.slips.filter(s => s.flag);
        return this.state.slips.filter(s => s.state === f);
    }
    setFilter(f) { this.state.filter = f; }

    async select(id) {
        this.state.selId = id;
        this.state.detail = await this.orm.call("pb.payslip.review", "get_slip_detail", [id]);
    }

    label(st) { return STATE_LABEL[st] || st; }
    cls(st) { return STATE_CLASS[st] || "s-draft"; }
    nextLabel(st) { return NEXT_LABEL[st]; }
    get statusFlow() { return STATUS_FLOW; }
    flowIdx(st) { const i = STATUS_FLOW.findIndex(x => x[0] === st); return i < 0 ? 0 : i; }

    vnd(n) { if (n === null || n === undefined) return "—"; if (Math.abs(n) >= 1e9) return "₫" + (n / 1e9).toFixed(1) + "B"; if (Math.abs(n) >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M"; if (Math.abs(n) >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K"; return "₫" + Math.round(n); }
    full(n) { if (n === null || n === undefined) return "—"; return "₫" + Math.round(n).toLocaleString("en-US"); }
    initials(name) { return (name || "?").split(" ").filter(Boolean).map(p => p[0]).join("").slice(-2).toUpperCase(); }

    async advance(id) {
        const res = await this.orm.call("pb.payslip.review", "advance_state", [id]);
        if (!res.ok) { this.notif.add(res.msg || _t("Action blocked"), { type: "warning" }); }
        // refresh the row + detail + totals
        const d = await this.orm.call("pb.payslip.review", "get_review_data", [this.state.runId]);
        this.state.slips = d.slips; this.state.totals = d.totals; this.state.run = d.run;
        await this.select(id);
    }
}

registry.category("actions").add("pb_payslip_review", PayslipReview);
