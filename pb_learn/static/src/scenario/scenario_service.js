/** @odoo-module **/
/* =============================================================================
   The scenario state machine — LEARNOS Phase 1b.

   ONE AUTHORED STORY, THREE WAYS TO TAKE IT
   -----------------------------------------
   A scenario is a walkthrough of a real task. The steps, the anchors and the
   words are identical whichever way you take it; the only thing that changes is
   WHO PRESSES:

     watch  the engine drives the real screens. It may synthesise a click on an
            ordinary control and it can never synthesise one on a guarded step —
            not "does not", CANNOT: `scenario_overlay.js` has exactly one call
            to `.click()` and no code path reaches it with a guarded step.
     try    the learner drives the practice replica, inside the Journey. Every
            click there is safe by construction: there is no server on the other
            end of a replica, so a wrong click is a nudge and nothing else.
     do     the learner drives the REAL product. The engine attaches a one-shot
            listener and waits. On a guarded step it never presses and never
            times out into advancing either.

   WHY A SERVICE AND NOT A COMPONENT
   ---------------------------------
   Watch and Do navigate. The first step of `sc_payrun` opens the pay-run
   wizard, which unmounts whatever client action started it — the same problem
   the live capstone hit in Phase B, and the same answer: the STATE lives
   outside any component, and the surface that renders it is mounted in the web
   client shell where nothing unmounts it.

   Try is different and deliberately so: it runs inside the Journey over a
   replica the Journey draws, exactly where the practice missions run. Starting
   a Try from anywhere therefore means opening the Journey with a deep link, and
   `start()` below is the one place that decides which of the two it is.

   NOT PERSISTED. A page reload ends a scenario, which is the behaviour of the
   guided tours this replaces and is right for a walkthrough: the live capstone persists
   because it is a task with real records at the other end, and a scenario is a
   thing you are being shown.
   ========================================================================== */
import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

import { RT } from "../engine/runtime";
import { loadContent } from "../content/content_loader";

/* The namespace `learn.progress` keys a scenario under. Must match
   models/learn_progress.py SCENARIO_PREFIX, which is what refuses an unknown
   key server-side. */
const PROGRESS_PREFIX = "scenario:";

/** The steps of a scenario that are playable in ONE mode — LEARNOS Phase 5.
 *
 *  ONE RULE, THREE READERS, AND IT HAS TO BE ONE FUNCTION. The overlay plays
 *  Watch and Do, the Journey plays Try, and the Coach's `scenario:key#step`
 *  deep link resolves a step KEY to an index; if any of them counted the steps
 *  differently the index would mean two things and the deep link would open
 *  the wrong card. Exported rather than kept inside the service because the
 *  Journey reads scenarios out of its own bundle, not out of this service.
 *
 *  A step with no `modes` plays in every mode, which is what every step
 *  authored before Phase 5 means and what the generator emits for them. A step
 *  that narrows itself is how a walkthrough of the real Formula Studio can
 *  also be a Try over the six controls the replica actually draws, without
 *  becoming two scenarios that drift apart.
 */
export function playableSteps(scenario, mode) {
    const steps = (scenario && scenario.steps) || [];
    if (!mode) {
        return steps;
    }
    return steps.filter((st) => !st.modes || !st.modes.length
                                || st.modes.includes(mode));
}

