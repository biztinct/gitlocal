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
import { shellHTML } from "../engine/screens";
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
            lang: "en",
            motion: "auto",
            error: "",
        });

        this.bundle = null;
        this.progress = {};
        this.visible = new Set();
        this._onKey = this._onKey.bind(this);

        onWillStart(async () => {
            this._restorePrefs();
            await this._loadBundle();
            this._applyDeepLink();
        });
        onMounted(() => {
            setOverlayRoot(this.overlayRef.el);
            document.addEventListener("keydown", this._onKey);
            document.body.classList.add("lrn-open");
            this._log("journey_open");
        });
        onPatched(() => this._afterPaint());
        onWillUnmount(() => {
            Spot.hide();
            document.removeEventListener("keydown", this._onKey);
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
            stations: composeStations(content, runtime),
            missions: content.missions || [],
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
        this.progress = this.bundle.progress || {};
        this.visible = new Set(
            this.bundle.stations.filter((s) => s.visible).map((s) => s.key));
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

        const ordered = LINE_ORDER.filter((k) => lines[k])
            .concat(Object.keys(lines).filter((k) => !LINE_ORDER.includes(k)));
        const lineHTML = ordered.map((lineKey) => {
            const items = lines[lineKey].filter(match);
            if (!items.length) {
                return "";
            }
            return `<section class="lrn-line">
                <h3 class="lrn-linehead">${ic(LINE_ICON[lineKey] || "map-pin")}
                    ${esc(T("lines." + lineKey))}</h3>
                <div class="lrn-cards">${items.map((s) => this._cardHTML(s)).join("")}</div>
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
                </div>
            </div>
        </header>
        <div class="lrn-toolbar">
            <button class="lrn-btn pri" data-act="to-missions"
                >${ic("flask")}${esc(T("missions"))}</button>
            <label class="lrn-search">${ic("search")}
                <input type="search" data-act="search" value="${esc(this.state.search)}"
                       placeholder="${esc(T("search"))}" aria-label="${esc(T("search"))}"/>
            </label>
        </div>
        ${lineHTML || `<p class="lrn-note">${esc(T("noAnswer"))}</p>`}`;
    }

    _cardHTML(s) {
        const st = this.stateOf(s.key);
        const badge = s.kind === "lesson"
            ? `<span class="lrn-chip b">${ic("play")}${esc(T("fullLesson"))}</span>`
            : `<span class="lrn-chip">${ic("list-checks")}${esc(T("outline"))}</span>`;
        const need = s.required
            ? `<span class="lrn-chip a">${esc(T("required"))}</span>`
            : `<span class="lrn-chip">${esc(T("optional"))}</span>`;
        const gate = s.missing
            ? `<span class="lrn-chip warn">${ic("lock")}${esc(T("notVisible"))}</span>`
            : (!s.visible
                ? `<span class="lrn-chip warn">${ic("lock")}${esc(T("notVisible"))}</span>`
                : "");
        // "Start here" is a PULSE, never an auto-play. The demo greeting opens
        // the map and points; the learner presses the card. A spotlight that
        // starts by itself is the thing pb_coach's first-run tour did, and the
        // reason people learned to dismiss it before reading it.
        const start = this.state.suggest && this.state.suggest !== ""
            && (s.lessons || []).some((l) => l.key === this.state.suggest);
        const startChip = start
            ? `<span class="lrn-chip a">${ic("sparkles")}${esc(T("startHere"))}</span>`
            : "";
        return `
        <button class="lrn-card ${s.star ? "star" : ""}${SP}${st === "done" ? "done" : ""}${
                SP}${start ? "pulse" : ""}"
                data-station="${esc(s.key)}">
            <span class="lrn-cardico">${ic(s.icon)}</span>
            <span class="lrn-cardmain">
                <span class="lrn-cardtitle">${esc(tx(s.name))}
                    ${st === "done" ? ic("check-circle", "ok") : ""}</span>
                <span class="lrn-carddesc">${esc(tx(s.summary))}</span>
                <span class="lrn-cardmeta">${startChip}${badge}${need}${gate}
                    <span class="lrn-chip">${ic("clock")}${esc(T("est"))}${SP}${s.duration_min}${SP}${esc(T("min"))}</span>
                </span>
            </span>
        </button>`;
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
            ? `<p class="lrn-callout warn">${ic("lock")}${esc(T("notVisibleBody"))}</p>` : ""}
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
        <div class="lrn-cbody">${tx(st.body)}</div>
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
        ${step.detail ? `<div class="lrn-cbody">${esc(tx(step.detail))}</div>` : ""}
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
        ${step.detail ? `<div class="lrn-cbody">${esc(tx(step.detail))}</div>` : ""}
        <div class="lrn-opts">${opts}</div>
        ${picked && !picked.correct
            ? `<div class="lrn-explain warn"><p>${tx(picked.recovery)}</p></div>` : ""}
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

    // -------------------------------------------------------------- behaviour
    onClick(ev) {
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

    _onKey(ev) {
        if (this.state.view !== "lesson") {
            return;
        }
        const typing = /^(INPUT|TEXTAREA)$/.test(ev.target.tagName);
        if (typing) {
            return;
        }
        if (ev.key === "Escape") {
            ev.preventDefault();
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
