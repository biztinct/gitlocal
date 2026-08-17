/** @odoo-module **/
/**
 * Attendance Control — a bespoke cockpit over the exception feed + correction
 * chain + bulk import. Three views: the board (KPIs · exceptions queue ·
 * corrections pipeline), the correction composer (day punches timeline + live
 * before/after + approval stepper), and the import stepper. RPC facade:
 * pb.attendance.flow. pbim-tokenized (.pbaf.pbim). Lucide icons only.
 *
 * ONE component, THREE mount points (W17): the client action `pb_attendance_flow`
 * keeps working untouched, and pb_time_hub mounts this same class twice —
 * `initialView="board"` as its Exceptions lens and `initialView="import"` as its
 * Import lens. `embedded` suppresses only the hero (the hub drew the page
 * header) and binds the feed's date window to the shared week (W4); every
 * facade call, every state machine and the whole composer are identical.
 */
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_attendance_flow/js/pbaf_icons";
import { addDays } from "@pb_wf_kit/js/wf_context_service";

const MODEL = "pb.attendance.flow";

const KIND_META = {
    missing_punch:    { icon: "alertCircle", label: _t("Missing punch"),   tone: "rose" },
    missing_checkout: { icon: "logOut",      label: _t("Missing check-out"), tone: "amber" },
    late:             { icon: "timer",       label: _t("Late arrival"),     tone: "amber" },
    early_leave:      { icon: "doorOpen",     label: _t("Early departure"),  tone: "amber" },
};

export class PbAttendanceFlow extends Component {
    static template = "pb_attendance_flow.PbAttendanceFlow";
    static props = {
        action: { type: Object, optional: true },
        // mounted as a hub lens rather than as a standalone client action
        embedded: { type: Boolean, optional: true },
        // which of the internal views the lens opens on: board | import
        initialView: { type: String, optional: true },
        // host-supplied person door (the hub's drawer); absent => native form
        onPerson: { type: Function, optional: true },
        // {employee_id, date, kind?} — open the composer prefilled for this
        // person/day on mount (the hub drawer's "File correction" hand-off)
        seed: { type: Object, optional: true },
        // host-supplied hook fired after a correction is filed/applied, so the
        // hub can refresh its ribbon without knowing anything about this state
        onChanged: { type: Function, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false, initialView: "board" };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.KIND_META = KIND_META;

        // Embedded: department + week come from the shared context (W4). The
        // standalone action keeps its own 14-day look-back — passing no window
        // leaves the facade on its historical default, so nothing about the
        // retired-but-still-live cockpit changes.
        this.ctxSvc = useService("wf_context");
        this.wf = useState(this.ctxSvc.state);
        if (this.props.embedded) {
            // onChange (not a render dep) because a context change must REFETCH,
            // not merely re-render; unsubscribed on unmount so a lens switch
            // cannot leave a callback writing into a dead component.
            const off = this.ctxSvc.onChange(() => this.load());
            onWillUnmount(off);
        }

        this.state = useState({
            loaded: false,
            busy: false,
            // board | composer | import
            view: this.props.initialView === "import" ? "import" : "board",
            data: null,
            activeKind: "all",
            refuseOpen: false,
            refuseNote: "",
            composer: null,             // correction detail
            imp: this._blankImport(),
        });
        onWillStart(async () => {
            await this.load();
            // The host remounts this lens (a keyed nonce) when it hands over a
            // seed, so onWillStart is the right — and only — place to consume
            // it: no prop-diffing, no half-open composer left behind.
            if (this.props.seed && this.props.seed.employee_id) {
                await this.seedCorrection(this.props.seed);
            }
        });
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

    /** [date_from, date_to, department_id] — the shared week when embedded. */
    _windowArgs() {
        if (!this.props.embedded) { return [false, false, false]; }
        // addDays is the kit's LOCAL-date helper — never rebuild week maths with
        // toISOString(), it slips a day in every non-UTC timezone.
        return [this.wf.weekStart, addDays(this.wf.weekStart, 6),
                this.wf.departmentId || false];
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_control_data", this._windowArgs());
            this.state.loaded = true;
            if (this.props.onChanged) { this.props.onChanged(this.state.data); }
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
    /**
     * Open the composer prefilled for an employee+day that did NOT come from an
     * exception row — the Time hub's person drawer hands over {employee_id,
     * date}. Same facade call, same guarded writer, same approval chain: only
     * the entry point differs.
     */
    async seedCorrection({ employee_id, date, kind }) {
        this.state.busy = true;
        try {
            const corr = await this.orm.call(MODEL, "create_correction", [{
                employee_id,
                date,
                correction_type: kind === "missing_punch" ? "create" : "adjust",
                exception_kind: kind || false,
                reason: _t("Correction filed from the person drawer for %(date)s.",
                           { date }),
            }]);
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
    /** The view a lens/cockpit returns to when an internal flow is closed. */
    get rootView() {
        return this.props.embedded && this.props.initialView === "import" ? "import" : "board";
    }
    get canLeaveImport() { return this.rootView !== "import"; }

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
            if (r.truncated) {
                this.notif.add(
                    _t("The file has more rows than the %s-row limit — only the first %s were read. Split the file to import the rest.", r.max_rows, r.max_rows),
                    { type: "warning", sticky: true });
            }
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
            if (imp.result.truncated) {
                this.notif.add(
                    _t("Only the first %s rows were imported — split the file for the rest.", imp.result.max_rows),
                    { type: "warning", sticky: true });
            }
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
    backFromImport() {
        // In the hub's Import lens there is no board to go back TO — the lens
        // IS the importer — so "done" resets the stepper instead of navigating.
        if (!this.canLeaveImport) {
            this.state.imp = this._blankImport();
            return;
        }
        this.state.view = "board";
        this.load();
    }

    // Every record is a door (W5). Inside the Time hub the door is the person
    // drawer — the host passes `onPerson`, nothing navigates, context is kept.
    // Standalone there is no drawer, so we fall back to the native form; as a
    // DIALOG, never target:"current", which would strand the officer with no
    // way back to the queue.
    openEmployee(employeeId) {
        if (this.props.onPerson) {
            this.props.onPerson(employeeId);
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: employeeId,
            views: [[false, "form"]],
            target: "new",
        });
    }

    // ---------------------------------------------------------- helpers
    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_attendance_flow", PbAttendanceFlow);
