/** @odoo-module **/
/**
 * FILLIN P2 B4 — "3 answers to check" on a person's side panel.
 *
 * Payobook fills in a new contract's usual answers by itself (BPJS covered,
 * tax allowance…). Until somebody confirms them, the person's panel says so
 * with one amber chip; pressing it opens the contract on its Components tab,
 * where the answers can be confirmed or changed. Nothing to check → nothing
 * rendered (quiet board pattern: colour only when there is something to do).
 *
 * Registered into this module's own chip seam (`pb_employee_360_chips`), the
 * `pb_scheme_map` "Paid by" chip being the precedent. The ORM call is silent:
 * a chip is an extra and must never put an error over a panel that loaded.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_employee_vault/js/pev_icons";

export class FillinChip extends Component {
    static template = "pb_employee_vault.FillinChip";
    static props = {
        empId: { type: [Number, String], optional: true },
        onOpenContract: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ n: 0, contractId: 0 });
        onWillStart(async () => {
            try {
                const r = await this.orm.silent.call(
                    "pb.people", "fillin_pending", [Number(this.props.empId) || 0]);
                this.state.n = (r && r.n) || 0;
                this.state.contractId = (r && r.contract_id) || 0;
            } catch {
                this.state.n = 0;
            }
        });
    }

    ic(n, s = 13) { return ic(n, s); }

    get label() {
        return this.state.n === 1 ? _t("1 answer to check")
            : _t("%s answers to check", this.state.n);
    }
    get tooltip() {
        return _t("Payobook filled these in from the scheme's usual answers when the contract was created. Open the contract to check or change them.");
    }
    open() {
        if (this.state.contractId && this.props.onOpenContract) {
            this.props.onOpenContract(this.state.contractId, "components");
        }
    }
}

registry.category("pb_employee_360_chips").add("fillin", FillinChip);
