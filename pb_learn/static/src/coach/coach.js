/** @odoo-module **/
/* =============================================================================
   The Payobook Coach — always on, on every screen.

   THE SHAPE, AND WHY
   ------------------
   A drawer, not a modal. You reach for the Coach *because* you are stuck on
   the screen behind it, so that screen has to stay readable and clickable: no
   dimming, no backdrop, no focus trap. This is the difference between help you
   can use and help you have to dismiss before you can act on it.

   WHAT IT WILL NOT DO
   -------------------
   It never claims to have acted, and it has no way to act: every answer is
   assembled on the SERVER out of blocks an author wrote, and the only controls
   an answer can render are its own — point at a control, say it more simply, open the
   lesson, ask something else. There is no path from a question to a product
   method. `tests/test_coach.py` asserts that rather than trusting it.

   It never invents a domain fact either. Every answer is retrieved from
   something an author wrote — since Phase 1a the static content plane rather
   than a database record — with ONE fenced exception added in Phase D: when a
   tenant switches the composer on, an answer may be COMPOSED by a model from
   this module's own tutorial text — never from database records — and it
   arrives badged as such so the reader knows which kind of answer they hold.
   Off by default; with the flag off this file behaves exactly as it did in
   Phase C.

   WHAT IT SENDS ABOUT YOU
   -----------------------
   The question text is never stored unless BOTH the tenant has switched
   collection on AND you have said yes to the prompt in this drawer. Until
   then the only thing logged is which screen you were on and whether there
   was an answer — see `ask()` below, where the Phase A2 ruling is spelled
   out and still holds as the default.
   ========================================================================== */