export const scenarioService = {
    dependencies: ["action", "orm"],

    start(env, { action, orm }) {
        /* The whole of a running scenario. Read by the overlay (watch / do) and
           by the Journey (try), which is why it is one object and not two. */
        const state = reactive({
            active: false,     // a scenario is running on the REAL screens
            key: null,
            mode: "watch",     // "watch" | "do" — "try" never sets active
            index: 0,
            done: false,
            navigating: false,
            /* THE LANGUAGE, AS A REACTIVE VALUE, and it is not redundant with
               RT.lang. OWL re-renders a component when a reactive key it READ
               DURING RENDER changes; every visible string goes through
               T()/tx(), which read RT.lang — a plain module object OWL cannot
               observe. The Coach's toggle writes here as well, so flipping
               language while a walkthrough is running re-draws the card
               instead of leaving it in the other language until a reload.
               Exactly the bug the Phase D deploy round found in the drawer. */
            lang: RT.lang,
        });

        let scenarios = null;      // null = not loaded yet, [] = loaded, empty
        let loading = null;

        /** Fetched once, and only when something actually asks. The overlay is
         *  mounted on every screen for every user and almost none of them will
         *  ever start a scenario; the content plane is a shared memoised fetch,
         *  so in practice this costs nothing the Coach has not already paid. */
        async function load() {
            if (scenarios) {
                return scenarios;
            }
            if (!loading) {
                loading = loadContent().then((content) => {
                    scenarios = content.scenarios || [];
                    RT.chrome = content.chrome || RT.chrome;
                    return scenarios;
                }).catch(() => {
                    scenarios = [];
                    return scenarios;
                });
            }
            return loading;
        }

        function all() {
            return scenarios || [];
        }

        function get(key) {
            return all().find((s) => s.key === key) || null;
        }

        /** The steps of the RUNNING scenario, in the mode it is running in. */
        function steps(key, mode) {
            return playableSteps(get(key === undefined ? state.key : key),
                                 mode === undefined ? state.mode : mode);
        }

        function current() {
            return steps()[state.index] || null;
        }

        /** The scenarios offered on ONE screen.
         *
         *  `screenKey` is whatever the Coach's three-pass resolver decided the
         *  learner is standing on — the same `screens_runtime` matchers the
         *  1a bootstrap ships. A scenario declares the screens it is offered
         *  on rather than having them inferred from its steps, because two of
         *  the six live inside a wizard that has no screen of its own. */
        function forScreen(screenKey) {
            if (!screenKey) {
                return [];
            }
            return all().filter((s) => (s.screens || []).includes(screenKey));
        }

        // -------------------------------------------------------- navigation
        /** Open a real-product destination named by xml-id.
         *
         *  Awaited, and guarded: `doAction` is a promise, and a synchronous
         *  try/catch around it catches nothing (ledger, Phase C review). A
         *  navigation that fails leaves the step's anchor unresolvable, which
         *  the overlay already degrades to a centred card — so a broken nav is
         *  a worse explanation, never a broken screen. */
        async function navigate(ref) {
            if (!ref) {
                return;
            }
            state.navigating = true;
            try {
                await action.doAction(ref, { clearBreadcrumbs: true });
            } catch {
                // The scenario keeps going and says less than it wanted to.
            } finally {
                state.navigating = false;
            }
        }

        // ---------------------------------------------------------- lifecycle
        /** Start a scenario in one of its declared modes.
         *
         *  Returns false rather than throwing on anything it cannot honour: the
         *  callers are a Journey card, a Coach drawer button and a deep link
         *  out of an intent, and none of those may break the screen it is on
         *  because a key went stale between a cached answer and today. */
        async function begin(key, mode) {
            await load();
            const sc = get(key);
            if (!sc) {
                return false;
            }
            const wanted = (sc.modes || []).includes(mode) ? mode : (sc.modes || [])[0];
            if (!wanted) {
                return false;
            }
            if (wanted === "try") {
                // Try belongs to the Journey, over the replica. The deep link
                // is the handover, and it is the same mechanism PayAI's "Show
                // me" already uses — one door into that action, not two.
                try {
                    await action.doAction("pb_learn.action_learn_journey", {
                        additionalContext: { scenario: key, mode: "try" },
                    });
                } catch {
                    return false;
                }
                return true;
            }
            state.key = key;
            state.mode = wanted;
            state.index = 0;
            state.done = false;
            state.lang = RT.lang;
            state.active = true;
            logStart(key, wanted);
            const entry = sc.entry || {};
            if (entry.nav) {
                await navigate(entry.nav);
            }
            return true;
        }

        function goTo(index) {
            const sc = get(state.key);
            if (!sc || index < 0 || index >= steps().length) {
                return;
            }
            state.index = index;
            record(state.key, { state: "in_progress", step_index: index });
            log("scenario_step", `${state.key}:${state.mode}:${index}`);
        }

        function next() {
            const sc = get(state.key);
            if (!sc) {
                return;
            }
            if (state.index < steps().length - 1) {
                goTo(state.index + 1);
            } else {
                finish();
            }
        }

        function back() {
            if (state.index > 0) {
                goTo(state.index - 1);
            }
        }

        /** The end of a walkthrough is a CARD, not a disappearance.
         *
         *  Seventeen steps of Watch that end by the overlay vanishing reads as
         *  a crash, and a learner who wanted the last step again has nothing
         *  left to press. `active` therefore stays true with `done` set: the
         *  overlay swaps the spotlight for a centred closing card, and `stop()`
         *  is what actually tears it down. */
        function finish() {
            const key = state.key;
            const mode = state.mode;
            if (state.done) {
                return;
            }
            state.done = true;
            if (key) {
                record(key, { state: "done", completed_at: nowServer(), lang: RT.lang });
                log("scenario_complete", `${key}:${mode}`);
            }
        }

        /** Leaving is always allowed and costs nothing. A scenario is a way of
         *  being shown something; abandoning one is a legitimate answer. */
        function stop() {
            const key = state.key;
            const mode = state.mode;
            const index = state.index;
            const wasDone = state.done;
            state.active = false;
            state.done = false;
            state.key = null;
            state.index = 0;
            // Closing the closing card is not abandoning it. Logging both would
            // make every completed walkthrough also count as one somebody
            // walked out of, which is the signal these rows exist to carry.
            if (key && !wasDone) {
                log("scenario_abandon", `${key}:${mode}:${index}`);
            }
        }

        // ------------------------------------------------------- learner state
        /* ONE place writes progress for all three modes, including Try — which
           runs in the Journey and calls back in here rather than keeping its
           own copy. Two writers of one key is how a Try and a Watch of the same
           scenario end up disagreeing about whether it was finished. */
        function nowServer() {
            return new Date().toISOString().slice(0, 19).replace("T", " ");
        }

        async function record(key, vals) {
            try {
                await orm.call("learn.progress", "record",
                               [PROGRESS_PREFIX + key, vals]);
            } catch {
                // Losing a progress write must never interrupt a walkthrough.
            }
        }

        async function log(kind, detail) {
            try {
                await orm.call("learn.event", "log", [kind], {
                    detail: detail || null,
                    lang: RT.lang,
                });
            } catch {
                // Measurement must never break the thing it measures.
            }
        }

        function logStart(key, mode) {
            record(key, { state: "in_progress", step_index: 0, lang: RT.lang });
            log("scenario_start", `${key}:${mode}`);
        }

        return {
            state,
            load, all, get, steps, current, forScreen,
            begin, next, back, goTo, finish, stop,
            record, log, logStart, nowServer,
            PROGRESS_PREFIX,
        };
    },
};

registry.category("services").add("learn.scenario", scenarioService);
