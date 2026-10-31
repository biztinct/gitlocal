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

/* FILTER W3. Both registers sit on the board's ONE filter panel (see
 * hiring_board.js): the role / recruiter / stage selects, the flag chips and
 * the localStorage filter memory are gone - the kit remembers each list's
 * filters, counts every value over everybody the reader may see, and the
 * lists come a page at a time from the server (`get_applicants_page`,
 * `get_offers_page`). Only the Board / List choice is still remembered here:
 * it is how the list is drawn, not what is in it. */
const APPS_KEY = "pbhr.applicants.v2";
const OLD_KEYS = ["pbhr.applicants.v1", "pbhr.offers.v1"];
const REG_COL_PAGE = 30;
const REG_COL_MORE = 40;
const APPS_PAGE = 120;
const OFFERS_PAGE = 60;

/** The register's hero figures, as the filters they tick (the views' own). */
const APP_FIGURES = {
    in_play: { family: ["play"] },
    waiting_mine: { attention: ["waiting"] },
    late: { attention: ["late"] },
};
/** The old door flags (`openRegister(tab, {flag})`), as panel filters. */
const APP_DOORS = {
    waiting_mine: { attention: ["waiting"] },
    late: { attention: ["late"] },
    iv_week: { attention: ["iv_week"] },
    duplicate: { attention: ["duplicate"] },
};
const OFFER_DOORS = {
    waiting_mine: { attention: ["mine"] },
    joining_soon: { attention: ["joining_soon"] },
    joined_month: { state: ["joined"], joined: { preset: "this_month" } },
    docs_overdue: { docs: ["overdue"] },
    check_flagged: { check: ["flagged"] },
};
/** List columns the server can order by, and the two sorts each flips. */
const LIST_SORTS = {
    name: ["name", "name_desc"],
    days: ["stuck", "moved"],
    applied: ["applied", "applied_old"],
};

const OFFER_STEP_KEYS = ["approval", "candidate", "signing", "joined", "closed"];

/** The state pill's tone, by the step the offer is at. */
const STEP_TONE = { approval: "info", candidate: "info", signing: "green", joined: "green", closed: "rose" };

function readView() {
    try {
        for (const k of OLD_KEYS) { window.localStorage.removeItem(k); }
        return window.localStorage.getItem(APPS_KEY) === "list" ? "list" : "board";
    } catch {
        return "board";
    }
}

