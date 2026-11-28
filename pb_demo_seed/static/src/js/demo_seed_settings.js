/** @odoo-module **/

/**
 * A "Demo data" door in the settings cog.
 *
 * REGISTERED RATHER THAN EDITED IN. The settings hub publishes a registry for
 * exactly this (`SETTINGS_CATEGORIES` in pb_settings/static/src/js/settings_hub.js)
 * so a module can add a category without anybody touching the hub's own list —
 * which also means a database without this module installed has no dangling
 * card pointing at an action that is not there.
 *
 * GATED ON THE SYSTEM ADMINISTRATOR, and that is not politeness. Loading demo
 * people into a live payroll database is the kind of mistake that is quick to
 * make and slow to explain, so the door is only visible to the one role that
 * is expected to know which database they are in.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";

registry.category(SETTINGS_CATEGORIES).add(
    "demo_data",
    {
        key: "demo_data",
        icon: "beaker",
        label: _t("Demo data"),
        blurb: _t("Put a small, complete demo world into this database — and take it out again."),
        groups: ["base.group_system"],
        cards: [
            {
                id: "demo_data",
                xmlid: "pb_demo_seed.action_pb_demo_seed",
                icon: "beaker",
                label: _t("Demo data"),
                sub: _t("Five demo people with a story each, plus the assets, budgets, suppliers and recognition around them."),
            },
        ],
    },
    { sequence: 90 },
);
