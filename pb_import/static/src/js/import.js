/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";

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

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            company: "",
            kpis: {},
            pipeline: [],
            batches: [],
            connectors: 0,
            hasConnectors: false,
            launches: [],
            filter: "all",
            step: "",
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.import", "get_import_data", []);
        Object.assign(this.state, {
            company: d.company, kpis: d.kpis, pipeline: d.pipeline,
            batches: d.batches, connectors: d.connectors || 0,
            hasConnectors: !!d.has_connectors,
            launches: d.launches, loaded: true,
        });
    }

    stateCls(s) { return STATE_CLS[s] || "muted"; }
    tileIcon(n) { return ic(TILE_ICON[n] || "upload", 18); }
    pipeIcon() { return ic("arrow", 14); }
    ic(n, s = 18) { return ic(n, s); }

    // ---- the numbers (quiet line) ----
    get glance() {
        const k = this.state.kpis || {};
        const pick = (f) => () => this.setFilter(this.state.filter === f ? "all" : f);
        return [
            { key: "all", n: k.total_batches || 0, label: _t("Import batches"), tone: "", run: () => this.showAll() },
            { key: "done", n: k.done || 0, label: _t("Completed"), tone: "", run: pick("done") },
            { key: "in_progress", n: k.in_progress || 0, label: _t("In progress"), tone: "", run: pick("in_progress") },
            { key: "errors", n: k.errors || 0, label: _t("With errors"), tone: k.errors ? "rose" : "", run: pick("errors") },
        ];
    }

    // ---- the steps: pressing one narrows Recent batches to that state ----
    get steps() {
        const counts = {};
        for (const p of this.state.pipeline || []) counts[p.key] = p.count || 0;
        return STEPS.map((st, i) => {
            const count = counts[st.key] || 0;
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: count === 1 ? _t("1 batch") : _t("%s batches", count),
                flag: "", on: this.state.step === st.key,
            };
        });
    }
    pickStep(key) {
        this.state.step = this.state.step === key ? "" : key;
        this.state.filter = "all";
    }
    get showingLine() {
        const listed = this.state.batches.length;
        const total = (this.state.kpis || {}).total_batches || listed;
        const st = STEPS.find((x) => x.key === this.state.step);
        if (!st && this.state.filter === "all") {
            let text;
            if (!listed) text = _t("no import batches yet");
            else if (total > listed) text = _t("the newest %s of %s batches", listed, total);
            else text = listed === 1 ? _t("all 1 batch") : _t("all %s batches", listed);
            return { all: true, text };
        }
        return { all: false, text: _t("%s of %s batches", this.filteredBatches.length, listed), where: st ? st.title : "" };
    }
    showAll() { this.state.step = ""; this.state.filter = "all"; }

    // ---- launches: primary tile becomes the hero CTA; rest stay as tiles ----
    get secondaryLaunches() { return this.state.launches.filter(l => !l.primary); }

    // ---- status filter chips ----
    _inFilter(b) {
        if (this.state.step && b.state !== this.state.step) return false;
        const f = this.state.filter;
        if (f === "all") return true;
        if (f === "in_progress") return IN_PROGRESS.includes(b.state);
        if (f === "errors") return b.state === "error" || (b.errors || 0) > 0;
        return b.state === f;     // draft, done
    }
    get filteredBatches() { return this.state.batches.filter(b => this._inFilter(b)); }
    countFor(key) {
        if (key === "all") return this.state.batches.length;
        return this.state.batches.filter(b => {
            if (key === "in_progress") return IN_PROGRESS.includes(b.state);
            if (key === "errors") return b.state === "error" || (b.errors || 0) > 0;
            return b.state === key;
        }).length;
    }
    setFilter(key) { this.state.filter = key; this.state.step = ""; }

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
