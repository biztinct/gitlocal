/** @odoo-module **/
/**
 * `pb_job_change` — "Change job": the board of every job change, the guided
 * flow for one person and one change's page, in one client action.
 *
 *   params.employee_id (+ params.vals)  open the flow for that person,
 *                                       prefilled (cross-step contract C-1);
 *   params.change_id                    open that change's page;
 *   params.start                        open the person picker;
 *   nothing                             the board.
 *
 * The server decides everything that matters — who signs it off, whether the
 * pay scheme changes, whether the start date is in a month already paid —
 * and the screen prints its sentences. Nothing is written until Send.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`).
 * R3 — every sentence is a `_t()` literal, template text, or a server answer.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const MODEL = "pb.job.change.board";
const PAGE = 40;
const GLANCE_FILTERS = {
    pending: { where: ["pending"] },
    scheduled: { where: ["scheduled"] },
    draft: { where: ["draft"] },
    applied: { where: ["applied"] },
};

function errText(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback;
}

export class PbJobChange extends Component {
    static template = "pb_job_change.PbJobChange";
    static components = { PbFilterLayout };
    static props = ["*"];

    get searchLabel() { return _t("Find a job change by person or reference…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        const params = (this.props.action && this.props.action.params) || {};
        this.state = useState({
            view: "board",
            loaded: false, allowed: true, why: "", kpis: {}, total: 0, canPay: false,
            rows: [], listTotal: 0, listLoaded: false, listError: false, loadingMore: false,
            pick: { term: "", rows: [], loading: false },
            flow: null,
            detail: null,
        });
        this.kit = useFilterKit({
            model: MODEL,
            noun: _t("job changes"),
            onChange: () => this.loadPage(),
        });
        this._timer = null;
        this._previewSeq = 0;
        onWillStart(async () => {
            await this.load();
            if (!this.state.allowed) { this.state.listLoaded = true; return; }
            if (params.change_id) {
                await this.openChange(params.change_id);
            } else if (params.employee_id) {
                await this.openFlow(params.employee_id, 0, params.vals || {});
            } else if (params.start) {
                await this.startPick();
            }
        });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }

    // ============================================================ the board
    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false, why: d.why || "",
                kpis: d.kpis || {}, total: d.total || 0, canPay: !!d.can_pay,
            });
        } catch (e) {
            console.warn("pb_job_change: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The job changes could not be read just now.");
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
            console.error("pb_job_change: the list could not load", e);
            if (!more) { this.state.listError = true; this.state.listLoaded = true; }
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
            { key: "pending", n: k.pending || 0, label: _t("waiting for approval"), tone: tone(k.pending, "amber"), run: pick("pending") },
            { key: "scheduled", n: k.scheduled || 0, label: _t("start later"), tone: tone(k.scheduled, "blue"), run: pick("scheduled") },
            { key: "draft", n: k.draft || 0, label: _t("being prepared"), tone: "", run: pick("draft") },
            { key: "applied", n: k.applied || 0, label: _t("done"), tone: "", run: pick("applied") },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    async backToBoard() {
        this.state.view = "board";
        this.state.flow = null;
        this.state.detail = null;
        await this.refresh();
    }

    // ============================================================ picking a person
    async startPick() {
        this.state.view = "pick";
        this.state.pick = { term: "", rows: [], loading: true };
        await this.searchPeople("");
    }
    onPickTerm(ev) {
        const term = ev.target.value;
        this.state.pick.term = term;
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.searchPeople(term), 250);
    }
    async searchPeople(term) {
        this.state.pick.loading = true;
        try {
            this.state.pick.rows = await this.orm.call(MODEL, "search_people", [term]);
        } catch (e) {
            this.notif.add(errText(e, _t("People could not be read just now.")), { type: "warning" });
        } finally {
            this.state.pick.loading = false;
        }
    }

    // ============================================================ the flow
    async openFlow(employeeId, changeId = 0, vals = {}) {
        let d;
        try {
            d = await this.orm.call(MODEL, "get_flow", [employeeId, changeId, vals]);
        } catch (e) {
            this.notif.add(errText(e, _t("This person could not be opened.")), { type: "danger" });
            return;
        }
        const draft = d.draft || {};
        const sections = {
            job: !!(draft.new_job_id || draft.new_job_title),
            team: !!(draft.new_department_id || draft.new_parent_id || draft.new_work_location_id
                     || draft.new_resource_calendar_id || draft.new_company_id),
            pay: !!draft.change_pay,
        };
        if (!sections.job && !sections.team && !sections.pay) {
            sections.job = draft.reason_kind !== "pay" && draft.reason_kind !== "transfer";
            sections.team = draft.reason_kind === "transfer";
            sections.pay = draft.reason_kind === "pay" && d.can_pay;
        }
        const lines = (d.lines || []).map((l) => {
            const typed = (draft.lines || []).find((x) => x.code === l.code);
            return { code: l.code, name: l.name, old: l.amount, new: typed ? typed.new : l.amount };
        });
        for (const x of (draft.lines || [])) {
            if (!lines.find((l) => l.code === x.code)) {
                lines.push({ code: x.code, name: x.name || x.code, old: 0, new: x.new });
            }
        }
        this.state.flow = {
            d, step: 1, busy: false, changeId: d.change_id || 0,
            sections,
            draft: {
                reason_kind: draft.reason_kind || "promotion",
                reason: draft.reason || "",
                effective_date: draft.effective_date || d.today,
                new_job_id: draft.new_job_id || 0,
                new_job_title: draft.new_job_title || "",
                new_department_id: draft.new_department_id || 0,
                new_parent_id: draft.new_parent_id || 0,
                new_parent: draft.new_parent || "",
                new_work_location_id: draft.new_work_location_id || 0,
                new_resource_calendar_id: draft.new_resource_calendar_id || 0,
                new_company_id: draft.new_company_id || 0,
                new_wage: draft.new_wage || (d.now.wage || 0),
                source: draft.source || "",
                source_ref: draft.source_ref || "",
            },
            lines,
            addCode: "",
            preview: null, previewBusy: false,
            mgr: { term: draft.new_parent || "", rows: [], open: false },
        };
        this.state.view = "flow";
        await this.runPreview();
    }

    get F() { return this.state.flow; }

    setKind(key) {
        const f = this.F;
        f.draft.reason_kind = key;
        if (key === "transfer" && !f.sections.team) { f.sections.team = true; }
        if (key === "pay" && f.d.can_pay && !f.sections.pay) { f.sections.pay = true; }
        if (key === "promotion" && !f.sections.job) { f.sections.job = true; }
        this.schedulePreview();
    }
    toggleSection(key) {
        const f = this.F;
        if (key === "pay" && !f.d.can_pay) { return; }
        f.sections[key] = !f.sections[key];
        this.schedulePreview();
    }
    get anySection() {
        const s = this.F.sections;
        return s.job || s.team || s.pay;
    }
    goStep(n) {
        if (n > 1 && !this.anySection) { return; }
        this.F.step = n;
    }

    onField(key, ev, number = false) {
        let v = ev.target.value;
        if (number) { v = v === "" ? 0 : parseInt(v, 10) || 0; }
        this.F.draft[key] = v;
        this.schedulePreview();
    }
    onMoney(key, ev) {
        const v = parseFloat(String(ev.target.value).replace(/[^0-9.\-]/g, ""));
        this.F.draft[key] = isNaN(v) ? 0 : v;
        this.schedulePreview();
    }
    onLine(line, ev) {
        const v = parseFloat(String(ev.target.value).replace(/[^0-9.\-]/g, ""));
        line.new = isNaN(v) ? 0 : v;
        this.schedulePreview();
    }
    onAddCode(ev) { this.F.addCode = ev.target.value; }
    addLine() {
        const f = this.F;
        const item = (f.d.addable || []).find((a) => a.code === f.addCode);
        if (!item || f.lines.find((l) => l.code === item.code)) { return; }
        f.lines.push({ code: item.code, name: item.name, old: 0, new: 0 });
        f.addCode = "";
    }
    get addableLeft() {
        const f = this.F;
        return (f.d.addable || []).filter((a) => !f.lines.find((l) => l.code === a.code));
    }

    // ---- the manager picker (search as you type)
    onMgrTerm(ev) {
        const f = this.F;
        f.mgr.term = ev.target.value;
        f.mgr.open = true;
        if (!f.mgr.term) { f.draft.new_parent_id = 0; f.draft.new_parent = ""; this.schedulePreview(); }
        clearTimeout(this._mgrTimer);
        this._mgrTimer = setTimeout(() => this.searchMgr(), 250);
    }
    focusMgr() { this.F.mgr.open = true; this.searchMgr(); }
    blurMgr() { setTimeout(() => { if (this.state.flow) { this.state.flow.mgr.open = false; } }, 150); }
    async searchMgr() {
        const f = this.F;
        try {
            f.mgr.rows = await this.orm.call(MODEL, "lookup",
                ["manager", f.mgr.term, f.draft.new_company_id || f.d.now.company_id]);
        } catch {
            f.mgr.rows = [];
        }
    }
    pickMgr(row) {
        const f = this.F;
        f.draft.new_parent_id = row.id;
        f.draft.new_parent = row.label;
        f.mgr.term = row.label;
        f.mgr.open = false;
        this.schedulePreview();
    }

    payload() {
        const f = this.F;
        const d = f.draft;
        const s = f.sections;
        return {
            employee_id: f.d.person.id,
            reason_kind: d.reason_kind,
            reason: d.reason,
            effective_date: d.effective_date,
            new_job_id: s.job ? d.new_job_id : 0,
            new_job_title: s.job ? d.new_job_title : "",
            new_department_id: s.team ? d.new_department_id : 0,
            new_parent_id: s.team ? d.new_parent_id : 0,
            new_work_location_id: s.team ? d.new_work_location_id : 0,
            new_resource_calendar_id: s.team ? d.new_resource_calendar_id : 0,
            new_company_id: s.team ? d.new_company_id : 0,
            change_pay: !!(s.pay && f.d.can_pay),
            new_wage: d.new_wage,
            lines: s.pay ? f.lines.map((l) => ({ code: l.code, name: l.name, old: l.old, new: l.new })) : [],
            source: d.source, source_ref: d.source_ref,
        };
    }

    schedulePreview() {
        clearTimeout(this._previewTimer);
        this._previewTimer = setTimeout(() => this.runPreview(), 350);
    }
    async runPreview() {
        const f = this.F;
        if (!f) { return; }
        const seq = ++this._previewSeq;
        f.previewBusy = true;
        try {
            const p = await this.orm.call(MODEL, "preview", [this.payload(), f.changeId]);
            if (seq === this._previewSeq && this.state.flow) { this.state.flow.preview = p; }
        } catch (e) {
            if (seq === this._previewSeq && this.state.flow) {
                this.state.flow.preview = { ok: false, problems: [errText(e, _t("This could not be checked just now."))], rows: [], steps: [], paid: [], reads: [] };
            }
        } finally {
            if (seq === this._previewSeq && this.state.flow) { this.state.flow.previewBusy = false; }
        }
    }

    get P() { return (this.F && this.F.preview) || { problems: [], rows: [], steps: [], paid: [], reads: [] }; }

    money(n) {
        const f = this.F;
        const dec = f ? f.d.now.decimals || 0 : 0;
        return Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec });
    }
    get rise() {
        const f = this.F;
        const old = f.d.now.wage || 0;
        if (!old || !f.draft.new_wage) { return ""; }
        const pct = ((f.draft.new_wage - old) / old) * 100;
        return (pct >= 0 ? "+" : "") + pct.toFixed(1) + "%";
    }

    async saveDraft() {
        const f = this.F;
        if (f.busy) { return; }
        f.busy = true;
        try {
            const res = await this.orm.call(MODEL, "save", [this.payload(), f.changeId]);
            f.changeId = res.id;
            this.notif.add(_t("Saved. It stays here until you send it."), { type: "success" });
        } catch (e) {
            this.notif.add(errText(e, _t("This could not be saved.")), { type: "danger" });
        } finally {
            f.busy = false;
        }
    }

    async send() {
        const f = this.F;
        if (f.busy || !this.P.ok) { return; }
        f.busy = true;
        try {
            const res = await this.orm.call(MODEL, "send", [this.payload(), f.changeId]);
            this.notif.add(res.message || _t("Sent."), { type: "success" });
            await this.openChange(res.id);
        } catch (e) {
            this.notif.add(errText(e, _t("This could not be sent.")), { type: "danger" });
            if (this.state.flow) { this.state.flow.busy = false; }
        }
    }

    // ============================================================ one change
    async openChange(id) {
        try {
            const d = await this.orm.call(MODEL, "get_change", [id]);
            this.state.detail = { d, busy: false };
            this.state.view = "detail";
            this.state.flow = null;
        } catch (e) {
            this.notif.add(errText(e, _t("This job change could not be opened.")), { type: "danger" });
        }
    }
    get D() { return (this.state.detail && this.state.detail.d) || {}; }

    async act(verb) {
        const det = this.state.detail;
        if (!det || det.busy) { return; }
        det.busy = true;
        try {
            const res = await this.orm.call(MODEL, "act", [det.d.id, verb]);
            if (verb === "rework") {
                await this.openRework(res.review_id);
                return;
            }
            if (res.msg || res.message) {
                this.notif.add(res.msg || res.message, { type: "success" });
            }
            await this.openChange(det.d.id);
        } catch (e) {
            this.notif.add(errText(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            if (this.state.detail) { this.state.detail.busy = false; }
        }
    }

    async openRework(reviewId) {
        if (!reviewId) { return; }
        await this.action.doAction({
            type: "ir.actions.client", tag: "pb_job_change_open_rework",
            name: _t("Past-month re-work"), params: { review_id: reviewId },
        });
    }

    async editChange() {
        const d = this.D;
        await this.openFlow(d.person.id, d.id, {});
    }

    async openLetter() {
        try {
            const act = await this.orm.call(MODEL, "open_letter", [this.D.id]);
            await this.action.doAction(act);
        } catch (e) {
            this.notif.add(errText(e, _t("The letter could not be opened.")), { type: "warning" });
        }
    }

    stepTone(status) {
        return { approved: "ok", done: "ok", open: "now", pending: "wait", skipped: "muted", rejected: "bad", returned: "bad" }[status] || "wait";
    }
}

registry.category("actions").add("pb_job_change", PbJobChange);
