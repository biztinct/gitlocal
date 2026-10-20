/** @odoo-module **/
/**
 * NAV P3a — the Hiring hub's two registers, APPLICANTS and OFFERS.
 *
 * Both are HOME TABS of the board (`state.tab` "applicants" / "offers"), not
 * components of their own, because the candidate drawer, the move menu, the
 * outcome popover, the share sheet, the email form and every P6 joining dialog
 * are drawn by this component and read this component's state. A register
 * that wanted the drawer from outside would have to copy it.
 *
 * HERO MOMENTS.
 *   Applicants — one line that reads as a sentence ("128 people in play ·
 *   27 roles · 9 waiting on you · 4 opinions late"), every figure a filter,
 *   and under it one pipeline across every role: the same cards, the same
 *   drawer, the same moves, with the role on each card.
 *   Offers — the story of an offer left to right as five numbered steps, with
 *   "waiting on you" lit on the first; every row says where the papers, the
 *   check and the joining date are, and its ⋯ menu offers only what the
 *   role's own Offer panel would.
 *
 * WHAT THIS FILE DOES NOT DECIDE: who may move, send or confirm. The server
 * answers `can_move` / `can_recruit` per role and refuses what it should; a
 * bulk move from here carries `register: true` so a stage one of the chosen
 * people's roles does not use is refused before anybody moves.
 *
 * The role-page verbs the drawer calls (`reloadRole`, `stageByKey`,
 * `nextKeyFor`, `flatOrder`, `cards`, `moveTargets`, `refresh`) are answered
 * from the register while one is showing, so the drawer works unchanged.
 */
import { onWillStart, useExternalListener, useRef } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { openHub } from "@pb_hub/js/hub_nav";
import { PbHiringBoard } from "./hiring_board";

const APPS_KEY = "pbhr.applicants.v1";
const OFFERS_KEY = "pbhr.offers.v1";
const REG_COL_PAGE = 30;
const REG_COL_MORE = 40;
const SEARCH_DEBOUNCE = 300;

const APPS_DEFAULT = { view: "board", role: "", recruiter: "", family: "", flag: "", q: "", sort: "stage", dir: 1 };
const OFFERS_DEFAULT = { step: "", role: "", recruiter: "", flag: "", q: "" };

/** A card's flag filters, the same tests the server runs (registers_p9.py). */
const APP_FLAG_TEST = {
    waiting_mine: (c) => (c.flags || []).includes("waiting"),
    late: (c) => !!((c.opinions || {}).late) || (c.flags || []).includes("late"),
    iv_week: (c) => (c.flags || []).includes("iv"),
    duplicate: (c) => (c.flags || []).includes("duplicate"),
};

const OFFER_FLAG_TEST = {
    waiting_mine: (r) => !!r.waiting_mine,
    docs_overdue: (r) => !!(r.docreq && r.docreq.overdue),
    check_flagged: (r) => !!(r.bgv && r.bgv.state === "flagged"),
    joining_soon: (r) => !!r.joining_soon,
    joined_month: (r) => !!r.joined_month,
};

const OFFER_STEP_KEYS = ["approval", "candidate", "signing", "joined", "closed"];

/** The state pill's tone, by the step the offer is at. */
const STEP_TONE = { approval: "info", candidate: "info", signing: "green", joined: "green", closed: "rose" };

function readStore(key, fallback) {
    try {
        const raw = window.localStorage.getItem(key);
        const v = raw ? JSON.parse(raw) : null;
        return v && typeof v === "object" ? { ...fallback, ...v } : { ...fallback };
    } catch {
        return { ...fallback };
    }
}

function writeStore(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch { /* private window: fine */ }
}

patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        this.regBoardRef = useRef("regboard");
        // A press anywhere else closes an offer's ⋯ menu.
        useExternalListener(window, "click", () => { if (this.state.offMenu) { this.state.offMenu = null; } });
        useExternalListener(window, "scroll", () => { if (this.state.offMenu) { this.state.offMenu = null; } }, { capture: true });
        Object.assign(this.state, {
            apps: {
                loaded: false, loading: false, allowed: true, cards: [], columns: [], total: 0,
                capped: false, roles: [], recruiters: [], glance: {}, canMove: false,
            },
            appsF: readStore(APPS_KEY, APPS_DEFAULT),
            appsColLimit: {}, appsColOpen: {}, appsRailOpen: "",
            offers: {
                loaded: false, loading: false, allowed: true, rows: [], steps: [], counts: {},
                roles: [], recruiters: [], total: 0, capped: false, showMoney: false,
            },
            offF: readStore(OFFERS_KEY, OFFERS_DEFAULT),
            offMenu: null, offMenuAt: "", regOffer: null,
        });
        onWillStart(async () => {
            const ctx = (this.props.action && this.props.action.context) || {};
            const start = this.props.startTab;
            if ((start === "applicants" || start === "offers") && !this.props.roleId && !ctx.pb_role_id) {
                await this.setTab(start);
            }
        });
    },

    // ================================================================ where
    get onApplicants() { return this.state.view === "home" && this.state.tab === "applicants"; },
    get onOffers() { return this.state.view === "home" && this.state.tab === "offers"; },
    get onRegister() { return this.onApplicants || this.onOffers; },
    /** The tab, whichever view is showing (the home template's own test). */
    get isRegisterTab() { return ["applicants", "offers"].includes(this.state.tab); },

    setTab(tab) {
        super.setTab(tab);
        if (tab === "applicants") { return this.loadApplicants({ quiet: this.state.apps.loaded }); }
        if (tab === "offers") { return this.loadOffers({ quiet: this.state.offers.loaded }); }
    },

    /** An Overview tile's door: the Offers tab with exactly one filter on. */
    async openRegister(tab, { flag = "", step = "" } = {}) {
        if (tab === "offers") {
            this.state.offF = { ...OFFERS_DEFAULT, flag, step };
            this.saveOffersFilters();
        } else if (tab === "applicants") {
            this.state.appsF = { ...this.state.appsF, role: "", recruiter: "", family: "", q: "", flag };
            this.saveAppsFilters();
        }
        await this.setTab(tab);
    },

    async reloadRegister() {
        if (this.onApplicants) { await this.loadApplicants({ quiet: true }); }
        if (this.onOffers) { await this.loadOffers({ quiet: true }); }
    },

    // ======================================================== role-page verbs
    // While a register is showing, the drawer's verbs read and refresh the
    // register instead of a role that is not open.
    async reloadRole() {
        if (this.onRegister) { return this.reloadRegister(); }
        return super.reloadRole(...arguments);
    },

    async refresh() {
        if (this.onRegister) {
            await Promise.all([this.load(), this.reloadRegister()]);
            if (!this.state.signing) { this.state.regOffer = null; }
            if (this.state.cand) { await this.openCand(this.state.cand.id, { quiet: true }); }
            return;
        }
        return super.refresh(...arguments);
    },

    async p6Refresh() {
        if (this.onRegister) { await this.reloadRegister(); }
        return super.p6Refresh(...arguments);
    },

    get cards() {
        if (this.onApplicants) { return this.state.apps.cards; }
        return super.cards;
    },

    get canMove() {
        if (this.onApplicants) { return !!this.state.apps.canMove; }
        return super.canMove;
    },

    kcMove(cd) {
        if (this.onApplicants) { return !!(cd && cd.can_move); }
        return super.kcMove(cd);
    },

    stageByKey(key) {
        if (this.onApplicants) { return this.state.apps.columns.find((s) => s.key === key); }
        return super.stageByKey(key);
    },

    get flatOrder() {
        if (!this.onApplicants) { return super.flatOrder; }
        if (this.state.appsF.view === "list") { return this.regListRows.map((c) => c.id); }
        const out = [];
        for (const col of this.regColumns) {
            for (const c of col.cards.slice(0, col.limit)) { out.push(c.id); }
        }
        return out;
    },

    get closedCards() {
        if (this.onApplicants) { return this.regCards.filter((c) => c.family === "closed"); }
        return super.closedCards;
    },

    scrollToCard(id) {
        if (!this.onApplicants) { return super.scrollToCard(id); }
        const el = this.regBoardRef.el && this.regBoardRef.el.querySelector(`[data-id="${id}"]`);
        if (el && el.scrollIntoView) { el.scrollIntoView({ block: "nearest", inline: "nearest" }); }
    },

    /** The next working stage on THIS person's role, in journey order. */
    nextKeyFor(card) {
        if (!this.onApplicants) { return super.nextKeyFor(card); }
        const role = this.regRole(card.role_id);
        const keys = this.state.apps.columns
            .filter((c) => c.family === "open" && (!role || role.stage_keys.includes(c.key)))
            .map((c) => c.key);
        const i = keys.indexOf(card.stage_key);
        return (i > -1 ? keys[i + 1] : keys[1]) || "";
    },

    onCardClick(ev, card) {
        if (this.onApplicants && !(card && card.can_move)) {
            this.state.focusId = card.id;
            this.openCand(card.id);
            return;
        }
        return super.onCardClick(ev, card);
    },

    toggleSel(card, ev) {
        if (this.onApplicants && !(card && card.can_move)) { return; }
        return super.toggleSel(card, ev);
    },

    async moveTo(ids, key, extra = {}) {
        if (this.onApplicants) { extra = { ...extra, register: true }; }
        return super.moveTo(ids, key, extra);
    },

    openMoveMenu(ids) {
        if (this.onApplicants) {
            const cards = ids.map((id) => this.cardById(id)).filter(Boolean);
            const locked = cards.filter((c) => !c.can_move);
            if (locked.length) {
                this.notif.add(locked.length === 1
                    ? _t("%s is on a role you do not recruit, so they cannot be moved from here.", locked[0].name)
                    : _t("%s of these people are on roles you do not recruit. Untick them and try again.", locked.length),
                { type: "warning" });
                return;
            }
            if (!cards.length) { return; }
            this.state.moveMenu = { ids };
            return;
        }
        return super.openMoveMenu(ids);
    },

    /** The stages every chosen person's role uses (outcomes are on all). */
    get moveTargets() {
        if (!this.onApplicants) { return super.moveTargets; }
        const m = this.state.moveMenu;
        const cards = ((m && m.ids) || []).map((id) => this.cardById(id)).filter(Boolean);
        const roles = [...new Set(cards.map((c) => c.role_id))].map((id) => this.regRole(id)).filter(Boolean);
        return this.state.apps.columns.filter((s) => s.key !== "joined" && (s.family === "closed"
            || roles.every((r) => r.stage_keys.includes(s.key))));
    },

    /** True when the chosen people's roles do not all use the same stages. */
    get moveMixed() {
        if (!this.onApplicants || !this.state.moveMenu) { return false; }
        const cards = this.state.moveMenu.ids.map((id) => this.cardById(id)).filter(Boolean);
        const ids = [...new Set(cards.map((c) => c.role_id))];
        if (ids.length < 2) { return false; }
        const sets = ids.map((id) => ((this.regRole(id) || {}).stage_keys || []).join(","));
        return new Set(sets).size > 1;
    },

    get moveNoShared() {
        return this.moveMixed && !this.moveTargets.some((s) => s.family === "open");
    },

    onKey(ev) {
        super.onKey(ev);
        if (ev.defaultPrevented || !this.onRegister) { return; }
        const s = this.state;
        const t = ev.target;
        const typing = t && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));
        if (ev.key === "Escape") {
            let done = true;
            if (s.outcome) { s.outcome = null; }
            else if (s.moveMenu) { s.moveMenu = null; }
            else if (s.noteForm) { s.noteForm = null; }
            else if (s.offMenu) { s.offMenu = null; }
            else if (typing || this.anyDialog) { done = false; }
            else if (s.cand) { this.closeCand(); }
            else if (s.sel.length) { this.clearSel(); }
            else { done = false; }
            if (done) { ev.stopPropagation(); ev.preventDefault(); }
            return;
        }
        if (typing || this.anyDialog || ev.metaKey || ev.ctrlKey || ev.altKey || !s.cand) { return; }
        const key = ev.key;
        const c = s.cand;
        if (key === "ArrowDown" || key === "ArrowRight") { ev.preventDefault(); this.stepCand(1); return; }
        if (key === "ArrowUp" || key === "ArrowLeft") { ev.preventDefault(); this.stepCand(-1); return; }
        if ((key === "m" || key === "M") && c.can_move) { ev.preventDefault(); this.openMoveMenu([c.id]); return; }
        if ((key === "e" || key === "E") && c.can_recruit) { ev.preventDefault(); this.startMessage({ id: c.id, name: c.name }); return; }
        if (key === "n" || key === "N") { ev.preventDefault(); this.startNoteFor(c.id, c.name); }
    },

    // ============================================================ APPLICANTS
    async loadApplicants({ quiet = false } = {}) {
        const a = this.state.apps;
        if (!quiet) { a.loading = true; }
        const seq = (this._appsSeq = (this._appsSeq || 0) + 1);
        const f = this.state.appsF;
        try {
            const d = await this.orm.call("pb.hiring", "get_applicants", [{
                role_id: Number(f.role) || false, recruiter_id: Number(f.recruiter) || false,
                family: f.family || "", q: (f.q || "").trim(),
            }]);
            if (seq !== this._appsSeq) { return; }
            Object.assign(a, {
                loaded: true, allowed: d.allowed !== false, cards: d.cards || [], columns: d.columns || [],
                total: d.total || 0, capped: !!d.capped, roles: d.roles || [],
                recruiters: d.recruiters || [], glance: d.glance || {}, canMove: !!d.can_move,
            });
            // A remembered role that is no longer on this reader's board is dropped.
            if (f.role && !a.roles.some((r) => String(r.id) === String(f.role))) {
                this.state.appsF.role = "";
                this.saveAppsFilters();
                await this.loadApplicants({ quiet: true });
            }
        } catch (e) {
            if (seq === this._appsSeq) { a.loaded = true; }
            this.fail(e);
        } finally {
            if (seq === this._appsSeq) { a.loading = false; }
        }
    },

    saveAppsFilters() { writeStore(APPS_KEY, this.state.appsF); },

    /** Ids from a select are strings; ids from the server are numbers. */
    sameId(a, b) { return String(a) === String(b); },

    regRole(id) { return (this.state.apps.roles || []).find((r) => r.id === id); },

    /** A filter the SERVER applies (role, recruiter, family, words). */
    async setAppsFilter(key, value) {
        this.state.appsF[key] = value;
        this.saveAppsFilters();
        this.clearSel();
        await this.loadApplicants({ quiet: true });
    },

    onAppsQuery(ev) {
        this.state.appsF.q = ev.target.value;
        this.saveAppsFilters();
        clearTimeout(this._appsQTimer);
        this._appsQTimer = setTimeout(() => this.loadApplicants({ quiet: true }), SEARCH_DEBOUNCE);
    },

    /** A figure or chip: one at a time, pressed again to clear. */
    toggleAppsFlag(key) {
        this.state.appsF.flag = this.state.appsF.flag === key ? "" : key;
        this.saveAppsFilters();
        this.clearSel();
    },

    setAppsView(view) {
        this.state.appsF.view = view;
        this.saveAppsFilters();
    },

    get anyAppsFilter() {
        const f = this.state.appsF;
        return !!(f.role || f.recruiter || f.family || f.flag || (f.q || "").trim());
    },

    async clearAppsFilters() {
        this.state.appsF = { ...APPS_DEFAULT, view: this.state.appsF.view, sort: this.state.appsF.sort, dir: this.state.appsF.dir };
        this.saveAppsFilters();
        this.clearSel();
        await this.loadApplicants({ quiet: true });
    },

    get regCards() {
        const test = APP_FLAG_TEST[this.state.appsF.flag];
        const cards = this.state.apps.cards || [];
        return test ? cards.filter(test) : cards;
    },

    get appsGlance() {
        const g = this.state.apps.glance || {};
        const f = this.state.appsF;
        const n = (v) => v || 0;
        return [
            { key: "in_play", n: n(g.in_play), label: n(g.in_play) === 1 ? _t("person in play") : _t("people in play"), tone: "",
              run: () => this.setAppsFilter("family", f.family === "play" ? "" : "play") },
            { key: "roles", n: n(g.roles), label: n(g.roles) === 1 ? _t("role") : _t("roles"), tone: "", run: null },
            { key: "waiting_mine", n: n(g.waiting_mine), label: _t("waiting on you"), tone: g.waiting_mine ? "amber" : "",
              run: () => this.toggleAppsFlag("waiting_mine") },
            { key: "late", n: n(g.opinions_late), label: _t("opinions late"), tone: g.opinions_late ? "rose" : "",
              run: () => this.toggleAppsFlag("late") },
        ];
    },

    get appsGlanceOn() {
        const f = this.state.appsF;
        if (f.flag === "waiting_mine" || f.flag === "late") { return f.flag; }
        return f.family === "play" ? "in_play" : "";
    },

    get appsChips() {
        const g = this.state.apps.glance || {};
        return [
            { key: "iv_week", label: _t("Interview this week"), n: g.iv_week || 0 },
            { key: "duplicate", label: _t("Possible duplicate"), n: g.duplicate || 0 },
        ];
    },

    get appsFamilies() {
        return [
            { key: "", label: _t("Every stage") },
            { key: "play", label: _t("In play") },
            { key: "offer", label: _t("Offer") },
            { key: "joined", label: _t("Joined") },
            { key: "closed", label: _t("Closed") },
        ];
    },

    /** The working columns: every open or done stage, folded when empty. */
    get regColumns() {
        const by = {};
        for (const c of this.regCards) { (by[c.stage_id] = by[c.stage_id] || []).push(c); }
        return (this.state.apps.columns || [])
            .filter((s) => s.family !== "closed")
            .map((s) => ({
                ...s,
                cards: by[s.id] || [],
                count: (by[s.id] || []).length,
                limit: this.state.appsColLimit[s.key] || REG_COL_PAGE,
            }));
    },

    get regRailRows() {
        const by = {};
        for (const c of this.regCards) {
            if (c.family === "closed") { by[c.stage_key] = (by[c.stage_key] || 0) + 1; }
        }
        return (this.state.apps.columns || []).filter((s) => s.family === "closed")
            .map((s) => ({ ...s, count: by[s.key] || 0 }));
    },

    get regRailTotal() { return this.regRailRows.reduce((n, s) => n + s.count, 0); },

    regFolded(col) { return !col.cards.length && !this.state.appsColOpen[col.key]; },

    toggleRegFold(col) { this.state.appsColOpen[col.key] = !this.state.appsColOpen[col.key]; },

    regShowMore(col) { this.state.appsColLimit[col.key] = (this.state.appsColLimit[col.key] || REG_COL_PAGE) + REG_COL_MORE; },

    regMoreLabel(col) { return _t("Show %s more", Math.min(REG_COL_MORE, col.cards.length - col.limit)); },

    toggleRegRail(key) { this.state.appsRailOpen = this.state.appsRailOpen === key ? "" : key; },

    get regColumnsShown() { return this.regColumns.filter((c) => c.cards.length).length; },

    // ----------------------------------------------------------- the list
    get regListCols() {
        return [
            { key: "name", label: _t("Name") },
            { key: "role", label: _t("Role") },
            { key: "stage", label: _t("Stage") },
            { key: "days", label: _t("Days in stage"), num: true },
            { key: "next", label: _t("Next interview") },
            { key: "opinions", label: _t("Opinions") },
            { key: "waiting", label: _t("Waiting on") },
            { key: "applied", label: _t("Applied") },
        ];
    },

    sortApps(key) {
        const f = this.state.appsF;
        if (f.sort === key) { f.dir = -f.dir; } else { f.sort = key; f.dir = key === "days" ? -1 : 1; }
        this.saveAppsFilters();
    },

    sortMark(key) {
        const f = this.state.appsF;
        if (f.sort !== key) { return ""; }
        return f.dir > 0 ? "arrowUp" : "arrowDown";
    },

    get regListRows() {
        const f = this.state.appsF;
        const dir = f.dir || 1;
        const text = (v) => String(v || "").toLowerCase();
        const val = {
            name: (c) => text(c.name), role: (c) => text(c.role),
            stage: (c) => c.stage_seq || 0, days: (c) => c.days_in_stage || 0,
            next: (c) => c.next_interview_at || "~", opinions: (c) => (c.opinions || {}).in || 0,
            waiting: (c) => text(c.waiting) || "~", applied: (c) => c.applied_days || 0,
        }[f.sort] || ((c) => c.stage_seq || 0);
        return [...this.regCards].sort((a, b) => {
            const x = val(a);
            const y = val(b);
            if (x < y) { return -dir; }
            if (x > y) { return dir; }
            // the default tie-break: longest in the stage first
            return (b.days_in_stage || 0) - (a.days_in_stage || 0);
        });
    },

    opinionsWords(c) {
        const o = c.opinions || {};
        if (!o.total) { return ""; }
        return o.late ? _t("%(in)s of %(total)s · %(late)s late", { in: o.in, total: o.total, late: o.late })
            : _t("%(in)s of %(total)s", { in: o.in, total: o.total });
    },

    daysWord(n) {
        if (!n) { return _t("today"); }
        return n === 1 ? _t("1 day") : _t("%s days", n);
    },

    appliedWord(c) { return this.dayOnly(c.applied_on); },

    /** A date with no time ("2026-10-18") on the reader's calendar. `dayShort`
     *  reads a stored datetime as UTC, which moves a bare date back a day
     *  for anybody west of Greenwich. */
    dayOnly(value) {
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || "").slice(0, 10));
        if (!m) { return ""; }
        return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
            .toLocaleDateString(undefined, { day: "numeric", month: "short" });
    },

    onRegRowClick(ev, card) {
        if (card.can_move && (ev.shiftKey || ev.metaKey || ev.ctrlKey || this.state.sel.length)) {
            this.toggleSel(card, ev);
            return;
        }
        this.state.focusId = card.id;
        this.openCand(card.id);
    },

    get appsShowing() {
        const shown = this.regCards.length;
        const all = (this.state.apps.cards || []).length;
        if (!this.anyAppsFilter) {
            return shown === 1 ? _t("1 person across your roles") : _t("%s people across your roles", shown);
        }
        // A figure or chip narrows what was read; the other filters ask the
        // server, so what came back is already only the people that match.
        if (this.state.appsF.flag) { return _t("%(n)s of %(all)s people", { n: shown, all }); }
        return shown === 1 ? _t("1 person matches the filters") : _t("%s people match the filters", shown);
    },

    get appsCapLine() {
        const a = this.state.apps;
        return _t("Showing the newest %(n)s of %(total)s. Narrow it with a role or a stage to see an older one.",
                  { n: (a.cards || []).length, total: a.total });
    },

    // ================================================================ OFFERS
    async loadOffers({ quiet = false } = {}) {
        const o = this.state.offers;
        if (!quiet) { o.loading = true; }
        const seq = (this._offSeq = (this._offSeq || 0) + 1);
        try {
            const d = await this.orm.call("pb.hiring", "get_offers", [{}]);
            if (seq !== this._offSeq) { return; }
            Object.assign(o, {
                loaded: true, allowed: d.allowed !== false, rows: d.rows || [], steps: d.steps || [],
                counts: d.counts || {}, roles: d.roles || [], recruiters: d.recruiters || [],
                total: d.total || 0, capped: !!d.capped, showMoney: !!d.show_money,
            });
        } catch (e) {
            if (seq === this._offSeq) { o.loaded = true; }
            this.fail(e);
        } finally {
            if (seq === this._offSeq) { o.loading = false; }
        }
    },

    saveOffersFilters() { writeStore(OFFERS_KEY, this.state.offF); },

    setOffersFilter(key, value) {
        this.state.offF[key] = value;
        this.state.offMenu = null;
        this.saveOffersFilters();
    },

    toggleOffersFlag(key) { this.setOffersFilter("flag", this.state.offF.flag === key ? "" : key); },

    pickOfferStep(key) { this.setOffersFilter("step", this.state.offF.step === key ? "" : key); },

    get anyOffersFilter() {
        const f = this.state.offF;
        return !!(f.step || f.role || f.recruiter || f.flag || (f.q || "").trim());
    },

    clearOffersFilters() {
        this.state.offF = { ...OFFERS_DEFAULT };
        this.state.offMenu = null;
        this.saveOffersFilters();
    },

    get offerSteps() {
        const counts = {};
        for (const s of this.state.offers.steps || []) { counts[s.key] = s.count; }
        const c = this.state.offers.counts || {};
        const words = {
            approval: [_t("In approval"), _t("Being prepared or signed off")],
            candidate: [_t("With the candidate"), _t("Sent, waiting for their answer")],
            signing: [_t("Accepted and signing"), _t("Papers and the joining date")],
            joined: [_t("Joined"), _t("Handed to People › Joiners")],
            closed: [_t("Did not happen"), _t("Turned down, did not join or not approved")],
        };
        return OFFER_STEP_KEYS.map((key, i) => {
            const n = counts[key] || 0;
            let flag = "";
            let flagTone = "";
            if (key === "approval" && c.waiting_mine) {
                flag = _t("%s waiting on you", c.waiting_mine);
                flagTone = "mine";
            } else if (key === "signing" && c.joining_soon) {
                flag = _t("%s joining in 30 days", c.joining_soon);
            }
            return {
                key, n: String(i + 1).padStart(2, "0"), title: words[key][0], sub: words[key][1],
                count: n, countLabel: n === 1 ? _t("1 offer") : _t("%s offers", n),
                flag, flagTone, on: this.state.offF.step === key,
            };
        });
    },

    get offerChips() {
        const c = this.state.offers.counts || {};
        return [
            { key: "waiting_mine", label: _t("Waiting on you"), n: c.waiting_mine || 0, tone: "mine" },
            { key: "docs_overdue", label: _t("Documents overdue"), n: c.docs_overdue || 0, tone: "amber" },
            { key: "check_flagged", label: _t("Check flagged"), n: c.check_flagged || 0, tone: "rose" },
            { key: "joining_soon", label: _t("Joining in 30 days"), n: c.joining_soon || 0, tone: "" },
            { key: "joined_month", label: _t("Joined this month"), n: c.joined_month || 0, tone: "" },
        ];
    },

    get offRows() {
        const f = this.state.offF;
        const q = (f.q || "").trim().toLowerCase();
        const test = OFFER_FLAG_TEST[f.flag];
        let rows = (this.state.offers.rows || []).filter((r) => {
            if (f.step && r.step !== f.step) { return false; }
            if (f.role && String(r.requisition_id) !== String(f.role)) { return false; }
            if (f.recruiter && String(r.recruiter_id) !== String(f.recruiter)) { return false; }
            if (test && !test(r)) { return false; }
            if (q) {
                const hay = [r.candidate, r.role, r.role_title, r.name, r.recruiter].join(" ").toLowerCase();
                if (!hay.includes(q)) { return false; }
            }
            return true;
        });
        if (f.flag === "joining_soon") {
            rows = [...rows].sort((a, b) => {
                const x = a.joining_days === null || a.joining_days === undefined ? Infinity : a.joining_days;
                const y = b.joining_days === null || b.joining_days === undefined ? Infinity : b.joining_days;
                return x - y || b.id - a.id;
            });
        }
        return rows;
    },

    get offShowing() {
        const shown = this.offRows.length;
        const all = (this.state.offers.rows || []).length;
        if (!this.anyOffersFilter) { return all === 1 ? _t("all 1 offer") : _t("all %s offers", all); }
        return _t("%(n)s of %(all)s offers", { n: shown, all });
    },

    get offCapLine() {
        const o = this.state.offers;
        return _t("Showing the newest %(n)s of %(total)s offers.", { n: (o.rows || []).length, total: o.total });
    },

    stepTone(row) { return STEP_TONE[row.step] || ""; },

    docsWords(row) {
        const d = row.docreq;
        if (!d) { return ""; }
        if (d.state === "complete") { return _t("All %s in", d.wanted); }
        return _t("%(in)s of %(total)s in", { in: d.in, total: d.wanted });
    },

    checkWords(row) {
        const b = row.bgv;
        if (!b) { return ""; }
        // "All clear", never "Clear": that word is the filter button's, and
        // Vietnamese reads it as "erase".
        if (b.state === "complete") { return _t("All clear"); }
        if (b.state === "flagged") { return b.flags === 1 ? _t("1 flag") : _t("%s flags", b.flags); }
        return b.pending === 1 ? _t("1 to answer") : _t("%s to answer", b.pending);
    },

    checkTone(row) {
        const b = row.bgv;
        if (!b) { return ""; }
        return b.state === "complete" ? "green" : b.state === "flagged" ? "rose" : "";
    },

    joiningWords(row) {
        if (row.state === "joined") {
            return row.joined_on ? _t("Joined %s", this.dayOnly(row.joined_on)) : _t("Joined");
        }
        if (row.state === "dropped") {
            return row.drop_words ? _t("Did not join: %s", row.drop_words) : _t("Did not join");
        }
        if (!["accepted", "signed"].includes(row.state) || row.joining_days === null || row.joining_days === undefined) {
            return "";
        }
        const d = row.joining_days;
        if (d === 0) { return _t("Joining today"); }
        if (d === 1) { return _t("Joining tomorrow"); }
        if (d > 1) { return _t("In %s days", d); }
        return d === -1 ? _t("Expected yesterday") : _t("Expected %s days ago", -d);
    },

    joiningTone(row) {
        if (row.state === "joined") { return "green"; }
        if (row.state === "dropped") { return "rose"; }
        const d = row.joining_days;
        if (!["accepted", "signed"].includes(row.state) || d === null || d === undefined) { return ""; }
        if (d < 0) { return "rose"; }
        return d <= 3 ? "amber" : "";
    },

    /** The ⋯ menu offers what the role's Offer panel would, and no more. */
    offerVerbs(row) {
        const out = [
            { key: "cand", label: _t("Open the candidate"), icon: "user" },
            { key: "offer", label: _t("Open the offer"), icon: "scrollText" },
        ];
        if (row.can_recruit && row.docreq && row.docreq.state !== "complete") {
            out.push({ key: "remind", label: _t("Remind about documents"), icon: "bell" });
        }
        if (row.can_recruit && ["sent", "accepted"].includes(row.state)) {
            out.push({ key: "signed", label: _t("Record the signed copy"), icon: "stamp" });
        }
        if (row.can_recruit && row.state === "signed") {
            out.push({ key: "date", label: _t("Change the joining date"), icon: "calendar" });
            out.push({ key: "joined", label: _t("Confirm they joined"), icon: "logIn" });
            out.push({ key: "drop", label: _t("Did not join"), icon: "userX", tone: "no" });
        }
        if (row.case_id) {
            out.push({ key: "case", label: _t("Open the joining checklist"), icon: "layoutList" });
        }
        return out;
    },

    /** The menu floats (fixed) under its button, so the table can scroll
     *  sideways on a narrow screen without clipping it. */
    toggleOffMenu(ev, row) {
        ev.stopPropagation();
        if (this.state.offMenu === row.id) { this.state.offMenu = null; return; }
        const r = ev.currentTarget.getBoundingClientRect();
        const below = window.innerHeight - r.bottom > 300;
        this.state.offMenuAt = below
            ? `top:${Math.round(r.bottom + 4)}px;right:${Math.round(window.innerWidth - r.right)}px`
            : `bottom:${Math.round(window.innerHeight - r.top + 4)}px;right:${Math.round(window.innerWidth - r.right)}px`;
        this.state.offMenu = row.id;
    },

    async runOfferVerb(row, key) {
        this.state.offMenu = null;
        const offerId = row.id;
        if (key === "cand") { await this.openCand(row.applicant_id); return; }
        if (key === "offer") { await this.act("open_offer", { offer_id: offerId }, { reload: false }); return; }
        if (key === "remind") { await this.act("remind_documents", { offer_id: offerId }); return; }
        if (key === "case") { await this.act("open_case", { offer_id: offerId }, { reload: false }); return; }
        if (key === "signed") {
            this.state.regOffer = row;
            this.startSigning();
            return;
        }
        if (key === "date") {
            await this.openCand(row.applicant_id);
            if (this.state.cand && this.state.cand.joining) { this.p6OpenDate(); }
            return;
        }
        if (key === "joined") { await this.p6FromOffer(row, "confirm"); return; }
        if (key === "drop") { await this.p6FromOffer(row, "drop"); }
    },

    /** "Record the signed copy" from a register row reads the row's offer. */
    get offer() {
        if (this.onOffers && this.state.regOffer) { return this.state.regOffer; }
        return super.offer;
    },

    cancelSigning() {
        this.state.regOffer = null;
        return super.cancelSigning(...arguments);
    },

    /** Joined rows: People › Joiners carries on from here. */
    get joinersDoor() {
        const actions = registry.category("actions");
        const lenses = registry.category("pb_people_hub_lens");
        return actions.contains("pb_people_hub") && lenses.contains("newjoiners");
    },

    async openJoiners(row) {
        try {
            await openHub(this.action, {
                xmlid: "pb_people_hub.action_pb_people_hub",
                lens: "newjoiners",
                focus: row.employee_id ? String(row.employee_id) : "",
                back: { label: _t("Hiring"), xmlid: "pb_hiring.action_pb_hiring_hub", lens: "offers" },
            });
        } catch (e) {
            this.fail(e);
        }
    },

    offerMoney(row) {
        if (!this.state.offers.showMoney || row.money_locked || row.monthly_total === null) { return ""; }
        return this.money(row.monthly_total, row.currency);
    },
});
