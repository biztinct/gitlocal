/** @odoo-module **/
/**
 * Pay & Deliver — a bespoke full-screen two-lane experience launched from the
 * Pay Runs cockpit (or the sidebar, which shows a run picker first).
 *   · Money out   — data-driven bank file: pick a bank chip, see live eligible /
 *                   excluded counters, generate, download a satisfying file tile.
 *   · Payslips out — password-PDF batch delivery with per-slip status pills and
 *                    one-click resend of failures.
 * RPC facade: pb.pay.delivery. pbim-tokenized (.pbpd.pbim). Lucide icons only.
 */
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.pay.delivery";

export class PbPayDelivery extends Component {
    static template = "pb_pay_delivery.PbPayDelivery";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        const runId = this.props.action?.params?.run_id;
        this.state = useState({
            loaded: false,
            busy: false,
            runId: runId || null,
            picking: !runId,     // no run → show the picker
            runs: [],
            data: null,
            bank: null,
            companyAccount: "",
            generated: null,     // {file_b64, filename, valid, excluded, ...}
            showExcl: false,
            delivery: null,      // send result payload
            netShown: 0,         // count-up display
        });
        onWillStart(async () => {
            if (this.state.runId) { await this.load(); }
            else { await this.loadRuns(); }
        });
        onMounted(() => this._startCountUp());
        onWillUnmount(() => this._stopCountUp());
    }

    // --------------------------------------------------------------- loaders
    async loadRuns() {
        try {
            this.state.runs = await this.orm.call(MODEL, "get_recent_runs", []);
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    async pickRun(id) {
        this.state.runId = id;
        this.state.picking = false;
        this.state.loaded = false;
        await this.load();
        this._startCountUp();
    }

    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_delivery_data", [this.state.runId]);
            this.state.data = d;
            this.state.delivery = d.delivery;
            if (!this.state.bank && d.banks.length) {
                // default to Vietcombank if present, else the first layout
                const vcb = d.banks.find(b => b.key === "vietcombank");
                this.state.bank = (vcb || d.banks[0]).key;
            }
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    // --------------------------------------------------------------- count-up
    _startCountUp() {
        this._stopCountUp();
        const target = (this.state.data && this.state.data.run.total_net) || 0;
        if (!target) { this.state.netShown = 0; return; }
        const t0 = 900, start = performance.now();
        const step = (now) => {
            const p = Math.min(1, (now - start) / t0);
            const eased = 1 - Math.pow(1 - p, 3);
            this.state.netShown = Math.round(target * eased);
            if (p < 1) { this._raf = requestAnimationFrame(step); }
        };
        this._raf = requestAnimationFrame(step);
    }
    _stopCountUp() { if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; } }

    // --------------------------------------------------------------- money out
    selectBank(key) { this.state.bank = key; this.state.generated = null; }
    onCompanyAccount(ev) { this.state.companyAccount = ev.target.value; }
    toggleExcl() { this.state.showExcl = !this.state.showExcl; }

    async generate() {
        if (!this.state.bank || this.state.busy) { return; }
        this.state.busy = true;
        try {
            this.state.generated = await this.orm.call(
                MODEL, "generate_bank_file",
                [this.state.runId, this.state.bank, this.state.companyAccount || false]);
            this.notif.add(_t("Bank file generated."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    downloadFile() {
        const g = this.state.generated;
        if (!g) { return; }
        const a = document.createElement("a");
        a.href = "data:application/octet-stream;base64," + g.file_b64;
        a.download = g.filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }

    // --------------------------------------------------------------- payslips out
    async send(forceAll) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            this.state.delivery = await this.orm.call(
                MODEL, "send_payslips", [this.state.runId, !!forceAll]);
            const d = this.state.delivery;
            this.notif.add(
                _t("Delivery complete — %s sent, %s failed, %s skipped.",
                   d.sent, d.failed, d.skipped),
                { type: d.failed ? "warning" : "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    back() {
        this.state.picking = true;
        this.state.data = null;
        this.state.runId = null;
        this.state.generated = null;
        this.state.bank = null;
        this.loadRuns();
    }

    // --------------------------------------------------------------- helpers
    get bankName() {
        const b = this.state.data && this.state.data.banks.find(x => x.key === this.state.bank);
        return b ? b.name : "";
    }
    money(n) {
        if (n === null || n === undefined) { return "—"; }
        const cur = (this.state.data && this.state.data.currency) || "₫";
        return cur + " " + Math.round(n).toLocaleString("en-US");
    }
    fileSize(bytes) {
        if (!bytes) { return "0 B"; }
        if (bytes >= 1024 * 1024) { return (bytes / 1048576).toFixed(1) + " MB"; }
        if (bytes >= 1024) { return (bytes / 1024).toFixed(1) + " KB"; }
        return bytes + " B";
    }
    pillClass(state) {
        return { sent: "ok", failed: "bad", skipped_no_email: "warn" }[state] || "";
    }
    pillLabel(state) {
        return { sent: _t("Sent"), failed: _t("Failed"),
                 skipped_no_email: _t("No email") }[state] || state;
    }
    reasonList(reasons) { return (reasons || []).join(" · "); }
    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed.");
    }
}

registry.category("actions").add("pb_pay_delivery", PbPayDelivery);
