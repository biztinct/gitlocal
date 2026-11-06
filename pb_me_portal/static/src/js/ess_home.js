/** @odoo-module **/
/**
 * HOME WITHOUT THE PAYROLL START, for an employee-only person.
 *
 * Same rule and same shape as pb_hiring's `home_no_pulse.js`: the server
 * decides who this is (`session.pb_employee_only`, see
 * `models/ess_landing.py`), Home drops its company-wide Pulse tab and opens on
 * Approvals — the requests that are theirs. Everybody else's Home is exactly
 * as before.
 */
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { PbHomeHub } from "@pb_home_hub/js/home_hub";

patch(PbHomeHub.prototype, {
    setup() {
        super.setup(...arguments);
        if (!session.pb_employee_only) { return; }
        this.config.lenses = this.config.lenses.filter((l) => l.key !== "pulse");
        this.config.defaultLens = "approvals";
    },
});
