/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";

/**
 * Top-right user menu — "My Home", the way to one's own employee home (/my:
 * payslips, leave, documents) from inside the app. Owner ask 2026-11-04; the
 * /my pages' own account menu carries the same item (pb_me_portal).
 *
 * Sits just above My Preferences (sequence 50 in
 * web/static/src/webclient/user_menu/user_menu_items.js).
 */
function myHomeItem() {
    return {
        type: "item",
        id: "pb_my_home",
        description: _t("My Home"),
        href: "/my",
        callback: () => {
            browser.location.href = "/my";
        },
        sequence: 45,
    };
}

registry.category("user_menuitems").add("pb_my_home", myHomeItem);
