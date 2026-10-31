/** @odoo-module **/
/**
 * Overtime Desk — a bespoke cockpit over the OT approval queue + the Bonus
 * Hours engine. Two views: the board (hero KPIs · approval queue with ceiling
 * context + live split chips · config gallery) and the server-gated Bonus Hours
 * review (filter rail + grouped table + CSV export). RPC facade: pb.ot.desk.
 * pbim-tokenized (.pbot.pbim), amber OT tint. Lucide icons only.
 */
import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_hr_workforce/js/pbot_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const MODEL = "pb.ot.desk";
/** Queue cards per page of the filter panel (server: `_QUEUE_PAGE`). */
const PAGE = 40;

export class PbOtDesk extends Component {
    static template = "pb_hr_workforce.PbOtDesk";
    static components = { PbFilterLayout };
    static props = {
        action: { type: Object, optional: true },
        // W17 (P3a): Mission Control owns the page identity, so `embedded`
        // suppresses the hero's eyebrow/title/subtitle and nothing else. The
        // Bonus Hours door beside it, the bonus view's own filter rail and every
        // facade call stay exactly as they are — the shell has no department or
        // period opinion to replace them with (P3a §3.4).
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
            view: "board",             // board | bonus
            data: null,
            // the approval queue, one page at a time for the filter panel
            rows: [],
            total: 0,
            listLoaded: false,
            loadingMore: false,
            selected: {},              // id -> true (bulk tray)
            rowResults: {},            // id -> {ok, error} after a bulk act
            refuseOpen: false,
            refuseNote: "",
            refuseIds: [],
            bonus: this._blankBonus(),
        });
        // The Bonus door is gated on `can_view_bonus`, which only exists once
        // the board has loaded — so the instruction is consumed AFTER it.
        this._cmdNonce = 0;
        // FILTER wave 8: the queue sits on the shared filter panel. The panel
        // owns the filters, the counts and the views; this desk loads one page
        // of cards for kit.query. The Bonus Hours review keeps its own rail.
        this.kit = useFilterKit({
            model: MODEL,
            noun: _t("requests"),
            onChange: () => this.loadQueue(),
        });
        onWillUpdateProps((next) => { this._applyPbCmd(next.pbCmd); });
        onWillStart(async () => {
            await this.load();
            this._applyPbCmd(this.props.pbCmd);
        });
    }

    _blankBonus() {
        return {
            loaded: false,
            data: null,
            group_by: "employee",
            preset: "month",
            date_from: "",
            date_to: "",
            employee: "",
            department: "",
            overtime_type: "",
            min_hours: "",
            page: 0,
        };
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_desk", [], { with_queue: false });
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    // -------------------------------------------------------------- queue
    /** One page of the queue for the panel's current filters. */
    async loadQueue({ more = false } = {}) {
        if (this.kit.refusal) {
            // a pure bonus viewer: the desk shows its own sentence instead
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(MODEL, "get_queue_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.total = d.total;
            this.state.listLoaded = true;
            if (!more) {
                // The filters changed: a tick on a card nobody can see any
                // more would be an approval nobody asked for (R6).
                const ids = new Set(d.rows.map((r) => String(r.id)));
                for (const id of Object.keys(this.state.selected)) {
                    if (!ids.has(id)) { delete this.state.selected[id]; }
                }
            }
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The queue could not be listed. Try again in a moment."), { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadQueue({ more: true }); } }
    get hasMore() { return this.state.rows.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.rows.length); }
    get showingLine() {
        return _t("Showing %(shown)s of %(total)s", {
            shown: this.fmtInt(this.state.rows.length), total: this.fmtInt(this.state.total) });
    }
    get nextLabel() { return _t("Show %s more", this.fmtInt(this.nextPage)); }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    get queue() { return this.state.rows; }
    /** Cards that can still be decided: the ones a tick or a button acts on. */
    get actable() { return this.state.rows.filter((q) => q.can_act); }
    get kpis() { return (this.state.data && this.state.data.kpis) || {}; }

    /** Is the panel on its start view (To approve) with nothing typed? */
    get atHome() {
        const v = this.kit.views[0];
        return !!v && this.kit.isExactly(v.filters || {});
    }
    get emptyKind() {
        if (this.atHome) { return "clear"; }
        if (this.kit.search && !this.kit.activeCount) { return "search"; }
        return "filters";
    }
    get searchEmptyTitle() { return _t("Nothing matches “%s”", this.kit.search); }
    startAgain() { this.kit.home(); }

    /**
     * The four tiles as one quiet line. The month's hours by overtime type,
     * which used to be a stacked bar, become one neutral figure per type
     * that has any hours. Bonus hours opens the bonus review.
     */
    get glance() {
        const k = this.kpis;
        // The figures that are filters press the panel (FILTER wave 8); "near
        // or over the ceiling" is a Python fact about people, not a field of a
        // request, so it stays a plain figure.
        const f = this.glanceFilters;
        const live = this.kit.loaded && !this.kit.failed;
        const rows = [
            { key: "pending", n: k.pending || 0, label: _t("pending approvals"), tone: k.pending ? "amber" : "",
              run: live ? () => this.kit.toggleFilters(f.pending) : null },
            { key: "ceiling", n: k.over_ceiling || 0, label: _t("near or over the ceiling"), tone: k.over_ceiling > 0 ? "rose" : "", run: null },
        ];
        if (this.state.data && this.state.data.can_view_bonus) {
            rows.push({ key: "bonus", n: this.fmt(k.bonus_month || 0), label: _t("bonus hours this month"), tone: "", run: () => this.openBonus() });
        }
        for (const b of k.by_type || []) {
            if (b.hours > 0) {
                const tf = f["t-" + b.type];
                rows.push({ key: "t-" + b.type, n: this.fmt(b.hours) + "h", label: _t("%s this month", this.typeLabel(b.type)), tone: "",
                            run: live && tf ? () => this.kit.toggleFilters(tf) : null });
            }
        }
        return rows;
    }
    get glanceFilters() {
        const out = { pending: { status: ["submitted"] } };
        for (const t of ["weekday", "weekend", "holiday", "night"]) {
            // the month's hours by type count what waits and what was approved
            out["t-" + t] = { type: [t], status: ["approved", "submitted"], day: { preset: "this_month" } };
        }
        return out;
    }
    get glanceOn() {
        if (!this.kit.loaded || this.kit.failed) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }
    get selectedIds() {
        return Object.keys(this.state.selected).filter((k) => this.state.selected[k]).map(Number);
    }
    get selectedCount() { return this.selectedIds.length; }

    isSelected(id) { return !!this.state.selected[id]; }
    toggle(id) { this.state.selected[id] = !this.state.selected[id]; }
    /** The kit's page (R6): every card shown that can still be decided. */
    selectAll() {
        const rows = this.actable;
        const all = this.allSelected;
        for (const q of rows) { this.state.selected[q.id] = !all; }
    }
    get allSelected() {
        const rows = this.actable;
        return !!rows.length && rows.every((q) => this.state.selected[q.id]);
    }
    get selectAllLabel() {
        return this.allSelected ? _t("Clear the selection")
            : _t("Select the %s waiting here", this.fmtInt(this.actable.length));
    }
    clearSel() { this.state.selected = {}; }

    fmt(v) {
        const n = Number(v || 0);
        return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
    }
    pct(used, cap) {
        if (!cap) { return 0; }
        return Math.min(100, Math.round((100 * (used || 0)) / cap));
    }
    barTone(used, cap) {
        const p = this.pct(used, cap);
        return p >= 90 ? "rose" : p >= 70 ? "amber" : "ok";
    }

    async approveOne(id) { await this._act([id], "approve"); }
    async refuseOne(id) { this._openRefuse([id]); }
    async bulkApprove() {
        if (!this.selectedCount) { return; }
        await this._act(this.selectedIds, "approve");
    }
    bulkRefuse() {
        if (!this.selectedCount) { return; }
        this._openRefuse(this.selectedIds);
    }

    _openRefuse(ids) {
        this.state.refuseIds = ids;
        this.state.refuseNote = "";
        this.state.refuseOpen = true;
    }
    cancelRefuse() { this.state.refuseOpen = false; this.state.refuseIds = []; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }
    async confirmRefuse() {
        const ids = this.state.refuseIds;
        this.state.refuseOpen = false;
        await this._act(ids, "refuse", this.state.refuseNote || false);
    }

    async _act(ids, action, note) {
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "act", [ids, action], { note });
            const results = (res && res.results) || [];
            let ok = 0;
            const fails = [];
            for (const r of results) {
                this.state.rowResults[r.id] = r;
                if (r.ok) { ok += 1; } else { fails.push(r); }
            }
            if (ok) {
                this.notif.add(
                    _t("%s overtime request(s) %s.", ok,
                        action === "approve" ? _t("approved") : _t("refused")),
                    { type: "success" });
            }
            if (fails.length) {
                this.notif.add(
                    fails.map((f) => `${f.name || f.id}: ${f.error}`).join("  ·  "),
                    { type: "warning", sticky: fails.length > 1 });
            }
            this.clearSel();
            // the numbers, then the counts and the page, in place
            await this.load();
            await this.kit.refresh();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    typeLabel(t) {
        return { weekday: _t("Weekday"), weekend: _t("Weekend"),
                 holiday: _t("Public Holiday"), night: _t("Night") }[t] || t; }

    // ---------------------------------------------------------- config gallery
    get configs() { return (this.state.data && this.state.data.configs) || { cards: [], caps: {} }; }
    openConfig(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.overtime.config",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    dayLetters() { return ["M", "T", "W", "T", "F", "S", "S"]; }

    // -------------------------------------------------------------- bonus tab
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
        if (cmd.name === "bonus") {
            // `openBonus` is a silent no-op without `can_view_bonus`, which is
            // fine for a button that is not rendered — but the palette entry IS
            // rendered (the rail gate is the lens, not this tier), so it has to
            // say why nothing happened rather than look broken (W5).
            if (this.state.data && this.state.data.can_view_bonus) {
                this.openBonus();
            } else {
                this.notif.add(
                    _t("Bonus hours review is restricted to payroll and attendance managers."),
                    { type: "warning" });
            }
        }
    }

    openBonus() {
        if (!(this.state.data && this.state.data.can_view_bonus)) { return; }
        this.state.view = "bonus";
        if (!this.state.bonus.loaded) { this.loadBonus(); }
    }
    backToBoard() { this.state.view = "board"; }

    _bonusFilters() {
        const b = this.state.bonus;
        return {
            preset: b.preset,
            date_from: b.date_from || false,
            date_to: b.date_to || false,
            employee: b.employee || false,
            department: b.department || false,
            overtime_type: b.overtime_type || false,
            min_hours: b.min_hours || false,
        };
    }
    async loadBonus() {
        const b = this.state.bonus;
        this.state.busy = true;
        try {
            b.data = await this.orm.call(
                MODEL, "get_bonus_hours", [this._bonusFilters(), b.page, b.group_by]);
            b.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    setGroupBy(g) { this.state.bonus.group_by = g; this.state.bonus.page = 0; this.loadBonus(); }
    setPreset(p) { this.state.bonus.preset = p; this.state.bonus.page = 0; this.loadBonus(); }
    onBonusField(f, ev) { this.state.bonus[f] = ev.target.value; }
    applyBonusFilters() { this.state.bonus.page = 0; this.loadBonus(); }
    nextBonusPage() { this.state.bonus.page += 1; this.loadBonus(); }
    prevBonusPage() { if (this.state.bonus.page > 0) { this.state.bonus.page -= 1; this.loadBonus(); } }

    async exportBonus() {
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "export_bonus_csv", [this._bonusFilters()]);
            const a = document.createElement("a");
            a.href = "data:text/csv;base64," + r.csv_b64;
            a.download = r.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            this.notif.add(
                r.truncated
                    ? _t("Exported %s rows (capped at %s — narrow the filters).", r.count, r.cap)
                    : _t("Exported %s rows.", r.count),
                { type: r.truncated ? "warning" : "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    groupByOptions() {
        return [
            { key: "employee", label: _t("Employee") },
            { key: "department", label: _t("Department") },
            { key: "day", label: _t("Day") },
            { key: "week", label: _t("Week") },
            { key: "month", label: _t("Month") },
        ];
    }

    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_ot_desk", PbOtDesk);
