/** @odoo-module **/
/**
 * FLEET P6 — the bar that says which company you are actually in.
 *
 * THE MISTAKE THIS EXISTS TO PREVENT is not a security one. It is somebody at
 * Payobook opening a customer's database to look at one pay run, being called
 * away, coming back an hour later and editing what they believe is their own
 * demo. So the bar is loud, it is rose (the one colour the product reserves for
 * "be careful"), it names the company in full, and it cannot be dismissed —
 * there is a Leave button instead, which is the only honest way to make it go
 * away.
 *
 * IT IS ONLY EVER DRAWN FOR ONE ACCOUNT. `session_info` carries
 * `pb_support_session` for the session that came through the support door and
 * for nobody else — the key is ABSENT for every customer's own people, so
 * nothing on their page has to decide anything and nothing is fetched.
 *
 * AND IT IS THE THING THAT KEEPS THE TRAIL HONEST. Moving between screens in
 * this product changes the address without asking the server for a page, so the
 * server can see almost none of it. The bar can: it watches its own address and
 * reports each new screen, by name, to the customer's own record. The person
 * being recorded is looking at the bar doing it.
 */
import { Component, onWillUnmount, useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";
import { ic } from "@pb_import_kit/js/import_icons";
import { _t } from "@web/core/l10n/translation";

/** How often the clock is read and the address is compared. */
const TICK_MS = 1000;
/** The last stretch, when the bar changes its tone and pulses once. */
export const FINAL_SECONDS = 5 * 60;

/**
 * "1h 58m left", "4m 20s left", "any moment now". PURE.
 *
 * Seconds appear only in the last five minutes: a countdown ticking through
 * every second of two hours is a distraction, and a countdown with no seconds
 * in the last minute is a countdown nobody trusts.
 */
export function countdownText(seconds) {
    const s = Math.max(0, Math.floor(Number(seconds) || 0));
    if (s <= 0) { return _t("any moment now"); }
    if (s < FINAL_SECONDS) {
        const m = Math.floor(s / 60);
        const rest = s % 60;
        return _t("%(m)sm %(s)ss left", { m, s: String(rest).padStart(2, "0") });
    }
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (h) { return _t("%(h)sh %(m)sm left", { h, m }); }
    return _t("%(m)sm left", { m });
}

/** "16:02" in the reader's own clock, from the server's UTC stamp. */
export function endsAtText(stamp) {
    if (!stamp) { return ""; }
    const d = new Date(`${String(stamp).replace(" ", "T")}Z`);
    if (isNaN(d.getTime())) { return ""; }
    try {
        return d.toLocaleTimeString(undefined,
            { hour: "2-digit", minute: "2-digit" });
    } catch {
        return String(stamp).slice(11, 16);
    }
}

export class PbTenancySupportBar extends Component {
    static template = "pb_tenancy.SupportBar";
    static props = {};

    setup() {
        this.sess = session.pb_support_session || null;
        this.state = useState({ left: this._secondsLeft(), pulsed: false,
                                leaving: false });
        this._path = "";
        this._title = "";
        if (this.sess) {
            this._timer = setInterval(() => this.tick(), TICK_MS);
            // The first screen, reported straight away: the landing page is a
            // screen somebody opened and belongs in the trail like any other.
            this.report();
        }
        onWillUnmount(() => {
            if (this._timer) { clearInterval(this._timer); }
        });
    }

    ic(name, size = 15) { return ic(name, size); }

    _secondsLeft() {
        if (!this.sess || !this.sess.ends_at) { return 0; }
        const end = new Date(`${String(this.sess.ends_at).replace(" ", "T")}Z`);
        if (isNaN(end.getTime())) { return 0; }
        return Math.round((end.getTime() - Date.now()) / 1000);
    }

    tick() {
        this.state.left = this._secondsLeft();
        if (this.state.left <= FINAL_SECONDS && !this.state.pulsed) {
            // ONCE. A bar that pulses for the last five minutes is a bar people
            // stop seeing; one pulse is a thing that happened.
            this.state.pulsed = true;
        }
        this.report();
    }

    /**
     * Tell the customer's own record which screen this is, when it changes.
     *
     * THE TITLE IS WATCHED AS WELL AS THE ADDRESS, and that is not fussiness.
     * The address changes the instant somebody clicks; the NAME of the screen
     * arrives a moment later, when the page has drawn itself. Reporting only on
     * the address left the customer's trail reading "Payobook" against every
     * line, which is a record of nothing.
     */
    report() {
        const here = window.location.pathname + window.location.search;
        const title = document.title || "";
        if (here === this._path && title === this._title) { return; }
        this._path = here;
        this._title = title;
        rpc("/pb_tenancy/support/seen", { path: here, title }, { silent: true })
            .catch((e) => console.debug("pb_tenancy: screen not recorded", e));
    }

    get company() { return (this.sess && this.sess.company) || "this company"; }

    get endsAt() { return endsAtText(this.sess && this.sess.ends_at); }

    get countdown() { return countdownText(this.state.left); }

    get closing() { return this.state.left <= FINAL_SECONDS; }

    /** A CLICK handler. Ends the session on the customer's side, then signs out. */
    async leave() {
        if (this.state.leaving) { return; }
        this.state.leaving = true;
        let next = "/pb_tenancy/support/gone";
        try {
            const r = await rpc("/pb_tenancy/support/leave", {});
            if (r && r.next) { next = r.next; }
        } catch (e) {
            console.error("pb_tenancy: could not close the support session", e);
        }
        window.location.href = next;
    }
}
