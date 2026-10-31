/** @odoo-module **/
/**
 * Home › ASK HR — a Payobook board (NAV P3d, 2026-10-21).
 *
 * NAV P2 mounted the native kanban here; P3d replaces it with the quiet board
 * every other queue has: one slim line of numbers, the four steps a question
 * moves through (New · With HR · Answered · Closed, each question at exactly
 * one), cards with the person, the category, the age and who has it, the shared
 * filter panel (FILTER wave 4: the steps are a filter in it, counted on the
 * server and paged), and an empty state that says what is true.
 *
 * THE HERO MOMENT is "Nobody has it yet" turning into your face with one key:
 * focus a card, press T, it is yours and on its way to With HR.
 *
 * WHO SEES WHAT is the record rules' answer, never this file's: one read
 * (`pb.ask.hr.get_board`) made AS THE READER. The HR team sees every question
 * and gets Take it / Hand to… / Close with a note (one card or several); an
 * employee sees only the questions they asked, no owner actions, and an
 * "Ask a new question" door to their own page.
 *
 * Every change goes through `pb.ask.hr.act`, which calls the methods the
 * native form calls. The native kanban / list / form stay as the off-menu
 * fallback; a card opens the native form in the main screen (its chatter is
 * the answer box, and the web client draws no chatter inside a dialog), with
 * Home › Ask HR as the way back.
 */
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { ic } from "@pb_import_kit/js/import_icons";
import { railKeydown } from "@pb_hub/js/hub_nav";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";

const MODEL = "pb.ask.hr.ticket";
const OPEN = ["new", "with_hr", "answered"];
const PAGE = 60;

/** Lucide icon per category (the kit's names). */
const CATEGORY_ICON = {
    pay: "banknote", leave: "umbrella", documents: "fileText",
    benefits: "shieldCheck", equipment: "laptop", other: "helpCircle",
};

// The filters used to be remembered per person in this browser
// ("pbhub.askhr.filters.v1"); the filter panel remembers them now (per
// browser tab, plus saved views), so that memory is gone on purpose.

