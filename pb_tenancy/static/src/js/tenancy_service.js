/** @odoo-module **/
/**
 * The one place in the browser that knows what the platform has said.
 *
 * SEEDED FROM THE PAGE, NOT FROM A REQUEST. `session_info` already carries the
 * answer, so the banner is correct on the first paint and there is no flash of
 * a page without it. The poll below exists only for a tab that stays open.
 *
 * WHAT IT POLLS, AND WHY IT IS NOT FREE-RUNNING.
 *   * Only while the tab is VISIBLE. A laptop with forty background tabs must
 *     not be asking forty questions a minute about a message that changes twice
 *     a month.
 *   * Immediately when a hidden tab comes back and more than a minute has
 *     passed — that is the case that actually matters, somebody returning to a
 *     screen they left this morning.
 *   * Once a minute otherwise. The handover asked for the poll to run only
 *     while a notice was already showing, but that cannot satisfy the thing the
 *     phase is FOR: an open page has to grow a banner it did not have when it
 *     loaded (ledger F14). One small read a minute per open tab is the price.
 *
 * IT WRITES NOTHING. Two things are remembered, both in this browser only:
 * which notice this person has dismissed, and which release they were last told
 * about. Neither leaves the machine, and losing them costs one extra toast.
 */
import { registry } from "@web/core/registry";
import { reactive } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";
import { _t } from "@web/core/l10n/translation";

/** How often an open, visible tab asks. */
export const POLL_MS = 60000;

const LS_DISMISSED = "pb_tenancy.dismissed";
const LS_SEEN_RELEASE = "pb_tenancy.seen_release";

const EMPTY = {
    release: "", release_date: "", releases: [], notice: null,
    pushed_at: "", is_master: false,
    // FLEET P4. EMPTY MAPS MEAN EVERYTHING IS SWITCHED ON, and they are the
    // starting point on purpose — a page painted before the first answer
    // arrives must show the whole product, not none of it. `apply()` overwrites
    // the whole object from EMPTY on every read, so a key the server stops
    // sending goes back to "on" rather than lingering as a stale "off".
    features: {}, feature_mode: {}, feature_lock_text: {},
    features_known: false,
};

/** localStorage, but a private window is not an error. */
function lsGet(key) {
    try { return window.localStorage.getItem(key) || ""; } catch { return ""; }
}
function lsSet(key, value) {
    try { window.localStorage.setItem(key, value); } catch { /* private mode */ }
}

/**
 * A stable identity for a notice.
 *
 * The platform stamps every notice it sends with an `id`, and dismissal is
 * remembered against it — so clearing one message and sending another brings
 * the bar back for somebody who had hidden the first, which is the whole point
 * of a new message. A notice with no id (hand-edited, or from an older push)
 * falls back to its title so it is still dismissible.
 */
export function noticeKey(notice) {
    if (!notice) { return ""; }
    return String(notice.id || notice.title || "");
}

export const tenancyService = {
    dependencies: ["notification", "action"],

    start(env, { notification, action }) {
        const state = reactive({
            ...EMPTY,
            ...(session.pb_tenancy || {}),
            // Not from the server: this browser's own answer to "have I closed
            // this one?", recomputed whenever the notice changes.
            dismissed: lsGet(LS_DISMISSED),
        });

        let lastFetch = Date.now();
        let timer = null;

        function apply(data) {
            if (!data) { return; }
            Object.assign(state, EMPTY, data);
        }

        async function refresh() {
            lastFetch = Date.now();
            try {
                apply(await rpc("/pb_tenancy/state", {}, { silent: true }));
            } catch (e) {
                // A dropped connection is not news the user needs; the banner
                // simply keeps saying whatever it last knew. Logged, never
                // swallowed silently (W40).
                console.debug("pb_tenancy: could not refresh the platform state", e);
            }
        }

        function tick() {
            if (document.visibilityState === "visible") { refresh(); }
        }

        /** Hide this notice for this browser until a different one arrives. */
        function dismiss() {
            const key = noticeKey(state.notice);
            if (!key) { return; }
            state.dismissed = key;
            lsSet(LS_DISMISSED, key);
        }

        /** Is there a notice to draw right now? */
        function visibleNotice() {
            const n = state.notice;
            if (!n || !n.title) { return null; }
            return noticeKey(n) === state.dismissed ? null : n;
        }

        /**
         * "Payobook was updated to release 2026.09.03." — once, ever.
         *
         * Fired for a release this browser has not been told about, INCLUDING
         * the first one it ever sees. A first sighting is genuinely news to the
         * person reading it: they have just been moved onto a numbered release
         * and there is now a page saying what is in it. The cost of being wrong
         * is one toast; the cost of staying quiet is that nobody ever discovers
         * What's new.
         */
        function announceRelease() {
            const rel = state.release;
            if (!rel || lsGet(LS_SEEN_RELEASE) === rel) { return; }
            lsSet(LS_SEEN_RELEASE, rel);
            notification.add(
                _t("Payobook was updated to release %(name)s.", { name: rel }),
                {
                    type: "success",
                    // Long enough to read a sentence AND reach for the button;
                    // the default four seconds makes the link decorative.
                    autocloseDelay: 12000,
                    sticky: false,
                    buttons: [{
                        name: _t("See what's new"),
                        onClick: () => action.doAction({
                            type: "ir.actions.client",
                            tag: "pb_tenancy_whats_new",
                            target: "current",
                        }),
                    }],
                },
            );
        }

        if (session.pb_tenancy) {
            // After the first paint, never during it: a toast raised while the
            // web client is still assembling itself lands in a notification
            // container that does not exist yet.
            setTimeout(announceRelease, 1500);
        }

        document.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "visible"
                && Date.now() - lastFetch > POLL_MS) {
                refresh();
            }
        });
        timer = setInterval(tick, POLL_MS);
        // The service lives as long as the page does; the handle is kept only so
        // a test — or a future "pause polling" switch — has something to stop.
        return { state, refresh, dismiss, visibleNotice, stop: () => clearInterval(timer) };
    },
};

registry.category("services").add("pb_tenancy", tenancyService);
