/** @odoo-module **/
/**
 * Sign out when idle (WDGAP QF5 B2) — one file, in the web client AND on the
 * My Payobook (portal) pages.
 *
 * Activity is what the PERSON does: pointer, keyboard, touch. Its last moment
 * is kept in localStorage, so every tab of this site shares it (written at most
 * every 15 s). While the person is active the server is told at most once a
 * minute (POST /web/session/alive) — the only call that keeps the server's own
 * clock going (models/idle_rule.py). When every tab has been idle for the
 * limit, a calm one-minute warning shows; then the page signs out and comes
 * back to the same screen after the next sign-in.
 *
 * The limit comes from the session info (`pb_idle_minutes`). Absent or 0 →
 * this service does nothing at all: no listener, no timer.
 */
import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

const LAST_KEY = "pb_idle_last";
const ALIVE_KEY = "pb_idle_alive";
const OUT_KEY = "pb_idle_out";        // "<time>:<tab>" — one tab signs out
const OUT_CLAIM = 2 * 60 * 1000;      // a hidden tab's timer can lag a minute
const OUT_SETTLE = 400;               // two tabs at the same second: last write wins
const FOLLOW_AFTER = 2000;
const RECORD_EVERY = 15 * 1000;
const ALIVE_EVERY = 60 * 1000;
const WARN_FOR = 60 * 1000;
const TICK = 1000;
const EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart"];
const CLOCK = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';

function readMs(key) {
    try {
        return Number(window.localStorage.getItem(key)) || 0;
    } catch {
        return 0;
    }
}

function writeMs(key, value) {
    try {
        window.localStorage.setItem(key, String(value));
    } catch {
        // private window or blocked storage: this tab still counts on its own
    }
}

function readText(key) {
    try {
        return window.localStorage.getItem(key) || "";
    } catch {
        return "";
    }
}

export const idleWatchService = {
    start() {
        const minutes = Number(session.pb_idle_minutes) || 0;
        if (!minutes) {
            return;
        }
        const limit = minutes * 60 * 1000;
        let ownLast = Date.now();        // this tab's own idea, if storage fails
        let warning = null;              // { el, text }
        let leaving = false;

        const lastActivity = () => Math.max(readMs(LAST_KEY), ownLast);

        const tellServer = (force) => {
            const now = Date.now();
            if (!force && now - readMs(ALIVE_KEY) < ALIVE_EVERY) {
                return;
            }
            writeMs(ALIVE_KEY, now);
            rpc("/web/session/alive", {}, { silent: true }).catch(() => {});
        };

        const recordActivity = (force) => {
            const now = Date.now();
            if (force || now - ownLast >= RECORD_EVERY) {
                ownLast = now;
                writeMs(LAST_KEY, now);
            }
            tellServer(force);
        };

        const hideWarning = () => {
            if (warning) {
                warning.el.remove();
                warning = null;
            }
        };

        const showWarning = (msLeft) => {
            const seconds = Math.max(1, Math.ceil(msLeft / 1000));
            if (!warning) {
                const el = document.createElement("div");
                el.className = "pbva-idle";
                el.setAttribute("role", "alertdialog");
                el.setAttribute("aria-live", "assertive");
                const icon = document.createElement("span");
                icon.className = "pbva-idle-ic";
                icon.innerHTML = CLOCK;
                const text = document.createElement("span");
                text.className = "pbva-idle-tx";
                const stay = document.createElement("button");
                stay.type = "button";
                stay.className = "pbva-idle-btn";
                stay.textContent = _t("Stay signed in");
                stay.addEventListener("click", () => {
                    recordActivity(true);
                    hideWarning();
                });
                el.append(icon, text, stay);
                document.body.appendChild(el);
                warning = { el, text };
            }
            warning.text.textContent = seconds === 1
                ? _t("You will be signed out in 1 second.")
                : _t("You will be signed out in %s seconds.", seconds);
        };

        const signOut = () => {
            if (leaving) {
                return;
            }
            leaving = true;
            // ONE tab signs the browser out. Signing out twice renews the
            // session twice, and a sign-in page another tab already opened
            // would then refuse its own form. The others reopen their page a
            // moment later, which lands them on the sign-in page by itself.
            const here = window.location.pathname + window.location.search + window.location.hash;
            const out = () => window.location.assign(
                "/web/session/logout?redirect=" + encodeURIComponent(here));
            const follow = () => window.setTimeout(() => window.location.reload(), FOLLOW_AFTER);
            const now = Date.now();
            const probe = `probe:${now}`;
            writeMs(OUT_KEY + "_probe", probe);
            if (readText(OUT_KEY + "_probe") !== probe) {
                out();                  // no shared storage: this tab is on its own
                return;
            }
            const claimed = Number(readText(OUT_KEY).split(":")[0]) || 0;
            if (now - claimed < OUT_CLAIM) {
                follow();
                return;
            }
            const mine = `${now}:${Math.random().toString(36).slice(2)}`;
            writeMs(OUT_KEY, mine);
            window.setTimeout(() => {
                if (readText(OUT_KEY) === mine) {
                    out();
                } else {
                    follow();
                }
            }, OUT_SETTLE);
        };

        const onActivity = () => {
            // While the warning shows, only "Stay signed in" keeps the session:
            // a pointer brushing past the screen should not.
            if (!warning) {
                recordActivity(false);
            }
        };

        const tick = () => {
            const idle = Date.now() - lastActivity();
            if (idle >= limit + WARN_FOR) {
                signOut();
            } else if (idle >= limit) {
                showWarning(limit + WARN_FOR - idle);
            } else {
                hideWarning();              // activity in another tab
            }
        };

        // Opening the page is something the person did (the server stamped
        // the page itself, so no call is needed here).
        writeMs(LAST_KEY, ownLast);
        for (const name of EVENTS) {
            window.addEventListener(name, onActivity, { capture: true, passive: true });
        }
        window.setInterval(tick, TICK);
    },
};

registry.category("services").add("pb_idle_watch", idleWatchService);
