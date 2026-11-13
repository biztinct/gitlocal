/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const STATE_CLS = { active: "ok", draft: "info", deprecated: "warn", archived: "muted" };
const PAGE = 60;
// The figures on the numbers line that filter: pressing one ticks exactly
// these filters in the panel (and lights the matching view tab).
const GLANCE_FILTERS = {
    active: { status: ["active"] },
    draft: { status: ["draft"] },
    deprecated: { status: ["deprecated"] },
};

export class PbStructures extends Component {
    static template = "pb_structures.PbStructures";
    static components = { HubBackChip, PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        // The return door a caller passed (Settings, a hub, another cockpit).
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since Cycle 1. Null when nobody sent us, and the chip is then
        // ABSENT rather than inert (W5/W29).
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false, kpis: {},
            rows: [], total: 0, listLoaded: false, loadingMore: false,
        });
        // FILTER wave 5: the shared filter panel owns the filters, the counts
        // and the views; this screen only loads a page for kit.query.
        this.kit = useFilterKit({
            model: "pb.structures",
            noun: _t("structures"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    /** The numbers line, counted over the whole catalogue. */
    async load() {
        const d = await this.orm.call("pb.structures", "get_board_head", []);
        Object.assign(this.state, { kpis: d.kpis || {}, loaded: true });
    }

    /** One page of the catalogue for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.structures", "get_structure_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.total = d.total;
            this.state.listLoaded = true;
        } catch (e) {
            console.error("pb_structures: the list could not load", e);
            this.notification.add(_t("The structures could not be loaded. Try again in a moment."), { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    get hasMore() { return this.state.rows.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.rows.length); }

    ic(n, s = 16) { return ic(n, s); }
    stateCls(s) { return STATE_CLS[s] || "muted"; }

    /** The counts as one quiet line, over the whole catalogue. The three
     *  states tick the filter panel; press the lit one again to show all. */
    get glance() {
        const k = this.state.kpis || {};
        const pick = (key) => () => this.kit.toggleFilters(GLANCE_FILTERS[key]);
        return [
            { key: "all", n: k.structures || 0, label: _t("Structures"), tone: "", run: () => this.kit.toggleFilters({}) },
            { key: "active", n: k.active || 0, label: _t("Active"), tone: "", run: pick("active") },
            { key: "draft", n: k.draft || 0, label: _t("Draft"), tone: "", run: pick("draft") },
            { key: "deprecated", n: k.deprecated || 0, label: _t("Deprecated"), tone: k.deprecated ? "amber" : "", run: pick("deprecated") },
            { key: "rules", n: k.rules || 0, label: _t("Salary rules"), tone: "", run: null },
            { key: "categories", n: k.categories || 0, label: _t("Categories"), tone: "", run: null },
            { key: "employees", n: k.employees || 0, label: _t("Employees covered"), tone: "", run: null },
            { key: "countries", n: k.countries || 0, label: _t("Countries"), tone: "", run: null },
        ];
    }
    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }
    // a getter, not a template literal: a literal is never extracted (F29)
    get searchHint() { return _t("Search a name or a code…"); }
    get emptyHint() {
        return this.kit.search && !this.kit.chips.length
            ? _t("No structure is called “%s” and no code matches it. Check the spelling, or search by code.", this.kit.search)
            : _t("Remove a filter above, or start again from every structure.");
    }

    openStructure(id) {
        if (!id) return;
        this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_detail", name: _t("Structure"), params: { structure_id: id } });
    }
    newStructure() { this.action.doAction({ type: "ir.actions.client", tag: "pb_structure_wizard", name: _t("New structure") }); }
    openAll() { this.action.doAction("pb_hr_payroll_base.action_hr_payroll_structure_base", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_structures", PbStructures);
