/** @odoo-module **/
/**
 * Settings › Form builder card.
 *
 * Registered by the registry's NAME rather than by importing it from
 * pb_settings, so the engine does not depend on the settings module (the hub
 * reads `registry.category("pb_settings_category")`, settings_hub.js:271).
 * Gated to the administrator (R2): the hub's server gate (`resolve_gates`)
 * answers on the groups named here, and every facade method the card opens
 * refuses anybody else as well.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("pb_settings_category").add(
    "form_builder",
    {
        key: "form_builder",
        group: "system",
        icon: "wand",
        label: _t("Form builder"),
        blurb: _t("Add your own fields to record screens and decide who sees them."),
        groups: ["base.group_system"],
        cards: [
            {
                id: "form_builder", tag: "pb_form_library", icon: "wand",
                label: _t("Form builder"),
                sub: _t("Every custom field in this company: where it appears, who can see it and what uses it."),
            },
        ],
    },
    { sequence: 60 },
);
