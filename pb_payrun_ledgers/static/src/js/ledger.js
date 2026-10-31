/** @odoo-module **/
/**
 * The generic pay-run ledger cockpit — one component, two mount points (W17).
 *
 * STANDALONE (`pb_fullfinal` / `pb_proration` / `pb_retro` client actions) it is
 * exactly what it has always been: one descriptor, its own title, a row click
 * that opens the native form, and an "Open full list →" escape at the bottom.
 *
 * IN A HUB (`embedded`, with `tabs`) it becomes an IN-LENS ledger:
 *   - the title row is the hub's, so it is suppressed here;
 *   - `tabs` puts two descriptors in one lens (Adjust = Retro | Proration) and
 *     the tab is what chooses the RPC model;
 *   - a row click opens a 320px WfDrawer with the line's whole story instead of
 *     navigating — the point of a hub is that reading a row does not cost you
 *     the surface you were reading it from;
 *   - "Open full list →" is NOT RENDERED. It is the escape the hub exists to
 *     remove, and a link that leaves a hub for a native list is worse than no
 *     link, because it looks like a filter and behaves like an exit.
 *
 * Nothing above changes one pixel of the standalone render: every hub-only
 * branch is guarded on `props.embedded`, which is absent there.
 */
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { useFilterKit, sameFilters } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

// The unit a step's count pill names, per descriptor `steps.unit`. Whole
// sentences, one msgid each, so a translator can reorder them.
const STEP_UNIT = {
    settlement: (n) => (n === 1 ? _t("1 settlement") : _t("%s settlements", n)),
};
// What the filter panel calls the rows of each ledger ("12 of 86 settlements").
const NOUN = {
    "pb.fullfinal": () => _t("settlements"),
    "pb.proration": () => _t("proration lines"),
    "pb.retro": () => _t("retro lines"),
};
const PAGE = 60;

