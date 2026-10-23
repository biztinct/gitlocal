/** @odoo-module **/
// Part of biz_theme — reusable Odoo 19 backend theme. License LGPL-3.
// =============================================================================
// First-open splash — the "First open" moment of the loading language.
// -----------------------------------------------------------------------------
// views/webclient_templates.xml renders #biz-splash into the web client's body
// with its own inline CSS, so the brand mark is rising while the web client
// mounts, the menus load and the first screen fetches its data (the head
// bundles are render-blocking, so nothing can paint before them anyway).
// This module decides when the splash leaves:
//
//   ready  = the first action is on screen (.o_action_manager has a child) or
//            the home menu is up; watched with a MutationObserver.
//   min    = the rise must finish before the fade: 1.9 s from the splash's own
//            first paint on the first open of this browser tab; 250 ms on later
//            reloads, where the inline script has already set .is-still.
//   cap    = 8 s hard cap, so a boot error can never hide behind the splash.
//
// Trap (health19 §5.262): the backend bundle is a parser-blocking <script> in
// <head>, so this module runs BEFORE <body> exists — wait for DOMContentLoaded.
// =============================================================================

const KEY = "biz_splash_seen";
const MIN_FIRST_MS = 1900;
const MIN_AGAIN_MS = 250;
const HARD_CAP_MS = 8000;
const FADE_MS = 600;

function isReady() {
    return !!(
        document.querySelector(".o_action_manager > *") ||
        document.querySelector(".o_home_menu")
    );
}

function dismiss(el) {
    if (el.dataset.out) {
        return;
    }
    el.dataset.out = "1";
    el.classList.add("is-out");
    setTimeout(() => el.remove(), FADE_MS);
}

function startSplash() {
    const el = document.getElementById("biz-splash");
    if (!el) {
        return;
    }
    try {
        sessionStorage.setItem(KEY, "1");
    } catch {
        // private mode / blocked storage: the splash simply plays every time
    }
    const still = el.classList.contains("is-still");
    const t0 = Number(el.dataset.t0) || 0;
    const min = still ? MIN_AGAIN_MS : MIN_FIRST_MS;

    const finish = () => {
        const shown = performance.now() - t0;
        setTimeout(() => dismiss(el), Math.max(0, min - shown));
    };

    if (isReady()) {
        finish();
        return;
    }
    const obs = new MutationObserver(() => {
        if (isReady()) {
            obs.disconnect();
            finish();
        }
    });
    obs.observe(document.body, { childList: true, subtree: true });
    setTimeout(() => {
        obs.disconnect();
        dismiss(el);
    }, HARD_CAP_MS);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startSplash, { once: true });
} else {
    startSplash();
}
