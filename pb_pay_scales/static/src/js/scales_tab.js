/** @odoo-module **/
/**
 * WDGAP S8-A — People › Pay › Scales.
 *
 * THE HERO IS THE LADDER WITH PEOPLE ON IT: a grade-by-step grid where every
 * cell shows its amount and how many people stand there. Click a cell to type;
 * "+%" on a row, a column or the whole table moves every cell at once. Nothing
 * is written until "Save the table", and saving the table never touches a
 * contract: people whose wage no longer equals their step read "Drifted"
 * until somebody decides (the contract drawer's "Bring to step", which then
 * goes through the contract's own approval).
 *
 * Registered as a Pay tab through `pb_pay_tabs` (the seam in pay_hub.js), in
 * front of Bands — the blueprint's tab order "Scales · Bands · …".
 *
 * Rules kept from the Pay screen: every icon from the shared `ic()` set; one
 * expression per sentence; Escape in the capture phase; the refusal ladder
 * never reads `error.message` (GR17).
 */
import { Component, onWillStart, useExternalListener, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.pay.scales";

function money(value, cur) {
    if (value === null || value === undefined || value === "") { return ""; }
    const decimals = cur && Number.isInteger(cur.decimals) ? cur.decimals : 0;
    const text = Number(value).toLocaleString(undefined, {
        minimumFractionDigits: decimals, maximumFractionDigits: decimals,
    });
    const symbol = (cur && cur.symbol) || "";
    if (!symbol) { return text; }
    return cur.position === "before" ? symbol + text : text + " " + symbol;
}

function parseNumber(text) {
    const clean = String(text === undefined || text === null ? "" : text)
        .replace(/[\s,]/g, "").replace(/[^0-9.\-]/g, "");
    if (clean === "" || clean === "-" || clean === ".") { return null; }
    const value = Number(clean);
    return Number.isFinite(value) ? value : null;
}

function roundTo(value, unit, decimals) {
    if (unit && unit > 0) { return Math.round(value / unit) * unit; }
    const f = Math.pow(10, decimals || 0);
    return Math.round(value * f) / f;
}

export class PbPayScales extends Component {
    static template = "pb_pay_scales.PbPayScales";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.overlay = useService("overlay");
        this.state = useState({
            loaded: false, failed: "", d: null,
            scaleId: 0, versionId: 0,
            staged: {}, baseRate: null,
            editing: "", grow: null, busy: false,
            drawer: null, newGrade: "",
        });
        onWillStart(() => this.load());
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
    }

    ic(name, size = 16) { return ic(name, size); }

    // ============================================================ errors
    _msg(error, fallback) {
        const data = error && error.data;
        if (data && data.message) { return data.message; }
        const nested = error && error.message && error.message.data;
        if (nested && nested.message) { return nested.message; }
        return fallback;
    }
    _fail(error, fallback) {
        this.notif.add(this._msg(error, fallback), { type: "warning" });
    }

    // =========================================================== reading
    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_scales", [
                this.state.scaleId || 0, this.state.versionId || 0]);
            this.state.d = d;
            this.state.failed = "";
            if (d && d.scale) {
                this.state.scaleId = d.scale.id;
                this.state.versionId = d.scale.version ? d.scale.version.id : 0;
            }
        } catch (error) {
            this.state.failed = this._msg(error, _t("The pay scales could not be read just now. Try again in a moment."));
        }
        this.state.loaded = true;
    }

    get d() { return this.state.d || {}; }
    get scale() { return this.d.scale || null; }
    get scales() { return this.d.scales || []; }
    get canWrite() { return Boolean(this.d.can_write); }
    get cur() { return (this.scale && this.scale.currency) || {}; }
    get version() { return (this.scale && this.scale.version) || null; }
    get editable() { return Boolean(this.canWrite && this.version && this.version.editable); }
    get isCoef() { return Boolean(this.scale && this.scale.mode === "coefficient"); }
    get steps() {
        const n = (this.scale && this.scale.step_count) || 0;
        return Array.from({ length: n }, (_v, i) => i + 1);
    }
    get grades() { return (this.scale && this.scale.grades) || []; }
    get health() { return (this.scale && this.scale.health) || {}; }
    get wire() { return (this.scale && this.scale.wire) || []; }
    get stagedCount() {
        return Object.keys(this.state.staged).length + (this.state.baseRate === null ? 0 : 1);
    }
    get saveLabel() {
        const n = this.stagedCount;
        return n === 1 ? _t("Save 1 change") : _t("Save %s changes", n);
    }
    get versionLine() {
        const v = this.version;
        if (!v) { return ""; }
        return _t("Version %(n)s of %(total)s", { n: v.number, total: this.scale.version_count });
    }
    get endedLine() {
        return _t("This version has ended. It is kept exactly as it was; make a new version to change the amounts.");
    }
    get safeLine() {
        return _t("Saving the table changes what the scale says. Nobody's pay changes: people whose pay no longer matches their step show as Drifted.");
    }

    async pickScale(id) {
        if (this.stagedCount && !window.confirm(_t("Leave without saving the table?"))) { return; }
        this.discard();
        this.state.scaleId = id;
        this.state.versionId = 0;
        await this.load();
    }
    async pickVersion(id) {
        if (this.stagedCount && !window.confirm(_t("Leave without saving the table?"))) { return; }
        this.discard();
        this.state.versionId = id;
        await this.load();
    }

    // ============================================================= cells
    key(grade, step) { return grade.id + ":" + step; }
    cellOf(grade, step) { return grade.cells[step - 1] || {}; }
    baseRate() {
        if (this.state.baseRate !== null) { return this.state.baseRate; }
        return (this.version && this.version.base_rate) || 0;
    }
    /** The number typed in the cell: an amount, or a coefficient. */
    rawOf(grade, step) {
        const k = this.key(grade, step);
        if (Object.prototype.hasOwnProperty.call(this.state.staged, k)) { return this.state.staged[k]; }
        const c = this.cellOf(grade, step);
        return this.isCoef ? (c.coefficient || 0) : (c.amount || 0);
    }
    valueOf(grade, step) {
        const raw = this.rawOf(grade, step);
        if (!this.isCoef) { return raw; }
        return roundTo(raw * this.baseRate(), this.scale.rounding, this.cur.decimals);
    }
    cellLabel(grade, step) {
        const v = this.valueOf(grade, step);
        return v ? money(v, this.cur) : "";
    }
    coefLabel(grade, step) {
        const raw = this.rawOf(grade, step);
        return raw ? String(raw) : "";
    }
    isStaged(grade, step) {
        return Object.prototype.hasOwnProperty.call(this.state.staged, this.key(grade, step));
    }
    cellClass(grade, step) {
        return {
            "pbs-cell": true,
            "is-staged": this.isStaged(grade, step),
            "is-empty": !this.valueOf(grade, step),
            "is-editing": this.state.editing === this.key(grade, step),
            "is-edit": this.editable,
        };
    }
    peopleLine(n) {
        if (!n) { return _t("nobody"); }
        return n === 1 ? _t("1 person") : _t("%s people", n);
    }
    startEdit(grade, step) {
        if (!this.editable) { return; }
        this.state.editing = this.key(grade, step);
        this._focusCell();
    }
    /** The input appears on the next paint; focus it and select its text. */
    _focusCell() {
        setTimeout(() => {
            const el = document.querySelector(".pbs-cell-in");
            if (el) { el.focus(); el.select(); }
        }, 0);
    }
    commitEdit(grade, step, text) {
        const value = parseNumber(text);
        const k = this.key(grade, step);
        this.state.editing = "";
        if (value === null || value < 0) { return; }
        const c = this.cellOf(grade, step);
        const was = this.isCoef ? (c.coefficient || 0) : (c.amount || 0);
        const final = this.isCoef ? value : roundTo(value, this.scale.rounding, this.cur.decimals);
        if (Math.abs(final - was) < 1e-9) { delete this.state.staged[k]; } else { this.state.staged[k] = final; }
    }
    onCellKey(grade, step, ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.commitEdit(grade, step, ev.target.value); }
        if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this.state.editing = ""; }
        if (ev.key === "Tab") {
            ev.preventDefault();
            this.commitEdit(grade, step, ev.target.value);
            const next = step < this.steps.length ? step + 1 : 0;
            if (next) { this.state.editing = this.key(grade, next); this._focusCell(); }
        }
    }
    onBaseRate(ev) {
        const value = parseNumber(ev.target.value);
        if (value === null || value < 0) { return; }
        this.state.baseRate = Math.abs(value - ((this.version && this.version.base_rate) || 0)) < 1e-9 ? null : value;
    }

    // ============================================================== grow
    openGrow(scope, ref) {
        if (!this.editable) { return; }
        this.state.grow = { scope, ref, pct: "" };
    }
    onGrowInput(ev) { this.state.grow.pct = ev.target.value; }
    applyGrow() {
        const g = this.state.grow;
        const pct = parseNumber(g && g.pct);
        if (pct === null) { this.state.grow = null; return; }
        const factor = 1 + pct / 100;
        for (const grade of this.grades) {
            if (g.scope === "row" && grade.id !== g.ref) { continue; }
            for (const step of this.steps) {
                if (g.scope === "col" && step !== g.ref) { continue; }
                const raw = this.rawOf(grade, step);
                if (!raw) { continue; }
                const next = this.isCoef ? Math.round(raw * factor * 10000) / 10000
                    : roundTo(raw * factor, this.scale.rounding, this.cur.decimals);
                const c = this.cellOf(grade, step);
                const was = this.isCoef ? (c.coefficient || 0) : (c.amount || 0);
                const k = this.key(grade, step);
                if (Math.abs(next - was) < 1e-9) { delete this.state.staged[k]; } else { this.state.staged[k] = next; }
            }
        }
        this.state.grow = null;
    }
    growTitle(scope) {
        if (scope === "row") { return _t("Grow this grade by a percentage"); }
        if (scope === "col") { return _t("Grow this step by a percentage"); }
        return _t("Grow the whole table by a percentage");
    }
    isGrowing(scope, ref) {
        const g = this.state.grow;
        return Boolean(g && g.scope === scope && g.ref === ref);
    }

    discard() {
        this.state.staged = {};
        this.state.baseRate = null;
        this.state.editing = "";
        this.state.grow = null;
    }

    async saveTable() {
        if (!this.stagedCount || this.state.busy) { return; }
        const cells = [];
        for (const [k, value] of Object.entries(this.state.staged)) {
            const [gid, step] = k.split(":").map(Number);
            cells.push(this.isCoef ? { grade_id: gid, step, coefficient: value }
                : { grade_id: gid, step, amount: value });
        }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "save_cells", [this.version.id, cells,
                this.state.baseRate === null ? null : this.state.baseRate]);
            this.discard();
            await this.load();
            this.notif.add(_t("The table is saved. Nobody's pay changed."), { type: "success" });
        } catch (error) {
            this._fail(error, _t("The table could not be saved just now."));
        }
        this.state.busy = false;
    }

    async proposeFromWages() {
        if (!this.editable) { return; }
        this.state.busy = true;
        try {
            const answer = await this.orm.call(MODEL, "propose_from_wages", [this.scale.id]);
            if (!answer.ok) {
                this.notif.add(answer.sentence, { type: "info" });
            } else {
                for (const row of answer.cells) {
                    const grade = this.grades.find((g) => g.id === row.grade_id);
                    if (!grade || this.isCoef) { continue; }
                    const c = this.cellOf(grade, row.step);
                    const k = this.key(grade, row.step);
                    if (Math.abs((c.amount || 0) - row.amount) > 1e-9) { this.state.staged[k] = row.amount; }
                }
                this.notif.add(answer.sentence, { type: "info" });
            }
        } catch (error) {
            this._fail(error, _t("A suggestion could not be worked out just now."));
        }
        this.state.busy = false;
    }

    // ============================================================ grades
    onNewGrade(ev) { this.state.newGrade = ev.target.value; }
    async addGrade(ev) {
        if (ev && ev.key && ev.key !== "Enter") { return; }
        const name = (this.state.newGrade || "").trim();
        if (!name || !this.canWrite) { return; }
        try {
            await this.orm.call(MODEL, "save_grade", [this.scale.id, 0, { name }]);
            this.state.newGrade = "";
            await this.load();
        } catch (error) {
            this._fail(error, _t("The grade could not be added just now."));
        }
    }
    async moveGrade(grade, direction) {
        try {
            await this.orm.call(MODEL, "move_grade", [grade.id, direction]);
            await this.load();
        } catch (error) {
            this._fail(error, _t("The grade could not be moved just now."));
        }
    }
    openGrade(grade) {
        this.state.drawer = {
            kind: "grade", gradeId: grade.id, name: grade.name,
            jobTerm: "", jobRows: [], pkgTerm: "", pkgRows: [],
            package: grade.package.map((p) => ({ template_id: p.template_id, code: p.code, name: p.name, amount: p.amount })),
            pkgDirty: false,
        };
        this.searchJobs("");
    }
    get drawerGrade() {
        const dr = this.state.drawer;
        return dr && dr.kind === "grade" ? (this.grades.find((g) => g.id === dr.gradeId) || null) : null;
    }
    onDrawerName(ev) { this.state.drawer.name = ev.target.value; }
    async renameGrade() {
        const dr = this.state.drawer;
        const name = (dr.name || "").trim();
        if (!name) { return; }
        try {
            await this.orm.call(MODEL, "save_grade", [this.scale.id, dr.gradeId, { name }]);
            await this.load();
        } catch (error) { this._fail(error, _t("The grade could not be renamed just now.")); }
    }
    async removeGrade() {
        const dr = this.state.drawer;
        if (!window.confirm(_t("Remove this grade and its amounts?"))) { return; }
        try {
            await this.orm.call(MODEL, "remove_grade", [dr.gradeId]);
            this.state.drawer = null;
            await this.load();
        } catch (error) { this._fail(error, _t("The grade could not be removed just now.")); }
    }
    async searchJobs(term) {
        const dr = this.state.drawer;
        if (!dr) { return; }
        dr.jobTerm = term;
        try {
            const rows = await this.orm.call(MODEL, "jobs_for_grade", [dr.gradeId, term]);
            if (this.state.drawer === dr && dr.jobTerm === term) { dr.jobRows = rows; }
        } catch (error) { dr.jobRows = []; }
    }
    onJobTerm(ev) { this.searchJobs(ev.target.value || ""); }
    async linkJob(row) {
        const dr = this.state.drawer;
        try {
            await this.orm.call(MODEL, "link_job", [dr.gradeId, row.link_id]);
            await this.load();
            await this.searchJobs(dr.jobTerm);
        } catch (error) { this._fail(error, _t("The job could not be put on this grade just now.")); }
    }
    async unlinkJob(job) {
        const dr = this.state.drawer;
        try {
            await this.orm.call(MODEL, "unlink_job", [job.link_id]);
            await this.load();
            await this.searchJobs(dr.jobTerm);
        } catch (error) { this._fail(error, _t("The job could not be taken off this grade just now.")); }
    }
    jobRowLine(row) {
        if (row.here) { return _t("On this grade"); }
        if (row.grade) { return _t("Now on %s", row.grade); }
        return row.band;
    }

    // ------------------------------------------------- grade allowances
    async onPkgTerm(ev) {
        const dr = this.state.drawer;
        const term = ev.target.value || "";
        dr.pkgTerm = term;
        if (term.length < 1) { dr.pkgRows = []; return; }
        try {
            const rows = await this.orm.call(MODEL, "lookup_templates", [term]);
            if (this.state.drawer === dr && dr.pkgTerm === term) {
                const have = new Set(dr.package.map((p) => p.template_id));
                dr.pkgRows = rows.filter((r) => !have.has(r.id));
            }
        } catch (error) { dr.pkgRows = []; }
    }
    addPkg(row) {
        const dr = this.state.drawer;
        dr.package.push({ template_id: row.id, code: row.code, name: row.name, amount: 0 });
        dr.pkgRows = [];
        dr.pkgTerm = "";
        dr.pkgDirty = true;
    }
    onPkgAmount(line, ev) {
        const value = parseNumber(ev.target.value);
        line.amount = value === null ? 0 : value;
        this.state.drawer.pkgDirty = true;
    }
    dropPkg(index) {
        this.state.drawer.package.splice(index, 1);
        this.state.drawer.pkgDirty = true;
    }
    pkgMoney(line) { return money(line.amount, this.cur); }
    async savePkg() {
        const dr = this.state.drawer;
        try {
            await this.orm.call(MODEL, "save_package", [this.version.id, dr.gradeId,
                dr.package.map((p) => ({ template_id: p.template_id, amount: p.amount }))]);
            dr.pkgDirty = false;
            await this.load();
            this.notif.add(_t("The allowances are saved. They are filled in for new joiners placed on this grade."), { type: "success" });
        } catch (error) { this._fail(error, _t("The allowances could not be saved just now.")); }
    }

    // ============================================================ people
    async openPeople(title, args) {
        this.state.drawer = { kind: "people", title, rows: [], loading: true, args };
        await this.reloadPeople();
    }
    async reloadPeople() {
        const dr = this.state.drawer;
        if (!dr || dr.kind !== "people") { return; }
        try {
            const a = dr.args;
            const answer = await this.orm.call(MODEL, "people",
                [this.scale.id, a.grade || 0, a.step || 0, a.state || ""]);
            dr.rows = answer.rows || [];
        } catch (error) {
            dr.rows = [];
            this._fail(error, _t("The people could not be read just now."));
        }
        dr.loading = false;
    }
    openCellPeople(grade, step) {
        const cell = this.cellOf(grade, step);
        if (!cell.people) { return; }
        this.openPeople(_t("%(grade)s, step %(step)s", { grade: grade.name, step }), { grade: grade.id, step });
    }
    openState(key) {
        const titles = {
            on: _t("On scale"), pinned: _t("Pinned"), drifted: _t("Drifted"),
            unplaced: _t("Not placed yet"),
        };
        this.openPeople(titles[key] || "", { state: key });
    }
    hcClass(key) {
        const n = this.health[key] || 0;
        return {
            "pay-hc": true, "pbs-hc": true,
            "is-quiet": n === 0,
            "is-warn": key === "drifted" && n > 0,
            "is-act": key === "unplaced" && n > 0,
        };
    }
    get matchLine() {
        const n = this.health.match || 0;
        return n === 1 ? _t("Place the 1 person paid exactly a step") : _t("Place the %s people paid exactly a step", n);
    }
    async placeMatching() {
        this.state.busy = true;
        try {
            const answer = await this.orm.call(MODEL, "place_matching", [this.scale.id]);
            this.notif.add(answer.msg, { type: answer.ok ? "success" : "info" });
            await this.load();
            await this.reloadPeople();
        } catch (error) { this._fail(error, _t("People could not be placed just now.")); }
        this.state.busy = false;
    }
    async placeRow(row) {
        try {
            await this.orm.call(MODEL, "place", [row.contract_id, this.gradeIdOf(row), row.step]);
            await this.load();
            await this.reloadPeople();
        } catch (error) { this._fail(error, _t("This person could not be placed just now.")); }
    }
    gradeIdOf(row) {
        const grade = this.grades.find((g) => g.name === row.grade);
        return grade ? grade.id : 0;
    }
    async keepPay(row) {
        try {
            await this.orm.call(MODEL, "pin_from_drawer", [row.contract_id]);
            await this.load();
            await this.reloadPeople();
        } catch (error) { this._fail(error, _t("This could not be saved just now.")); }
    }
    async unpinRow(row) {
        try {
            await this.orm.call(MODEL, "unpin", [row.contract_id]);
            await this.load();
            await this.reloadPeople();
        } catch (error) { this._fail(error, _t("This could not be saved just now.")); }
    }
    stateTone(row) { return "pbs-st is-" + row.state; }
    stateWord(row) {
        return { on: _t("On scale"), pinned: _t("Pinned"), drifted: _t("Drifted"), unplaced: _t("Not placed") }[row.state] || "";
    }
    /** The contract drawer, from pb_contracts, opened over this screen. */
    openContract(row) {
        const Drawer = registry.category("pb_contracts_drawer").get("contract_360", null);
        if (!Drawer) { return; }
        let remove = () => {};
        remove = this.overlay.add(Drawer, {
            contractId: row.contract_id,
            onClose: () => { remove(); this.load().then(() => this.reloadPeople()); },
        });
    }

    // ===================================================== new / settings
    openNew() {
        const today = this.d.today || "";
        this.state.drawer = {
            kind: "new", name: "", country: (this.d.countries && this.d.countries[0] && this.d.countries[0].code) || "VN",
            steps: 4, mode: "amount", rounding: "", grades: "", date_from: today ? today.slice(0, 8) + "01" : "",
        };
    }
    openSettings() {
        const s = this.scale;
        this.state.drawer = {
            kind: "settings", name: s.name, steps: s.step_count, rounding: s.rounding || "",
            company_ids: [...s.company_ids], note: s.note,
        };
    }
    openVersion() {
        this.state.drawer = { kind: "version", date_from: "", grow: "" };
    }
    onDrawer(field, ev) { this.state.drawer[field] = ev.target.value; }
    toggleCompany(id) {
        const list = this.state.drawer.company_ids;
        const at = list.indexOf(id);
        if (at >= 0) { list.splice(at, 1); } else { list.push(id); }
    }
    hasCompany(id) { return this.state.drawer.company_ids.includes(id); }
    async createScale() {
        const dr = this.state.drawer;
        const grades = (dr.grades || "").split("\n").map((g) => g.trim()).filter(Boolean);
        try {
            const res = await this.orm.call(MODEL, "save_scale", [0, {
                name: dr.name, country_code: dr.country, step_count: Number(dr.steps) || 1,
                mode: dr.mode, rounding: parseNumber(dr.rounding) || 0, grades,
                date_from: dr.date_from || false,
            }]);
            this.state.drawer = null;
            this.state.scaleId = res.scale_id;
            this.state.versionId = 0;
            await this.load();
        } catch (error) { this._fail(error, _t("The scale could not be made just now.")); }
    }
    async saveSettings() {
        const dr = this.state.drawer;
        try {
            await this.orm.call(MODEL, "save_scale", [this.scale.id, {
                name: dr.name, step_count: Number(dr.steps) || 1,
                rounding: parseNumber(dr.rounding) || 0, company_ids: dr.company_ids, note: dr.note,
            }]);
            this.state.drawer = null;
            this.discard();
            await this.load();
        } catch (error) { this._fail(error, _t("The scale could not be saved just now.")); }
    }
    async removeScale() {
        if (!window.confirm(_t("Remove this pay scale? Its grades and amounts go with it."))) { return; }
        try {
            await this.orm.call(MODEL, "remove_scale", [this.scale.id]);
            this.state.drawer = null;
            this.state.scaleId = 0;
            this.state.versionId = 0;
            await this.load();
        } catch (error) { this._fail(error, _t("The scale could not be removed just now.")); }
    }
    async createVersion() {
        const dr = this.state.drawer;
        try {
            const res = await this.orm.call(MODEL, "new_version", [this.scale.id, dr.date_from,
                parseNumber(dr.grow) || 0]);
            this.state.drawer = null;
            this.state.versionId = res.version_id;
            this.discard();
            await this.load();
        } catch (error) { this._fail(error, _t("The new version could not be made just now.")); }
    }
    async removeVersion() {
        if (!window.confirm(_t("Remove this version? It has not started yet."))) { return; }
        try {
            await this.orm.call(MODEL, "remove_version", [this.version.id]);
            this.state.versionId = 0;
            await this.load();
        } catch (error) { this._fail(error, _t("The version could not be removed just now.")); }
    }
    versionClass(v) {
        return { "pbs-ver": true, "is-on": this.version && v.id === this.version.id, "is-current": v.current, "is-ended": v.ended };
    }
    versionTag(v) {
        if (v.current) { return _t("in force"); }
        if (v.future) { return _t("coming"); }
        return _t("ended");
    }
    closeDrawer() { this.state.drawer = null; }

    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.editing) { return; }
        if (this.state.grow) { this.state.grow = null; ev.stopPropagation(); return; }
        if (this.state.drawer) { this.state.drawer = null; ev.stopPropagation(); }
    }
}

registry.category("pb_pay_tabs").add("scales", {
    icon: "layers",
    label: _t("Scales"),
    title: _t("Pay scales"),
    subtitle: _t("A table of grades and steps, one amount each, dated. A new joiner starts on step 1 of their job's grade. Nothing here changes anybody's pay."),
    before: "bands",
    Component: PbPayScales,
});
