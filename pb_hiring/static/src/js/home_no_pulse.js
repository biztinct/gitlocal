/** @odoo-module **/
/**
 * HOME WITHOUT THE PAYROLL START, for somebody whose work is hiring.
 *
 * Owner ruling 2026-10-04: a recruiter, talent lead or hiring manager with no
 * payroll menu must not be greeted by "Get your first payroll out" and a
 * "Run Payroll" button. Their first screen is already Hiring (the server sets
 * `home_action_id`, see `models/sidebar_door.py`); this is the other half —
 * pressing Home opens on Approvals, and the Pulse tab is not offered at all.
 *
 * The server decides who this is (`session.pb_hiring_not_payroll`, the same
 * rule that picks the first screen), so the tab and the first screen cannot
 * disagree. Everybody else's Home is exactly as before.
 */
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { PbHomeHub } from "@pb_home_hub/js/home_hub";

patch(PbHomeHub.prototype, {
    setup() {
        super.setup(...arguments);
        if (!session.pb_hiring_not_payroll) { return; }
        this.config.lenses = this.config.lenses.filter((l) => l.key !== "pulse");
        this.config.defaultLens = "approvals";
    },
});
