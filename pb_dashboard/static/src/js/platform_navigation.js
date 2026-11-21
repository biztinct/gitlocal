/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";

// The server applies the same entitlement to the actual menu tree. This item
// exposes existing administrator access; it never changes anybody's roles.
registry.category("user_menuitems").add("pb_platform_administration", () => ({
    type: "item",
    id: "pb_platform_administration",
    description: _t("Platform administration"),
    hide: !session.pb_platform_navigation,
    href: "/bizapp/settings?debug=1",
    callback: () => { browser.location.href = "/bizapp/settings?debug=1"; },
    sequence: 55,
}));
