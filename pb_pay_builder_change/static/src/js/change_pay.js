/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { PayBuilder } from "@pb_pay_builder/js/pay_builder";

export class ChangePay extends Component {
    static template = "pb_pay_builder_change.ChangePay";
    static components = { Dialog, PayBuilder };
    static props = ["contractId", "afterSend", "close"];
    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ui = useState({ date: "", reason: "review", reasons: [], values: {}, answer: null, fast: false, error: "", busy: false });
        onWillStart(async () => {
            try { Object.assign(this.ui, await this.orm.call("pb.pay.builder", "change_open", [this.props.contractId])); }
            catch (e) { this.ui.error = e.data?.message || _t("This contract is not available."); }
        });
    }
    get title() { return this.ui.person ? _t("Change pay for %s", this.ui.person) : _t("Change pay"); }
    get saveLabel() { return this.ui.fast ? _t("Save") : _t("Send for approval"); }
    change(key, value) {
        if (value == null) delete this.ui.values[key];
        else this.ui.values[key] = value;
        this.ui.answer = null;
    }
    get ready() { return this.ui.date && this.ui.reason && this.ui.answer?.state === "ok" && !this.ui.answer.has_failed && Object.keys(this.ui.values).length; }
    async send() {
        if (!this.ready || this.ui.busy) return;
        this.ui.busy = true;
        this.ui.error = "";
        try {
            const result = await this.orm.call("pb.pay.builder", "change_send",
                [this.props.contractId, this.ui.date, this.ui.reason, this.ui.values]);
            if (!result.ok || !["pending", "scheduled", "applied"].includes(result.state)) {
                this.ui.error = result.message || _t("The pay change could not be sent.");
                return;
            }
            this.notif.add(result.message, { type: "success" });
            await this.props.afterSend();
            this.props.close();
        } catch (e) {
            this.ui.error = e.data?.message || _t("The pay change could not be sent.");
        } finally {
            this.ui.busy = false;
        }
    }
}
registry.category("pb_change_pay").add("open", (dialog, props, onClose) => dialog.add(ChangePay, props, { onClose }));
