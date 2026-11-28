/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Payobook debranding — top-right user menu.
 *
 * Remove every Odoo / odoo.com reference from the account dropdown. The
 * product is "Payobook"; links to odoo.com (My Odoo.com Account, and the
 * Documentation / Support items that also point at odoo.com) must not surface.
 *
 * These items are registered by Odoo core in
 *   web/static/src/webclient/user_menu/user_menu_items.js
 * under the "user_menuitems" registry. pb_sidebar loads after web core, so by
 * the time this module is imported the core items are already registered and
 * can be removed cleanly.
 */
const userMenu = registry.category("user_menuitems");

for (const key of ["odoo_account", "documentation", "support"]) {
    if (userMenu.contains(key)) {
        userMenu.remove(key);
    }
}
