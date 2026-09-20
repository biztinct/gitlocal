/** @odoo-module **/
/**
 * Pay & Deliver — a bespoke full-screen experience launched from the Pay Runs
 * cockpit (or the sidebar, which shows a run picker first).
 *   · Bank file       — prepare it, follow it, download the approved one.
 *   · Payment release — ask for the money to be sent; see it land.
 *   · Payslips out    — password-PDF batch delivery with per-slip status pills.
 *
 * PHASE 5. Every lane used to be a button that did the thing. Each is now a
 * button that ASKS — and where the business published "no approval needed" the
 * button says so on its face, so nobody is ever surprised by what a press
 * costs. A lane that is waiting names the person it is waiting for and offers
 * the door to the request: waiting is never a dead end.
 *
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
        this.action = useService("action");
        this.ic = ic;
        const runId = this.props.action?.params?.run_id;
        // Somewhere else sent the person here and has to be able to take them
        // back. Deliberately read from the action's own context rather than
        // imported from the hub: this cockpit does not depend on that module,
        // and an import it does not have takes the whole bundle down.
        this.back = this.props.action?.context?.pb_back || null;
        this.state = useState({
            loaded: false,
            busy: false,
            runId: runId || null,
            picking: !runId,     // no run → show the picker
            runs: [],
            data: null,
            bank: null,
            companyAccount: "",
            bankReference: "",
            showExcl: false,
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

    /** Back to whatever sent us here, with everything it was holding. */
    goBack() {
        if (!this.back) { return; }
        const context = this.back.context || {};
        this.action.doAction({
            type: "ir.actions.client",
            tag: this.back.tag,
            name: this.back.label,
            target: "current",
            params: { ...context },
            context: { ...context },
        }, { clearBreadcrumbs: true });
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
            if (!this.state.bank && d.banks.length) {
                // default to the bank the last file used, else Vietcombank,
                // else the first layout there is
                const used = d.banks.find(b => b.key === d.bank_file.bank_format);
                const vcb = d.banks.find(b => b.key === "vietcombank");
                this.state.bank = (used || vcb || d.banks[0]).key;
            }
            if (d.release && d.release.bank_reference) {
                this.state.bankReference = d.release.bank_reference;
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

    // --------------------------------------------------------------- bank file
    selectBank(key) { this.state.bank = key; }
    onCompanyAccount(ev) { this.state.companyAccount = ev.target.value; }
    onBankReference(ev) { this.state.bankReference = ev.target.value; }
    toggleExcl() { this.state.showExcl = !this.state.showExcl; }

    get bankFile() { return (this.state.data && this.state.data.bank_file) || {}; }
    get release() { return (this.state.data && this.state.data.release) || {}; }
    get delivery() { return (this.state.data && this.state.data.delivery) || {}; }

    /** What the bank-file button says, so a press never surprises anybody. */
    get prepareLabel() {
        const again = this.bankFile.exists;
        if (this.bankFile.fast_lane) {
            return again ? _t("Prepare again — approved on the spot")
                         : _t("Prepare and approve now (no approval needed)");
        }
        return again ? _t("Prepare it again and send it in")
                     : _t("Prepare bank file for approval");
    }

    get releaseLabel() {
        return this.release.fast_lane
            ? _t("Release the money now (no approval needed)")
            : _t("Send the release for approval");
    }

    get sendLabel() {
        return this.delivery.fast_lane
            ? _t("Send payslips")
            : _t("Send payslips for approval");
    }

    async prepareBankFile() {
        if (!this.state.bank || this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "prepare_bank_file",
                [this.state.runId, this.state.bank, this.state.companyAccount || false]);
            await this.load();
            const f = this.bankFile;
            this.notif.add(
                f.state === "approved"
                    ? _t("The bank file is ready to download.")
                    : _t("The bank file is with %s for approval.",
                         f.with_whom || _t("its approver")),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async downloadFile() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const act = await this.orm.call(MODEL, "download_bank_file", [this.state.runId]);
            await this.action.doAction(act);
            await this.load();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- release
    async requestRelease() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "request_release",
                [this.state.runId, this.state.bankReference || false]);
            await this.load();
            const r = this.release;
            this.notif.add(
                r.state === "released"
                    ? _t("The money is marked as released.")
                    : _t("The release is with %s.", r.with_whom || _t("its approver")),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- payslips
    async send(forceAll) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "send_payslips", [this.state.runId, !!forceAll]);
            await this.load();
            const d = this.delivery;
            if (d.state === "pending") {
                this.notif.add(
                    _t("The payslips are with %s for approval.",
                       d.with_whom || _t("their approver")), { type: "success" });
            } else {
                this.notif.add(
                    _t("Delivery complete — %s sent, %s failed, %s skipped.",
                       d.sent, d.failed, d.skipped),
                    { type: d.failed ? "warning" : "success" });
            }
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- the door
    async openRequest(requestId) {
        if (!requestId) { return; }
        const act = await this.orm.call(MODEL, "open_request", [requestId]);
        this.action.doAction(act);
    }

    backToRuns() {
        this.state.picking = true;
        this.state.data = null;
        this.state.runId = null;
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
    /** The tone of a lane's status chip. One vocabulary for all three. */
    toneOf(state) {
        return {
            approved: "ok", released: "ok", done: "ok", posted: "ok",
            pending: "wait", draft: "", returned: "warn", sending: "wait",
            rejected: "bad", superseded: "muted",
        }[state] || "";
    }
    stepTone(status) {
        return { done: "ok", active: "wait", blocked: "bad",
                 returned: "warn", skipped: "muted" }[status] || "";
    }
    pillClass(state) {
        return { sent: "ok", failed: "bad", skipped_no_email: "warn" }[state] || "";
    }
    pillLabel(state) {
        return { sent: _t("Sent"), failed: _t("Failed"),
                 skipped_no_email: _t("No email") }[state] || state;
    }
    reasonList(reasons) { return (reasons || []).join(" · "); }
    // deep-link an excluded row to the employee's record so the reviewer can go
    // straight to the bank account that failed validation (payload carries the id)
    openEmployeeBank(employeeId) {
        if (!employeeId) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: employeeId,
            views: [[false, "form"]],
            target: "current",
        });
    }
    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed.");
    }
}

registry.category("actions").add("pb_pay_delivery", PbPayDelivery);
