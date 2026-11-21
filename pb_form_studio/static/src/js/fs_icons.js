/** @odoo-module **/
/**
 * Lucide icons for the Form builder — the shared kit set plus the few glyphs
 * it lacks, behind a CACHED helper.
 *
 * Cached on purpose: `t-out` of a NEW `markup()` re-inserts the DOM node on
 * every redraw (the PayAI mic flicker, memory owl-markup-flicker). The Studio
 * redraws on every drag-over, so `ic()` from the kit (a fresh markup per
 * call) would make every tile's icon flash. One markup per (name, size).
 */
import { markup } from "@odoo/owl";
import { IC } from "@pb_import_kit/js/import_icons";

const EXTRA = {
    type: '<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/>',
    alignLeft: '<line x1="21" x2="3" y1="6" y2="6"/><line x1="15" x2="3" y1="12" y2="12"/><line x1="17" x2="3" y1="18" y2="18"/>',
    toggle: '<rect width="20" height="12" x="2" y="6" rx="6" ry="6"/><circle cx="8" cy="12" r="2"/>',
    unlock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    gripVertical: '<circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/>',
    octagonX: '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    pointer: '<path d="m9 9 5 12 1.8-5.2L21 14Z"/><path d="M7.2 2.2 8 5.1"/><path d="m5.1 8-2.9-.8"/><path d="M14 4.1 12 6"/><path d="m6 12-1.9 2"/>',
    plusCircle: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>',
    fileClock: '<path d="M16 22h2a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><circle cx="8" cy="16" r="6"/><path d="M9.5 17.5 8 16.25V14"/>',
    languages: '<path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/>',
    settings2: '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
};

const CACHE = new Map();

/** Inline Lucide SVG as (cached) OWL markup. */
export function fsIc(name, size = 16) {
    const key = name + ":" + size;
    let out = CACHE.get(key);
    if (!out) {
        const body = EXTRA[name] || IC[name] || IC.check;
        out = markup(
            `<svg class="pbfb-ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
            `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ` +
            `aria-hidden="true">${body}</svg>`
        );
        CACHE.set(key, out);
    }
    return out;
}

/** The icon of a field kind (same keys as the server's `TTYPE_KIND`). */
export const KIND_ICON = {
    text: "type", longtext: "alignLeft", integer: "hash", number: "percent", money: "banknote",
    bool: "toggle", date: "calendar", select: "list", m2o: "link", file: "paperclip",
    readonly: "lock",
};
