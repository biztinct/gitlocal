/* Payobook geo-tracking service worker — app-shell caching only.
 * Cache-first for the static shell bundle, network-first for JSON/RPC.
 * NO Background Sync, NO background geolocation (platform-honest). */
"use strict";

const CACHE = "biz-geo-shell-v1";

self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

function isShellAsset(url) {
    return url.pathname.startsWith("/web/assets/") ||
           url.pathname.includes("/static/lib/leaflet/") ||
           url.pathname.includes("/static/src/");
}

self.addEventListener("fetch", (event) => {
    const req = event.request;
    if (req.method !== "GET") {
        return; // never cache mutations
    }
    const url = new URL(req.url);

    // Network-first for RPC / JSON — always want the freshest state.
    if (url.pathname.startsWith("/driver/") || url.pathname.startsWith("/web/dataset/")) {
        return; // let the network handle it (no offline JSON caching)
    }

    // Cache-first for the app shell.
    if (isShellAsset(url)) {
        event.respondWith(
            caches.match(req).then((hit) => {
                if (hit) {
                    return hit;
                }
                return fetch(req).then((resp) => {
                    if (resp && resp.status === 200 && resp.type === "basic") {
                        const copy = resp.clone();
                        caches.open(CACHE).then((c) => c.put(req, copy));
                    }
                    return resp;
                }).catch(() => hit);
            })
        );
    }
});
