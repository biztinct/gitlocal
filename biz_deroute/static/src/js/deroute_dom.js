// Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
//
// DOM-level guarantee that no rendered anchor ever carries the /odoo prefix.
// Some href builders are plain function exports (e.g. menu_helpers'
// computeAppsAndMenuItems) whose references are captured by core consumers
// before this module evaluates, so they cannot be patched; rewriting at
// insertion time covers them all — navbar items, many2one links, chatter
// bodies, third-party renders — and makes hover previews, "Copy link
// address" and middle-clicks show the branded prefix.
import { BRAND_PREFIX, CORE_PREFIX } from "@biz_deroute/js/deroute_router";

function rebrandAnchor(el) {
    const href = el.getAttribute?.("href");
    if (
        href &&
        (href === CORE_PREFIX ||
            href.startsWith(CORE_PREFIX + "/") ||
            href.startsWith(CORE_PREFIX + "?") ||
            href.startsWith(CORE_PREFIX + "#"))
    ) {
        el.setAttribute("href", BRAND_PREFIX + href.slice(CORE_PREFIX.length));
    }
}

function sweep(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) {
        return;
    }
    if (node.tagName === "A") {
        rebrandAnchor(node);
    }
    if (node.firstElementChild) {
        node.querySelectorAll('a[href^="/odoo"]').forEach(rebrandAnchor);
    }
}

const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        if (mutation.type === "attributes") {
            // Re-rewriting is a no-op (href no longer matches), so no loop.
            rebrandAnchor(mutation.target);
        } else {
            mutation.addedNodes.forEach(sweep);
        }
    }
});

function start() {
    sweep(document.body);
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["href"],
    });
}

if (document.body) {
    start();
} else {
    document.addEventListener("DOMContentLoaded", start, { once: true });
}
