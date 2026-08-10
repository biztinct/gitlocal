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
   ========================================================================== */
import { user } from "@web/core/user";

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

        // pb_coach got there first on this login — stand down, and record that
        // we consider this login greeted so we do not fire the moment the
        // hero tour is dismissed.
        const coachGreeted = !!ls(COACH_LOGIN_KEY) || ss(COACH_SESSION_KEY) === "1";

        let loginKey = "";
        try {
            const rows = await orm.read("res.users", [user.userId], ["login_date"]);
            loginKey = rows && rows[0] ? String(rows[0].login_date || "") : "";
        } catch {
            loginKey = "";
        }

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
