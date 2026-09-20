/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

/**
 * Two doors into the guided setup that live on somebody else's screen.
 *
 * **The command palette** (⌘K / Ctrl+K). One row in `pb_hub`'s registry, the
 * same shape every other surface uses. `pb_blueprint` already depends on
 * `pb_hub`, so this is a registration and not a new coupling.
 *
 * **The Settings hub.** `pb_settings` publishes a soft registry of categories
 * and this adds one to it — deliberately through the registry's NAME rather
 * than by importing anything from that module: `pb_blueprint` does not depend
 * on it, and an import of a module absent from the bundle takes the whole
 * backend down rather than failing locally (B3 §10 made the same call for
 * `pb_pay_delivery`). A category nobody has installed the hub for is simply a
 * registry entry nothing ever reads.
 *
 * Both doors open the journey BY TAG, never by xmlid: opened by xmlid the URL
 * becomes `/odoo/action-<id>` and every extra parameter is dropped, so a
 * refresh mid-setup would land on an empty journey (BP14).
 */

const FORMULA_MANAGER = "pb_hr_payroll_formula.group_formula_manager";
const FORMULA_USER = "pb_hr_payroll_formula.group_formula_user";

registry.category("pb_hub_palette").add("new_configuration", {
    id: "new_configuration",
    label: _t("New configuration"),
    sublabel: _t("Setup"),
    icon: "sparkles",
    action: { tag: "pb_blueprint" },
    groups: [FORMULA_MANAGER, FORMULA_USER],
}, { sequence: 2115 });

registry.category("pb_settings_category").add("guided_setup", {
    key: "guided_setup",
    icon: "sparkles",
    label: _t("Guided setup"),
    blurb: _t("Build a payroll configuration step by step, with a live view of one person's pay."),
    groups: [FORMULA_MANAGER, FORMULA_USER],
    cards: [
        {
            id: "guided_setup", tag: "pb_blueprint", icon: "sparkles",
            label: _t("New configuration"),
            sub: _t("Six steps from a starting point to a configuration you can explain — and any setup you left half-finished is on the configurations screen, waiting to be resumed."),
        },
    ],
}, { sequence: 25 });
