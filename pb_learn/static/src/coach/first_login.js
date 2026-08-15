/** @odoo-module **/
/* =============================================================================
   The demo world's first-login greeting, and the launcher stack.

   TWO JOBS, both of which used to belong to pb_coach's overlay, and both of
   which are chrome rather than content — which is why they live in their own
   file instead of growing the Coach.

   1. GREET A DEMO USER ONCE PER LOGIN.
      pb_coach auto-STARTED the hero_path spotlight on first login. Its
      successor deliberately does less: it opens the Journey MAP with a "Start
      here" pulse on LW and stops. The difference is the whole argument. An
      overlay that begins moving before you have read anything is the thing
      people learn to dismiss; a map that is open with one card pointed at is an
      invitation you can accept, ignore, or come back to — and every one of
      those is a legitimate answer on somebody's first thirty seconds in a
      product they are evaluating.

      Same mechanism as pb_coach's, deliberately: keyed to the user's
      `login_date`, so a logout→login re-greets and a page refresh does not
      nag, with a per-tab-session fallback when login_date is unreadable.

   2. COEXISTENCE, UNTIL pb_coach IS UNINSTALLED.
      Both modules are installed during the transition, and two greetings on one
      login is worse than either. So this checks pb_coach's OWN flags — the
      exact key names its overlay writes — and stands down if the hero tour has
      already greeted this login. It never writes pb_coach's flags; it only
      reads them.

   3. THE LAUNCHER STACK is the same coexistence question in CSS. Three controls
      share the bottom-right corner while pb_coach is installed and two once it
      is gone, so the offset is decided at runtime from whether the service
      exists, and written as a body class the stylesheet keys off. Both deploy
      states render correctly, which is the requirement — there is no moment
      where the corner is wrong.

   4. GREET A REAL TENANT ONCE, EVER  (LEARNOS Phase 3).
      The demo greeting above is for somebody evaluating a product. A brand-new
      tenant admin is somebody who has just bought one, and the two deserve
      different first thirty seconds: theirs is a small centred card that OFFERS
      the welcome walkthrough and takes "Later" for an answer. Same ruling as
      the demo greeting — it does not start anything by itself.

      The two are mutually exclusive by construction: `maybeGreet` returns
      unless the session is a demo one, `maybeWelcome` returns unless the
      database is NOT the demo world. Nobody can be shown both.
   ========================================================================== */
import { user } from "@web/core/user";

import { T, esc, ic } from "../engine/runtime";

/* pb_learn's own flags. Namespaced separately from pb_coach's on purpose: the
   two systems must be able to disagree about whether they have greeted, and
   sharing a key would make uninstalling pb_coach silently re-greet everybody. */
const LOGIN_KEY = "pbLearnLoginSeen";
const SESSION_KEY = "pbLearnWelcomed";

/* pb_coach's flags, READ ONLY. These are the literal names its overlay writes
   (coach_overlay.js `_get`/`_put`/`_sess` prefix "pb_coach_"). If they move,
   the worst case is a demo user who is greeted twice on one login while both
   modules are installed — not an error, and it disappears at uninstall. */
const COACH_LOGIN_KEY = "pb_coach_login_seen";
const COACH_SESSION_KEY = "pb_coach_welcomed";

const DEMO_GROUP = "pb_demo.group_payobook_demo";

/* The real-tenant welcome, Phase 3. TWO keys, because they answer two
   different questions and one key cannot answer both:

     ANSWERED  permanent. Set the moment somebody presses either button, and
               never read again after that. "Later" is a real answer and this
               is what makes the card take it.
     LOGIN     the once-per-login machinery the demo greeting already uses. It
               is what stops a page refresh re-asking somebody who has not
               answered yet, while still offering the card again tomorrow to
               somebody who closed the tab on it.

   Somebody who never answers therefore meets it once per login until they do,
   which is one card and two buttons — not a nag. */
const WELCOME_ANSWERED = "pbLearnWelcomeAnswered";
const WELCOME_LOGIN = "pbLearnWelcomeLogin";

/* The scenario the card offers, in the mode it offers it in. `watch` is the
   only honest mode for a card somebody has not asked for yet: the engine
   drives, the learner reads, and it stops at anything that writes. */
const WELCOME_SCENARIO = "sc_welcome";
const WELCOME_MODE = "watch";

/* Every storage read is wrapped: a browser with storage disabled must not be
   able to stop the Coach from mounting. */
