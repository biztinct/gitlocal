/** @odoo-module **/
/**
 * Bank Verification cockpit — queues + a bespoke split verify screen (document
 * viewer left, extracted fields right). RPC facade: pb.bank.ocr. Reuses the
 * generic DocDrop for uploads. pbim-tokenized (.pbim.pbbk).
 *
 * IA CYCLE 5: the last Font Awesome in the product left this file's template.
 * Nine glyphs — a spinner, two arrows, a refresh, a tick, three warnings and a
 * pencil — became `ic()` calls against the shared Lucide registry (W2). Eight
 * of the nine already had an equivalent there; `pencil` was added for the ninth.
 * Two of them were `t-attf-class` expressions choosing a glyph by a condition,
 * which is the shape that survives longest unnoticed: they are now the same
 * condition choosing an ICON NAME, evaluated by this component's own `ic()`
 * method rather than by a class string nothing validates.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DocDrop } from "@biz_doc_ocr/js/doc_drop";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.bank.ocr";

const FIELD_DEFS = [
    { key: "x_bank_name", label: _t("Bank") },
    { key: "x_bank_branch", label: _t("Branch") },
    { key: "x_account_name", label: _t("Account Holder") },
    { key: "x_account_number", label: _t("Account Number") },
    { key: "x_iban", label: _t("IBAN") },
    { key: "x_swift", label: _t("SWIFT / BIC") },
];

export class PbBankOcr extends Component {
    static template = "pb_bank_ocr.PbBankOcr";
    static components = { DocDrop };
    static props = { action: { type: Object, optional: true }, "*": true };

    /** The shared Lucide helper. Never a glyph font, never an emoji (W2). */
    ic(name, size = 14) { return ic(name, size); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.fieldDefs = FIELD_DEFS;
        this.state = useState({
            loaded: false,
            view: "queue",
            data: { queues: {}, kpis: {}, provider: {}, is_hr: false, is_finance: false },
            req: null,
            edited: {},          // key -> true (field touched)
            busy: false,
            scanning: false,
            refuseOpen: false,
            refuseNote: "",
            history: null,
            step: "",            // quiet board: the step pressed ('' = the lanes)
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        this.state.data = await this.orm.call(MODEL, "get_queue_data", []);
        this.state.loaded = true;
    }

    // ------------------------------------------------------ quiet board
    //
    // The KPI tiles are one quiet line; the request's route is numbered
    // steps. A request is at EXACTLY one step (its state), counted once even
    // when it sits in two lanes (mine AND the HR queue); a refused one is an
    // outcome at no step. Counts cover what this board loaded for the reader.
    get allCards() {
        const q = this.state.data.queues || {};
        const seen = new Map();
        for (const lane of [q.mine, q.hr, q.finance, q.done]) {
            for (const c of (lane || [])) { if (!seen.has(c.id)) seen.set(c.id, c); }
        }
        return [...seen.values()];
    }
    get stepDefs() {
        return [
            { key: "draft", title: _t("Draft") },
            { key: "hr_review", title: _t("HR Review") },
            { key: "finance_review", title: _t("Finance Review") },
            { key: "approved", title: _t("Approved") },
        ];
    }
    _reqLabel(n) { return n === 1 ? _t("1 request") : _t("%s requests", n); }
    get steps() {
        const cards = this.allCards;
        const d = this.state.data;
        return this.stepDefs.map((st, i) => {
            const n = cards.filter((c) => c.state === st.key).length;
            const mine = (st.key === "hr_review" && d.is_hr) || (st.key === "finance_review" && d.is_finance);
            let flag = "";
            if (n && mine) {
                flag = n === 1 ? _t("1 waiting on you") : _t("%s waiting on you", n);
            } else if (n && (st.key === "hr_review" || st.key === "finance_review")) {
                flag = n === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", n);
            }
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count: n,
                countLabel: this._reqLabel(n), sub: "", flag, flagTone: "",
                on: this.state.step === st.key,
            };
        });
    }
    pickStep(key) { this.state.step = this.state.step === key ? "" : key; }
    get stepCards() { return this.allCards.filter((c) => c.state === this.state.step); }
    get stepTitle() {
        const st = this.stepDefs.find((x) => x.key === this.state.step);
        return st ? st.title : "";
    }
    get showingLine() {
        const all = this.allCards.length;
        if (!this.state.step) {
            return { all: true, text: !all ? _t("no requests yet") : all === 1 ? _t("all 1 request") : _t("all %s requests", all) };
        }
        return { all: false, text: _t("%s of %s requests", this.stepCards.length, all), where: this.stepTitle };
    }
    get glance() {
        const k = this.state.data.kpis || {};
        const d = this.state.data;
        const tone = (v) => (v ? "amber" : "");
        const out = [{ key: "mine", n: k.mine_open || 0, label: _t("My open"), tone: "", run: null }];
        if (d.is_hr) {
            out.push({ key: "hr", n: k.hr_pending || 0, label: _t("HR review"), tone: tone(k.hr_pending),
                       run: () => this.pickStep("hr_review") });
        }
        if (d.is_finance) {
            out.push({ key: "fin", n: k.finance_pending || 0, label: _t("Finance"), tone: tone(k.finance_pending),
                       run: () => this.pickStep("finance_review") });
        }
        return out;
    }
    get glanceOn() {
        return this.state.step === "hr_review" ? "hr" : this.state.step === "finance_review" ? "fin" : "";
    }

    // ------------------------------------------------------------- upload
    async onUpload(file) {
        this.state.busy = true;
        try {
            const id = await this.orm.call(MODEL, "create_from_upload", [{
                name: file.name, mime: file.mime, data: file.data,
            }]);
            await this.openReq(id, true);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async openReq(id, autoScan) {
        this.state.req = await this.orm.call(MODEL, "get_request", [id]);
        this.state.edited = {};
        this.state.view = "detail";
        this.state.history = null;
        if (autoScan && this.state.req.ocr_state === "pending") {
            await this.runOcr();
        }
    }

    back() { this.state.view = "queue"; this.state.req = null; this.load(); }

    // ------------------------------------------------------------- ocr
    async runOcr() {
        if (!this.state.req) { return; }
        this.state.scanning = true;
        try {
            this.state.req = await this.orm.call(MODEL, "run_ocr", [this.state.req.id]);
            this.state.edited = {};
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.scanning = false;
        }
    }

    // ------------------------------------------------------------- fields
    fieldVal(key) {
        return (this.state.req.fields[key] || {}).value || "";
    }
    confidence(key) {
        const c = (this.state.req.fields[key] || {}).confidence;
        return (c === null || c === undefined) ? null : Math.round(c * 100);
    }
    confBand(key) {
        const c = (this.state.req.fields[key] || {}).confidence;
        if (c === null || c === undefined) { return ""; }
        if (c >= 0.9) { return "green"; }
        if (c >= 0.6) { return "amber"; }
        return "rose";
    }
    onFieldInput(key, ev) {
        this.state.req.fields[key].value = ev.target.value;
        this.state.edited[key] = true;
    }
    isEdited(key) { return !!this.state.edited[key]; }

    async saveAndValidate() {
        const vals = {};
        for (const d of FIELD_DEFS) { vals[d.key] = this.fieldVal(d.key); }
        vals.duplicate_ack = this.state.req.duplicate_ack;
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "save_fields", [this.state.req.id, vals]);
            this.state.req = await this.orm.call(MODEL, "validate", [this.state.req.id]);
            this.state.edited = {};
            this.notif.add(_t("Validated."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    toggleAck() { this.state.req.duplicate_ack = !this.state.req.duplicate_ack; }

    // ------------------------------------------------------------- actions
    async doAction(action) {
        if (action === "refuse") { this.state.refuseOpen = true; return; }
        this.state.busy = true;
        try {
            // persist any field edits before advancing (owner submit path)
            if (action === "submit" && Object.keys(this.state.edited).length) {
                await this.saveAndValidate();
            }
            this.state.req = await this.orm.call(MODEL, "do_action",
                [this.state.req.id, action], {});
            const msg = action === "finance_approve"
                ? _t("Approved — the employee bank master has been updated.")
                : _t("Done.");
            this.notif.add(msg, { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async confirmRefuse() {
        this.state.busy = true;
        try {
            this.state.req = await this.orm.call(MODEL, "do_action",
                [this.state.req.id, "refuse"], { note: this.state.refuseNote || false });
            this.state.refuseOpen = false;
            this.state.refuseNote = "";
            this.notif.add(_t("Request refused."), { type: "warning" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    cancelRefuse() { this.state.refuseOpen = false; this.state.refuseNote = ""; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }

    // ------------------------------------------------------------- history
    async toggleHistory() {
        if (this.state.history) { this.state.history = null; return; }
        this.state.history = await this.orm.call(
            MODEL, "get_history", [this.state.req.employee_id]);
    }

    // ------------------------------------------------------------- settings
    async testProvider() {
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "test_provider", []);
            this.notif.add(
                (r.success ? _t("Provider OK") : _t("Provider error")) +
                (r.latency_ms ? ` · ${r.latency_ms} ms` : "") +
                (r.message ? ` · ${r.message}` : ""),
                { type: r.success ? "success" : "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- helpers
    get isPdf() {
        return this.state.req && /pdf/i.test(this.state.req.doc_mime || "");
    }
    get nameGaugeAngle() {
        // -90deg (0%) .. +90deg (100%) needle
        const s = (this.state.req && this.state.req.validation.name_score) || 0;
        return -90 + (s / 100) * 180;
    }
    bandLabel(band) {
        return { green: _t("Strong match"), amber: _t("Review"), red: _t("Mismatch") }[band] || "";
    }
    stateLabel(s) {
        return {
            draft: _t("Draft"), hr_review: _t("HR Review"),
            finance_review: _t("Finance Review"), approved: _t("Approved"),
            refused: _t("Refused"),
        }[s] || s;
    }
    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_bank_ocr", PbBankOcr);
