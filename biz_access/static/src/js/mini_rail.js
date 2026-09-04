/** @odoo-module **/
/**
 * `PbMiniRail` — the left menu, drawn small, showing what somebody would see.
 *
 * WHY A MINIATURE AND NOT A LIST. "This role opens Pay Run and People" is a
 * sentence somebody has to translate before they can check it. The left menu
 * drawn as the left menu is the thing they already look at forty times a day,
 * so a picture of it needs no translating at all — and the moment a tick box
 * lights a row up, the promise the dialog is making has been SHOWN rather than
 * described. That is the whole reason the Role Composer has a right-hand side.
 *
 * IT DECIDES NOTHING. Every state on every row — on, locked, hidden, and which
 * rows are newly lit — is worked out on the server by the same code that
 * answers for it afterwards (`pb.access._rail_states`). This component draws
 * what it is handed and nothing else. A second copy of the visibility rule
 * living in a browser is a copy that will one day disagree, and it would
 * disagree by promising somebody a screen they cannot open.
 *
 * IT IS A COMPONENT, NOT A LUMP OF MARKUP, BECAUSE IT IS USED TWICE. The
 * composer's preview is the first place; the person passport is the second.
 *
 * THE ICONS. The left menu's own icon set is a closed list that lives with the
 * left menu, and this module is not allowed to reach into it. So the names are
 * mapped onto the shared `ic()` registry here, and anything unrecognised draws
 * a plain circle — the same thing the real menu does with a name it does not
 * know. A miniature drawing a wrong-but-confident icon would be worse than one
 * drawing a dot.
 */
import { Component, markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** Left-menu icon name -> shared registry key. */
const RAIL_ICONS = {
    "home": "home",
    "calendar": "calendar",
    "clock": "clock",
    "receipt": "receipt",
    "zap": "zap",
    "download": "download",
    "users": "users",
    "user": "user",
    "file": "file",
    "file-text": "fileText",
    "calculator": "calculator",
    "layers": "layers",
    "shield": "shield",
    "percent": "percent",
    "trending-up": "trendingUp",
    "trending-down": "trendingDown",
    "clipboard-check": "checkCircle",
    "lock": "lock",
    "building": "building",
    "database": "database",
    "compass": "compass",
    "settings": "settings",
    "map-pin": "mapPin",
    "truck": "truck",
    "table": "table",
    "plane": "plane",
    "scan": "scan",
    "send": "send",
    "landmark": "landmark",
    "activity": "activity",
    "umbrella": "umbrella",
    "inbox": "inbox",
    "book-open": "bookOpen",
    "scroll-text": "scrollText",
    "refresh-cw": "refresh",
    "award": "award",
    "briefcase": "briefcase",
    "list": "list",
    "search": "search",
    "sparkles": "sparkles",
};

const CIRCLE = '<circle cx="12" cy="12" r="9"/>';

/** A left-menu icon, or a plain dot when the name is not one we can draw. */
export function railIcon(name, size = 14) {
    const key = RAIL_ICONS[(name || "").trim()];
    if (key) {
        return ic(key, size);
    }
    return markup(
        `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
        `stroke="currentColor" stroke-width="2" stroke-linecap="round" ` +
        `stroke-linejoin="round">${CIRCLE}</svg>`);
}

export class PbMiniRail extends Component {
    static template = "biz_access.PbMiniRail";
    static props = {
        sections: { type: Array },
        legend: { type: Boolean, optional: true },
    };
    static defaultProps = { legend: true };

    ic(n, s = 13) { return ic(n, s); }

    railIcon(name, s = 14) { return railIcon(name, s); }

    /** ONE expression per sentence, so the spaces survive (R34). */
    title(item) {
        if (item.state === "on") { return _t("They can open this."); }
        if (item.state === "locked") {
            return _t("They see this, locked, with a note about what it is.");
        }
        return _t("This is not on their menu at all.");
    }

    stateIcon(item) {
        if (item.state === "on") { return ic("check", 12); }
        if (item.state === "locked") { return ic("lock", 12); }
        return ic("eyeOff", 12);
    }
}
