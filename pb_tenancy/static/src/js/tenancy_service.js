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
// FLEET P5. The trial countdown and the near-limit warning are closed for the
// DAY, not for ever: they are counting down, so tomorrow's is new information.
const LS_STANDING_DAY = "pb_tenancy.standing_day";

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
    // The three maps above, as ONE string that changes only when an answer
    // changes. Every screen that has to repaint when a switch is flipped
    // watches THIS and reads the maps normally — because the maps are replaced
    // with fresh objects on every read, and a screen watching one of them
    // would repaint once a minute for ever, whether or not anything had moved.
    features_sig: "",
    // FLEET P5. Where this company stands: are they let in, are they on a
    // trial, how close are they to their plan's employee limit. Every one of
    // these fails OPEN — an empty answer means open, no trial and no limit.
    access: "open", access_text: "", plan_name: "",
    trial: { phase: "none", days_left: 0, ends: "", text: "" },
    trial_ends: "",
    seat: { verdict: "ok", limit: 0, count: 0, left: -1, pct: 0 },
    seat_limit: 0, seat_count: 0,
    // One string that moves only when one of the answers above moves. Screens
    // watch THIS rather than the objects, which are rebuilt on every read
    // (the same trick features_sig plays — ledger F47).
    standing_sig: "",
};

/** The three maps as one comparable string. Order is fixed by the caller. */
function featureSig(data) {
    const d = data || {};
    return JSON.stringify([d.features || {}, d.feature_mode || {},
                           d.feature_lock_text || {}]);
}

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
            features_sig: featureSig(session.pb_tenancy),
            // Not from the server: this browser's own answer to "have I closed
            // this one?", recomputed whenever the notice changes.
            dismissed: lsGet(LS_DISMISSED),
            standing_dismissed: lsGet(LS_STANDING_DAY),
        });

        let lastFetch = Date.now();
        let timer = null;

        function apply(data) {
            if (!data) { return; }
            // FLEET P4. The left menu is drawn by the SERVER, so a switch
            // flipped on the platform cannot reach it the way the tiles are
            // reached — a component watching this state repaints itself, but
            // the rail is a list of rows that were fetched once. When the
            // answer moves, the rail is asked again, on the seam it already
            // has. Nothing happens on the first read: the page was painted
            // from the same answer a moment ago.
            const sig = featureSig(data);
            const moved = !!state.features_sig && state.features_sig !== sig;
            // FLEET P5. THE DOOR CLOSES ON A TAB THAT IS ALREADY OPEN. The
            // server redirects a fresh page load, but somebody who was already
            // working when the platform paused them would carry on in the tab
            // they had until they navigated. The poll is what finds out, and
            // the poll is exempt from the door precisely so it can.
            const wasOpen = state.access !== "suspended";
            Object.assign(state, EMPTY, data, { features_sig: sig });
            if (moved) { env.bus.trigger("PB_SIDEBAR:RELOAD"); }
            if (wasOpen && state.access === "suspended") {
                window.location.href = "/pb_tenancy/paused";
            }
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

        /**
         * Hide the standing bar for the REST OF TODAY.
         *
         * Not for ever: "your trial ends in three days" becomes "in two days"
         * tomorrow, and that is news. Not for the session either: somebody who
         * closed it at nine should not meet it again at ten.
         */
        function dismissStanding() {
            const day = new Date().toISOString().slice(0, 10);
            state.standing_dismissed = day;
            lsSet(LS_STANDING_DAY, day);
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
        return { state, refresh, dismiss, dismissStanding, visibleNotice,
                 stop: () => clearInterval(timer) };
    },
};

registry.category("services").add("pb_tenancy", tenancyService);
