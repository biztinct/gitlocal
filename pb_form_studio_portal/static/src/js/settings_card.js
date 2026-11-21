/** @odoo-module **/
/**
 * Settings › System › Form builder gets a second card: "My Payobook page"
 * (FS-12). The engine's own entry is extended in place (this file loads
 * after it: the module depends on the engine), so there is still ONE Form
 * builder category. Administrator only, like the category itself.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const cat = registry.category("pb_settings_category");
if (cat.contains("form_builder")) {
    const entry = cat.get("form_builder");
    if (!(entry.cards || []).some((c) => c.id === "my_payobook_page")) {
        entry.cards = [...(entry.cards || []), {
            id: "my_payobook_page", tag: "pb_page_builder", icon: "smartphone",
            label: _t("My Payobook page"),
            sub: _t("Arrange the employee's My Profile page: sections, fields, headings and a banner picture."),
        }];
    }
}
