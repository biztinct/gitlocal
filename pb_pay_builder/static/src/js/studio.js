/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbFormulaStudio } from "@pb_formula_studio/js/formula_studio";

patch(PbFormulaStudio.prototype, {
    async choosePaySource(personal) {
        const draft = this.state.draft;
        if (this.state.editBusy || draft.is_contract_component === personal) {
            this.keepPaySource();
            return;
        }
        const request = this.paySwitchRequest = (this.paySwitchRequest || 0) + 1;
        this.state.paySwitch = { busy: true };
        try {
            const result = await this.orm.call("pb.pay.builder", "switch_preview", [draft.id, personal]);
            if (this.state.draft !== draft || request !== this.paySwitchRequest) return;
            if (!result.ok) {
                this.state.paySwitch = null;
                this.notif.add(result.msg, { type: "warning" });
            } else if (result.count) {
                this.state.paySwitch = { ...result, personal, showNames: false };
            } else {
                draft.is_contract_component = personal;
                this.state.paySwitch = null;
            }
        } catch {
            if (request === this.paySwitchRequest && this.state.draft === draft) {
                this.state.paySwitch = null;
                this.notif.add(_t("The people affected could not be checked. Try again."), { type: "warning" });
            }
        }
    },
    keepPaySource() {
        this.paySwitchRequest = (this.paySwitchRequest || 0) + 1;
        this.state.paySwitch = null;
    },
    acceptPaySource() {
        if (!this.state.paySwitch?.warning) return;
        this.state.draft.is_contract_component = this.state.paySwitch.personal;
        this.keepPaySource();
    },
    cancelEdit() {
        this.keepPaySource();
        return super.cancelEdit(...arguments);
    },
    async enterEdit() {
        this.keepPaySource();
        return super.enterEdit(...arguments);
    },
    async saveComponent() {
        if (!this.state.paySwitch) return super.saveComponent(...arguments);
    },
    async chooseMainPay(ev) {
        const cfg = this.state.config.id;
        const id = Number(ev.target.value) || false;
        const settings = this.state.settings;
        ev.target.value = settings.values.pbpb_main_rule_id || "";
        this.state.payMainBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "save_config_settings", [cfg, { pbpb_main_rule_id: id }]);
            if (r.ok && this.state.settings === settings) settings.values.pbpb_main_rule_id = id;
            if (!r.ok) this.notif.add(r.msg, { type: "warning" });
        } finally {
            this.state.payMainBusy = false;
        }
    },
});
