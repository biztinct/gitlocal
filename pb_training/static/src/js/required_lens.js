/** @odoo-module **/
/**
 * Learning › REQUIRED (LEARNING L2) — who must hold what, and who is missing it.
 *
 * Four inner tabs: MATRIX (default) · RULES · DAY ONE · COMES ROUND AGAIN.
 *
 * HERO MOMENT (matrix): one sentence over the grid — "92% in date across 214
 * people · 12 expiring · 5 missing" — with the percent drawn as a quiet ring,
 * and four state chips that filter the rows (grey at zero; rose / amber /
 * indigo only when there is something to act on).
 *
 * The grid clones the roster's (pb_schedule, handover F6): a scrolling box,
 * sticky header row and sticky first columns, 200 people a page with a
 * "showing N of M" line. A missing or expiring cell opens a small "Assign
 * now" popover; a column header opens the rule; ticked rows get "Assign now"
 * and "Set safety group" (managers) in a bulk bar.
 *
 * Reads `pb.training.matrix` / `required_rules` (gated: `allowed: false` and a
 * sentence for a reader outside the training team). Writes go through the
 * board's one verb, `pb.training.act`. A trainer may assign from a cell; only
 * a training manager sees New / Edit / Switch off / Set safety group.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const TABS = ["matrix", "rules", "day_one", "recurring"];
const STATE_KEYS = ["missing", "expiring", "in_progress", "not_due"];
const SETTINGS_XMLID = "pb_training.action_pb_training_required_settings";

function blankForm(kind = "always") {
    return {
        id: 0, name: "", kind, target: "course", channel_id: 0,
        refresher_channel_id: 0, name_pattern: "", hours_required: 0, path_id: 0,
        validity_months: kind === "recurring" ? 12 : 0, due_days: kind === "day_one" ? 14 : 30,
        every_months: kind === "recurring" ? 12 : 0,
        department_ids: [], job_ids: [], work_location_ids: [], country_ids: [],
        employee_types: [], safety_groups: [], include_contractors: true,
        auto_assign: true, counts_for_probation: false, note: "",
    };
}

function blankFilters() {
    return { department_id: 0, job_id: 0, work_location_id: 0, country_code: "",
             safety_group: "", requirement_id: 0, state: "", q: "", page: 1, pack: "" };
}

export class PbRequiredLens extends Component {
    static template = "pb_training.PbRequiredLens";
    static props = {
        embedded: { type: Boolean, optional: true },
        startTab: { type: String, optional: true },
        startState: { type: String, optional: true },
        startPack: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        const filters = blankFilters();
        filters.state = STATE_KEYS.includes(this.props.startState) ? this.props.startState : "";
        this.state = useState({
            tab: TABS.includes(this.props.startTab) ? this.props.startTab : "matrix",
            loaded: false, failed: false, busy: false,
            m: { rows: [], columns: [], summary: {}, lists: {} },
            r: { rows: [], legacy_rules: [], legacy_schedules: [], lists: {} },
            filters,
            rulePack: this.props.startPack || "",
            picked: {},
            pop: null,
            groupPick: "",
            drawer: false,
            form: blankForm(),
            saving: false,
            acting: "",
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        this.state.failed = false;
        this.state.busy = true;
        try {
            if (this.state.tab === "matrix") {
                this.state.m = await this.orm.call("pb.training", "matrix", [this.state.filters]);
            } else {
                this.state.r = await this.orm.call("pb.training", "required_rules", [{ pack: this.state.rulePack }]);
            }
        } catch (e) {
            console.warn("pb_training: the required training could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
            this.state.busy = false;
        }
    }

    async retry() { this.state.loaded = false; await this.load(); }

    async setTab(tab) {
        if (this.state.tab === tab) { return; }
        this.state.tab = tab;
        this.state.pop = null;
        this.state.loaded = false;
        await this.load();
    }

    get m() { return this.state.m || {}; }
    get r() { return this.state.r || {}; }
    get allowed() {
        const d = this.state.tab === "matrix" ? this.m : this.r;
        return d.allowed !== false;
    }
    get canManage() { return !!(this.m.can_manage || this.r.can_manage); }
    get lists() { return (this.state.tab === "matrix" ? this.m.lists : this.r.lists) || {}; }

    tabLabel(t) {
        return { matrix: _t("Matrix"), rules: _t("Rules"), day_one: _t("Day one"),
                 recurring: _t("Comes round again") }[t];
    }
    tabIcon(t) {
        return { matrix: "layoutGrid", rules: "listChecks", day_one: "sunrise", recurring: "repeat" }[t];
    }
    get tabs() { return TABS; }

    // ------------------------------------------------------------- matrix
    get summary() { return this.m.summary || {}; }
    get columns() { return this.m.columns || []; }
    get rows() { return this.m.rows || []; }

    get gridStyle() {
        return `grid-template-columns: 40px 232px repeat(${Math.max(this.columns.length, 1)}, minmax(128px, 1fr));`;
    }

    get ringDash() {
        const pct = this.summary.percent;
        const c = 2 * Math.PI * 18;
        const on = pct === null || pct === undefined ? 0 : (c * pct) / 100;
        return `${on} ${c}`;
    }

    get ringClass() {
        const pct = this.summary.percent;
        if (pct === null || pct === undefined) { return "is-zero"; }
        if (pct >= 95) { return "is-good"; }
        if (pct >= 80) { return "is-warn"; }
        return "is-bad";
    }

    stateLabel(key) {
        return { missing: _t("Missing"), expiring: _t("Expiring"), in_progress: _t("Under way"),
                 not_due: _t("Not due yet") }[key];
    }

    stateChipClass(key) {
        const n = this.summary[key] || 0;
        return { "is-on": this.state.filters.state === key, "is-zero": !n,
                 [`is-${key}`]: !!n };
    }

    async setState(key) {
        this.state.filters.state = this.state.filters.state === key ? "" : key;
        this.state.filters.page = 1;
        await this.load();
    }

    onSearch(ev) {
        this.state.filters.q = ev.target.value;
        clearTimeout(this._t);
        this._t = setTimeout(() => { this.state.filters.page = 1; this.load(); }, 250);
    }

    async onFilter(field, ev, numeric = true) {
        this.state.filters[field] = numeric ? (Number(ev.target.value) || 0) : ev.target.value;
        this.state.filters.page = 1;
        await this.load();
    }

    get anyFilter() {
        const f = this.state.filters;
        return !!(f.department_id || f.job_id || f.work_location_id || f.country_code
                  || f.safety_group || f.requirement_id || f.state || f.q);
    }

    async clearFilters() {
        this.state.filters = blankFilters();
        await this.load();
    }

    async goPage(delta) {
        const next = (this.m.page || 1) + delta;
        if (next < 1 || next > (this.m.pages || 1)) { return; }
        this.state.filters.page = next;
        await this.load();
    }

    get shownWords() {
        const shown = this.rows.length;
        const total = this.m.total || 0;
        if (this.m.truncated) {
            return _t("Showing %s of %s people — narrow it by department or site.", shown, total);
        }
        return total === 1 ? _t("1 person") : _t("%s people", total);
    }

    cell(row, col) { return (row.cells || {})[String(col.id)] || null; }

    cellClass(row, col) {
        const c = this.cell(row, col);
        const st = c ? c.state : "exempt";
        const open = this.state.pop && this.state.pop.emp === row.employee_id && this.state.pop.req === col.id;
        return { [`is-${st}`]: true, "is-open": !!open,
                 "is-act": ["missing", "expiring", "not_due"].includes(st) && this.m.can_write && col.can_assign };
    }

    cellIcon(row, col) {
        const c = this.cell(row, col);
        return { valid: "checkCircle", expiring: "hourglass", missing: "triangleAlert",
                 in_progress: "clock", not_due: "circle", unlinked: "link" }[c ? c.state : ""] || "";
    }

    onCell(row, col) {
        const c = this.cell(row, col);
        if (!c || !["missing", "expiring", "not_due"].includes(c.state) || !this.m.can_write) { return; }
        const same = this.state.pop && this.state.pop.emp === row.employee_id && this.state.pop.req === col.id;
        this.state.pop = same ? null : { emp: row.employee_id, req: col.id, name: row.name, col };
    }

    closePop() { this.state.pop = null; }

    popWords(col) {
        if (!col.can_assign) { return _t("No course is linked to this rule yet — link one in Rules."); }
        return _t("Puts them on the course with the rule's own due date.");
    }

    async assignCell() {
        const pop = this.state.pop;
        if (!pop) { return; }
        await this.act("assign_from_cell", { requirement_id: pop.req, employee_id: pop.emp }, `cell-${pop.req}-${pop.emp}`);
        this.state.pop = null;
    }

    // ------------------------------------------------------------- picking
    isPicked(row) { return !!this.state.picked[row.employee_id]; }
    togglePick(row) {
        if (this.state.picked[row.employee_id]) { delete this.state.picked[row.employee_id]; } else { this.state.picked[row.employee_id] = true; }
    }
    get pickedIds() { return Object.keys(this.state.picked).map(Number); }
    get allPicked() { return this.rows.length > 0 && this.rows.every((r) => this.state.picked[r.employee_id]); }
    toggleAll() {
        if (this.allPicked) { this.state.picked = {}; return; }
        for (const r of this.rows) { this.state.picked[r.employee_id] = true; }
    }
    clearPicked() { this.state.picked = {}; }
    get pickedWords() {
        const n = this.pickedIds.length;
        return n === 1 ? _t("1 person picked") : _t("%s people picked", n);
    }

    async bulkAssign() {
        await this.act("bulk_assign_required", { employee_ids: this.pickedIds,
            requirement_id: this.state.filters.requirement_id || false }, "bulk");
        this.state.picked = {};
    }

    async setGroup() {
        await this.act("set_safety_group", { employee_ids: this.pickedIds, group: this.state.groupPick }, "group");
        this.state.picked = {};
    }

    // ------------------------------------------------------------- exports
    async download(method) {
        this.state.acting = method;
        try {
            const res = await this.orm.call("pb.training", method, [this.state.filters]);
            if (!res || !res.file_b64) { return; }
            const a = document.createElement("a");
            a.href = `data:${res.mimetype};base64,${res.file_b64}`;
            a.download = res.filename || "required-training";
            document.body.appendChild(a);
            a.click();
            a.remove();
            this.notif.add(_t("The file is in your downloads."), { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.acting = "";
        }
    }

    // ------------------------------------------------------------- verbs
    async act(verb, payload, key = verb) {
        this.state.acting = key;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.message) { this.notif.add(res.message, { type: res.type || "success" }); }
            await this.load();
            return res;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.acting = "";
        }
    }

    openSettings() { this.action.doAction(SETTINGS_XMLID); }

    // ------------------------------------------------------------- rules tabs
    get ruleRows() {
        const rows = this.r.rows || [];
        if (this.state.tab === "day_one") { return rows.filter((x) => x.kind === "day_one"); }
        if (this.state.tab === "recurring") { return rows.filter((x) => x.kind === "recurring"); }
        return rows;
    }

    get packChips() {
        const seen = {};
        for (const row of this.r.rows || []) {
            if (row.pack && !seen[row.pack]) { seen[row.pack] = row.pack_word; }
        }
        return Object.entries(seen).map(([key, label]) => ({ key, label }));
    }

    async setPack(key) {
        this.state.rulePack = this.state.rulePack === key ? "" : key;
        await this.load();
    }

    toggleAuto(row) { return this.act("toggle_requirement_auto", { requirement_id: row.id }, `auto-${row.id}`); }
    toggleActive(row) { return this.act("archive_requirement", { requirement_id: row.id }, `on-${row.id}`); }

    openColumn(col) {
        if (!this.canManage) { return; }
        const row = (this.r.rows || []).find((x) => x.id === col.id);
        if (row) { this.editRule(row); return; }
        this.orm.call("pb.training", "required_rules", [{}]).then((r) => {
            this.state.r = r;
            const found = (r.rows || []).find((x) => x.id === col.id);
            if (found) { this.editRule(found); }
        });
    }

    // ------------------------------------------------------------- drawer
    newRule() {
        const kind = this.state.tab === "day_one" ? "day_one" : (this.state.tab === "recurring" ? "recurring" : "always");
        this.state.form = blankForm(kind);
        this.state.drawer = true;
    }

    editRule(row) {
        this.state.form = Object.assign(blankForm(row.kind), JSON.parse(JSON.stringify(row.values)));
        this.state.drawer = true;
    }

    closeDrawer() { this.state.drawer = false; }

    setField(field, ev, kind = "text") {
        let value = ev.target.value;
        if (kind === "int") { value = Number(value) || 0; }
        if (kind === "bool") { value = !!ev.target.checked; }
        this.state.form[field] = value;
    }

    addTo(field, ev) {
        const id = Number(ev.target.value) || 0;
        if (id && !this.state.form[field].includes(id)) { this.state.form[field].push(id); }
        ev.target.value = "0";
    }

    removeFrom(field, id) {
        this.state.form[field] = this.state.form[field].filter((x) => x !== id);
    }

    toggleIn(field, key) {
        const list = this.state.form[field];
        const at = list.indexOf(key);
        if (at >= 0) { list.splice(at, 1); } else { list.push(key); }
    }

    nameOf(listKey, id) {
        const row = (this.lists[listKey] || []).find((x) => x.id === id);
        return row ? row.name : "";
    }

    get canSave() {
        const f = this.state.form;
        if (!f.name.trim() || this.state.saving) { return false; }
        if (f.target === "course" && !f.channel_id) { return false; }
        if ((f.target === "certificate" || f.target === "licence") && !f.name_pattern.trim() && !f.channel_id) { return false; }
        if (f.target === "hours" && !Number(f.hours_required)) { return false; }
        if (f.target === "path" && !f.path_id) { return false; }
        return true;
    }

    async save() {
        if (!this.canSave) { return; }
        this.state.saving = true;
        try {
            const res = await this.orm.call("pb.training", "act", ["save_requirement", this.state.form]);
            this.notif.add((res && res.message) || _t("Saved."), { type: "success" });
            this.state.drawer = false;
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    openMatrixFor(row) {
        this.state.filters = blankFilters();
        this.state.filters.requirement_id = row.id;
        this.setTab("matrix");
    }
}
