/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";

import { onMounted, onPatched } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { whenReady } from "@odoo/owl";

// Home button now targets the current Payobook Dashboard (the legacy Flow
// Dashboard has been retired from the left-menu flow; pb_hr_flow stays dormant).
const DEFAULT_ACTION_ID = "pb_dashboard.action_pb_dashboard";
const FLOW_MODEL = "hr.flow.wizard";

/**
 * Check whether the Flow Dashboard (.circular-workflow) is on screen.
 */
const isFlowDashboardVisible = () => !!document.querySelector('.circular-workflow');

/**
 * Hide / show form control buttons depending on whether we are
 * on the Flow Dashboard.
 */
const adjustControlPanel = () => {
    const cp = document.querySelector('.o_control_panel');
    if (!cp) return;

    const isFlow = isFlowDashboardVisible();

    // New button wrapper
    const newBtnWrap = cp.querySelector('.o_control_panel_main_buttons');
    if (newBtnWrap) {
        if (isFlow) {
            newBtnWrap.style.setProperty('display', 'none', 'important');
        } else {
            newBtnWrap.style.removeProperty('display');
        }
    }

    // Cog / actions menu
    const cogMenu = cp.querySelector('.o_cp_action_menus');
    if (cogMenu) {
        if (isFlow) {
            cogMenu.style.setProperty('display', 'none', 'important');
        } else {
            cogMenu.style.removeProperty('display');
        }
    }

    // Save / cancel status indicator
    const status = cp.querySelector('.o_form_status_indicator');
    if (status) {
        if (isFlow) {
            status.style.setProperty('display', 'none', 'important');
        } else {
            status.style.removeProperty('display');
        }
    }

    // Home icon — always ensure exactly one
    ensureHomeIcon(cp);
};

/**
 * Add exactly one home icon to the breadcrumb area.
 */
const ensureHomeIcon = (cp) => {
    if (!cp) cp = document.querySelector('.o_control_panel');
    if (!cp) return;

    const existing = cp.querySelector('.o_hr_flow_home_link');
    if (existing) return; // already there

    // Odoo 19: breadcrumbs container
    const breadcrumbContainer = cp.querySelector('.o_control_panel_breadcrumbs');
    if (!breadcrumbContainer) return;

    const link = document.createElement('a');
    link.className = 'o_hr_flow_home_link';
    link.setAttribute('role', 'button');
    link.setAttribute('aria-label', _t("Open Dashboard"));
    link.setAttribute('title', 'Home');
    link.setAttribute('href', `/web#action=${DEFAULT_ACTION_ID}`);
    link.innerHTML = '<i class="fa fa-home"></i>';
    link.style.cssText = 'margin-right:8px;font-size:16px;color:#4c4c4c;cursor:pointer;text-decoration:none;display:flex;align-items:center;';

    link.addEventListener('click', (ev) => {
        ev.preventDefault();
        const actionService = window.__hr_flow_action_service;
        if (actionService && actionService.doAction) {
            actionService.doAction(DEFAULT_ACTION_ID, {
                clear_breadcrumbs: true,
                clearBreadcrumbs: true,
            });
        } else {
            window.location.href = `/web#action=${DEFAULT_ACTION_ID}`;
        }
    });

    breadcrumbContainer.insertBefore(link, breadcrumbContainer.firstChild);
};

/* ─── Patch ControlPanel to capture the action service ─── */
patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
        if (this.env && this.env.services && this.env.services.action) {
            window.__hr_flow_action_service = this.env.services.action;
        }
        onMounted(() => {
            // Small delay so the DOM is fully settled
            setTimeout(adjustControlPanel, 50);
        });
        onPatched(() => {
            setTimeout(adjustControlPanel, 50);
        });
    },
});

/* ─── Global observer as fallback ─── */
whenReady(() => {
    let timer;
    const obs = new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(adjustControlPanel, 100);
    });
    obs.observe(document.body, { childList: true, subtree: true });
    // Initial run
    setTimeout(adjustControlPanel, 500);
});
