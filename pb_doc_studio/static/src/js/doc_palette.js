/** @odoo-module **/
/**
 * The Document studio's row in the global ⌘K palette (DOCSTUDIO F1).
 * Same people as the Settings card; the group heading is imported, never
 * minted again (a second `_t("Admin")` would draw a second heading).
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { G_ADMIN } from "@pb_hub/js/hub_palette_entries";
import { DOC_STUDIO_GROUPS } from "./settings_card";

registry.category("pb_hub_palette").add("doc_studio", {
    id: "doc_studio",
    label: _t("Documents"),
    sublabel: _t("Letter wording and design"),
    icon: "fileText",
    group: G_ADMIN,
    action: { xmlid: "pb_doc_studio.action_pb_doc_studio" },
    requires: "pb_doc_studio",
    groups: DOC_STUDIO_GROUPS,
}, { sequence: 2125 });
