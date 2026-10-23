/** @odoo-module **/
/**
 * "About Payobook" in Settings, through the hub's soft registry.
 *
 * The hub cannot import this module (it would be the dependency backwards), so
 * a category is REGISTERED rather than added to the hub's own list — exactly
 * the seam settings_hub.js documents at SETTINGS_CATEGORIES. On a database
 * without this module nothing is registered and Settings is unchanged.
 *
 * THE CATEGORY HAS NO GATE, and that is deliberate: which release you are on,
 * what changed in it and what your company pays are not privileged information.
 * ONE OF ITS CARDS HAS ONE (FLEET P6) — the page holding the switch that says
 * whether Payobook support may open this company's data belongs to whoever
 * decides who here can do what. See the bottom of the file for how a single
 * card is gated in a hub that gates categories.
 */
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { _t } from "@web/core/l10n/translation";

/**
 * FLEET P6. The permission the customer's own administrator holds — the group
 * behind the "who here can do what" ability, which the Tenant administrator
 * role requires.
 *
 * NOT `base.group_system`: on a customer's database that group is the
 * PLATFORM's, and the tenant-admin rails exist precisely to take it away from
 * the customer's own administrator. Putting the record of OUR access behind a
 * door only WE hold would be the exact opposite of what the page is for.
 */
const ACCESS_TEAM = "biz_access.group_access_manager";

const CARDS = [
    {
        id: "whats_new",
        tag: "pb_tenancy_whats_new",
        icon: "sparkles",
        label: _t("What's new"),
        sub: _t("Every update we have shipped, newest first, in plain words."),
    },
    // FLEET P5. The second card, so the section page comes back on its own
    // with nothing to undo.
    //
    // NO GATE. What your company pays for, how many people are on Payobook and
    // last month's invoice are not privileged: the people who need them are the
    // office manager and whoever is asked "why has the bill gone up".
    {
        id: "plan_usage",
        tag: "pb_tenancy_plan_usage",
        icon: "creditCard",
        label: _t("Plan & usage"),
        sub: _t("Your plan, how many employees it allows, and your invoices."),
    },
];

/** FLEET P6. The third card, offered only to whoever may actually use it. */
const SUPPORT_CARD = {
    id: "support_access",
    tag: "pb_tenancy_support",
    icon: "shield",
    label: _t("Support access"),
    sub: _t("Whether Payobook support may open your data, and every time we have."),
};

function register(cards) {
    registry.category(SETTINGS_CATEGORIES).add("about", {
        key: "about",
        icon: "info",
        label: _t("About Payobook"),
        blurb: _t("Which release you are on, what your company pays, and who "
                  + "has opened your data."),
        groups: [],
        cards,
    }, { sequence: 40, force: true });
}

// The two everybody gets, registered at once so Settings is never briefly
// without them.
register(CARDS);

/**
 * THE THIRD CARD IS GATED, AND THE GATE HAS TO BE ASKED FOR.
 *
 * The hub gates CATEGORIES on permissions, not individual cards, and this
 * category must stay open — "which release am I on" is for everybody. So the
 * card is added once the answer comes back, by re-registering the same
 * descriptor: the hub reads the registry fresh every time somebody opens
 * Settings, and this answer arrives at page load, long before anybody clicks a
 * cog.
 *
 * FAILS CLOSED, WHICH IS THE OPPOSITE OF THE HUB'S OWN RULE, on purpose. The
 * hub fails open per group because an unresolvable name means a module is
 * missing and hiding a screen for that reason is hiding it for the wrong one.
 * Here an unresolvable name means the permission system is not on this
 * database, and a page holding the switch that governs our access to somebody's
 * payroll should not be offered to everyone in the building because of it. The
 * server refuses just the same either way (`pb.tenancy.support_set_allowed`) —
 * this only decides whether a tile is drawn.
 *
 * ASKED AFTER THE FIRST PAINT, never during it. It is one small cached request
 * and it must not queue in front of the page somebody is waiting for — the same
 * reason the release toast waits 1.5 seconds.
 */
setTimeout(() => {
    user.hasGroup(ACCESS_TEAM).then((holds) => {
        if (holds) { register([...CARDS, SUPPORT_CARD]); }
    }).catch((e) => {
        console.warn("pb_tenancy: could not work out who manages permissions "
                     + "on this database", e);
    });
}, 2500);
