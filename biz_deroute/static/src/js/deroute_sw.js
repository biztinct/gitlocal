// Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
//
// The stock backend service worker only exists to serve /odoo offline, back
// the (unused here) backend PWA install, and carry mail web-push. It is
// scoped to /odoo, which this deployment no longer serves, so skip
// registration and unregister workers left over from before the /bizapp
// migration. Deliberate trade-off: Discuss browser push notifications are
// disabled — re-enabling them requires a re-scoped worker (see README).
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

patch(WebClient.prototype, {
    registerServiceWorker() {
        // mail's _subscribePush/_unsubscribePush await this deferred; with
        // no registration they then bail out gracefully.
        this.serviceWorkerActivatedDeferred.resolve();
        const sw = navigator.serviceWorker;
        if (sw?.getRegistrations) {
            sw.getRegistrations()
                .then((registrations) => {
                    for (const reg of registrations) {
                        // Scope-filtered: never touch self-scoped PWAs that
                        // share the origin (e.g. /health_pwa/).
                        if (new URL(reg.scope).pathname.startsWith("/odoo")) {
                            reg.unregister();
                        }
                    }
                })
                .catch(() => {});
        }
    },
});
