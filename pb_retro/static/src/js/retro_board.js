/** @odoo-module **/
/**
 * `pb_retro_board` — "Past-month re-work": a lens of the Payroll hub (and its
 * own page from the palette).
 *
 * THE HERO is the answer strip once a re-work is worked out: "Take-home
 * +4,200,000 across 3 people · Income tax +310,000 · Employer cost +5,100,000",
 * with right under it the plain promise: nothing has been paid or changed.
 *
 * The working-out runs in chunks of 40 payslips (the pay run driver's chunk)
 * with a progress bar; the browser only asks, the server decides which
 * payslips a re-work covers.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`): a NEW markup()
 *      per render re-inserts the SVG on every patch (OWL markup flicker).
 * R3 — every sentence a person reads is a `_t()` literal, a template text, or
 *      comes from the server already translated.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const MODEL = "pb.retro.board";
const PAGE = 40;
const GLANCE_FILTERS = {
    draft: { where: ["draft"] },
    done: { where: ["done"] },
    closed: { where: ["closed"] },
};

function blankWizard() {
    return {
        step: 1, id: 0, busy: false, loading: true,
        schemes: [], configId: 0, monthFrom: "", monthTo: "",
        people: "all", picked: {}, pickedNames: {}, peopleRows: [], peopleMore: 0,
        peopleTerm: "", peopleLoading: false,
        preview: null, previewBusy: false,
        excluded: {}, whatifs: [], slipCache: {},
        reason: "",
    };
}

export class PbRetroBoard extends Component {
    static template = "pb_retro.PbRetroBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    get searchLabel() { return _t("Find a re-work by its reason or pay scheme…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false, allowed: true, why: "", kpis: {}, total: 0, hasUpdates: false,
            rows: [], listTotal: 0, listLoaded: false, listError: false, loadingMore: false,
            view: "list", result: null, resultBusy: false,
            people: { rows: [], total: 0, show: "changed", search: "", loading: false },
            open: {},
            work: null,
            wiz: null,
            issuesOpen: false,
        });
        this.kit = useFilterKit({
            model: MODEL,
            noun: _t("re-works"),
            onChange: () => this.loadPage(),
        });
        this._peopleSeq = 0;
        this._searchTimer = null;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => {
            await this.load();
            if (!this.state.allowed) { this.state.listLoaded = true; }
        });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }

    // ------------------------------------------------------------ the board
    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false, why: d.why || "",
                kpis: d.kpis || {}, total: d.total || 0, hasUpdates: !!d.has_updates,
            });
        } catch (e) {
            console.warn("pb_retro: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The re-works could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) { this.state.listLoaded = true; return; }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call(MODEL, "get_page", [], this.kit.kw({
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            }));
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_retro: the re-works could not load", e);
            if (!more) { this.state.listError = true; this.state.listLoaded = true; }
            this.notif.add(_t("The re-works could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() { this.state.listError = false; this.state.listLoaded = false; this.kit.refresh(); }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "draft", n: k.draft || 0, label: _t("draft"), tone: tone(k.draft, "amber"), run: pick("draft") },
            { key: "done", n: k.done || 0, label: _t("worked out"), tone: tone(k.done, "blue"), run: pick("done") },
            { key: "closed", n: k.closed || 0, label: _t("closed"), tone: "", run: pick("closed") },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ------------------------------------------------------------ the result
    async openReview(id) {
        this.state.view = "result";
        this.state.resultBusy = true;
        this.state.issuesOpen = false;
        this.state.open = {};
        try {
            this.state.result = await this.orm.call(MODEL, "get_review", [id]);
            this.state.people = { rows: [], total: 0, show: "changed", search: "", loading: false };
            if (["done", "closed"].includes(this.state.result.state)) {
                const hasChanges = (this.state.result.status.changed || 0) + (this.state.result.status.drift || 0);
                this.state.people.show = hasChanges ? "changed" : "issues";
                await this.loadPeople();
            }
        } catch (e) {
            this.notif.add(this._msg(e, _t("This re-work could not be opened.")), { type: "danger" });
            this.backToList();
        } finally {
            this.state.resultBusy = false;
        }
    }
    backToList() {
        this.state.view = "list";
        this.state.result = null;
        this.refresh();
    }
    async loadPeople({ more = false } = {}) {
        const r = this.state.result;
        if (!r) { return; }
        const P = this.state.people;
        const seq = ++this._peopleSeq;
        P.loading = true;
        try {
            const d = await this.orm.call(MODEL, "get_people", [r.id], {
                offset: more ? P.rows.length : 0, limit: 30, show: P.show, search: P.search,
            });
            if (seq !== this._peopleSeq) { return; }
            P.rows = more ? [...P.rows, ...d.people] : d.people;
            P.total = d.total;
            if (!more && P.rows.length === 1) { this.state.open[P.rows[0].key] = true; }
        } catch (e) {
            if (seq === this._peopleSeq) {
                this.notif.add(this._msg(e, _t("The people could not load.")), { type: "warning" });
            }
        } finally {
            if (seq === this._peopleSeq) { P.loading = false; }
        }
    }
    setShow(show) {
        if (this.state.people.show === show) { return; }
        this.state.people.show = show;
        this.loadPeople();
    }
    onPeopleSearch(ev) {
        this.state.people.search = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadPeople(), 250);
    }
    toggleIssues() { this.state.issuesOpen = !this.state.issuesOpen; }
    hasWhatifPerson(row) { return this.whatifPeople.some((p) => p.id === row.employee_id); }
    togglePerson(p) { this.state.open[p.key] = !this.state.open[p.key]; }
    isOpen(p) { return !!this.state.open[p.key]; }
    expandAll(on) {
        for (const p of this.state.people.rows) { this.state.open[p.key] = on; }
    }
    get peopleHasMore() { return this.state.people.rows.length < this.state.people.total; }

    async openPayslip(payslipId) {
        const r = this.state.result;
        if (!r || !payslipId) { return; }
        try {
            const action = await this.orm.call(MODEL, "open_payslip", [r.id, payslipId]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The payslip could not be opened.")), { type: "danger" });
        }
    }
    async openUpdates() {
        const r = this.state.result;
        if (!r || !r.updates_xmlid) { return; }
        try {
            await this.action.doAction(r.updates_xmlid);
        } catch (e) {
            this.notif.add(this._msg(e, _t("Updates could not be opened.")), { type: "danger" });
        }
    }

    async move(verb) {
        const r = this.state.result;
        if (!r) { return; }
        try {
            const res = await this.orm.call(MODEL, "move", [r.id, verb]);
            this.notif.add(res.msg || _t("Done."), { type: "success" });
            await this.openReview(r.id);
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        }
    }

    async exportXlsx() {
        const r = this.state.result;
        if (!r) { return; }
        try {
            const res = await this.orm.call(MODEL, "export_xlsx", [r.id]);
            if (!res || !res.ok) {
                this.notif.add((res && res.msg) || _t("The Excel file could not be made."), { type: "warning" });
                return;
            }
            const bin = atob(res.file_b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
            const url = URL.createObjectURL(new Blob([bytes], { type: res.mimetype }));
            const a = document.createElement("a");
            a.href = url;
            a.download = res.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The Excel file could not be made.")), { type: "danger" });
        }
    }

    // ------------------------------------------------------------ working it out
    async workOut(reviewId) {
        if (this.state.work) { return; }
        const started = Date.now();
        this.state.work = { total: 0, done: 0, phase: "start", id: reviewId };
        try {
            const plan = await this.orm.call(MODEL, "work_start", [reviewId]);
            const ids = plan.slip_ids || [];
            const chunk = plan.chunk || 40;
            this.state.work.total = ids.length;
            this.state.work.phase = "chunks";
            for (let i = 0; i < ids.length; i += chunk) {
                const res = await this.orm.call(MODEL, "work_chunk", [reviewId, ids.slice(i, i + chunk)]);
                this.state.work.done = Math.min(ids.length, i + chunk);
                if (res && res.done === 0 && ids.length) { /* already done in another tab */ }
            }
            this.state.work.phase = "finish";
            await this.orm.call(MODEL, "work_finish", [reviewId, Date.now() - started]);
            this.state.work = null;
            this.notif.add(_t("Worked out. Nothing has been paid or changed."), { type: "success" });
            await this.openReview(reviewId);
        } catch (e) {
            this.state.work = null;
            this.notif.add(this._msg(e, _t("The re-work could not be worked out.")), { type: "danger" });
            if (this.state.view === "result") { await this.openReview(reviewId); }
        }
    }
    get workPct() {
        const w = this.state.work;
        if (!w || !w.total) { return w && w.phase === "finish" ? 100 : 4; }
        return Math.max(4, Math.round((100 * w.done) / w.total));
    }

    // ------------------------------------------------------------ the wizard
    async newReview() {
        this.state.wiz = blankWizard();
        await this._loadSchemes();
    }
    async editReview() {
        const r = this.state.result;
        if (!r) { return; }
        const w = blankWizard();
        Object.assign(w, {
            id: r.id, configId: r.config_id, monthFrom: r.month_from, monthTo: r.month_to,
            people: r.people, reason: r.reason, step: 4,
        });
        for (const e of r.employees || []) { w.picked[e.id] = true; w.pickedNames[e.id] = e.name; }
        for (const id of r.excluded_change_ids || []) { w.excluded[id] = true; }
        w.whatifs = (r.whatifs || []).map((x, i) => ({
            key: "w" + i + "-" + x.id, employee_id: x.employee_id, person: x.person,
            payslip_id: x.payslip_id, code: x.code, value: String(x.value), note: x.note,
        }));
        this.state.wiz = w;
        await this._loadSchemes();
        await this.refreshPreview();
        for (const x of w.whatifs) { await this._slipsFor(x.employee_id); }
    }
    closeWizard() { this.state.wiz = null; }
    async _loadSchemes() {
        const w = this.state.wiz;
        try {
            const d = await this.orm.call(MODEL, "new_options", []);
            w.schemes = d.schemes || [];
            w.monthCap = d.month_cap || 12;
            w.peopleCap = d.people_cap || 500;
            if (!w.configId && w.schemes.length === 1) { w.configId = w.schemes[0].id; }
        } catch (e) {
            this.notif.add(this._msg(e, _t("The pay schemes could not be read.")), { type: "danger" });
        } finally {
            w.loading = false;
        }
    }
    get wizScheme() {
        const w = this.state.wiz;
        return w ? (w.schemes.find((s) => s.id === w.configId) || null) : null;
    }
    pickScheme(s) {
        const w = this.state.wiz;
        if (w.configId !== s.id) {
            w.configId = s.id;
            w.monthFrom = ""; w.monthTo = "";
            w.picked = {}; w.pickedNames = {}; w.whatifs = []; w.excluded = {}; w.preview = null;
            w.slipCache = {};
        }
    }
    // months — click the first month, then the last; a third click starts again
    pickMonth(m) {
        const w = this.state.wiz;
        if (!w.monthFrom || (w.monthFrom && w.monthTo && w.monthFrom !== w.monthTo)) {
            w.monthFrom = m.month; w.monthTo = m.month;
        } else if (m.month < w.monthFrom) {
            w.monthTo = w.monthFrom; w.monthFrom = m.month;
        } else {
            w.monthTo = m.month;
        }
        w.preview = null;
        w.slipCache = {};
    }
    monthState(m) {
        const w = this.state.wiz;
        if (!w.monthFrom) { return ""; }
        if (m.month === w.monthFrom || m.month === w.monthTo) { return "is-end"; }
        if (m.month > w.monthFrom && m.month < w.monthTo) { return "is-in"; }
        return "";
    }
    get monthCount() {
        const w = this.state.wiz;
        if (!w || !w.monthFrom) { return 0; }
        const [y1, m1] = w.monthFrom.split("-").map(Number);
        const [y2, m2] = w.monthTo.split("-").map(Number);
        return (y2 - y1) * 12 + (m2 - m1) + 1;
    }
    get monthsLabel() {
        const w = this.state.wiz;
        const sc = this.wizScheme;
        if (!w || !sc || !w.monthFrom) { return ""; }
        const a = sc.months.find((m) => m.month === w.monthFrom);
        const b = sc.months.find((m) => m.month === w.monthTo);
        if (!a || !b) { return ""; }
        return a.month === b.month ? a.label : a.label + " – " + b.label;
    }
    _vals() {
        const w = this.state.wiz;
        return {
            id: w.id || 0, config_id: w.configId, month_from: w.monthFrom, month_to: w.monthTo,
            people: w.people,
            employee_ids: Object.keys(w.picked).filter((k) => w.picked[k]).map(Number),
            excluded_change_ids: Object.keys(w.excluded).filter((k) => w.excluded[k]).map(Number),
            reason: w.reason,
            whatifs: w.whatifs.filter((x) => x.payslip_id && x.code).map((x) => ({
                payslip_id: x.payslip_id, code: x.code, value: x.value, note: x.note,
            })),
        };
    }
    async refreshPreview() {
        const w = this.state.wiz;
        if (!w || !w.configId || !w.monthFrom) { return; }
        w.previewBusy = true;
        try {
            w.preview = await this.orm.call(MODEL, "scope_preview", [this._vals()]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("What the re-work covers could not be worked out.")), { type: "danger" });
        } finally {
            w.previewBusy = false;
        }
    }
    async loadPeopleOptions() {
        const w = this.state.wiz;
        w.peopleLoading = true;
        try {
            const d = await this.orm.call(MODEL, "people_options", [this._vals(), w.peopleTerm || ""]);
            w.peopleRows = d.rows || [];
            w.peopleMore = d.more || 0;
            for (const r of w.peopleRows) { w.pickedNames[r.id] = r.name; }
        } catch (e) {
            this.notif.add(this._msg(e, _t("The people could not be read.")), { type: "danger" });
        } finally {
            w.peopleLoading = false;
        }
    }
    onPeopleTerm(ev) {
        this.state.wiz.peopleTerm = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadPeopleOptions(), 250);
    }
    setPeopleMode(mode) {
        const w = this.state.wiz;
        w.people = mode;
        w.preview = null;
        if (mode === "picked" && !w.peopleRows.length) { this.loadPeopleOptions(); }
    }
    togglePick(row) {
        const w = this.state.wiz;
        w.picked[row.id] = !w.picked[row.id];
        w.preview = null;
    }
    pickAllShown(on) {
        const w = this.state.wiz;
        for (const r of w.peopleRows) { w.picked[r.id] = on; }
        w.preview = null;
    }
    get pickedCount() {
        const w = this.state.wiz;
        return w ? Object.keys(w.picked).filter((k) => w.picked[k]).length : 0;
    }
    get canNext() {
        const w = this.state.wiz;
        if (!w) { return false; }
        if (w.step === 1) { return !!w.configId; }
        if (w.step === 2) { return !!w.monthFrom && this.monthCount <= (w.monthCap || 12); }
        if (w.step === 3) { return w.people === "all" || this.pickedCount > 0; }
        return true;
    }
    async nextStep() {
        const w = this.state.wiz;
        if (!this.canNext) { return; }
        if (w.step === 2 && w.people === "picked" && !w.peopleRows.length) { this.loadPeopleOptions(); }
        w.step = Math.min(4, w.step + 1);
        if (w.step === 3 || w.step === 4) { await this.refreshPreview(); }
    }
    prevStep() { const w = this.state.wiz; w.step = Math.max(1, w.step - 1); }
    goStep(n) {
        const w = this.state.wiz;
        if (n < w.step) { w.step = n; return; }
        if (n === w.step + 1) { this.nextStep(); }
    }
    get wizSteps() {
        const w = this.state.wiz;
        return [
            { n: 1, label: _t("Pay scheme") },
            { n: 2, label: _t("Months") },
            { n: 3, label: _t("People") },
            { n: 4, label: _t("What changed") },
        ].map((s) => ({ ...s, on: w && w.step === s.n, done: w && w.step > s.n }));
    }
    toggleChange(ch) {
        const w = this.state.wiz;
        w.excluded[ch.id] = !w.excluded[ch.id];
    }
    isExcluded(ch) { return !!this.state.wiz.excluded[ch.id]; }

    // the what-if grid
    get whatifPeople() {
        const w = this.state.wiz;
        if (w.people === "picked") {
            return Object.keys(w.picked).filter((k) => w.picked[k])
                .map((k) => ({ id: Number(k), name: w.pickedNames[k] || "" }))
                .sort((a, b) => a.name.localeCompare(b.name));
        }
        return w.peopleRows;
    }
    async addWhatif() {
        const w = this.state.wiz;
        if (!w.peopleRows.length) { await this.loadPeopleOptions(); }
        const people = this.whatifPeople;
        const first = people[0];
        const items = (w.preview && w.preview.items) || [];
        const row = {
            key: "n" + Date.now() + Math.random().toString(36).slice(2, 6),
            employee_id: first ? first.id : 0, person: first ? first.name : "",
            payslip_id: 0, code: items.length ? items[0].code : "", value: "", note: "",
        };
        w.whatifs.push(row);
        if (row.employee_id) { await this._slipsFor(row.employee_id, row); }
    }
    removeWhatif(row) {
        const w = this.state.wiz;
        w.whatifs = w.whatifs.filter((x) => x.key !== row.key);
    }
    async _slipsFor(employeeId, row = null) {
        const w = this.state.wiz;
        if (!employeeId) { return []; }
        if (!w.slipCache[employeeId]) {
            try {
                w.slipCache[employeeId] = await this.orm.call(MODEL, "slip_options", [this._vals(), employeeId]);
            } catch (e) {
                w.slipCache[employeeId] = [];
            }
        }
        if (row && !row.payslip_id && w.slipCache[employeeId].length) {
            row.payslip_id = w.slipCache[employeeId][0].id;
        }
        return w.slipCache[employeeId];
    }
    slipsOf(row) { return this.state.wiz.slipCache[row.employee_id] || []; }
    async onWhatifPerson(row, ev) {
        row.employee_id = Number(ev.target.value) || 0;
        row.payslip_id = 0;
        await this._slipsFor(row.employee_id, row);
    }
    onWhatif(row, field, ev) {
        const v = ev.target.value;
        row[field] = field === "payslip_id" ? Number(v) || 0 : v;
    }
    wasOf(row) {
        const slip = this.slipsOf(row).find((s) => s.id === row.payslip_id);
        if (!slip || !row.code) { return ""; }
        return slip.labels[row.code] || "0";
    }
    onWhatifKey(row, ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.addWhatif();
        }
    }
    onReason(ev) { this.state.wiz.reason = ev.target.value; }
    get whatifProblem() {
        const w = this.state.wiz;
        for (const x of w.whatifs) {
            if (!x.payslip_id || !x.code) { return _t("Pick the person, month and pay item of every what-if value."); }
            if (x.value === "" || isNaN(Number(x.value))) { return _t("Type a number for every what-if value."); }
            if (!(x.note || "").trim()) { return _t("Every what-if value needs a note: say where the new figure comes from."); }
        }
        return "";
    }
    get changesIncluded() {
        const w = this.state.wiz;
        const changes = (w.preview && w.preview.changes) || [];
        return changes.filter((c) => !c.paid_back && !w.excluded[c.id]).length;
    }
    async saveAndWork() {
        const w = this.state.wiz;
        if (!(w.reason || "").trim()) {
            this.notif.add(_t("Say why this re-work is needed, in a few words."), { type: "warning" });
            return;
        }
        if (this.whatifProblem) {
            this.notif.add(this.whatifProblem, { type: "warning" });
            return;
        }
        w.busy = true;
        try {
            const res = await this.orm.call(MODEL, "save_review", [this._vals()]);
            this.state.wiz = null;
            this.state.view = "result";
            await this.openReview(res.id);
            await this.workOut(res.id);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The re-work could not be saved.")), { type: "danger" });
        } finally {
            if (this.state.wiz) { w.busy = false; }
        }
    }

    // ------------------------------------------------------------ plumbing
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.wiz) { this.closeWizard(); return; }
        if (this.state.view === "result" && !this.state.work) { this.backToList(); }
    }
    signClass(sign) { return sign > 0 ? "is-up" : sign < 0 ? "is-down" : "is-zero"; }
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_retro_board", PbRetroBoard);
