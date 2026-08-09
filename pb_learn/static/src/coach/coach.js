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

   It never invents a domain fact either. There is no composer and no model:
   if the spine has no answer it says what it CAN answer here, by name. A
   fluent invention about a contribution rate would be worse than a miss.
   ========================================================================== */
import { Component, markup, onMounted, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";

import { RT, T, tx, esc, ic } from "../engine/runtime";
import { flashRing } from "../engine/spotlight";
import { calcHTML, calcKpiHTML } from "../engine/visuals";

/* Shared with the Journey: one language preference for the whole system. */
const LOCAL_PREFS = "pbLearnPrefs";

/* The only actions an answer may carry. Anything else is a bug, and the test
   compares the rendered HTML against exactly this set. */
export const COACH_ACTIONS = new Set([
    "c-close", "c-ask", "c-suggest", "c-show", "c-simpler", "c-lesson", "c-back",
    "c-lang",
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
            const answer = await this.orm.call("learn.intent", "ask", [q, this.state.screen]);
            this.state.answer = answer;
            this.state.history.push({ q, answered: !!answer.matched });
            this._log(answer.matched ? "coach_hit" : "coach_miss", answer.key || q.slice(0, 40));
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
        return markup(parts.join(""));
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
        // reading. There is only one kind that is not a curated intent: a
        // definition out of the column glossary. (health_learn also badges a
        // model-composed answer; Phase A ships no composer, so that badge
        // would be a promise about a path that does not exist.)
        const badge = a.source_kind === "column"
            ? `<span class="lrn-chip b">${ic("book-open")}${esc(T("columnAnswer"))}</span>`
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
        }
    }

    /* ONE language preference, shared with the Journey.
       Two independent toggles for one setting is a bug waiting to happen: the
       learner flips the Coach to Vietnamese, opens a lesson, and it is in
       English again. Both surfaces read and write the same localStorage key. */
    toggleLang() {
        RT.lang = RT.lang === "en" ? "vi" : "en";
        this.state.lang = RT.lang;
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
        return RT.lang === "en" ? "Tiếng Việt" : "English";
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
