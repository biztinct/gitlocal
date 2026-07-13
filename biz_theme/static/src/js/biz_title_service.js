import { registry } from "@web/core/registry";
import { session } from "@web/session";

/**
 * Branded browser-tab title.
 *
 * The stock `title` service (web/core/browser/title_service.js) hard-codes
 * `|| "Odoo"` as the fallback when no title parts are set, and it runs AFTER
 * our server-rendered <title>, so it clobbers the debranded title on every
 * backend page. This is a drop-in replacement (registered with {force:true})
 * that swaps that single fallback for the resolved app name — injected by
 * biz_theme's ir_http.session_info() as `biz_app_name`
 * (biz_theme.app_name param → debrand keys → company name → "Odoo").
 *
 * Everything else is a verbatim copy of the core service so behaviour
 * (counters, " - " joined parts, action names) is unchanged.
 */
const brandName = () => session.biz_app_name || "Odoo";

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

        // Seed the branded default immediately, so the tab never flashes "Odoo"
        // before the first action sets its own part.
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
