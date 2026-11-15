/** @odoo-module **/
/**
 * `pb_leave_kinds` — the Kinds of leave screen (WDGAP S5-A).
 *
 * THE HERO IS THE DRAWER. One kind of leave, five numbered steps (what it is,
 * how people take it, pay, allowance, what the employee sees) and, as the
 * values change, the rules in plain words and the employee's own tile and
 * form option — before anything is saved.
 *
 * THREE PLACES A KIND CAN BE: switched on, waiting for review (made from a
 * ready-made kind), switched off. A kind is at exactly one, so the steps add up.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`): a NEW markup()
 *      per render re-inserts the SVG on every patch (OWL markup flicker).
 * R3 — every sentence a person reads is a `_t()` literal or comes from the
 *      server already translated.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
const GLANCE_FILTERS = {
    on: { state: ["on"] },
    review: { state: ["review"] },
    pay_open: { pay: ["open"], state: ["on"] },
    earning: { earning: ["monthly", "yearly"], state: ["on"] },
};
/** The drawer's fields, as `get_kind` answers them and `save_kind` takes them. */
const FIELDS = [
    "name", "names", "company_id", "country", "unit", "counted", "approval", "hr_only",
    "backdate_ok", "backdate_alert", "document", "carry_cap", "pay", "pay_pct", "funding",
    "employer_pct", "earning", "days_per_year", "waiting_months", "max_balance", "take_ahead",
    "expire_months", "earn_from", "steps",
];

function blankKind(board) {
    return {
        id: 0, name: "", names: { en: "", vi: "", id: "" },
        company_id: board.default_company_id || 0, country: board.default_country || "",
        unit: "day", counted: true, approval: "hr", hr_only: false, backdate_ok: false,
        backdate_alert: true, document: false, carry_cap: 0, pay: "paid", pay_pct: 100,
        funding: "employer", employer_pct: 0, earning: "none", days_per_year: 0,
        waiting_months: 0, max_balance: 0, take_ahead: false, expire_months: 0,
        earn_from: "", steps: [], sources: {}, locks: { policy: false, used: false },
        state: "off", state_label: _t("New"), review: false, starter: false, recent: [],
        holders: 0, can_write: true,
    };
}

export class PbLeaveKinds extends Component {
    static template = "pb_leave_setup.PbLeaveKinds";
    static components = { PbFilterLayout };
    static props = ["*"];

