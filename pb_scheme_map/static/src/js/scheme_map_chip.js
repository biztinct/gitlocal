/** @odoo-module **/
/**
 * "Paid by" on a person's card.
 *
 * WHY A REGISTRY AND NOT AN IMPORT
 * --------------------------------
 * The Employee 360 drawer belongs to `pb_employee_vault`, and the drawer slot
 * the People cockpit offers (`pb_people_drawer`) is single-occupant — the vault
 * already fills it. A second module cannot take it, and a fork of the drawer
 * would be two drawers to keep in step forever.
 *
 * So the vault opens a chip registry in its header (`pb_employee_360_chips`)
 * and this module registers one line into it. The dependency runs one way: the
 * vault knows chips may exist; this module knows the vault exists. Neither
 * imports the other, and both are installable alone.
 *
 * WHAT IT SAYS. The scheme that pays this person, the scheme that pays their
 * mid-month advance when there is one, and — in the tooltip — HOW that was
 * worked out ("from Bread's team map"). A person no scheme covers reads "Not
 * covered by any scheme", which is a fact somebody can act on, rather than an
 * empty space that reads as a screen that failed to load.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.scheme.board";

export class PaidByChip extends Component {
    static template = "pb_scheme_map.PaidByChip";
    static props = {
        empId: { type: [Number, String], optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ data: { found: false } });
        onWillStart(async () => {
            try {
                // `silent` on purpose: a chip is an extra on somebody else's
                // drawer, and a failed extra must never put a loading bar or an
                // error dialog over the drawer that DID load.
                const answer = await this.orm.silent.call(
                    MODEL, "paid_by", [Number(this.props.empId) || 0]);
                this.state.data = answer || { found: false };
            } catch {
                this.state.data = { found: false };
            }
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    /** How the answer was reached, for the tooltip — never on the chip face. */
    get tooltip() {
        const d = this.state.data || {};
        if (!d.config_id) {
            return _t("No team, division or rule on the scheme map reaches this person, so no pay run would include them.");
        }
        return d.via
            ? _t("Worked out %(via)s.", { via: d.via })
            : _t("Worked out from the scheme map.");
    }
}

registry.category("pb_employee_360_chips").add("paid_by", PaidByChip);
