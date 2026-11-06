import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * My requests (TIERS T3a) — keyboard ergonomics on the timeline.
 *
 * The rows are plain links (Tab and Enter already work, and the page is fully
 * usable without this script). This adds the list-app keys: ArrowDown / j and
 * ArrowUp / k move between rows, Home / End jump to the first / last row.
 * Rows with nowhere to go (no page of their own) are skipped.
 */
export class PbMeRequests extends Interaction {
    static selector = "[data-pbme-rows]";
    dynamicContent = {
        _root: { "t-on-keydown": this.onKeydown },
    };

    rows() {
        return [...this.el.querySelectorAll("a.pbme-rq-row[href]")];
    }

    onKeydown(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }
        const rows = this.rows();
        if (!rows.length) {
            return;
        }
        const at = rows.indexOf(document.activeElement);
        let next = null;
        if (ev.key === "ArrowDown" || ev.key === "j") {
            next = rows[Math.min(rows.length - 1, at + 1)];
        } else if (ev.key === "ArrowUp" || ev.key === "k") {
            next = rows[Math.max(0, at - 1)];
        } else if (ev.key === "Home") {
            next = rows[0];
        } else if (ev.key === "End") {
            next = rows[rows.length - 1];
        }
        if (next) {
            ev.preventDefault();
            next.focus();
        }
    }
}

registry.category("public.interactions").add("pb_me_portal.my_requests", PbMeRequests);
