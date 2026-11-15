/** @odoo-module **/
/**
 * WDGAP S8-A — "On scale · Senior associate, step 2" on a person's panel.
 *
 * Through the employee panel's chip registry (`pb_employee_360_chips`), the
 * same seam "Paid by" uses — no edit of `pb_employee_vault`. Silent on
 * purpose: a chip is an extra on somebody else's drawer, so a failed read
 * shows nothing rather than an error over a drawer that did load. Shows
 * nothing either for a person who is not on, and not due for, any scale.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

export class ScaleChip extends Component {
    static template = "pb_pay_scales.ScaleChip";
    static props = {
        empId: { type: [Number, String], optional: true },
        onOpenContract: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: { found: false } });
        onWillStart(async () => {
            try {
                const answer = await this.orm.silent.call(
                    "pb.pay.scales", "employee_chip", [Number(this.props.empId) || 0]);
                this.state.data = answer || { found: false };
            } catch {
                this.state.data = { found: false };
            }
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    get toneClass() { return "pbs-echip is-" + (this.state.data.tone || "muted"); }

    open() {
        const d = this.state.data;
        if (d.contract_id && this.props.onOpenContract) {
            this.props.onOpenContract(d.contract_id, "terms");
        }
    }
}

registry.category("pb_employee_360_chips").add("pay_scale", ScaleChip);
