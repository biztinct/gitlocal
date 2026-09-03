/** @odoo-module **/
/**
 * "About Payobook" in Settings, through the hub's soft registry.
 *
 * The hub cannot import this module (it would be the dependency backwards), so
 * a category is REGISTERED rather than added to the hub's own list — exactly
 * the seam settings_hub.js documents at SETTINGS_CATEGORIES. On a database
 * without this module nothing is registered and Settings is unchanged.
 *
 * NO GATE. `groups: []` means everybody, and that is deliberate: which release
 * you are on and what changed in it is not privileged information, it is the
 * answer to "why does this screen look different today" for whoever happens to
 * be looking at it. There is nothing behind the door but reading.
 *
 * ONE CARD, so the hub takes the reader straight through to the page rather
 * than showing a section page with a single tile on it (`soleCard`). If a later
 * phase adds a second card here — "Plan & usage", say — the section page comes
 * back on its own with nothing to undo.
 */
import { registry } from "@web/core/registry";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { _t } from "@web/core/l10n/translation";

registry.category(SETTINGS_CATEGORIES).add("about", {
    key: "about",
    icon: "info",
    label: _t("About Payobook"),
    blurb: _t("Which release you are on and what changed in it."),
    groups: [],
    cards: [
        {
            id: "whats_new",
            tag: "pb_tenancy_whats_new",
            icon: "sparkles",
            label: _t("What's new"),
            sub: _t("Every update we have shipped, newest first, in plain words."),
        },
        // FLEET P5. The second card, so the section page the comment above
        // predicted comes back on its own with nothing to undo.
        //
        // STILL NO GATE. What your company pays for, how many people are on
        // Payobook and last month's invoice are not privileged: the people who
        // need them are the office manager and whoever is asked "why has the
        // bill gone up". Gating it on the platform's own administrator group
        // would put it behind a door nobody on a customer's database holds
        // (the tenant-admin rails see to that).
        {
            id: "plan_usage",
            tag: "pb_tenancy_plan_usage",
            icon: "creditCard",
            label: _t("Plan & usage"),
            sub: _t("Your plan, how many employees it allows, and your invoices."),
        },
    ],
}, { sequence: 40 });
