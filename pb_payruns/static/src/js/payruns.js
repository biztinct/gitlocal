/** @odoo-module **/
/**
 * The Pay Runs board.
 *
 * HISTORY WORTH KNOWING. This cockpit was built, registered as the client action
 * `pb_payruns` — and then never pointed at: the rail item and the ⌘K entry both
 * open `pb_payruns.action_pb_payruns_kanban`, the native kanban with a KPI band
 * injected into it. IA Cycle 2 revived it as the Pay Run hub's **Runs** lens.
 * The standalone client action still exists and still works — this is one
 * component with two mount points, not a fork (W6/W17).
 *
 * PAYRUN BOARD redesign (2026-10-11, docs/design/PAYRUN_BOARD_REDESIGN.md).
 * What the board is now:
 *   - a "This month" hero: the month's journey (the hub tracker's five
 *     stages), one plain sentence whose phrases filter the board, and ONE
 *     next-step button chosen from what is actually outstanding;
 *   - three equal lanes whose header IS the numbered step (the numbers line,
 *     the step strip and the column header used to say the same count three
 *     times); pressing a header focuses that lane and folds the other two;
 *   - cards with one figure (net), a delivery rail on approved runs
 *     (approved → bank file → paid → payslips → journals) so "Pay & Deliver"
 *     is the primary only while a run is unpaid, Done grouped by month;
 *   - a quick-look panel instead of leaving for the native form, multi-select
 *     with a bulk bar, keyboard moves, and a list view.
 * The reject confirm stays IN the card with its required reason (a
 * window.confirm is a native dialog on a surface that owns a design system).
 */
import { Component, useState, useRef, useEffect, onWillStart, onMounted,
         onWillUnmount, onWillPatch, onPatched, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useNavigationState } from "@pb_hub/js/navigation_state";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

// FILTER wave 5 — the board's page sizes (pb.payruns LANE_PAGE / LIST_PAGE)
// and the three steps a lane header can put in focus.
const LANE_PAGE = 30;
const LIST_PAGE = 60;
const LANE_STEPS = ["draft", "approval_pending", "done"];

// There is ONE action a card can take on the run itself now: send it in. What
// happens next is a decision, and a decision is made where the request is —
// in Approvals — never from a board button that would have to guess which step
// it is answering.
const NEXT_METHOD = {
    submit: "action_approval_submit",
};
const NEXT_LABEL = {
    submit: _t("Submit for approval"),
    decide: _t("Open the approval"),
};
// Whole sentences, one msgid each. Building "%s done" out of the button label
// above would hand a translator two fragments and no way to reorder them (W80).
const DONE_MSG = {
    submit: _t("Pay run sent in for approval."),
};

// The five stages of a month, numbered as the Pay Run hub's tracker numbers
// them (pb.pay.hub _STAGE_DOC). Stage 5 is "every run delivered".
const MONTH_STAGES = [
    _t("Not started"), _t("Drafting"), _t("In approval"), _t("Approved"), _t("Delivered"),
];

// A few Lucide glyphs the shared kit does not carry. Local on purpose: the kit
// is shared by forty screens and a board should not have to bump it to get an
// ellipsis.
const LOCAL_IC = {
    more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
    keyboard: '<rect width="20" height="16" x="2" y="4" rx="2" ry="2"/><path d="M6 8h.001"/><path d="M10 8h.001"/><path d="M14 8h.001"/><path d="M18 8h.001"/><path d="M8 12h.001"/><path d="M12 12h.001"/><path d="M16 12h.001"/><path d="M7 16h10"/>',
    grid: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    userCheck: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>',
    journal: '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/>',
};
function icon(n, s = 15) {
    if (LOCAL_IC[n]) {
        return markup(
            `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" ` +
            `stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${LOCAL_IC[n]}</svg>`);
    }
    return ic(n, s);
}

// Division monogram tints, assigned by a stable hash of the division key so
// Retail is the same teal on every board and every month.
const HUES = ["indigo", "teal", "blue", "amber", "rose", "violet"];
function hueOf(key) {
    if (!key) return "slate";
    let h = 0;
    for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
    return HUES[h % HUES.length];
}
function monogram(label, key) {
    const src = (label || key || "").trim();
    if (!src) return "PR";
    const words = src.split(/[\s_\-—]+/).filter(Boolean);
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    // one word: its first letter plus its first consonant after that, so
    // Retail → RT, Logistics → LG, Construction → CN (never a clash with CO)
    const rest = src.slice(1).replace(/[aeiouAEIOU]/g, "");
    return (src[0] + (rest[0] || src[1] || "")).toUpperCase();
}

