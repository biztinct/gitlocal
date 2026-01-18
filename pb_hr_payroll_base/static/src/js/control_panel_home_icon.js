/** @odoo-module **/

import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";

patch(ControlPanel.prototype, "pb_hr_payroll_base_home_icon", {
    setup() {
        this._super(...arguments);
        onMounted(() => this._updateHomeIcon());
        onPatched(() => this._updateHomeIcon());
    },

    _getHomeContext() {
        const searchModel = this.env && this.env.searchModel;
        return (searchModel && (searchModel.globalContext || searchModel.context)) || {};
    },

    _updateHomeIcon() {
        if (!this.el) {
            return;
        }

        const context = this._getHomeContext();
        const shouldShow = !context.hide_hr_flow_home;
        const existing = this.el.querySelector(".o_hr_flow_home_link");

        if (!shouldShow) {
            if (existing) {
                existing.remove();
            }
            return;
        }

        if (existing) {
            existing.dataset.actionId = context.home_action_id || "";
            return;
        }

        const container = this.el.querySelector(".o_cp_top_left") || this.el.querySelector(".o_control_panel");
        if (!container) {
            return;
        }

        const breadcrumb = container.querySelector(".breadcrumb, .o_breadcrumb, .o_control_panel_breadcrumbs");
        if (!breadcrumb) {
            return;
        }

        const link = document.createElement("a");
        link.className = "o_hr_flow_home_link";
        link.setAttribute("role", "button");
        link.setAttribute("aria-label", "Open HR Flow Dashboard");
        link.setAttribute("title", "Home");
        link.dataset.actionId = context.home_action_id || "";
        link.innerHTML = "<i class=\"fa fa-home\"></i>";

        link.addEventListener("click", (ev) => {
            ev.preventDefault();
            const actionId = link.dataset.actionId || "pb_hr_flow.action_hr_flow_wizard";
            this.env.services.action.doAction(actionId);
        });

        breadcrumb.insertAdjacentElement("beforebegin", link);
    },
});
