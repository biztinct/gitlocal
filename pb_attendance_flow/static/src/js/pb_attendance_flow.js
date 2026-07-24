/** @odoo-module **/
/**
 * Attendance Control — a bespoke cockpit over the exception feed + correction
 * chain + bulk import. Three views: the board (KPIs · exceptions queue ·
 * corrections pipeline), the correction composer (day punches timeline + live
 * before/after + approval stepper), and the import stepper. RPC facade:
 * pb.attendance.flow. pbim-tokenized (.pbaf.pbim). Lucide icons only.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_attendance_flow/js/pbaf_icons";

const MODEL = "pb.attendance.flow";

const KIND_META = {
    missing_punch:    { icon: "alertCircle", label: _t("Missing punch"),   tone: "rose" },
    missing_checkout: { icon: "logOut",      label: _t("Missing check-out"), tone: "amber" },
    late:             { icon: "timer",       label: _t("Late arrival"),     tone: "amber" },
    early_leave:      { icon: "doorOpen",     label: _t("Early departure"),  tone: "amber" },
};

export class PbAttendanceFlow extends Component {
    static template = "pb_attendance_flow.PbAttendanceFlow";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.KIND_META = KIND_META;
        this.state = useState({
            loaded: false,
            busy: false,
            view: "board",              // board | composer | import
            data: null,
            activeKind: "all",
            refuseOpen: false,
            refuseNote: "",
            composer: null,             // correction detail
            imp: this._blankImport(),
        });
        onWillStart(async () => { await this.load(); });
    }

    _blankImport() {
        return {
            step: "upload",             // upload | map | validate | done
            fileName: "",
            fileB64: null,
            columns: [],
            sample: [],
            total: 0,
            mapping: { employee: "", date: "", check_in: "", check_out: "" },
            validation: null,
            result: null,
        };
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_control_data", []);
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    // ---------------------------------------------------------- exceptions queue
    get kindTabs() {
        const groups = (this.state.data && this.state.data.exception_groups) || [];
        return groups.map((g) => ({
            kind: g.kind, count: g.rows.length, ...KIND_META[g.kind],
        }));
    }
    get visibleExceptions() {
        const all = (this.state.data && this.state.data.exceptions) || [];
        if (this.state.activeKind === "all") { return all; }
        return all.filter((x) => x.kind === this.state.activeKind);
    }
    setKind(kind) { this.state.activeKind = kind; }
    minutesTone(mins) { return mins >= 30 ? "rose" : "amber"; }
    kindIcon(kind) { return (KIND_META[kind] || {}).icon || "alertCircle"; }
    kindLabel(kind) { return (KIND_META[kind] || {}).label || kind; }

    // pre-fill a correction from an exception row and open the composer
    async fileCorrection(x) {
        this.state.busy = true;
        try {
            const type = x.kind === "missing_punch" ? "create"
                : x.kind === "missing_checkout" ? "adjust" : "adjust";
            const payload = {
                employee_id: x.employee_id,
                date: x.date,
                correction_type: type,
                exception_kind: x.kind,
                reason: this._seedReason(x),
            };
            const corr = await this.orm.call(MODEL, "create_correction", [payload]);
            this._openComposer(corr);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    _seedReason(x) {
        return _t("%(label)s on %(date)s — %(detail)s",
            { label: this.kindLabel(x.kind), date: x.date, detail: x.detail || "" });
    }

    // ---------------------------------------------------------- composer
    async openCorrection(id) {
        this.state.busy = true;
        try {
            const corr = await this.orm.call(MODEL, "get_correction", [id]);
            this._openComposer(corr);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    _openComposer(corr) {
        this.state.composer = corr;
        this.state.refuseOpen = false;
        this.state.refuseNote = "";
        this.state.view = "composer";
    }
    backToBoard() {
        this.state.view = "board";
        this.state.composer = null;
        this.load();
    }

    onComposerField(field, ev) { this.state.composer[field] = ev.target.value; }
    setComposerType(type) { this.state.composer.type = type; }
    pickTargetPunch(punchId) {
        this.state.composer.attendance_id = punchId;
        const p = (this.state.composer.day_punches || []).find((q) => q.id === punchId);
        if (p) {
            this.state.composer.new_check_in = p.check_in;
            this.state.composer.new_check_out = p.check_out;
        }
    }

    _composerVals() {
        const c = this.state.composer;
        return {
            correction_type: c.type,
            attendance_id: c.attendance_id || false,
            new_check_in: c.new_check_in || false,
            new_check_out: c.new_check_out || false,
            reason: c.reason || "",
            date: c.date || false,
        };
    }
    async saveComposer() {
        const c = this.state.composer;
        this.state.busy = true;
        try {
            this.state.composer = await this.orm.call(
                MODEL, "save_correction", [c.id, this._composerVals()]);
            this.notif.add(_t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async composerAction(action) {
        if (action === "refuse") { this.state.refuseOpen = true; return; }
        const c = this.state.composer;
        this.state.busy = true;
        try {
            if (action === "submit") {
                await this.orm.call(MODEL, "save_correction", [c.id, this._composerVals()]);
            }
            this.state.composer = await this.orm.call(
                MODEL, "correction_action", [c.id, action], {});
            const after = this.state.composer;
            if (action === "approve" && after.state === "refused") {
                this.notif.add(after.apply_error || _t("Correction refused."), { type: "warning" });
            } else {
                this.notif.add(_t("Done."), { type: "success" });
            }
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async confirmRefuse() {
        const c = this.state.composer;
        this.state.busy = true;
        try {
            this.state.composer = await this.orm.call(
                MODEL, "correction_action", [c.id, "refuse"],
                { note: this.state.refuseNote || false });
            this.state.refuseOpen = false;
            this.state.refuseNote = "";
            this.notif.add(_t("Correction refused."), { type: "warning" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    cancelRefuse() { this.state.refuseOpen = false; this.state.refuseNote = ""; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }

    parsedStepper(json) {
        try { return JSON.parse(json || "{}"); } catch (e) { return {}; }
    }
    typeLabel(t) {
        return { create: _t("Add a punch"), adjust: _t("Adjust a punch"),
                 delete: _t("Remove a punch") }[t] || t; }
    stateLabel(s) {
        return { draft: _t("Draft"), submitted: _t("Submitted"),
                 approved: _t("Applied"), refused: _t("Refused") }[s] || s; }
    stateTone(s) {
        return { approved: "ok", submitted: "info", refused: "bad", draft: "" }[s] || ""; }

    // ---------------------------------------------------------- import
    openImport() { this.state.imp = this._blankImport(); this.state.view = "import"; }

    onImportFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const reader = new FileReader();
        reader.onload = () => {
            const b64 = String(reader.result).split(",")[1] || "";
            this.state.imp.fileB64 = b64;
            this.state.imp.fileName = file.name;
            this.parseImport();
        };
        reader.readAsDataURL(file);
    }
    async parseImport() {
        const imp = this.state.imp;
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "import_parse", [imp.fileB64, imp.fileName]);
            imp.columns = r.columns;
            imp.sample = r.sample;
            imp.total = r.total;
            imp.mapping = r.mapping;
            imp.step = "map";
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    onMap(target, ev) { this.state.imp.mapping[target] = ev.target.value; }
    async validateImport() {
        const imp = this.state.imp;
        this.state.busy = true;
        try {
            imp.validation = await this.orm.call(
                MODEL, "import_validate", [imp.fileB64, imp.fileName, imp.mapping]);
            imp.step = "validate";
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async commitImport() {
        const imp = this.state.imp;
        this.state.busy = true;
        try {
            imp.result = await this.orm.call(
                MODEL, "import_commit", [imp.fileB64, imp.fileName, imp.mapping]);
            imp.step = "done";
            this.notif.add(
                _t("%s imported, %s skipped.", imp.result.created, imp.result.skipped),
                { type: imp.result.skipped ? "warning" : "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    get canValidate() {
        const m = this.state.imp.mapping;
        return !!(m.employee && m.date && m.check_in);
    }
    backToMap() { this.state.imp.step = "map"; }
    backFromImport() { this.state.view = "board"; this.load(); }

    // deep-link an exception's employee to their record (native fallback)
    openEmployee(employeeId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: employeeId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---------------------------------------------------------- helpers
    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_attendance_flow", PbAttendanceFlow);
