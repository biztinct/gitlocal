/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ConnectionLostError } from "@web/core/network/rpc";
import { ic as kitIc } from "@pb_import_kit/js/import_icons";
import { TIC, tic } from "@pb_tenants/js/pbtn_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";

const COUNTRIES = [
    ["", _t("— pick later —")], ["VN", _t("Vietnam")], ["ID", _t("Indonesia")], ["IN", _t("India")],
    ["SG", _t("Singapore")], ["TH", _t("Thailand")], ["KH", _t("Cambodia")], ["MY", _t("Malaysia")],
];
const STATE_BADGE = {
    live: ["ok", _t("Live")], provisioning: ["info", _t("Provisioning")], draft: ["muted", _t("Draft")],
    error: ["err", _t("Error")], decommissioned: ["muted", _t("Decommissioned")],
};

export class PbTenants extends Component {
    static template = "pb_tenants.PbTenants";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        // The return door a caller passed (Settings, a hub, another cockpit).
        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since Cycle 1. Null when nobody sent us, and the chip is then
        // ABSENT rather than inert (W5/W29).
        this.back = hubBack(this.props);
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
        this.notif.add(_t("Platform status refreshed."), { type: "info" });
    }

    async refreshFleetHealth() {
        this.state.det.busy = "platform";
        try {
            const d = await this.orm.silent.call("pb.tenants", "refresh_health", []);
            this.state.data = d;
        } finally { this.state.det.busy = ""; }
    }

    openUrl(url) { window.open(url, "_blank"); }

    async copy(text, label = _t("Copied")) {
        try {
            await navigator.clipboard.writeText(text);
            this.notif.add(label + " — " + text, { type: "success" });
        } catch {
            this.notif.add(_t("Copy failed — select and copy manually."), { type: "warning" });
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
        w.slug = { st: "checking", msg: _t("Checking availability…"), url: "" };
        this._slugTimer = setTimeout(async () => {
            const slug = w.form.slug;
            try {
                const r = await this.orm.silent.call("pb.tenants", "check_slug", [slug]);
                if (this.state.wiz.form.slug !== slug) { return; }
                w.slug = r.ok
                    ? { st: "ok", msg: _t("Available"), url: r.url }
                    : { st: "bad", msg: r.reason || _t("Not available"), url: "" };
            } catch (e) {
                if (this.state.wiz.form.slug !== slug) { return; }
                w.slug = { st: "bad", msg: this.errText(e, _t("Could not check — retry.")), url: "" };
            }
        }, 350);
    }

    /**
     * Readable one-liner for a failed RPC.
     *
     * This used to be a bare `catch {}` painting "Could not check — retry." over
     * everything, which made a dropped connection and a real server refusal look
     * identical — and cost an afternoon of diagnosis once. Always keep the cause
     * visible: on screen if we can name it, in the console regardless.
     */
    errText(e, fallback) {
        console.error("pb_tenants RPC failed:", e);
        if (!e) { return fallback; }
        if (e instanceof ConnectionLostError || e.name === "ConnectionLostError") {
            return _t("Lost connection to the server — check your network and retry.");
        }
        const raw = e.data?.message || e.message || e.data?.arguments?.[0] || "";
        const msg = String(raw).trim().split("\n")[0];
        return msg ? (msg.length > 160 ? msg.slice(0, 157) + "…" : msg) : fallback;
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
                w.console.push({ line: _t("Provisioning %(host)s …", { host: w.form.slug + "." + this.state.data.base_domain }), level: "info" });
            }
            for (const st of w.steps) {
                if (st.state === "done") { continue; }
                st.state = "run";
                const r = await this.orm.silent.call("pb.tenants", "provision_run", [w.tenantId, st.key]);
                (r.log || []).forEach((l) => w.console.push(l));
                st.ms = r.ms || 0;
                if (!r.ok) {
                    st.state = "fail";
                    w.error = r.error || _t("Step failed.");
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
            this.notif.add((e && e.data && e.data.message) || _t("Action failed."), { type: "danger" });
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
            title: _t("Restore to staging"),
            body: _t("This restores a copy of the backup into '%(database)s'. The live tenant is untouched. Any existing staging copy is replaced. Continue?", { database: det.d.staging_db }),
            confirmLabel: _t("Restore copy"),
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
            title: _t("Remove staging copy"),
            body: _t("Drop the staging database '%(database)s'? The live tenant is untouched.", { database: det.d.staging_db }),
            confirmLabel: _t("Drop staging"),
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
            title: _t("Remove domain"),
            body: _t("Detach %(hostname)s from this tenant? Its certificate and routing are removed.", { hostname }),
            confirmLabel: _t("Remove"),
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
            this.notif.add(_t("Tenant decommissioned. Final backup: %(backup)s", { backup: r.final_backup || _t("n/a") }), { type: "success" });
            this.backToFleet();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("Offboarding failed."), { type: "danger" });
        } finally {
            det.busy = "";
        }
    }

    healthDot(t) {
        return { ok: "hd-ok", warn: "hd-warn", down: "hd-down" }[t.health] || "hd-unknown";
    }
}

registry.category("actions").add("pb_tenants", PbTenants);
