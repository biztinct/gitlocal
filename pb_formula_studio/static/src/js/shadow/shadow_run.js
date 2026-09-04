/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const CHUNK = 50;

// Shadow Parallel Run cockpit (F6). Two surfaces: an overview (run list + launch
// a run from a config's historical payslips) and a per-run detail (confidence,
// period breakdown, cluster triage). The recompute is driven client-side in
// chunks over silent RPC so the progress bar is honest and no request stalls.
export class PbShadowRun extends Component {
    static template = "pb_formula_studio.PbShadowRun";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            view: "overview",       // overview | detail
            runs: [],
            configs: [],
            launch: { config_id: null, limit: 500 },
            busy: false,
            progress: null,         // {done, total, phase}
            detail: null,           // get_shadow_detail payload
            tolDraft: "",
        });
        onWillStart(async () => {
            await this.loadOverview();
            const p = this.props.action && this.props.action.params;
            if (p && p.run_id) await this.openRun(p.run_id);
            this.state.loading = false;
        });
    }

    async loadOverview() {
        const d = await this.orm.call("hr.formula.shadow.run", "get_shadow_overview", []);
        this.state.runs = d.runs;
        this.state.configs = d.configs;
        if (!this.state.launch.config_id && d.configs.length) {
            this.state.launch.config_id = d.configs[0].id;
        }
    }

    // ---- launch + drive a full run ----
    async launchRun() {
        const cfg = this.state.launch.config_id;
        if (!cfg) { this.notif.add(_t("Pick a configuration first"), { type: "warning" }); return; }
        this.state.busy = true;
        this.state.progress = { done: 0, total: 0, phase: "Seeding from payslips…" };
        try {
            const seed = await this.orm.call("hr.formula.shadow.run", "create_from_payslips",
                [cfg, this.state.launch.limit || null]);
            if (!seed.ok) { this.notif.add(seed.msg || _t("Nothing to shadow"), { type: "danger" }); return; }
            await this.computeRun(seed.run_id);
            await this.loadOverview();
            await this.openRun(seed.run_id);
        } catch (e) {
            this.notif.add(_t("Shadow run failed to start"), { type: "danger" });
        } finally {
            this.state.busy = false;
            this.state.progress = null;
        }
    }

    async computeRun(runId) {
        const prep = await this.orm.call("hr.formula.shadow.run", "prepare_shadow", [runId]);
        const ids = prep.line_ids || [];
        this.state.progress = { done: 0, total: ids.length, phase: "Recomputing & comparing…" };
        for (let i = 0; i < ids.length; i += CHUNK) {
            const chunk = ids.slice(i, i + CHUNK);
            await this.orm.call("hr.formula.shadow.run", "compute_shadow_batch",
                [{ line_ids: chunk }], {}, { silent: true });
            this.state.progress = { done: Math.min(i + CHUNK, ids.length), total: ids.length, phase: "Recomputing & comparing…" };
        }
        this.state.progress = { done: ids.length, total: ids.length, phase: "Clustering…" };
        await this.orm.call("hr.formula.shadow.run", "finalize_shadow", [runId]);
    }

    async recompute(runId) {
        this.state.busy = true;
        try { await this.computeRun(runId); await this.openRun(runId); }
        finally { this.state.busy = false; this.state.progress = null; }
    }

    // ---- detail ----
    async openRun(runId) {
        const d = await this.orm.call("hr.formula.shadow.run", "get_shadow_detail", [runId]);
        this.state.detail = d;
        this.state.tolDraft = JSON.stringify(d.tolerance || {}, null, 0);
        this.state.view = "detail";
    }
    backToList() { this.state.view = "overview"; this.state.detail = null; }

    confidencePct(v) { return Math.round((v || 0) * 1000) / 10; }
    ringDash(v) { const c = 2 * Math.PI * 52; return { dash: c, offset: c * (1 - (v || 0)) }; }
    confClass(v) { return v >= 0.999 ? "perfect" : v >= 0.98 ? "good" : v >= 0.9 ? "warn" : "bad"; }

    // ---- cluster triage ----
    async setResolution(cluster, resolution) {
        await this.orm.call("hr.formula.shadow.run", "cluster_set_resolution",
            [cluster.id, resolution]);
        cluster.resolution = resolution;
    }
    async openInStudio(cluster) {
        // jump to Formula Studio focused on the offending config/component
        await this.action.doAction({
            type: "ir.actions.client", tag: "pb_formula_studio",
            params: { config_id: this.state.detail.config_id, focus_code: cluster.code },
        });
    }
    async nameWithAI() {
        if (!this.state.detail) return;
        this.state.busy = true;
        try {
            const r = await this.orm.call("hr.formula.shadow.run", "name_clusters_ai",
                [this.state.detail.id]);
            this.notif.add(r.named
                ? _t("PayAI named %(count)s clusters", { count: r.named })
                : _t("No AI naming available"),
                { type: r.named ? "success" : "info" });
            await this.openRun(this.state.detail.id);
        } finally { this.state.busy = false; }
    }
    async applyTolerance() {
        let tol;
        try { tol = JSON.parse(this.state.tolDraft || "{}"); }
        catch (e) { this.notif.add(_t("Tolerance must be valid JSON"), { type: "danger" }); return; }
        this.state.busy = true;
        try {
            await this.orm.call("hr.formula.shadow.run", "write",
                [[this.state.detail.id], { tolerance_json: JSON.stringify(tol) }]);
            await this.orm.call("hr.formula.shadow.run", "action_recompare", [[this.state.detail.id]]);
        this.notif.add(_t("Re-compared with new tolerance"), { type: "success" });
            await this.openRun(this.state.detail.id);
        } finally { this.state.busy = false; }
    }
    async certify() {
        const id = this.state.detail.id;
        await this.orm.call("hr.formula.shadow.run", "write", [[id], { state: "certified" }]);
        await this.action.doAction({
            type: "ir.actions.report", report_name: "pb_hr_payroll_formula.shadow_certificate",
            report_type: "qweb-pdf", context: { active_ids: [id], active_model: "hr.formula.shadow.run" },
        });
        await this.openRun(id);
    }
    async dropRun(runId) {
        await this.orm.call("hr.formula.shadow.run", "action_drop", [[runId]]);
        await this.loadOverview();
        this.backToList();
    }
    onLaunchConfig(ev) { this.state.launch.config_id = parseInt(ev.target.value, 10); }
    onLaunchLimit(ev) { this.state.launch.limit = parseInt(ev.target.value, 10) || null; }
}

registry.category("actions").add("pb_shadow_run", PbShadowRun);
