import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * The notice board (TIERS T3b) — keyboard ergonomics. Both pages are plain
 * links and work without this file; it holds no words.
 *
 *  - on the board: ArrowDown / j and ArrowUp / k move between notices (the
 *    big card first, then the list), Home / End jump to the first / last;
 *  - on one notice: ArrowLeft goes to the newer notice, ArrowRight to the
 *    older one (only when focus is not in a field).
 */
export class PbNoticeRows extends Interaction {
    static selector = "[data-pbnb-rows]";
    dynamicContent = {
        _root: { "t-on-keydown": this.onKeydown },
    };

    onKeydown(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }
        const rows = [...this.el.querySelectorAll("a.pbnb-hero, a.pbnb-row")];
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

export class PbNoticeNav extends Interaction {
    static selector = "[data-pbnb-nav]";

    start() {
        this.addListener(document, "keydown", this.onKeydown);
    }

    onKeydown(ev) {
        if (ev.altKey || ev.ctrlKey || ev.metaKey || ev.shiftKey) {
            return;
        }
        const target = ev.target;
        if (target && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName))) {
            return;
        }
        const link =
            ev.key === "ArrowLeft"
                ? this.el.querySelector("[data-pbnb-newer]")
                : ev.key === "ArrowRight"
                  ? this.el.querySelector("[data-pbnb-older]")
                  : null;
        if (link && link.href) {
            ev.preventDefault();
            window.location.assign(link.href);
        }
    }
}

registry.category("public.interactions").add("pb_me_portal_comm.notice_rows", PbNoticeRows);
registry.category("public.interactions").add("pb_me_portal_comm.notice_nav", PbNoticeNav);
