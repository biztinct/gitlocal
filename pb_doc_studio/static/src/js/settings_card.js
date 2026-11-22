/** @odoo-module **/
/**
 * Settings › Documents card (DOCSTUDIO F1).
 *
 * Registered by the registry's NAME (as `pb_form_studio` does for "Form
 * builder"), so this module needs no import from the Settings hub. The hub
 * asks the server who may see it (`pb.settings.resolve_gates`): the people
 * who may change letter wording. Every facade method refuses anybody else as
 * well (`pb.doc.studio._require`).
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export const DOC_STUDIO_GROUPS = ["pb_lifecycle.group_lifecycle_admin", "base.group_system"];

registry.category("pb_settings_category").add(
    "documents",
    {
        key: "documents",
        group: "hr",
        icon: "fileText",
        label: _t("Documents"),
        blurb: _t("The wording, languages and look of every letter."),
        groups: DOC_STUDIO_GROUPS,
        cards: [
            {
                id: "doc_studio", tag: "pb_doc_studio", icon: "fileText",
                label: _t("Documents"),
                sub: _t("Letters and certificates: their wording, fields, languages, page design and copies for a company or country."),
            },
        ],
    },
    { sequence: 62 },
);
