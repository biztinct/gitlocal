// Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
//
// Replica of the internal-anchor click interceptor in
// @web/core/browser/router (which hardcodes /odoo in both of its
// conditions and is registered as a module-scope listener, so it cannot be
// patched). When the app lives on the branded prefix, core's listener
// no-ops; this one takes over so clicks on backend links (chatter bodies,
// pasted internal links, legacy /odoo hrefs) stay SPA navigations instead
// of full page loads. Upgrade ritual: diff this against the core listener.
import { browser } from "@web/core/browser/browser";
import { router, routerBus } from "@web/core/browser/router";
import { BRAND_PREFIX, CORE_PREFIX, hasPrefix } from "@biz_deroute/js/deroute_router";

function isBackendTarget(pathname) {
    return (
        pathname === "/web" ||
        hasPrefix(pathname, CORE_PREFIX) ||
        hasPrefix(pathname, BRAND_PREFIX)
    );
}

browser.addEventListener("click", (ev) => {
    if (ev.defaultPrevented || ev.target.closest("[contenteditable]")) {
        return;
    }
    const a = ev.target.closest("a");
    const href = a?.getAttribute("href");
    if (!href || href.startsWith("#")) {
        return;
    }
    let url;
    try {
        url = new URL(a.href);
    } catch {
        return;
    }
    if (
        browser.location.host === url.host &&
        hasPrefix(browser.location.pathname, BRAND_PREFIX) &&
        isBackendTarget(url.pathname) &&
        a.target !== "_blank"
    ) {
        ev.preventDefault();
        const state = router.urlToState(url);
        // replace:true rebuilds the state from the URL (keeping only locked
        // keys like debug/lang), sync:true commits the branded URL and
        // router.current before the ROUTE_CHANGE tick — the action
        // service's own later push then compares equal and is a no-op.
        router.pushState(state, { replace: true, sync: true });
        if (url.hash) {
            browser.history.replaceState(
                browser.history.state,
                "",
                browser.location.pathname + browser.location.search + url.hash
            );
        }
        new Promise((res) => setTimeout(res, 0)).then(() => routerBus.trigger("ROUTE_CHANGE"));
    }
});
