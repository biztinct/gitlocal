// Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
//
// Rebrands the SPA router's URL prefix at the seam core marks as patchable
// ("state <-> url conversions can be patched if needed in a custom
// webclient" — @web/core/browser/router). Internally the router keeps
// thinking in /odoo; only the serialized URLs are branded, so every state
// comparison, actionStack merge and popstate restore stays byte-identical
// to stock behavior.
import { router, startRouter } from "@web/core/browser/router";

export const CORE_PREFIX = "/odoo";
export const BRAND_PREFIX = "/bizapp";

export function hasPrefix(pathname, prefix) {
    return pathname === prefix || pathname.startsWith(prefix + "/");
}

function swapPrefix(url, from, to) {
    if (url === from || url.startsWith(from + "/") || url.startsWith(from + "?") || url.startsWith(from + "#")) {
        return to + url.slice(from.length);
    }
    return url;
}

const coreStateToUrl = router.stateToUrl;
const coreUrlToState = router.urlToState;

router.stateToUrl = function (state) {
    return swapPrefix(coreStateToUrl.call(this, state), CORE_PREFIX, BRAND_PREFIX);
};

router.urlToState = function (urlObj) {
    const translated = new URL(urlObj.href);
    if (hasPrefix(translated.pathname, BRAND_PREFIX)) {
        translated.pathname = CORE_PREFIX + translated.pathname.slice(BRAND_PREFIX.length);
    }
    const hrefBefore = translated.href;
    const state = coreUrlToState.call(this, translated);
    if (translated.href !== hrefBefore) {
        // Core mutates urlObj.href for legacy /web#hash and stray
        // /scoped_app URLs. It rebuilds the href through router.stateToUrl
        // (already branded above), so propagate it verbatim.
        urlObj.href = translated.href;
    }
    return state;
};

// Core ran startRouter() at module load, before these patches existed, so
// the initial state was parsed with the branded prefix unrecognized.
// Re-derive it now; services only read router.current after the bundle has
// fully evaluated, so this runs early enough.
startRouter();
