/** @odoo-module **/
/* =============================================================================
   The Guided Journey — Payobook Learn, Phase A.

   OWL owns the shell and the state; the engine builds the inner HTML. That
   split is deliberate: the spotlight, trace and morph work by measuring and
   decorating live DOM, which is imperative work that reactive re-rendering
   fights rather than helps. So OWL renders one host node per view, and the
   post-render hook runs the visual effects.

   Binding rules from the brief, enforced here rather than left to the CSS:
     * the spotlight never covers the control it explains (see spotlight.js)
     * completion needs a right answer, never a click on Next
     * a wrong answer is a recovery, never a rejection
     * both languages switch live, without a reload or a lost place
   ========================================================================== */
import { Component, markup, onMounted, onPatched, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

import { RT, T, tx, esc, ic, reduced, SP} from "../engine/runtime";
/* The glossary pass (LEARNOS Phase 2). `gtx` is `tx` plus the hovercard
   wrapper, and it is used at exactly the sites that insert an authored body
   RAW — a lesson step, a mission step detail, a scenario card. Everywhere
   else on this screen goes through esc() and must keep doing so. */
import { gtx, glossaryOpen, setGlossary, installGlossary, closeGlossary }
    from "../engine/glossary";
import { loadContent, composeStations } from "../content/content_loader";
import { Spot, Trace, setOverlayRoot } from "../engine/spotlight";

/* Where a mission opens when its first step does not say. One entry per
   Journey line, so a mission never opens on a screen from another section.
   Phase A draws one line; later phases add rows here, not a second map. */
const MISSION_HOME = {
    payrun: "runpayroll",
    setup: "statutory",
};

/* The READING order of the lines on the map, and the icon each heading gets.
 *
 * LEARNOS PHASE 6: THE ORDER IS AUTHORED IN `docs/tutorial_poc/author/data.js`
 * AND SHIPS IN THE CONTENT PLANE, because the SERVER needs it too —
 * `learn.runtime.next_best()` answers "the next required station in reading
 * order". The constant below is the FALLBACK for a bundle that predates the
 * key; `get lineOrder()` prefers what the content shipped, and
 * `test_nextbest::test_15` fails if the two ever disagree. Do not edit this
 * list on its own: edit the authoring source and regenerate.
 *
 * Not the model's selection order and not the station sequence: the generator
 * numbers stations with one counter across every line in declaration order, so
 * a new section is APPENDED there to avoid renumbering the ones before it —
 * which is right for storage and wrong for a page. A learner meets Overview
 * first and Setup last, whatever order the content happened to be written in.
 *
 * A line missing from this list is still drawn, after the ones that are here.
 * That is deliberate: a new section must never be able to disappear from the
 * map because somebody forgot a second file. */
const LINE_ORDER = ["overview", "payrun", "people", "insights", "compliance", "setup"];
const LINE_ICON = {
    overview: "grid",
    payrun: "zap",
    people: "users",
    insights: "trending-up",
    compliance: "shield-check",
    setup: "plug",
};
import { SCREENS, practiceShellHTML, shellHTML } from "../engine/screens";
import { INPUT_ANCHORS } from "../engine/fixture";
import { looseMatch } from "../engine/input_match";
import { playableSteps } from "../scenario/scenario_service";
import { LiveState } from "../live/live_state";
import { morphHTML, calcHTML, pipeHTML, runPipeline } from "../engine/visuals";

const LOCAL_PREFS = "pbLearnPrefs";

export class LearnJourney extends Component {
    static template = "pb_learn.Journey";
    /* A client action is handed `action`, `actionId`, `className` and
       `updateActionState` by the action manager. Phase A declared no props at
       all, which was fine while nothing read them; the deep link needs
       `props.action.context`, so the component now accepts what it is given.
       "*" rather than a list, because the set belongs to the action manager. */
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        // Scenarios: the Journey hosts TRY (over the replica, where the
        // missions already run) and hands WATCH and DO to the service, whose
        // overlay is mounted in the web client shell and survives the
        // navigation those two modes do.
        this.sc = useService("learn.scenario");
        this.overlayRef = useRef("overlay");

        this.state = useState({
            ready: false,
            view: "map",            // map | outline | lesson
            stationKey: null,
            step: 0,
            quiz: false,
            answered: null,         // index of the option chosen
            morphSide: "before",
            search: "",
            // Phase 3 — mission runner.
            // Deep links. `lesson` opens a lesson outright (PayAI's "Show me");
            // `suggest` only PULSES a card on the map (the demo first-login
            // greeting). Two keys because they are two different promises: one
            // takes you somewhere, the other points.
            suggest: "",
            missionKey: null,
            mStep: 0,
            mChoice: null,       // key of the option chosen
            mRecovered: false,   // needed a recovery anywhere in this run
            mAcked: false,       // consequence card acknowledged on this step
            mHint: false,
            mDone: false,
            mGain: 0,
            // Phase 1b — a scenario taken in TRY mode, over the replica.
            // `sNudge` is the gentle correction for a click on the wrong
            // control: a nudge, never a mark against the learner, and it
            // clears the moment they get it right.
            scenarioKey: null,
            sStep: 0,
            sNudge: false,
            sDone: false,
            // Phase 5 — an input step's mismatch. Separate from `sNudge`,
            // which is a wrong CONTROL: this one is the right control with the
            // wrong value in it, and it is the only thing a wrong value can
            // ever produce. It never advances anything.
            sMiss: false,
            // Phase 5 — practice mode, the free-roam sandbox. `pScreen` is the
            // replica the learner is standing on and survives a trip back to
            // the map, so re-opening the sandbox resumes where they left it.
            pScreen: "dashboard",
            lang: "en",
            motion: "auto",
            error: "",
        });

        this.bundle = null;
        this.progress = {};
        this.visible = new Set();
        // The one-shot that keeps a blur and the click that caused it
        // from being two advances. See `_scenarioClick`.
        this._blurAdvanced = false;
        this._onKey = this._onKey.bind(this);

        onWillStart(async () => {
            this._restorePrefs();
            await this._loadBundle();
            this._applyDeepLink();
        });
        onMounted(() => {
            setOverlayRoot(this.overlayRef.el);
            // CAPTURE PHASE, and it is not a style choice. "document, not
            // window" was necessary and NOT sufficient: Odoo's hotkey service
            // stops propagation at document-BUBBLE, so a bubble listener here
            // is silently dead in real Chrome while synthetic dispatch in a
            // test still works — measured on the Phase 2+3 deploy, on the
            // welcome card's Escape, and the reason first_login.js has bound
            // capture ever since. The removal has to match the phase or the
            // listener is never removed at all.
            document.addEventListener("keydown", this._onKey, true);
            document.body.classList.add("lrn-open");
            this._log("journey_open");
        });
        onPatched(() => this._afterPaint());
        onWillUnmount(() => {
            // The card lives on document.body, so leaving the Journey with
            // one open would strand it over the next screen.
            closeGlossary();
            Spot.hide();
            document.removeEventListener("keydown", this._onKey, true);
            document.body.classList.remove("lrn-open");
        });
    }

    // ---------------------------------------------------------------- loading
    _restorePrefs() {
        // Only the two preferences live in the browser. Progress is a server
        // record: a learner who moves to the ward laptop keeps their place, and
        // Product can measure completion at all (analysis §6).
        try {
            const p = JSON.parse(window.localStorage.getItem(LOCAL_PREFS) || "{}");
            const sessionLang = window.odoo?.session_info?.user_context?.lang || "";
            this.state.lang = p.lang || (sessionLang.startsWith("vi") ? "vi" : "en");
            this.state.motion = p.motion || "auto";
        } catch {
            this.state.lang = "en";
            this.state.motion = "auto";
        }
        RT.lang = this.state.lang;
        RT.motion = this.state.motion;
    }

    _savePrefs() {
        try {
            window.localStorage.setItem(LOCAL_PREFS, JSON.stringify({
                lang: this.state.lang, motion: this.state.motion,
            }));
        } catch {
            // A locked-down browser profile must not break the lesson.
        }
    }

    async _loadBundle() {
        // TWO sources since Phase 1a, and the split is the whole point: the
        // CONTENT is a static asset every tenant has identical bytes of, and
        // the one RPC carries only what is irreducibly about this session —
        // which stations this reader can reach, their slots, their progress.
        // The bundle assembled here is the shape the views below have read
        // since Phase A; nothing downstream of this method changed.
        let content, runtime;
        try {
            [content, runtime] = await Promise.all([
                loadContent(),
                this.orm.call("learn.runtime", "bootstrap", []),
            ]);
        } catch (e) {
            this.state.error = e?.message?.data?.message || String(e);
            return;
        }
        this.bundle = {
            // LEARNOS Phase 6. Three answers the server already worked out,
            // riding along with the one call this component already makes.
            // All three are EMPTY when their tenant flag is off, and every
            // surface below draws nothing on empty rather than drawing an
            // explanation of why a feature is missing.
            nextBest: runtime.next_best || {},
            streak: runtime.streak || {},
            skillTree: !!runtime.skill_tree,
            lineOrder: runtime.line_order || [],
            stations: composeStations(content, runtime),
            missions: content.missions || [],
            scenarios: content.scenarios || [],
            glossary: content.glossary || [],
            chrome: content.chrome || {},
            version: content.version || "",
            tokens: runtime.tokens || {},
            progress: runtime.progress || {},
            confidence: runtime.confidence || {},
            user: runtime.user || {},
        };
        RT.tokens = this.bundle.tokens || {};
        RT.chrome = this.bundle.chrome || {};
        // The hovercard's match table and its one delegated listener. Built
        // from the glossary the content plane already carries, so no surface
        // owns a second copy of the terms.
        setGlossary(this.bundle.glossary);
        installGlossary();
        this.progress = this.bundle.progress || {};
        this.visible = new Set(
            this.bundle.stations.filter((s) => s.visible).map((s) => s.key));
        // The rail path for a screen that is reachable but has no menu line of
        // its own — "Pay Run", "People". Empty for everything the reader can
        // already see on the rail, so a card only says something when there is
        // something to say.
        this.reachOf = new Map(
            this.bundle.stations.filter((s) => s.reach).map((s) => [s.key, s.reach]));
        // The server knows the user's own language; honour it the first time
        // and let the toggle win afterwards.
        if (!window.localStorage.getItem(LOCAL_PREFS)) {
            this.state.lang = this.bundle.user?.lang || "en";
            RT.lang = this.state.lang;
        }
        this.state.ready = true;
    }

    // ----------------------------------------------------------------- lookups
    get stations() {
        return this.bundle ? this.bundle.stations : [];
    }

    station(key) {
        return this.stations.find((s) => s.key === key) || null;
    }

    get current() {
        return this.station(this.state.stationKey);
    }

    get lesson() {
        const st = this.current;
        return st && st.lessons.length ? st.lessons[0] : null;
    }

    get steps() {
        const l = this.lesson;
        return l ? l.steps : [];
    }

    get missions() {
        return this.bundle ? (this.bundle.missions || []) : [];
    }

    get mission() {
        return this.missions.find((m) => m.key === this.state.missionKey) || null;
    }

    get mSteps() {
        return this.mission ? this.mission.steps : [];
    }

    get mCurrent() {
        return this.mSteps[this.state.mStep] || null;
    }

    get scenarios() {
        return this.bundle ? (this.bundle.scenarios || []) : [];
    }

    get scenario() {
        return this.scenarios.find((s) => s.key === this.state.scenarioKey) || null;
    }

    /** The steps this scenario plays in TRY. Filtered through the same
     *  function the overlay and the Coach use, so the three surfaces agree
     *  about what step 4 of 7 is (Phase 5). */
    get sSteps() {
        return playableSteps(this.scenario, "try");
    }

    get sCurrent() {
        return this.sSteps[this.state.sStep] || null;
    }

    /** Which replica a Try step stands on.
     *
     *  Same rule as a mission's: a step with no `screen` of its own has not
     *  moved the learner, so it is standing on the last screen the scenario
     *  navigated to — never a default, which would ask a question about a
     *  screen the learner is not looking at. */
    _scenarioScreen(step) {
        if (step && step.screen) {
            return step.screen;
        }
        for (let i = this.state.sStep - 1; i >= 0; i--) {
            const prev = this.sSteps[i];
            if (prev && prev.screen) {
                return prev.screen;
            }
        }
        const sc = this.scenario;
        return (sc && sc.entry && sc.entry.screen) || "runpayroll";
    }

    stateOf(key) {
        return (this.progress[key] || {}).state || "not_started";
    }

    get doneCount() {
        return this.stations.filter((s) => this.stateOf(s.key) === "done").length;
    }

    get badgeEarned() {
        return this.stations
            .filter((s) => s.star)
            .every((s) => this.stateOf(s.key) === "done");
    }

    /* ------------------------------------------------- LEARNOS Phase 6 */

    /** The reading order, from the content plane, with this file's constant
     *  as the fallback for a stale bundle. One AUTHORED source
     *  (docs/tutorial_poc/author/data.js) feeds both this and the server's
     *  `next_best`, so the map and the suggestion cannot disagree about which
     *  section comes next. */
    get lineOrder() {
        const fromContent = this.bundle && this.bundle.lineOrder;
        return fromContent && fromContent.length ? fromContent : LINE_ORDER;
    }

    get nextBest() {
        return (this.bundle && this.bundle.nextBest) || {};
    }

    get skillTree() {
        return !!(this.bundle && this.bundle.skillTree);
    }

    get streak() {
        return (this.bundle && this.bundle.streak) || {};
    }

    /** done / total for one line. Derived on every render from the same
     *  progress the cards read — there is no per-line counter anywhere, and a
     *  stored one would be a second truth to keep in step. */
    lineProgress(list) {
        const total = list.length;
        const done = list.filter((s) => this.stateOf(s.key) === "done").length;
        return { done, total, pct: total ? Math.round(done / total * 100) : 0 };
    }

    /** bronze | silver | gold | "" — DERIVED, NEVER STORED.
     *
     *  Read off the two fields the lesson already writes: `first_try_correct`
     *  and `attempts`. Gold is the understanding check answered correctly on
     *  the first answer; silver is getting there on the second; bronze is
     *  finishing, which is the point and is never presented as a failure.
     *
     *  ONLY FOR LESSONS. An outline station has no understanding check, so it
     *  has no attempts either — grading one bronze would be marking somebody
     *  down for reading the kind of page that has nothing to answer. */
    tierOf(station) {
        if (!this.skillTree || station.kind !== "lesson") {
            return "";
        }
        if (this.stateOf(station.key) !== "done") {
            return "";
        }
        const p = this.progress[station.key] || {};
        if (p.first_try_correct) {
            return "gold";
        }
        return (p.attempts || 0) <= 2 ? "silver" : "bronze";
    }

    // ------------------------------------------------------------- persistence
    async _saveProgress(key, vals) {
        this.progress[key] = Object.assign({}, this.progress[key], vals);
        try {
            await this.orm.call("learn.progress", "record", [key, vals]);
        } catch {
            // Losing a progress write must never interrupt a lesson. The local
            // copy still drives the UI; the next write re-syncs it.
        }
    }

    async _log(kind, detail) {
        try {
            await this.orm.call("learn.event", "log", [kind], {
                station_key: this.state.stationKey || null,
                screen: this.steps[this.state.step]?.screen || null,
                detail: detail === undefined ? null : detail,
                lang: this.state.lang,
            });
        } catch {
            // Measurement must never be able to break the thing it measures.
        }
    }

    // -------------------------------------------------------------- rendering
    get body() {
        if (this.state.error) {
            return markup(`<div class="lrn-panel lrn-blocked"><h3>${ic("alert-triangle")}
                ${esc(T("noAnswer"))}</h3><p class="lrn-note">${esc(this.state.error)}</p></div>`);
        }
        if (!this.state.ready) {
            return markup(`<div class="lrn-skeleton" aria-busy="true"></div>`);
        }
        if (this.state.view === "lesson") {
            return markup(this._lessonBody());
        }
        if (this.state.view === "mission") {
            return markup(this._missionBody());
        }
        if (this.state.view === "scenario") {
            return markup(this._scenarioBody());
        }
        if (this.state.view === "practice") {
            return markup(this._practiceBody());
        }
        if (this.state.view === "missions") {
            return markup(this._missionListBody());
        }
        if (this.state.view === "outline") {
            return markup(this._outlineBody());
        }
        return markup(this._mapBody());
    }

    /* -------------------------------------------------------------- map view */
    _mapBody() {
        const q = this.state.search.trim().toLowerCase();
        const lines = {};
        for (const s of this.stations) {
            (lines[s.line] = lines[s.line] || []).push(s);
        }
        const match = (s) =>
            !q || tx(s.name).toLowerCase().includes(q) || tx(s.summary).toLowerCase().includes(q);

        // Scenarios ride on the same lines as the stations, so a learner meets
        // "run a pay run, three ways" in the Pay Run section rather than in a
        // second list somewhere else. A line whose stations are all filtered
        // out by the search still shows its scenarios if they match.
        const screnLines = {};
        for (const sc of this.scenarios) {
            (screnLines[sc.line] = screnLines[sc.line] || []).push(sc);
        }
        const screnMatch = (sc) =>
            !q || tx(sc.name).toLowerCase().includes(q)
            || tx(sc.tagline).toLowerCase().includes(q);

        const order = this.lineOrder;
        const keys = Object.keys(lines).concat(
            Object.keys(screnLines).filter((k) => !lines[k]));
        const ordered = order.filter((k) => keys.includes(k))
            .concat(keys.filter((k) => !order.includes(k)));
        const lineHTML = ordered.map((lineKey) => {
            const items = (lines[lineKey] || []).filter(match);
            const screns = (screnLines[lineKey] || []).filter(screnMatch);
            if (!items.length && !screns.length) {
                return "";
            }
            return `<section class="lrn-line">
                <h3 class="lrn-linehead">${ic(LINE_ICON[lineKey] || "map-pin")}
                    ${esc(T("lines." + lineKey))}
                    ${this._lineRingHTML(lines[lineKey] || [])}</h3>
                <div class="lrn-cards">${items.map((s) => this._cardHTML(s)).join("")}</div>
                ${this._scenarioRowHTML(screns)}
            </section>`;
        }).join("");

        const total = this.stations.length;
        const pctDone = total ? Math.round(this.doneCount / total * 100) : 0;

        return `
        <header class="lrn-hero">
            <div>
                <h1>${esc(T("hubTitle"))}</h1>
                <p class="lrn-lead">${esc(T("hubLead"))}</p>
            </div>
            <div class="lrn-progress" role="group" aria-label="${esc(T("overall"))}">
                <div class="lrn-ring" style="--p:${pctDone}"><span>${pctDone}%</span></div>
                <div class="lrn-pmeta">
                    <b>${esc(T("overall"))}</b>
                    <span>${this.doneCount}${SP}/ ${total}</span>
                    ${this.badgeEarned
                        ? `<span class="lrn-chip ok">${ic("award")}${esc(T("badgeGot"))}</span>`
                        : `<span class="lrn-chip">${ic("award")}${esc(T("badge"))}</span>`}
                    ${this._streakHTML()}
                </div>
            </div>
        </header>
        ${this._continueHTML()}
        <div class="lrn-toolbar">
            <button class="lrn-btn pri" data-act="to-missions"
                >${ic("flask")}${esc(T("missions"))}</button>
            <label class="lrn-search">${ic("search")}
                <input type="search" data-act="search" value="${esc(this.state.search)}"
                       placeholder="${esc(T("search"))}" aria-label="${esc(T("search"))}"/>
            </label>
        </div>
        ${this._practiceCardHTML()}
        ${lineHTML || `<p class="lrn-note">${esc(T("noAnswer"))}</p>`}`;
    }

    /* ------------------------------------------------- LEARNOS Phase 6 views

       CONTINUE. One suggestion, chosen by the server from this learner's own
       rows, with the reason it was chosen printed beside it. The reason is
       not decoration: a strip that says "do this next" and nothing else is a
       nag, and one that says why is an explanation somebody can disagree with.

       Drawn only when the server sent one — the flag being off, or every
       lesson being finished with the capstone out of reach, both produce an
       empty payload and no strip. */
    _continueHTML() {
        const nb = this.nextBest;
        if (!nb.reason_key) {
            return "";                       // the flag is off: draw nothing
        }
        const reason = tx(nb.reason || {});
        // FINISHED IS AN ANSWER AND IT GETS DRAWN. `next_best` returns
        // `nbAllDone` with no key, and the first draft rendered nothing for
        // it — so the one learner who had completed everything was the one
        // the feature went silent on. No button, because there is nowhere to
        // send them; the sandbox card below is the standing offer.
        if (!nb.key || nb.kind === "none") {
            return `
            <div class="lrn-continue done">
                <span class="lrn-cardico">${ic("check-circle", "ok")}</span>
                <span class="lrn-cardmain">
                    <span class="lrn-clabel">${esc(T("nbTitle"))}</span>
                    <span class="lrn-carddesc">${esc(reason)}</span>
                </span>
            </div>`;
        }
        const isMission = nb.kind === "mission";
        const target = isMission
            ? (this.missions.find((m) => m.key === nb.key) || null)
            : this.station(nb.key);
        if (!target) {
            // A stale bundle naming content this build does not ship. Say
            // nothing rather than drawing a button that opens nothing.
            return "";
        }
        return `
        <div class="lrn-continue">
            <span class="lrn-cardico">${ic(isMission ? "flask" : (target.icon || "map-pin"))}</span>
            <span class="lrn-cardmain">
                <span class="lrn-clabel">${esc(T("nbTitle"))}</span>
                <span class="lrn-cardtitle">${esc(tx(target.name))}</span>
                <span class="lrn-carddesc">${esc(reason)}</span>
            </span>
            <button class="lrn-btn pri" data-act="nb-go"
                    data-key="${esc(nb.key)}" data-kind="${esc(nb.kind)}"
                >${ic("play")}${esc(T(isMission ? "nbGoMission" : "nbGo"))}</button>
        </div>`;
    }

    /** Days in a row, and an honest tooltip. No notification, no reminder, no
     *  "you are about to lose it" — the number is there when the learner
     *  looks, and gone quietly when they miss a day. */
    _streakHTML() {
        const streak = this.streak;
        if (!this.skillTree || !streak.days) {
            return "";
        }
        return `<span class="lrn-chip streak" title="${esc(T("streakHint"))}"
            >${ic("flame")}${esc(streak.display || String(streak.days))}${SP}${
            esc(T("streakTitle"))}</span>`;
    }

    /** A ring per section heading. Same conic-gradient idiom as the hero
     *  ring above it and as pb_dashboard's — one dial shape in the product,
     *  flat two-stop, no gradient. */
    _lineRingHTML(list) {
        if (!this.skillTree || !list.length) {
            return "";
        }
        const p = this.lineProgress(list);
        return `<span class="lrn-lineprog"
                title="${esc(p.done + " / " + p.total + " " + T("lineProgress"))}">
            <span class="lrn-ring sm" style="--p:${p.pct}"></span>
            <span class="lrn-linecount">${p.done}${SP}/ ${p.total}</span>
        </span>`;
    }

    /* --------------------------------------------------- practice mode card
       ABOVE the lines and never inside one. The sandbox is not a station and
       does not belong to a section: it is every screen at once, with nothing
       to complete and nothing to get right. Drawing it as one more card in the
       Overview row would promise a lesson it does not have. */
    _practiceCardHTML() {
        return `
        <div class="lrn-practicecard">
            <span class="lrn-cardico">${ic("flask")}</span>
            <span class="lrn-cardmain">
                <span class="lrn-cardtitle">${esc(T("practiceMode"))}</span>
                <span class="lrn-carddesc">${esc(T("practiceModeLead"))}</span>
            </span>
            <button class="lrn-btn pri" data-act="to-practice"
                >${ic("compass")}${esc(T("practiceOpen"))}</button>
        </div>`;
    }

    /* ------------------------------------------------- practice mode: the view
       The replica with its menu switched on. There is no walkthrough here and
       no step counter: `data-nav` swaps the screen and everything else on the
       replica stays inert, which is what it already is outside a scenario.

       The watermark is NOT rendered here. It is rendered by
       `practiceShellHTML`, unconditionally, so that no state this component
       holds can produce a sandbox without one. */
    _practiceBody() {
        const shell = practiceShellHTML(this.state.pScreen, this.visible);
        return `${shell}
        <div class="lrn-playbar" role="group">
            <span class="lrn-stepno">${esc(T("practiceHint"))}</span>
            <button class="lrn-btn sm ghost" data-act="p-exit"
                >${ic("x")}${esc(T("exit"))}</button>
        </div>`;
    }

    _cardHTML(s) {
        const st = this.stateOf(s.key);
        const badge = s.kind === "lesson"
            ? `<span class="lrn-chip b">${ic("play")}${esc(T("fullLesson"))}</span>`
            : `<span class="lrn-chip">${ic("list-checks")}${esc(T("outline"))}</span>`;
        const need = s.required
            ? `<span class="lrn-chip a">${esc(T("required"))}</span>`
            : `<span class="lrn-chip">${esc(T("optional"))}</span>`;
        // Three states, not two. A screen that moved into a hub is REACHABLE —
        // saying "not in your menu" about it was the wrong word in the
        // direction that makes a reader stop looking, so it gets a plain chip
        // naming the door instead of a padlock.
        const gate = (s.missing || !s.visible)
            ? `<span class="lrn-chip warn">${ic("lock")}${esc(T("notVisible"))}</span>`
            : (s.reach
                ? `<span class="lrn-chip">${ic("compass")}${esc(T("reachVia"))}${SP}${esc(s.reach)}</span>`
                : "");
        // "Start here" is a PULSE, never an auto-play. The demo greeting opens
        // the map and points; the learner presses the card. A spotlight that
        // starts by itself is the thing the retired first-run tour did, and the
        // reason people learned to dismiss it before reading it.
        const start = this.state.suggest && this.state.suggest !== ""
            && (s.lessons || []).some((l) => l.key === this.state.suggest);
        const startChip = start
            ? `<span class="lrn-chip a">${ic("sparkles")}${esc(T("startHere"))}</span>`
            : "";
        // The tier is DERIVED from the progress row the lesson already wrote
        // and is drawn as one quiet chip beside the tick — the celebration
        // stays the check that is already there, once, and nothing new
        // animates. See `tierOf`.
        const tier = this.tierOf(s);
        const tierChip = tier
            ? `<span class="lrn-chip tier ${tier}" title="${esc(T("tierHint"))}"
                >${ic("award")}${esc(T(
                    tier === "gold" ? "tierGold"
                        : tier === "silver" ? "tierSilver" : "tierBronze"))}</span>`
            : "";
        return `
        <button class="lrn-card ${s.star ? "star" : ""}${SP}${st === "done" ? "done" : ""}${
                SP}${tier ? "t-" + tier : ""}${SP}${start ? "pulse" : ""}"
                data-station="${esc(s.key)}">
            <span class="lrn-cardico">${ic(s.icon)}</span>
            <span class="lrn-cardmain">
                <span class="lrn-cardtitle">${esc(tx(s.name))}
                    ${st === "done" ? ic("check-circle", "ok") : ""}</span>
                <span class="lrn-carddesc">${esc(tx(s.summary))}</span>
                <span class="lrn-cardmeta">${startChip}${tierChip}${badge}${need}${gate}
                    <span class="lrn-chip">${ic("clock")}${esc(T("est"))}${SP}${s.duration_min}${SP}${esc(T("min"))}</span>
                </span>
            </span>
        </button>`;
    }

    /* ------------------------------------------------------- scenario cards
       One row per line, under the stations. A scenario is not a station and
       does not look like one: the MODE is the affordance, so each way of taking
       it is its own button with its own promise about who presses. */
    _scenarioRowHTML(list) {
        if (!list.length) {
            return "";
        }
        const label = { watch: "scWatch", try: "scTry", do: "scDo" };
        const hint = { watch: "scWatchHint", try: "scTryHint", do: "scDoHint" };
        const icon = { watch: "play", try: "flask", do: "target" };
        const cards = list.map((sc) => {
            const done = (this.progress[`scenario:${sc.key}`] || {}).state === "done";
            const modes = (sc.modes || []).map((m) => `
                <button class="lrn-btn sm ${m === "watch" ? "pri" : ""}"
                        data-scenario="${esc(sc.key)}" data-mode="${esc(m)}"
                        title="${esc(T(hint[m] || "scWatchHint"))}"
                    >${ic(icon[m] || "play")}${esc(T(label[m] || "scWatch"))}</button>`).join("");
            return `
            <div class="lrn-scren ${done ? "done" : ""}">
                <span class="lrn-screnico">${ic(sc.icon)}</span>
                <span class="lrn-screnmain">
                    <span class="lrn-screntitle">${esc(tx(sc.name))}
                        ${done ? ic("check-circle", "ok") : ""}</span>
                    <p class="lrn-screndesc">${esc(tx(sc.tagline))}</p>
                    <span class="lrn-screnmodes">${modes}</span>
                </span>
            </div>`;
        }).join("");
        /* The row's LEAD-IN. `scenariosLead` was authored in Phase 1b and
           rendered nowhere — the string existed, the map did not show it, and
           a learner met three unexplained buttons. It says what the three
           modes are for, which is the one thing the buttons cannot. */
        return `<div class="lrn-screnhead">
                <span class="lrn-screnheadtitle">${esc(T("scenarios"))}</span>
                <p class="lrn-screnlead">${esc(T("scenariosLead"))}</p>
            </div>
            <div class="lrn-screnrow" role="group"
                aria-label="${esc(T("scenarios"))}">${cards}</div>`;
    }

    /* ------------------------------------------------------ scenario: TRY
       The replica, and the learner drives. Nothing here can reach a record:
       `shellHTML` renders a fixture, and the click bridge below only ever
       changes which step of the walkthrough is showing. */
    _scenarioBody() {
        const sc = this.scenario;
        if (!sc) {
            return "";
        }
        if (this.state.sDone) {
            return this._scenarioDoneBody(sc);
        }
        const step = this.sCurrent;
        if (!step) {
            return "";
        }
        const shell = shellHTML(this._scenarioScreen(step),
                                { guided: true, visible: this.visible });
        const pct = Math.round((this.state.sStep + 1) / this.sSteps.length * 100);
        return `${shell}
        <div class="lrn-playbar" role="group">
            <span class="lrn-meter"><i style="width:${pct}%"></i></span>
            <span class="lrn-stepno">${esc(
                T("step") + " " + (this.state.sStep + 1) + " " + T("of") + " " + this.sSteps.length)}</span>
            <button class="lrn-btn sm" data-act="s-back"
                ${this.state.sStep === 0 ? "disabled" : ""}
                >${ic("chevron-left")}${esc(T("back"))}</button>
            <button class="lrn-btn sm ghost" data-act="s-exit">${ic("x")}${esc(T("exit"))}</button>
        </div>`;
    }

    _scenarioDoneBody(sc) {
        return `
        <div class="lrn-quizwrap">
            <span class="lrn-chip b">${ic("award")}${esc(T("scDone"))}</span>
            <h2>${esc(tx(sc.name))}</h2>
            <p class="lrn-lead">${esc(T("scDoneBody"))}</p>
            <div class="lrn-cta"><button class="lrn-btn pri" data-act="to-map"
                >${ic("chevron-left")}${esc(T("yourJourney"))}</button></div>
        </div>`;
    }

    /** The Try card. An observe step offers Next; a click or input step does
     *  NOT — the whole point of Try is that the learner finds and presses the
     *  control, and a Next button beside "press the glowing one" is a way past
     *  the only thing being taught. */
    _scenarioCardHTML() {
        const step = this.sCurrent;
        if (!step) {
            return "";
        }
        const acts = step.act === "click" || step.act === "input";
        // An input step says BOTH things: what value is wanted, and that
        // typing it is what moves the walkthrough. The second half is not
        // decoration — there is no Next button on this card, so a learner who
        // does not know Enter is the way on has no way on.
        const ask = step.act === "input"
            ? T("scExpected") + ": " + tx(step.value) + " — " + T("scTypeHere")
            : T("scPressIt");
        return `
        ${step.kicker ? `<div class="lrn-kicker">${esc(tx(step.kicker))}</div>` : ""}
        <h3>${esc(tx(step.title))}</h3>
        <div class="lrn-cbody">${gtx(step.body)}</div>
        ${acts ? `<div class="lrn-scwait">
            <h4>${ic("target")}${esc(T("scYourTurn"))}</h4>
            <p>${esc(ask)}</p>
        </div>` : ""}
        ${this.state.sMiss
            ? `<div class="lrn-scmiss">${ic("info")}<span>${esc(T("scNotYet"))}</span></div>` : ""}
        ${this.state.sNudge
            ? `<div class="lrn-scnudge">${ic("info")}${esc(T("scNudge"))}</div>` : ""}
        ${step.tip ? `<div class="lrn-tip">${ic("info")}<span>${esc(tx(step.tip))}</span></div>` : ""}
        <div class="lrn-ctools">
            <span class="lrn-chip">${ic("shield-check")}${esc(T("scTryBadge"))}</span>
            ${acts ? "" : `<button class="lrn-btn sm pri" data-act="s-next"
                >${esc(T("next"))}${ic("chevron-right")}</button>`}
        </div>`;
    }

    /* ---------------------------------------------------------- outline view */
    _outlineBody() {
        const s = this.current;
        if (!s) {
            return "";
        }
        const o = s.outline;
        const block = (icon, label, value) => value
            ? `<div class="lrn-obl"><h4>${ic(icon)}${esc(label)}</h4><p>${esc(tx(value))}</p></div>`
            : "";
        const mistakes = (o.mistakes || []).map((m) =>
            `<li>${esc(tx(m))}</li>`).join("");

        return `
        <div class="lrn-back"><button class="lrn-btn ghost sm" data-act="to-map">
            ${ic("chevron-left")}${esc(T("yourJourney"))}</button></div>
        <header class="lrn-ohead">
            <span class="lrn-cardico big">${ic(s.icon)}</span>
            <div>
                <h1>${esc(tx(s.name))}</h1>
                <p class="lrn-lead">${esc(tx(s.summary))}</p>
            </div>
        </header>
        ${s.kind !== "lesson"
            ? `<p class="lrn-callout">${ic("info")}${esc(T("outlineNote"))}</p>` : ""}
        ${!s.visible
            ? `<p class="lrn-callout warn">${ic("lock")}${esc(T("notVisibleBody"))}</p>`
            : (s.reach
                ? `<p class="lrn-callout">${ic("compass")}<b>${esc(T("reachVia"))}${SP}${esc(s.reach)}.</b>${SP}${esc(T("reachViaBody"))}</p>`
                : "")}
        <div class="lrn-obls">
            ${block("help-circle", T("whatIs"), o.what)}
            ${block("target", T("whyMatters"), o.why)}
            ${block("clock", T("whenUse"), o.when)}
            ${block("lock", T("prereq"), o.prereq)}
        </div>
        ${mistakes ? `<div class="lrn-panel"><h3>${ic("alert-triangle")}${esc(T("mistakes"))}</h3>
            <ul class="lrn-mistakes">${mistakes}</ul></div>` : ""}
        ${s.kind === "lesson"
            ? `<div class="lrn-cta"><button class="lrn-btn pri" data-act="start-lesson">
                 ${ic("play")}${esc(T("fullLesson"))}${SP}· ${s.duration_min}${SP}${esc(T("min"))}</button></div>`
            : ""}`;
    }

    /* ----------------------------------------------------------- lesson view */
    _lessonBody() {
        const steps = this.steps;
        if (!steps.length) {
            return "";
        }
        if (this.state.quiz) {
            return this._quizBody();
        }
        const st = steps[this.state.step];
        const shell = shellHTML(st.screen, { guided: true, visible: this.visible });
        const pctDone = Math.round((this.state.step + 1) / steps.length * 100);
        return `${shell}
        <div class="lrn-playbar" role="group" aria-label="${esc(T("step"))}">
            <span class="lrn-meter"><i style="width:${pctDone}%"></i></span>
            <span class="lrn-stepno">${esc(T("step"))}${SP}${this.state.step + 1}${SP}${esc(T("of"))}${SP}${steps.length}</span>
            <button class="lrn-btn sm" data-act="l-back" ${this.state.step === 0 ? "disabled" : ""}>
                ${ic("chevron-left")}${esc(T("back"))}</button>
            <button class="lrn-btn sm pri" data-act="l-next">
                ${esc(this.state.step === steps.length - 1 ? T("check") : T("next"))}${ic("chevron-right")}</button>
            <button class="lrn-btn sm ghost" data-act="l-replay" title="${esc(T("replay"))}"
                aria-label="${esc(T("replay"))}">${ic("rotate-ccw")}</button>
            <button class="lrn-btn sm ghost" data-act="l-exit">${ic("x")}${esc(T("exit"))}</button>
        </div>`;
    }

    /** The card the spotlight places. Built here, not in the template, because
     *  it is positioned against a measured rectangle. */
    _coachCardHTML() {
        const st = this.steps[this.state.step];
        if (!st) {
            return "";
        }
        let moment = "";
        if (st.visual === "calc") {
            moment = `<div class="lrn-moment">${calcHTML()}</div>`;
        } else if (st.visual === "pipeline") {
            moment = `<div class="lrn-moment">${pipeHTML(st.moment_chain, 0)}</div>`;
        } else if (st.visual === "morph") {
            moment = `<div class="lrn-moment">${morphHTML(st, this.state.morphSide)}</div>`;
        }
        return `
        ${st.kicker ? `<div class="lrn-kicker">${esc(tx(st.kicker))}</div>` : ""}
        <h3>${esc(tx(st.title))}</h3>
        <div class="lrn-cbody">${gtx(st.body)}</div>
        ${moment}
        ${st.consequence ? `<div class="lrn-conseq"><h4>${ic("alert-triangle")}${esc(T("consequence"))}</h4>
            <p>${esc(tx(st.consequence))}</p></div>` : ""}
        ${st.tip ? `<div class="lrn-tip">${ic("info")}<span>${esc(tx(st.tip))}</span></div>` : ""}`;
    }

    /* ------------------------------------------------------------- quiz view */
    _quizBody() {
        const l = this.lesson;
        const quiz = l.quizzes[0];
        if (!quiz) {
            return this._debriefBody();
        }
        const chosen = this.state.answered;
        const opts = quiz.options.map((o, i) => {
            const picked = chosen === i;
            const cls = picked ? (o.correct ? "right" : "wrong") : "";
            // No verdict heading above the explanation. Every explanation is
            // authored to open with its own — "Yes.", "Exactly.", "Let's
            // rethink that." — in both languages, so a heading made the app
            // say the same sentence twice. The colour and the option's own
            // mark carry the signal; the words are the content's job.
            return `
            <button class="lrn-opt ${cls}" data-opt="${i}" ${chosen !== null ? "disabled" : ""}>
                <span class="lrn-optmark">${picked ? ic(o.correct ? "check" : "rotate-ccw") : String.fromCharCode(65 + i)}</span>
                <span>${esc(tx(o.label))}</span>
            </button>
            ${picked ? `<div class="lrn-explain ${o.correct ? "ok" : "warn"}">
                <p>${esc(tx(o.feedback))}</p></div>` : ""}`;
        }).join("");

        const answeredRight = chosen !== null && quiz.options[chosen].correct;
        return `
        <div class="lrn-quizwrap">
            <header class="lrn-quizhead">
                <span class="lrn-chip b">${ic("help-circle")}${esc(T("check"))}</span>
                <p class="lrn-note">${esc(T("checkNote"))}</p>
            </header>
            <h2>${esc(tx(quiz.prompt))}</h2>
            <div class="lrn-opts">${opts}</div>
            <div class="lrn-quizfoot">
                ${chosen === null
                    ? `<button class="lrn-btn ghost" data-act="l-backstep">${ic("chevron-left")}${esc(T("back"))}</button>`
                    : answeredRight
                        ? `<button class="lrn-btn pri" data-act="l-finish">${ic("check")}${esc(T("finish"))}</button>`
                        : `<button class="lrn-btn pri" data-act="l-retry">${ic("rotate-ccw")}${esc(T("tryAgain"))}</button>`}
            </div>
        </div>`;
    }

    _debriefBody() {
        return `<div class="lrn-quizwrap"><h2>${esc(T("finish"))}</h2>
            <button class="lrn-btn pri" data-act="l-finish">${esc(T("continueBtn"))}</button></div>`;
    }


    /* ------------------------------------------------------- mission list */
    _missionListBody() {
        const cards = this.missions.map((m) => {
            const done = (this.progress[`mission:${m.key}`] || {}).state === "done";
            const full = m.kind === "full";
            // A live capstone is marked on the CARD, not only inside it. It is
            // the one mission on this list that touches real records, and a
            // learner should know that before they open it, not after.
            const live = m.kind === "live";
            return `
            <button class="lrn-card ${full || live ? "star" : ""}${SP}${done ? "done" : ""}"
                    data-mission="${esc(m.key)}">
                <span class="lrn-cardico">${ic(m.icon)}</span>
                <span class="lrn-cardmain">
                    <span class="lrn-cardtitle">${esc(tx(m.name))}
                        ${done ? ic("check-circle", "ok") : ""}</span>
                    <span class="lrn-carddesc">${esc(tx(m.summary))}</span>
                    <span class="lrn-cardmeta">
                        ${live ? `<span class="lrn-chip a">${ic("zap")}${esc(T("liveBadge"))}</span>` : ""}
                        <span class="lrn-chip ${full ? "b" : ""}">${ic(full ? "flask" : "list-checks")}
                            ${esc(live ? T("liveStart") : (full ? T("startMission") : T("outlineMission")))}</span>
                        <span class="lrn-chip">${ic("clock")}${esc(
                            T("est") + " " + m.duration_min + " " + T("min"))}</span>
                    </span>
                </span>
            </button>`;
        }).join("");
        return `
        <div class="lrn-back"><button class="lrn-btn ghost sm" data-act="to-map">
            ${ic("chevron-left")}${esc(T("yourJourney"))}</button></div>
        <header class="lrn-hero"><div>
            <h1>${esc(T("missions"))}</h1>
            <p class="lrn-lead">${esc(T("missionsLead"))}</p>
        </div></header>
        <div class="lrn-cards">${cards}</div>`;
    }

    /* ---------------------------------------------------------- mission run
       Runs on the PRACTICE REPLICA, never a live screen. A step that says
       "compute the run" would otherwise create 48 real payslips. */
    /** Which replica screen a mission step is standing on.
     *
     *  A step with no `nav` — a decision, a consequence card — does not move
     *  the learner; it asks a question about where they already are. So the
     *  screen is the last one the mission navigated to, not a default.
     *
     *  In health_learn this fell back to one hard-coded screen, which was
     *  invisibly correct for the missions that start there and wrong for every
     *  other section — a decision asked over the wrong screen entirely. The
     *  line's own home screen decides instead.
     */
    _missionScreen(step) {
        if (step.nav) {
            return step.nav;
        }
        for (let i = this.state.mStep - 1; i >= 0; i--) {
            const prev = this.mSteps[i];
            if (prev && prev.nav) {
                return prev.nav;
            }
        }
        // Nothing has navigated yet — the mission's own line decides where it
        // opens, so a mission never opens on a screen from another section.
        return this.mission.screen || MISSION_HOME[this.mission.line] || "runpayroll";
    }

    _missionBody() {
        const m = this.mission;
        if (!m) {
            return "";
        }
        if (m.kind === "live") {
            // Live capstones validate REAL actions on REAL records and are
            // demo-world only (design_v2 §5). Outside it there is nothing to
            // observe, so the runner says so by name rather than opening a
            // mission whose steps could never complete. The server refuses too
            // — this branch is the courtesy, learn.live._live_gate is the gate.
            return this.isDemo
                ? this._liveBriefingBody(m)
                : this._missionUnavailableBody(m);
        }
        if (m.kind !== "full") {
            return this._missionOutlineBody(m);
        }
        if (this.state.mDone) {
            return this._debriefBody(m);
        }
        const step = this.mCurrent;
        if (!step) {
            return "";
        }
        const screen = this._missionScreen(step);
        const shell = shellHTML(screen, { guided: true, visible: this.visible });
        const pct = Math.round((this.state.mStep + 1) / this.mSteps.length * 100);
        return `${shell}
        <div class="lrn-playbar" role="group">
            <span class="lrn-meter"><i style="width:${pct}%"></i></span>
            <span class="lrn-stepno">${esc(
                T("step") + " " + (this.state.mStep + 1) + " " + T("of") + " " + this.mSteps.length)}</span>
            <button class="lrn-btn sm ghost" data-act="m-hint">${ic("lightbulb")}${esc(T("showHint"))}</button>
            <button class="lrn-btn sm ghost" data-act="m-exit">${ic("x")}${esc(T("exit"))}</button>
        </div>`;
    }

    /** A mission this build cannot run. Named, not hidden: a card that opens
     *  onto nothing is worse than a card that says why. */
    _missionUnavailableBody(m) {
        return `
        <div class="lrn-back"><button class="lrn-btn ghost sm" data-act="to-missions">
            ${ic("chevron-left")}${esc(T("missions"))}</button></div>
        <header class="lrn-ohead">
            <span class="lrn-cardico big">${ic(m.icon)}</span>
            <div><h1>${esc(tx(m.name))}</h1><p class="lrn-lead">${esc(tx(m.summary))}</p></div>
        </header>
        <p class="lrn-callout warn">${ic("lock")}${esc(T("liveNotYet"))}</p>`;
    }

    /** The live capstone's front door: what is real, and a nudge to rehearse.
     *
     *  The nudge is a LINK and never a lock. An account executive driving a
     *  demo has to be able to jump straight to the climax, and a learner who
     *  wants to feel the consequence first should be one click from doing so.
     *  Hard-locking would serve neither of them. */
    _liveBriefingBody(m) {
        const rehearsed = (this.progress["mission:m1"] || {}).state === "done";
        const c = m.consequence || {};
        return `
        <div class="lrn-back"><button class="lrn-btn ghost sm" data-act="to-missions">
            ${ic("chevron-left")}${esc(T("missions"))}</button></div>
        <header class="lrn-ohead">
            <span class="lrn-cardico big">${ic(m.icon)}</span>
            <div><h1>${esc(tx(m.name))}
                    <span class="lrn-chip a">${ic("zap")}${esc(T("liveBadge"))}</span></h1>
                <p class="lrn-lead">${esc(tx(m.summary))}</p></div>
        </header>
        <div class="lrn-panel">
            <h3>${ic("alert-triangle")}${esc(T("liveReal"))}</h3>
            <p class="lrn-note">${esc(T("liveRealBody"))}</p>
            <div class="lrn-obls">
                <div class="lrn-obl"><h4>${ic("target")}${esc(T("scope"))}</h4>
                    <p>${esc(tx(c.scope))}</p></div>
                <div class="lrn-obl"><h4>${ic("rotate-ccw")}${esc(T("reversible"))}</h4>
                    <p>${esc(tx(c.reversible))}</p></div>
                <div class="lrn-obl"><h4>${ic("help-circle")}${esc(T("verify"))}</h4>
                    <p>${esc(tx(c.verify))}</p></div>
            </div>
        </div>
        ${rehearsed ? "" : `<div class="lrn-panel">
            <h3>${ic("flask")}${esc(T("liveNudge"))}</h3>
            <p class="lrn-note">${esc(T("liveNudgeBody"))}</p>
            <button class="lrn-btn sm" data-mission="m1">${ic("play")}${esc(T("liveNudgeGo"))}</button>
        </div>`}
        <div class="lrn-cta">
            <button class="lrn-btn pri" data-act="live-start">
                ${ic("zap")}${esc(T("liveStart"))}</button>
        </div>`;
    }

    _missionOutlineBody(m) {
        return `
        <div class="lrn-back"><button class="lrn-btn ghost sm" data-act="to-missions">
            ${ic("chevron-left")}${esc(T("missions"))}</button></div>
        <header class="lrn-ohead">
            <span class="lrn-cardico big">${ic(m.icon)}</span>
            <div><h1>${esc(tx(m.name))}</h1><p class="lrn-lead">${esc(tx(m.summary))}</p></div>
        </header>
        <p class="lrn-callout">${ic("info")}${esc(tx(m.outline_note))}</p>`;
    }

    /** The mission's coach card: instruction, detail, and — on a risky step —
     *  the consequence interception that must be acknowledged first. */
    _missionCardHTML() {
        const m = this.mission;
        const step = this.mCurrent;
        if (!step) {
            return "";
        }
        if (step.is_decision) {
            return this._decisionHTML(step);
        }
        if (step.is_consequence && !this.state.mAcked) {
            return this._consequenceHTML(m);
        }
        return `
        <div class="lrn-kicker">${esc(step.is_undo ? T("undoShown") : T("startMission"))}</div>
        <h3>${esc(tx(step.instruction))}</h3>
        ${step.detail ? `<div class="lrn-cbody">${gtx(step.detail)}</div>` : ""}
        ${this.state.mHint && step.hint
            ? `<div class="lrn-tip">${ic("lightbulb")}<span>${esc(tx(step.hint))}</span></div>` : ""}
        <div class="lrn-ctools">
            <button class="lrn-btn sm" data-act="m-back" ${this.state.mStep === 0 ? "disabled" : ""}
                >${ic("chevron-left")}${esc(T("back"))}</button>
            <button class="lrn-btn sm pri" data-act="m-next">${esc(T("next"))}${ic("chevron-right")}</button>
        </div>`;
    }

    /* The interception. Scope, reversibility, what to verify — the three
       questions a person actually needs before a risky action, and the reason
       the mission cannot advance until they have been seen. */
    _consequenceHTML(m) {
        const c = m.consequence;
        return `
        <div class="lrn-kicker">${esc(T("consequence"))}</div>
        <h3>${esc(tx(c.title))}</h3>
        <div class="lrn-conseq">
            <h4>${ic("target")}${esc(T("scope"))}</h4><p>${esc(tx(c.scope))}</p>
        </div>
        <div class="lrn-conseq">
            <h4>${ic("rotate-ccw")}${esc(T("reversible"))}</h4><p>${esc(tx(c.reversible))}</p>
        </div>
        <div class="lrn-conseq">
            <h4>${ic("shield-check")}${esc(T("verify"))}</h4><p>${esc(tx(c.verify))}</p>
        </div>
        <div class="lrn-ctools">
            <button class="lrn-btn sm ghost" data-act="m-cancel">${esc(T("cancelAct"))}</button>
            <button class="lrn-btn sm pri" data-act="m-ack">${ic("check")}${esc(T("proceed"))}</button>
        </div>`;
    }

    _decisionHTML(step) {
        const chosen = this.state.mChoice;
        const picked = chosen ? step.options.find((o) => o.key === chosen) : null;
        const opts = step.options.map((o) => `
            <button class="lrn-opt ${chosen === o.key ? (o.correct ? "right" : "wrong") : ""}"
                    data-mopt="${esc(o.key)}" ${chosen ? "disabled" : ""}>
                <span>${esc(tx(o.label))}</span>
            </button>`).join("");
        return `
        <div class="lrn-kicker">${esc(T("check"))}</div>
        <h3>${esc(tx(step.instruction))}</h3>
        ${step.detail ? `<div class="lrn-cbody">${gtx(step.detail)}</div>` : ""}
        <div class="lrn-opts">${opts}</div>
        ${picked && !picked.correct
            ? `<div class="lrn-explain warn"><p>${gtx(picked.recovery)}</p></div>` : ""}
        ${this.state.mHint && step.hint && !chosen
            ? `<div class="lrn-tip">${ic("lightbulb")}<span>${esc(tx(step.hint))}</span></div>` : ""}
        <div class="lrn-ctools">
            ${!chosen ? "" : picked.correct
                ? `<button class="lrn-btn sm pri" data-act="m-next">${esc(T("continueBtn"))}${ic("chevron-right")}</button>`
                : `<button class="lrn-btn sm pri" data-act="m-retry">${ic("rotate-ccw")}${esc(T("tryAgain"))}</button>`}
        </div>`;
    }

    _debriefBody(m) {
        const list = (rows) => rows.map((r) => `<li>${esc(tx(r))}</li>`).join("");
        return `
        <div class="lrn-quizwrap">
            <span class="lrn-chip b">${ic("award")}${esc(T("debriefTitle"))}</span>
            <h2>${esc(tx(m.name))}</h2>

            <div class="lrn-panel"><h3>${ic("check-circle")}${esc(T("whatYouDid"))}</h3>
                <ul class="lrn-mistakes">${list(m.did)}</ul></div>

            <!-- The seeded anomaly, revealed AFTER the decision so it lands as
                 judgement rather than as trivia. -->
            <div class="lrn-panel"><h3>${ic("alert-triangle")}${esc(tx(m.anomaly.title))}</h3>
                <p>${esc(tx(m.anomaly.body))}</p></div>

            <div class="lrn-panel"><h3>${ic("shield-check")}${esc(T("checklist"))}</h3>
                <ul class="lrn-mistakes">${list(m.check)}</ul></div>

            <p class="lrn-note">${esc(T("confGain"))}: <b>${this.state.mGain || 0}</b>${
                esc(this.state.mRecovered ? " — " + T("recoveryUsed") : "")}</p>

            <div class="lrn-cta"><button class="lrn-btn pri" data-act="to-missions"
                >${ic("chevron-left")}${esc(T("backToMissions"))}</button></div>
        </div>`;
    }

    // ---------------------------------------------------------- post-render fx
    _afterPaint() {
        if (this.state.view === "practice") {
            // No spotlight in the sandbox: nothing is being pointed at, and a
            // ring left over from the map would be pointing at the wrong page.
            Spot.hide();
            return;
        }
        if (this.state.view === "scenario") {
            const step = this.sCurrent;
            if (!step || this.state.sDone) {
                Spot.hide();
                return;
            }
            Spot.show(step.anchor, this._scenarioCardHTML());
            this._markWanted(step);
            return;
        }
        if (this.state.view === "mission") {
            const m = this.mission;
            const step = this.mCurrent;
            if (!m || m.kind !== "full" || this.state.mDone || !step) {
                Spot.hide();
                return;
            }
            Spot.show(step.target, this._missionCardHTML());
            return;
        }
        if (this.state.view !== "lesson" || this.state.quiz) {
            Spot.hide();
            return;
        }
        const st = this.steps[this.state.step];
        if (!st) {
            return;
        }
        Spot.show(st.anchor, this._coachCardHTML());
        if (st.visual === "trace") {
            // After the spotlight's own scroll has settled, or the line is
            // drawn between two rectangles that are about to move.
            setTimeout(() => Trace.run(st.moment_from, st.moment_to), reduced() ? 0 : 420);
        } else if (st.visual === "pipeline" && Spot.card) {
            runPipeline(Spot.card, st.moment_chain);
        }
    }

    /** Ring the control a Try step is waiting for, and only that one.
     *
     *  The spotlight already dims around it, but the learner is being asked to
     *  FIND it: the ring is still there when they look up from the card, and it
     *  is what the nudge points back at after a wrong click. */
    _markWanted(step) {
        const root = this.overlayRef.el && this.overlayRef.el.parentElement;
        const host = root || document;
        for (const el of host.querySelectorAll(".lrn-scwant")) {
            el.classList.remove("lrn-scwant");
        }
        if (!step.anchor || step.act === "observe") {
            return;
        }
        const want = host.querySelector(`[data-coach="${step.anchor}"]`);
        if (want) {
            want.classList.add("lrn-scwant");
        }
        // An input step puts the cursor where the answer goes. Without it the
        // learner reads "type it in the field I am pointing at" and then has
        // to find the field, which is the one thing the ring was for.
        // `preventScroll`: the spotlight has already scrolled the anchor into
        // view and a second scroll fights the first one.
        if (want && step.act === "input") {
            const field = want.matches("input") ? want : want.querySelector("input");
            try {
                if (field && field !== document.activeElement) {
                    field.focus({ preventScroll: true });
                }
            } catch {
                // A detached field must not end the walkthrough.
            }
        }
    }

    /* -------------------------------------------------- the Try click bridge
       The MISSING half of a replica: without this, every control on a practice
       screen is inert and a Try step can only be walked past with Next, which
       is a lesson with extra steps rather than a rehearsal.

       Two rules, both from the mode matrix:
         · the expected control advances the walkthrough;
         · anything else is a NUDGE. Not a failure, not a mark, and never a
           silent no-op — a replica control that does nothing when you press it
           teaches the learner that the product is broken.
       Returns true when the event belonged to a scenario, so the ordinary
       Journey handlers below do not also fire on it. */
    _scenarioClick(ev) {
        if (this.state.view !== "scenario" || this.state.sDone) {
            return false;
        }
        const hit = ev.target.closest("[data-coach], [data-nav]");
        if (!hit) {
            return false;
        }
        const step = this.sCurrent;
        if (!step || step.act === "observe") {
            // Nothing is being asked for. The replica's controls stay inert
            // rather than pretending to work.
            return true;
        }
        const key = hit.getAttribute("data-coach");
        // THE BLUR AND THE CLICK THAT CAUSED IT ARE ONE GESTURE, and without
        // this they would be two steps. Type the value, press the control the
        // NEXT step asks for: `focusout` fires first and advances on the
        // value, then this handler sees the new step with its own anchor
        // already under the cursor and advances again — so the card for the
        // step in between is never read. Armed by `_scenarioInputCheck` only
        // when a blur advanced, and disarmed by the `mousedown` that starts
        // any LATER click, so a learner who tabs away and comes back never
        // loses one. Ordering is what makes it exact rather than a timer:
        // mousedown, then focusout, then click.
        if (this._blurAdvanced) {
            this._blurAdvanced = false;
            if (key && step.anchor && key === step.anchor) {
                return true;
            }
        }
        const onTarget = !!(key && step.anchor && key === step.anchor);
        // AN INPUT STEP NEVER ADVANCES ON A CLICK. Pressing the field is how
        // you start typing in it, and nothing more: the value is what is being
        // asked for, and a click that walked past the value would make the
        // step a button-press with a text box beside it. The only advance an
        // input step has is `_scenarioInputCheck`, below.
        if (step.act === "input") {
            this.state.sNudge = !onTarget;
            return true;
        }
        if (step.act === "click" && onTarget) {
            this.state.sNudge = false;
            this.sNext();
        } else {
            this.state.sNudge = true;
        }
        return true;
    }

    /** THE ONLY PLACE AN INPUT STEP ADVANCES, and the guard is its first
     *  statement for the same reason `_watchAutoClick` re-asks its own.
     *
     *  Everything that could make this fire on the wrong thing is answered
     *  before `sNext()` is reachable: the view, the step's act, the element
     *  being INSIDE the anchor the step named, an empty field, and finally the
     *  value itself through `looseMatch`. A wrong value produces `sMiss` and
     *  nothing else — there is no branch here that advances without the match,
     *  and `tests/test_scenario.py::test_15` asserts that structurally rather
     *  than trusting this paragraph.
     */
    _scenarioInputCheck(el, fromBlur) {
        if (this.state.view !== "scenario" || this.state.sDone) {
            return;
        }
        const step = this.sCurrent;
        if (!step || step.act !== "input" || !step.anchor) {
            return;
        }
        const host = el.closest("[data-coach]");
        if (!host || host.getAttribute("data-coach") !== step.anchor) {
            return;
        }
        const typed = el.value || "";
        if (!typed.trim()) {
            // Blurring an untouched field is not a wrong answer. Saying it was
            // would put a correction on the screen for doing nothing.
            return;
        }
        const spec = INPUT_ANCHORS[step.anchor] || {};
        if (!looseMatch(typed, tx(step.value), spec.kind)) {
            this.state.sMiss = true;
            return;
        }
        this.state.sMiss = false;
        this.state.sNudge = false;
        this._blurAdvanced = !!fromBlur;
        this.sNext();
    }

    /* ------------------------------------------- the practice click bridge
       ONE control does anything in the sandbox: a `data-nav` leaf in the
       replica's own menu. Everything else on a practice screen is inert,
       exactly as it is on a lesson's replica — a fake Compute button that
       "worked" would be teaching the wrong thing about the real one.

       Returns true when the event belonged to the sandbox, so the Journey's
       own handlers do not also fire on it. */
    _practiceClick(ev) {
        if (this.state.view !== "practice") {
            return false;
        }
        const nav = ev.target.closest("[data-nav]");
        if (!nav) {
            return false;
        }
        this.pNav(nav.getAttribute("data-nav"));
        return true;
    }

    // -------------------------------------------------------------- behaviour
    onClick(ev) {
        // FIRST, and it has to be: a Try step's target is a replica control
        // carrying `data-coach`, and some of those also carry `data-nav`, which
        // the mission handlers below would read as ordinary replica navigation.
        const scenarioBtn = ev.target.closest("[data-scenario]");
        if (scenarioBtn) {
            ev.preventDefault();
            this.openScenario(scenarioBtn.dataset.scenario, scenarioBtn.dataset.mode);
            return;
        }
        if (this._scenarioClick(ev)) {
            ev.preventDefault();
            return;
        }
        if (this._practiceClick(ev)) {
            ev.preventDefault();
            return;
        }
        const stationBtn = ev.target.closest("[data-station]");
        if (stationBtn) {
            this.openStation(stationBtn.dataset.station);
            return;
        }
        const missionBtn = ev.target.closest("[data-mission]");
        if (missionBtn) {
            this.openMission(missionBtn.dataset.mission);
            return;
        }
        const mopt = ev.target.closest("[data-mopt]");
        if (mopt) {
            this.chooseMission(mopt.dataset.mopt);
            return;
        }
        const opt = ev.target.closest("[data-opt]");
        if (opt) {
            this.answer(parseInt(opt.dataset.opt, 10));
            return;
        }
        const act = ev.target.closest("[data-act]");
        if (!act) {
            return;
        }
        const a = act.dataset.act;
        const fn = {
            "to-map": () => this.toMap(),
            "start-lesson": () => this.startLesson(),
            "l-next": () => this.next(),
            "l-back": () => this.back(),
            "l-backstep": () => this.back(),
            "l-replay": () => this.replay(),
            "l-exit": () => this.exitLesson(),
            "l-retry": () => this.retry(),
            "l-finish": () => this.finish(),
            "to-missions": () => this.toMissions(),
            "m-next": () => this.mNext(),
            "m-back": () => this.mBack(),
            "m-hint": () => { this.state.mHint = !this.state.mHint; },
            "m-exit": () => this.mExit(),
            "m-ack": () => { this.state.mAcked = true; },
            "m-cancel": () => this.mBack(),
            "m-retry": () => { this.state.mChoice = null; },
            "live-start": () => this.startLive(),
            "s-next": () => this.sNext(),
            "s-back": () => this.sBack(),
            "s-exit": () => this.sExit(),
            "to-practice": () => this.openPractice(),
            "p-exit": () => this.pExit(),
            // LEARNOS Phase 6. The Continue strip opens whatever the server
            // suggested — a station or the live capstone — through the SAME
            // two doors everything else on this page uses, so the suggestion
            // cannot become a third way of starting a lesson.
            "nb-go": () => {
                const kind = act.dataset.kind;
                const key = act.dataset.key;
                if (kind === "mission") {
                    this.openMission(key);
                } else {
                    this.openStation(key);
                }
            },
            "morph-before": () => { this.state.morphSide = "before"; },
            "morph-after": () => { this.state.morphSide = "after"; },
        }[a];
        if (fn) {
            ev.preventDefault();
            fn();
        }
    }

    onInput(ev) {
        const el = ev.target.closest('[data-act="search"]');
        if (el) {
            this.state.search = el.value;
        }
    }

    /** Enter, inside a replica field. The check is the same one a blur runs;
     *  Enter exists because it is what a person types after a value. */
    onKeydown(ev) {
        // DISARM FIRST, AND FOR THE KEYBOARD TOO. Enter and Space ACTIVATE a
        // focused control, which dispatches a click — so a learner who typed
        // the value, pressed Tab and then pressed Enter on the next button was
        // having that press swallowed by the one-shot below, silently. The
        // pointer gesture is disarmed by `mousedown`; this is the same
        // disarm for the gesture that has no mousedown in it. A silent no-op
        // on a replica control is the thing the click bridge exists to
        // prevent, so it may not be how the bridge itself behaves.
        if (ev.key === "Enter" || ev.key === " " || ev.key === "Spacebar") {
            this._blurAdvanced = false;
        }
        if (ev.key !== "Enter") {
            return;
        }
        const el = ev.target.closest && ev.target.closest("input");
        if (!el) {
            return;
        }
        ev.preventDefault();
        this._scenarioInputCheck(el);
    }

    /** Leaving the field. Checked too, because somebody who types the value
     *  and then clicks the control they think comes next should not be told
     *  they got it wrong — they got it right and moved on. */
    onFocusOut(ev) {
        const el = ev.target.closest && ev.target.closest("input");
        if (el) {
            this._scenarioInputCheck(el, true);
        }
    }

    /** Disarms the one-shot above. It runs BEFORE the blur it may cause, so a
     *  click that starts fresh always clears a flag left over from a tab-away,
     *  and a click that caused the blur is armed after it. */
    onMouseDown() {
        this._blurAdvanced = false;
    }

    _onKey(ev) {
        const typing = /^(INPUT|TEXTAREA)$/.test(ev.target.tagName);
        if (typing) {
            return;
        }
        // ONE RUNG AT A TIME. A hovercard over a lesson closes on the first
        // Escape and this stands down for it; the second Escape leaves the
        // lesson. Every branch below that CLOSES something swallows the key
        // for the same reason — the arrow branches only move the reader, so
        // they take the default and leave the key alone.
        if (ev.key === "Escape" && glossaryOpen()) {
            return;
        }
        if (this.state.view === "practice") {
            if (ev.key === "Escape") {
                ev.preventDefault();
                ev.stopPropagation();
                this.pExit();
            }
            return;
        }
        if (this.state.view === "scenario") {
            // NO right-arrow on a step that is waiting for a press. The keyboard
            // must not be a way past the control the walkthrough is asking for
            // — that is the same promise the missing Next button makes.
            const step = this.sCurrent;
            if (ev.key === "Escape") {
                ev.preventDefault();
                ev.stopPropagation();
                this.sExit();
            } else if (ev.key === "ArrowRight" && step && step.act === "observe") {
                ev.preventDefault();
                this.sNext();
            } else if (ev.key === "ArrowLeft") {
                ev.preventDefault();
                this.sBack();
            }
            return;
        }
        if (this.state.view !== "lesson") {
            return;
        }
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.exitLesson();
        } else if (ev.key === "ArrowRight") {
            ev.preventDefault();
            this.next();
        } else if (ev.key === "ArrowLeft") {
            ev.preventDefault();
            this.back();
        }
    }

    /* --------------------------------------------------------- deep links
       PayAI's "Show me" opens `pb_learn.action_learn_journey` with
       `context.lesson = "<key>"`; the demo first-login greeting opens it with
       `context.suggest = "LW"`.

       NEITHER MAY EVER BREAK THE JOURNEY. A key that does not resolve — a
       lesson retired between a cached conversation and today, a station whose
       leaf is not installed on this tenant, a context somebody hand-typed —
       falls through to the map, which is exactly where the learner wanted to be
       anyway. There is no error state here on purpose: the worst outcome of a
       bad deep link should be an ordinary Journey. */
    _applyDeepLink() {
        let ctx = {};
        try {
            ctx = (this.props && this.props.action && this.props.action.context) || {};
        } catch {
            ctx = {};
        }
        const suggest = typeof ctx.suggest === "string" ? ctx.suggest : "";
        if (suggest && this._stationOfLesson(suggest)) {
            this.state.suggest = suggest;
        }
        // A scenario deep link. `learn.scenario.begin("…", "try")` opens this
        // action rather than rendering the replica wherever the learner was
        // standing, so the Coach drawer, a Journey card and an intent's
        // `show_me` all reach Try through ONE door.
        // The Coach's practice-mode entry (Phase 5). One door, same as the
        // scenario link: the drawer opens this action rather than growing a
        // second sandbox of its own.
        if (ctx.practice) {
            this.openPractice();
            return;
        }
        // LEARNOS Phase 6. The Coach's "Continue" opens the STATION the
        // server suggested. A station key, not a lesson key: the suggestion is
        // made over stations (outlines included, which have no lesson to name),
        // and `openStation` is the same door a card press uses.
        const stKey = typeof ctx.station === "string" ? ctx.station : "";
        if (stKey && this.station(stKey)) {
            this.openStation(stKey);
            return;
        }
        const scKey = typeof ctx.scenario === "string" ? ctx.scenario : "";
        if (scKey && this.scenarios.some((s) => s.key === scKey)) {
            const mode = typeof ctx.mode === "string" ? ctx.mode : "try";
            this.openScenario(scKey, mode);
            return;
        }

        const key = typeof ctx.lesson === "string" ? ctx.lesson : "";
        if (!key) {
            return;
        }
        const station = this._stationOfLesson(key);
        if (!station) {
            return;                       // unknown key → the map, silently
        }
        this.openStation(station.key);
        this.startLesson();
        this._log("lesson_deeplink");
    }

    /** The station carrying a lesson KEY (L1, LW…), or null. */
    _stationOfLesson(key) {
        return this.stations.find(
            (s) => (s.lessons || []).some((l) => l.key === key)) || null;
    }

    // ------------------------------------------------------------ navigation
    toMap() {
        Spot.hide();
        this.state.view = "map";
        this.state.stationKey = null;
        // A finished scenario leaves its card behind otherwise, and the map
        // would draw the Try view's leftovers the next time it is opened.
        this.state.scenarioKey = null;
        this.state.sDone = false;
        this.state.sNudge = false;
        this.state.sMiss = false;
    }

    openStation(key) {
        this.state.stationKey = key;
        this.state.view = "outline";
        this._log("station_open");
    }

    startLesson() {
        const p = this.progress[this.state.stationKey] || {};
        // Resume ONLY a lesson that is genuinely mid-flight. Re-opening a
        // finished one used to jump straight to step 10 of 10, which reads as
        // the app skipping the lesson rather than remembering your place.
        const resumable = p.state === "in_progress"
            && (p.step_index || 0) < this.steps.length - 1;
        this.state.step = resumable ? p.step_index : 0;
        this.state.quiz = false;
        this.state.answered = null;
        this.state.morphSide = "before";
        this.state.view = "lesson";
        this._saveProgress(this.state.stationKey, { state: "in_progress", lang: this.state.lang });
        this._log("lesson_start");
    }

    next() {
        if (this.state.quiz) {
            return;
        }
        if (this.state.step < this.steps.length - 1) {
            this.state.step += 1;
            this.state.morphSide = "before";
            this._saveProgress(this.state.stationKey, { step_index: this.state.step });
            this._log("step_view", this.state.step);
        } else {
            this.state.quiz = true;
            this.state.answered = null;
        }
    }

    back() {
        if (this.state.quiz) {
            this.state.quiz = false;
            this.state.answered = null;
            return;
        }
        if (this.state.step > 0) {
            this.state.step -= 1;
            this.state.morphSide = "before";
        }
    }

    replay() {
        // Re-run this step's effect without changing position — the single
        // most-used control for a learner reading in their second language.
        this._afterPaint();
    }

    exitLesson() {
        Spot.hide();
        this.state.view = "outline";
        this.state.quiz = false;
        this._log("lesson_abandon", this.state.step);
    }

    answer(i) {
        if (this.state.answered !== null) {
            return;
        }
        const quiz = this.lesson.quizzes[0];
        const correct = !!quiz.options[i].correct;
        this.state.answered = i;
        const p = this.progress[this.state.stationKey] || {};
        const attempts = (p.attempts || 0) + 1;
        this._saveProgress(this.state.stationKey, {
            attempts,
            first_try_correct: attempts === 1 && correct ? true : !!p.first_try_correct,
        });
        this._log("quiz_answer", `${i}:${correct ? "y" : "n"}`);
    }

    retry() {
        // Recovery, not rejection: the learner returns to the same question
        // with the explanation still readable above it.
        this.state.answered = null;
    }

    finish() {
        this._saveProgress(this.state.stationKey, {
            state: "done",
            completed_at: this._nowServer(),
            lang: this.state.lang,
        });
        this._log("lesson_complete");
        Spot.hide();
        this.state.view = "outline";
        this.state.quiz = false;
        this.state.answered = null;
    }

    _nowServer() {
        // Odoo stores naive UTC. Send the same shape rather than an ISO string
        // with a Z, which the ORM would reject.
        return new Date().toISOString().slice(0, 19).replace("T", " ");
    }


    // ---------------------------------------------------------- missions
    toMissions() {
        Spot.hide();
        this.state.view = "missions";
        this.state.missionKey = null;
        this.state.mDone = false;
    }

    /** Hand the mission to the docked runner and get out of its way.
     *
     *  The Journey does NOT drive a live mission: its first step navigates to
     *  the product, which unmounts this component. LiveState is the handover,
     *  and LiveHost — mounted in the web client shell beside the Coach — is
     *  what survives the navigation. */
    startLive() {
        const m = this.mission;
        if (!m || m.kind !== "live" || !this.isDemo) {
            return;
        }
        LiveState.start(m.key);
        this.state.view = "missions";
    }

    /** Whether this session is in the demo world at all. Read from the bundle,
     *  which reads the real group and the real company — never guessed from a
     *  URL or a company name in the browser. */
    get isDemo() {
        return !!(this.bundle && this.bundle.user && this.bundle.user.is_demo);
    }

    openMission(key) {
        this.state.missionKey = key;
        this.state.view = "mission";
        this.state.mStep = 0;
        this.state.mChoice = null;
        this.state.mRecovered = false;
        this.state.mAcked = false;
        this.state.mHint = false;
        this.state.mDone = false;
        this._log("mission_start", key);
    }

    mNext() {
        const step = this.mCurrent;
        // A risky step cannot be walked past. The interception IS the lesson.
        if (step && step.is_consequence && !this.state.mAcked) {
            return;
        }
        if (this.state.mStep < this.mSteps.length - 1) {
            this.state.mStep += 1;
            this.state.mChoice = null;
            this.state.mAcked = false;
            this.state.mHint = false;
            this._log("mission_step", `${this.state.missionKey}:${this.state.mStep}`);
        } else {
            this.finishMission();
        }
    }

    mBack() {
        if (this.state.mStep > 0) {
            this.state.mStep -= 1;
            this.state.mChoice = null;
            this.state.mAcked = false;
            this.state.mHint = false;
        }
    }

    mExit() {
        Spot.hide();
        this.state.view = "missions";
        this._log("mission_abandon", `${this.state.missionKey}:${this.state.mStep}`);
    }

    chooseMission(optKey) {
        if (this.state.mChoice) {
            return;
        }
        const step = this.mCurrent;
        const opt = step.options.find((o) => o.key === optKey);
        this.state.mChoice = optKey;
        if (opt && !opt.correct) {
            // Recovery, not rejection: the learner stays in the mission and
            // reads why, then chooses again.
            this.state.mRecovered = true;
            this._log("mission_recover", `${this.state.missionKey}:${optKey}`);
        }
    }

    async finishMission() {
        Spot.hide();
        this.state.mDone = true;
        this._log("mission_complete", this.state.missionKey);
        await this._saveProgress(`mission:${this.state.missionKey}`, {
            state: "done", completed_at: this._nowServer(), lang: this.state.lang,
        });
        try {
            this.state.mGain = await this.orm.call("learn.confidence", "award",
                [this.state.missionKey, this.state.mRecovered]);
        } catch {
            this.state.mGain = 0;
        }
    }

    // ------------------------------------------------------------ scenarios
    /** Open a scenario in one of its modes.
     *
     *  Try is HOSTED HERE, over the replica. Watch and Do are handed to the
     *  service, whose overlay lives in the web client shell — its first step
     *  navigates to the real product, which unmounts this component, so a
     *  Journey-owned runner could not survive its own first step. */
    async openScenario(key, mode) {
        const sc = this.scenarios.find((s) => s.key === key);
        if (!sc) {
            return;
        }
        const wanted = (sc.modes || []).includes(mode) ? mode : (sc.modes || [])[0];
        if (wanted !== "try") {
            await this.sc.load();
            await this.sc.begin(key, wanted);
            return;
        }
        Spot.hide();
        this.state.scenarioKey = key;
        this.state.view = "scenario";
        this.state.sStep = 0;
        this.state.sNudge = false;
        this.state.sMiss = false;
        this.state.sDone = false;
        this.sc.logStart(key, "try");
    }

    sNext() {
        this.state.sNudge = false;
        this.state.sMiss = false;
        if (this.state.sStep < this.sSteps.length - 1) {
            this.state.sStep += 1;
            this.sc.record(this.state.scenarioKey, {
                state: "in_progress", step_index: this.state.sStep,
            });
            this.sc.log("scenario_step",
                        `${this.state.scenarioKey}:try:${this.state.sStep}`);
        } else {
            this.sFinish();
        }
    }

    sBack() {
        this.state.sNudge = false;
        this.state.sMiss = false;
        if (this.state.sStep > 0) {
            this.state.sStep -= 1;
        }
    }

    sFinish() {
        Spot.hide();
        this.state.sDone = true;
        this.sc.record(this.state.scenarioKey, {
            state: "done", completed_at: this._nowServer(), lang: this.state.lang,
        });
        this.sc.log("scenario_complete", `${this.state.scenarioKey}:try`);
        // The local copy drives the card's tick without a re-fetch, exactly as
        // a finished lesson does.
        this.progress[`scenario:${this.state.scenarioKey}`] = { state: "done" };
    }

    sExit() {
        Spot.hide();
        // Escape on the completion card is a normal close, not an abandon —
        // the same double-count scenario_service.stop() refuses after done.
        if (!this.state.sDone) {
            this.sc.log("scenario_abandon",
                        `${this.state.scenarioKey}:try:${this.state.sStep}`);
        }
        this.state.view = "map";
        this.state.scenarioKey = null;
        this.state.sNudge = false;
        this.state.sMiss = false;
    }

    // --------------------------------------------------------- practice mode
    /** Open the free-roam sandbox.
     *
     *  THE WHOLE SURFACE IS THESE THREE METHODS AND `_practiceBody`, AND THE
     *  ONLY SERVER CALL ANY OF THEM MAKES IS `_log`, WHICH WRITES ONE ROW INTO
     *  `learn.event`.
     *
     *  What holds that claim up is a TRIPWIRE, not a proof, and the difference
     *  is worth stating where somebody might rely on it.
     *  `tests/test_practice.py` walks this surface syntactically —
     *  `this.NAME(` edges, `this.orm.call("literal"` sites — and refuses the
     *  shapes that would let a call hide from that walk: a non-literal model
     *  name, `this.orm` handed to anything other than its own `.call`, `this`
     *  aliased to a local, `this[…]` dispatch, and any `.call(` whose receiver
     *  is not `this.orm`. A determined author can still route around a
     *  syntactic scan; what they cannot do is route around it BY ACCIDENT, and
     *  the tripwires are chosen so that every ordinary way of growing this
     *  code into a server call trips one.
     */
    openPractice() {
        Spot.hide();
        this.state.view = "practice";
        this._log("practice_open", this.state.pScreen);
    }

    /** Switch replica screens. The one thing a control in the sandbox does. */
    pNav(key) {
        // `Object.hasOwn`, not `hasOwnProperty.call`: the practice surface is
        // scanned for `.call(` sites and the only one allowed there is
        // `this.orm.call`. A second, innocent `.call(` in this method would
        // have to be exempted by name, and an exemption list on a safety scan
        // is the beginning of the scan not meaning anything.
        if (!key || !Object.hasOwn(SCREENS, key)) {
            return;
        }
        this.state.pScreen = key;
        this._log("practice_nav", key);
    }

    pExit() {
        Spot.hide();
        this._log("practice_exit", this.state.pScreen);
        this.state.view = "map";
    }

    // -------------------------------------------------------------- settings
    toggleLang() {
        this.state.lang = this.state.lang === "en" ? "vi" : "en";
        RT.lang = this.state.lang;
        this._savePrefs();
    }

    toggleMotion() {
        this.state.motion = this.state.motion === "reduced" ? "auto" : "reduced";
        RT.motion = this.state.motion;
        this._savePrefs();
    }

    // ------------------------------------------------------- template helpers
    get langLabel() {
        return this.state.lang === "en" ? "Tiếng Việt" : "English";
    }

    get motionLabel() {
        return this.state.motion === "reduced" ? T("motionOn") : T("reduceMotion");
    }

    get brandLabel() {
        return this.state.ready ? T("brand") : "Payobook";
    }

    get learnLabel() {
        return this.state.ready ? T("learn") : "";
    }

    /** Narration for screen readers: the step title, announced on change. */
    get narration() {
        if (this.state.view !== "lesson" || this.state.quiz) {
            return "";
        }
        const st = this.steps[this.state.step];
        return st ? (T("step")) + (SP) + (this.state.step + 1) + (SP) + (T("of")) + (SP) + (this.steps.length) + ". " + (tx(st.title)) : "";
    }
}

registry.category("actions").add("learn_journey", LearnJourney);
