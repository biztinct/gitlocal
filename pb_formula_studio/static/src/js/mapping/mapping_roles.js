/** @odoo-module **/
/**
 * COLROLES' role vocabulary, in ONE place.
 *
 * JOURNEY J1 merges the two shells of the mapping board into the full-screen
 * host, and the employee board's lane chips came with it. The chips need a role's
 * ICON and its fallback LABEL — both of which lived as a `const ROLES` and a
 * `roleLabel()` switch inside `formula_studio.js`, a 7000-line module the
 * full-screen host has no business importing.
 *
 * Copying six keys into a second file would have been three minutes and a future
 * afternoon: a role added to one list and not the other renders a chip with no
 * glyph, which nothing errors on. So the vocabulary moved DOWN here, next to the
 * board that reads it, and `formula_studio.js` imports it — the grid, the outline
 * and the chips are now looking at the same six rows.
 *
 * `icon` keys the `pb_formula_studio.RoleIco` template in `studio.xml` (same
 * inner-shapes contract as `SrcIco`/`ProbIco`). Labels are NOT constants:
 * `_t()` at module scope evaluates before the translations load, so they are
 * resolved per call.
 */
import { _t } from "@web/core/l10n/translation";

/** Picker order: pay first, then the data that travels with it. */
export const ROLES = [
    { key: "payroll", icon: "coins" },
    { key: "identity", icon: "idcard" },
    { key: "profile", icon: "user" },
    { key: "contract", icon: "briefcase" },
    { key: "bank", icon: "bank" },
    { key: "reference", icon: "filetext" },
];

/** The lane order the employee board's chips and swim-lanes both use. */
export const ROLE_LANE_ORDER = [
    "identity", "bank", "profile", "contract", "reference", "payroll",
];

export function roleMeta(role) {
    return ROLES.find((r) => r.key === (role || "payroll")) || ROLES[0];
}

export function roleIcon(role) { return roleMeta(role).icon; }

export function roleLabel(role) {
    return {
        payroll: _t("Payroll"), identity: _t("Identity"),
        profile: _t("Employee profile"), contract: _t("Contract"),
        bank: _t("Bank"), reference: _t("Reference"),
    }[role || "payroll"] || _t("Payroll");
}

export function roleHint(role) {
    return {
        payroll: _t("Feeds the calculation."),
        identity: _t("Says which employee the row belongs to."),
        profile: _t("Personal details kept on the employee."),
        contract: _t("Terms kept on the contract."),
        bank: _t("Payment details."),
        reference: _t("A code or note carried along."),
    }[role || "payroll"] || "";
}
