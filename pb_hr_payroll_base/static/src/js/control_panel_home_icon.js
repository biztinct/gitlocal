/** @odoo-module **/

import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";

let lastHomeContext = {};
let observerStarted = false;

const DEFAULT_ACTION_ID = "pb_hr_flow.action_hr_flow_wizard";
const BREADCRUMB_SELECTORS = [
    ".o_control_panel .breadcrumb",
    ".o_control_panel .o_breadcrumb",
    ".o_control_panel_breadcrumbs",
    ".o_cp_top_left .breadcrumb",
    ".o_cp_top_left .o_breadcrumb",
].join(", ");

const ensureHomeIcon = () => {
    const hide = lastHomeContext.hide_hr_flow_home;
    const actionId = lastHomeContext.home_action_id || DEFAULT_ACTION_ID;
    const breadcrumbs = Array.from(document.querySelectorAll(BREADCRUMB_SELECTORS));

    if (!breadcrumbs.length) {
        return;
    }

    breadcrumbs.forEach((breadcrumb) => {
        const container = breadcrumb.parentElement || breadcrumb;
        const existing = container.querySelector(".o_hr_flow_home_link");

        if (hide) {
            if (existing) {
                existing.remove();
            }
            return;
        }

        if (existing) {
            existing.dataset.actionId = actionId;
            return;
        }

        const link = document.createElement("a");
        link.className = "o_hr_flow_home_link";
        link.setAttribute("role", "button");
        link.setAttribute("aria-label", "Open HR Flow Dashboard");
        link.setAttribute("title", "Home");
        link.dataset.actionId = actionId;
        link.innerHTML = "<i class=\"fa fa-home\"></i>";

        link.addEventListener("click", (ev) => {
            ev.preventDefault();
            const targetAction = link.dataset.actionId || DEFAULT_ACTION_ID;
            const actionService = window.__hr_flow_action_service;
            if (actionService && actionService.doAction) {
                actionService.doAction(targetAction, {
                    clear_breadcrumbs: true,
                    clearBreadcrumbs: true,
                });
                return;
            }
        });

        breadcrumb.insertAdjacentElement("beforebegin", link);
    });
};

const startObserver = () => {
    if (observerStarted) {
        return;
    }
    observerStarted = true;
    const observer = new MutationObserver(() => ensureHomeIcon());
    observer.observe(document.body, { childList: true, subtree: true });
    ensureHomeIcon();
};

patch(ControlPanel.prototype, "pb_hr_payroll_base_home_icon", {
    setup() {
        this._super(...arguments);
        if (this.env && this.env.services && this.env.services.action) {
            window.__hr_flow_action_service = this.env.services.action;
        }
        onMounted(() => this._updateHomeIcon());
        onPatched(() => this._updateHomeIcon());
    },

    _getHomeContext() {
        const searchModel = this.env && this.env.searchModel;
        const context = (searchModel && (searchModel.globalContext || searchModel.context)) || {};
        lastHomeContext = context || {};
        return context;
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
            this.env.services.action.doAction(actionId, {
                clear_breadcrumbs: true,
                clearBreadcrumbs: true,
            });
        });

        breadcrumb.insertAdjacentElement("beforebegin", link);
    },
});

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startObserver);
} else {
    startObserver();
}