function ls(key) {
    try {
        return window.localStorage.getItem(key) || "";
    } catch {
        return "";
    }
}
function setLs(key, value) {
    try {
        window.localStorage.setItem(key, value || "");
    } catch {
        /* ignore */
    }
}
function ss(key) {
    try {
        return window.sessionStorage.getItem(key) || "";
    } catch {
        return "";
    }
}
function setSs(key, value) {
    try {
        window.sessionStorage.setItem(key, value || "");
    } catch {
        /* ignore */
    }
}

/** Is pb_coach installed in THIS session? The service is the honest signal:
 *  a module can be present on disk and uninstalled in the database. */
export function coachPresent(env) {
    try {
        return !!(env && env.services && env.services.pb_coach);
    } catch {
        return false;
    }
}

/** Body class the stylesheet keys the launcher offset off. Set once, on mount.
 *  With pb_coach absent the stack is PayAI (24px) + this launcher; with it
 *  present there is a third control at 92px and this one stays above it. */
export function markLauncherStack(env) {
    try {
        document.body.classList.toggle("pb-coach-absent", !coachPresent(env));
    } catch {
        /* ignore */
    }
}

/* ===========================================================================
   THE REAL-TENANT WELCOME CARD
   ===========================================================================*/

/** The card's markup. Exported so it can be asserted on without a DOM.
 *
 *  Every string is `esc(T(...))`: these are chrome keys generated from the
 *  authoring source, so they arrive as text and are inserted as text. There
 *  is no raw-insertion position in here, which is why there is no `gtx` —
 *  the one raw wrapper in this module is for authored BODIES that carry
 *  their own <b>, and a four-line card has none.
 */
export function welcomeCardHTML() {
    return `<div class="lrn-welcome-h">
            <span class="lrn-welcome-ic">${ic("compass")}</span>
            <h2 class="lrn-welcome-t">${esc(T("welcomeTitle"))}</h2>
        </div>
        <p class="lrn-welcome-b">${esc(T("welcomeBody"))}</p>
        <div class="lrn-welcome-a">
            <button type="button" class="lrn-welcome-go" data-welcome="go">${ic("play")}<span>${esc(T("welcomeGo"))}</span></button>
            <button type="button" class="lrn-welcome-later" data-welcome="later">${esc(T("welcomeLater"))}</button>
        </div>`;
}

/** Draw the card and resolve with the answer: "go" or "later".
 *
 *  ONE ELEMENT, ONE LISTENER, and it is torn down whichever way the answer
 *  comes — a button or Escape. No backdrop and no focus trap:
 *  this is the Coach's visual language, and the screen behind an offer has to
 *  stay readable while somebody decides whether they have two minutes.
 *
 *  Escape counts as "later", because a card that cannot be dismissed with the
 *  key everybody reaches for is a modal pretending not to be one.
 */
function askWelcome() {
    return new Promise((resolve) => {
        const el = document.createElement("div");
        el.className = "lrn-welcome";
        el.setAttribute("role", "dialog");
        el.setAttribute("aria-modal", "false");
        el.innerHTML = welcomeCardHTML();

        let done = false;
        /* KEYDOWN ON `document`, NEVER `window`. Odoo's hotkey service stops
           propagation before the window-bubble phase, so a window listener is
           silently dead — the standing ledger rule, and the reason this card
           can be dismissed at all. */
        const onKey = (ev) => {
            if (ev.key === "Escape") {
                // A transient layer that closes on a key SWALLOWS that key —
                // the learner meant "close the card", not "and also exit
                // whatever is behind it".
                ev.stopPropagation();
                ev.preventDefault();
                answer("later");
            }
        };
        const onClick = (ev) => {
            const btn = ev.target.closest("[data-welcome]");
            if (btn) {
                answer(btn.getAttribute("data-welcome"));
            }
        };
        function answer(choice) {
            if (done) {
                return;
            }
            done = true;
            document.removeEventListener("keydown", onKey, true);
            el.removeEventListener("click", onClick);
            el.remove();
            resolve(choice === "go" ? "go" : "later");
        }

        el.addEventListener("click", onClick);
        document.addEventListener("keydown", onKey, true);
        document.body.appendChild(el);
        const go = el.querySelector(".lrn-welcome-go");
        if (go) {
            try {
                go.focus();
            } catch {
                /* ignore */
            }
        }
    });
}

/** Offer the welcome walkthrough, once, to a brand-new tenant admin.
 *
 *  Returns false in every case that is not "a real (non-demo) database, a
 *  session that has not answered this card, and a login this card has not
 *  already been offered on". Never throws: like the demo greeting it runs
 *  inside the Coach's onMounted, and the Coach is on every screen.
 *
 *  `demoWorld` comes from the SERVER — `learn.runtime.bootstrap`, which asks
 *  the same question `learn.live` asks of a capstone. It is deliberately a
 *  property of the DATABASE rather than of the user: an administrator poking
 *  around the demo world is not a new tenant, and a user-level probe would
 *  have shown them a card welcoming them to a product they are running.
 */
