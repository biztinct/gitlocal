/** @odoo-module **/
/**
 * Expenses › CLAIMS — the expense claims, on the shared filter panel.
 *
 * NAV P2 mounted the model's own native list here. FILTER wave 7
 * (2026-10-31) replaces it with a small Payobook list on the shared filter
 * panel (pb_filter_kit): views (Waiting approval first, the old default
 * filter), a count beside every value, search, sorts and pages of 60, all
 * counted on the server (`pb.expense.claims`). A row still opens the native
 * claim form in the main breadcrumb, which brings the reader back here with
 * the filters as they were (the panel remembers them for the browser tab).
 * Decisions are still taken from Approvals; nothing here approves anything.
 */
import { Component, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.expense.claim";
const FACADE = "pb.expense.claims";
const PAGE = 60;

export class PbClaimsLens extends Component {
    static template = "pb_expenses_hub.PbClaimsLens";
    static components = { PbFilterLayout };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            rows: [],
            total: 0,
            loaded: false,
            loadingMore: false,
        });
        this.kit = useFilterKit({
            model: FACADE,
            noun: _t("claims"),
            onChange: () => this.loadPage(),
        });
    }

    /** One page of claims for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.failed) {
            this.state.loaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(FACADE, "get_claim_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.total = d.total;
            this.state.loaded = true;
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The expense claims could not be listed. Try again in a moment."), { type: "danger" });
                this.state.loaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() { return this.state.rows.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.rows.length); }

    /** "" (rows) · "none" (no claim at all) · "calm" (nothing waiting) ·
     *  "search" · "filters". */
    get emptyKind() {
        if (!this.state.loaded || this.state.rows.length) { return ""; }
        if (!this.kit.total && !this.kit.search) { return "none"; }
        if (this.kit.search && !this.kit.activeCount) { return "search"; }
        if (this.kit.isExactly({ status: ["submitted"] })) { return "calm"; }
        return "filters";
    }
    startAgain() { this.kit.home(); }
    showEverything() { this.kit.clearAll(); }

    /** A CLICK handler: the native form, in the main breadcrumb. */
    openClaim(resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Expense claims"),
            res_model: MODEL,
            res_id: resId || false,
            views: [[false, "form"]],
            target: "current",
        });
    }
    onRowKey(ev, row) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.openClaim(row.id);
        } else if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const next = ev.key === "ArrowDown"
                ? ev.currentTarget.nextElementSibling : ev.currentTarget.previousElementSibling;
            if (next && next.focus) { next.focus(); }
        }
    }

    /** A key that changes with the filters, so the rows slide in once. */
    get listKey() {
        return JSON.stringify(this.kit.filters) + ":" + this.kit.search + ":" + this.kit.sort;
    }
}
