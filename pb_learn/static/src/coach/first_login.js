/** @odoo-module **/
/* =============================================================================
   The real-tenant welcome card, and the launcher stack.

   Both used to belong to pb_coach's overlay, and both are chrome rather than
   content — which is why they live in their own
   file instead of growing the Coach.

   1. NO DEMO GREETING ANY MORE  (owner, 2026-10-12).
      This file used to open the Journey map on every demo sign-in, keyed to
      `login_date`. That pulled people off their own first screen: a demo user
      lands on Home (their `action_id`, set by pb_demo_portal), and Learn stays
      one press away on the rail. Nothing here navigates on sign-in now.

   2. COEXISTENCE, UNTIL pb_coach IS UNINSTALLED.
      The only part of the coexistence work still needed is the launcher
      offset below; the greeting that had to stand down for pb_coach's own
      hero tour is gone, so pb_coach's localStorage flags are no longer read.

   3. THE LAUNCHER STACK is the same coexistence question in CSS. Three controls
      share the bottom-right corner while pb_coach is installed and two once it
      is gone, so the offset is decided at runtime from whether the service
      exists, and written as a body class the stylesheet keys off. Both deploy
      states render correctly, which is the requirement — there is no moment
      where the corner is wrong.

   4. GREET A REAL TENANT ONCE, EVER  (LEARNOS Phase 3).
      A brand-new tenant admin is somebody who has just bought the product.
      Their first thirty seconds is a small centred card that OFFERS the
      welcome walkthrough and takes "Later" for an answer. It does not start
      anything by itself.

      `maybeWelcome` returns on the demo world and for any demo user, so a
      demo session never sees it.
   ========================================================================== */
import { user } from "@web/core/user";
import { session } from "@web/session";

import { T, esc, ic } from "../engine/runtime";

const DEMO_GROUP = "pb_demo.group_payobook_demo";

/* The real-tenant welcome, Phase 3. TWO keys, because they answer two
   different questions and one key cannot answer both:

     ANSWERED  permanent. Set the moment somebody presses either button, and
               never read again after that. "Later" is a real answer and this
               is what makes the card take it.
     LOGIN     once-per-login, keyed to `login_date`. It is what stops a page refresh re-asking somebody who has not
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

/* WHO THE CARD IS FOR (owner item, LEARN REFRESH 2, 2026-10-07). `sc_welcome`
   is the payroll tour — Pulse, a pay run, Approvals, the Formula Engine — and
   it was offered to everybody on a real tenant. Two people it is not for, both
   decided on the server by the same rules their left menu and first screen
   use, and handed over on the session:

     session.pb_hiring_not_payroll  (pb_hiring)    the Hiring board admits them
                                                  and Pay Run is not on their
                                                  menu → offer the Hiring
                                                  walkthrough instead.
     session.pb_employee_only       (pb_me_portal) neither payroll nor hiring →
                                                  no card: they land on
                                                  My Payobook, and there is no
                                                  tour of a screen that is theirs.

   Either key is simply absent when its module is not installed, which reads
   as "everybody else" — the payroll tour, as before. */
const HIRING_SCENARIO = "sc_hiring";

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
 *
 *  `hiring` swaps the body and the button for the Hiring walkthrough's.
 */
export function welcomeCardHTML(hiring = false) {
    return `<div class="lrn-welcome-h">
            <span class="lrn-welcome-ic">${ic("compass")}</span>
            <h2 class="lrn-welcome-t">${esc(T("welcomeTitle"))}</h2>
        </div>
        <p class="lrn-welcome-b">${esc(T(hiring ? "welcomeHiringBody" : "welcomeBody"))}</p>
        <div class="lrn-welcome-a">
            <button type="button" class="lrn-welcome-go" data-welcome="go">${ic("play")}<span>${esc(T(hiring ? "welcomeHiringGo" : "welcomeGo"))}</span></button>
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
function askWelcome(hiring) {
    return new Promise((resolve) => {
        const el = document.createElement("div");
        el.className = "lrn-welcome";
        el.setAttribute("role", "dialog");
        el.setAttribute("aria-modal", "false");
        el.innerHTML = welcomeCardHTML(hiring);

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
                // stopImmediatePropagation, not stopPropagation: every
                // Escape listener sits on document-capture, and a sibling on
                // the SAME node still runs after stopPropagation (proven live
                // on the hovercard during the Phase 4-6 deploy).
                ev.stopImmediatePropagation();
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
 *  already been offered on". Never throws: it runs inside the Coach's
 *  onMounted, and the Coach is on every screen.
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
        // Belt and braces, and it costs one cached call: a demo user on a
        // database that is not the demo world still never sees the card.
        if (await user.hasGroup(DEMO_GROUP)) {
            return false;
        }
        if (ls(WELCOME_ANSWERED)) {
            return false;
        }
        // Employee-only: no card at all (see HIRING_SCENARIO above).
        if (session.pb_employee_only) {
            return false;
        }
        const hiring = !!session.pb_hiring_not_payroll;

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

        const choice = await askWelcome(hiring);
        // Answered either way — the card is finished with this browser.
        setLs(WELCOME_ANSWERED, choice);
        if (choice === "go" && sc) {
            // The one door: the scenario service is what starts a walkthrough
            // everywhere else in this module too, so a Watch begun here is
            // the same run, logged the same way, as one begun from the Coach.
            await sc.begin(hiring ? HIRING_SCENARIO : WELCOME_SCENARIO, WELCOME_MODE);
        }
        return true;
    } catch {
        return false;
    }
}