export async function maybeWelcome(env, orm, sc, demoWorld) {
    try {
        if (demoWorld) {
            return false;
        }
        // Belt and braces, and it costs one cached call: the group is how the
        // demo greeting decides, so asking it here too makes the two branches
        // provably disjoint rather than disjoint-by-agreement.
        if (await user.hasGroup(DEMO_GROUP)) {
            return false;
        }
        if (ls(WELCOME_ANSWERED)) {
            return false;
        }

        let loginKey = "";
        try {
            const rows = await orm.read("res.users", [user.userId], ["login_date"]);
            loginKey = rows && rows[0] ? String(rows[0].login_date || "") : "";
        } catch {
            loginKey = "";
        }
        const seen = loginKey ? ls(WELCOME_LOGIN) : (ss(WELCOME_LOGIN) === "1" ? "s" : "");
        const fresh = (loginKey && loginKey !== seen) || (!loginKey && seen !== "s");
        if (!fresh) {
            return false;
        }
        if (loginKey) {
            setLs(WELCOME_LOGIN, loginKey);
        } else {
            setSs(WELCOME_LOGIN, "1");
        }

        const choice = await askWelcome();
        // Answered either way — the card is finished with this browser.
        setLs(WELCOME_ANSWERED, choice);
        if (choice === "go" && sc) {
            // The one door: the scenario service is what starts a walkthrough
            // everywhere else in this module too, so a Watch begun here is
            // the same run, logged the same way, as one begun from the Coach.
            await sc.begin(WELCOME_SCENARIO, WELCOME_MODE);
        }
        return true;
    } catch {
        return false;
    }
}

/** Open the Journey once per login for demo users, with LW pointed at.
 *
 *  Returns quietly in every case that is not "a demo user who has not been
 *  greeted on this login and whom pb_coach has not already greeted". Never
 *  throws: it runs inside the Coach's onMounted, and the Coach is on every
 *  screen in the product.
 */
export async function maybeGreet(env, orm, action) {
    try {
        const isDemo = await user.hasGroup(DEMO_GROUP);
        if (!isDemo) {
            return false;
        }

        let loginKey = "";
        try {
            const rows = await orm.read("res.users", [user.userId], ["login_date"]);
            loginKey = rows && rows[0] ? String(rows[0].login_date || "") : "";
        } catch {
            loginKey = "";
        }

        // pb_coach got there first ON THIS LOGIN — stand down, and record that
        // we consider this login greeted so we do not fire the moment the hero
        // tour is dismissed.
        //
        // THREE conditions, and the last two are the fix for a bug that would
        // only have appeared after the uninstall. `pb_coach_login_seen` is a
        // localStorage string that SURVIVES pb_coach being removed: a truthiness
        // test on it would have suppressed this greeting forever, on every
        // browser profile that ever saw the hero tour, with nothing to point at.
        // So: pb_coach has to still be INSTALLED (the service), and its flag has
        // to name THIS login rather than some login last March. The
        // session-storage flag needs no date — sessionStorage dies with the tab.
        const coachGreeted = coachPresent(env)
            && ((!!loginKey && ls(COACH_LOGIN_KEY) === loginKey)
                || ss(COACH_SESSION_KEY) === "1");

        if (coachGreeted) {
            // Match pb_coach's own bookkeeping so this login counts as done.
            if (loginKey) {
                setLs(LOGIN_KEY, loginKey);
            } else {
                setSs(SESSION_KEY, "1");
            }
            return false;
        }

        const seen = loginKey ? ls(LOGIN_KEY) : (ss(SESSION_KEY) === "1" ? "s" : "");
        const fresh = (loginKey && loginKey !== seen) || (!loginKey && seen !== "s");
        if (!fresh) {
            return false;
        }
        if (loginKey) {
            setLs(LOGIN_KEY, loginKey);
        } else {
            setSs(SESSION_KEY, "1");
        }

        // The map, with a pulse. NOT a lesson: `suggest` points, `lesson`
        // opens, and a greeting has no business deciding that somebody has
        // eight minutes right now.
        await action.doAction("pb_learn.action_learn_journey", {
            additionalContext: { suggest: "LW" },
        });
        return true;
    } catch {
        // A greeting that breaks the product it is greeting you into is worse
        // than no greeting.
        return false;
    }
}
