/** @odoo-module **/
/**
 * The contract list on an employee's "Contracts History" page.
 *
 * The stock list is `editable="bottom"` inside a form that is `edit="false"`,
 * so the field is readonly AND `canOpenRecord` is false (x2many_field.js) — a
 * click on a contract did nothing at all. This widget opens the clicked
 * contract in the same slide-over the Contracts board uses (the soft
 * `pb_contracts_drawer` registry), mounted through the overlay service so the
 * page stays where it is. Closing the panel reloads the page, so a wage or a
 * date changed in the panel shows in the row at once.
 */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

export class PbContractHistoryField extends X2ManyField {
    setup() {
        super.setup();
        this.overlay = useService("overlay");
        this.canOpenRecord = true;
    }

    async openRecord(record) {
        const Drawer = registry.category("pb_contracts_drawer").get("contract_360", null);
        if (!Drawer || !record.resId) {
            return super.openRecord(record);
        }
        const remove = this.overlay.add(Drawer, {
            contractId: record.resId,
            onClose: () => {
                remove();
                this.props.record.load();
            },
        });
    }
}

registry.category("fields").add("pb_contract_history", {
    ...x2ManyField,
    component: PbContractHistoryField,
});
