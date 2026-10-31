/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const STATE_CLS = {
    draft: "draft", loaded: "info", matched: "info", validated: "info",
    processing: "info", done: "done", error: "error", cancelled: "muted",
};
// launch-tile icon names (from the model) → Lucide keys in the kit
const TILE_ICON = {
    upload: "upload", table: "table", users: "users", plug: "plug", function: "sigma",
};

/**
 * Where "Manage connectors" comes back to.
 *
 * Standalone, Import is its own action, so the chip says "Import". Embedded as
 * the Pay Run hub's Import lens, the surface the user is actually looking at is
 * the HUB — so the host hands its own descriptor down through `connectorBack`.
 * The alternative, `pb_import` naming `pb_pay_hub`, would be a Setup-area module
 * knowing the name of a pay-run hub that was built two cycles after it.
 */
const DEFAULT_BACK = { label: _t("Import"), tag: "pb_import" };
const IN_PROGRESS = ["loaded", "matched", "validated", "processing"];
const PAGE = 60;
// The import pipeline, in order. A batch is at exactly one step — its own
// state — so the counts add up; error / cancelled batches are at none.
const STEPS = [
    { key: "draft", title: _t("Draft"), sub: _t("Created, no file read yet") },
    { key: "loaded", title: _t("Loaded"), sub: _t("File read, people not matched yet") },
    { key: "matched", title: _t("Matched"), sub: _t("People matched, not checked yet") },
    { key: "validated", title: _t("Validated"), sub: _t("Checked and ready to commit") },
    { key: "processing", title: _t("Processing"), sub: _t("Being written in") },
    { key: "done", title: _t("Done"), sub: _t("Committed") },
];

