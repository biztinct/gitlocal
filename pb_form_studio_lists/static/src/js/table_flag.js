/** @odoo-module **/
/**
 * The board's page call, told when the table is showing.
 *
 * A board loads its page with `this.orm.call(model, "<page method>", [], {…})`.
 * In table mode the same call must also bring the custom-field cells of the
 * page (`context.pbfl_table`, read by this module's server `_inherit`). The
 * board's own `loadPage` is left exactly as it is: its `orm` is handed a thin
 * wrapper that adds the flag to that one method, and only while the table
 * shows. Every other call passes through untouched.
 */
import { _t } from "@web/core/l10n/translation";

export function tableKw(kwargs) {
    return { ...kwargs, context: { ...(kwargs.context || {}), pbfl_table: true } };
}

export function withTableFlag(orm, method, isOn) {
    const wrapped = Object.create(orm);
    wrapped.call = (model, name, args = [], kwargs = {}) =>
        orm.call(model, name, args, name === method && isOn() ? tableKw(kwargs) : kwargs);
    return wrapped;
}

/** Card state class (`ok`, `warn`, `info`, `muted`) → the table's pill tone. */
export const TONE = { ok: "green", warn: "amber", info: "blue", muted: "slate" };

/** "12 days" chip for a running contract ending within 30 days, else null. */
export function soonChip(days) {
    if (days === null || days === undefined || days < 0 || days > 30) {
        return null;
    }
    if (days === 0) {
        return _t("Today");
    }
    return days === 1 ? _t("1 day") : _t("%s days", days);
}
