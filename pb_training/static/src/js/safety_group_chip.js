/** @odoo-module **/
/**
 * "Safety group 3" and the person's site on the People drawer (LEARNING L2).
 *
 * The Employee 360 drawer (`pb_employee_vault`) opens a chip registry in its
 * header, `pb_employee_360_chips`, so another module can say one line about a
 * person without forking the drawer (precedent: pb_workseg's "Where they
 * work"). Nothing is drawn when the person has neither a safety group nor a
 * site — the normal case outside Vietnam, and a chip that says "none" on
 * every card is noise.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

export class SafetyGroupChip extends Component {
    static template = "pb_training.SafetyGroupChip";
    static props = { empId: { type: [Number, String], optional: true } };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: { found: false } });
        onWillStart(async () => {
            try {
                // `silent`: an extra on somebody else's drawer must never put
                // a loading bar or an error over the drawer that did load.
                const answer = await this.orm.silent.call(
                    "pb.training", "safety_chip", [Number(this.props.empId) || 0]);
                this.state.data = answer || { found: false };
            } catch {
                this.state.data = { found: false };
            }
        });
    }

    ic(name, size = 13) { return ic(name, size); }
}

registry.category("pb_employee_360_chips").add("pb_training_safety_group", SafetyGroupChip);