export class PbAskHrLens extends Component {
    static template = "pb_ask_hr.PbAskHrLens";
    static components = { PbFilterLayout };
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.pickSearchRef = useRef("pickSearch");
        this.noteRef = useRef("closeNote");
        this.state = useState({
            loading: true,
            failed: false,
            d: null,
            // the cards the filter panel produced, one page at a time
            cards: [],
            total: 0,
            stepCounts: {},
            listLoaded: false,
            loadingMore: false,
            sel: {},           // id -> true
            busy: false,
            picker: null,      // { ids, users, q }
            closing: null,     // { ids, note, tell }
        });
        // The shared filter panel (pb_filter_kit): it owns the filters, the
        // counts and the views; the step strip and the numbers set it.
        this.kit = useFilterKit({
            model: "pb.ask.hr",
            noun: _t("questions"),
            onChange: () => this.loadPage(),
        });
        onWillStart(() => this.load());
        // A sheet that opens puts the cursor where the typing goes.
        useEffect((picking, closing) => {
            const el = picking ? this.pickSearchRef.el : closing ? this.noteRef.el : null;
            if (el) { el.focus(); }
        }, () => [!!this.state.picker, !!this.state.closing]);
    }

    // ================================================================ read
    /** The numbers and the strip's notes (counted over every question the
     *  reader may see, whatever is filtered). */
    async load() {
        this.state.loading = true;
        this.state.failed = false;
        try {
            this.state.d = await this.orm.call("pb.ask.hr", "get_head", []);
        } catch (e) {
            console.warn("pb_ask_hr: the board could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loading = false;
        }
    }

    /** One page of cards for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.failed = true;
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.cards.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.ask.hr", "get_ticket_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.cards = more ? [...this.state.cards, ...d.cards] : d.cards;
            this.state.total = d.total;
            if (!more) {
                this.state.stepCounts = d.steps || {};
                // a card the new filters no longer show is not selected (R6)
                const here = new Set(d.cards.map((c) => c.id));
                const sel = {};
                for (const id of Object.keys(this.state.sel)) {
                    if (here.has(Number(id))) { sel[id] = true; }
                }
                this.state.sel = sel;
            }
            this.state.listLoaded = true;
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                console.warn("pb_ask_hr: the questions could not be listed", e);
                this.notif.add(_t("The questions could not be listed. Try again in a moment."), { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() { return this.state.cards.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.cards.length); }

    /** The numbers, the counts and the cards, in place. */
    async reload() {
        await Promise.all([this.load(), this.kit.refresh()]);
    }

    get d() { return this.state.d || { counts: {}, categories: [] }; }
    get counts() { return this.d.counts || {}; }
    get canAct() { return !!this.d.can_act; }

    // ============================================================ numbers
    /** What each figure means as a filter: the same filters as its view. */
    get glanceFilters() {
        if (this.canAct) {
            return {
                new: { step: ["new"] },
                with_hr: { step: ["with_hr"] },
                answered: { step: ["answered"] },
                week: this.d.week_start ? { answered: { from: this.d.week_start } } : null,
            };
        }
        return {
            new: { step: ["new", "with_hr"] },
            answered: { step: ["answered"] },
            closed: { step: ["closed"] },
        };
    }

    glancePick(key) {
        const f = this.glanceFilters[key];
        return f ? () => this.kit.toggleFilters(f) : null;
    }

    get glance() {
        const c = this.counts;
        const d = this.d;
        if (this.canAct) {
            const med = d.median || {};
            return [
                { key: "new", n: c.new || 0, label: _t("new"),
                  tone: d.new_late ? "amber" : "", run: this.glancePick("new") },
                { key: "with_hr", n: c.with_hr || 0, label: _t("with HR"),
                  tone: "", run: this.glancePick("with_hr") },
                { key: "answered", n: c.answered || 0, label: _t("waiting on the person"),
                  tone: "", run: this.glancePick("answered") },
                { key: "week", n: d.answered_week || 0, label: _t("answered this week"),
                  tone: "", run: this.glancePick("week") },
                { key: "median", n: med.words || "–",
                  label: _t("median first reply (last 30 days)"),
                  tone: "", run: null, zero: !med.words },
            ];
        }
        return [
            { key: "new", n: (c.new || 0) + (c.with_hr || 0), label: _t("waiting for HR"),
              tone: "", run: this.glancePick("new") },
            { key: "answered", n: c.answered || 0, label: _t("answered, your turn"),
              tone: c.answered ? "amber" : "", run: this.glancePick("answered") },
            { key: "closed", n: c.closed || 0, label: _t("closed"),
              tone: "", run: this.glancePick("closed") },
        ];
    }

    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters)) {
            if (f && this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    get stepsLabel() { return _t("Where every question is"); }

    /** The keyboard line under the cards: [key cap, what it does]. */
    get keys() {
        const k = [["↑ ↓", _t("move")], ["Enter", _t("open")]];
        if (this.canAct) {
            k.push(["Space", _t("select")], ["T", _t("take it")], ["H", _t("hand to…")]);
        }
        k.push(["/", _t("find")]);
        return k;
    }

    get stepDefs() {
        return [
            { key: "new", title: _t("New") },
            { key: "with_hr", title: _t("With HR") },
            { key: "answered", title: _t("Answered") },
            { key: "closed", title: _t("Closed") },
        ];
    }

    /** The strip: counts follow the panel's other filters (from the server);
     *  a step is lit while it is the only step ticked in "Where it is". */
    get steps() {
        const c = this.state.stepCounts || {};
        const d = this.d;
        const ticked = this.kit.values("step");
        return this.stepDefs.map((st, i) => {
            const n = c[st.key] || 0;
            let flag = "";
            let sub = "";
            if (this.canAct && st.key === "new" && d.new_late) {
                flag = d.new_late === 1 ? _t("1 waiting over 2 working days")
                    : _t("%s waiting over 2 working days", d.new_late);
            }
            if (this.canAct && st.key === "with_hr" && d.mine_with_hr) {
                sub = d.mine_with_hr === 1 ? _t("1 is yours") : _t("%s are yours", d.mine_with_hr);
            }
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count: n,
                countLabel: n === 1 ? _t("1 question") : _t("%s questions", n),
                sub, flag, flagTone: "",
                mine: st.key === "with_hr" && !!d.mine_with_hr,
                on: ticked.length === 1 && ticked[0] === st.key,
            };
        });
    }

    /** Press a step: that step only, the other filters kept; press the lit
     *  step again: every open step, as the board starts. */
    pickStep(key) {
        const lit = this.kit.values("step");
        const next = { ...this.kit.filters };
        next.step = lit.length === 1 && lit[0] === key ? [...OPEN] : [key];
        this.kit.setFilters(next, { search: this.kit.search });
        this.state.sel = {};
    }

    // ============================================================ filters
    get filtered() {
        return !!(this.kit.activeCount || this.kit.search);
    }

    clearFilters() { this.kit.toggleFilters({}); }

    catIcon(key) { return ic(CATEGORY_ICON[key] || "helpCircle", 13); }

    /** The cards the panel produced (one page or several). */
    get cards() { return this.state.cards; }

    /** A key that changes with the filters, so the list slides in once. */
    get listKey() {
        return JSON.stringify(this.kit.filters) + ":" + this.kit.search;
    }

    // ======================================================== empty states
    /** Which empty state, if any: "calm" (nothing open), "never" (an
     *  employee who has asked nothing), "nomatch" (filters), "step". */
    get emptyKind() {
        if (this.cards.length) { return ""; }
        if (!this.canAct && !this.d.total) { return "never"; }
        const steps = this.kit.values("step");
        const onlyOpen = steps.length && steps.every((s) => OPEN.includes(s));
        const others = Object.keys(this.kit.filters).filter((k) => k !== "step" && this.kit.isActive(k));
        if (onlyOpen && !others.length && !this.kit.search && !this.d.open_total) {
            return "calm";
        }
        if (others.length || this.kit.search) { return "nomatch"; }
        return "step";
    }

    get stepEmptyWords() {
        const steps = this.kit.values("step");
        const st = steps.length === 1 ? this.stepDefs.find((s) => s.key === steps[0]) : null;
        return st ? _t("Nothing at %s right now.", st.title) : _t("Nothing here right now.");
    }

    // ========================================================== selection
    get selIds() { return Object.keys(this.state.sel).map(Number); }
    get selCount() { return this.selIds.length; }
    isSel(c) { return !!this.state.sel[c.id]; }

    toggleSel(c) {
        if (!this.canAct) { return; }
        const sel = { ...this.state.sel };
        if (sel[c.id]) { delete sel[c.id]; } else { sel[c.id] = true; }
        this.state.sel = sel;
    }

    get allSel() {
        return this.cards.length > 0 && this.cards.every((c) => this.state.sel[c.id]);
    }

    /** Every card shown (the pages loaded), never one the filters hide (R6). */
    toggleAll() {
        if (this.allSel) { this.state.sel = {}; return; }
        const sel = {};
        for (const c of this.cards) { sel[c.id] = true; }
        this.state.sel = sel;
    }

    clearSel() { this.state.sel = {}; }

    get selWords() {
        const n = this.selCount;
        return n === 1 ? _t("1 selected") : _t("%s selected", n);
    }

    // ============================================================ keyboard
    onListKeydown(ev) {
        if (railKeydown(ev, ".pbah-c")) { return; }
        const el = ev.target && ev.target.closest && ev.target.closest(".pbah-c");
        if (!el || ev.target !== el) { return; }
        const card = this.cards.find((c) => String(c.id) === el.dataset.id);
        if (!card) { return; }
        const key = ev.key;
        if (key === "Enter") {
            ev.preventDefault();
            this.open(card);
        } else if (key === " " && this.canAct) {
            ev.preventDefault();
            this.toggleSel(card);
        } else if ((key === "t" || key === "T") && this.canTake(card)) {
            ev.preventDefault();
            this.take([card.id]);
        } else if ((key === "h" || key === "H") && this.canHand(card)) {
            ev.preventDefault();
            this.openPicker([card.id]);
        }
    }

    onRootKeydown(ev) {
        const tag = (ev.target && ev.target.tagName) || "";
        const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(tag);
        if (ev.key === "Escape") {
            if (this.state.picker) { this.state.picker = null; return; }
            if (this.state.closing) { this.state.closing = null; return; }
            if (this.selCount && !typing) { this.clearSel(); }
        }
        // "/" is the filter panel's now: it focuses the list's search box
    }

    // ============================================================== doors
    /** Coming back from the form lands on this tab, not on Pulse: the Home
     *  action the breadcrumb restores is told which lens to raise. */
    rememberHere() {
        const ctrl = this.action.currentController;
        const act = ctrl && ctrl.action;
        if (act && act.type === "ir.actions.client") {
            const ctx = { ...(act.context || {}), pb_lens: "askhr" };
            delete ctx.pb_focus;
            act.context = ctx;
        }
    }

    open(card) {
        if (!this.canAct) {
            // The person's own page: the conversation, the reply box, "That
            // solved it". The backend form is read-only for them.
            this.action.doAction({
                type: "ir.actions.act_url", url: "/my/ask-hr/" + card.id, target: "self",
            });
            return;
        }
        this.rememberHere();
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Ask HR"),
            res_model: MODEL,
            res_id: card.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    askNew() {
        this.action.doAction({
            type: "ir.actions.act_url", url: "/my/ask-hr/new", target: "self",
        });
    }

    /** The native list (the off-menu fallback): open questions, or the
     *  closed ones when the board says it shows only the latest of them. */
    openList(closed = false) {
        this.rememberHere();
        this.action.doAction("pb_ask_hr.action_pb_ask_hr_ticket", {
            viewType: "list",
            additionalContext: closed
                ? { search_default_filter_open: 0, search_default_filter_closed: 1 }
                : {},
        });
    }

    // ============================================================ actions
    canTake(c) { return this.canAct && c.state !== "closed" && !c.owner_id; }
    canHand(c) { return this.canAct && c.state !== "closed"; }

    async act(verb, payload) {
        if (this.state.busy) { return false; }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.ask.hr", "act", [verb, payload]);
            this.notif.add(res.message, { type: "success" });
            this.state.sel = {};
            await this.reload();
            return true;
        } catch (e) {
            const msg = (e && e.data && e.data.message) || _t("That could not be done. Nothing has changed.");
            this.notif.add(msg, { type: "danger" });
            return false;
        } finally {
            this.state.busy = false;
        }
    }

    take(ids) { return this.act("take", { ids }); }

    async openPicker(ids) {
        if (!ids.length) { return; }
        this.state.picker = { ids, users: null, q: "" };
        try {
            const users = await this.orm.call("pb.ask.hr", "get_owners", []);
            if (this.state.picker) { this.state.picker.users = users; }
        } catch (e) {
            this.state.picker = null;
            this.notif.add(_t("The HR team could not be read just now."), { type: "danger" });
        }
    }

    get pickerTitle() {
        const p = this.state.picker;
        if (!p) { return ""; }
        if (p.ids.length === 1) {
            const c = this.cards.find((x) => x.id === p.ids[0]);
            return _t("Hand %s to…", c ? c.number : "");
        }
        return _t("Hand %s questions to…", p.ids.length);
    }

    get pickerUsers() {
        const p = this.state.picker;
        if (!p || !p.users) { return []; }
        const q = (p.q || "").trim().toLowerCase();
        return q ? p.users.filter((u) => u.name.toLowerCase().includes(q)) : p.users;
    }

    onPickerSearch(ev) { this.state.picker.q = ev.target.value; }
    onPickerKeydown(ev) {
        // From the search box, the down arrow walks into the list.
        if (ev.key === "ArrowDown" && ev.target === this.pickSearchRef.el) {
            const first = ev.currentTarget.querySelector(".pbah-pick__b");
            if (first) { ev.preventDefault(); first.focus(); }
            return;
        }
        railKeydown(ev, ".pbah-pick__b");
    }

    async handTo(user) {
        const ids = this.state.picker.ids;
        this.state.picker = null;
        await this.act("hand", { ids, user_id: user.id });
    }

    openClose(ids) {
        if (!ids.length) { return; }
        this.state.closing = { ids, note: "", tell: true };
    }

    get closingTitle() {
        const n = this.state.closing ? this.state.closing.ids.length : 0;
        return n === 1 ? _t("Close this question") : _t("Close %s questions", n);
    }

    onCloseNote(ev) { this.state.closing.note = ev.target.value; }
    setTell(v) { this.state.closing.tell = v; }

    async confirmClose() {
        const c = this.state.closing;
        this.state.closing = null;
        await this.act("close", { ids: c.ids, note: c.note, tell: c.tell });
    }

    // ============================================================== cards
    ownerWords(c) {
        if (c.owner_id) { return c.mine ? _t("You") : c.owner; }
        return _t("Nobody has it yet");
    }

    avatar(c) { return "/web/image/hr.employee.public/" + c.employee_id + "/avatar_128"; }
    ownerAvatar(c) { return "/web/image/res.users/" + c.owner_id + "/avatar_128"; }

    cardTitle(c) {
        return _t("Asked %s ago", c.age);
    }
}

registry.category(HOME_LENSES).add("askhr", {
    key: "askhr",
    icon: "messageSquare",
    label: _t("Ask HR"),
    Component: PbAskHrLens,
    // Every internal user: an employee sees their own questions (record
    // rule), the HR team sees the queue.
    groups: ["base.group_user"],
}, { sequence: 15 });

/* ---------------------------------------------------------- command bar --- */
registry.category("pb_hub_palette").add("askhr_home", {
    id: "askhr_home",
    label: _t("Ask HR"),
    sublabel: _t("Home"),
    icon: "messageSquare",
    requires: "pb_home_hub",
    action: { xmlid: "pb_home_hub.action_pb_home_hub", lens: "askhr" },
    keywords: ["ask hr", "hr request", "hr question", "hỏi nhân sự"],
}, { sequence: 2050 });
