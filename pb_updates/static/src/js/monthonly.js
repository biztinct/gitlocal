/** @odoo-module **/
/**
 * UPDATES P3a (D1) — "This file is used for this pay run only" on the two
 * screens where a person brings in a pay data file (the Run Payroll screen
 * and the Import screen's guided "Load Pay Data"), with a way to People ›
 * Updates. Display only: month-only is enforced on the server.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PayrunWizard } from "@pb_payrun_wizard/js/payrun_wizard";
import { ImportWizard } from "@pb_import_wizard/js/import_wizard";
import { icon } from "@pb_updates/js/updates_review";

const MONTH_ONLY = {
    pbuIcon(name, size) { return icon(name, size); },
    pbuOpenUpdates() {
        this.env.services.action.doAction("pb_updates.action_pb_updates_desk")
            .catch(() => this.env.services.notification.add(
                _t("Updates is not available on this database."), { type: "warning" }));
    },
};

patch(PayrunWizard.prototype, MONTH_ONLY);
patch(ImportWizard.prototype, MONTH_ONLY);
