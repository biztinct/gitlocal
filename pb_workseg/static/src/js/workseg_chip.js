/** @odoo-module **/
/**
 * "Where they work" on a person's card.
 *
 * WHY A REGISTRY AND NOT AN IMPORT
 * --------------------------------
 * The Employee 360 drawer belongs to `pb_employee_vault`, and it opens a chip
 * registry in its header (`pb_employee_360_chips`) exactly so a second module
 * can say one line about a person without forking the drawer. P2 put "Paid by"
 * there; this is the second row. The dependency runs one way and both modules
 * are installable alone.
 *
 * WHAT IT SAYS, AND WHEN IT SAYS NOTHING. A person whose month is a whole
 * month at one employment gets NO chip at all — that is the normal case and a
 * chip reading "not split" on four and a half thousand cards is noise. Where
 * days really were worked somewhere else, the chip names the other entity and
 * how many days, and the tooltip says who pays for them.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.assignments";

export class WhereTheyWorkChip extends Component {
    static template = "pb_workseg.WhereTheyWorkChip";
    static props = {
        empId: { type: [Number, String], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: { found: false } });
        onWillStart(async () => {
            try {
                // `silent` on purpose: a chip is an extra on somebody else's
                // drawer, and a failed extra must never put a loading bar or
                // an error dialog over the drawer that DID load.
                const answer = await this.orm.silent.call(
                    MODEL, "chip_for", [Number(this.props.empId) || 0]);
                this.state.data = answer || { found: false };
            } catch {
                this.state.data = { found: false };
            }
        });
    }

    ic(name, size = 13) { return ic(name, size); }

    get tooltip() {
        const d = this.state.data || {};
        return d.tooltip || _t("Part of this month was worked somewhere else.");
    }
}

registry.category("pb_employee_360_chips").add("where_they_work",
                                               WhereTheyWorkChip);
