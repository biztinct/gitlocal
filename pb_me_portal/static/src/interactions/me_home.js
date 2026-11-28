import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

/**
 * The employee home (/my): every tile the platform draws inside
 * `.o_portal_docs` is MOVED into its section (`data-pbme-group`, set by the
 * `portal_docs_entry_pbme` override from the URL-keyed registry).
 *
 * Moved, never copied: the stock counters interaction keeps references to the
 * tiles and to their counter spans, and fills them in after its own request
 * returns — a copy would be a tile whose number never arrives. Moving keeps
 * every node inside `.o_portal_my_home`, which is where that script looks.
 *
 * Until this runs, the tiles stay visible in the stock grid (already badged
 * and sorted by CSS), so a page whose scripts fail is plain, never blank.
 */
const GROUPS = ["me", "time", "growth", "people", "more"];

export class PbMeHome extends Interaction {
    static selector = ".pbme-home";

    setup() {
        this.moved = [];
    }

    start() {
        const docs = this.el.querySelector(".o_portal_docs");
        const cards = docs ? [...docs.querySelectorAll(".o_portal_index_card")] : [];
        const seq = (card) => Number(card.dataset.pbmeSeq) || 999;
        // stable sort by the registry's order, so the DOM (and the keyboard)
        // reads in the same order the eye does
        cards
            .map((card, index) => ({ card, index }))
            .sort((a, b) => seq(a.card) - seq(b.card) || a.index - b.index)
            .forEach(({ card }) => {
                const group = GROUPS.includes(card.dataset.pbmeGroup)
                    ? card.dataset.pbmeGroup
                    : "more";
                const target =
                    this.el.querySelector(`[data-pbme-section="${group}"]`) ||
                    this.el.querySelector('[data-pbme-section="more"]');
                if (!target) {
                    return;
                }
                this.moved.push([card, card.parentElement, card.nextSibling]);
                target.appendChild(card);
            });
        for (const body of this.el.querySelectorAll("[data-pbme-section]")) {
            const holder = body.closest(".pbme-sec, .pbme-b-me");
            if (holder) {
                holder.classList.toggle("is-empty", !body.children.length);
            }
        }
        this.el.classList.add("pbme-ready");
    }

    destroy() {
        // put every tile back where the platform drew it (edit mode, or any
        // other teardown), in reverse so each "next sibling" exists again
        for (const [card, parent, next] of this.moved.reverse()) {
            if (parent && parent.isConnected) {
                parent.insertBefore(card, next && next.parentElement === parent ? next : null);
            }
        }
        this.moved = [];
        for (const holder of this.el.querySelectorAll(".pbme-sec, .pbme-b-me")) {
            holder.classList.remove("is-empty");
        }
        this.el.classList.remove("pbme-ready");
    }
}

registry.category("public.interactions").add("pb_me_portal.me_home", PbMeHome);
