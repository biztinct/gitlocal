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
import { Component, markup, onMounted, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

import { RT, T, tx, esc, ic, SP, reduced } from "../engine/runtime";
/* The glossary hovercard (LEARNOS Phase 2). Answer blocks are the one
   place in the drawer that inserts authored prose RAW, so they are the
   one place `gtx` replaces `tx`. */
import { gtx, glossaryOpen, setGlossary, installGlossary, closeGlossary }
    from "../engine/glossary";
import { loadContent, composeScreens } from "../content/content_loader";
import { flashRing } from "../engine/spotlight";
import { calcHTML, calcKpiHTML } from "../engine/visuals";
import { markLauncherStack, maybeWelcome } from "./first_login";
import { registerFieldRows, registerLessonRows } from "../hub/learn_palette";
/* LEARNREV P3 — the Library and the ⌘K field rows open a screen with its
   Guide through this door (they cannot import this file), and the field
   index the ⌘K rows are made of. */
import { helperDoor } from "./guide_door";
import { loadFieldIndex } from "../content/field_index";
/* LEARN REFRESH step 1 — where the learner is, published by the hubs, and the
   one module that turns a screen into a place (engine/places.js). The rail's
   own icon set draws the tab list, so each tab looks as it does on the rail. */
import { hubPlace, placeSub, switchLens } from "@pb_hub/js/hub_place";
import { ic as railIc } from "@pb_import_kit/js/import_icons";
import { canOpen, hubScreenOf, openLearn, openScreen, reachable, resolveLensReach, screenAtPlace,
         setReach, tabName, waitForPlace } from "../engine/places";
/* LEARNREV P2 — the Guide panel (six sections above the one chat) and the
   (i) field cards. Both are behind the `guide` switch (bootstrap); with it
   off nothing below is called and the drawer is what shipped before. */
import { openHub } from "@pb_hub/js/hub_nav";
import { actionable, askChips, dropAccess, fieldMatches, fmt, hasProvider, runAction,
         sectionsHTML } from "./guide_panel";
import { InfoLayer, closeFieldCard, fieldCardOpen, markFeedback, openFieldCard }
    from "./field_info";

/* The one sentence the drawer needs when the content plane itself failed to
   load — and so cannot supply it. Mirrors the `helperFailed` chrome key. */
const LOAD_FAILED = {
    en: "The guide could not load just now. Your screen is not affected. Close PayAI and open it again.",
    vi: "Phần hướng dẫn chưa tải được lúc này. Màn hình của bạn không bị ảnh hưởng. Hãy đóng PayAI rồi mở lại.",
};

/* Shared with the Journey: one language preference for the whole system. */
const LOCAL_PREFS = "pbLearnPrefs";

/* The only actions an answer may carry. Anything else is a bug, and the test
   compares the rendered HTML against exactly this set. */
export const COACH_ACTIONS = new Set([
    "c-close", "c-suggest", "c-show", "c-simpler", "c-lesson",
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
    // ONECHAT OC2 — "Continue" (the next step), the tab strip and "ask the
    // Ask tab instead" are gone: one chat, no tabs, no "Your next step"
    // (owner ruling 2026-10-14). What replaced them:
    //   c-say           send a sentence through the one composer path (the
    //                   router, `learn.helper.route`), exactly as if typed;
    //   c-practise-here "Let me practise this" on the context card;
    //   c-choice        a chip of a "Which did you mean?" turn;
    //   c-extra         "Explain how instead" / "Do it for me" under a turn;
    //   c-again         "Show again" on a history marker;
    //   c-more, c-readaloud, c-clear, c-clear-yes, c-clear-no, c-usevoice
    //                   the header's More menu.
    // None reaches a product method from here: a sentence goes to PayAI only
    // through PayAI's own chat and its own server-side fences, the same path
    // typing it takes.
    "c-say", "c-practise-here", "c-choice", "c-extra", "c-again",
    "c-more", "c-readaloud", "c-clear", "c-clear-yes", "c-clear-no", "c-usevoice",
    // LEARN v3 — the moment card above the helper button: a milestone note,
    // the month-end nudge, or a first-visit note. Each either opens something
    // this drawer already opens (a lesson, a walkthrough, "explain this
    // screen") or dismisses the card. None reaches a product method; the only
    // writes are this learner's own learning-log rows.
    "c-mgo", "c-mok", "c-fvexplain", "c-fvwatch", "c-mlater", "c-mewatch", "c-meskip",
    // LEARN REFRESH step 1 — "Take me there" on the hub page's tab list. It
    // asks the hub on screen to show another of ITS OWN tabs, through the
    // shell's own lens switch (the same call its rail buttons make); it
    // reaches no product method and writes nothing.
    "c-goto",
    // LEARNREV P2 — the Guide panel. Opening and closing a section, the
    // "You are here" chips (each opens a screen the way its tab would), a
    // Right now button (filter the board on screen / open a screen / open a
    // record's form — what a person could click themselves), a Fields row,
    // Retry, the lesson map, dock / float, and "Open the Guide" under an
    // Explain answer and on the first-visit card. None reaches a product
    // method: the board's own filter is set through the bus, and an open is
    // the hub's own arrival protocol (openHub).
    "c-gsec", "c-gpath", "c-gscreen", "c-gact", "c-gfield", "c-gretry", "c-gmap",
    "c-gdock", "c-guide", "c-fvguide",
    // LEARNREV P3 — "Show the Guide": the sections fold to their titles while
    // a conversation is under way, and this opens them again. A read.
    "c-gshow",
]);

/* ONECHAT OC2 — ONE CHAT, NO TABS.

   The Coach and PayAI used to be two floating buttons, then one drawer with
   three tabs. Now the drawer is ONE chat called PayAI: one stream of turns,
   one composer, and the server's router (`learn.helper.route`) decides where
   each sentence goes — PayAI's action path, PayAI's data answer, the guide,
   Explain this screen, or practice. Nobody picks a tab.

   OWNERSHIP. The stream, the composer and the voice live in PayAI's embedded
   chat (pb_payroll_ai_insights), because the plan cards, history, voice and
   read-aloud already live there. The shell, the header, the guide's answers
   and the practice doors stay HERE, handed to the chat as one `helper`
   object — so pb_learn still never imports PayAI.

   Registries, because neither module may import the other:

     pb_helper_host — this module says "the one helper is here". PayAI reads it
                      at mount time and, when it is set, draws no pill and no
                      modal of its own.
     pb_helper_chat — PayAI registers its embedded chat under "main". Absent
                      module (or a person without the group): this drawer
                      draws its own small guide-only stream instead.
     pb_helper_tabs — the old name ("ask"), read only as a fallback for one
                      release, so a stale PayAI bundle still mounts. */
export const HELPER_CHAT = "pb_helper_chat";
export const HELPER_TABS = "pb_helper_tabs";
export const HELPER_HOST = "pb_helper_host";
registry.category(HELPER_HOST).add("orb", { module: "pb_learn" });

/* How long a practice turn ("Opening practice: …") stays readable before the
   drawer closes and the practice opens. A beat, not a wait. */
const PRACTICE_BEAT_MS = 600;
/* At most this many chips on the context card and in a practice turn. */
const MAX_CHIPS = 4;
let TURN_SEQ = 0;

/* LEARN v3 — moments. Screens this browser has already been told about, and
   the month the month-end nudge was skipped for (shared with the map). */
const SEEN_SCREENS = "pbLearnSeenScreens";
const MONTH_END_SKIP = "pbLearnMonthEndSkip";
const MONTH_END_TODAY = "pbLearnMonthEndShown";
/* Milestones are asked of the server at most this often. */
const MILESTONE_EVERY_MS = 60000;
/* LEARNREV P0 (G2) — said when "Open the lesson" finds no lesson for the
   screen. Written here, in both languages, because P0 may not regenerate the
   content plane; the P1 generator takes it over as a chrome string. */
const NO_LESSON_NOTE = {
    key: "noLessonHere",
    en: "No lesson for this screen yet. Opening Learn, which lists every screen.",
    vi: "Chưa có bài học cho màn hình này. Đang mở trang Học tập, nơi liệt kê mọi màn hình.",
};
/* LEARNREV P2 — docked (a right-hand column, ≥ 1280 px) or floating, and
   which Guide sections this person left open, per screen. */
const DOCK_KEY = "pbLearnDock";
const SECTIONS_KEY = "pbLearnGuideSec";
/* LEARNREV P3 — screens where this person pressed "Show the Guide" after it
   folded for a conversation: there it stays open on the next message. */
const GUIDE_SHOW_KEY = "pbLearnGuideShow";
/* Docking exists from this width (guide.scss). */
const DOCK_MIN_PX = 1280;
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
            lang: RT.lang,
            // Phase D2 — question mining. `askConsent` is only ever set true
            // by the SERVER saying both that collection is on and that this
            // learner has not been asked yet.
            askConsent: false,
            pendingQ: null,      // {q, matched} held until a yes; dropped on a no
            // ONECHAT OC2 — the guide-only stream, drawn when there is no
            // PayAI chat for this person (module absent, or no access). Kept
            // in memory for the page's life: across a close and across
            // screens (a divider marks each new screen), never stored.
            turns: [],
            // LEARN v3 — the one moment card showing, or null.
            moment: null,
            // LEARN REFRESH step 1 — the content plane failed to load, and a
            // "Take me there" that could not move (the tab is not open to
            // this reader any more).
            loadFailed: false,
            gotoFailed: false,
            // LEARNREV P2 — the Guide for the screen on show (`learn.guide.
            // rpc_guide`), the call's key, its progress, which sections are
            // open, which Fields row is expanded, docked or floating.
            guide: null,
            gKey: "",
            gLoading: false,
            gError: false,
            gSec: {},
            gField: "",
            // Bumped whenever a Guide arrives: the chat's opening card
            // carries chips built from it, and redraws on its `place` prop.
            gTick: 0,
            dock: lsGet(DOCK_KEY, "dock") === "float" ? "float" : "dock",
            // LEARNREV P3 — the sections folded to their titles because a
            // message was sent (the conversation gets the height).
            gFolded: false,
        });
        // LEARNREV P3 — a message has been sent in this drawer session (the
        // fold happens once per session), and a Guide asked for by the
        // Library / ⌘K that waits for its screen to be grounded.
        this._sentThisOpen = false;
        this._pendingGuide = null;
        // One Guide per screen + arguments + language, for the drawer's life;
        // "Right now" is read again on every open (`_loadGuide({refresh})`).
        this._guideCache = new Map();
        this._gInflight = "";
        // The Fields search words: NOT reactive, so typing never redraws the
        // panel (the box would lose focus); rows are hidden in place.
        this._gQuery = "";
        this._info = null;
        this._markups = {};
        // LEARN REFRESH step 1 — WHERE AM I. The hubs publish the hub and tab
        // on screen (pb_hub/js/hub_place.js); `useState` on that store is the
        // subscription, and `placeKey` (read by the template root) is what
        // makes a tab switch re-render this component at all.
        this.place = useState(hubPlace);
        this._milestoneAt = 0;
        // Passed to the chat as a prop. A stable function, made once, so the
        // chat is not re-rendered by a new identity on every drawer render.
        this.closeHelper = () => this.close();
        // ONECHAT OC2 — the header's More menu. `close` lives on the object so
        // the Escape ladder in `_onKey` can call it as `this.menu.close()`.
        this.menu = useState({ open: false, confirm: false, tick: 0 });
        this.menu.close = () => {
            this.menu.open = false;
            this.menu.confirm = false;
        };
        // ONECHAT OC2 — the chat's handle (`attach`), and what was asked of
        // it before it had mounted: the moment card's Explain, a ⌘K sentence,
        // the header's Explain pressed during the mount. Flushed on attach.
        this._api = null;
        this._queue = [];
        this._flushing = false;
        // Built ONCE: its functions read reactive state at call time, so the
        // identity never changes — and the `lang` prop is what re-renders the
        // chat on a language flip (ledger OC16).
        this.helper = this._makeHelper();

        this.bundle = null;
        this._onKey = this._onKey.bind(this);
        this._onViewport = this._onViewport.bind(this);
        // Whether this person may use the PayAI chat, asked once. A chat whose
        // every question fails on an access rule is a dead end; without it the
        // drawer draws its own guide-only stream.
        this.chatAllowed = false;

        onWillStart(async () => {
            this._restoreLang();
            try {
                const entry = this._chatEntry();
                const groups = entry ? (entry.groups || []) : null;
                this.chatAllowed = groups === null ? false : !groups.length
                    || (await Promise.all(groups.map((g) => user.hasGroup(g)))).some(Boolean);
            } catch {
                this.chatAllowed = false;
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
                    // LEARNREV P0 — a retired screen's lesson door lands on
                    // the station it folded into (the Journey's own rule).
                    station_aliases: content.station_aliases || {},
                    // LEARN v3 — the month-end date, for the Dashboard nudge.
                    path: runtime.path || {},
                    // LEARNREV P2 — the Guide switch (Learn › Settings).
                    guide: !!runtime.guide,
                };
                // Which stations this reader can reach, for the walkthrough
                // engine's "you don't have access" answer (engine/places.js).
                setReach(runtime.visible_stations);
                // LEARN REFRESH step 4 — and which hub tabs (their own gates).
                resolveLensReach(this.env, this.orm, content.screens || []).catch(() => {});
                // LEARN v3 — lessons in the ⌘K search, from the same content.
                try {
                    registerLessonRows(content);
                } catch (e) {
                    console.warn("pb_learn: lesson rows not added to the search", e);
                }
                // LEARNREV P3 — and every field card ("Pay role · Field on
                // Component treatment"). After the drawer is ready, never in
                // its way: a failed index is simply no field rows.
                loadFieldIndex(this.orm, RT.lang).then((rows) => {
                    try {
                        registerFieldRows(rows, (screen, field) =>
                            this._guideAt(screen, { section: "fields", field }));
                    } catch (e) {
                        console.warn("pb_learn: field rows not added to the search", e);
                    }
                });
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
                this.state.loadFailed = true;
            }
        });

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveScreen());
        // LEARN REFRESH step 1 — and when the TAB changes, which is not an
        // action change at all. After the patch, so it is a read of the
        // store and a write of this component's own state only.
        useEffect(() => {
            this._resolveScreen();
            // LEARNREV P2 — a scheme picked on Mapping is a new Guide (its
            // Right now is that scheme's); the same key is a cache hit.
            this._loadGuide();
        }, () => [this.placeKey]);
        // LEARNREV P2 — docked: the page makes room on the right (coach.scss,
        // ≥ 1280 px only). Follows open / the person's choice / the switch.
        useEffect(() => { this._syncDock(); },
                  () => [this.state.open, this.state.dock, this.guideOn]);
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
            // ONECHAT OC2 — the phone's keyboard. `visualViewport` is the
            // only honest measure of what is left above it (a plain `vh`
            // includes the part the keyboard covers), so the bottom sheet
            // sizes itself off the variables this sets (coach.scss).
            if (window.visualViewport) {
                window.visualViewport.addEventListener("resize", this._onViewport);
                this._onViewport();
            }
            // LEARN v3. The corner holds one button now, so it sits in the
            // bottom slot. A body class rather than a runtime measurement:
            // coach.scss places the launcher off it.
            document.body.classList.add("lrn-one-helper");
            // LEARNREV P3 — the Library's Guide chip, its search's "Ask PayAI"
            // and the ⌘K field rows come in through here (coach/guide_door.js).
            helperDoor.guideAt = (screen, opts) => this._guideAt(screen, opts);
            helperDoor.ask = (text) => this.openHelper({ text, send: false });
            // Two pieces of CHROME the Coach happens to be the right host for,
            // because it is the one component mounted on every screen. Both
            // live in first_login.js; neither can throw, and neither is allowed
            // to delay the drawer.
            markLauncherStack(this.env);
            // A real tenant gets the welcome card. The demo world gets no
            // sign-in greeting (owner, 2026-10-12): demo users land on Home,
            // not on the Journey. A bundle that failed to load gets no card —
            // it would otherwise render its own chrome keys as its text.
            if (this.bundle) {
                maybeWelcome(this.env, this.orm, this.sc, this.bundle.demo_world);
            }
        });
        onWillUnmount(() => {
            document.removeEventListener("keydown", this._onKey, true);
            if (window.visualViewport) {
                window.visualViewport.removeEventListener("resize", this._onViewport);
            }
            document.body.classList.remove("lrn-one-helper");
            helperDoor.guideAt = null;
            helperDoor.ask = null;
            // The card is on document.body, not in this component's tree.
            closeGlossary();
            // LEARNREV P2 — the field card, the (i) and the dock likewise.
            document.body.classList.remove("lrn-docked");
            if (this._info) {
                this._info.stop();
            }
            closeFieldCard(false);
        });
    }

    // ---------------------------------------------------------------- context
    /** Which learn screen is showing, from the action manager — the same
     *  signal SidebarHost already resolves on. */
    _resolveScreen() {
        const controller = this.action.currentController;
        const action = controller?.action;
        const screens = this.bundle?.screens || [];
        // LEARN REFRESH step 1 — PASS −1, THE PLACE. Inside a hub the action
        // is the HUB (`pb_pay_hub`) whichever tab is showing, so the passes
        // below can only ever find the hub. The published place says which
        // tab (and inner tab, and open detail panel) it is; a tab with no
        // lesson yet grounds on the hub's own page rather than on nothing.
        const atPlace = screenAtPlace(screens, action && action.tag);
        if (atPlace) {
            this._ground(atPlace.key);
            return;
        }
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
        this._ground(found ? found.key : null);
    }

    _ground(key) {
        this.state.gotoFailed = false;
        if (key !== this.state.screen) {
            this.state.screen = key;
            // LEARN v3. A moment belongs to the screen it was shown on.
            this.state.moment = null;
            setTimeout(() => this._pickMoment(), 900);
            // ONECHAT OC2 — the conversation is NOT cleared any more: it is
            // one thread across screens, and the chat marks the move with a
            // context card ("On: Pay Run › Runs") instead.
            // LEARNREV P2 — a new screen is a new Guide: its sections as this
            // person left them there, no field card from the last screen.
            if (this.guideOn) {
                closeFieldCard(false);
                this.state.gField = "";
                this._gQuery = "";
                this.state.gSec = this._sectionMemory(key);
                this.state.gFolded = false;
                this._loadGuide();
            }
        }
        // LEARNREV P3 — the Library asked for this screen's Guide before the
        // screen was grounded: apply it now, over the remembered sections.
        if (this._pendingGuide && this._pendingGuide.screen === key) {
            this._applyGuide(this._pendingGuide);
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
            // LEARNREV P2: a field card is the same kind of rung — its own
            // listener closes it and swallows the key (field_info.js).
            if (glossaryOpen() || fieldCardOpen()) {
                return;
            }
            // ONECHAT OC2 — two rungs above "close the drawer", in this
            // order. An open More menu closes first, and focus goes back to
            // its button. Then a recording in progress is CANCELLED (nothing
            // is sent for transcription) and the drawer stays open — the
            // person pressed Escape to stop talking, not to leave. The
            // `menu.close()` in the second rung is harmless when the menu is
            // shut. This listener is document-capture (ledger OC11), so it
            // runs before anything inside the drawer sees the key.
            if (this.menu.open) {
                ev.stopPropagation();
                this.menu.close();
                this._focusMore();
                return;
            }
            if (this._api?.isRecording()) {
                ev.stopPropagation();
                this._api.cancelRecording();
                this.menu.close();
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
        this.menu.close();
        if (this.state.open) {
            this._sentThisOpen = false;
            this.state.gFolded = false;
            this._log("coach_open");
            // LEARNREV P2 — "Right now" is read afresh on every open.
            this._loadGuide({ refresh: true });
            // The chat focuses its own box when it mounts; the guide-only
            // stream has its box here.
            setTimeout(() => this.inputRef.el?.focus(), 60);
            // LEARNREV P0 (G4): the guide-only stream renders afresh on every
            // open too — show the latest turn, not the first. (The PayAI chat
            // scrolls itself on mount.)
            if (!this.chat) {
                setTimeout(() => this._scrollFallback(), 80);
            }
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
            const g = this.guideOn ? this.state.guide : null;
            if (this.guideOn) {
                // LEARNREV P2 (G25) — the nudge has one job: say what the
                // screen is for (the Guide's purpose, not the blurb) and
                // open the Guide. Watch only when a walkthrough offers it.
                const watch = this._guideWatchKey();
                title = fmt(T("gFirstOn"), { screen: tx(s.name) });
                body = (g && g.screen && g.screen.purpose) || tx(s.blurb);
                tools = `<button class="lrn-btn sm pri" data-act="c-fvguide">${ic("panel-right")}${esc(T("gOpenGuide"))}</button>
                    ${watch ? `<button class="lrn-btn sm" data-act="c-fvwatch">${ic("play")}${esc(T("scWatch"))}</button>` : ""}
                    <button class="lrn-btn sm ghost" data-act="c-mlater">${esc(T("fvLater"))}</button>`;
            } else {
                title = `${T("fvOn")}${SP}${tx(s.name)}?`;
                body = tx(s.blurb);
                tools = `<button class="lrn-btn sm pri" data-act="c-fvexplain">${ic("info")}${esc(T("explainScreen"))}</button>
                    ${m.watch ? `<button class="lrn-btn sm" data-act="c-fvwatch">${ic("play")}${esc(T("scWatch"))}</button>` : ""}
                    <button class="lrn-btn sm ghost" data-act="c-mlater">${esc(T("fvLater"))}</button>`;
            }
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
            // ONECHAT OC2 — through the queue: the chat has not mounted yet,
            // so the answer is held until it attaches (ledger OC4).
            this.openHelper({ explain: true });
        } else if (act === "c-fvwatch" && (this.guideOn ? this._guideWatchKey() : m.watch)) {
            this.startScenario(this.guideOn ? this._guideWatchKey() : m.watch, "watch", "");
        } else if (act === "c-fvguide") {
            this._openGuideHere(true);
        }
    }

    /** LEARNREV P2 — the first walkthrough the Guide lists that offers Watch. */
    _guideWatchKey() {
        const tasks = ((this.state.guide && this.state.guide.doors) || {}).tasks || [];
        const t = tasks.find((x) => (x.modes || []).includes("watch") && this._offers(x.key, "watch"));
        return t ? t.key : "";
    }

    // ------------------------------------------------------- ONECHAT OC2
    /** The registered chat entry, whoever may use it (the group check is in
     *  onWillStart). `pb_helper_chat/main`; the old `pb_helper_tabs/ask` name
     *  is read only as a fallback — a three-line shim, removed next release. */
    _chatEntry() {
        const reg = registry.category(HELPER_CHAT);
        if (reg.contains("main")) {
            return reg.get("main");
        }
        const old = registry.category(HELPER_TABS);
        return old.contains("ask") ? old.get("ask") : null;
    }

    /** PayAI's embedded chat, when it is installed AND this person may use
     *  it. Null means the drawer draws its own guide-only stream. */
    get chat() {
        return this.chatAllowed ? this._chatEntry() : null;
    }

    /** THE ONE WAY IN from outside the drawer: the header's Explain, the
     *  moment card's Explain, ⌘K, a suggested question. Opens the drawer and
     *  queues the request until the chat has mounted and attached — before
     *  that there is nothing to draw it in (ledger OC4). Without a chat the
     *  guide-only stream takes it at once. */
    openHelper(opts = {}) {
        // LEARNREV P3 — `guide: {section: "this" | "screen" | "fields",
        // field}`: the drawer opens docked (where docking exists) with that
        // section expanded and, for a field, its Fields row open and in view.
        // With the Guide switched off there is no panel: Explain this screen
        // is the floor, as everywhere else.
        if (opts.guide) {
            if (this.guideOn) {
                this._applyGuide(Object.assign({ screen: this.state.screen }, opts.guide));
            } else {
                opts = Object.assign({}, opts, { explain: true });
            }
        }
        if (!this.state.open) {
            this.state.open = true;
            this.state.moment = null;
            this._sentThisOpen = false;
            if (!opts.guide) {
                this.state.gFolded = false;
            }
            this._log("coach_open");
            this._loadGuide({ refresh: true });
        }
        if (!this.chat) {
            if (opts.explain) {
                this._explainInto();
            } else if (opts.text && opts.send) {
                this.ask(opts.text);
            } else if (opts.text) {
                this.state.question = opts.text;
            }
            return;
        }
        if (opts.explain || opts.text) {
            this._queue.push(opts);
        }
        if (this._api) {
            this._flush();
        }
    }

    /** Called by the chat once it has mounted (and loaded its history). */
    _attach(api) {
        this._api = api;
        this._flush();
    }

    _detach(api) {
        // `this._api === null`: the chat went away before it ever attached
        // (the drawer closed while its history was loading).
        if (!api || this._api === api || this._api === null) {
            this._api = null;
            this.menu.close();
            // Whatever was still waiting for this chat (a ⌘K sentence, an
            // Explain) was given up with it: never sent on a later open.
            this._queue = [];
        }
    }

    async _flush() {
        if (this._flushing) {
            return;
        }
        this._flushing = true;
        try {
            while (this._api && this._queue.length) {
                const api = this._api;
                const item = this._queue.shift();
                if (item.explain) {
                    await this._explainInto();
                } else if (item.text && item.send) {
                    await api.sendText(item.text, { origin: item.origin || "helper" });
                } else if (item.text) {
                    api.setDraft(item.text);
                }
            }
        } finally {
            this._flushing = false;
        }
    }

    /** Explain this screen, drawn as a turn in whichever stream is showing. */
    async _explainInto() {
        const answer = await this.explainScreen();
        if (this._api) {
            await this._api.pushGuide(answer, { kind: "explain" });
            return;
        }
        if (answer) {
            this._pushTurn({ kind: "guide", answer });
        } else {
            this._pushTurn({ kind: "note", note: this._pair("coachNoScreen") });
        }
    }

    /** A sentence, sent as if typed: through the router. */
    _say(text, origin) {
        const t = String(text || "").trim();
        if (!t) {
            return;
        }
        if (this.chat) {
            this.openHelper({ text: t, send: true, origin: origin || "chip" });
        } else {
            this.ask(t);
        }
    }

    // --------------------------------------------------- the helper object
    /** What the chat is handed. Plain functions over this component's state,
     *  read at call time, so the object never changes identity. Every
     *  renderer takes the language explicitly: the chat passes its `lang`
     *  prop, which is what re-renders past guide turns on a flip. */
    _makeHelper() {
        return {
            T: (key, lang) => this._inLang(lang, () => T(key)),
            text: (pair, lang) => this._inLang(lang, () => tx(pair)),
            screen: () => this.state.screen,
            screenLabelPair: () => ({
                en: this._inLang("en", () => this.screenLabel),
                vi: this._inLang("vi", () => this.screenLabel),
            }),
            covered: () => this.covered,
            canExplain: () => this.covered,
            answerHTML: (answer, lang, opts) =>
                markup(this._inLang(lang, () => this._answerHTML(answer, opts || {}))),
            // ONECHAT OC3 — the same answer as plain words, for read-back.
            answerSpeech: (answer, lang) => this._inLang(lang, () => this._answerSpeech(answer)),
            turnHTML: (turn, lang, opts) =>
                markup(this._inLang(lang, () => this._turnHTML(turn, opts || {}))),
            contextHTML: (lang, opts) =>
                markup(this._inLang(lang, () => this._contextHTML(opts || {}))),
            consentHTML: (lang) => markup(this._inLang(lang, () => this._consentHTML())),
            chipsHTML: (chips, lang) => markup(this._inLang(lang, () => this._chipsHTML(chips, "c-extra"))),
            pair: (key) => this._pair(key),
            practiseChip: (answer) => this._practiseChip(answer),
            scenarioName: (key) => {
                const sc = this.sc.get(key);
                return sc ? sc.name : null;
            },
            onGuideAnswer: (question, answer) => this._onGuideAnswer(question, answer),
            explain: () => this.explainScreen(),
            explainFor: (screenKey) => this._explainFor(screenKey),
            answerFor: (key) => this._answerFor(key),
            startPractice: (key, mode) => this.startScenario(key, mode, ""),
            // LEARNREV P2 — the Guide's arguments (the Mapping scheme), sent
            // with a routed sentence so whatnext reads the same Right now.
            // LEARNREV P3 — the chat asks for these exactly once per routed
            // sentence (`_route`), so it is also how the drawer learns that a
            // message was sent: the Guide folds to its titles (S8b).
            guideArgs: () => {
                this._chatSent();
                return this.guideOn ? this._guideArgs() : {};
            },
            openPracticeMode: () => this.openPractice(),
            attach: (api) => this._attach(api),
            detach: (api) => this._detach(api),
        };
    }

    /** Run `fn` with the runtime language set to `lang`. RT.lang already
     *  follows the pill; this only makes a renderer's language explicit. */
    _inLang(lang, fn) {
        const want = lang === "vi" || lang === "en" ? lang : RT.lang;
        const saved = RT.lang;
        RT.lang = want;
        try {
            return fn();
        } finally {
            RT.lang = saved;
        }
    }

    /** A chrome string in both languages, for a turn that re-renders on a flip. */
    _pair(key) {
        const v = (RT.chrome || {})[key];
        const pair = v && typeof v === "object" ? { en: v.en || "", vi: v.vi || v.en || "" } : { en: key, vi: key };
        pair.key = key;
        return pair;
    }

    _turnId() {
        TURN_SEQ += 1;
        return `h${TURN_SEQ}`;
    }

    /** Push a helper turn into whichever stream is showing. */
    _pushTurn(turn) {
        if (this._api) {
            return this._api.pushTurn(turn);
        }
        const t = Object.assign({ id: this._turnId(), screen: this.state.screen }, turn);
        this.state.turns.push(t);
        this._scrollFallback();
        return t;
    }

    _findTurn(id) {
        if (!id) {
            return null;
        }
        if (this._api) {
            return this._api.findTurn(id);
        }
        return this.state.turns.find((t) => t.id === id) || null;
    }

    _hasConversation() {
        return this._api ? !this._api.isEmpty() : this.state.turns.length > 0;
    }

    async _answerFor(key) {
        if (!key) {
            return null;
        }
        try {
            return await this.orm.call("learn.intent", "answer_for", [key, this.state.screen, RT.lang]);
        } catch {
            return null;
        }
    }

    /** One guide answer by key — a "How it works" choice, "Explain how
     *  instead". Never routed: the person already said which they meant. */
    async _answerInto(key) {
        const answer = await this._answerFor(key);
        if (!answer) {
            return;
        }
        if (this._api) {
            await this._api.pushGuide(answer, { kind: "guide" });
        } else {
            this._pushTurn({ kind: "guide", answer });
        }
    }

    /** The scenarios on THIS screen that can be practised. */
    _screenTry() {
        return this.screenScenarios.filter((sc) => (sc.modes || []).includes("try"));
    }

    /** "Practise this" under an answer: the scenario the answer teaches, if
     *  the engine really offers Try for it (`_offers`), else nothing. The
     *  Access walkthrough has no Try at all, so it can never be offered. */
    _practiseChip(answer) {
        const key = answer && answer["try"];
        if (!this._offers(key, "try")) {
            return null;
        }
        return { key, name: this.sc.get(key).name };
    }

    /** Practise one scenario: a practice turn first ("Opening practice: …"),
     *  then the practice itself after a beat. Never "Do it live". */
    _practiseFrom(key, mode) {
        const m = mode || "try";
        if (!this._offers(key, m)) {
            return;
        }
        if (this._api) {
            this._api.practise(key, m);
            return;
        }
        const sc = this.sc.get(key);
        this._pushTurn({ kind: "practice", practice: { key, mode: m, name: sc ? sc.name : "" } });
        setTimeout(() => this.startScenario(key, m, ""), PRACTICE_BEAT_MS);
    }

    /** "Let me practise this" on the context card. */
    _practiseHere() {
        const own = this._screenTry();
        if (own.length === 1) {
            this._practiseFrom(own[0].key, "try");
            return;
        }
        if (!own.length) {
            return;
        }
        this._pushTurn({
            kind: "practice",
            practice: {
                chips: own.slice(0, MAX_CHIPS).map((sc) => ({ key: sc.key, mode: "try", name: sc.name })),
                sandbox: true,
            },
        });
    }

    _toggleSimpler(id) {
        const turn = this._findTurn(id);
        if (turn) {
            turn.simpler = !turn.simpler;
        }
    }

    /** A "Which did you mean?" chip. Resolved WITHOUT routing again. */
    async _pickChoice(id, index) {
        const turn = this._findTurn(id);
        const choice = turn && (turn.choices || [])[index];
        if (!choice || turn.picked !== undefined && turn.picked !== null) {
            return;
        }
        turn.picked = index;
        // PayAI was still answering, so nothing was sent: the choice stays
        // open to press again rather than being used up for nothing.
        if ((await this._runChip(choice, turn)) === false) {
            turn.picked = null;
        }
    }

    /** "Explain how instead" / "Do it for me" under a turn. */
    async _extraChip(id, index) {
        const turn = this._findTurn(id);
        const chip = turn && (turn.extra || [])[index];
        if (chip) {
            await this._runChip(chip, turn);
        }
    }

    /** Run a chip; false when nothing could be done (PayAI busy). A PayAI
     *  chip re-sends the words of the turn it sits under: when those words
     *  were SPOKEN, the send stays spoken (`turn.spoken`), so a plan made
     *  from it still needs a tap where it names a person or an amount
     *  (owner decision Q6). The flag only ever makes the send stricter. */
    async _runChip(chip, turn) {
        if (chip.route === "guide") {
            await this._answerInto(chip.key);
        } else if (chip.route === "practice") {
            this._practiseFrom(chip.key, chip.mode || "try");
        } else if (chip.route === "payai" && this._api) {
            const text = typeof chip.text === "string" ? chip.text : tx(chip.label || "");
            const spoken = !!(turn && turn.spoken);
            return (await this._api.sendDirect({ text, askOnly: !!chip.ask_only, spoken })) !== false;
        } else {
            return false;
        }
        return true;
    }

    /** "Show again" on a history marker: the answer, drawn in place. */
    async _expandMarker(id) {
        const turn = this._findTurn(id);
        if (!turn) {
            return;
        }
        if (turn.expanded) {
            turn.expanded = null;
            return;
        }
        // `answer_for` takes an intent key, `column:<key>` and `screen:<key>`
        // alike — exactly the keys a marker carries.
        const answer = ["guide", "explain"].includes(turn.mkind) && turn.key
            ? await this._answerFor(turn.key) : null;
        if (answer && answer.matched) {
            turn.expanded = answer;
        }
    }

    _clearConversation() {
        if (this._api) {
            this._api.clear();
        } else {
            this.state.turns = [];
        }
        this.state.askConsent = false;
        this.state.pendingQ = null;
    }

    _focusMore() {
        setTimeout(() => {
            const el = document.querySelector(".lrn-drawer [data-act='c-more']");
            if (el) {
                el.focus();
            }
        }, 0);
    }

    /** Arrow keys move through the More menu; Enter picks (a real button). */
    onMenuKey(ev) {
        if (!this.menu.open || !["ArrowDown", "ArrowUp", "Home", "End"].includes(ev.key)) {
            return;
        }
        const items = Array.from(document.querySelectorAll(".lrn-menu [role^='menuitem']"));
        if (!items.length) {
            return;
        }
        ev.preventDefault();
        const at = items.indexOf(document.activeElement);
        let next = 0;
        if (ev.key === "End") {
            next = items.length - 1;
        } else if (ev.key === "ArrowDown") {
            next = at < 0 ? 0 : (at + 1) % items.length;
        } else if (ev.key === "ArrowUp") {
            next = at <= 0 ? items.length - 1 : at - 1;
        }
        items[next].focus();
    }

    _openMenu() {
        this.menu.open = !this.menu.open;
        this.menu.confirm = false;
        if (this.menu.open) {
            setTimeout(() => {
                const first = document.querySelector(".lrn-menu [role^='menuitem']");
                if (first) {
                    first.focus();
                }
            }, 0);
        }
    }

    /** The phone's keyboard: what is left of the screen above it. */
    _onViewport() {
        const vv = window.visualViewport;
        if (!vv) {
            return;
        }
        const root = document.documentElement;
        root.style.setProperty("--lrn-vvh", `${Math.round(vv.height)}px`);
        const kb = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
        root.style.setProperty("--lrn-kb", `${kb}px`);
    }

    /** "On: <screen>" in the header. The content plane's name when it covers
     *  the screen, the action's own name when it does not — every screen gets
     *  named, which is the point of saying where the helper thinks you are. */
    get screenLabel() {
        void this.state.lang;
        const s = this.screenInfo;
        if (this.onHub) {
            // "Pay Run › Payslips" — the hub and the tab, in the helper's
            // language, plus the inner tab or open panel when that is what
            // the lesson is about ("Pay Run › Adjust › Proration").
            const hs = this.hubScreen;
            const hub = hs ? tx(hs.name) : this.place.hubLabel;
            const tab = this.place.lens ? this.tabLabel(this.place.lens) : "";
            let label = tab ? `${hub}${SP}›${SP}${tab}` : hub;
            if (s && !s.hub && (placeSub() || this.place.detail)) {
                label = `${label}${SP}›${SP}${tx(s.name)}`;
            }
            return label;
        }
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

    // ------------------------------------------------ LEARN REFRESH step 1
    /** Read by the template root: the subscription to tab changes. */
    get placeKey() {
        const p = this.place;
        const sub = p.subs[`${p.tag}:${p.lens}`] || "";
        // LEARNREV P2 — and the scheme a Mapping tab shows (its Right now).
        const cfg = (p.extra && p.extra.config_id) || 0;
        return `${p.seq}|${p.tag}|${p.lens}|${sub}|${p.detail}|${p.lenses.length}|${cfg}`;
    }

    /** True while the action on screen is the hub that published the place. */
    get onHub() {
        const a = this.action.currentController?.action;
        return !!(this.place.tag && a && a.tag === this.place.tag);
    }

    /** The hub's own page in the content plane (its orientation), or null. */
    get hubScreen() {
        return this.onHub ? hubScreenOf(this.bundle?.screens || [], this.place.tag) : null;
    }

    /** A tab's name in the helper's language; the rail's label when the
     *  content has no words for it (a tab added after this was written). */
    tabLabel(lens) {
        const n = tabName(this.bundle?.screens || [], this.place.tag, lens);
        if (n) {
            return n;
        }
        const l = this.place.lenses.find((x) => x.key === lens);
        return l ? l.label : lens;
    }

    tabLine(lens) {
        const hs = this.hubScreen;
        const t = hs && hs.hub.tabs && hs.hub.tabs[lens];
        return t ? tx(t.line) : "";
    }

    /** The in-product "Reduce motion" choice as well as the system's. */
    get isStill() {
        return reduced();
    }

    /** "Take me there": the hub switches its own tab; the drawer stays. */
    goTab(lens) {
        const ok = switchLens(lens);
        this.state.gotoFailed = !ok;
        if (ok) {
            this._log("coach_goto", lens);
        }
    }

    close() {
        this.state.open = false;
        this.menu.close();
        // A ⌘K sentence or an Explain still waiting for the chat to mount
        // was given up when the person closed the drawer: it must not be
        // sent on some later, unrelated open.
        this._queue = [];
        // ONECHAT OC2 — the conversation is KEPT across a close (the chat's
        // turns live for the page's life; so does the guide-only stream).
        // What does not survive is half-typed text in the guide-only box.
        this.state.question = "";
        // A question held pending a consent answer does not survive the
        // drawer closing. Closing without answering is not a yes, and text
        // kept across a close would eventually be stored against a question
        // the person had moved on from.
        if (this.state.askConsent) {
            this._dropConsent();
        }
        this.state.askConsent = false;
        this.state.pendingQ = null;
    }

    // ------------------------------------------- the guide-only stream
    onInput(ev) {
        this.state.question = ev.target.value;
        this._grow(ev.target);
    }

    onSubmit(ev) {
        ev.preventDefault();
        this.ask(this.state.question);
    }

    /** Enter sends, Shift+Enter is a new line — the chat's own rule. */
    onComposerKey(ev) {
        if (ev.key === "Enter" && !ev.shiftKey && !ev.isComposing) {
            ev.preventDefault();
            this.ask(this.state.question);
        }
    }

    /** One to five lines, then it scrolls. */
    _grow(el) {
        if (!el || !el.style) {
            return;
        }
        el.style.height = "auto";
        el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }

    _scrollFallback() {
        setTimeout(() => {
            const el = document.querySelector(".lrn-drawer .lrn-stream");
            if (el) {
                el.scrollTop = el.scrollHeight;
            }
        }, 30);
    }

    /** A divider for the screen the next turn is about, when it moved. */
    _markScreen() {
        const turns = this.state.turns;
        const last = turns[turns.length - 1];
        if (!last || last.screen !== this.state.screen) {
            this.state.turns.push({
                id: this._turnId(), kind: "context", live: false,
                screen: this.state.screen,
                label: { en: this._inLang("en", () => this.screenLabel),
                         vi: this._inLang("vi", () => this.screenLabel) },
            });
        }
    }

    /** THE GUIDE-ONLY COMPOSER (no PayAI chat for this person). The same
     *  router the chat uses decides; only its base layer answers here —
     *  guide, explain, practice, capability, a note, or the honest miss. */
    async ask(question) {
        const q = (question || "").trim();
        if (!q || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.question = "";
        this._chatSent();
        this._markScreen();
        this.state.turns.push({ id: this._turnId(), kind: "person", text: q, screen: this.state.screen });
        this._scrollFallback();
        try {
            const kwargs = { screen_key: this.state.screen, lang: RT.lang, session_id: null };
            const guideArgs = this.guideOn ? this._guideArgs() : {};
            if (Object.keys(guideArgs).length) {
                kwargs.context = { pb_guide_args: guideArgs };
            }
            const r = await this.orm.call("learn.helper", "route", [q], kwargs);
            await this._fallbackDispatch(q, r || {});
        } catch {
            this._pushTurn({ kind: "note", note: this._pair("routeFailed") });
        } finally {
            this.state.busy = false;
            this._scrollFallback();
            setTimeout(() => this.inputRef.el?.focus(), 30);
        }
    }

    async _fallbackDispatch(q, r) {
        const route = r.route;
        if (route === "guide" && r.answer) {
            this._pushTurn({ kind: "guide", answer: r.answer, lead: r.lead || null });
            await this._onGuideAnswer(q, r.answer);
        } else if (route === "explain") {
            await this._explainInto();
        } else if (route === "practice") {
            if (r.answer) {
                this._pushTurn({ kind: "guide", answer: r.answer });
            }
            const p = r.practice || {};
            this._pushTurn({ kind: "practice", practice: p, note: r.note || null });
            if (p.key && (p.mode === "try" || !r.note)) {
                setTimeout(() => this.startScenario(p.key, p.mode, ""), PRACTICE_BEAT_MS);
            }
        } else if (route === "choose") {
            const choices = (r.choices || []).filter((c) => c.route !== "payai");
            this._pushTurn({ kind: "choose", note: r.note || null, choices });
        } else if (route === "miss" && r.answer && !r.note) {
            this._pushTurn({ kind: "guide", answer: r.answer });
            await this._onGuideAnswer(q, r.answer);
        } else {
            // A note (small talk, nothing waiting, no assistant here) — or a
            // PayAI route, which this stream cannot take: say so plainly.
            const note = r.note || this._pair("noPayai");
            this._pushTurn({ kind: "note", note, suggest: r.suggest || [] });
            if (route === "miss") {
                await this._onGuideAnswer(q, r.answer || { matched: false });
            }
        }
    }

    /** What every guide answer does once it is on screen, whichever stream
     *  drew it: the hit/miss count, and the consent-gated question store.
     *  NEVER the question text in the log. */
    async _onGuideAnswer(q, answer) {
        if (!answer) {
            return;
        }
        try {
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
            // Measurement and mining must never break the answer on screen.
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
                if (!this.state.askConsent) {
                    this.state.askConsent = true;
                    // ONECHAT OC2 — a turn in the stream, BELOW the answer it
                    // rides along with (never a toll gate above it).
                    this._pushTurn({ kind: "consent" });
                }
            }
        } catch {
            // Consent plumbing must never break the answer it rides along
            // with. Failing closed means nothing is stored, which is the
            // right direction to fail in.
        }
    }

    async decideConsent(granted) {
        this.state.askConsent = false;
        this._dropConsent();
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
        // ONECHAT OC2 — returns the answer; whoever asked draws it as a turn
        // (`_explainInto`, or the chat's own route dispatch).
        if (!this.state.screen) {
            return null;
        }
        try {
            const answer = await this.orm.call(
                "learn.intent", "explain_screen", [this.state.screen, RT.lang]);
            this._log(answer.matched ? "coach_hit" : "coach_miss",
                      answer.key || "");
            return answer;
        } catch {
            return null;
        }
    }

    /** "Show again" on an Explain marker: that screen's explanation. */
    async _explainFor(screenKey) {
        if (!screenKey) {
            return null;
        }
        try {
            return await this.orm.call("learn.intent", "explain_screen", [screenKey, RT.lang]);
        } catch {
            return null;
        }
    }

    _dropConsent() {
        if (this._api) {
            this._api.dropTurns("consent");
        } else {
            this.state.turns = this.state.turns.filter((t) => t.kind !== "consent");
        }
    }

    async askIntent(key, label) {
        // A suggested question is asked with its own label, so the transcript
        // reads like a conversation rather than a menu selection — and it
        // goes through the router, exactly as if it had been typed.
        this._say(label || this._labelOf(key), "suggest");
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
            // Said in the stream, as its own short turn: the answer above it
            // stays as it was.
            this._pushTurn({ kind: "note", note: this._pair("pointNotHere") });
        } else {
            this.close();
        }
    }

    /** "Open the lesson" opens THIS screen's lesson (LEARNREV P0, G2, ledger
     *  LR-R2), in the Learn hub (rail visible), on the station's outline:
     *    1. the station whose key is this screen's key (station keys equal
     *       screen keys for content screens), or the station a retired screen
     *       folded into (`station_aliases`, the Journey's own rule), or the
     *       station whose lesson walks this screen;
     *    2. else, for a button under an answer, the station whose lesson steps
     *       point at the answer's `show_me` anchors, or whose key is a screen
     *       the answer's walkthrough (`watch` / `try`) plays on;
     *    3. else the lesson map, and the drawer says so in a note and stays
     *       open — never a silent landing at the top. Hubs (`hub_*`) land here. */
    openLesson(answer) {
        const key = this._lessonStationFor(this.state.screen, answer);
        if (key) {
            openLearn(this.action, `station:${key}`);
            this.close();
            return;
        }
        this._pushTurn({ kind: "note", note: Object.assign({}, NO_LESSON_NOTE) });
        openLearn(this.action, "");
    }

    _lessonStationFor(screen, answer) {
        const stations = (this.bundle && this.bundle.stations) || [];
        const has = (k) => !!k && stations.some((s) => s.key === k);
        const walks = (pred) => {
            const st = stations.find((s) => (s.lessons || []).some(
                (l) => (l.steps || []).some(pred)));
            return st ? st.key : "";
        };
        if (screen && !screen.startsWith("hub_")) {
            if (has(screen)) {
                return screen;
            }
            const alias = ((this.bundle && this.bundle.station_aliases) || {})[screen];
            if (has(alias)) {
                return alias;
            }
            const walked = walks((step) => step.screen === screen);
            if (walked) {
                return walked;
            }
        }
        if (answer) {
            const anchors = new Set(answer.show_me || []);
            if (anchors.size) {
                const pointed = walks((step) => anchors.has(step.anchor));
                if (pointed) {
                    return pointed;
                }
            }
            for (const sk of [answer.watch, answer["try"]]) {
                const sc = sk ? this.sc.get(sk) : null;
                const on = ((sc && sc.screens) || []).find((s) => has(s));
                if (on) {
                    return on;
                }
            }
        }
        return "";
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

    // ============================================ LEARNREV P2 — the Guide
    /** The switch is on (Learn › Settings, `bootstrap.guide`). */
    get guideOn() {
        return !!(this.bundle && this.bundle.guide);
    }

    /** The Guide is drawn above the chat: switch on, content loaded, and the
     *  helper knows which Learn screen this is. */
    get guideShown() {
        return this.guideOn && this.state.ready && !!this.state.screen;
    }

    /** The chat's `place` prop: the tab on screen, plus a tick per Guide —
     *  its only job is to redraw the chat's opening card. */
    get chatPlace() {
        return `${this.placeKey}|${this.state.gTick}`;
    }

    get askTitle() {
        void this.state.lang;
        return T("gSecAsk");
    }

    get dockLabel() {
        void this.state.lang;
        return T(this.state.dock === "dock" ? "gFloat" : "gDock");
    }

    get dockIcon() {
        return this.state.dock === "dock" ? "picture-in-picture" : "panel-right";
    }

    /** What the screen's Right now needs to know: the scheme picked on a
     *  Mapping tab (MappingStudio publishes it with its place). */
    _guideArgs() {
        const extra = (this.place && this.place.extra) || {};
        const cfg = Number(extra.config_id) || 0;
        return this.place && this.place.tag === "pb_mapping_studio" && cfg ? { config_id: cfg } : {};
    }

    /** Fetch the Guide for the screen on show. Cached per screen, arguments
     *  and language; `refresh` reads it again (Right now changes). Never
     *  throws: a failure is `gError`, drawn as its reason with a Retry. */
    async _loadGuide({ refresh = false } = {}) {
        if (!this.guideOn || !this.state.screen) {
            if (this.state.guide || this.state.gKey) {
                this.state.guide = null;
                this.state.gKey = "";
            }
            if (this._info) {
                this._info.stop();
            }
            return;
        }
        const screen = this.state.screen;
        const args = this._guideArgs();
        const lang = RT.lang === "vi" ? "vi_VN" : "en_US";
        const key = [screen, JSON.stringify(args), lang].join("|");
        const cached = this._guideCache.get(key) || null;
        if (this.state.gKey !== key) {
            this.state.gKey = key;
            this.state.guide = cached;
            this.state.gError = false;
            this._startInfo();
        }
        if ((cached && !refresh) || this._gInflight === key) {
            return;
        }
        this._gInflight = key;
        this.state.gLoading = true;
        try {
            const raw = await this.orm.call("learn.guide", "rpc_guide", [screen, args],
                                            { context: { lang } });
            const g = dropAccess(raw);
            this._guideCache.set(key, g);
            if (this.state.gKey === key) {
                this.state.guide = g;
                this.state.gTick += 1;
                this.state.gError = false;
                if (actionable(g).length) {
                    // Right now is always open when it has something to do.
                    this.state.gSec = Object.assign({}, this.state.gSec, { now: true });
                }
                this._startInfo();
            }
        } catch {
            if (this.state.gKey === key && !this.state.guide) {
                this.state.gError = true;
            }
        } finally {
            if (this._gInflight === key) {
                this._gInflight = "";
            }
            if (this.state.gKey === key) {
                this.state.gLoading = false;
            }
        }
    }

    /** Which sections were left open on this screen (default: This screen,
     *  Right now and Tasks open; Fields and Understand folded). */
    _sectionMemory(screen) {
        let all = {};
        try {
            all = JSON.parse(lsGet(SECTIONS_KEY, "{}")) || {};
        } catch {
            all = {};
        }
        return Object.assign({ screen: true, now: true, fields: false, tasks: true, understand: false },
                             all[screen] || {});
    }

    _rememberSections() {
        let all = {};
        try {
            all = JSON.parse(lsGet(SECTIONS_KEY, "{}")) || {};
        } catch {
            all = {};
        }
        all[this.state.screen] = Object.assign({}, this.state.gSec);
        lsSet(SECTIONS_KEY, JSON.stringify(all));
    }

    _toggleSection(sec) {
        if (this.state.gFolded) {
            // Folded for a conversation: a title pressed opens that section
            // (and only that one is newly open), the rest as they were.
            this.state.gFolded = false;
            this.state.gSec = Object.assign({}, this.state.gSec, { [sec]: true });
            this._rememberSections();
            return;
        }
        this.state.gSec = Object.assign({}, this.state.gSec, { [sec]: !this.state.gSec[sec] });
        this._rememberSections();
    }

    /** The same Markup object while the HTML is unchanged, so a redraw for
     *  any other reason leaves the panel's DOM (and its scroll, and the
     *  search box's focus) alone — the OWL markup-flicker rule. */
    _stable(slot, html) {
        const prev = this._markups[slot];
        if (prev !== undefined && String(prev) === html) {
            return prev;
        }
        const m = markup(html);
        this._markups[slot] = m;
        return m;
    }

    get guideHTML() {
        void this.state.lang;
        const s = this.screenInfo;
        // LEARNREV P3 (S8b) — folded while a conversation is under way: the
        // five titles only, and one link to open them again.
        const folded = !!(this.state.gFolded && this.state.guide);
        const inner = sectionsHTML(this.state.guide, {
            open: folded ? {} : this.state.gSec,
            loading: this.state.gLoading,
            error: this.state.gError,
            fallbackNext: s && s.next_step ? tx(s.next_step) : "",
            query: this._gQuery,
            expanded: this.state.gField,
            offers: (k, m) => this._offers(k, m),
            stations: (this.bundle && this.bundle.stations) || [],
            text: (pair) => tx(pair),
            watchFor: (card) => !!this._watchStep(card),
        });
        if (!folded) {
            return this._stable("guide", inner);
        }
        return this._stable("guide", `<div class="lrn-gfolded">${inner}
            <button type="button" class="lrn-gshow" data-act="c-gshow">${ic("chevron-down")}${esc(T("gShowGuide"))}</button></div>`);
    }

    /** The Fields search box: rows hide in place, nothing re-renders. */
    onGuideInput(ev) {
        const box = ev.target;
        if (!box || !box.matches || !box.matches("[data-gfind]")) {
            return;
        }
        this._gQuery = box.value || "";
        const fields = (this.state.guide && this.state.guide.fields) || [];
        const root = box.closest(".lrn-gsecb");
        let shown = 0;
        for (const card of fields) {
            const row = root && root.querySelector(`.lrn-gfield[data-field="${card.key}"]`);
            const ok = fieldMatches(card, this._gQuery);
            if (row) {
                row.hidden = !ok;
            }
            shown += ok ? 1 : 0;
        }
        const none = root && root.querySelector(".lrn-gnomatch");
        if (none) {
            none.hidden = shown > 0;
        }
    }

    /** A walkthrough step that points at this field's anchor: Watch it. */
    _watchStep(card) {
        if (!card || !card.anchor || !this.state.guide) {
            return null;
        }
        for (const t of ((this.state.guide.doors || {}).tasks || [])) {
            const sc = this.sc.get(t.key);
            if (!sc || !this._offers(t.key, "watch")) {
                continue;
            }
            const step = (sc.steps || []).find((st) => st.anchor === card.anchor);
            if (step) {
                return { scenario: t.key, key: step.key || "" };
            }
        }
        return null;
    }

    _startInfo() {
        const fields = ((this.state.guide && this.state.guide.fields) || []).filter((f) => f.anchor);
        if (!this.guideOn || !fields.length) {
            if (this._info) {
                this._info.stop();
            }
            return;
        }
        if (!this._info) {
            this._info = new InfoLayer(document,
                () => ((this.state.guide && this.state.guide.fields) || []).filter((f) => f.anchor),
                (key, btn) => this._openFieldCard(key, btn));
        }
        // After the board has drawn: the anchor may still be loading.
        setTimeout(() => this._info && this.guideOn && this._info.start(), 0);
    }

    _openFieldCard(key, btn) {
        const card = ((this.state.guide && this.state.guide.fields) || []).find((f) => f.key === key);
        if (!card) {
            return;
        }
        openFieldCard(btn, card, {
            watch: !!this._watchStep(card),
            onAction: (kind, k) => this._fieldAct(kind, k),
        });
    }

    /** A field card's footer, from the floating card or a Fields row. */
    _fieldAct(kind, key) {
        const card = ((this.state.guide && this.state.guide.fields) || []).find((f) => f.key === key);
        if (kind === "guide") {
            if (!this.state.open) {
                this.openHelper({});
            }
            this.state.gSec = Object.assign({}, this.state.gSec, { fields: true });
            this.state.gField = key;
            setTimeout(() => {
                const row = document.querySelector(`.lrn-drawer .lrn-gfield[data-field="${key}"]`);
                if (row) {
                    row.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
                }
            }, 90);
        } else if (kind === "watch") {
            const step = this._watchStep(card);
            if (step) {
                this.startScenario(step.scenario, "watch", step.key);
            }
        } else if (kind === "up" || kind === "down") {
            const up = kind === "up";
            markFeedback(key, up);
            this.orm.call("learn.guide", "rpc_feedback", [this.state.screen, key, up]).catch(() => {});
        }
    }

    /** A Right now button. */
    _guideAct(index) {
        const item = (((this.state.guide || {}).right_now || {}).items || [])[index];
        const done = item ? runAction(item.action, {
            action: this.action, openHub, bus: this.env.bus,
            doAction: (act) => this.action.doAction(act),
        }) : null;
        if (!done) {
            return;
        }
        if (done.kind === "filter") {
            // The board's chips into view, then Right now read again.
            setTimeout(() => {
                const chips = document.querySelector("[data-coach='tr-filters']");
                if (chips) {
                    chips.scrollIntoView({ block: "nearest", behavior: reduced() ? "auto" : "smooth" });
                }
            }, 60);
            setTimeout(() => this._loadGuide({ refresh: true }), 400);
        }
    }

    /** A "You are here" chip: the hub, or the hub's tab. */
    _openPath(index) {
        const p = (((this.state.guide || {}).screen || {}).path || [])[index];
        const open = p && p.open;
        if (!open || !open.xmlid) {
            return;
        }
        runAction({ kind: "open", xmlid: open.xmlid, lens: open.lens, lens_key: open.lens_key },
                  { action: this.action, openHub });
    }

    /** A before / next chip: that screen, at its first place. */
    _openScreen(key) {
        const screens = (this.bundle && this.bundle.screens) || [];
        const s = screens.find((x) => x.key === key);
        if (!s) {
            return;
        }
        for (const place of s.places || []) {
            const [tag, lens] = String(place).split(":");
            const hub = hubScreenOf(screens, tag);
            if (hub && hub.hub && hub.hub.xmlid && lens) {
                runAction({ kind: "open", xmlid: hub.hub.xmlid, lens, lens_key: hub.hub.lens_key || "pb_lens" },
                          { action: this.action, openHub });
                return;
            }
        }
        const nav = (s.navs || [])[0];
        if (nav) {
            this.action.doAction(nav);
        }
    }

    /** Docked: a body class the page makes room for (coach.scss, ≥ 1280 px
     *  only), with the panel's top just under the top bar. */
    _syncDock() {
        const on = !!(this.guideOn && this.state.open && this.state.dock === "dock");
        if (on) {
            const nav = document.querySelector(".o_main_navbar");
            const top = nav ? Math.max(0, Math.round(nav.getBoundingClientRect().bottom)) : 0;
            document.documentElement.style.setProperty("--lrn-dock-top", `${top}px`);
            document.body.classList.add("lrn-docked");
        } else {
            document.body.classList.remove("lrn-docked");
        }
    }

    _toggleDock() {
        this.state.dock = this.state.dock === "dock" ? "float" : "dock";
        lsSet(DOCK_KEY, this.state.dock);
    }

    /** "Open the Guide" (under Explain, on the first-visit card): the drawer
     *  open, docked, with This screen expanded. */
    _openGuideHere(dock) {
        if (dock && this.state.dock !== "dock") {
            this.state.dock = "dock";
        }
        this.state.gSec = Object.assign({}, this.state.gSec, { screen: true });
        if (!this.state.open) {
            this.openHelper({});
        }
        setTimeout(() => {
            const el = document.querySelector(".lrn-drawer .lrn-guide");
            if (el) {
                el.scrollTop = 0;
            }
        }, 60);
    }

    // ============================================ LEARNREV P3 — the doors in
    /** Open the Guide the way a Library row / a field result asked for:
     *  docked where docking exists, unfolded, that section open and — for a
     *  field — its Fields row expanded and scrolled into view once the
     *  screen's Guide has arrived. Waits (`_pendingGuide`) when the screen it
     *  names is not grounded yet; `_ground` applies it then. */
    _applyGuide(want) {
        const sec = want.section === "this" ? "screen" : (want.section || "screen");
        if (want.screen && want.screen !== this.state.screen) {
            this._pendingGuide = want;
            return;
        }
        this._pendingGuide = null;
        if (window.innerWidth >= DOCK_MIN_PX && this.state.dock !== "dock") {
            // Not remembered: the person's own choice (the header button) is.
            this.state.dock = "dock";
        }
        this.state.gFolded = false;
        const open = Object.assign({}, this.state.gSec, { [sec]: true });
        if (want.field) {
            open.fields = true;
            this.state.gField = want.field;
        }
        this.state.gSec = open;
        const field = want.field || "";
        let tries = 0;
        const reveal = () => {
            tries += 1;
            const root = document.querySelector(".lrn-drawer .lrn-guide");
            const target = field
                ? root && root.querySelector(`.lrn-gfield[data-field="${field}"]`)
                : root && root.querySelector(`.lrn-gsec[data-sec="${sec}"]`);
            if (target) {
                target.scrollIntoView({ block: field ? "center" : "start",
                                        behavior: reduced() ? "auto" : "smooth" });
                return;
            }
            // The Guide for a screen just opened is still on its way.
            if (tries < 30) {
                setTimeout(reveal, 150);
            }
        };
        setTimeout(reveal, 90);
    }

    /** The Library's Guide chip and the ⌘K field rows: open `screenKey`
     *  where it lives, wait for its hub to say it arrived (the walkthrough's
     *  own seam), then open the drawer on its Guide. A screen this person
     *  cannot open is not opened at all ("unreachable": the Library shows its
     *  outline with a grey note instead). */
    async _guideAt(screenKey, opts = {}) {
        const screens = (this.bundle && this.bundle.screens) || [];
        const screen = screens.find((s) => s.key === screenKey);
        if (!screen) {
            return "missing";
        }
        if (reachable(screen) === false || !canOpen(screen)) {
            return "unreachable";
        }
        const want = { screen: screenKey, section: opts.section || "screen", field: opts.field || "" };
        let where = "here";
        try {
            const res = await openScreen(this.action, screens, screen);
            if (res && res.place) {
                where = await waitForPlace(res.place, res.seq);
            } else {
                await new Promise((r) => setTimeout(r, 300));
            }
        } catch {
            return "missing";
        }
        if (where === "elsewhere") {
            // The shell moved this person off a tab they cannot open.
            return "elsewhere";
        }
        this._resolveScreen();
        this.openHelper({ guide: want });
        return "here";
    }

    /** A message was sent: the first one of this drawer session folds the
     *  Guide to its section titles, so the conversation gets the height —
     *  unless this person asked for the Guide to stay open on this screen. */
    _chatSent() {
        if (this._sentThisOpen) {
            return;
        }
        this._sentThisOpen = true;
        if (!this.guideShown || this._guideKeptOpen(this.state.screen)) {
            return;
        }
        this.state.gFolded = true;
    }

    _guideKeptOpen(screen) {
        try {
            return !!(JSON.parse(lsGet(GUIDE_SHOW_KEY, "{}")) || {})[screen];
        } catch {
            return false;
        }
    }

    /** "Show the Guide": open the sections again, and keep them open on this
     *  screen from now on. */
    _showGuide() {
        this.state.gFolded = false;
        let all = {};
        try {
            all = JSON.parse(lsGet(GUIDE_SHOW_KEY, "{}")) || {};
        } catch {
            all = {};
        }
        if (this.state.screen) {
            all[this.state.screen] = 1;
            lsSet(GUIDE_SHOW_KEY, JSON.stringify(all));
        }
    }

    /** The header's title: "Guide · <screen>" while the Guide shows, the
     *  helper's own name otherwise. */
    get headTitle() {
        void this.state.lang;
        const s = this.screenInfo;
        if (this.guideShown && s) {
            return fmt(T("gHead"), { screen: tx(s.name) });
        }
        return T("coachName");
    }

    /** The full "Pay Run › Runs" place, as the title's tooltip while the
     *  short "Guide · Runs" is what the header shows. */
    get headHint() {
        return this.guideShown ? this.screenLabel : "";
    }

    // -------------------------------------------------------------- rendering
    get bodyHTML() {
        // THE SUBSCRIPTION. Read during render, so flipping the language
        // re-renders the whole drawer — the answer, the grounded line, the
        // suggestions and the chrome — from the other language slot of the
        // payload we already hold. Without this read the assignment in
        // toggleLang() changes a value nobody is watching. Do not "tidy" it
        // away: `tx()` below reads RT.lang, which OWL cannot see.
        //
        // ONECHAT OC2 — this is now the GUIDE-ONLY stream: drawn only when
        // there is no PayAI chat for this person. The chat draws the same
        // turns through `helper.turnHTML`, so both read as one surface.
        const lang = this.state.lang;
        void lang;
        void this.place.lens;
        if (!this.state.ready) {
            // The content plane is what failed, so the sentence cannot come
            // from it: the one string this drawer carries itself.
            return markup(`<div class="lrn-cground off">${ic("info")}
                <span>${esc(LOAD_FAILED[RT.lang] || LOAD_FAILED.en)}</span></div>`);
        }
        const turns = this.state.turns;
        if (!turns.length) {
            // The banner only while nothing has been said, then it is gone.
            return markup(`<p class="lrn-dhonest">${ic("shield-check")}<span>${esc(T("honestGuide"))}</span></p>
                ${this._contextHTML({})}`);
        }
        return markup(turns.map((t) => this._turnHTML(t, {})).join(""));
    }

    /** ONE TURN, ONE VISUAL LANGUAGE. Every turn the helper itself writes —
     *  a guide answer, a note, a practice turn, a choice, the consent card,
     *  the screen divider, a history marker — is drawn here, for both
     *  streams. PayAI's own answers and plan cards are drawn by its chat,
     *  in the same card frame (ai_insight_chat.scss). */
    _turnHTML(t, opts) {
        if (!t) {
            return "";
        }
        const id = esc(t.id || "");
        switch (t.kind) {
            case "person":
                return `<div class="lrn-turn me" data-turn="${id}"><div class="lrn-tbubble">${esc(t.text)}</div></div>`;
            case "guide": {
                const lead = t.lead ? `<p class="lrn-tlead">${esc(tx(t.lead))}</p>` : "";
                return `<div class="lrn-turn ai guide" data-turn="${id}">${lead}${this._answerHTML(t.answer, { simpler: t.simpler })}${this._chipsHTML(t.extra, "c-extra")}</div>`;
            }
            case "note":
                return `<div class="lrn-turn ai note" data-turn="${id}" role="status">
                    <div class="lrn-tnote">${ic("info")}<span>${esc(tx(t.note))}</span></div>${this._suggestFrom(t.suggest || [])}</div>`;
            case "practice":
                return `<div class="lrn-turn ai practice" data-turn="${id}">${this._practiceTurnHTML(t)}</div>`;
            case "choose": {
                const picked = t.picked !== undefined && t.picked !== null;
                const chips = (t.choices || []).map((c, i) => `<button type="button" class="lrn-tchip${picked && t.picked === i ? " on" : ""}"
                        data-act="c-choice" data-i="${i}"${picked ? " disabled" : ""}>${ic(c.route === "payai" ? "sparkles" : (c.route === "practice" ? "flask" : "compass"))}<span>${esc(tx(c.label))}</span></button>`).join("");
                return `<div class="lrn-turn ai choose" data-turn="${id}">
                    <p class="lrn-tlead">${esc(tx(t.note || this._pair("whichMeant")))}</p><div class="lrn-tchips">${chips}</div></div>`;
            }
            case "consent":
                return `<div class="lrn-turn ai consent" data-turn="${id}">${this._consentHTML()}</div>`;
            case "context":
                if (t.live) {
                    return `<div class="lrn-turn ctx" data-turn="${id}">${this._contextHTML(opts)}</div>`;
                }
                return `<div class="lrn-tdivider" data-turn="${id}"><span>${ic("map-pin")}${esc(T("onScreen"))}${SP}${esc(tx(t.label || ""))}</span></div>`;
            case "marker":
                return `<div class="lrn-turn ai marker" data-turn="${id}">${this._markerHTML(t)}</div>`;
            default:
                return "";
        }
    }

    /** A turn the history brought back after a page load. The guide's answer
     *  itself was never stored (only an authored label), so "Show again"
     *  asks for it by key and draws it in place. */
    _markerHTML(t) {
        const again = ["guide", "explain"].includes(t.mkind) && !!t.key;
        let line = "";
        if (t.mkind === "guide") {
            line = `${ic("compass")}<span>${esc(T("fromGuide"))}:${SP}${esc(t.label || "")}</span>`;
        } else if (t.mkind === "composed") {
            line = `${ic("sparkles")}<span>${esc(T("composedAgain"))}</span>`;
        } else if (t.mkind === "explain") {
            line = `${ic("scan-text")}<span>${esc(t.label || "")}</span>`;
        } else if (t.mkind === "practice") {
            line = `${ic("flask")}<span>${esc(t.label || "")}</span>`;
        } else {
            line = `${ic("info")}<span>${esc(t.label || "")}</span>`;
        }
        const btn = again ? `<button type="button" class="lrn-tagain" data-act="c-again"
            aria-expanded="${t.expanded ? "true" : "false"}">${ic("rotate-ccw")}${esc(T("showAgain"))}</button>` : "";
        const body = t.expanded ? `<div class="lrn-tmore">${this._answerHTML(t.expanded, { simpler: t.simpler })}</div>` : "";
        return `<div class="lrn-tmarker">${line}${btn}</div>${body}`;
    }

    _practiceTurnHTML(t) {
        const p = t.practice || {};
        const note = t.note ? `<div class="lrn-tnote">${ic("info")}<span>${esc(tx(t.note))}</span></div>` : "";
        if (p.key) {
            const watchOnly = p.mode === "watch" && !!t.note;
            const sentence = (p.mode === "watch" ? T("openingWatch") : T("openingPractice"))
                .replace("{name}", tx(p.name || ""));
            if (watchOnly) {
                return `${note}<div class="lrn-tchips"><button type="button" class="lrn-tchip"
                    data-act="c-scenario" data-key="${esc(p.key)}" data-mode="watch">${ic("play")}<span>${esc(tx(p.name || ""))}</span></button></div>`;
            }
            return `<div class="lrn-tpractice">${ic(p.mode === "watch" ? "play" : "flask")}<span>${esc(sentence)}</span></div>${note}`;
        }
        const chips = (p.chips || []).filter((c) => this._offers(c.key, c.mode || "try")).map((c) => `<button type="button" class="lrn-tchip"
                data-act="c-scenario" data-key="${esc(c.key)}" data-mode="${esc(c.mode || "try")}">${ic("flask")}<span>${esc(tx(c.name || ""))}</span></button>`);
        const sandbox = `<button type="button" class="lrn-tchip ghost" data-act="c-practice">${ic("flask")}<span>${esc(T("practiceOpen"))}</span></button>`;
        if (p.sandbox_first) {
            chips.unshift(sandbox);
        } else {
            chips.push(sandbox);
        }
        return `${note}<p class="lrn-tlead">${esc(T("practiceChipsLead"))}</p><div class="lrn-tchips">${chips.join("")}</div>`;
    }

    /** "Explain how instead" / "Do it for me" — one row of chips under a
     *  turn; a `primary` chip is the solid button. */
    _chipsHTML(chips, act) {
        if (!chips || !chips.length) {
            return "";
        }
        return `<div class="lrn-tchips">${chips.map((c, i) => `<button type="button"
            class="lrn-tchip${c.primary ? " pri" : ""}" data-act="${act}" data-i="${i}">${ic(c.route === "guide" ? "compass" : "sparkles")}<span>${esc(tx(c.label))}</span></button>`).join("")}</div>`;
    }

    /** THE CONTEXT CARD — not stored. Shown when the stream is empty, and as
     *  the newest item when the drawer opens on another screen than the last
     *  turn's; it collapses to a one-line divider once something is sent.
     *  No "Your next step", no "Practice mode" card, no "Take the tour"
     *  card (ONECHAT OC2): the tour is a "Show me how" row on Home and a
     *  sentence the router knows, practice is a chip and a menu item. */
    _contextHTML(opts) {
        void this.state.lang;
        if (!this.state.ready) {
            return `<div class="lrn-cground off">${ic("info")}<span>${esc(LOAD_FAILED[RT.lang] || LOAD_FAILED.en)}</span></div>`;
        }
        // LEARNREV P2 — with the Guide above, the opening card is only the
        // questions to ask: the screen's story is This screen, the
        // walkthroughs are Tasks, the tabs are the "You are here" chips.
        if (this.guideShown) {
            return `<div class="lrn-ctx">${this._notSureHTML(opts || {})}</div>`;
        }
        const parts = [this._groundedHTML()];
        if (this.state.gotoFailed) {
            parts.push(`<div class="lrn-cblock warn">${ic("info")}<span>${esc(T("hubTabGone"))}</span></div>`);
        }
        const hub = !!(this.screenInfo && this.screenInfo.hub);
        if (hub) {
            parts.push(this._oftenHTML());
        }
        parts.push(this._notSureHTML(opts || {}));
        if (!hub) {
            parts.push(this._scenarioHTML());
        }
        parts.push(this._tabsHTML(hub));
        return `<div class="lrn-ctx">${parts.join("")}</div>`;
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

    /** "Not sure what to ask?" — the opening offer, for the person who
     *  cannot phrase the question: up to four of this screen's own
     *  questions as chips (sent through the router, exactly as if typed),
     *  "What can you do?" where PayAI may act, "Let me practise this" where
     *  this screen has something to practise, then Explain this screen —
     *  which needs no vocabulary at all. */
    _notSureHTML(opts) {
        const s = this.screenInfo;
        // LEARNREV P2 — with the Guide showing, "What should I do next
        // here?" is the panel's own Right now when the screen has a live
        // list, so the chip goes; and two questions built from the Guide
        // join the screen's own ("What reads the pay role?", "Why does
        // Loan Installment need my answer?").
        const g = this.guideShown ? this.state.guide : null;
        const live = !!(g && hasProvider(g));
        const list = ((s ? s.suggest : (this.bundle?.global_suggest || [])) || [])
            .filter((i) => !(live && i.key === "whatnext")).slice(0, MAX_CHIPS);
        const chips = list.map((i) => `<button type="button" class="lrn-cq" data-act="c-suggest"
            data-key="${esc(i.key)}" data-label="${esc(tx(i.label))}">${ic("help-circle")}<span>${esc(tx(i.label))}</span></button>`);
        for (const q of g ? askChips(g) : []) {
            chips.push(`<button type="button" class="lrn-cq" data-act="c-say"
                data-text="${esc(q.text)}">${ic("help-circle")}<span>${esc(q.text)}</span></button>`);
        }
        if (opts && opts.canAct) {
            chips.push(`<button type="button" class="lrn-cq" data-act="c-say"
                data-text="${esc(T("whatCanYouDo"))}">${ic("sparkles")}<span>${esc(T("whatCanYouDo"))}</span></button>`);
        }
        if (this._screenTry().length) {
            chips.push(`<button type="button" class="lrn-cq" data-act="c-practise-here">${ic("flask")}<span>${esc(T("letMePractise"))}</span></button>`);
        }
        const explain = this.covered ? `<button type="button" class="lrn-btn sm lrn-cexplain" data-act="c-explain"
                title="${esc(T("explainHint"))}">${ic("scan-text")}${esc(T("explainScreen"))}</button>` : "";
        if (!chips.length && !explain) {
            return "";
        }
        return `<div class="lrn-cnotsure">
            <div class="lrn-clabel">${esc(T("notSure"))}</div>
            <div class="lrn-cchips">${chips.join("")}</div>
            ${explain}
        </div>`;
    }

    /** Open the Journey on the suggested station. Same door as `openLesson`,
     *  one key further — there is exactly one place in this module that knows
     *  how to open a station from outside the map. */
    openSuggested(key) {
        if (!key) {
            return;
        }
        openLearn(this.action, `station:${key}`);
        this.close();
    }

    /** Open the Journey on the sandbox. Same door as `openLesson`, one key
     *  further: the deep link is what the Journey reads, so there is exactly
     *  one place that knows how to build a practice view. */
    openPractice() {
        openLearn(this.action, "practice");
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
        if (s && s.hub) {
            const line = this.onHub ? this.tabLine(this.place.lens) : "";
            // The shell may be showing its padlock page: the tab on screen is
            // not one this reader can open. Say THAT, not "no lesson yet".
            const closed = this.onHub && this.place.ready
                && !this.place.lenses.some((l) => l.key === this.place.lens);
            return `<div class="lrn-cground">${ic("map-pin")}
                <span><b>${esc(this.screenLabel)}</b></span>
                ${line ? `<p class="lrn-cline">${esc(line)}</p>` : ""}
                <p class="lrn-note">${esc(tx(s.blurb))}</p>
                <p class="lrn-note lrn-hnolesson">${ic(closed ? "lock" : "book-open")}${esc(T(closed ? "hubTabClosed" : "hubNoLesson"))}</p></div>`;
        }
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
        // ONECHAT OC2 — "Practise", not "Try": one word for one promise
        // across the drawer. "Do it live" keeps its own label, and only here.
        const label = { watch: "scWatch", try: "scPractise", do: "scDo" };
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

    /** The hub's tabs as a compact list, the current one marked. Only the
     *  tabs the SHELL shows this reader (hub_place.js `lenses`), in its
     *  order: a tab they cannot open is never offered here either. */
    _tabsHTML(open) {
        const hs = this.hubScreen;
        const lenses = this.place.lenses || [];
        if (!hs || lenses.length < 2) {
            return "";
        }
        const rows = lenses.map((l) => {
            const here = l.key === this.place.lens;
            const line = this.tabLine(l.key);
            const lock = l.locked ? ic("lock") : "";
            const cls = here ? "lrn-htab here" : "lrn-htab";
            return `<li class="${cls}">
                <button type="button" class="lrn-htabbtn" data-act="c-goto" data-lens="${esc(l.key)}"
                    ${here ? `aria-current="page" disabled` : ""}
                    title="${esc(here ? T("youAreHere") : T("takeMeThere"))}">
                    <span class="lrn-htabic">${String(railIc(l.icon || "circle", 15))}</span>
                    <span class="lrn-htabtx"><b>${esc(this.tabLabel(l.key))}${lock}</b>${line
                        ? `<small>${esc(line)}</small>` : ""}</span>
                    ${here ? `<span class="lrn-chip a">${esc(T("youAreHere"))}</span>`
                        : `<span class="lrn-htabgo">${ic("arrow-right")}</span>`}
                </button></li>`;
        }).join("");
        const list = `<ul class="lrn-htabs">${rows}</ul>`;
        if (open) {
            return `<div class="lrn-hub">
                <div class="lrn-clabel">${esc(T("hubTabs"))}</div>${list}</div>`;
        }
        return `<details class="lrn-hub lrn-hubfold">
            <summary class="lrn-clabel">${esc(T("hubAllTabs"))}${SP}${esc(tx(hs.name))}${SP}(${lenses.length})</summary>${list}</details>`;
    }

    /** "People often come here to" — at most three, each a tab switch, and
     *  only for tabs this reader can see. */
    _oftenHTML() {
        const hs = this.hubScreen;
        if (!hs) {
            return "";
        }
        const seen = new Set((this.place.lenses || []).map((l) => l.key));
        const items = (hs.hub.often || []).filter((o) => seen.has(o.lens));
        if (!items.length) {
            return "";
        }
        return `<div class="lrn-hoften">
            <div class="lrn-clabel">${esc(T("hubOften"))}</div>
            ${items.map((o) => {
                const here = o.lens === this.place.lens;
                return `<button type="button" class="lrn-hoftenbtn" data-act="c-goto"
                    data-lens="${esc(o.lens)}" ${here ? "disabled" : ""}>
                    <span>${esc(tx(o.text))}</span>
                    <span class="lrn-hoftengo">${here ? esc(T("youAreHere"))
                        : `${esc(T("takeMeThere"))}${ic("arrow-right")}`}</span></button>`;
            }).join("")}
        </div>`;
    }

    _answerHTML(a, opts = {}) {
        if (!a) {
            return "";
        }
        if (!a.matched) {
            // ONECHAT OC2 — no "ask the Ask tab instead" any more: the router
            // already sent pay-figure questions to PayAI, so a miss here is a
            // real miss, with what CAN be answered on this screen under it.
            return `<div class="lrn-cmiss">
                <p><b>${esc(T("noAnswer"))}</b></p>
                <p class="lrn-note">${esc(T("noAnswerBody"))}</p>
            </div>${this._suggestFrom(a.suggest || [])}`;
        }
        const simplerOn = !!opts.simpler && !!a.simpler;
        const blocks = (a.blocks || []).map((b) => this._blockHTML(b)).join("");
        const tools = [];
        if ((a.show_me || []).length) {
            tools.push(`<button class="lrn-btn sm" data-act="c-show" data-anchor="${esc(a.show_me[0])}"
                >${ic("eye")}${esc(T("showMe"))}</button>`);
        }
        // LEARNOS Phase 4 — ANSWERS THAT TEACH. When a walkthrough covers the
        // same ground, the answer offers it: Watch it happen, or practise it
        // on the practice company. Not a new action — `c-scenario` is the
        // control the "Show me how" rows have used since Phase 1b, so there
        // is still exactly one path from this drawer into the scenario engine.
        if (this._offers(a.watch, "watch")) {
            tools.push(`<button class="lrn-btn sm" data-act="c-scenario"
                data-key="${esc(a.watch)}" data-mode="watch"
                title="${esc(T("scWatchHint"))}"
                >${ic("play")}${esc(T("scWatch"))}</button>`);
        }
        // ONECHAT OC2 — "Practise this": ONE chip, only when the scenario the
        // answer teaches really offers Try. It replaces the old "Try" button
        // (one label, not two); a click draws a practice turn first, then
        // opens the practice. "Do it live" is never offered under this word.
        if (this._offers(a["try"], "try")) {
            tools.push(`<button class="lrn-btn sm pri" data-act="c-scenario"
                data-key="${esc(a["try"])}" data-mode="try"
                title="${esc(T("scTryHint"))}"
                >${ic("flask")}${esc(T("practiseThis"))}</button>`);
        }
        if (a.simpler) {
            tools.push(`<button class="lrn-btn sm" data-act="c-simpler"
                >${ic("lightbulb")}${esc(simplerOn ? T("less") : T("simpler"))}</button>`);
        }
        // LEARNREV P2 — an explanation built from the Guide opens it.
        if (a.guide_door && this.guideOn) {
            tools.push(`<button class="lrn-btn sm pri" data-act="c-guide"
                >${ic("panel-right")}${esc(T("gOpenGuide"))}</button>`);
        }
        if (a.source_kind !== "capability") {
            tools.push(`<button class="lrn-btn sm ghost" data-act="c-lesson"
                >${ic("book-open")}${esc(T("openLesson"))}</button>`);
        }

        const simplerBlock = simplerOn
            ? `<div class="lrn-cblock p simpler">${gtx(a.simpler)}</div>` : "";

        // The learner is entitled to know which KIND of answer they are
        // reading. ONECHAT OC2: every answer now names its source in one row
        // at the top — "From the guide" for a curated intent; "About this
        // column" for a definition out of the column glossary; "Composed from
        // the guide" for one a model wrote from this module's own material
        // (the only answer no author has read, so the most important label);
        // "About this screen" for an explanation assembled from the screen's
        // own blurb and columns. PayAI's answers say "From your pay data".
        const SOURCES = {
            column: ["book-open", "aboutColumn"],
            composed: ["sparkles", "composedAnswer"],
            screen: ["scan-text", "aboutScreen"],
            capability: null,
        };
        const src = Object.prototype.hasOwnProperty.call(SOURCES, a.source_kind || "")
            ? SOURCES[a.source_kind] : ["compass", "fromGuide"];
        const badge = src
            ? `<div class="lrn-csrc">${ic(src[0])}<span>${esc(T(src[1]))}</span></div>`
            : "";
        return `<div class="lrn-canswer">
            ${badge}
            <h4>${esc(tx(a.label))}</h4>
            ${simplerBlock || blocks}
            <div class="lrn-ctools">${tools.join("")}</div>
        </div>`;
    }

    /** ONECHAT OC3 — an answer as the words read aloud after a spoken
     *  question (handover §6.5): the heading, then the blocks as plain text.
     *  Never the source line ("Grounded in …") and never the worked figures
     *  (owner decision Q2 — figures stay on screen). The chat's `speechText`
     *  then strips what markup is left, the vendor's name and any amount. */
    _answerSpeech(a) {
        if (!a) {
            return "";
        }
        if (!a.matched) {
            return [T("noAnswer"), T("noAnswerBody")].join(" ");
        }
        const plain = (html) => String(html || "").replace(/<[^>]*>/g, " ");
        const parts = [tx(a.label)];
        for (const b of a.blocks || []) {
            if (b.kind === "source" || b.kind === "calc" || b.kind === "calc_kpi") {
                continue;
            }
            if (b.kind === "steps") {
                (b.steps || []).forEach((st, i) => {
                    const line = String(tx(st.text) || "").trim();
                    parts.push(`${i + 1}. ${line}${/[.!?]$/.test(line) ? "" : "."}`);
                });
            } else {
                parts.push(plain(gtx(b.body)));
            }
        }
        return parts.map((p) => String(p || "").replace(/\s+/g, " ").trim())
            .filter(Boolean).join(" ");
    }

    _suggestFrom(list) {
        if (!list.length) {
            return "";
        }
        return `<div class="lrn-csuggest">
            <div class="lrn-clabel">${esc(T("canAnswer"))}</div>
            ${list.slice(0, MAX_CHIPS).map((i) => `<button class="lrn-cq" data-act="c-suggest" data-key="${esc(i.key)}"
                data-label="${esc(tx(i.label))}">${ic("help-circle")}<span>${esc(tx(i.label))}</span></button>`).join("")}
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
        // A click anywhere outside the More menu closes it.
        if (this.menu.open && !ev.target.closest(".lrn-menu, [data-act='c-more']")) {
            this.menu.close();
        }
        // LEARNREV P2 — a field card opened as a Fields row: Watch and the
        // thumbs (the same footer the floating card has).
        const fc = ev.target.closest(".lrn-gfcard [data-fc]");
        if (fc) {
            ev.preventDefault();
            this._fieldAct(fc.dataset.fc, fc.dataset.key || this.state.gField);
            return;
        }
        const el = ev.target.closest("[data-act]");
        if (!el) {
            return;
        }
        const act = el.dataset.act;
        if (!COACH_ACTIONS.has(act)) {
            return;
        }
        ev.preventDefault();
        const holder = el.closest("[data-turn]");
        const turnId = holder ? holder.dataset.turn : "";
        if (act === "c-close") {
            this.close();
        } else if (act === "c-suggest") {
            this.askIntent(el.dataset.key, el.dataset.label);
        } else if (act === "c-say") {
            this._say(el.dataset.text, "chip");
        } else if (act === "c-show") {
            this.showMe(el.dataset.anchor);
        } else if (act === "c-simpler") {
            this._toggleSimpler(turnId);
        } else if (act === "c-lesson") {
            const turn = this._findTurn(turnId);
            this.openLesson(turn && turn.answer);
        } else if (act === "c-lang") {
            this.toggleLang();
        } else if (act === "c-consent-yes") {
            this.decideConsent(true);
        } else if (act === "c-consent-no") {
            this.decideConsent(false);
        } else if (act === "c-scenario") {
            // Practise (Try) draws its practice turn first; Watch and Do it
            // live start at once, as they always have.
            if (el.dataset.mode === "try") {
                this._practiseFrom(el.dataset.key, "try");
            } else {
                this.startScenario(el.dataset.key, el.dataset.mode, 0);
            }
        } else if (act === "c-explain") {
            this.openHelper({ explain: true });
        } else if (act === "c-practice") {
            this.openPractice();
        } else if (act === "c-practise-here") {
            this._practiseHere();
        } else if (act === "c-choice") {
            this._pickChoice(turnId, Number(el.dataset.i));
        } else if (act === "c-extra") {
            this._extraChip(turnId, Number(el.dataset.i));
        } else if (act === "c-again") {
            this._expandMarker(turnId);
        } else if (act === "c-more") {
            this._openMenu();
        } else if (act === "c-readaloud") {
            if (this._api) {
                this._api.toggleReadAloud();
            }
            this.menu.tick += 1;
        } else if (act === "c-clear") {
            this.menu.confirm = true;
        } else if (act === "c-clear-yes") {
            this._clearConversation();
            this.menu.close();
        } else if (act === "c-clear-no") {
            this.menu.confirm = false;
        } else if (act === "c-usevoice") {
            if (this._api) {
                this._api.reopenVoiceConsent();
            }
            this.menu.close();
        } else if (act === "c-goto") {
            this.goTab(el.dataset.lens);
        } else if (["c-mgo", "c-mok", "c-fvexplain", "c-fvwatch", "c-mlater",
                    "c-mewatch", "c-meskip", "c-fvguide"].includes(act)) {
            this._momentAct(act);
        } else if (act === "c-gsec") {
            this._toggleSection(el.dataset.sec);
        } else if (act === "c-gpath") {
            this._openPath(Number(el.dataset.i));
        } else if (act === "c-gscreen") {
            this._openScreen(el.dataset.screen);
        } else if (act === "c-gact") {
            this._guideAct(Number(el.dataset.i));
        } else if (act === "c-gfield") {
            this.state.gField = this.state.gField === el.dataset.key ? "" : el.dataset.key;
        } else if (act === "c-gretry") {
            this._loadGuide({ refresh: true });
        } else if (act === "c-gmap") {
            openLearn(this.action, "");
            this.close();
        } else if (act === "c-gdock") {
            this._toggleDock();
        } else if (act === "c-guide") {
            this._openGuideHere(false);
        } else if (act === "c-gshow") {
            this._showGuide();
        }
    }

    /** The header's More menu. BUILT HERE, as a string, so every control in
     *  it is a declared `data-act` of this module (test_coach test_08) —
     *  including the one door into practice mode the drawer still has. */
    get menuHTML() {
        void this.state.lang;
        void this.menu.tick;
        if (!this.menu.open) {
            return markup("");
        }
        if (this.menu.confirm) {
            return markup(`<div class="lrn-menu" role="menu" aria-label="${esc(T("clearConv"))}">
                <p class="lrn-menuconfirm">${esc(T("clearConvConfirm"))}</p>
                <div class="lrn-menurow">
                    <button type="button" role="menuitem" class="lrn-btn sm pri lrn-bad" data-act="c-clear-yes">${ic("trash-2")}${esc(T("clearConvYes"))}</button>
                    <button type="button" role="menuitem" class="lrn-btn sm ghost" data-act="c-clear-no">${esc(T("clearConvNo"))}</button>
                </div>
            </div>`);
        }
        const api = this._api;
        const items = [];
        if (api && api.ttsSupported()) {
            const on = !!api.readAloudOn();
            items.push(`<button type="button" role="menuitemcheckbox" aria-checked="${on ? "true" : "false"}"
                class="lrn-menuitem" data-act="c-readaloud">${ic(on ? "volume-2" : "volume-x")}<span>${esc(T("readAloud"))}</span><span class="lrn-switch${on ? " on" : ""}" aria-hidden="true"></span></button>`);
        }
        if (this._hasConversation()) {
            items.push(`<button type="button" role="menuitem" class="lrn-menuitem" data-act="c-clear">${ic("trash-2")}<span>${esc(T("clearConv"))}</span></button>`);
        }
        items.push(`<button type="button" role="menuitem" class="lrn-menuitem" data-act="c-practice">${ic("flask")}<span>${esc(T("practiceOpen"))}</span></button>`);
        if (api && api.voiceDeclined()) {
            items.push(`<button type="button" role="menuitem" class="lrn-menuitem" data-act="c-usevoice">${ic("mic")}<span>${esc(T("useVoice"))}</span></button>`);
        }
        return markup(`<div class="lrn-menu" role="menu" aria-label="${esc(T("more"))}">${items.join("")}</div>`);
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
        // LEARNREV P2 — the Guide is read in the helper's language.
        if (this.guideOn) {
            if (this._info) {
                this._info.stop();
            }
            this._loadGuide();
        }
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
            // `user.lang` (a browser locale, "vi-VN"): the old read of the
            // page's session info found nothing on this version — it is
            // deleted on load — so a Vietnamese user always started in English.
            const sessionLang = String(user.lang || "").toLowerCase();
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
    get askPlaceholder() {
        void this.state.lang;
        return T("askPlaceholder");
    }

    get sendLabel() {
        void this.state.lang;
        return T("send");
    }

    get closeLabel() {
        void this.state.lang;
        return T("close");
    }

    get moreLabel() {
        void this.state.lang;
        return T("more");
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
        void this.state.lang;
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
