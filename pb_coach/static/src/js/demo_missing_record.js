/** @odoo-module **/

import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { FetchRecordError } from "@web/model/relational_model/errors";

/**
 * Shared-demo hardening.
 *
 * The demo is shared and its pay runs / payslips are intentionally cleaned or
 * overwritten by other demo users (see the disclaimer chip). So a demo user who
 * had a run open — in a breadcrumb, a bookmarked deep link, or a restored action
 * stack — can land on a record that no longer exists, producing the scary
 * "It seems the records with IDs N cannot be found. They might have been deleted."
 * toast (web/model/relational_model/errors.js → FetchRecordError).
 *
 * For demo users we swallow that error and glide back to the dashboard instead.
 * Real (non-demo) users are unaffected: the handler returns falsy and the stock
 * fetchRecordErrorHandler shows the normal message.
 */
let isDemoUser = false;
user.hasGroup("pb_demo.group_payobook_demo")
    .then((v) => { isDemoUser = v; })
    .catch(() => { /* not a demo user / group missing — leave false */ });

function demoMissingRecordHandler(env, error, originalError) {
    if (!isDemoUser || !(originalError instanceof FetchRecordError)) {
        return false; // let the default handler deal with it
    }
    try {
        env.services.action.doAction("pb_dashboard.action_pb_dashboard", { clearBreadcrumbs: true });
        env.services.notification.add(
            "That demo record was refreshed by another session — you're back on your dashboard.",
            { type: "info" }
        );
    } catch (e) {
        return false; // if the redirect fails, fall back to the normal error
    }
    return true;
}

// sequence 1 → runs before the stock "fetchRecordErrorHandler" (default sequence)
// so demo users get the graceful redirect first.
registry.category("error_handlers").add("demoMissingRecordHandler", demoMissingRecordHandler, {
    sequence: 1,
});
