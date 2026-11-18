/** @odoo-module **/
/**
 * WDGAP S2-C ruling BL4 — "Account in another person's name" on a person's
 * side panel, with "Mark as seen".
 *
 * Registered into the side panel's own chip seam (`pb_employee_360_chips`,
 * the FILLIN / "Paid by" precedent) BY NAME: this module does not depend on
 * the panel's module, and a category nobody reads is simply never shown.
 * The server decides who sees it (HR and the payroll team): for anybody else
 * the call is refused and the chip renders nothing. Marking seen hides the
 * notice for THIS account and holder only and changes nothing about payment.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const ICONS = {};
function icon(name, size = 13) {
    const key = name + ":" + size;
    if (!ICONS[key]) { ICONS[key] = ic(name, size); }
    return ICONS[key];
}

export class PbOtherNameChip extends Component {
    static template = "pb_pay_delivery.OtherNameChip";
    static props = {
        empId: { type: [Number, String], optional: true },
        onOpenContract: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.icon = icon;
        this.state = useState({ show: false, holder: "", busy: false });
        onWillStart(async () => {
            try {
                const r = await this.orm.silent.call(
                    "hr.employee", "pb_other_name_state", [Number(this.props.empId) || 0]);
                this.state.show = !!(r && r.show);
                this.state.holder = (r && r.holder) || "";
            } catch {
                this.state.show = false;
            }
        });
    }

    get label() {
        return _t("This bank account is in another person's name: %s", this.state.holder);
    }
    get tooltip() {
        return _t("Marking it as seen only hides this notice. Whether this person is paid by bank file is decided by the company setting on Settings › Payroll › Bank layouts.");
    }
    async markSeen() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const r = await this.orm.call(
                "hr.employee", "pb_other_name_mark_seen", [Number(this.props.empId) || 0]);
            this.state.show = !!(r && r.show);
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("pb_employee_360_chips").add("pb_other_name", PbOtherNameChip);
