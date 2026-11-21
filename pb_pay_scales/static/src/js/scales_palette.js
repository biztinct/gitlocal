/** @odoo-module **/
/**
 * WDGAP S8-A — the ⌘K door to the scales, in the free 3460 block (FACTS §0:
 * 3460–3490 reserved for scales). Same gate as the rest of Pay.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { PAY_GATE } from "@pb_pay/js/pay_palette";

registry.category("pb_hub_palette").add("pay_scales", {
    id: "pay_scales",
    label: _t("Pay scales"),
    sublabel: _t("Pay"),
    icon: "layers",
    groups: PAY_GATE,
    requires: "pb_pay",
    action: { xmlid: "pb_pay_scales.action_pb_pay_scales" },
}, { sequence: 3460 });
