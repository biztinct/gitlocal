/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { ic } from "@pb_import_kit/js/import_icons";

// A PAYSLIP IN A PAY RUN IS NOT APPROVED ON ITS OWN. The three-rung slip
// ladder this screen used to drive ran beside the run's own approval and had
// nothing to do with it — and the bank export pays every payslip in state
// `done`, so it was a way to get one person's money out of a run nobody had
// sent in. What is left here is reviewing: reading the numbers and flagging
// what looks wrong. `level1`/`level2` stay in the LABEL map only so a payslip
// written before this change still reads as something rather than as a key.
const STATE_LABEL = { draft: _t("Draft"), verify: _t("Waiting for approval"),
                      level1: _t("Waiting for approval"), level2: _t("Waiting for approval"),
                      done: _t("Done"), cancel: _t("Rejected") };
const STATE_CLASS = { draft: "s-draft", verify: "s-amber", level1: "s-amber",
                      level2: "s-amber", done: "s-green", cancel: "s-red" };
const NEXT_LABEL = {};
const STATUS_FLOW = [["draft", _t("Draft")], ["verify", _t("Waiting for approval")], ["done", _t("Done")]];
// The step strip's three steps and the "Where it is" value each one ticks.
const STEPS = [["draft", _t("Draft")], ["waiting", _t("Waiting for approval")], ["done", _t("Done")]];
const LIVE_STEPS = STEPS.map(([k]) => k);
const PAGE = 60;

export class PayslipReview extends Component {
    static template = "pb_payslip_review.PayslipReview";
    static components = { PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, runId: null, run: null, runs: [], totals: {},
            slips: [], total: 0, steps: {}, listLoaded: false, loadingMore: false,
            selId: null, detail: null,
        });
        // FILTER wave 5: the shared filter panel. The run picker stays the
        // screen's one scope control above it and rides on every kit call as
        // ctx.run_id; changing the run reconfigures the panel for that run.
        // `defer`: the head resolves which run is open before the panel loads.
        this.kit = useFilterKit({
            model: "pb.payslip.review",
            noun: _t("payslips"),
            defer: true,
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => {
            await this.loadHead();
            await this.kit.reconfigure({ ctx: { run_id: this.state.runId || false } });
        });
    }

    /** The run, the picker and the numbers — over the whole run. */
    async loadHead(runId = null) {
        const d = await this.orm.call("pb.payslip.review", "get_review_head", [runId]);
        this.state.run = d.run; this.state.runs = d.runs;
        this.state.totals = d.totals || {}; this.state.runId = d.run ? d.run.id : null;
        this.state.loaded = true;
    }

    async onRunChange(ev) {
        const runId = parseInt(ev.target.value);
        this.state.listLoaded = false;
        this.state.slips = [];
        await this.loadHead(runId);
        // the panel recounts for the new run; the list reloads through it
        await this.kit.reconfigure({ ctx: { run_id: this.state.runId || false } });
    }

    /** One page of this run's payslips for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (!this.state.runId) { this.state.listLoaded = true; return; }
        const q = this.kit.query;
        const offset = more ? this.state.slips.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.payslip.review", "get_slip_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
                context: { pbf_ctx: { run_id: this.state.runId } },
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.slips = more ? [...this.state.slips, ...d.rows] : d.rows;
            this.state.total = d.total;
            this.state.steps = d.steps || {};
            this.state.listLoaded = true;
            if (!more) { await this._keepSelection(); }
        } catch (e) {
            console.error("pb_payslip_review: the list could not load", e);
            this.notif.add(_t("The payslips could not be loaded. Try again in a moment."), { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    get hasMore() { return this.state.slips.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.slips.length); }

    /** The detail pane follows the list: when the open payslip is no longer
     *  on the page, the first flagged one on it opens (else the first). */
    async _keepSelection() {
        const slips = this.state.slips;
        if (this.state.selId && slips.some((s) => s.id === this.state.selId)) { return; }
        const first = slips.find((s) => s.flag) || slips[0];
        if (first) { await this.select(first.id); }
        else { this.state.selId = null; this.state.detail = null; }
    }

    get filteredSlips() { return this.state.slips; }

    // ================================================ quiet board
    //
    // The old tiles are one slim numbers line; the old state chips are the
    // numbered steps. A payslip is at EXACTLY one step; a cancelled one is at
    // no step. FILTER wave 5: a step counts against every OTHER filter (the
    // panel's rule, R1) and pressing it ticks that step in "Where it is",
    // keeping the other filters; pressing the lit step lets go of it.
    _slipsLabel(n) { return n === 1 ? _t("1 payslip") : _t("%s payslips", n); }

    get stepOn() {
        const v = this.kit.values("status");
        return v.length === 1 && LIVE_STEPS.includes(v[0]) ? v[0] : "";
    }
    get steps() {
        const counts = this.state.steps || {};
        const on = this.stepOn;
        return STEPS.map(([key, title], i) => {
            const c = counts[key] || { n: 0, flagged: 0 };
            const flagged = c.flagged || 0;
            return {
                key, title,
                n: String(i + 1).padStart(2, "0"),
                count: c.n || 0,
                countLabel: this._slipsLabel(c.n || 0),
                flag: !flagged ? "" : flagged === 1 ? _t("1 needs review") : _t("%s need review", flagged),
                on: on === key,
            };
        });
    }
    pickStep(key) {
        const next = { ...this.kit.filters };
        if (this.stepOn === key) { delete next.status; } else { next.status = [key]; }
        this.kit.setFilters(next, { search: this.kit.search });
    }

    get glance() {
        const t = this.state.totals || {};
        const flag = { review: ["flag"] };
        return [
            { key: "count", n: t.count || 0, label: _t("Payslips"), tone: "", run: null },
            { key: "flag", n: t.flagged || 0, label: _t("Need review"), tone: t.flagged ? "amber" : "",
              run: () => this.kit.toggleFilters(flag), on: this.kit.loaded && this.kit.isExactly(flag) },
            { key: "gross", n: t.gross ? this.vnd(t.gross) : 0, label: _t("Gross total"), tone: "", run: null },
            { key: "net", n: t.net ? this.vnd(t.net) : 0, label: _t("Net total"), tone: "", run: null },
        ];
    }

    get emptyHint() {
        return this.kit.search && !this.kit.chips.length
            ? _t("Nobody in this run matches “%s”. Check the spelling, or search by payslip number or employee code.", this.kit.search)
            : _t("Remove a filter above, or start again from every payslip in this run.");
    }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }
    ic(n, s = 22) { return ic(n, s); }
    // a getter, not a template literal: a literal is never extracted (F29)
    get searchHint() { return _t("Search a name, payslip number or employee code…"); }

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
        // refresh the numbers, the list and its counts, and the detail
        await this.loadHead(this.state.runId);
        await this.kit.refresh();
        await this.select(id);
    }
}

registry.category("actions").add("pb_payslip_review", PayslipReview);