function writeView(view) {
    try { window.localStorage.setItem(APPS_KEY, view); } catch { /* private window: fine */ }
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
                loaded: false, allowed: true, cards: [], columns: [], total: 0,
                roles: [], glance: {}, canMove: false,
            },
            appsF: { view: readView() },
            appsColLimit: {}, appsColOpen: {}, appsRailOpen: "",
            offers: {
                loaded: false, allowed: true, rows: [], steps: {}, flags: {},
                total: 0, showMoney: false,
            },
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

    /** An Overview figure's door: a register with exactly one filter on. */
    async openRegister(tab, { flag = "", step = "" } = {}) {
        let filters = {};
        if (tab === "offers") {
            filters = { ...(OFFER_DOORS[flag] || {}) };
            if (step) { filters.step = [step]; }
        } else if (tab === "applicants") {
            filters = { ...(APP_DOORS[flag] || {}) };
        }
        await this.openTabWith(tab, filters);
    },

    async reloadRegister() {
        if (this.onRegister) { await this.refreshKitList(); }
    },

    /** The kit's onChange, for the two registers. */
    async loadKitPage({ more = false } = {}) {
        if (this.kitOn === "applicants") { return this.loadApplicantsPage({ more }); }
        if (this.kitOn === "offers") { return this.loadOffersPage({ more }); }
        return super.loadKitPage(...arguments);
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
    async loadApplicantsPage({ more = false } = {}) {
        const a = this.state.apps;
        const q = this.kit.query;
        const offset = more ? a.cards.length : 0;
        if (more) { this.state.kitMore = true; }
        try {
            const d = await this.orm.call("pb.hiring", "get_applicants_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: APPS_PAGE,
            });
            if (!this.kit.isCurrent(q.seq) || this.kitOn !== "applicants") { return; }
            const roles = more ? [...a.roles] : [];
            for (const r of d.roles || []) {
                if (!roles.some((x) => x.id === r.id)) { roles.push(r); }
            }
            Object.assign(a, {
                loaded: true, allowed: d.allowed !== false,
                cards: more ? [...a.cards, ...(d.cards || [])] : (d.cards || []),
                total: d.total || 0, roles,
            });
            if (!more) {
                Object.assign(a, { columns: d.columns || [], glance: d.glance || {}, canMove: !!d.can_move });
                // somebody the new filters no longer list is unticked, so a
                // bulk move never reaches a person nobody can see (R6)
                const ids = new Set(a.cards.map((c) => c.id));
                this.state.sel = this.state.sel.filter((id) => ids.has(id));
            }
            this.state.tabTotals = { ...this.state.tabTotals, applicants: d.total || 0 };
        } catch (e) {
            this.state.apps.loaded = true;
            this._kitFail(e, _t("The applicants could not be read. Press Refresh the board, or try again in a moment."));
        } finally {
            this.state.kitMore = false;
        }
    },

    /** Kept for older callers: read the register again. */
    async loadApplicants() { return this.reloadRegister(); },

    /** Ids from a select are strings; ids from the server are numbers. */
    sameId(a, b) { return String(a) === String(b); },

    regRole(id) { return (this.state.apps.roles || []).find((r) => r.id === id); },

    setAppsView(view) {
        this.state.appsF.view = view;
        writeView(view);
    },

    get appsSearchHint() { return _t("Search a name, an email, a role…"); },
    get offersSearchHint() { return _t("Search a candidate, a role, an offer…"); },

    /** Is the register narrowed by anything at all. */
    get anyAppsFilter() { return this.anyFilter; },

    clearAppsFilters() { if (this.kitReady) { this.kit.toggleFilters({}); } },

    /** The cards the panel produced: the page(s) read so far. */
    get regCards() { return this.state.apps.cards || []; },

    get appsHasMore() { return (this.state.apps.cards || []).length < (this.state.apps.total || 0); },

    get appsGlance() {
        const g = this.state.apps.glance || {};
        const n = (v) => v || 0;
        const team = !!g.team;
        const pick = (key) => () => (this.kitReady && this.kitOn === "applicants"
            ? this.kit.toggleFilters(APP_FIGURES[key]) : this.openTabWith("applicants", APP_FIGURES[key]));
        return [
            { key: "in_play", n: n(g.in_play), label: n(g.in_play) === 1 ? _t("person in play") : _t("people in play"), tone: "",
              run: pick("in_play") },
            { key: "roles", n: n(g.roles), label: n(g.roles) === 1 ? _t("role") : _t("roles"), tone: "", run: null },
            { key: "waiting_mine", n: n(g.waiting_mine), label: _t("waiting on you"), tone: g.waiting_mine ? "amber" : "",
              run: team ? pick("waiting_mine") : null },
            { key: "late", n: n(g.opinions_late), label: _t("opinions late"), tone: g.opinions_late ? "rose" : "",
              run: team ? pick("late") : null },
        ];
    },

    get appsGlanceOn() {
        if (this.kitOn !== "applicants" || !this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(APP_FIGURES)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    },

    /** The working columns: every open or done stage, folded when empty.
     *  The count is the column's over the WHOLE filtered list; the cards are
     *  the ones read so far. */
    get regColumns() {
        const by = {};
        for (const c of this.regCards) { (by[c.stage_id] = by[c.stage_id] || []).push(c); }
        return (this.state.apps.columns || [])
            .filter((s) => s.family !== "closed")
            .map((s) => {
                const cards = by[s.id] || [];
                // typical days here: the people in the column that were read
                const days = cards.map((c) => c.days_in_stage || 0);
                return {
                    ...s,
                    cards,
                    avg_days: days.length ? Math.round((days.reduce((x, y) => x + y, 0) / days.length) * 10) / 10 : null,
                    count: Math.max(s.count || 0, cards.length),
                    unread: Math.max(0, (s.count || 0) - cards.length),
                    limit: this.state.appsColLimit[s.key] || REG_COL_PAGE,
                };
            });
    },

    get regRailRows() {
        return (this.state.apps.columns || []).filter((s) => s.family === "closed")
            .map((s) => ({ ...s, count: s.count || 0 }));
    },

    get regRailTotal() { return this.regRailRows.reduce((n, s) => n + s.count, 0); },

    regFolded(col) { return !col.count && !this.state.appsColOpen[col.key]; },

    toggleRegFold(col) { this.state.appsColOpen[col.key] = !this.state.appsColOpen[col.key]; },

    regShowMore(col) { this.state.appsColLimit[col.key] = (this.state.appsColLimit[col.key] || REG_COL_PAGE) + REG_COL_MORE; },

    regMoreLabel(col) { return _t("Show %s more", Math.min(REG_COL_MORE, col.cards.length - col.limit)); },

    /** A column holds more people than the pages read so far. */
    regUnreadLabel(col) {
        return col.unread === 1 ? _t("1 more further down the list") : _t("%s more further down the list", col.unread);
    },

    toggleRegRail(key) { this.state.appsRailOpen = this.state.appsRailOpen === key ? "" : key; },

    get regColumnsShown() { return this.regColumns.filter((c) => c.count).length; },

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

    /** A column the server can order by (the rest are not sortable: a page
     *  sorted in the browser would be a stale array, ruling R6). */
    canSortApps(key) { return !!LIST_SORTS[key]; },

    sortApps(key) {
        const pair = LIST_SORTS[key];
        if (!pair || !this.kitReady) { return; }
        this.kit.setSort(this.kit.sort === pair[0] ? pair[1] : pair[0]);
    },

    sortMark(key) {
        const pair = LIST_SORTS[key];
        if (!pair) { return ""; }
        if (this.kit.sort === pair[0]) { return key === "days" ? "arrowDown" : key === "applied" ? "arrowDown" : "arrowUp"; }
        if (this.kit.sort === pair[1]) { return key === "days" ? "arrowUp" : key === "applied" ? "arrowUp" : "arrowDown"; }
        return "";
    },

    sortAria(key) {
        const mark = this.sortMark(key);
        return mark === "arrowUp" ? "ascending" : mark === "arrowDown" ? "descending" : "none";
    },

    /** In the panel's order, as the server sent it. */
    get regListRows() { return this.regCards; },

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

    // ================================================================ OFFERS
    async loadOffersPage({ more = false } = {}) {
        const o = this.state.offers;
        const q = this.kit.query;
        const offset = more ? o.rows.length : 0;
        if (more) { this.state.kitMore = true; }
        try {
            const d = await this.orm.call("pb.hiring", "get_offers_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: OFFERS_PAGE,
            });
            if (!this.kit.isCurrent(q.seq) || this.kitOn !== "offers") { return; }
            Object.assign(o, {
                loaded: true, allowed: d.allowed !== false,
                rows: more ? [...o.rows, ...(d.rows || [])] : (d.rows || []),
                total: d.total || 0, showMoney: !!d.show_money,
            });
            if (!more) { Object.assign(o, { steps: d.steps || {}, flags: d.flags || {} }); }
            this.state.tabTotals = { ...this.state.tabTotals, offers: d.total || 0 };
        } catch (e) {
            this.state.offers.loaded = true;
            this._kitFail(e, _t("The offers could not be read. Press Refresh the board, or try again in a moment."));
        } finally {
            this.state.kitMore = false;
        }
    },

    /** Kept for older callers: read the register again. */
    async loadOffers() { return this.reloadRegister(); },

    /** A step on the strip: only its offers; pressed again, the step goes. */
    pickOfferStep(key) {
        if (this.kitOn !== "offers" || !this.kitReady) { return this.openTabWith("offers", { step: [key] }); }
        const on = this.kit.values("step");
        if (on.length === 1 && String(on[0]) === key) {
            this.kit.clear("step");
        } else {
            this.kit.only("step", key);
        }
    },

    get anyOffersFilter() { return this.anyFilter; },

    clearOffersFilters() { if (this.kitReady) { this.kit.toggleFilters({}); } },

    get offersHasMore() { return (this.state.offers.rows || []).length < (this.state.offers.total || 0); },

    /** The five steps, counted over every OTHER filter that is on (R1). */
    get offerSteps() {
        const counts = this.state.offers.steps || {};
        const flags = this.state.offers.flags || {};
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
            if (key === "approval" && flags.mine) {
                flag = _t("%s waiting on you", flags.mine);
                flagTone = "mine";
            } else if (key === "signing" && flags.joining_soon) {
                flag = _t("%s joining in 30 days", flags.joining_soon);
            }
            return {
                key, n: String(i + 1).padStart(2, "0"), title: words[key][0], sub: words[key][1],
                count: n, countLabel: n === 1 ? _t("1 offer") : _t("%s offers", n),
                flag, flagTone, on: this.kitOn === "offers" && this.kit.isOn("step", key),
            };
        });
    },

    /** The offers the panel produced: the page(s) read so far. */
    get offRows() { return this.state.offers.rows || []; },

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
