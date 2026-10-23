import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

/**
 * TIERS T3b — clock in / out from My Payobook.
 *
 * Both pages work without this file: the round button (Clock page) and the
 * home card's button are plain form POSTs, and the server draws the elapsed
 * time as it was when the page was made. This file adds what a good clock app
 * does, and holds no words (every word is in the QWeb templates):
 *
 *  - the live timer: the hours and minutes count up from the clock-in
 *    (`data-since-ms`), corrected for the gap between this device's clock and
 *    the server's (`data-server-now-ms`), and today's total with it;
 *  - the press: the ring starts closing the moment the button is pressed, and
 *    a second press is ignored (the server also ignores a second punch inside
 *    a minute);
 *  - the location: only when the company keeps it (`data-tracking="1"`), the
 *    browser is asked ONCE; the punch never waits more than 4 seconds and goes
 *    through without coordinates when the person says no;
 *  - the re-sync: back on a tab after a while, the state is asked again and
 *    the page reloads only if it changed (clocked out on another device).
 */
const GEO_TIMEOUT_MS = 4000;
const RESYNC_AFTER_MS = 60 * 1000;

function splitMinutes(total) {
    const minutes = Math.max(0, Math.floor(total));
    return [Math.floor(minutes / 60), minutes % 60];
}

export class PbEwClockLive extends Interaction {
    static selector = "[data-pbew-live]";

    setup() {
        const data = this.el.dataset;
        this.state = data.state || "out";
        this.sinceMs = Number(data.sinceMs) || 0;
        this.todayClosed = Number(data.todayClosed) || 0;
        this.sinceToday = data.sinceToday === "1";
        // server time minus device time, so a phone whose clock is wrong
        // still counts from the real clock-in
        const serverNow = Number(data.serverNowMs) || 0;
        this.skew = serverNow ? serverNow - Date.now() : 0;
        this.hiddenAt = 0;
    }

    start() {
        if (this.state === "in" && this.sinceMs) {
            this.tick();
            const every = window.setInterval(() => this.tick(), 15000);
            this.registerCleanup(() => window.clearInterval(every));
        }
        this.addListener(document, "visibilitychange", this.onVisibility);
    }

    elapsedMinutes() {
        return (Date.now() + this.skew - this.sinceMs) / 60000;
    }

    paint(prefix, total) {
        const [h, m] = splitMinutes(total);
        const hEl = this.el.querySelector(`[data-${prefix}-h]`);
        const mEl = this.el.querySelector(`[data-${prefix}-m]`);
        const wrap = this.el.querySelector(`[data-${prefix}-hwrap]`);
        if (hEl) {
            hEl.textContent = String(h);
        }
        if (mEl) {
            mEl.textContent = String(m);
        }
        if (wrap) {
            wrap.classList.toggle("d-none", h === 0);
        }
    }

    tick() {
        const live = this.elapsedMinutes();
        this.paint("pbew", live);
        if (this.sinceToday) {
            this.paint("pbew-today", this.todayClosed + live);
        }
    }

    onVisibility() {
        if (document.visibilityState === "hidden") {
            this.hiddenAt = Date.now();
            return;
        }
        if (this.state === "in" && this.sinceMs) {
            this.tick();
        }
        if (!this.hiddenAt || Date.now() - this.hiddenAt < RESYNC_AFTER_MS) {
            return;
        }
        this.hiddenAt = 0;
        this.waitFor(rpc("/my/work/clock/state", {})).then((res) => {
            if (res && res.state && res.state !== this.state) {
                window.location.reload();
            }
        }).catch(() => {});
    }
}

export class PbEwClockForm extends Interaction {
    static selector = "form[data-pbew-clock-form]";
    dynamicContent = {
        _root: { "t-on-submit": this.onSubmit },
    };

    setup() {
        this.sent = false;
    }

    start() {
        // the one-off `done` key is dropped from the address bar once shown,
        // so a reload does not say "You are clocked in" again
        const url = new URL(window.location.href);
        if (url.searchParams.has("done")) {
            url.searchParams.delete("done");
            window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
        }
    }

    field(name) {
        return this.el.querySelector(`input[name="${name}"]`);
    }

    onSubmit(ev) {
        if (this.sent) {
            ev.preventDefault();
            return;
        }
        const nonce = this.field("nonce");
        if (nonce && !nonce.value) {
            nonce.value = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
        }
        const button = this.el.querySelector("button[type=submit]");
        if (button) {
            button.classList.add("is-pressing");
        }
        const wantsPlace = this.el.dataset.tracking === "1" && "geolocation" in navigator;
        const lat = this.field("lat");
        if (!wantsPlace || !lat || lat.value) {
            this.sent = true;
            return;
        }
        // ask for the place once, never longer than GEO_TIMEOUT_MS, and send
        // either way
        ev.preventDefault();
        this.sent = true;
        let done = false;
        const send = () => {
            if (done) {
                return;
            }
            done = true;
            this.el.submit();
        };
        const timer = window.setTimeout(send, GEO_TIMEOUT_MS + 250);
        try {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    window.clearTimeout(timer);
                    lat.value = String(pos.coords.latitude);
                    const lng = this.field("lng");
                    const acc = this.field("accuracy");
                    if (lng) {
                        lng.value = String(pos.coords.longitude);
                    }
                    if (acc) {
                        acc.value = String(Math.round(pos.coords.accuracy || 0));
                    }
                    send();
                },
                () => {
                    window.clearTimeout(timer);
                    send();
                },
                { enableHighAccuracy: false, timeout: GEO_TIMEOUT_MS, maximumAge: 120000 }
            );
        } catch {
            window.clearTimeout(timer);
            send();
        }
    }
}

registry.category("public.interactions").add("pb_ess_workforce.clock_live", PbEwClockLive);
registry.category("public.interactions").add("pb_ess_workforce.clock_form", PbEwClockForm);
