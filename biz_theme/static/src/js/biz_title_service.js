import { markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * Branded browser-tab title.
 *
 * The stock `title` service (web/core/browser/title_service.js) hard-codes the
 * platform vendor's own name as the fallback when no title parts are set, and
 * it runs AFTER our server-rendered <title>, so it clobbers the debranded
 * title on every backend page. This is a drop-in replacement (registered with
 * {force:true}) that swaps that single fallback for the resolved app name —
 * injected by biz_theme's ir_http.session_info() as `biz_app_name`
 * (biz_theme.app_name param → debrand keys → company name → NEUTRAL_APP_NAME).
 *
 * ERRORS E4-2. This file's OWN fallback used to be the vendor's name too, for
 * the case where session_info has not run. It is now the same neutral word the
 * server chain ends on — never the vendor's, and never the product's either,
 * because biz_theme is the reusable half and a white-labelled tenant must not
 * meet our name here. The literal below is pinned to
 * biz_theme/models/ir_http.py's NEUTRAL_APP_NAME by
 * biz_theme/tests/test_brand_fallback.py.
 *
 * Everything else is a verbatim copy of the core service so behaviour
 * (counters, " - " joined parts, action names) is unchanged.
 */
const NEUTRAL_APP_NAME = "Workspace";
const brandName = () => session.biz_app_name || NEUTRAL_APP_NAME;

export const bizTitleService = {
    start() {
        const titleCounters = {};
        const titleParts = {};

        function getParts() {
            return Object.assign({}, titleParts);
        }

        function setCounters(counters) {
            for (const key in counters) {
                const val = counters[key];
                if (!val) {
                    delete titleCounters[key];
                } else {
                    titleCounters[key] = val;
                }
            }
            updateTitle();
        }

        function setParts(parts) {
            for (const key in parts) {
                const val = parts[key];
                if (!val) {
                    delete titleParts[key];
                } else {
                    titleParts[key] = val;
                }
            }
            updateTitle();
        }

        function updateTitle() {
            const counter = Object.values(titleCounters).reduce((acc, count) => acc + count, 0);
            const name = Object.values(titleParts).join(" - ") || brandName();
            if (!counter) {
                document.title = name;
            } else {
                document.title = `(${counter}) ${name}`;
            }
        }

        // Seed the branded default immediately, so the tab never flashes the
        // vendor's name before the first action sets its own part.
        updateTitle();

        return {
            get current() {
                return document.title;
            },
            getParts,
            setCounters,
            setParts,
        };
    },
};

registry.category("services").add("title", bizTitleService, { force: true });

// =========================================================================
// EMPTY-LIST MESSAGES OPENED FROM OUR OWN SCREENS (2026-09-23)
//
// A cockpit button that returns `action.read()[0]` hands the client an action
// whose `help` is a plain string. Core only turns `help` into markup on the
// two paths it loads itself (by id, or from a form button), so on this path
// the empty-list message rendered as literal "<p class=...>" text. Every
// doAction(object) now gets the same treatment core gives its own paths.
// `help` comes from action records written by developers or administrators,
// the same source core already trusts on those paths.
// =========================================================================
const services = registry.category("services");
const actionDef = services.get("action", null);
if (actionDef && !actionDef.bizHelpMarkup) {
    const withMarkupHelp = (action) =>
        (action && typeof action === "object" && typeof action.help === "string")
            ? { ...action, help: markup(action.help) }
            : action;
    const wrap = (api) => {
        if (api && typeof api.doAction === "function") {
            const doAction = api.doAction;
            api.doAction = (action, options) => doAction(withMarkupHelp(action), options);
        }
        return api;
    };
    services.add("action", {
        ...actionDef,
        bizHelpMarkup: true,
        start(...args) {
            const api = actionDef.start.apply(this, args);
            return api && typeof api.then === "function" ? api.then(wrap) : wrap(api);
        },
    }, { force: true });
}