export class PbPayruns extends Component {
    static template = "pb_payruns.PbPayruns";
    static components = { PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rejectWhy = useRef("rejectWhy");
        this.root = useRef("root");
        // the reason box takes the keyboard the moment the confirm opens
        useEffect((open) => {
            if (open && this.rejectWhy.el) { this.rejectWhy.el.focus(); }
        }, () => [this.state.confirming]);
        this.state = useState({
            loaded: false,
            busy: 0,
            confirming: 0,          // run id whose Reject is awaiting confirmation
            rejectNote: "",         // the "Why?" typed in that confirm
            currency: "",
            currencyName: "",
            currencies: [],         // the moneys of the runs on screen
            columns: [],
            // FILTER wave 5: every lane is the server's page for the panel's
            // filters — {key: {rows, total, flags}} for the three steps and
            // the Rejected drawer ('cancel'); the list view is one page.
            lanes: {},
            lanesLoaded: false,
            loadingLane: "",
            listRows: [],
            listTotal: 0,
            monthBatches: [],       // the hero's month, un-narrowed by the panel
            period: null,           // the month block the hero speaks about
            view: "board",          // 'board' | 'list'
            selected: {},           // {run id: true}
            lastSel: 0,
            peek: 0,                // run id open in the quick look
            menu: 0,                // run id whose ⋯ menu is open
            openMonths: {},         // Done lane: {month key: true}
            cur: 0,                 // keyboard cursor
            sheet: null,            // {kind:'submit', ids} | {kind:'keys'}
            showRejected: false,
            // the run the hub sent us to (arrival.focus), highlighted once
            focusId: this._arrivalFocus(),
        });
        // The filters, the search and the sort belong to the filter panel,
        // which remembers them itself; this keeps only how the board is laid
        // out (board or list, open months, cursor, scroll) for the way back.
        const savedNavigation = useNavigationState(this, "payruns", () => ({
            view: this.state.view, openMonths: { ...this.state.openMonths },
            showRejected: this.state.showRejected, cur: this.state.cur,
            scrollTop: this.root.el?.scrollTop || 0,
        }));
        if (savedNavigation) {
            const { scrollTop, view, openMonths, showRejected, cur } = savedNavigation;
            Object.assign(this.state, {
                view: view === "list" ? "list" : "board",
                openMonths: openMonths || {}, showRejected: !!showRejected, cur: cur || 0,
            });
            savedNavigation.scrollTop = scrollTop;
        }
        // The shared filter panel (pb_filter_kit). `always: ['stage']`: the
        // lane headers read the "Where it is" counts on every refresh, folded
        // or not — a lane counts against every OTHER filter (ruling R1).
        this.kit = useFilterKit({
            model: "pb.payruns",
            noun: _t("pay runs"),
            always: ["stage"],
            onChange: () => this.loadPage(),
        });
        this._rects = {};
        this._onKey = this._onKey.bind(this);
        this._onDocClick = this._onDocClick.bind(this);
        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            if (savedNavigation && this.root.el) {
                this.root.el.scrollTop = savedNavigation.scrollTop || 0;
                const card = this.root.el.querySelector(`[data-card="${this.state.cur}"]`);
                card?.focus({ preventScroll: true });
            }
            document.addEventListener("keydown", this._onKey);
            document.addEventListener("click", this._onDocClick, true);
        });
        onWillUnmount(() => {
            document.removeEventListener("keydown", this._onKey);
            document.removeEventListener("click", this._onDocClick, true);
        });
        // FLIP: a card that changes lane slides there instead of blinking.
        onWillPatch(() => { this._rects = this._snapRects(); });
        onPatched(() => { this._flip(this._rects); this._rects = {}; });
    }

    /**
     * The run id the host asked us to show.
     *
     * Read ONCE, in setup, from a prop — a mount hook reads, it never writes
     * back to the host (W21). `arrival` only arrives when the lens declared
     * `wantsArrival`, so standalone this is always 0.
     */
    _arrivalFocus() {
        const f = (this.props.arrival || {}).focus;
        const n = parseInt(f, 10);
        return Number.isFinite(n) && n > 0 ? n : 0;
    }

    get embedded() { return !!this.props.embedded; }

    /** Everything above the lanes: the hero's month, the lane names. */
    async load() {
        const d = await this.orm.call("pb.payruns", "get_board_head", []);
        Object.assign(this.state, {
            currency: d.currency, columns: d.columns || [],
            monthBatches: d.month_batches || [], period: d.period || null,
            currencyName: d.currency_name || "", loaded: true,
        });
    }

    /** The lanes (or the list) for the panel's current filters. */
    async loadPage() {
        const q = this.kit.query;
        const list = this.state.view === "list";
        try {
            const d = await this.orm.call("pb.payruns", "get_board_page", [], {
                filters: q.filters, search: q.search, sort: q.sort,
                lane: list ? "list" : null,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            if (list) {
                this.state.listRows = d.rows || [];
                this.state.listTotal = d.total || 0;
            } else {
                this.state.lanes = d.lanes || {};
                this.state.lanesLoaded = true;
            }
            // GROUP P3 — each run is priced in its own company's money, and
            // a board holding two currencies says so instead of pretending.
            this.state.currencies = d.currencies || [];
            this._afterLoad();
        } catch (e) {
            console.error("pb_payruns: the board could not load", e);
            this.notification.add(_t("The pay runs could not be loaded. Try again in a moment."), { type: "warning" });
        }
    }
    /** "Show N more" on one lane: its next page, appended. */
    async loadLane(key) {
        if (this.state.loadingLane) return;
        const q = this.kit.query;
        const lane = this.state.lanes[key];
        if (!lane) return;
        this.state.loadingLane = key;
        try {
            const d = await this.orm.call("pb.payruns", "get_board_page", [], {
                filters: q.filters, search: q.search, sort: q.sort,
                lane: key, offset: lane.rows.length,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            const got = (d.lanes || {})[key];
            if (got) {
                const have = new Set(lane.rows.map((b) => b.id));
                this.state.lanes[key] = { ...got, rows: [...lane.rows, ...got.rows.filter((b) => !have.has(b.id))] };
            }
        } catch (e) {
            console.error("pb_payruns: more pay runs could not load", e);
            this.notification.add(_t("More pay runs could not be loaded. Try again in a moment."), { type: "warning" });
        } finally {
            this.state.loadingLane = "";
        }
    }
    /** "Show N more" in the list view. */
    async loadMoreList() {
        if (this.state.loadingLane) return;
        const q = this.kit.query;
        this.state.loadingLane = "list";
        try {
            const d = await this.orm.call("pb.payruns", "get_board_page", [], {
                filters: q.filters, search: q.search, sort: q.sort,
                lane: "list", offset: this.state.listRows.length,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            const have = new Set(this.state.listRows.map((b) => b.id));
            this.state.listRows = [...this.state.listRows, ...(d.rows || []).filter((b) => !have.has(b.id))];
            this.state.listTotal = d.total || 0;
        } finally {
            this.state.loadingLane = "";
        }
    }
    lanePage(key) { return this.state.lanes[key] || { rows: [], total: 0, flags: {} }; }
    laneMore(key) {
        const l = this.lanePage(key);
        return Math.max(0, Math.min(LANE_PAGE, (l.total || 0) - l.rows.length));
    }
    get listMore() { return Math.max(0, Math.min(LIST_PAGE, this.state.listTotal - this.state.listRows.length)); }

    _afterLoad() {
        // A run the new filters no longer show is unticked, so a bulk action
        // never reaches a run nobody can see (ruling R6).
        const shown = new Set(this.batches.map((b) => b.id));
        for (const id of Object.keys(this.state.selected)) {
            if (!shown.has(Number(id))) delete this.state.selected[id];
        }
        // The Done lane opens ONE month by default: this month if it has
        // approved runs, else the latest month that does (a tenant whose last
        // run was two months ago). Reloads keep whatever the reader opened.
        if (!Object.keys(this.state.openMonths).length) {
            const keys = this.doneMonthKeys;
            const p = this.state.period;
            const pick = p && keys.includes(p.key) ? p.key : keys[0];
            if (pick) this.state.openMonths[pick] = true;
        }
    }
    /** Actions on a run reload the hero, the panel's counts and the lanes. */
    async reloadAll() {
        await Promise.all([this.load(), this.kit.refresh()]);
    }

    ic(n, s = 15) { return icon(n, s); }

    // ================================================================ words
    _runs(n) { return n === 1 ? _t("1 pay run") : _t("%s pay runs", n); }
    _people(n) { return n === 1 ? _t("1 person") : _t("%s people", this.int(n)); }
    int(n) { return Number(n || 0).toLocaleString(); }
    mono(b) { return monogram(b.division_label, b.division); }
    hue(b) { return hueOf(b.division); }
    initials(name) {
        const w = (name || "").trim().split(/\s+/).filter(Boolean);
        return ((w[0] || "?")[0] + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase();
    }

    // ================================================================ derived
    /** Every card on screen: the lanes' pages, the Rejected drawer's and
     *  the list's — the only runs a bulk action or a key press can reach. */
    get batches() {
        const out = [];
        const seen = new Set();
        const add = (b) => { if (!seen.has(b.id)) { seen.add(b.id); out.push(b); } };
        for (const lane of Object.values(this.state.lanes || {})) (lane.rows || []).forEach(add);
        (this.state.listRows || []).forEach(add);
        return out;
    }
    /** A run by id, on screen or in the hero's month. */
    findRun(id) {
        return this.batches.find((b) => b.id === id)
            || this.state.monthBatches.find((b) => b.id === id) || null;
    }
    get monthBatches() { return this.state.monthBatches || []; }
    isPaid(b) { return b.state === "done" && !!(b.delivery && b.delivery.paid); }
    isDelivered(b) { return b.state === "done" && !!(b.delivery && b.delivery.delivered); }
    get manyCurrencies() { return (this.state.currencies || []).length > 1; }

    /** The lane in focus: "Where it is" ticked to exactly one step. */
    get stepOn() {
        const v = this.kit.values("stage");
        return v.length === 1 && LANE_STEPS.includes(v[0]) ? v[0] : "";
    }
    /** A lane folds when "Where it is" is ticked and does not include it. */
    laneHidden(key) {
        const v = this.kit.values("stage");
        return v.length > 0 && !v.includes(key);
    }
    /** A lane's count: the panel's "Where it is" count (R1 — it counts
     *  against every OTHER filter, so a folded lane still says what is
     *  there); the lane's own total until the counts arrive. */
    stageCount(key) {
        const c = (this.kit.counts.stage || {}).values || [];
        const row = c.find((r) => String(r.v) === key);
        return row ? row.n : (this.lanePage(key).total || 0);
    }
    columnBatches(key) { return this.laneHidden(key) ? [] : this.lanePage(key).rows; }

    /** Lane headers: the numbered step, its count and its one flag. */
    get lanes() {
        const hints = {
            draft: _t("Still being prepared. Submit when the figures are right."),
            approval_pending: _t("With the people on its sign-off route."),
            done: _t("Approved. Pay, deliver payslips and post journals from here."),
        };
        const focus = this.stepOn;
        return this.state.columns.map((col, i) => {
            const page = this.lanePage(col.key);
            const total = this.stageCount(col.key);
            const fl = this.laneHidden(col.key) ? {} : (page.flags || {});
            let flag = "", tone = "";
            if (col.key === "approval_pending") {
                const me = fl.mine || 0;
                const all = this.laneHidden(col.key) ? 0 : page.total || 0;
                if (me) { flag = me === 1 ? _t("1 is waiting on you") : _t("%s are waiting on you", me); tone = "me"; }
                else if (all) { flag = all === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", all); tone = "amber"; }
            } else if (col.key === "draft") {
                const back = fl.back || 0;
                const bad = fl.bad || 0;
                if (back) { flag = back === 1 ? _t("1 sent back to be fixed") : _t("%s sent back to be fixed", back); tone = "amber"; }
                else if (bad) { flag = bad === 1 ? _t("1 run needs a check before it is sent in") : _t("%s runs need a check before they are sent in", bad); tone = "rose"; }
            } else if (col.key === "done") {
                const topay = fl.topay || 0;
                if (topay) { flag = topay === 1 ? _t("1 approved, not paid yet") : _t("%s approved, not paid yet", topay); tone = "indigo"; }
            }
            const hidden = this.laneHidden(col.key);
            return {
                key: col.key, n: String(i + 1).padStart(2, "0"), title: col.label,
                count: total, countLabel: this._runs(total), hint: hints[col.key] || "",
                flag, tone, on: focus === col.key,
                collapsed: hidden,
                shown: this.columnBatches(col.key),
                more: hidden ? 0 : this.laneMore(col.key),
                monos: page.rows.slice(0, 4),
            };
        });
    }
    get boardClass() {
        // one lane open and two folded: the grid gives the open one the room
        const open = this.state.columns.map((c, i) => (this.laneHidden(c.key) ? -1 : i)).filter((i) => i >= 0);
        const focus = open.length === 1 ? "f" + (open[0] + 1) : open.length ? "" : "none";
        return focus + (this.selectedIds.length ? " selecting" : "");
    }

    /** Month groups inside a lane. Done folds older months; the others only
     *  draw a divider when more than one month is present. */
    groups(key) {
        const rs = this.columnBatches(key);
        const months = [];
        for (const b of rs) if (!months.includes(b.month)) months.push(b.month);
        if (months.length < 2) return [{ key: months[0] || "", label: "", runs: rs, open: true, fold: false }];
        return months.map(m => {
            const runs = rs.filter(b => b.month === m);
            const fold = key === "done";
            const open = !fold || !!this.state.openMonths[m] || !!this.kit.search;
            const net = runs.reduce((s, b) => s + (b.net || 0), 0);
            const cur = runs[0] && runs[0].currency;
            const count = runs.length === 1 ? _t("1 run") : _t("%s runs", runs.length);
            const topay = runs.filter(b => !this.isPaid(b)).length;
            return {
                key: m, label: runs[0].month_label || m, runs, fold, open, count, topay,
                sub: topay ? _t("%(count)s · %(n)s to pay", { count, n: topay }) : count,
                net: runs.every(b => b.currency === cur) ? this.money(net, cur) : "",
            };
        });
    }
    get doneMonthKeys() {
        const out = [];
        for (const b of this.lanePage("done").rows) if (!out.includes(b.month)) out.push(b.month);
        return out;
    }
    toggleMonth(m) {
        if (this.state.openMonths[m]) delete this.state.openMonths[m];
        else this.state.openMonths[m] = true;
    }

    // ================================================================ hero
    get hero() {
        const p = this.state.period;
        if (!p) return null;
        const rs = this.monthBatches;
        const drafts = rs.filter(b => b.state === "draft");
        const waiting = rs.filter(b => b.state === "approval_pending");
        const mine = rs.filter(b => b.awaiting_me);
        const back = rs.filter(b => b.return_note);
        const topay = rs.filter(b => b.state === "done" && !this.isPaid(b));
        const paid = rs.filter(b => this.isPaid(b));
        const divisions = new Set(rs.map(b => b.division).filter(Boolean)).size;
        const stage = p.stage || 1;
        const journey = MONTH_STAGES.map((label, i) => ({
            label, n: i + 1, done: i + 1 < stage, now: i + 1 === stage,
        }));
        const phrases = [];
        if (drafts.length) phrases.push({ key: "drafts", text: drafts.length === 1 ? _t("1 is still a draft") : _t("%s are still drafts", drafts.length) });
        if (waiting.length) phrases.push({ key: "waiting", text: waiting.length === 1 ? _t("1 is waiting for a sign-off") : _t("%s are waiting for a sign-off", waiting.length) });
        if (topay.length) phrases.push({ key: "topay", text: topay.length === 1 ? _t("1 is approved and ready to pay") : _t("%s are approved and ready to pay", topay.length) });
        if (paid.length) phrases.push({ key: "paid", text: paid.length === 1 ? _t("1 is paid and delivered") : _t("%s are paid and delivered", paid.length) });
        phrases.forEach((ph, i) => {
            ph.sep = i === 0 ? " " : i === phrases.length - 1 ? _t(" and ") : _t(", ");
            ph.on = this.kit.loaded && this.kit.isExactly(this.phraseFilters(ph.key));
        });
        let lead, ask = "", tone = "", next, why = "";
        if (!rs.length) {
            lead = _t("No pay run covers %s yet.", p.label);
            ask = _t("Start when the month's figures are in.");
            next = { act: "newrun", icon: "zap", label: _t("Run payroll for %s", p.label) };
        } else {
            lead = divisions > 1
                ? _t("%(runs)s this month across %(n)s divisions.", { runs: this._runs(rs.length), n: divisions })
                : _t("%s this month.", this._runs(rs.length));
            if (mine.length) {
                ask = mine.length === 1 ? _t("1 pay run is waiting on you.") : _t("%s pay runs are waiting on you.", mine.length);
                tone = "amber";
                next = { act: "approve", id: mine[0].id, icon: "userCheck", label: mine.length === 1 ? _t("Open the approval") : _t("Open your approvals") };
                why = mine.length === 1 ? mine[0].name : "";
            } else if (back.length) {
                ask = back.length === 1 ? _t("1 pay run was sent back to be fixed.") : _t("%s pay runs were sent back to be fixed.", back.length);
                tone = "amber";
                next = { act: "peek", id: back[0].id, icon: "rotate", label: _t("See what to fix") };
                why = back[0].name;
            } else if (drafts.length) {
                ask = _t("Nothing is waiting on you.");
                const can = drafts.filter(b => b.can_act);
                if (can.length) {
                    next = { act: "bulksubmit", icon: "send", label: can.length === 1 ? _t("Submit the draft") : _t("Submit %s drafts for approval", can.length) };
                    why = can.length === 1 ? can[0].name : _t("Each goes to its own sign-off route.");
                } else {
                    next = { act: "focus", key: "draft", icon: "calendar", label: _t("See the drafts") };
                }
            } else if (topay.length) {
                ask = _t("Nothing is waiting on you.");
                next = { act: "paydeliver", id: topay[0].id, icon: "banknote", label: _t("Pay & Deliver") };
                why = topay.length === 1 ? topay[0].name : _t("%s runs are approved and unpaid.", topay.length);
            } else if (waiting.length) {
                ask = _t("Nothing is waiting on you.");
                next = { act: "focus", key: "approval_pending", icon: "clock", label: _t("See who it is with") };
            } else {
                ask = _t("%s is complete.", p.label);
                tone = "green";
                next = { act: "newrun", icon: "zap", label: _t("Run payroll for %s", p.next_label) };
            }
            if (back.length && mine.length) {
                why = back.length === 1 ? _t("1 run was also sent back to be fixed.") : _t("%s runs were also sent back to be fixed.", back.length);
            }
        }
        const cur = rs[0] && rs[0].currency;
        const oneMoney = rs.length && rs.every(b => b.currency === cur);
        const net = rs.reduce((s, b) => s + (b.net || 0), 0);
        const people = rs.reduce((s, b) => s + (b.employees || 0), 0);
        return {
            deadline: this.deadline(p, rs),
            label: p.label, range: p.range, stage, total: p.total || 5,
            stageLabel: MONTH_STAGES[stage - 1] || "", journey, lead, phrases, ask, tone, next, why,
            stageLine: _t("Stage %(i)s of %(n)s · %(label)s", { i: stage, n: p.total || 5, label: MONTH_STAGES[stage - 1] || "" }),
            movingLine: _t("The month moves when its slowest run does."),
            net: oneMoney ? this.money(net, cur) : "—",
            currency: oneMoney ? (rs[0].currency_name || "") : "",
            meta: rs.length ? _t("%(people)s · %(runs)s", { people: this._people(people), runs: this._runs(rs.length) }) : _t("Nothing computed yet"),
            moving: stage < 5 && rs.length > 0,
        };
    }
    /**
     * NAV P3b — the month's two dates, from the Payroll calendar (owner
     * decision 2026-10-21, reversing the 11 Oct "no pay-day words" ruling
     * that was made only because no pay-day setting existed yet).
     *   before the cut-off   "Changes close in 4 days (Fri 24 Oct) · People are paid on Fri 31 Oct"
     *   after it             "Changes closed Fri 24 Oct · People are paid on Fri 31 Oct"
     *   after pay day        green "Paid on Fri 31 Oct" once every run of the month is paid,
     *                        else amber "Pay day was Fri 31 Oct"
     * No calendar row: null, and the line is simply absent.
     * The dates arrive formatted by the server from the DATE (no JS Date).
     */
    deadline(p, rs) {
        if (!p || (!p.cutoff && !p.pay_date)) return null;
        const c = p.cutoff_in_days, pd = p.pay_in_days;
        if (p.pay_date && pd !== null && pd < 0) {
            const allPaid = rs.length > 0 && rs.every(b => this.isPaid(b));
            return allPaid
                ? { tone: "green", icon: "checkCircle", text: _t("Paid on %s", p.pay_label) }
                : { tone: "amber", icon: "alert", text: _t("Pay day was %s", p.pay_label) };
        }
        const parts = [];
        let tone = "";
        if (p.cutoff && c !== null) {
            if (c < 0) parts.push(_t("Changes closed %s", p.cutoff_label));
            else if (c === 0) parts.push(_t("Changes close today (%s)", p.cutoff_label));
            else if (c === 1) parts.push(_t("Changes close tomorrow (%s)", p.cutoff_label));
            else parts.push(_t("Changes close in %(n)s days (%(date)s)", { n: c, date: p.cutoff_label }));
            // Colour only to act (quiet board): the last two days before the
            // cut-off, while a run of the month is still a draft.
            if (c >= 0 && c <= 1 && rs.some(b => b.state === "draft")) tone = "amber";
        }
        if (p.pay_date && pd !== null) {
            parts.push(pd === 0 ? _t("People are paid today (%s)", p.pay_label)
                                : _t("People are paid on %s", p.pay_label));
        }
        return parts.length ? { tone, icon: "calendarClock", text: parts.join(" · ") } : null;
    }
    heroNext() {
        const n = this.hero && this.hero.next;
        if (!n) return;
        const b = n.id ? this.findRun(n.id) : null;
        if (n.act === "newrun") return this.newRun();
        if (n.act === "approve") return this.openApprovals();
        if (n.act === "peek") return this.openPeek(n.id);
        if (n.act === "paydeliver" && b) return this.payDeliver(b);
        if (n.act === "focus") return this.pickStep(n.key);
        if (n.act === "bulksubmit") {
            const ids = this.monthBatches.filter(b => b.state === "draft" && b.can_act).map(b => b.id);
            this.state.sheet = { kind: "submit", ids };
        }
    }
    /** The filters a phrase of the hero's sentence stands for: that kind of
     *  run, in the month the hero speaks about. */
    phraseFilters(key) {
        const month = { period: { preset: "this_month" } };
        const paid = !!this.kit.section("paid");
        if (key === "drafts") return { ...month, stage: ["draft"] };
        if (key === "waiting") return { ...month, stage: ["approval_pending"] };
        if (key === "topay") return paid ? { ...month, paid: ["topay"] } : { ...month, stage: ["done"] };
        if (key === "paid") return paid ? { ...month, paid: ["paid"] } : { ...month, stage: ["done"] };
        return {};
    }
    /** A phrase ticks exactly its filters in the panel; pressing it again
     *  goes back to the first view. */
    pressPhrase(key) { this.kit.toggleFilters(this.phraseFilters(key)); }

    // ================================================================ narrowing
    /** A lane header ticks that step in "Where it is" and keeps every other
     *  filter; pressing the lane in focus lets go of it again. */
    pickStep(key) {
        const next = { ...this.kit.filters };
        if (this.stepOn === key) { delete next.stage; } else { next.stage = [key]; }
        this.kit.setFilters(next, { search: this.kit.search });
    }
    /** Board or list: each loads its own page from the server. */
    setView(key) {
        if (this.state.view === key) return;
        this.state.view = key;
        this.loadPage();
    }
    get narrowed() { return !!(this.kit.activeCount || this.kit.search); }
    /** Rejected runs the panel's "Where it is" leaves out (shown as a line
     *  under the board, so they are never silently missing). */
    get rejectedHidden() {
        const page = this.lanePage("cancel");
        return page.total ? 0 : (this.laneHidden("cancel") ? this.stageCount("cancel") : 0);
    }
    showRejectedToo() {
        const cur = this.kit.values("stage");
        this.kit.setFilters({ ...this.kit.filters, stage: [...cur, "cancel"] }, { search: this.kit.search });
        this.state.showRejected = true;
    }
    get rejectedOpen() { return this.state.showRejected || this.kit.isOn("stage", "cancel"); }
    emptyLane(key) {
        const n = this.narrowed;
        if (key === "draft") return n ? { title: _t("Nothing in draft here.") } : { title: _t("No drafts."), sub: _t("Press Run payroll to start a new pay run."), cta: true };
        if (key === "approval_pending") return n ? { title: _t("Nothing waiting here.") } : { title: _t("Nothing is waiting."), sub: _t("A run you submit sits here until everyone on its route has signed it off.") };
        return n ? { title: _t("Nothing approved here yet.") } : { title: _t("Nothing approved yet."), sub: _t("Approved runs land here, ready to pay and deliver.") };
    }

    // ================================================================ cards
    nextLabel(a) { return NEXT_LABEL[a] || _t("Open"); }
    kindLabel(b) {
        if (b.credit_note) return _t("refund");
        return "";
    }
    /** The route segments of a waiting card. */
    route(b) {
        const a = b.approval || {};
        const total = a.step_total || 0, idx = a.step_index || 0;
        const segs = [];
        for (let i = 1; i <= total; i++) segs.push(i < idx ? "d" : i === idx ? "c" : "");
        const who = (a.with || "").split(", ").filter(Boolean);
        return {
            title: a.step ? (total ? _t("Sign-off %(i)s of %(n)s · %(step)s", { i: idx, n: total, step: a.step }) : a.step) : (a.workflow || _t("On its sign-off route")),
            state: b.awaiting_me ? _t("your turn") : a.blocked ? _t("stuck") : _t("in progress"),
            segs, who, blocked: a.blocked || "",
            withText: who.length ? _t("With %s", who.join(", ")) : _t("With nobody yet"),
        };
    }
    /** The delivery rail of a Done card. */
    delivery(b) {
        const d = b.delivery || {};
        const steps = [
            { key: "approved", label: _t("Approved"), done: true },
            { key: "bank", label: _t("Bank file"), done: !!d.bank_file },
            { key: "paid", label: _t("Paid"), done: !!d.paid },
            { key: "slips", label: _t("Payslips"), done: !!d.delivered },
            { key: "journals", label: _t("Journals"), done: !!d.journals, optional: true },
        ];
        const next = steps.findIndex(s => !s.done && !s.optional);
        steps.forEach((s, i) => { s.next = i === next; });
        let status, ok = false;
        const approvedOn = (b.approval && b.approval.closed_on) || "";
        if (!d.paid) {
            status = approvedOn ? _t("Approved %s · not paid yet", approvedOn) : _t("Approved · not paid yet");
        } else if (!d.delivered) {
            status = d.paid_on ? _t("Paid %s · payslips not sent yet", d.paid_on) : _t("Paid · payslips not sent yet");
        } else {
            ok = true;
            status = d.paid_on
                ? _t("Paid %(date)s · %(n)s payslips sent", { date: d.paid_on, n: this.int(d.slips_sent) })
                : _t("Paid · %s payslips sent", this.int(d.slips_sent));
            if (d.journals) status += _t(" · journals posted");
        }
        return { steps, status, ok, paid: !!d.paid };
    }
    /**
     * NAV P3b — the card's checklist: can this run move, and who must act.
     * The lines come from the server (`b.checks`, in the spec's order, each
     * with its owner); a draft with nothing in its way ends on one green
     * "Ready to send in". Done and Rejected cards draw no checklist. The
     * waiting-for-a-person line stays the route block's job (not repeated).
     */
    checks(b) {
        if (b.state !== "draft" && b.state !== "approval_pending") return [];
        const out = (b.checks || []).map((c, i) => Object.assign({ i }, c, {
            tip: c.advisory ? _t("Advice only. It does not stop the run from being sent in.") : "",
        }));
        if (b.ready) {
            out.push({ i: out.length, key: "ready", tone: "green", icon: "checkCircle",
                       text: _t("Ready to send in"), detail: "", owner: null, next: null, advisory: false, more: "" });
        }
        return out;
    }
    /** The owner chip: initials and given name, "you" lit for the reader. */
    ownerLabel(o) { return o ? (o.me ? _t("you") : (o.short || o.name)) : ""; }
    ownerTitle(o) { return o ? (o.me ? _t("%s (you)", o.name) : o.name) : ""; }
    /** "Weeks closed: 3 of the 4 weeks so far" on the quick look, when the
     *  close line exists. Only weeks that have started are counted. */
    weeksClosed(b) {
        const w = b.close_weeks;
        if (!w || !w.total || !(b.checks || []).some(c => c.key === "close_week")) return "";
        return _t("Weeks closed: %(n)s of the %(total)s weeks so far", { n: w.closed, total: w.total });
    }
    /** A checklist line's one door. `run` opens the run (its payslips and
     *  components are there); `close` opens Workforce › Close with a back
     *  chip to where the reader was. Named by xmlid string: this board never
     *  depends on the module that owns the destination. */
    async openCheck(b, c) {
        const key = c && c.next && c.next.key;
        if (key === "run") return this.openBatch(b.id);
        if (key !== "close") return;
        this.state.peek = 0;
        this.state.menu = 0;
        const back = this.embedded
            ? { label: String(_t("Payroll")), tag: "", xmlid: "pb_payhub.action_pb_pay_hub", lens: "runs", lensKey: "pb_lens", context: {} }
            : { label: String(_t("Pay runs")), tag: "pb_payruns", xmlid: "", lens: "", lensKey: "pb_lens", context: {} };
        try {
            await this.action.doAction("pb_mission.action_pb_workforce", {
                additionalContext: { pb_shell_lens: "close", pb_back: back },
                clearBreadcrumbs: true,
            });
        } catch {
            this.notification.add(_t("Workforce is not available on this server."), { type: "warning" });
        }
    }

    // ================================================================ selection
    get selectedIds() { return Object.keys(this.state.selected).map(Number); }
    isSelected(id) { return !!this.state.selected[id]; }
    toggleSelect(b, ev) {
        if (ev && ev.shiftKey && this.state.lastSel) {
            // shift-select walks the runs SHOWN: the list's rows, or the lane's
            const col = (this.state.view === "list" ? this.state.listRows : this.columnBatches(b.state)).map(x => x.id);
            const a = col.indexOf(this.state.lastSel), z = col.indexOf(b.id);
            if (a > -1 && z > -1) {
                col.slice(Math.min(a, z), Math.max(a, z) + 1).forEach(id => { this.state.selected[id] = true; });
                this.state.lastSel = b.id;
                return;
            }
        }
        if (this.state.selected[b.id]) delete this.state.selected[b.id];
        else this.state.selected[b.id] = true;
        this.state.lastSel = b.id;
    }
    clearSelection() { this.state.selected = {}; }
    get bulk() {
        // only runs on screen: a selection never reaches a run the filters hide (R6)
        const shown = this.batches;
        const rs = this.selectedIds.map(id => shown.find(b => b.id === id)).filter(Boolean);
        if (!rs.length) return null;
        const cur = rs[0].currency;
        const net = rs.reduce((s, b) => s + (b.net || 0), 0);
        return {
            n: rs.length === 1 ? _t("1 pay run selected") : _t("%s pay runs selected", rs.length),
            net: rs.every(b => b.currency === cur) ? _t("%s net", this.money(net, cur)) : "",
            canSubmit: rs.every(b => b.state === "draft" && b.can_act),
            ids: rs.map(b => b.id),
        };
    }
    bulkSubmit() { this.state.sheet = { kind: "submit", ids: this.bulk.ids }; }
    async bulkExcel() {
        for (const id of this.selectedIds) {
            const b = this.findRun(id);
            if (b) await this._run("action_download_payslip_xlsx", b.id, null, null, true);
        }
    }

    // ================================================================ sheets
    get sheetRuns() {
        const s = this.state.sheet;
        if (!s || s.kind !== "submit") return [];
        return s.ids.map(id => this.findRun(id)).filter(Boolean);
    }
    closeSheet() { this.state.sheet = null; }
    openKeys() { this.state.sheet = { kind: "keys" }; }
    get keys() {
        return [
            { what: _t("Move between runs"), keys: ["↑", "↓"] },
            { what: _t("Move between steps"), keys: ["←", "→"] },
            { what: _t("Quick look"), keys: ["Enter"] },
            { what: _t("Select / unselect"), keys: ["Space"] },
            { what: _t("Submit a draft"), keys: ["S"] },
            { what: _t("Find a run"), keys: ["/"] },
            { what: _t("Close / clear"), keys: ["Esc"] },
            { what: _t("This help"), keys: ["?"] },
        ];
    }
    async confirmSheet() {
        const ids = (this.state.sheet && this.state.sheet.ids) || [];
        this.state.sheet = null;
        await this.submitMany(ids);
    }

    // ================================================================ quick look
    openPeek(id) { this.state.peek = id; this.state.menu = 0; this.state.cur = id; }
    closePeek() { this.state.peek = 0; }
    get peekRun() { return this.state.peek ? this.findRun(this.state.peek) : null; }
    peekSteps(b) {
        const at = b.state === "draft" ? 0 : b.state === "approval_pending" ? 1 : b.state === "done" ? 2 : -1;
        return this.state.columns.map((c, i) => ({
            key: c.key, n: String(i + 1).padStart(2, "0"), title: c.label,
            cls: i < at ? "d" : i === at ? (i === 1 && b.awaiting_me ? "w" : "n") : "",
        }));
    }
    peekRoute(b) {
        const a = b.approval || {};
        return (a.steps || []).map(st => ({
            title: st.title, done: st.status === "done", now: st.status === "active",
            meta: st.status === "done"
                ? (st.decided_by.length ? _t("Signed off by %s", st.decided_by.join(", ")) : _t("Decided")) + (st.decided_on ? " · " + st.decided_on : "")
                : st.status === "active"
                    ? (b.awaiting_me ? _t("Waiting on you") : (st.with.length ? _t("With %s", st.with.join(", ")) : _t("With nobody yet")))
                    : st.status === "skipped" ? _t("Not needed") : _t("Later"),
        }));
    }
    peekDelivery(b) {
        const d = b.delivery || {};
        const a = b.approval || {};
        return [
            { title: _t("Approved"), done: true, meta: a.closed_on || "" },
            { title: _t("Bank file made"), done: !!d.bank_file, meta: "" },
            { title: _t("Paid"), done: !!d.paid, meta: d.paid_on || "" },
            { title: _t("Payslips emailed"), done: !!d.delivered, meta: d.delivered ? _t("%s sent", this.int(d.slips_sent)) : "" },
            { title: _t("Journals posted"), done: !!d.journals, meta: d.journals_on || "" },
        ].map((s, i, arr) => {
            const firstOpen = arr.findIndex(x => !x.done);
            const now = !s.done && i === firstOpen;
            return Object.assign(s, {
                now,
                meta: s.done ? (s.meta || _t("done")) : now ? _t("next") : _t("later"),
            });
        });
    }
    get laneTitles() { return { all: _t("Show every step"), one: _t("Show only this step") }; }
    /** Filters on and not one run on the board (lanes and drawer alike). */
    get nothingMatches() {
        if (!this.narrowed) return false;
        if (this.state.view === "list") return !this.state.listRows.length && !this.state.listTotal;
        if (!this.state.lanesLoaded) return false;
        return Object.values(this.state.lanes || {}).every((l) => !(l.total || 0));
    }
    get emptyHint() {
        return this.kit.search && !this.kit.chips.length
            ? _t("No pay run is called “%s”. Check the spelling, or search by division.", this.kit.search)
            : _t("Remove a filter above, or start again from every pay run.");
    }
    get rejectedHiddenLine() {
        const n = this.rejectedHidden;
        return n === 1 ? _t("1 rejected pay run is not shown by these filters.")
            : _t("%s rejected pay runs are not shown by these filters.", n);
    }
    get sheetTitle() { return _t("Submit %s for approval?", this._runs(this.sheetRuns.length)); }
    get sheetButton() { const n = this.sheetRuns.length; return n > 1 ? _t("Submit all %s", n) : _t("Submit"); }
    subLine(b) { return _t("%(people)s · gross %(gross)s", { people: this._people(b.employees), gross: this.runGross(b) }); }
    balanceLine(b) {
        return b.balance_ok === false
            ? _t("%s unaccounted for. Open the run to see which component.", this.money(b.balance_gap, b.currency))
            : _t("Gross − deductions = net. The figures add up.");
    }
    unsourcedLine(b) {
        return b.unsourced === 1 ? _t("1 payslip was computed with no source data.")
            : _t("%s payslips were computed with no source data.", b.unsourced);
    }
    peekFigures(b) {
        return [
            { key: "gross", label: _t("Gross"), v: this.money(b.gross, b.currency) },
            { key: "ded", label: _t("Deductions"), v: this.money(b.deductions, b.currency) },
            { key: "cost", label: _t("Employer cost"), v: this.money(b.employer_cost, b.currency) },
            { key: "pp", label: _t("Net per person"), v: b.employees ? this.money((b.net || 0) / b.employees, b.currency) : "—" },
        ];
    }
    fullMoney(b) {
        const n = Math.round(b.net || 0).toLocaleString();
        return b.currency_name ? `${b.currency || ""}${n} ${b.currency_name}` : `${b.currency || ""}${n}`;
    }

    // ================================================================ money
    /* A run's own figures are ALWAYS drawn through these two, never through
       `money()` directly. `money()` falls back to the board's currency, which
       is the reader's company — so an India run on a Vietnamese board came out
       in dong. One board can hold several currencies; a per-run figure has no
       business defaulting to any of them. */
    runGross(b) { return this.money(b.gross, b.currency); }
    runMoney(b) { return this.money(b.net, b.currency); }
    money(n, symbol) {
        if (n === null || n === undefined) return "—";
        const cur = symbol || this.state.currency || "₫";
        const a = Math.abs(n);
        const sign = n < 0 ? "−" : "";
        if (a >= 1e9) return sign + cur + (a / 1e9).toFixed(2) + "B";
        if (a >= 1e6) return sign + cur + (a / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return sign + cur + (a / 1e3).toFixed(0) + "K";
        return sign + cur + Math.round(a);
    }

    // ================================================================ list view
    // FILTER wave 5: the list is one server page in the panel's sort; a
    // column header picks the matching sort from the panel's sort menu.
    get listRows() { return this.state.listRows; }
    sortBy(k) {
        const cur = this.kit.sort;
        let next = { name: "name", employees: "people", gross: "gross", net: "net" }[k];
        if (k === "date_end") next = cur === "latest" ? "oldest" : "latest";
        if (next && next !== cur && this.kit.sorts.some((s) => s.key === next)) this.kit.setSort(next);
    }
    sortMark(k) {
        const cur = this.kit.sort;
        if (k === "date_end") return cur === "latest" ? " ↓" : cur === "oldest" ? " ↑" : "";
        const key = { name: "name", employees: "people", gross: "gross", net: "net" }[k];
        return key && cur === key ? (k === "name" ? " ↑" : " ↓") : "";
    }
    pill(b) {
        if (b.state === "draft") return b.return_note ? { cls: "waiting", text: _t("Sent back") } : { cls: "draft", text: _t("Draft") };
        if (b.state === "approval_pending") return { cls: "waiting", text: b.awaiting_me ? _t("Waiting on you") : this.route(b).withText };
        if (this.isPaid(b)) return { cls: "done", text: b.delivery.paid_on ? _t("Paid %s", b.delivery.paid_on) : _t("Paid") };
        return { cls: "approved", text: _t("Approved · to pay") };
    }

    // ================================================================ navigation
    openBatch(id) {
        if (!id) return;
        this.state.peek = 0;
        this.state.menu = 0;
        this.state.cur = id;
        // target:"current" WITHOUT clearBreadcrumbs — the breadcrumb is the way
        // back to the hub, and the run form is VU-skinned, so this is a real
        // door with a real return path (W5).
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: id, views: [[false, "form"]], target: "current",
        });
    }

    /**
     * "Run payroll".
     *
     * Standalone it opens the wizard's own action. In a hub the wizard is
     * already a LENS, and replacing the whole workspace with a full-page action
     * would throw the user out of the hub to reach a surface that is one rail
     * click away — so the host hands in a callback and the hub switches lens.
     */
    newRun() {
        if (this.props.onRunPayroll) { return this.props.onRunPayroll(); }
        this.action.doAction("pb_payrun_wizard.action_pb_payrun_wizard", { clearBreadcrumbs: true });
    }

    // ================================================================ workflow actions
    async _run(method, id, okMsg, ctx, keepBusy) {
        if (!id || (this.state.busy && !keepBusy)) return;
        this.state.busy = id;
        try {
            const res = await this.orm.call("hr.payslip.run", method, [[id]],
                ctx ? { context: ctx } : {});
            if (res && typeof res === "object" && res.type) {
                // act_url / client action → run it; notifications → toast
                await this.action.doAction(res);
            } else if (okMsg) {
                this.notification.add(okMsg, { type: "success" });
            }
            await this.reloadAll();
        } catch (e) {
            this.notification.add(e.message ? e.message.toString() : _t("Action failed"), { type: "danger" });
        } finally {
            this.state.busy = 0;
        }
    }
    advance(b) {
        if (b.next_action === "decide") { return this.openApprovals(); }
        const method = NEXT_METHOD[b.next_action];
        if (method) {
            this.state.peek = 0;
            this.state.menu = 0;
            this._run(method, b.id, DONE_MSG[b.next_action]);
        }
    }
    /** Send several drafts in, one after another, and say how many went. */
    async submitMany(ids) {
        if (!ids.length || this.state.busy) return;
        let sent = 0;
        const failed = [];
        for (const id of ids) {
            this.state.busy = id;
            try {
                await this.orm.call("hr.payslip.run", NEXT_METHOD.submit, [[id]]);
                sent += 1;
                delete this.state.selected[id];
            } catch (e) {
                failed.push(e.message ? e.message.toString() : _t("Action failed"));
            }
        }
        this.state.busy = 0;
        await this.reloadAll();
        if (sent) {
            this.notification.add(sent === 1 ? DONE_MSG.submit : _t("%s pay runs sent in for approval.", sent), { type: "success" });
        }
        if (failed.length) this.notification.add(failed[0], { type: "danger" });
    }

    /** The one door to a decision. Named as a plain string rather than
     *  imported, so this board never depends on the module that owns it. */
    async openApprovals() {
        this.state.peek = 0;
        this.state.menu = 0;
        try {
            await this.action.doAction(
                "pb_approval_config.action_pb_approval_inbox");
        } catch {
            this.notification.add(
                _t("Approvals are not available on this server."),
                { type: "warning" });
        }
    }

    // ---- reject: an in-card confirm, never a native dialog ----
    // LEARN REFRESH step 6: the confirm asks "Why?" and will not reject
    // without an answer; the reason rides the context (pb_reject_note) and is
    // kept on the run, shown in the Rejected list and on the run form.
    askReject(b) {
        this.state.rejectNote = "";
        this.state.confirming = b.id;
        this.state.menu = 0;
        this.state.peek = 0;
    }
    cancelReject() { this.state.confirming = 0; this.state.rejectNote = ""; }
    get rejectNoteOk() { return !!(this.state.rejectNote || "").trim(); }
    onRejectKey(ev, b) {
        if (ev.key === "Escape") { ev.preventDefault(); this.cancelReject(); }
        else if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault(); this.confirmReject(b);
        }
    }
    confirmReject(b) {
        const note = (this.state.rejectNote || "").trim();
        if (!note) { this.rejectWhy.el && this.rejectWhy.el.focus(); return; }
        this.state.confirming = 0;
        this.state.rejectNote = "";
        delete this.state.selected[b.id];
        this._run("action_payslip_run_cancel", b.id, _t("Pay run rejected"),
                  { pb_reject_note: note });
    }

    report(b) { this.state.menu = 0; this._run("action_open_payroll_report", b.id); }
    excel(b) { this.state.menu = 0; this._run("action_download_payslip_xlsx", b.id); }
    // Phase F: the bespoke Pay & Deliver experience replaces the legacy
    // "Bank file" + "Email" launchers (bank transfer file + payslip delivery).
    payDeliver(b) { this.state.menu = 0; this.state.peek = 0; this._run("action_pb_pay_deliver", b.id); }
    journals(b) { this.state.menu = 0; this._run("action_pb_journals", b.id); }
    payments(b) { this.state.menu = 0; this._run("action_pb_payments", b.id); }

    toggleMenu(b) { this.state.menu = this.state.menu === b.id ? 0 : b.id; }
    toggleRejected() { this.state.showRejected = !this.state.showRejected; }
    /** The Rejected drawer: the server's page of rejected runs for the
     *  panel's filters (it narrows with the division, the period, …). */
    get rejectedBatches() { return this.columnBatches("cancel"); }
    get rejectedCount() { return this.laneHidden("cancel") ? 0 : this.lanePage("cancel").total || 0; }

    // ================================================================ keyboard + motion
    _onDocClick(ev) {
        // any click outside an open ⋯ menu closes it
        if (this.state.menu && !ev.target.closest(".pbr-menu, .pbr-more")) this.state.menu = 0;
    }
    _typing(ev) {
        const t = ev.target;
        const tag = (t && t.tagName || "").toLowerCase();
        return tag === "input" || tag === "textarea" || tag === "select" || (t && t.isContentEditable);
    }
    _onKey(ev) {
        const el = this.root.el;
        if (!el || !el.isConnected || el.offsetParent === null) return; // not the lens on screen
        const s = this.state;
        if (ev.key === "Escape") {
            // the panel's search box clears itself on Escape (pb_filter_kit)
            if (this._typing(ev)) return;
            if (s.sheet) { s.sheet = null; return; }
            if (s.peek) { s.peek = 0; return; }
            if (s.menu) { s.menu = 0; return; }
            if (this.selectedIds.length) { this.clearSelection(); return; }
            // a lane in focus lets go (the other filters stay)
            if (this.stepOn) { this.pickStep(this.stepOn); }
            return;
        }
        if (this._typing(ev) || ev.metaKey || ev.ctrlKey || ev.altKey) return;
        // "/" (find a run) is the filter panel's own key now
        if (ev.key === "?") { ev.preventDefault(); this.openKeys(); return; }
        if (s.view !== "board" || !s.loaded || s.sheet) return;
        const cols = this.state.columns.map(c => this.groups(c.key).flatMap(g => g.open ? g.runs.map(b => b.id) : []));
        let ci = cols.findIndex(c => c.includes(s.cur));
        let ri = ci > -1 ? cols[ci].indexOf(s.cur) : -1;
        const move = (dc, dr) => {
            if (ci < 0) { ci = cols.findIndex(c => c.length); ri = 0; }
            else {
                if (dc) {
                    let n = ci, guard = 0;
                    do { n = (n + dc + cols.length) % cols.length; guard++; } while (!cols[n].length && guard < cols.length);
                    ci = n; ri = Math.min(Math.max(ri, 0), cols[ci].length - 1);
                }
                if (dr) ri = Math.max(0, Math.min(cols[ci].length - 1, ri + dr));
            }
            if (ci < 0 || !cols[ci] || !cols[ci].length) return;
            s.cur = cols[ci][ri];
            const card = el.querySelector(`[data-card="${s.cur}"]`);
            card && card.scrollIntoView({ block: "nearest", behavior: "smooth" });
        };
        const b = s.cur ? this.batches.find(x => x.id === s.cur) : null;
        switch (ev.key) {
            case "ArrowDown": ev.preventDefault(); move(0, 1); break;
            case "ArrowUp": ev.preventDefault(); move(0, -1); break;
            case "ArrowRight": ev.preventDefault(); move(1, 0); break;
            case "ArrowLeft": ev.preventDefault(); move(-1, 0); break;
            case "Enter": if (b) { ev.preventDefault(); this.openPeek(b.id); } break;
            case " ": if (b) { ev.preventDefault(); this.toggleSelect(b); } break;
            case "s": case "S": if (b && b.state === "draft" && b.can_act) this.advance(b); break;
        }
    }
    _snapRects() {
        const out = {};
        const el = this.root.el;
        if (!el) return out;
        el.querySelectorAll("[data-card]").forEach(c => { out[c.dataset.card] = c.getBoundingClientRect(); });
        return out;
    }
    _flip(before) {
        const el = this.root.el;
        if (!el || !before || typeof el.animate !== "function") return;
        if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        el.querySelectorAll("[data-card]").forEach(c => {
            const b = before[c.dataset.card];
            if (!b) return;
            const a = c.getBoundingClientRect();
            const dx = b.left - a.left, dy = b.top - a.top;
            if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {
                c.animate([{ transform: `translate(${dx}px,${dy}px)`, opacity: .7 }, { transform: "none", opacity: 1 }],
                          { duration: 480, easing: "cubic-bezier(.2,.8,.2,1)" });
            }
        });
    }
}

registry.category("actions").add("pb_payruns", PbPayruns);
