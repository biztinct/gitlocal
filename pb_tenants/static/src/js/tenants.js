/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ic as kitIc } from "@pb_import_kit/js/import_icons";
import { TIC, tic } from "@pb_tenants/js/pbtn_icons";

const COUNTRIES = [
    ["", "— pick later —"], ["VN", "Vietnam"], ["ID", "Indonesia"], ["IN", "India"],
    ["SG", "Singapore"], ["TH", "Thailand"], ["KH", "Cambodia"], ["MY", "Malaysia"],
];
const STATE_BADGE = {
    live: ["ok", "Live"], provisioning: ["info", "Provisioning"], draft: ["muted", "Draft"],
    error: ["err", "Error"], decommissioned: ["muted", "Decommissioned"],
};

export class PbTenants extends Component {
    static template = "pb_tenants.PbTenants";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        this.countries = COUNTRIES;
        this.stateBadge = STATE_BADGE;
        this._slugTimer = null;
        this.state = useState({
            loaded: false,
            view: "fleet",
            data: { platform: { checks: [], registrar_records: [] }, kpis: {}, tenants: [], steps: [] },
            checklistOpen: true,
            wiz: this._freshWiz(),
            det: { id: null, tab: "overview", d: null, busy: "", confirm: "", newDomain: "", restoreMsg: null },
        });
        onWillStart(async () => { await this.loadFleet(); });
    }

    ic(n, s = 16) { return TIC[n] ? tic(n, s) : kitIc(n, s); }

    _freshWiz() {
        return {
            step: 1, running: false, finished: false, error: null,
            form: { name: "", slug: "", admin_name: "", admin_email: "", country_code: "" },
            slugTouched: false,
            slug: { st: "idle", msg: "", url: "" },
            steps: [], console: [], tenantId: null, creds: null, doneUrl: null,
        };
    }

    // ------------------------------------------------------------- fleet
    async loadFleet(silent = true) {
        const call = silent ? this.orm.silent : this.orm;
        const d = await call.call("pb.tenants", "get_fleet_data", []);
        this.state.data = d;
        this.state.loaded = true;
    }

    async recheckPlatform() {
        this.state.det.busy = "platform";
        try { await this.loadFleet(); } finally { this.state.det.busy = ""; }
        this.notif.add("Platform status refreshed.", { type: "info" });
    }

    async refreshFleetHealth() {
        this.state.det.busy = "platform";
        try {
            const d = await this.orm.silent.call("pb.tenants", "refresh_health", []);
            this.state.data = d;
        } finally { this.state.det.busy = ""; }
    }

    openUrl(url) { window.open(url, "_blank"); }

    async copy(text, label = "Copied") {
        try {
            await navigator.clipboard.writeText(text);
            this.notif.add(label + " — " + text, { type: "success" });
        } catch {
            this.notif.add("Copy failed — select and copy manually.", { type: "warning" });
        }
    }

    // ------------------------------------------------------------- wizard
    openWizard() {
        this.state.wiz = this._freshWiz();
        this.state.view = "wizard";
    }

    closeWizard() {
        if (this.state.wiz.running) { return; }
        this.state.view = "fleet";
        this.loadFleet();
    }

    slugify(name) {
        return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").replace(/^[0-9-]+/, "").slice(0, 30);
    }

    onNameInput() {
        const w = this.state.wiz;
        if (!w.slugTouched) {
            w.form.slug = this.slugify(w.form.name);
            this.queueSlugCheck();
        }
    }

    onSlugInput() {
        const w = this.state.wiz;
        w.slugTouched = true;
        w.form.slug = this.slugify(w.form.slug) || w.form.slug.toLowerCase();
        this.queueSlugCheck();
    }

    queueSlugCheck() {
        const w = this.state.wiz;
        clearTimeout(this._slugTimer);
        if (!w.form.slug) { w.slug = { st: "idle", msg: "", url: "" }; return; }
        w.slug = { st: "checking", msg: "Checking availability…", url: "" };
        this._slugTimer = setTimeout(async () => {
            const slug = w.form.slug;
            try {
                const r = await this.orm.silent.call("pb.tenants", "check_slug", [slug]);
                if (this.state.wiz.form.slug !== slug) { return; }
                w.slug = r.ok
                    ? { st: "ok", msg: "Available", url: r.url }
                    : { st: "bad", msg: r.reason || "Not available", url: "" };
            } catch {
                w.slug = { st: "bad", msg: "Could not check — retry.", url: "" };
            }
        }, 350);
    }

    get wizValid() {
        const w = this.state.wiz;
        return !!(w.form.name.trim() && w.slug.st === "ok" && /\S+@\S+\.\S+/.test(w.form.admin_email));
    }

    toReview() { if (this.wizValid) { this.state.wiz.step = 2; } }
    backToIdentity() { this.state.wiz.step = 1; }

    async launchProvision() {
        const w = this.state.wiz;
        w.step = 3;
        w.steps = this.state.data.steps.map((s) => ({ ...s, state: "pending", ms: 0 }));
        await this.runProvision();
    }

    async runProvision() {
        const w = this.state.wiz;
        w.running = true; w.error = null;
        try {
            if (!w.tenantId) {
                const res = await this.orm.silent.call("pb.tenants", "provision_start", [{ ...w.form }]);
                w.tenantId = res.tenant_id;
                w.console.push({ line: "Provisioning " + w.form.slug + "." + this.state.data.base_domain + " …", level: "info" });
            }
            for (const st of w.steps) {
                if (st.state === "done") { continue; }
                st.state = "run";
                const r = await this.orm.silent.call("pb.tenants", "provision_run", [w.tenantId, st.key]);
                (r.log || []).forEach((l) => w.console.push(l));
                st.ms = r.ms || 0;
                if (!r.ok) {
                    st.state = "fail";
                    w.error = r.error || "Step failed.";
                    return;
                }
                st.state = "done";
                if (r.credentials) { w.creds = r.credentials; }
                if (r.url) { w.doneUrl = r.url; }
            }
            w.finished = true;
            this.loadFleet();
        } catch (e) {
            const cur = w.steps.find((s) => s.state === "run");
            if (cur) { cur.state = "fail"; }
            w.error = (e && e.data && e.data.message) || (e && e.message) || "Provisioning failed.";
            w.console.push({ line: w.error, level: "error" });
        } finally {
            w.running = false;
        }
    }

    retryProvision() {
        const w = this.state.wiz;
        w.steps.forEach((s) => { if (s.state === "fail") { s.state = "pending"; } });
        this.runProvision();
    }

    // ------------------------------------------------------------- detail
    async openDetail(id) {
        this.state.det = { id, tab: "overview", d: null, busy: "", confirm: "", newDomain: "", restoreMsg: null };
        this.state.view = "detail";
        this.state.det.d = await this.orm.silent.call("pb.tenants", "get_tenant", [id]);
    }

    backToFleet() {
        this.state.view = "fleet";
        this.loadFleet();
    }

    async _detCall(method, args, busy, okMsg) {
        const det = this.state.det;
        det.busy = busy;
        try {
            const d = await this.orm.silent.call("pb.tenants", method, args);
            if (d && d.id) { det.d = d; }
            if (okMsg) { this.notif.add(okMsg, { type: "success" }); }
            return d;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || "Action failed.", { type: "danger" });
        } finally {
            det.busy = "";
        }
    }

    async refreshTenantHealth() {
        await this._detCall("refresh_health", [this.state.det.id], "health", "Health refreshed.");
    }

    async backupNow() {
        await this._detCall("backup_now", [this.state.det.id, "manual"], "backup", "Backup completed.");
    }

    restoreStaging(backupId) {
        const det = this.state.det;
        this.dialog.add(ConfirmationDialog, {
            title: "Restore to staging",
            body: "This restores a copy of the backup into '" + det.d.staging_db +
                "'. The live tenant is untouched. Any existing staging copy is replaced. Continue?",
            confirmLabel: "Restore copy",
            confirm: () => {
                this._detCall("restore_staging", [det.id, backupId || null], "restore").then((r) => {
                    if (r && r.staging_url) {
                        det.restoreMsg = r;
                        this._detCall("get_tenant", [det.id], "restore");
                    }
                });
            },
            cancel: () => {},
        });
    }

    dropStaging() {
        const det = this.state.det;
        this.dialog.add(ConfirmationDialog, {
            title: "Remove staging copy",
            body: "Drop the staging database '" + det.d.staging_db + "'? The live tenant is untouched.",
            confirmLabel: "Drop staging",
            confirm: () => { det.restoreMsg = null; this._detCall("drop_staging", [det.id], "restore", "Staging removed."); },
            cancel: () => {},
        });
    }

    async addDomain() {
        const det = this.state.det;
        const host = (det.newDomain || "").trim();
        if (!host) { return; }
        const d = await this._detCall("domain_add", [det.id, host], "domain", "Domain added — configure DNS next.");
        if (d) { det.newDomain = ""; }
    }

    async checkDomain(id) { await this._detCall("domain_check", [id], "domain"); }
    async activateDomain(id) { await this._detCall("domain_activate", [id], "domain", "Domain is live with TLS."); }

    removeDomain(id, hostname) {
        this.dialog.add(ConfirmationDialog, {
            title: "Remove domain",
            body: "Detach " + hostname + " from this tenant? Its certificate and routing are removed.",
            confirmLabel: "Remove",
            confirm: () => { this._detCall("domain_remove", [id], "domain", "Domain removed."); },
            cancel: () => {},
        });
    }

    async offboard() {
        const det = this.state.det;
        if (det.confirm !== det.d.slug) { return; }
        det.busy = "offboard";
        try {
            const r = await this.orm.call("pb.tenants", "offboard", [det.id, det.confirm]);
            this.notif.add("Tenant decommissioned. Final backup: " + (r.final_backup || "n/a"), { type: "success" });
            this.backToFleet();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || "Offboarding failed.", { type: "danger" });
        } finally {
            det.busy = "";
        }
    }

    healthDot(t) {
        return { ok: "hd-ok", warn: "hd-warn", down: "hd-down" }[t.health] || "hd-unknown";
    }
}

registry.category("actions").add("pb_tenants", PbTenants);