    get stepsLabel() { return _t("Where every kind of leave is"); }
    get searchLabel() { return _t("Find a kind of leave…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, allowed: true, why: "", canWrite: false,
            board: { options: {}, checks: { pay_open: [], no_start: { count: 0, names: [] } } },
            kpis: {}, total: 0,
            rows: [], listTotal: 0, listLoaded: false, listError: false,
            loadingMore: false, stepCounts: {},
            // the drawer
            kind: null, draft: null, busy: false, dirty: false, preview: null,
            // ready-made kinds
            starter: null,
        });
        this.kit = useFilterKit({
            model: "pb.leave.setup",
            noun: _t("kinds of leave"),
            onChange: () => this.loadPage(),
        });
        this._previewSeq = 0;
        this._previewTimer = null;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => {
            await this.load();
            const ctx = (this.props.action && this.props.action.context) || {};
            if (ctx.pb_leave_open === "starters" && this.state.allowed && this.state.canWrite) {
                await this.openStarter();
            }
        });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    // ------------------------------------------------------------ loading
    async load() {
        try {
            const d = await this.orm.call("pb.leave.setup", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                why: d.why || "",
                canWrite: !!d.can_write,
                kpis: d.kpis || {},
                total: d.total || 0,
                board: d.allowed === false ? this.state.board : d,
            });
        } catch (e) {
            console.warn("pb_leave_setup: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The kinds of leave could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.leave.setup", "get_kinds_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            if (d.steps) { this.state.stepCounts = d.steps; }
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_leave_setup: the list could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The kinds of leave could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() {
        this.state.listError = false;
        this.state.listLoaded = false;
        this.kit.refresh();
    }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    // --------------------------------------------------------- the quiet board
    get stepDefs() {
        return [
            { key: "on", title: _t("Switched on") },
            { key: "review", title: _t("Waiting for review") },
            { key: "off", title: _t("Switched off") },
        ];
    }
    _kindsLabel(n) { return n === 1 ? _t("1 kind") : _t("%s kinds", this.fmtInt(n)); }
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const count = counts[st.key] || 0;
            let flag = "";
            if (st.key === "review" && count) {
                flag = count === 1 ? _t("1 to review") : _t("%s to review", count);
            }
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: this._kindsLabel(count), sub: "", flag, flagTone: "",
                on: this.kit.loaded && this.kit.isOn("state", st.key),
            };
        });
    }
    pickStep(key) {
        const kit = this.kit;
        if (kit.isOn("state", key) && !kit.isExactly({ state: [key] })) {
            kit.toggle("state", key);
            return;
        }
        kit.toggleFilters({ state: [key] });
    }
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "on", n: k.on || 0, label: _t("switched on"), tone: "", run: pick("on") },
            { key: "review", n: k.review || 0, label: _t("waiting for review"), tone: tone(k.review, "amber"), run: pick("review") },
            { key: "pay_open", n: k.pay_open || 0, label: _t("with pay to decide"), tone: tone(k.pay_open, "amber"), run: pick("pay_open") },
            { key: "earning", n: k.earning || 0, label: _t("build up by themselves"), tone: "", run: pick("earning") },
            { key: "no_start", n: k.no_start || 0, label: _t("people with no date of joining"), tone: tone(k.no_start, "amber"), run: null },
        ];
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }
    get checks() { return this.state.board.checks || { pay_open: [], no_start: { count: 0, names: [] } }; }
    get hasChecks() {
        const c = this.checks;
        return (c.pay_open && c.pay_open.length) || (c.no_start && c.no_start.count) || this.state.kpis.review;
    }
    get options() { return this.state.board.options || {}; }

    // ------------------------------------------------------------ the drawer
    async openKind(row) {
        if (!(await this.confirmLeave())) { return; }
        this.state.busy = true;
        this.state.kind = { ...blankKind(this.state.board), ...row, loading: true };
        this.state.draft = null;
        try {
            const k = await this.orm.call("pb.leave.setup", "get_kind", [row.id]);
            this._setKind(k);
        } catch (e) {
            this.notif.add(this._msg(e, _t("This kind of leave could not be opened.")), { type: "danger" });
            this.state.kind = null;
        } finally {
            this.state.busy = false;
        }
    }
    openNew() {
        const k = blankKind(this.state.board);
        this._setKind(k);
    }
    _setKind(k) {
        this.state.kind = k;
        const draft = {};
        for (const f of FIELDS) {
            const v = k[f];
            draft[f] = Array.isArray(v) ? v.map((x) => ({ ...x })) : (v && typeof v === "object" ? { ...v } : v);
        }
        draft.names = { en: "", vi: "", id: "", ...(k.names || {}) };
        if (!draft.names.en) { draft.names.en = k.name || ""; }
        this.state.draft = draft;
        this.state.dirty = false;
        this.updatePreview(true);
    }
    async confirmLeave() {
        if (this.state.kind && this.state.dirty) {
            // a quiet, honest guard: changes are never thrown away silently
            return window.confirm(_t("Leave without saving your changes?"));
        }
        return true;
    }
    async closeKind() {
        if (!(await this.confirmLeave())) { return; }
        this.state.kind = null;
        this.state.draft = null;
        this.state.preview = null;
    }
    get K() { return this.state.kind; }
    get D() { return this.state.draft; }
    get canEdit() { return this.state.canWrite && !!(this.K && this.K.can_write !== false); }
    get payLocked() { return !!(this.K && this.K.locks && this.K.locks.policy); }
    get usedLocked() { return !!(this.K && this.K.locks && this.K.locks.used); }
    get builds() {
        const d = this.D;
        return !!(d && d.counted && d.earning !== "none" && d.unit !== "hour");
    }
    /** The other languages this database speaks (the name is kept in each). */
    get hasVi() { return (this.state.board.langs || []).includes("vi"); }
    get hasId() { return (this.state.board.langs || []).includes("id"); }
    source(key) {
        const s = (this.K && this.K.sources) || {};
        return s[key] || "";
    }
    get otherSources() {
        const s = (this.K && this.K.sources) || {};
        return Object.entries(s).filter(([k]) => !["days", "steps", "pay"].includes(k)).map(([, v]) => v);
    }

    set(field, value) {
        if (!this.D) { return; }
        this.D[field] = value;
        this.state.dirty = true;
        if (field === "earning" && value !== "none" && !Number(this.D.days_per_year)) {
            this.D.days_per_year = 12;
        }
        if (field === "pay" && value === "unpaid") { this.D.funding = "none"; }
        if (field === "pay" && value !== "unpaid" && this.D.funding === "none") { this.D.funding = "employer"; }
        this.updatePreview();
    }
    onInput(field, ev) { this.set(field, ev.target.value); }
    onCheck(field, ev) { this.set(field, !!ev.target.checked); }
    onName(lang, ev) {
        this.D.names[lang] = ev.target.value;
        if (lang === "en") { this.D.name = ev.target.value; }
        this.state.dirty = true;
        this.updatePreview();
    }
    onMonth(ev) {
        const v = ev.target.value;
        this.set("earn_from", v && v.length === 7 ? v + "-01" : v);
    }
    get earnMonth() { return (this.D && this.D.earn_from || "").slice(0, 7); }
    addStep() {
        const last = this.D.steps.length ? this.D.steps[this.D.steps.length - 1] : null;
        this.D.steps.push({ years: last ? Number(last.years) + 5 : 5, days: last ? Number(last.days) + 1 : 1 });
        this.state.dirty = true;
        this.updatePreview();
    }
    removeStep(i) {
        this.D.steps.splice(i, 1);
        this.state.dirty = true;
        this.updatePreview();
    }
    onStep(i, field, ev) {
        this.D.steps[i][field] = ev.target.value;
        this.state.dirty = true;
        this.updatePreview();
    }

    updatePreview(now = false) {
        clearTimeout(this._previewTimer);
        const run = async () => {
            const d = this.D;
            if (!d) { return; }
            const seq = ++this._previewSeq;
            try {
                const p = await this.orm.call("pb.leave.setup", "preview", [this._payload()]);
                if (seq === this._previewSeq) { this.state.preview = p; }
            } catch {
                if (seq === this._previewSeq) { this.state.preview = null; }
            }
        };
        if (now) { run(); } else { this._previewTimer = setTimeout(run, 220); }
    }

    _payload() {
        const d = this.D;
        const out = {};
        for (const f of FIELDS) { out[f] = d[f]; }
        out.name = (d.names && d.names.en) || d.name || "";
        out.steps = (d.steps || []).map((s) => ({ years: s.years, days: s.days }));
        if (this.payLocked) {
            for (const f of ["pay", "pay_pct", "funding", "employer_pct", "earning"]) { delete out[f]; }
        }
        if (this.usedLocked) { delete out.unit; delete out.counted; }
        return out;
    }

    async save(switchOn = false) {
        const d = this.D;
        if (!d) { return; }
        if (!((d.names && d.names.en) || "").trim()) {
            this.notif.add(_t("Give the kind of leave a name."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const k = await this.orm.call("pb.leave.setup", "save_kind",
                                          [this.K.id || 0, this._payload()], { switch_on: !!switchOn });
            this._setKind(k);
            this.notif.add(switchOn ? _t("Saved and switched on. People can ask for it now.") : _t("Saved."),
                           { type: "success" });
            await this.refresh();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async toggleOn(on) {
        if (!this.K || !this.K.id) { return; }
        if (this.state.dirty) {
            await this.save(on);
            return;
        }
        this.state.busy = true;
        try {
            const k = await this.orm.call("pb.leave.setup", "set_active", [this.K.id, !!on]);
            this._setKind(k);
            this.notif.add(on ? _t("Switched on. People can ask for it now.")
                              : _t("Switched off. Nobody can ask for it; what was taken stays recorded."),
                           { type: "success" });
            await this.refresh();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    async postNow() {
        if (!this.K || !this.K.id) { return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.leave.setup", "post_now", [this.K.id]);
            this._setKind(res.kind);
            this.notif.add(res.msg, { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ ready-made kinds
    async openStarter(country = "") {
        const b = this.state.board;
        this.state.starter = {
            country: country || b.default_country || "VN",
            company_id: b.default_company_id || 0,
            rows: [], picked: {}, loading: true, busy: false,
        };
        await this.loadStarter();
    }
    closeStarter() { this.state.starter = null; }
    async loadStarter() {
        const st = this.state.starter;
        if (!st) { return; }
        st.loading = true;
        try {
            const d = await this.orm.call("pb.leave.setup", "starter_list", [st.country, st.company_id]);
            st.rows = d.rows || [];
            st.picked = {};
            for (const r of st.rows) { if (!r.made) { st.picked[r.key] = true; } }
        } catch (e) {
            st.rows = [];
            this.notif.add(this._msg(e, _t("The ready-made kinds could not be read.")), { type: "danger" });
        } finally {
            st.loading = false;
        }
    }
    pickCountry(code) { this.state.starter.country = code; this.loadStarter(); }
    pickCompany(ev) { this.state.starter.company_id = parseInt(ev.target.value || "0", 10) || 0; this.loadStarter(); }
    togglePick(row) {
        if (row.made) { return; }
        this.state.starter.picked[row.key] = !this.state.starter.picked[row.key];
    }
    get pickedCount() {
        const st = this.state.starter;
        return st ? Object.values(st.picked).filter(Boolean).length : 0;
    }
    get addLabel() {
        const n = this.pickedCount;
        return n === 1 ? _t("Add 1 kind, switched off") : _t("Add %s kinds, switched off", n);
    }
    async applyStarter() {
        const st = this.state.starter;
        const keys = Object.entries(st.picked).filter(([, v]) => v).map(([k]) => k);
        if (!keys.length) {
            this.notif.add(_t("Tick at least one kind to add."), { type: "warning" });
            return;
        }
        st.busy = true;
        try {
            const res = await this.orm.call("pb.leave.setup", "starter_apply", [st.country, st.company_id, keys]);
            this.notif.add(res.msg, { type: "success" });
            this.state.starter = null;
            await this.refresh();
            this.kit.toggleFilters({ state: ["review"] });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The kinds could not be added.")), { type: "danger" });
        } finally {
            if (this.state.starter) { this.state.starter.busy = false; }
        }
    }

    // ------------------------------------------------------------ plumbing
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.starter) { this.state.starter = null; return; }
        if (this.state.kind) { this.closeKind(); }
    }
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_leave_kinds", PbLeaveKinds);
