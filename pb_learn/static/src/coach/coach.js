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

import { RT, T, tx, esc, ic } from "../engine/runtime";
/* The glossary hovercard (LEARNOS Phase 2). Answer blocks are the one
   place in the drawer that inserts authored prose RAW, so they are the
   one place `gtx` replaces `tx`. */
import { gtx, glossaryOpen, setGlossary, installGlossary, closeGlossary }
    from "../engine/glossary";
import { loadContent, composeScreens } from "../content/content_loader";
import { flashRing } from "../engine/spotlight";
import { calcHTML, calcKpiHTML } from "../engine/visuals";
import { markLauncherStack, maybeGreet, maybeWelcome } from "./first_login";

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
]);

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
        });

        this.bundle = null;
        this._onKey = this._onKey.bind(this);

        onWillStart(async () => {
            this._restoreLang();
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
                };
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
        parts.push(this._groundedHTML());
        if (this.state.answer) {
            parts.push(this._answerHTML(this.state.answer));
        } else {
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
            // LAST. A learner who came to the drawer with a question should
            // meet the answers first; the sandbox is what they reach for when
            // none of them was the thing they wanted.
            parts.push(this._practiceHTML());
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
            ${this._continueHTML()}
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
        return T("stuck");
    }

    get launcherTitle() {
        return T("stuck") + " (?)";
    }
}
