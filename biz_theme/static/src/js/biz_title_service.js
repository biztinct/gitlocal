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
