/** @odoo-module **/
/**
 * The fixed-term rule on the contract decisions board — a `patch()` adding the
 * one door the template needs (open the rule table), and a ⌘K row in the S8-B
 * block (4465). No edit of pb_contract_lifecycle.
 */
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbContractLifeBoard } from "@pb_contract_lifecycle/js/contractlife_board";

patch(PbContractLifeBoard.prototype, {
    async pbcrOpenRules() {
        const act = await this.orm.call("pb.contractlife", "open_fixed_term_rules", []);
        await this.action.doAction(act);
    },
});

registry.category("pb_hub_palette").add("contract_rules", {
    id: "contract_rules",
    label: _t("Fixed-term contract rules"),
    sublabel: _t("Contracts"),
    icon: "scale",
    groups: ["hr.group_hr_user"],
    action: { xmlid: "pb_contract_rules.action_pb_contract_rule" },
    keywords: ["renewal", "fixed-term", "hợp đồng xác định thời hạn", "PKWT"],
}, { sequence: 4465 });