// One generic ledger cockpit rendered from a backend descriptor. Each screen is
// a thin subclass that only sets the RPC model; the descriptor supplies the
// numbers and the steps. FILTER W6: the rows are paged from the server for
// the shared filter panel's state (they used to be the newest 400, filtered
// here); each data model declares its own sections and views.
export class LedgerCockpit extends Component {
    static template = "pb_payrun_ledgers.Ledger";
    static components = { WfDrawer, PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            acting: 0,          // the row whose action is running
            loaded: false, data: {},
            // the list: one page at a time for the filter panel's state
            rows: [], rowsTotal: 0, listLoaded: false, loadingMore: false,
            // hub mode only
            tab: this.tabs.length ? this.tabs[0].key : "",
            drawer: null,          // { title, subtitle, sections, currency }
            drawerLoading: false,
        });
        // The kit is pointed at this tab's data model; a tab switch points it
        // at the other one (`reconfigure`). Each ledger keeps its own filters
        // and saved views (screen keys fullfinal / proration / retro).
        // `status`, `check` and `mine` are counted on every refresh: the
        // steps and their flags read them, so they follow the filters (R1).
        this.kit = useFilterKit({
            model: this.MODEL,
            noun: this.noun,
            always: ["status", "check", "mine"],
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
        // LEARN REFRESH step 1. A host that wants to know which inner tab is
        // showing (the Pay Run hub tells the helper "Adjust › Proration")
        // passes `onTab`. Told after the mount and on every switch; it is the
        // host's callback, so this cockpit still owns nothing but its tab.
        onMounted(() => this._tellTab());
    }

    _tellTab() {
        if (typeof this.props.onTab === "function" && this.state.tab) {
            this.props.onTab(this.state.tab);
        }
    }

    // ------------------------------------------------------------- hub shape
    /**
     * `embedded` alone suppresses chrome; `tabs` is what makes this an in-lens
     * ledger. They are separate because a future hub may embed ONE descriptor
     * with no tab strip, and a tab strip of one is a control that does nothing.
     */
    get embedded() { return !!this.props.embedded; }
    // Template string literals are never extracted for translation, so the
    // step strip's heading lives here as a real msgid (LEARN REFRESH step 6).
    get stepsLabel() { return _t("Where every settlement is"); }
    get searchPh() { return this.state.data.search_ph || _t("Search…"); }
    get noun() { return (NOUN[this.MODEL] || (() => _t("lines")))(); }
    get tabs() { return this.props.tabs || []; }
    get tabDef() {
        return this.tabs.find((t) => t.key === this.state.tab) || this.tabs[0] || null;
    }

    /**
     * The model this mount reads from.
     *
     * A subclass's static MODEL is the standalone answer; a tab's is the hub's.
     * The tab wins, so one component serves both without a second class.
     */
    get MODEL() {
        const t = this.tabDef;
        return (t && t.model) || this.constructor.MODEL;
    }

    /** The words, the numbers line and the steps — over the whole scope. */
    async load() {
        let d = {};
        try {
            d = await this.orm.call(this.MODEL, "get_head", []);
        } catch (e) {
            console.warn("pb_payrun_ledgers: get_head failed", e);
            this.notif.add(_t("This ledger could not be loaded. Try again in a moment."), { type: "danger" });
        }
        this.state.data = d || {};
        this.state.loaded = true;
    }

    /** One page of rows for the panel's current filters; a reply for an
     *  older filter state (or the other tab) is dropped. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const model = this.MODEL;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(model, "get_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq) || model !== this.MODEL) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.rowsTotal = d.total;
            this.state.listLoaded = true;
        } catch (e) {
            console.warn("pb_payrun_ledgers: get_page failed", e);
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The rows could not be loaded. Try again in a moment."), { type: "warning" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    get hasMore() { return this.state.rows.length < this.state.rowsTotal; }
    get nextPage() { return Math.min(PAGE, this.state.rowsTotal - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    /** A CLICK handler — the tab switch reloads, and mounts never write (W21).
     *  The panel is pointed at the other ledger: its own sections, views and
     *  remembered filters come back. */
    async setTab(key) {
        if (this.state.tab === key) { return; }
        this.state.tab = key;
        this._tellTab();
        this.state.drawer = null;
        this.state.loaded = false;
        this.state.listLoaded = false;
        this.state.rows = [];
        await Promise.all([this.load(), this.kit.reconfigure({ model: this.MODEL, noun: this.noun })]);
    }

    ic(n, s = 16) { return ic(n, s); }

    // ---- formatting ----
    // SCHEMECTX: the sign comes from the payload, which asks the scheme that
    // produced the rows. No literal fallback — a hardcoded "₫" is exactly how
    // an Indian settlement came to be written in dong. The sign always goes
    // in FRONT, whatever `res.currency` stores against it (SC3).
    get cur() { return this.state.data.currency || ""; }
    money(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.cur;
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }
    // The drawer is ONE row, so it knows its own scheme's money even when the
    // grid above it mixes two and falls back to the company's.
    moneyFull(n, cur) {
        return (cur ?? this.cur) + Math.round(n || 0).toLocaleString("en-US");
    }
    kpiVal(k) {
        if (k.money) return this.money(k.value);
        return (typeof k.value === "number") ? k.value.toLocaleString("en-US") : (k.value ?? "—");
    }
    metricVal(m) {
        if (m.money) return this.moneyFull(m.value);
        return (m.value === 0 || m.value) ? String(m.value) : "—";
    }
    /** Drawer values: money through the full formatter, everything else as-is. */
    detailVal(f) {
        if (f.money) {
            return this.moneyFull(f.value, (this.state.drawer || {}).currency);
        }
        return (f.value === 0 || f.value) ? String(f.value) : "—";
    }

    // ---- the panel's counts (they follow every other filter, R1) ----
    _count(key, value) {
        const c = this.kit.counts[key] || {};
        const row = (c.values || []).find((r) => String(r.v) === String(value));
        return row ? row.n || 0 : 0;
    }
    /** Back to the whole ledger (its first view). */
    showAll() { this.kit.home(); }

    /** Why the list is empty — one translatable sentence each (R34). */
    get emptyTitle() {
        if (!this.kit.total) { return _t("Nothing here yet"); }
        if (this.kit.search && !this.kit.chips.length) { return _t("Nothing matches “%s”", this.kit.search); }
        return _t("Nothing matches these filters");
    }
    get emptyText() {
        if (!this.kit.total) {
            return _t("Rows appear here once a pay data load or a settlement creates them.");
        }
        if (this.kit.search && !this.kit.chips.length) {
            return _t("Check the spelling, or search by a person's name or a component.");
        }
        return _t("There are %(n)s %(noun)s, but none fits every filter you have set. Remove a filter above, or show them all.",
                  { n: this.fmtInt(this.kit.total), noun: this.noun });
    }

    // ================================================ quiet board
    //
    // Counts go into one slim numbers line; the money totals the page exists
    // to show stay as figures of their own. A descriptor that carries
    // `steps` (Full & Final: a settlement's approval route) also gets the
    // numbered step strip; each record is at exactly one step.
    get quietKpis() { return (this.state.data.kpis || []).filter((k) => !k.money); }
    get moneyKpis() { return (this.state.data.kpis || []).filter((k) => k.money); }

    /** A figure with a `facet` [section, value] is a filter: pressing it
     *  ticks exactly that in the panel; pressing it again shows everything. */
    _kpiFilters(k) {
        return k.facet ? { [k.facet[0]]: [k.facet[1]] } : null;
    }
    get glance() {
        return this.quietKpis.map((k, i) => {
            const f = this._kpiFilters(k);
            const tone = !k.value ? "" : k.tone === "err" ? "rose" : k.tone === "warn" ? "amber" : "";
            return {
                // a real 0 (not the string "0") so the kit greys it
                key: "k" + i, n: k.value ? this.kpiVal(k) : 0, label: k.label, tone,
                run: f ? () => this.kit.toggleFilters(f) : null,
                _on: f && this.kit.loaded ? this.kit.isExactly(f) : false,
            };
        });
    }
    get glanceOn() {
        const on = this.glance.find((g) => g._on);
        return on ? on.key : "";
    }

    get stepItems() { return ((this.state.data.steps || {}).items) || []; }
    get stepUnit() { return (this.state.data.steps || {}).unit || ""; }
    /** The steps, counted by the panel for every OTHER filter that is on,
     *  so they follow the filters (R1). A step = its states in "Where it is". */
    get steps() {
        const unit = STEP_UNIT[this.stepUnit] || ((n) => String(n));
        return this.stepItems.map((st, i) => {
            const count = st.states.reduce((n, s) => n + this._count("status", s), 0);
            const mine = st.key === "pending" ? this._count("mine", "mine") : 0;
            const waiting = st.key === "pending" ? count : 0;
            const ready = st.key === "prepare" ? this._count("check", "yes") : 0;
            const returned = st.key === "prepare" ? this._count("status", "returned") : 0;
            let flag = "";
            if (mine) {
                flag = mine === 1 ? _t("1 waiting on you") : _t("%s waiting on you", mine);
            } else if (waiting) {
                flag = waiting === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", waiting);
            } else if (ready) {
                flag = ready === 1 ? _t("1 ready to check") : _t("%s ready to check", ready);
            } else if (returned) {
                flag = returned === 1 ? _t("1 sent back to be fixed") : _t("%s sent back to be fixed", returned);
            }
            return {
                key: st.key, n: String(i + 1).padStart(2, "0"), title: st.title,
                count, countLabel: unit(count), sub: "",
                flag, flagTone: "", on: this.stepIsOn(st),
            };
        });
    }
    stepIsOn(st) {
        return sameFilters({ status: this.kit.values("status") }, { status: st.states });
    }
    /** A step ticks its states in "Where it is", keeping every other filter;
     *  pressing the lit step again lifts it. */
    pickStep(key) {
        const st = this.stepItems.find((x) => x.key === key);
        if (!st) { return; }
        if (this.stepIsOn(st)) {
            this.kit.clear("status");
        } else {
            this.kit.setFilters({ ...this.kit.filters, status: [...st.states] }, { search: this.kit.search });
        }
    }

    // ---- navigation / actions ----
    /**
     * A row is a door either way — the hub's door just opens inwards.
     * Standalone: the native form (unchanged). Embedded: the drawer.
     */
    openRow(r) {
        if (this.embedded) { return this.openDrawer(r); }
        if (!r.res_model || !r.id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: r.res_model, res_id: r.id,
            views: [[false, "form"]], target: "current",
        });
    }

    async openDrawer(r) {
        if (!r.id) { return; }
        // Shown immediately from what the ROW already knows, then filled in:
        // an empty panel that appears instantly reads as loading, whereas a
        // click with nothing on screen for 200ms reads as a dead row.
        this.state.drawer = { title: r.title || "—", subtitle: r.subtitle || "", sections: [] };
        this.state.drawerLoading = true;
        try {
            const d = await this.orm.call(this.MODEL, "get_detail", [r.id]);
            if (!this.state.drawer) { return; }        // closed while in flight
            this.state.drawer = {
                title: d.title || r.title || "—",
                subtitle: d.subtitle || r.subtitle || "",
                sections: d.sections || [],
                // the row's OWN money, which the server has always sent and
                // this panel used to throw away (SCHEMECTX)
                currency: d.currency || this.cur,
            };
        } catch (e) {
            // Reported, never swallowed (W40): the drawer stays open with what
            // the row knew, and the user is told the rest did not arrive.
            console.warn("pb_payrun_ledgers: get_detail failed", e);
            this.notif.add(_t("Could not load this line's detail."), { type: "danger" });
        } finally {
            this.state.drawerLoading = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    async rowAction(r, ev) {
        ev.stopPropagation();
        if (!r.action || this.state.acting) return;
        this.state.acting = r.id;
        try {
            const act = await this.orm.call(r.res_model, r.action.method, [[r.id]]);
            if (act && typeof act === "object" && act.type) {
                await this.action.doAction(act);
            } else if (r.action.done) {
                // LEARN REFRESH step 6: a row action that CHANGES the record
                // (Send for approval) says so and re-reads the numbers, the
                // counts and the page (not the whole board — the filters and
                // the page stay), so the row moves to its new step in front
                // of the reader.
                this.notif.add(r.action.done, { type: "success" });
                await Promise.all([this.load(), this.kit.refresh()]);
            }
        } catch (e) {
            // the server's own words, never a bare "failed" (W40)
            const msg = (e && e.data && e.data.message) || (e && e.message);
            this.notif.add(msg || _t("Action failed"), { type: "danger" });
        } finally {
            this.state.acting = 0;
        }
    }

    /** Standalone only — the template never renders the link in hub mode. */
    openFullList() {
        if (this.state.data.list_action) this.action.doAction(this.state.data.list_action, { clearBreadcrumbs: true });
    }
}

class PbFullFinal extends LedgerCockpit { static MODEL = "pb.fullfinal"; }
class PbProration extends LedgerCockpit { static MODEL = "pb.proration"; }
class PbRetro extends LedgerCockpit { static MODEL = "pb.retro"; }

registry.category("actions").add("pb_fullfinal", PbFullFinal);
registry.category("actions").add("pb_proration", PbProration);
registry.category("actions").add("pb_retro", PbRetro);