import { Component, markup, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

import { RT, T, tx, esc, ic, SP } from "../engine/runtime";
/* The glossary hovercard (LEARNOS Phase 2). Answer blocks are the one
   place in the drawer that inserts authored prose RAW, so they are the
   one place `gtx` replaces `tx`. */
import { gtx, glossaryOpen, setGlossary, installGlossary, closeGlossary }
    from "../engine/glossary";
import { loadContent, composeScreens } from "../content/content_loader";
import { flashRing } from "../engine/spotlight";
import { calcHTML, calcKpiHTML } from "../engine/visuals";
import { markLauncherStack, maybeGreet, maybeWelcome } from "./first_login";
import { registerLessonRows } from "../hub/learn_palette";

/* Shared with the Journey: one language preference for the whole system. */
const LOCAL_PREFS = "pbLearnPrefs";

/* The only actions an answer may carry. Anything else is a bug, and the test
   compares the rendered HTML against exactly this set. */
export const COACH_ACTIONS = new Set([
    "c-close", "c-ask", "c-suggest", "c-show", "c-simpler", "c-lesson", "c-back",
    "c-lang",
    // Phase 1b. "Show me how" starts a scenario. It reaches no product method
    // either: the engine it hands off to points, waits and narrates, and the
    // one press it is capable of making is on an unguarded control in Watch.
    "c-scenario",
    // Phase D2. Two buttons, one decision, asked once. Neither reaches a
    // product method — they write this learner's own consent row and nothing
    // else, which is why they belong in this set rather than outside it.
    "c-consent-yes", "c-consent-no",
    // LEARNOS Phase 4. "Explain this screen" is a READ: one RPC to
    // learn.intent.explain_screen, which composes an answer out of the content
    // plane. It reaches no product method either, which is why it is in this
    // set rather than an exception to it. The Watch / Try buttons an answer may
    // now carry are NOT new actions — they are `c-scenario`, the control the
    // "Show me how" rows have used since Phase 1b.
    "c-explain",
    // LEARNOS Phase 5. Practice mode opens the Journey's free-roam sandbox —
    // the same client action the "Open the lesson" button already opens, with
    // one context key on it. It reaches no product method for the same reason
    // `c-lesson` does not: the only thing on the other side of it is a replica.
    "c-practice",
    // LEARNOS Phase 6. "Continue" opens the station the server suggested —
    // the same door `c-lesson` uses, with the key the bootstrap already sent.
    // The SUGGESTION is a server computation over this learner's own progress
    // rows; nothing about it reaches a product method or a language model.
    "c-continue",
    // LEARN v3 — one helper. "c-tab" switches between Guide me, Ask and
    // Practice inside this drawer; "c-askdata" hands a question the guide
    // could not answer to the Ask tab. Neither reaches a product method: the
    // Ask tab is PayAI's own chat, which has its own server-side fences, and
    // the hand-off only puts the question text into its box and presses its
    // send — exactly what the learner would do by retyping it.
    "c-tab", "c-askdata",
    // LEARN v3 — the moment card above the helper button: a milestone note,
    // the month-end nudge, or a first-visit note. Each either opens something
    // this drawer already opens (a lesson, a walkthrough, "explain this
    // screen") or dismisses the card. None reaches a product method; the only
    // writes are this learner's own learning-log rows.
    "c-mgo", "c-mok", "c-fvexplain", "c-fvwatch", "c-mlater", "c-mewatch", "c-meskip",
]);

/* LEARN v3 — ONE HELPER, NOT TWO BUTTONS.

   The Coach and PayAI used to be two floating buttons stacked in the corner,
   sharing no code and no memory. Now this drawer is the only launcher, and
   PayAI's chat is drawn INSIDE it as the "Ask" tab.

   Two registries carry that, and the dependency direction is the reason there
   are two: neither module depends on the other, so neither may import the
   other.

     pb_helper_host — this module says "the one helper is here". PayAI reads it
                      at mount time and, when it is set, draws no pill and no
                      modal of its own (assets are all loaded before the web
                      client mounts, so the answer is stable by then).
     pb_helper_tabs — PayAI registers its embedded chat under "ask". Absent
                      module, absent tab: the drawer shows two tabs and says
                      nothing about a third. */
export const HELPER_TABS = "pb_helper_tabs";
export const HELPER_HOST = "pb_helper_host";
registry.category(HELPER_HOST).add("orb", { module: "pb_learn" });

/* Which tab the drawer opens on. Guide, always: the person pressed the button
   because of the screen in front of them. */
const TAB_ORDER = ["guide", "ask", "practice"];

/* LEARN v3 — moments. Screens this browser has already been told about, and
   the month the month-end nudge was skipped for (shared with the map). */
const SEEN_SCREENS = "pbLearnSeenScreens";
const MONTH_END_SKIP = "pbLearnMonthEndSkip";
const MONTH_END_TODAY = "pbLearnMonthEndShown";
/* Milestones are asked of the server at most this often. */
const MILESTONE_EVERY_MS = 60000;
const MILESTONE_COPY = {
    m_employee: ["msEmployeeT", "msEmployeeB"],
    m_run: ["msRunT", "msRunB"],
    m_submitted: ["msSubmittedT", "msSubmittedB"],
    m_done: ["msDoneT", "msDoneB"],
};

function lsGet(key, fallback) {
    try {
        const v = window.localStorage.getItem(key);
        return v === null ? fallback : v;
    } catch {
        return fallback;
    }
}

function lsSet(key, value) {
    try {
        window.localStorage.setItem(key, value);
    } catch {
        // A locked-down profile only loses the memory of a dismissal.
    }
}

export class CoachHost extends Component {
    static template = "pb_learn.CoachHost";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.sc = useService("learn.scenario");
        this.inputRef = useRef("input");

        this.state = useState({
            open: false,
            ready: false,
            screen: null,        // content screen key, or null when off-map
            busy: false,
            question: "",
            answer: null,        // the payload from learn.intent.ask
            simpler: false,
            history: [],         // {q, answered} — so "ask another" keeps context
            lang: RT.lang,
            // Phase D2 — question mining. `askConsent` is only ever set true
            // by the SERVER saying both that collection is on and that this
            // learner has not been asked yet.
            askConsent: false,
            pendingQ: null,      // {q, matched} held until a yes; dropped on a no
            // LEARN v3 — the tab showing, and a question handed from the
            // guide to the Ask tab. `handoff.id` changes on every hand-off so
            // the Ask tab can tell a new question from a re-render.
            tab: "guide",
            handoff: null,
            lastQ: "",
            // LEARN v3 — the one moment card showing, or null.
            moment: null,
        });
        this._milestoneAt = 0;
        // Passed to the Ask tab as a prop. A stable function, made once, so
        // the tab is not re-rendered by a new identity on every drawer render.
        this.closeHelper = () => this.close();

        this.bundle = null;
        this._onKey = this._onKey.bind(this);
        // LEARN v3. Whether this person may use the Ask tab, asked once. A tab
        // whose every question fails on an access rule is a dead end.
        this.askAllowed = false;

        onWillStart(async () => {
            this._restoreLang();
            try {
                const reg = registry.category(HELPER_TABS);
                const groups = reg.contains("ask") ? (reg.get("ask").groups || []) : null;
                this.askAllowed = groups === null ? false : !groups.length
                    || (await Promise.all(groups.map((g) => user.hasGroup(g)))).some(Boolean);
            } catch {
                this.askAllowed = false;
            }
            // Fetched once. The drawer must open instantly — a learner who is
            // stuck does not want to watch a spinner. Since Phase 1a the
            // screens, their chips and the chrome come from the static content
            // plane (shared with the Journey: one fetch for the page) and the
            // one RPC carries only the matchers, the slots and the mining
            // switch. The composed shape is what `coach_bundle` returned.
            try {
                const [content, runtime] = await Promise.all([
                    loadContent(),
                    this.orm.call("learn.runtime", "bootstrap", []),
                ]);
                this.bundle = {
                    screens: composeScreens(content, runtime),
                    global_suggest: content.global_suggest || [],
                    chrome: content.chrome || {},
                    glossary: content.glossary || [],
                    tokens: runtime.tokens || {},
                    collect_questions: !!runtime.collect_questions,
                    // LEARNOS Phase 6. Rides along with the bootstrap the
                    // drawer already fetches, so the "not sure what to ask"
                    // state can offer the same next step the Journey's map
                    // offers without a second round trip — and offers nothing
                    // at all when the tenant flag is off, which is what an
                    // empty payload means.
                    next_best: runtime.next_best || {},
                    // Which of the two first-run greetings this database gets.
                    // A DATABASE property, asked of the company the same way a
                    // live capstone asks it — see maybeWelcome.
                    demo_world: !!runtime.demo_world,
                    // LEARN v3 — for the next-step card's title. The key alone
                    // is not something a learner can read.
                    stations: content.stations || [],
                    // LEARN v3 — the month-end date, for the Dashboard nudge.
                    path: runtime.path || {},
                };
                // LEARN v3 — lessons in the ⌘K search, from the same content.
                try {
                    registerLessonRows(content);
                } catch (e) {
                    console.warn("pb_learn: lesson rows not added to the search", e);
                }
                // Same fetch, no second round trip: the scenario service reads
                // the memoised content plane the drawer has just resolved.
                await this.sc.load();
                RT.tokens = this.bundle.tokens || RT.tokens;
                RT.chrome = this.bundle.chrome || RT.chrome;
                // The Coach is mounted on EVERY screen, so it is usually the
                // surface that installs the hovercard — the Journey does the
                // same thing and whichever loads first wins.
                setGlossary(this.bundle.glossary);
                installGlossary();
                this.state.ready = true;
            } catch {
                // A Coach that cannot load must not break the screen it sits on.
                this.state.ready = false;
            }
        });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveScreen());
        onMounted(() => {
            this._resolveScreen();
            // CAPTURE PHASE, and it is not a style choice. "document, not
            // window" was necessary and NOT sufficient: Odoo's hotkey service
            // stops propagation at document-BUBBLE, so a bubble listener here
            // is silently dead in real Chrome while synthetic dispatch in a
            // test still works — measured on the Phase 2+3 deploy, on the
            // welcome card's Escape, and the reason first_login.js has bound
            // capture ever since. The removal has to match the phase or the
            // listener is never removed at all.
            document.addEventListener("keydown", this._onKey, true);
            // LEARN v3. The corner holds one button now, so it sits in the
            // bottom slot. A body class rather than a runtime measurement:
            // coach.scss places the launcher off it.
            document.body.classList.add("lrn-one-helper");
            // Two pieces of CHROME the Coach happens to be the right host for,
            // because it is the one component mounted on every screen. Both
            // live in first_login.js; neither can throw, and neither is allowed
            // to delay the drawer.
            markLauncherStack(this.env);
            // TWO first-run greetings, one database each. The demo world gets
            // the Journey map with a pulse; a real tenant gets the welcome
            // card. Neither can fire on the other's database, and a bundle
            // that failed to load gets neither — the card would otherwise
            // render its own chrome keys as its text.
            maybeGreet(this.env, this.orm, this.action);
            if (this.bundle) {
                maybeWelcome(this.env, this.orm, this.sc, this.bundle.demo_world);
            }
        });
        onWillUnmount(() => {
            document.removeEventListener("keydown", this._onKey, true);
            document.body.classList.remove("lrn-one-helper");
            // The card is on document.body, not in this component's tree.
            closeGlossary();
        });
    }

    // ---------------------------------------------------------------- context
    /** Which learn screen is showing, from the action manager — the same
     *  signal SidebarHost already resolves on. */
    _resolveScreen() {
        const controller = this.action.currentController;
        const action = controller?.action;
        const screens = this.bundle?.screens || [];
        // TWO PASSES, exactly as SidebarHost._resolve does it: exact matches
        // (tag, xml-id) across ALL screens first, and only then the broad model
        // match. One pass with || inside is order-dependent and wrong here —
        // Lead Analysis is a crm.lead pivot, so it matched Contacts' model
        // matcher and the Coach confidently grounded on the wrong screen.
        // Pass 0: the leaf whose OWN action this is. A parent leaf lists its
        // children's actions so the SIDEBAR can highlight the parent — correct
        // there, wrong here: it grounded Cash In Transit on AR Management.
        const own = action ? screens.find((s) =>
            (action.tag && s.own_tag && s.own_tag === action.tag)
            || (action.xml_id && s.own_xmlid && s.own_xmlid === action.xml_id)
        ) : null;
        const exact = own || (action ? screens.find((s) =>
            (action.tag && (s.action_tags || []).includes(action.tag))
            || (action.xml_id && (s.action_xmlids || []).includes(action.xml_id))
        ) : null);
        const byModel = !exact && action?.res_model
            ? screens.find((s) => (s.models || []).includes(action.res_model))
            : null;
        const found = exact || byModel;
        const key = found ? found.key : null;
        if (key !== this.state.screen) {
            this.state.screen = key;
            // LEARN v3. A moment belongs to the screen it was shown on.
            this.state.moment = null;
            setTimeout(() => this._pickMoment(), 900);
            // A question asked about the previous screen is not an answer about
            // this one. Clear rather than leave something subtly wrong on show.
            this.state.answer = null;
            this.state.simpler = false;
        }
    }

    get screenInfo() {
        return (this.bundle?.screens || []).find((s) => s.key === this.state.screen) || null;
    }

    get covered() {
        return !!this.screenInfo;
    }

    // ------------------------------------------------------------- behaviour
    _onKey(ev) {
        const typing = /^(INPUT|TEXTAREA)$/.test(ev.target.tagName)
            || ev.target.isContentEditable;
        if (ev.key === "?" && !typing && !this.state.open) {
            ev.preventDefault();
            this.toggle();
        } else if (ev.key === "Escape" && this.state.open) {
            // THE LADDER, ONE RUNG AT A TIME. A hovercard open over the drawer
            // closes first and this stands down for it — otherwise one Escape
            // would take both, and which one it took would depend on which
            // surface finished loading first (both listeners are on document
            // at capture now).
            if (glossaryOpen()) {
                return;
            }
            // Only closes the Coach. The screen behind it keeps its own Escape.
            ev.stopPropagation();
            this.close();
        }
    }

    toggle() {
        this.state.open = !this.state.open;
        this.state.moment = null;
        if (this.state.open) {
            this._log("coach_open");
            setTimeout(() => this.inputRef.el?.focus(), 60);
        }
    }

    // ---------------------------------------------------- LEARN v3 moments
    /** Choose at most one moment for the screen the learner is on.
     *
     *  In this order, because it is the order of usefulness: something the
     *  COMPANY just achieved, then the month-end date, then "first time on
     *  this screen". Nothing while the drawer is open, a walkthrough is
     *  running, the lesson map is open or the first-run welcome card is up. */
    async _pickMoment() {
        if (!this.bundle || this.state.open || this.state.moment) {
            return;
        }
        if (this.sc.state.active || document.body.classList.contains("lrn-open")
                || document.querySelector(".lrn-welcome")) {
            return;
        }
        const now = Date.now();
        if (now - this._milestoneAt > MILESTONE_EVERY_MS) {
            this._milestoneAt = now;
            try {
                const list = await this.orm.call("learn.path", "milestones", []);
                const m = (list || []).find((x) => MILESTONE_COPY[x.key]);
                if (m && !this.state.open) {
                    this.state.moment = { kind: "milestone", key: m.key, station: m.station };
                    return;
                }
            } catch {
                // A moment is a courtesy; its failure is silent.
            }
        }
        const me = (this.bundle.path && this.bundle.path.month_end) || {};
        const today = new Date().toISOString().slice(0, 10);
        if (this.state.screen === "dashboard" && me.cutoff
                && lsGet(MONTH_END_SKIP, "") !== me.month
                && lsGet(MONTH_END_TODAY, "") !== today) {
            lsSet(MONTH_END_TODAY, today);
            this.state.moment = { kind: "monthend", days: me.days || 0, month: me.month };
            return;
        }
        const screen = this.screenInfo;
        if (screen) {
            let seen = [];
            try {
                seen = JSON.parse(lsGet(SEEN_SCREENS, "[]")) || [];
            } catch {
                seen = [];
            }
            if (!seen.includes(screen.key)) {
                seen.push(screen.key);
                lsSet(SEEN_SCREENS, JSON.stringify(seen));
                const watch = this.screenScenarios.find((x) => (x.modes || []).includes("watch"));
                this.state.moment = { kind: "first", watch: watch ? watch.key : "" };
                this._log("first_visit", screen.key);
            }
        }
    }

    get momentHTML() {
        void this.state.lang;
        const m = this.state.moment;
        if (!m || this.state.open) {
            return markup("");
        }
        let icon = "sparkles";
        let title = "";
        let body = "";
        let tools = "";
        if (m.kind === "milestone") {
            const [t, b] = MILESTONE_COPY[m.key];
            icon = "check-circle";
            title = T(t);
            body = T(b);
            tools = `<button class="lrn-btn sm pri" data-act="c-mgo">${esc(T("msGo"))}</button>
                <button class="lrn-btn sm ghost" data-act="c-mok">${esc(T("msOk"))}</button>`;
        } else if (m.kind === "monthend") {
            icon = "calendar";
            title = m.days <= 0 ? T("monthEndToday")
                : `${T("monthEndIn")}${SP}${m.days}${SP}${T(m.days === 1 ? "dayWord" : "daysWord")}`;
            body = T("monthEndBody");
            tools = `${this._offers("sc_payslips", "watch")
                ? `<button class="lrn-btn sm pri" data-act="c-mewatch">${ic("play")}${esc(T("scWatch"))}</button>` : ""}
                <button class="lrn-btn sm ghost" data-act="c-meskip">${esc(T("monthEndSkip"))}</button>`;
        } else {
            const s = this.screenInfo;
            if (!s) {
                return markup("");
            }
            icon = "compass";
            title = `${T("fvOn")}${SP}${tx(s.name)}?`;
            body = tx(s.blurb);
            tools = `<button class="lrn-btn sm pri" data-act="c-fvexplain">${ic("info")}${esc(T("explainScreen"))}</button>
                ${m.watch ? `<button class="lrn-btn sm" data-act="c-fvwatch">${ic("play")}${esc(T("scWatch"))}</button>` : ""}
                <button class="lrn-btn sm ghost" data-act="c-mlater">${esc(T("fvLater"))}</button>`;
        }
        return markup(`<div class="lrn-hmoment ${m.kind}" role="status">
            <span class="lrn-momentic">${ic(icon)}</span>
            <div class="lrn-momentmain">
                <b>${esc(title)}</b>
                <p>${esc(body)}</p>
                <div class="lrn-ctools">${tools}</div>
            </div>
            <button class="lrn-momentx" data-act="c-mlater" aria-label="${esc(T("fvLater"))}">${ic("x")}</button>
        </div>`);
    }

    async _momentAct(act) {
        const m = this.state.moment;
        this.state.moment = null;
        if (!m) {
            return;
        }
        if (m.kind === "milestone") {
            try {
                await this.orm.call("learn.path", "ack_milestone", [m.key]);
            } catch {
                // Told again next time, which is the right way to fail.
            }
            if (act === "c-mgo" && m.station) {
                this.openSuggested(m.station);
            }
            return;
        }
        if (act === "c-meskip" && m.month) {
            lsSet(MONTH_END_SKIP, m.month);
        } else if (act === "c-mewatch") {
            this.startScenario("sc_payslips", "watch", "");
        } else if (act === "c-fvexplain") {
            this.state.open = true;
            this._log("coach_open");
            this.explainScreen();
        } else if (act === "c-fvwatch" && m.watch) {
            this.startScenario(m.watch, "watch", "");
        }
    }

    // ------------------------------------------------------------ LEARN v3
    /** PayAI's embedded chat, when that module is installed. */
    get askTab() {
        const reg = registry.category(HELPER_TABS);
        return this.askAllowed && reg.contains("ask") ? reg.get("ask") : null;
    }

    /** The tab strip. Reads `state.lang` so a language flip relabels it —
     *  the strip is in the template, outside `bodyHTML`. */
    get tabs() {
        void this.state.lang;
        const label = { guide: "tabGuide", ask: "tabAsk", practice: "tabPractice" };
        const icon = { guide: "compass", ask: "message-circle", practice: "flask" };
        return TAB_ORDER
            .filter((k) => k !== "ask" || this.askTab)
            .map((k) => ({ key: k, label: T(label[k]), icon: icon[k] }));
    }

    setTab(key) {
        if (!TAB_ORDER.includes(key) || (key === "ask" && !this.askTab)) {
            return;
        }
        this.state.tab = key;
        this._log("coach_tab", key);
        if (key === "guide") {
            setTimeout(() => this.inputRef.el?.focus(), 60);
        }
    }

    /** Hand the last question to the Ask tab and send it there. */
    askData() {
        const q = (this.state.lastQ || this.state.question || "").trim();
        if (!this.askTab) {
            return;
        }
        this.state.handoff = q ? { text: q, id: Date.now() } : null;
        this.state.tab = "ask";
    }

    /** "On: <screen>" in the header. The content plane's name when it covers
     *  the screen, the action's own name when it does not — every screen gets
     *  named, which is the point of saying where the helper thinks you are. */
    get screenLabel() {
        void this.state.lang;
        const s = this.screenInfo;
        if (s) {
            return tx(s.name);
        }
        const action = this.action.currentController?.action;
        return (action && action.name) || "";
    }

    get onScreenText() {
        void this.state.lang;
        return T("onScreen");
    }

    close() {
        this.state.open = false;
        // Reopening starts fresh. A stale answer from ten minutes and two
        // screens ago is worse than the suggestions, because it looks like a
        // reply to whatever the person is stuck on NOW.
        this.state.answer = null;
        this.state.simpler = false;
        this.state.question = "";
        // A question held pending a consent answer does not survive the
        // drawer closing. Closing without answering is not a yes, and text
        // kept across a close would eventually be stored against a question
        // the person had moved on from.
        this.state.askConsent = false;
        this.state.pendingQ = null;
        // LEARN v3. Reopening starts on the Guide tab, for the same reason a
        // stale answer is cleared: the person is asking about NOW.
        this.state.tab = "guide";
        this.state.handoff = null;
    }

    onInput(ev) {
        this.state.question = ev.target.value;
    }

    onSubmit(ev) {
        ev.preventDefault();
        this.ask(this.state.question);
    }

    async ask(question) {
        const q = (question || "").trim();
        if (!q || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.simpler = false;
        try {
            const answer = await this.orm.call(
                "learn.intent", "ask", [q, this.state.screen, RT.lang]);
            this.state.answer = answer;
            this.state.lastQ = q;
            this.state.history.push({ q, answered: !!answer.matched });
            // NEVER the question text. health_learn logs the first 40
            // characters of an unanswered question, which is a good content
            // signal and a bad privacy decision: a help box on a payroll system
            // receives "why is Nguyễn Thị Mai's net only 4m" — a named employee
            // and their pay, landing in a table with no retention policy and no
            // way for that person to know it is there.
            //
            // What survives is the signal that is actually used: `screen` is
            // logged alongside every event, so coach_miss still answers "which
            // screens do people get stuck on", which is what drives the next
            // piece of content. WHICH question they asked becomes a Phase D
            // opt-in on its own deletable model.
            this._log(answer.matched ? "coach_hit" : "coach_miss", answer.key || "");
            await this._maybeStore(q, !!answer.matched);
        } catch {
            this.state.answer = null;
        } finally {
            this.state.busy = false;
        }
    }

    /** Phase D2 — store the question, or ask for permission to, or neither.
     *
     *  Three states and only one of them sends text. The server re-checks
     *  both gates in `learn.question.record`, so what happens here is a
     *  courtesy that saves a round trip — never the control. */
    async _maybeStore(q, matched) {
        // The tenant switch, read once with the bundle. With mining off this
        // returns before any RPC at all — which is what makes "with the flag
        // off the Coach behaves exactly as it did in Phase C" true of the
        // NETWORK as well as of the answer. A stale bundle fails closed.
        if (!this.bundle?.collect_questions) {
            return;
        }
        try {
            const state = await this.orm.call("learn.consent", "questions_state", []);
            if (state === "granted") {
                await this.orm.call("learn.question", "record",
                    [q, this.state.screen, matched, RT.lang]);
                return;
            }
            if (state === "declined") {
                return;
            }
            // 'unset'. Only prompt when there is something to consent TO: a
            // dialog about a collection that is switched off costs attention
            // and implies the collection is happening.
            const should = await this.orm.call("learn.consent", "should_ask_questions", []);
            if (should) {
                // HELD, NOT SENT. The text stays in this tab until the answer
                // is yes; a no drops it and it is never transmitted for
                // storage at all.
                this.state.pendingQ = { q, matched };
                this.state.askConsent = true;
            }
        } catch {
            // Consent plumbing must never break the answer it rides along
            // with. Failing closed means nothing is stored, which is the
            // right direction to fail in.
        }
    }

    async decideConsent(granted) {
        this.state.askConsent = false;
        const pending = this.state.pendingQ;
        this.state.pendingQ = null;
        try {
            await this.orm.call("learn.consent", "set_questions", [!!granted]);
            if (granted && pending) {
                await this.orm.call("learn.question", "record",
                    [pending.q, this.state.screen, pending.matched, RT.lang]);
            }
        } catch {
            // Same rule: a failed write leaves nothing stored.
        }
    }

    /** LEARNOS Phase 4 — "Explain this screen".
     *
     *  A question nobody has to phrase, so nothing is typed and nothing is
     *  stored: `_maybeStore` is deliberately NOT called here. There is no
     *  learner question to mine, and recording the SCREEN somebody pressed a
     *  button on would be a different collection from the one they consented
     *  to. The event log gets the press, as it does for every other control.
     */
    async explainScreen() {
        if (this.state.busy || !this.state.screen) {
            return;
        }
        this.state.busy = true;
        this.state.simpler = false;
        try {
            const answer = await this.orm.call(
                "learn.intent", "explain_screen", [this.state.screen, RT.lang]);
            this.state.answer = answer;
            this._log(answer.matched ? "coach_hit" : "coach_miss",
                      answer.key || "");
        } catch {
            this.state.answer = null;
        } finally {
            this.state.busy = false;
        }
    }

    async askIntent(key) {
        // A suggested question is asked with its own label, so the transcript
        // reads like a conversation rather than a menu selection.
        const label = this._labelOf(key);
        this.state.question = label;
        await this.ask(label);
    }

    _labelOf(key) {
        const pool = (this.screenInfo?.suggest || [])
            .concat(this.bundle?.global_suggest || []);
        const hit = pool.find((i) => i.key === key);
        return hit ? tx(hit.label) : key;
    }

    /* A `show_me` target may now be a SCENARIO rather than an anchor:
       `scenario:<key>` or `scenario:<key>#<stepKey>`. The two shapes answer two
       different questions — "where is that control" and "show me how this is
       done" — and an intent is allowed to answer the second one, which is what
       most "how do I…" questions are actually asking.

       THE FRAGMENT IS A STEP KEY, NEVER AN INDEX. An index would keep opening
       something after a walkthrough gained a step in the middle, just not the
       step the author meant — the kind of breakage nobody reports because the
       button still works. The generator refuses a fragment that names no step. */
    static SCENARIO_TARGET = /^scenario:([a-z0-9_]+)(?:#([a-z0-9_]+))?$/;

    /** Point at a real control. Returns honestly when there is nothing to
     *  point at — a Coach that scrolls to nothing is worse than one that says
     *  it cannot. */
    showMe(anchor) {
        const hit = CoachHost.SCENARIO_TARGET.exec(anchor || "");
        if (hit) {
            this.startScenario(hit[1], null, hit[2] || "");
            return;
        }
        const found = flashRing(anchor);
        if (!found) {
            this.state.answer = Object.assign({}, this.state.answer, {
                pointFailed: true,
            });
        } else {
            this.close();
        }
    }

    openLesson() {
        this.action.doAction("pb_learn.action_learn_journey");
        this.close();
    }

    /** Start a scenario from the drawer.
     *
     *  The drawer CLOSES first: a walkthrough of the screen behind it cannot
     *  be followed through a panel sitting on top of it, and Watch's first act
     *  is usually to navigate. `stepKey` comes from a `scenario:<key>#<stepKey>`
     *  target and is applied AFTER the entry navigation, so an intent can
     *  answer "why did this pay change" by opening the walkthrough on the
     *  salary breakdown rather than on the board it starts from. */
    async startScenario(key, mode, stepKey) {
        this.close();
        try {
            await this.sc.load();
            const started = await this.sc.begin(key, mode || null);
            if (!started || !stepKey) {
                return;
            }
            // The index has to be into the list the ENGINE will play, not into
            // every step the author wrote: a scenario whose Watch and Try
            // differ (Phase 5) numbers its steps differently in each, and an
            // index taken from the wrong one opens a card about something else.
            const index = this.sc.steps(key, this.sc.state.mode)
                .findIndex((s) => s.key === stepKey);
            // A fragment that names no step opens the walkthrough at its
            // beginning, which is a worse answer and not a broken one.
            if (index > 0) {
                this.sc.goTo(index);
            }
        } catch {
            // An unknown or retired key leaves the learner on their screen with
            // the drawer closed, which is where they already were.
        }
    }

    /** The scenarios offered on THIS screen.
     *
     *  Resolved off `state.screen`, which is what the three-pass matcher out of
     *  `learn.runtime.bootstrap` decided the learner is standing on — so the
     *  Coach and the walkthroughs can never disagree about which cockpit this
     *  is. Empty is the normal case on most screens and draws nothing. */
    get screenScenarios() {
        return this.sc.forScreen(this.state.screen);
    }

    async _log(kind, detail) {
        try {
            await this.orm.call("learn.event", "log", [kind], {
                screen: this.state.screen || null,
                detail: detail || null,
                lang: RT.lang,
            });
        } catch {
            // Measurement must never break the thing it measures.
        }
    }

    // -------------------------------------------------------------- rendering
    get bodyHTML() {
        // THE SUBSCRIPTION. Read during render, so flipping the language
        // re-renders the whole drawer — the answer, the grounded line, the
        // suggestions and the chrome — from the other language slot of the
        // payload we already hold. Without this read the assignment in
        // toggleLang() changes a value nobody is watching. Do not "tidy" it
        // away: `tx()` below reads RT.lang, which OWL cannot see.
        const lang = this.state.lang;
        void lang;
        if (!this.state.ready) {
            return markup(`<p class="lrn-note">${esc(T("noAnswerBody"))}</p>`);
        }
        const parts = [];
        // LEARN v3 — the Practice tab. Everything on it opens a copy; nothing
        // on it can reach a real record.
        if (this.state.tab === "practice") {
            parts.push(this._practiceHTML());
            parts.push(this._practiceTryHTML());
            parts.push(this._tourHTML());
            return markup(parts.join(""));
        }
        parts.push(this._groundedHTML());
        if (this.state.answer) {
            parts.push(this._answerHTML(this.state.answer));
        } else {
            // LEARN v3 — the next step, with its reason, at the very top when
            // the tenant has that switch on. Draws nothing when it is off.
            parts.push(this._nextStepHTML());
            // LEARNOS Phase 4 — the "not sure what to ask?" state. FIRST,
            // because it is the offer that needs no vocabulary: somebody who
            // cannot phrase the question can still press one button and be
            // told what the screen is. The two offers below it need the
            // learner to already know what they want.
            parts.push(this._notSureHTML());
            // ABOVE the suggested questions, and only when there are any. A
            // walkthrough of the screen in front of you is a better first offer
            // than a list of questions about it — and on the screens that have
            // none, this draws nothing rather than an empty heading.
            parts.push(this._scenarioHTML());
            parts.push(this._suggestHTML());
            // The sandbox used to sit LAST here. LEARN v3 gives it a tab of
            // its own, so a single line points at it instead of a whole card.
        }
        // BELOW the answer, deliberately. The person opened the drawer because
        // they were stuck; the answer is what they came for, and a consent card
        // above it is a toll gate on help. Asked once, either way.
        if (this.state.askConsent) {
            parts.push(this._consentHTML());
        }
        return markup(parts.join(""));
    }

    /** Asked once per learner, and only when the tenant has switched
     *  collection on. Both buttons are terminal: a decline is remembered
     *  server-side, so this card cannot come back and nag. */
    _consentHTML() {
        return `<div class="lrn-cconsent">
            <div class="lrn-clabel">${ic("shield-check")}${esc(T("consentTitle"))}</div>
            <p class="lrn-note">${esc(T("consentBody"))}</p>
            <div class="lrn-ctools">
                <button class="lrn-btn sm" data-act="c-consent-yes"
                    >${ic("check")}${esc(T("consentYes"))}</button>
                <button class="lrn-btn sm ghost" data-act="c-consent-no"
                    >${ic("ban")}${esc(T("consentNo"))}</button>
            </div>
        </div>`;
    }

    /** The opening offer, for the person who cannot phrase the question.
     *
     *  Drawn only on a screen the content plane covers, because that is the
     *  only place `explain_screen` has a floor to build from — off the map it
     *  would be a button whose one outcome is the miss the drawer is already
     *  showing. Fail closed, and say nothing rather than offering nothing.
     */
    _notSureHTML() {
        if (!this.covered) {
            return "";
        }
        return `<div class="lrn-cnotsure">
            <div class="lrn-clabel">${esc(T("notSure"))}</div>
            <button class="lrn-btn sm pri" data-act="c-explain"
                    title="${esc(T("explainHint"))}"
                >${ic("info")}${esc(T("explainScreen"))}</button>
        </div>`;
    }

    /** "Continue" — the same suggestion the Journey's map makes, offered to
     *  somebody who opened the drawer without a question.
     *
     *  SECOND, after "explain this screen", and the order is the argument: a
     *  person standing on a screen they do not understand is asking about
     *  THIS screen, and being sent somewhere else first would be answering a
     *  question they did not ask. The suggestion is what to do afterwards.
     *
     *  Draws nothing when the flag is off, when the learner has finished
     *  everything, or when the suggestion is the live capstone — that one
     *  belongs on the map, where its briefing is, not behind a one-line
     *  button on an unrelated screen. */
    _continueHTML() {
        const nb = (this.bundle && this.bundle.next_best) || {};
        if (!nb.reason_key) {
            return "";                       // the flag is off: draw nothing
        }
        // Finished everything: the sentence, and no button. Saying so in one
        // line is the whole point — the alternative is a drawer that quietly
        // stops offering anything and looks broken.
        if (!nb.key || nb.kind === "none") {
            return `<p class="lrn-note">${esc(tx(nb.reason || {}))}</p>`;
        }
        if (nb.kind !== "station") {
            // The live capstone belongs on the map, where its briefing is —
            // not behind a one-line button on an unrelated screen.
            return "";
        }
        return `<button class="lrn-btn sm" data-act="c-continue"
                data-key="${esc(nb.key)}" title="${esc(tx(nb.reason || {}))}"
            >${ic("play")}${esc(T("nbTitle"))}</button>`;
    }

    /** LEARN v3 — the next step as a card of its own, top of the Guide tab.
     *
     *  Same suggestion, same flag, same `c-continue` door as before; what
     *  changed is that the reason is READ, not hidden in a tooltip. The
     *  button itself is `_continueHTML`, unchanged. */
    _nextStepHTML() {
        const nb = (this.bundle && this.bundle.next_best) || {};
        if (!nb.reason_key) {
            return "";
        }
        const station = (this.bundle.stations || []).find((s) => s.key === nb.key);
        const title = station && nb.kind === "station" ? tx(station.name) : "";
        const mins = station && station.duration_min
            ? `<span class="lrn-cnext-min">${ic("clock")}${esc(String(station.duration_min))}${SP}${esc(T("min"))}</span>` : "";
        return `<div class="lrn-cnext">
            <div class="lrn-clabel">${esc(T("nextStep"))}</div>
            ${title ? `<div class="lrn-cnext-t">${esc(title)}${mins}</div>` : ""}
            <p class="lrn-note">${esc(tx(nb.reason || {}))}</p>
            ${title ? this._continueHTML() : ""}
        </div>`;
    }

    /** LEARN v3 — Practice tab: this screen's walkthroughs that can be TRIED
     *  (or done with the engine waiting). Watch-only ones live on the Guide
     *  tab; repeating them here would be two doors to one room. */
    _practiceTryHTML() {
        const rows = this.screenScenarios
            .filter((sc) => (sc.modes || []).some((m) => m === "try" || m === "do"))
            .map((sc) => `<div class="lrn-cscen">
                <div class="lrn-cscentitle">${ic(sc.icon)}${esc(tx(sc.name))}</div>
                <div class="lrn-cscenmodes">
                    ${(sc.modes || []).filter((m) => m !== "watch").map((m) => `
                        <button class="lrn-btn sm ${m === "try" ? "pri" : ""}"
                                data-act="c-scenario" data-key="${esc(sc.key)}"
                                data-mode="${esc(m)}"
                                title="${esc(T(m === "try" ? "scTryHint" : "scDoHint"))}"
                            >${esc(T(m === "try" ? "scTry" : "scDo"))}</button>`).join("")}
                </div>
            </div>`).join("");
        if (!rows) {
            return "";
        }
        return `<div class="lrn-cscens">
            <div class="lrn-clabel">${esc(T("practiceTry"))}</div>
            ${rows}
        </div>`;
    }

    /** LEARN v3 — the product tour, reachable from any screen. */
    _tourHTML() {
        if (!this._offers("sc_welcome", "watch")) {
            return "";
        }
        return `<div class="lrn-cpractice">
            <div class="lrn-clabel">${esc(T("practiceTour"))}</div>
            <p class="lrn-note">${esc(T("practiceTourLead"))}</p>
            <button class="lrn-btn sm" data-act="c-scenario" data-key="sc_welcome"
                    data-mode="watch">${ic("play")}${esc(T("scWatch"))}</button>
        </div>`;
    }

    /** Open the Journey on the suggested station. Same door as `openLesson`,
     *  one key further — there is exactly one place in this module that knows
     *  how to open a station from outside the map. */
    openSuggested(key) {
        if (!key) {
            return;
        }
        this.action.doAction("pb_learn.action_learn_journey", {
            additionalContext: { station: key },
        });
        this.close();
    }

    /** The way into the free-roam sandbox, from wherever the learner is.
     *
     *  Drawn on EVERY screen, unlike the two offers above it: those need the
     *  content plane to cover the screen, and this one needs nothing — the
     *  practice company is the same twenty replicas whatever cockpit the
     *  learner is standing on. It is also the honest answer to "can I just try
     *  this somewhere safe", which is a question the drawer could not answer
     *  before Phase 5.
     */
    _practiceHTML() {
        return `<div class="lrn-cpractice">
            <div class="lrn-clabel">${esc(T("practiceMode"))}</div>
            <p class="lrn-note">${esc(T("practiceModeLead"))}</p>
            <button class="lrn-btn sm" data-act="c-practice"
                >${ic("flask")}${esc(T("practiceOpen"))}</button>
        </div>`;
    }

    /** Open the Journey on the sandbox. Same door as `openLesson`, one key
     *  further: the deep link is what the Journey reads, so there is exactly
     *  one place that knows how to build a practice view. */
    openPractice() {
        this.action.doAction("pb_learn.action_learn_journey", {
            additionalContext: { practice: 1 },
        });
        this.close();
    }

    /** Does this scenario really offer that mode?
     *
     *  The payload is already trustworthy — the generator refuses a `try`
     *  target on a scenario that has no Try, and `_explain_scenarios` reads
     *  the modes off the record. This asks the loaded scenario anyway, so the
     *  drawer CANNOT draw a button the engine would refuse to start, whatever
     *  a stale bundle or a future author sends it. Unknown key, unloaded
     *  service, missing mode: no button.
     */
    _offers(key, mode) {
        if (!key) {
            return false;
        }
        const sc = this.sc.get(key);
        return !!sc && (sc.modes || []).includes(mode);
    }

    /** The Coach says what screen it is grounded on, every time. If it is a
     *  screen with no content yet, it says THAT instead of guessing. */
    _groundedHTML() {
        const s = this.screenInfo;
        if (!s) {
            return `<div class="lrn-cground off">${ic("info")}
                <span>${esc(T("coachNoScreen"))}</span></div>`;
        }
        return `<div class="lrn-cground">${ic("map-pin")}
            <span><b>${esc(T("groundedIn"))}</b> ${esc(tx(s.name))}</span>
            <p class="lrn-note">${esc(tx(s.blurb))}</p></div>`;
    }

    /** "Show me how" — one row per scenario for this screen, one button per
     *  mode it declares. The mode IS the offer: watch, try and do are three
     *  different promises about who presses, so they are three buttons rather
     *  than a scenario with a setting. */
    _scenarioHTML() {
        const list = this.screenScenarios;
        if (!list.length) {
            return "";
        }
        const label = { watch: "scWatch", try: "scTry", do: "scDo" };
        const hint = { watch: "scWatchHint", try: "scTryHint", do: "scDoHint" };
        const rows = list.map((sc) => `
            <div class="lrn-cscen">
                <div class="lrn-cscentitle">${ic(sc.icon)}${esc(tx(sc.name))}</div>
                <div class="lrn-cscenmodes">
                    ${(sc.modes || []).map((m) => `
                        <button class="lrn-btn sm ${m === "watch" ? "pri" : ""}"
                                data-act="c-scenario" data-key="${esc(sc.key)}"
                                data-mode="${esc(m)}"
                                title="${esc(T(hint[m] || "scWatchHint"))}"
                            >${esc(T(label[m] || "scWatch"))}</button>`).join("")}
                </div>
            </div>`).join("");
        return `<div class="lrn-cscens">
            <div class="lrn-clabel">${esc(T("scenarios"))}</div>
            ${rows}
        </div>`;
    }

    _suggestHTML() {
        const s = this.screenInfo;
        // Off the map, fall back to what the Coach can answer anywhere rather
        // than showing nothing. "No lessons here yet" followed by silence is
        // still a dead end.
        const list = s ? s.suggest : (this.bundle?.global_suggest || []);
        if (!list.length) {
            return `<p class="lrn-note">${esc(T("noAnswerBody"))}</p>`;
        }
        return `<div class="lrn-csuggest">
            <div class="lrn-clabel">${esc(T("suggested"))}</div>
            ${list.map((i) => `<button class="lrn-cq" data-act="c-suggest" data-key="${esc(i.key)}"
                >${ic("help-circle")}${esc(tx(i.label))}</button>`).join("")}
        </div>`;
    }

    _answerHTML(a) {
        if (!a.matched) {
            // LEARN v3. A miss in the guide is often a question about the
            // person's own numbers, which the Ask tab can look at. Offered only
            // when that tab exists.
            const handoff = this.askTab
                ? `<p class="lrn-note">${esc(T("askDataLead"))}</p>
                   <div class="lrn-ctools"><button class="lrn-btn sm pri" data-act="c-askdata"
                       >${ic("message-circle")}${esc(T("askDataInstead"))}</button></div>`
                : "";
            return `<div class="lrn-cmiss">
                <p><b>${esc(T("noAnswer"))}</b></p>
                <p class="lrn-note">${esc(T("noAnswerBody"))}</p>
                ${handoff}
            </div>${this._suggestFrom(a.suggest || [])}`;
        }
        const blocks = (a.blocks || []).map((b) => this._blockHTML(b)).join("");
        const tools = [];
        if ((a.show_me || []).length) {
            tools.push(`<button class="lrn-btn sm" data-act="c-show" data-anchor="${esc(a.show_me[0])}"
                >${ic("eye")}${esc(T("showMe"))}</button>`);
        }
        // LEARNOS Phase 4 — ANSWERS THAT TEACH. When a walkthrough covers the
        // same ground, the answer offers it: Watch it happen, or Try it on the
        // practice company. Not a new action — `c-scenario` is the control the
        // "Show me how" rows have used since Phase 1b, so there is still
        // exactly one path from this drawer into the scenario engine.
        if (this._offers(a.watch, "watch")) {
            tools.push(`<button class="lrn-btn sm" data-act="c-scenario"
                data-key="${esc(a.watch)}" data-mode="watch"
                title="${esc(T("scWatchHint"))}"
                >${ic("play")}${esc(T("scWatch"))}</button>`);
        }
        if (this._offers(a["try"], "try")) {
            tools.push(`<button class="lrn-btn sm" data-act="c-scenario"
                data-key="${esc(a["try"])}" data-mode="try"
                title="${esc(T("scTryHint"))}"
                >${ic("flask")}${esc(T("scTry"))}</button>`);
        }
        if (a.simpler) {
            tools.push(`<button class="lrn-btn sm" data-act="c-simpler"
                >${ic("lightbulb")}${esc(this.state.simpler ? T("less") : T("simpler"))}</button>`);
        }
        tools.push(`<button class="lrn-btn sm ghost" data-act="c-lesson"
            >${ic("book-open")}${esc(T("openLesson"))}</button>`);

        const simplerBlock = this.state.simpler && a.simpler
            ? `<div class="lrn-cblock p simpler">${gtx(a.simpler)}</div>` : "";

        // The learner is entitled to know which KIND of answer they are
        // reading. Two are not a curated intent: a definition out of the
        // column glossary, and — only when a tenant has switched the composer
        // on — one a model wrote from this module's own material. The second
        // badge is the more important of the two, because it is the only
        // answer in the drawer that no author has read.
        // Phase 4 adds a THIRD: an explanation the server assembled from this
        // screen's own blurb, next step and column definitions. It is not a
        // curated answer to a question anybody asked, so it says so.
        const BADGES = {
            column: ["book-open", "columnAnswer"],
            composed: ["sparkles", "composedAnswer"],
            screen: ["info", "screenAnswer"],
        };
        const badgeSpec = BADGES[a.source_kind];
        const badge = badgeSpec
            ? `<span class="lrn-chip b">${ic(badgeSpec[0])}${esc(T(badgeSpec[1]))}</span>`
            : "";
        return `<div class="lrn-canswer">
            ${badge}
            <h4>${esc(tx(a.label))}</h4>
            ${simplerBlock || blocks}
            ${a.pointFailed ? `<div class="lrn-cblock warn">${ic("info")}
                ${esc(T("pointNotHere"))}</div>` : ""}
            <div class="lrn-ctools">${tools.join("")}</div>
        </div>`;
    }

    _suggestFrom(list) {
        if (!list.length) {
            return "";
        }
        return `<div class="lrn-csuggest">
            <div class="lrn-clabel">${esc(T("canAnswer"))}</div>
            ${list.map((i) => `<button class="lrn-cq" data-act="c-suggest" data-key="${esc(i.key)}"
                >${ic("help-circle")}${esc(tx(i.label))}</button>`).join("")}
        </div>`;
    }

    _blockHTML(b) {
        // Authored prose carries inline <b>/<i> — the same markup lesson bodies
        // use — so it is inserted as markup rather than escaped. These strings
        // ship in the module and are never learner input; escaping them printed
        // the tags to the reader.
        const body = gtx(b.body);
        switch (b.kind) {
            case "steps":
                return `<ol class="lrn-csteps">${(b.steps || []).map((s) =>
                    `<li>${esc(tx(s.text))}${s.anchor
                        ? `<button class="lrn-clink" data-act="c-show" data-anchor="${esc(s.anchor)}"
                            >${ic("eye")}${esc(T("showMe"))}</button>` : ""}</li>`).join("")}</ol>`;
            case "warn":
                return `<div class="lrn-cblock warn">${ic("alert-triangle")}<span>${body}</span></div>`;
            case "ok":
                return `<div class="lrn-cblock ok">${ic("check-circle")}<span>${body}</span></div>`;
            case "refusal":
                // "Your role can't do that here" is only true when the block is
                // scoped to a capability. The compliance refusal applies to
                // EVERY role, and heading it with a role message told the
                // reader the wrong thing about why the answer is no.
                return `<div class="lrn-cblock refusal">${ic("lock")}
                    <span>${b.capability === "any"
                        ? "" : `<b>${esc(T("refusal"))}</b><br/>`}${body}</span></div>`;
            case "who":
                return `<div class="lrn-cmeta"><b>${esc(T("whoCan"))}</b> ${body}</div>`;
            case "how":
                // "How to get access" is right when the block is scoped to a
                // capability — the reader is being told how to be allowed. It
                // is wrong for a refusal that applies to everyone, where the
                // answer is what to do INSTEAD, not how to be permitted.
                return `<div class="lrn-cmeta"><b>${
                    esc(b.capability === "any" ? T("howInstead") : T("howAsk"))
                }</b> ${body}</div>`;
            case "source":
                return `<div class="lrn-csource">${ic("book-open")}
                    <span><b>${esc(T("source"))}</b> ${body}</span></div>`;
            case "calc":
            case "calc_kpi":
                // The arithmetic lives in the fixture, where the contract
                // checker guards it. Rendered by the same helper the lesson
                // uses, so the two can never disagree.
                return `<div class="lrn-cblock calc">${
                    b.kind === "calc" ? calcHTML() : calcKpiHTML()}</div>`;
            default:
                return `<div class="lrn-cblock p">${body}</div>`;
        }
    }

    // ------------------------------------------------------------ delegation
    onClick(ev) {
        const el = ev.target.closest("[data-act]");
        if (!el) {
            return;
        }
        const act = el.dataset.act;
        if (!COACH_ACTIONS.has(act)) {
            return;
        }
        ev.preventDefault();
        if (act === "c-close") {
            this.close();
        } else if (act === "c-suggest") {
            this.askIntent(el.dataset.key);
        } else if (act === "c-show") {
            this.showMe(el.dataset.anchor);
        } else if (act === "c-simpler") {
            this.state.simpler = !this.state.simpler;
        } else if (act === "c-lesson") {
            this.openLesson();
        } else if (act === "c-back") {
            this.state.answer = null;
        } else if (act === "c-lang") {
            this.toggleLang();
        } else if (act === "c-consent-yes") {
            this.decideConsent(true);
        } else if (act === "c-consent-no") {
            this.decideConsent(false);
        } else if (act === "c-scenario") {
            this.startScenario(el.dataset.key, el.dataset.mode, 0);
        } else if (act === "c-explain") {
            this.explainScreen();
        } else if (act === "c-practice") {
            this.openPractice();
        } else if (act === "c-continue") {
            this.openSuggested(el.dataset.key);
        } else if (act === "c-tab") {
            this.setTab(el.dataset.tab);
        } else if (act === "c-askdata") {
            this.askData();
        } else if (["c-mgo", "c-mok", "c-fvexplain", "c-fvwatch", "c-mlater",
                    "c-mewatch", "c-meskip"].includes(act)) {
            this._momentAct(act);
        }
    }

    /* ONE language preference, shared with the Journey.
       Two independent toggles for one setting is a bug waiting to happen: the
       learner flips the Coach to Vietnamese, opens a lesson, and it is in
       English again. Both surfaces read and write the same localStorage key. */
    /* THE ORDER MATTERS, AND SO DOES WHO READS `state.lang`.
       Found in Chrome on the live deploy: the toggle flipped the preference,
       persisted it, and left the open drawer in the old language until a full
       page reload. The payload was never the problem — both languages are in
       every answer already.

       OWL re-renders a component when a reactive key it READ DURING RENDER
       changes. `state.lang` was being assigned here and read by nothing in
       the render path: every visible string goes through `T()`/`tx()`, which
       read `RT.lang` — a plain module object, not reactive. So the assignment
       changed a value nobody was subscribed to and nothing re-rendered.

       journey.js has always worked for exactly one reason: its `langLabel`
       getter reads `this.state.lang`, which subscribes the component during
       render. Same mechanism adopted here — `state.lang` is set FIRST, and
       `bodyHTML` and `langLabel` both read it. */
    toggleLang() {
        this.state.lang = this.state.lang === "en" ? "vi" : "en";
        RT.lang = this.state.lang;
        // And the scenario overlay, which is a SECOND component reading the
        // same non-reactive RT.lang and would otherwise stay in the old
        // language until a reload — with a walkthrough running on top of the
        // screen, which is the worst place for it. Same fix, same reason.
        this.sc.state.lang = RT.lang;
        try {
            const p = JSON.parse(window.localStorage.getItem(LOCAL_PREFS) || "{}");
            p.lang = RT.lang;
            window.localStorage.setItem(LOCAL_PREFS, JSON.stringify(p));
        } catch {
            // A locked-down profile must not break the drawer.
        }
    }

    _restoreLang() {
        try {
            const p = JSON.parse(window.localStorage.getItem(LOCAL_PREFS) || "{}");
            const sessionLang = window.odoo?.session_info?.user_context?.lang || "";
            RT.lang = p.lang || (sessionLang.startsWith("vi") ? "vi" : "en");
        } catch {
            RT.lang = "en";
        }
        this.state.lang = RT.lang;
    }

    get langLabel() {
        // `state.lang`, not RT.lang — this getter is rendered in the drawer
        // header, so reading the reactive copy is what subscribes the
        // component. Exactly what journey.js:1160 does, and the reason its
        // toggle has always re-rendered live while this one did not.
        return this.state.lang === "en" ? "Tiếng Việt" : "English";
    }

    /* Drawer chrome, through the same tx() path as everything else. Hard-coded
       in the template these stayed English while the answers beside them
       switched — and the honesty line is the last thing that should be
       readable in only one of the two languages this desk works in. */
    get honestText() {
        return T("honest");
    }

    get askPlaceholder() {
        return T("askPlaceholder");
    }

    /* The header's explain button. Two getters rather than T() in the
       template, for the same reason every other string here is one: the
       template cannot read the reactive language, and `bodyHTML` is what
       re-renders the drawer when the toggle flips.

       THE SUBSCRIPTION IS DELIBERATE HERE TOO. These render in the header,
       which is OUTSIDE bodyHTML, so they need their own read of
       `state.lang` — exactly the bug journey.js taught this module twice. */
    get explainLabel() {
        void this.state.lang;
        return T("explainScreen");
    }

    get explainHintText() {
        void this.state.lang;
        return T("explainHint");
    }

    get coachName() {
        return T("coachName");
    }

    /* "Stuck?" / "Cần trợ giúp?" — the launcher's own words, through the same
       bilingual path as everything else. Hard-coded in the template it stayed
       English while the drawer behind it switched. */
    get launcherLabel() {
        void this.state.lang;
        return T("orbLabel");
    }

    get launcherTitle() {
        void this.state.lang;
        return T("orbHint");
    }
}