export class PbImport extends Component {
    static template = "pb_import.PbImport";
    static props = ["*"];
    static components = { PbFilterLayout };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            company: "",
            connectors: 0,
            hasConnectors: false,
            launches: [],
            // the batch list: one page at a time for the filter panel's state
            rows: [],
            rowsTotal: 0,
            listLoaded: false,
            loadingMore: false,
        });
        // FILTER W6 — the shared filter panel owns the filters, the counts and
        // the views; the list is paged from the server (the old cap was 20).
        // `state` and `errors` are counted on every refresh, folded or not:
        // the steps and the numbers line read them, so they follow the
        // filters (ruling R1).
        this.kit = useFilterKit({
            model: "pb.import",
            noun: _t("batches"),
            always: ["state", "errors"],
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.import", "get_import_data", []);
        Object.assign(this.state, {
            company: d.company,
            connectors: d.connectors || 0,
            hasConnectors: !!d.has_connectors,
            launches: d.launches, loaded: true,
        });
    }

    /** One page of batches for the panel's current filters; a reply for an
     *  older filter state is dropped. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.import", "get_batch_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.rowsTotal = d.total;
            this.state.listLoaded = true;
        } catch (e) {
            console.warn("pb_import: could not load the batches", e);
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The batches could not be loaded. Try again in a moment."), { type: "warning" });
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

    stateCls(s) { return STATE_CLS[s] || "muted"; }
    tileIcon(n) { return ic(TILE_ICON[n] || "upload", 18); }
    pipeIcon() { return ic("arrow", 14); }
    ic(n, s = 18) { return ic(n, s); }

    // ---- counts from the panel (they follow every other filter, R1) ----
    _count(key, value) {
        const c = this.kit.counts[key] || {};
        const row = (c.values || []).find((r) => String(r.v) === value);
        return row ? row.n || 0 : 0;
    }

    // ---- the numbers (quiet line): each figure is a filter ----
    get glanceFilters() {
        return {
            done: { state: ["done"] },
            in_progress: { state: [...IN_PROGRESS] },
            errors: { errors: ["attention"] },
        };
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }
    get glance() {
        const f = this.glanceFilters;
        const inProgress = IN_PROGRESS.reduce((n, s) => n + this._count("state", s), 0);
        const errors = this._count("errors", "attention");
        return [
            { key: "all", n: this.kit.total || 0, label: _t("Import batches"), tone: "", run: () => this.showAll() },
            { key: "done", n: this._count("state", "done"), label: _t("Completed"), tone: "",
              run: () => this.kit.toggleFilters(f.done) },
            { key: "in_progress", n: inProgress, label: _t("In progress"), tone: "",
              run: () => this.kit.toggleFilters(f.in_progress) },
            // "With errors" = stopped with an error OR holding rows that could
            // not be read — the Needs attention view, and what the Learn
            // glossary always said it was (it used to count the first only)
            { key: "errors", n: errors, label: _t("With errors"), tone: errors ? "rose" : "",
              run: () => this.kit.toggleFilters(f.errors) },
        ];
    }

    // ---- the steps: pressing one narrows the list to that state ----
    get steps() {
        return STEPS.map((st, i) => {
            const count = this._count("state", st.key);
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: count === 1 ? _t("1 batch") : _t("%s batches", count),
                flag: "", on: this.stepIsOn(st.key),
            };
        });
    }
    stepIsOn(key) {
        const v = this.kit.values("state");
        return v.length === 1 && String(v[0]) === key;
    }
    /** A step narrows the list to that step, keeping every other filter;
     *  pressing the lit step again lifts it. */
    pickStep(key) {
        if (this.stepIsOn(key)) { this.kit.clear("state"); } else { this.kit.only("state", key); }
    }
    /** Back to every batch (the first view). */
    showAll() { this.kit.home(); }

    /** Why the list is empty — one translatable sentence each (R34). */
    get emptyTitle() {
        if (!this.kit.total) { return _t("No import batches yet"); }
        if (this.kit.search && !this.kit.chips.length) { return _t("No batch matches “%s”", this.kit.search); }
        return _t("No batch matches these filters");
    }
    get emptyText() {
        if (!this.kit.total) {
            return _t("Load this period's pay data above. Every file or connected-system load you start appears here.");
        }
        if (this.kit.search && !this.kit.chips.length) {
            return _t("Check the spelling, or search by batch name, file name, pay scheme or connected system.");
        }
        return this.kit.total === 1
            ? _t("There is 1 batch, but it does not fit every filter you have set. Remove a filter above, or show every batch.")
            : _t("There are %s batches, but none fits every filter you have set. Remove a filter above, or show every batch.",
                 this.fmtInt(this.kit.total));
    }

    // ---- launches: primary tile becomes the hero CTA; rest stay as tiles ----
    get secondaryLaunches() { return this.state.launches.filter(l => !l.primary); }

    // ---- actions ----
    startWizard() { this.action.doAction("pb_import_wizard.action_pb_import_wizard", { clearBreadcrumbs: true }); }
    openBatch(id) {
        if (!id) return;
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_import_batch_cockpit",
            name: "Import Batch", params: { batch_id: id },
        });
    }
    launch(xmlid) {
        if (!xmlid) return;
        this.action.doAction(xmlid, { clearBreadcrumbs: true });
    }

    // ---------------------- the one door to connectors ----------------------
    /**
     * Is the connectors home reachable from here at all?
     *
     * A row that opens nothing is worse than no row (W29), and `pb_integrations`
     * is not a dependency of this module — it depends on `pb_import_advanced`,
     * which this one also depends on, so naming it in the manifest would invert
     * the graph. The actions registry is the honest probe: a module that is not
     * installed did not ship its JS.
     */
    get canManageConnectors() {
        return this.state.hasConnectors
            && registry.category("actions").contains("pb_integrations");
    }

    /** A CLICK handler. The chip on the other side comes back here. */
    manageConnectors() {
        openHub(this.action, {
            tag: "pb_integrations",
            back: this.props.connectorBack || DEFAULT_BACK,
        });
    }
}

registry.category("actions").add("pb_import", PbImport);
