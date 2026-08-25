/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const IC = {
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    alert: '<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
    arrow: '<path d="M5 12h14M12 5l7 7-7 7"/>',
    back: '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>',
    receipt: '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M12 17.5v-11"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
};
const STEPS = ["Source & file", "Review & match", "Validate", "Commit"];
const LINE_CLS = { matched: "ok", validated: "ok", processed: "ok", new: "new", unmatched: "warn", error: "err", draft: "muted" };
const LINE_LABEL = { matched: "Matched", validated: "Validated", processed: "Processed", unmatched: "Unmatched", error: "Error", draft: "Pending" };

export class ImportWizard extends Component {
    static template = "pb_import_wizard.ImportWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            step: 1, loading: false, busyMsg: "",
            defaults: null,
            form: { name: "", source_type: "excel", formula_config_id: "", connector_id: "",
                    date_from: "", date_to: "", file_b64: "", file_name: "", period: "" },
            summary: null,
            match: { lineId: null, term: "", results: [] },
        });
        // JOURNEY J2 — the doors that were already scoped stay scoped.
        //
        // Every legacy import door now lands here, and four of them knew
        // something when they were pressed: the scheme whose form you were on,
        // the connection whose cockpit you were in, whether a file or a pull is
        // meant. Landing on "the first scheme alphabetically" would have made
        // consolidation a downgrade for exactly the users who had a shortcut.
        // Read once from the arrival context and never written back — the
        // arrival protocol every cockpit in this product follows. Anything the
        // context names that this user cannot have is simply not applied, and
        // the picker below shows what they did get.
        const ctx = (this.props.action && this.props.action.context) || {};
        this.arrival = {
            config: Number(ctx.default_formula_config_id) || 0,
            connector: Number(ctx.default_connector_id) || 0,
            source: ["excel", "connector", "api_data_store", "manual"]
                .includes(ctx.default_source_type) ? ctx.default_source_type : "",
        };
        onWillStart(async () => {
            const d = await this.orm.call("pb.import.wizard", "get_defaults", []);
            this.state.defaults = d;
            this.state.form.name = d.name;
            const pick = (list, asked) =>
                (asked && (list || []).some((x) => x.id === asked) ? asked
                    : ((list || []).length ? list[0].id : 0));
            const cfg = pick(d.configs, this.arrival.config);
            const con = pick(d.connectors, this.arrival.connector);
            if (cfg) this.state.form.formula_config_id = String(cfg);
            if (con) this.state.form.connector_id = String(con);
            if (this.arrival.source) this.state.form.source_type = this.arrival.source;
        });
    }

    ic(n, s = 16) { return markup(`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${IC[n] || IC.check}</svg>`); }
    get steps() { return STEPS; }
    lineCls(s) { return LINE_CLS[s] || "muted"; }
    lineLabel(l) { return l.is_new ? "New employee" : (LINE_LABEL[l.state] || l.state); }

    onField(f, ev) { this.state.form[f] = ev.target.value; }
    setSource(id) { this.state.form.source_type = id; }

    // period preset chips — fill the date inputs (mirrors the native form)
    applyPeriod(p) {
        this.state.form.period = p.id;
        if (p.id !== "custom") {
            this.state.form.date_from = p.date_from;
            this.state.form.date_to = p.date_to;
        }
    }

    // ---- inline manual match (validate step) ----
    openMatch(lineId) {
        const m = this.state.match;
        m.lineId = m.lineId === lineId ? null : lineId;
        m.term = ""; m.results = [];
        if (m.lineId) this._searchEmp("");
    }
    async onMatchSearch(ev) {
        this.state.match.term = ev.target.value;
        await this._searchEmp(ev.target.value);
    }
    async _searchEmp(term) {
        try {
            this.state.match.results = await this.orm.call(
                "pb.import.wizard", "search_employees", [term, 12]);
        } catch (e) {
            this.state.match.results = [];
        }
    }
    async pickEmployee(empId) {
        const lineId = this.state.match.lineId;
        if (!lineId) return;
        this.state.summary = await this.orm.call(
            "pb.import.wizard", "match_line", [lineId, empId, false]);
        this.state.match.lineId = null; this.state.match.results = [];
    }
    async markNewEmployee(lineId) {
        this.state.summary = await this.orm.call(
            "pb.import.wizard", "match_line", [lineId, false, true]);
        this.state.match.lineId = null; this.state.match.results = [];
    }
    onFile(ev) {
        const f = ev.target.files && ev.target.files[0];
        if (!f) return;
        const reader = new FileReader();
        reader.onload = () => {
            this.state.form.file_b64 = String(reader.result).split(",")[1] || "";
            this.state.form.file_name = f.name;
        };
        reader.readAsDataURL(f);
    }

    get canLoad() {
        const f = this.state.form;
        if (!f.formula_config_id) return false;
        if (f.source_type === "excel") return !!f.file_b64;
        if (f.source_type === "connector" || f.source_type === "api_data_store") return !!f.connector_id;
        return false;
    }

    async _run(method, args, msg, nextStep) {
        this.state.loading = true; this.state.busyMsg = msg;
        try {
            const res = await this.orm.call("pb.import.wizard", method, args);
            this.state.summary = res;
            if (res && res.error) this.notif.add(res.error, { type: "warning" });
            if (nextStep) this.state.step = nextStep;
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || "Step failed.", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    toReview() {
        if (!this.canLoad) return;
        return this._run("create_and_load", [this.state.form], "Loading file and matching employees…", 2);
    }
    toValidate() {
        return this._run("do_validate", [this.state.summary.batch_id], "Validating rows…", 3);
    }
    commit() {
        return this._run("do_process", [this.state.summary.batch_id], "Committing — creating employees & payslips…", 4);
    }
    async fixLine(id, op) {
        const res = await this.orm.call("pb.import.wizard", "fix_line", [id, op]);
        this.state.summary = res;
    }

    // derived line buckets for step 3
    get errorLines() { return (this.state.summary?.lines || []).filter(l => l.state === "error" || l.state === "unmatched"); }

    back() { if (this.state.step > 1) this.state.step -= 1; }
    openRun() {
        const id = this.state.summary?.payslip_run_id;
        if (id) this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.payslip.run", res_id: id, views: [[false, "form"]], target: "current" });
    }
    openBatch() {
        const id = this.state.summary?.batch_id;
        if (id) this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.payroll.import.batch", res_id: id, views: [[false, "form"]], target: "current" });
    }
    close() { this.action.doAction("pb_import.action_pb_import", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_import_wizard", ImportWizard);
