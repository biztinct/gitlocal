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
   assembled from stored blocks on the server, and the only controls an answer
   can render are its own — point at a control, say it more simply, open the
   lesson, ask something else. There is no path from a question to a product
   method. `tests/test_coach.py` asserts that rather than trusting it.

   It never invents a domain fact either. Every answer is retrieved from a
   record an author wrote, with ONE fenced exception added in Phase D: when a
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

import { RT, T, tx, esc, ic } from "../engine/runtime";
import { flashRing } from "../engine/spotlight";
import { calcHTML, calcKpiHTML } from "../engine/visuals";
import { markLauncherStack, maybeGreet } from "./first_login";

/* Shared with the Journey: one language preference for the whole system. */
const LOCAL_PREFS = "pbLearnPrefs";

/* The only actions an answer may carry. Anything else is a bug, and the test
   compares the rendered HTML against exactly this set. */
export const COACH_ACTIONS = new Set([
    "c-close", "c-ask", "c-suggest", "c-show", "c-simpler", "c-lesson", "c-back",
    "c-lang",
    // Phase D2. Two buttons, one decision, asked once. Neither reaches a
    // product method — they write this learner's own consent row and nothing
    // else, which is why they belong in this set rather than outside it.
    "c-consent-yes", "c-consent-no",
]);

export class CoachHost extends Component {
    static template = "pb_learn.CoachHost";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.inputRef = useRef("input");

        this.state = useState({
            open: false,
            ready: false,
            screen: null,        // learn.screen key, or null when off-map
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
        });

        this.bundle = null;
        this._onKey = this._onKey.bind(this);

        onWillStart(async () => {
            this._restoreLang();
            // Fetched once. The drawer must open instantly — a learner who is
            // stuck does not want to watch a spinner.
            try {
                this.bundle = await this.orm.call("learn.intent", "coach_bundle", []);
                RT.tokens = this.bundle.tokens || RT.tokens;
                RT.chrome = this.bundle.chrome || RT.chrome;
                this.state.ready = true;
            } catch {
                // A Coach that cannot load must not break the screen it sits on.
                this.state.ready = false;
            }
        });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveScreen());
        onMounted(() => {
            this._resolveScreen();
            document.addEventListener("keydown", this._onKey);
            // Two pieces of CHROME the Coach happens to be the right host for,
            // because it is the one component mounted on every screen. Both
            // live in first_login.js; neither can throw, and neither is allowed
            // to delay the drawer.
            markLauncherStack(this.env);
            maybeGreet(this.env, this.orm, this.action);
        });
        onWillUnmount(() => document.removeEventListener("keydown", this._onKey));
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
            // Only closes the Coach. The screen behind it keeps its own Escape.
            ev.stopPropagation();
            this.close();
        }
    }

    toggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            this._log("coach_open");
            setTimeout(() => this.inputRef.el?.focus(), 60);
        }
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

    /** Point at a real control. Returns honestly when there is nothing to
     *  point at — a Coach that scrolls to nothing is worse than one that says
     *  it cannot. */
    showMe(anchor) {
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
        parts.push(this._groundedHTML());
        if (this.state.answer) {
            parts.push(this._answerHTML(this.state.answer));
        } else {
            parts.push(this._suggestHTML());
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
            return `<div class="lrn-cmiss">
                <p><b>${esc(T("noAnswer"))}</b></p>
                <p class="lrn-note">${esc(T("noAnswerBody"))}</p>
            </div>${this._suggestFrom(a.suggest || [])}`;
        }
        const blocks = (a.blocks || []).map((b) => this._blockHTML(b)).join("");
        const tools = [];
        if ((a.show_me || []).length) {
            tools.push(`<button class="lrn-btn sm" data-act="c-show" data-anchor="${esc(a.show_me[0])}"
                >${ic("eye")}${esc(T("showMe"))}</button>`);
        }
        if (a.simpler) {
            tools.push(`<button class="lrn-btn sm" data-act="c-simpler"
                >${ic("lightbulb")}${esc(this.state.simpler ? T("less") : T("simpler"))}</button>`);
        }
        tools.push(`<button class="lrn-btn sm ghost" data-act="c-lesson"
            >${ic("book-open")}${esc(T("openLesson"))}</button>`);

        const simplerBlock = this.state.simpler && a.simpler
            ? `<div class="lrn-cblock p simpler">${esc(tx(a.simpler))}</div>` : "";

        // The learner is entitled to know which KIND of answer they are
        // reading. Two are not a curated intent: a definition out of the
        // column glossary, and — only when a tenant has switched the composer
        // on — one a model wrote from this module's own material. The second
        // badge is the more important of the two, because it is the only
        // answer in the drawer that no author has read.
        const badge = a.source_kind === "column"
            ? `<span class="lrn-chip b">${ic("book-open")}${esc(T("columnAnswer"))}</span>`
            : a.source_kind === "composed"
                ? `<span class="lrn-chip b">${ic("sparkles")}${esc(T("composedAnswer"))}</span>`
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
        const body = tx(b.body);
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

    get coachName() {
        return T("coachName");
    }

    /* "Stuck?" / "Cần trợ giúp?" — the launcher's own words, through the same
       bilingual path as everything else. Hard-coded in the template it stayed
       English while the drawer behind it switched. */
    get launcherLabel() {
        return T("stuck");
    }

    get launcherTitle() {
        return T("stuck") + " (?)";
    }
}
