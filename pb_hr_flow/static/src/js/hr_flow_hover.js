/** @odoo-module */
/**
 * HR Flow hover & tertiary panel interactions
 * Migrated to Odoo 19 module syntax
 */

import { whenReady } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

const STORAGE_KEY = 'hr_flow_state';

const adminRoutes = new Set([
    'payroll-retro',
    'payroll-test',
    'pay-salary-payments',
    'pay-salary-journals',
]);

const loadState = () => {
    try {
        return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
    } catch (e) {
        return null;
    }
};

const saveState = (primary, secondary, panelKey) => {
    const payload = { primary: primary || null, secondary: secondary || null, panel: panelKey || null };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
};

const clearState = () => {
    sessionStorage.removeItem(STORAGE_KEY);
};

/**
 * Call a model method via RPC (Odoo 19 syntax)
 */
const callModel = async (model, method, args) => {
    return rpc(`/web/dataset/call_kw/${model}/${method}`, {
        model: model,
        method: method,
        args: args,
        kwargs: {},
    });
};

/**
 * Navigate to an action using the action service stored on window
 * by control_panel_home_icon.js
 */
const doAction = (action) => {
    const actionService = window.__hr_flow_action_service;
    if (actionService && actionService.doAction) {
        actionService.doAction(action);
    } else {
        // Fallback: reload with action
        if (action.type === 'ir.actions.act_window_close') {
            return;
        }
        window.location.reload();
    }
};

/**
 * Tertiary panel data definitions
 */
const tertiaryData = {
    payroll_config: {
        title: _t('Payroll Configuration'),
        items: [
            { label: _t('Connector'), icon: 'fa-plug', desc: _t('HRIS/Excel connectors'), disabled: false, route: 'payroll-connector' },
            { label: _t('Configure Salary'), icon: 'fa-sliders', desc: _t('Formulas & structures'), disabled: false, route: 'payroll-config' },
            { label: _t('Payslip Configuration'), icon: 'fa-cogs', desc: _t('Identifiers & labels'), disabled: false, route: 'payroll-payslip-config' },
            { label: _t('Employee/Contract Mapping'), icon: 'fa-exchange', desc: _t('Map fields to components'), disabled: false, route: 'payroll-employee-contract-mapping' },
            { label: _t('Mid-Cycle Mapping'), icon: 'fa-random', desc: _t('Map mid-cycle to end-cycle'), disabled: false, route: 'payroll-cycle-mapping' },
            { label: _t('Insurance Policies'), icon: 'fa-shield', desc: _t('BHXH/BHYT/BHTN rates'), disabled: false, route: 'vietnam-insurance-policies' },
            { label: _t('Insurance Adjustments'), icon: 'fa-pencil-square-o', desc: _t('Manual adjustments'), disabled: false, route: 'vietnam-insurance-adjustments' },
            { label: _t('Tax Tables'), icon: 'fa-percent', desc: _t('PIT rates & slabs'), disabled: false, route: 'vietnam-tax-tables' },
            { label: _t('Employee Dependents'), icon: 'fa-users', desc: _t('Tax deductions'), disabled: false, route: 'vietnam-employee-dependents' },
        ],
    },
    payroll: {
        title: _t('Payroll'),
        items: [
            { label: _t('Proration Audit'), icon: 'fa-pie-chart', desc: _t('Review prorated components'), disabled: false, route: 'payroll-proration' },
            { label: _t('Retro Adjustments'), icon: 'fa-history', desc: _t('Track auto retro deltas'), disabled: false, route: 'payroll-retro' },
            { label: _t('Test Calculation'), icon: 'fa-flask', desc: _t('Sample data & validation'), disabled: false, route: 'payroll-test' },
            { label: _t('Batch Compute'), icon: 'fa-play-circle', desc: _t('Import & compute batches'), disabled: false, route: 'payroll-batch' },
            { label: _t('Batch Workflow'), icon: 'fa-filter', desc: _t('Payslip batches & runs'), disabled: false, route: 'payroll-batch-workflow' },
            { label: _t('Payslip List'), icon: 'fa-list', desc: _t('All payslips'), disabled: false, route: 'payroll-payslip' },
            { label: _t('Full and Final'), icon: 'fa-file-pdf-o', desc: _t('Final settlement report'), disabled: false, route: 'payroll-full-and-final' },
        ],
    },
    approval: {
        title: _t('Payroll Approval'),
        items: [
            { label: _t('Pending Queue'), icon: 'fa-clock-o', desc: _t('Approve current period'), disabled: false, route: 'approval-pending' },
            { label: _t('History'), icon: 'fa-history', desc: _t('Past approvals & audits'), disabled: false, route: 'approval-history' },
            { label: _t('Rules'), icon: 'fa-gavel', desc: _t('Validation & thresholds'), disabled: false, route: 'approval-rules' },
        ],
    },
    pay_salary: {
        title: _t('Pay Salary'),
        items: [
            { label: _t('Bank Export'), icon: 'fa-bank', desc: _t('Generate payment files'), disabled: false, route: 'pay-salary-bank' },
            { label: _t('Payments'), icon: 'fa-money', desc: _t('Review payments'), disabled: false, route: 'pay-salary-payments' },
            { label: _t('Journals'), icon: 'fa-book', desc: _t('Accounting entries'), disabled: false, route: 'pay-salary-journals' },
        ],
    },
    attendance: {
        title: _t('Attendance & Workforce'),
        items: [
            { label: _t('Workforce Dashboard'), icon: 'fa-tachometer', desc: _t('KPI overview & analytics'), disabled: false, route: 'wf-dashboard' },
            { label: _t('Live Attendance'), icon: 'fa-wifi', desc: _t('Real-time check-in feed'), disabled: false, route: 'wf-live-attendance' },
            { label: _t('Timecards'), icon: 'fa-clock-o', desc: _t('Visual Gantt timeline'), disabled: false, route: 'wf-timecards' },
            { label: _t('Shift Roster'), icon: 'fa-calendar', desc: _t('Weekly shift grid'), disabled: false, route: 'wf-shift-roster' },
            { label: _t('Payroll Report'), icon: 'fa-bar-chart', desc: _t('Employee pay run comparison'), disabled: false, route: 'wf-payroll-report' },
            { label: _t('Overtime Rules'), icon: 'fa-balance-scale', desc: _t('Rate rules & applicability'), disabled: false, route: 'wf-overtime-rules' },
            { label: _t('Shift Templates'), icon: 'fa-clone', desc: _t('Reusable shift patterns'), disabled: false, route: 'wf-shift-templates' },
            { label: _t('Leave Dashboard'), icon: 'fa-leaf', desc: _t('Leave overview'), disabled: false, route: 'leaves-dashboard' },
        ],
    },
    overtime: {
        title: _t('Overtime'),
        items: [
            { label: _t('Request Overtime'), icon: 'fa-send', desc: _t('Submit overtime request'), disabled: false, route: 'overtime-request' },
            { label: _t('Approve Overtime'), icon: 'fa-check-square', desc: _t('Manager approval queue'), disabled: false, route: 'overtime-approve' },
            { label: _t('Overtime Policy/Rules'), icon: 'fa-balance-scale', desc: _t('Configure rates and caps'), disabled: false, route: 'overtime-rules' },
            { label: _t('Overtime Analytics'), icon: 'fa-bar-chart', desc: _t('Hours and costs overview'), disabled: false, route: 'overtime-analytics' },
            { label: _t('Overtime Settings'), icon: 'fa-cog', desc: _t('Geofence/reasons & defaults'), disabled: false, route: 'overtime-settings' },
        ],
    },
    shift: {
        title: _t('Shift'),
        items: [
            { label: _t('Shift Planning'), icon: 'fa-calendar', desc: _t('Plan and manage shifts'), disabled: false, route: 'shift-calendar' },
            { label: _t('Shift Templates'), icon: 'fa-clone', desc: _t('Reusable shift patterns'), disabled: false, route: 'shift-templates' },
            { label: _t('Shift Calendar'), icon: 'fa-calendar-check-o', desc: _t('My shift calendar'), disabled: false, route: 'shift-my-calendar' },
            { label: _t('Shift Settings'), icon: 'fa-sliders', desc: _t('Locations, geofence, reasons'), disabled: false, route: 'shift-settings' },
        ],
    },
    timesheet: {
        title: _t('Timesheet'),
        items: [
            { label: _t('My Timesheets'), icon: 'fa-table', desc: _t('Enter and submit hours'), disabled: false, route: 'timesheet-mine' },
            { label: _t('Timesheet Approvals'), icon: 'fa-check', desc: _t('Manager validation queue'), disabled: false, route: 'timesheet-approvals' },
            { label: _t('Timesheet Reports'), icon: 'fa-area-chart', desc: _t('Pivot/list by employee'), disabled: false, route: 'timesheet-reports' },
            { label: _t('Timesheet Settings'), icon: 'fa-cog', desc: _t('Period locks and rules'), disabled: false, route: 'timesheet-settings' },
        ],
    },
    leaves: {
        title: _t('Leaves'),
        items: [
            { label: _t('Leave Dashboard'), icon: 'fa-dashboard', desc: _t('Leave overview'), disabled: false, route: 'leaves-dashboard' },
            { label: _t('Accrual Plan'), icon: 'fa-list-alt', desc: _t('Accrual policies'), disabled: false, route: 'leaves-accrual' },
            { label: _t('Public Holidays'), icon: 'fa-calendar', desc: _t('Holiday calendar'), disabled: false, route: 'leaves-public-holidays' },
            { label: _t('Approvals'), icon: 'fa-check-square-o', desc: _t('Leave requests'), disabled: false, route: 'leaves-approvals' },
        ],
    },
    govt: {
        title: _t('Government Reports'),
        items: [
            { label: _t('Monthly Generated Tax Reports'), icon: 'fa-calendar', desc: _t('Báo cáo thuế tháng'), disabled: false, route: 'govt-monthly-generated', className: 'tertiary-card-wide' },
            { label: _t('BHXH630'), icon: 'fa-file-excel-o', desc: _t('Ốm đau/Thai sản'), disabled: false, route: 'govt-bhxh630' },
            { label: _t('BHXHDSTK01-DV_595'), icon: 'fa-file-excel-o', desc: _t('Mẫu 595'), disabled: false, route: 'govt-bhxhdstk01' },
            { label: _t('Bảng kê D01-TS'), icon: 'fa-file-excel-o', desc: _t('D01-TS'), disabled: false, route: 'govt-d01' },
            { label: _t('Báo giảm lao động'), icon: 'fa-file-excel-o', desc: _t('Giảm LĐ'), disabled: false, route: 'govt-giam' },
            { label: _t('Báo tăng lao động'), icon: 'fa-file-excel-o', desc: _t('Tăng LĐ'), disabled: false, route: 'govt-tang' },
        ],
    },
    workforce_planning: {
        title: _t('Workforce Planning'),
        items: [
            { label: _t('Planning Scenarios'), icon: 'fa-cubes', desc: _t('Salary simulation & forecasting'), disabled: false, route: 'wfp-scenarios' },
            { label: _t('Employee Forecasts'), icon: 'fa-users', desc: _t('Per-employee cost projections'), disabled: false, route: 'wfp-forecasts' },
            { label: _t('Tag Components'), icon: 'fa-tags', desc: _t('Classify formula components'), disabled: false, route: 'wfp-tagging' },
            { label: _t('Pay Grades'), icon: 'fa-signal', desc: _t('Salary bands & compa-ratios'), disabled: false, route: 'wfp-pay-grades' },
            { label: _t('Merit Matrix'), icon: 'fa-th', desc: _t('Performance × compa-ratio grid'), disabled: false, route: 'wfp-merit-matrix' },
            { label: _t('Compensation Cycles'), icon: 'fa-refresh', desc: _t('Budget → worksheets → approval'), disabled: false, route: 'wfp-comp-cycles' },
        ],
    },
};

const bindWorkflow = () => {
    let workflow = document.querySelector('.circular-workflow');
    if (!workflow) {
        return;
    }

    // If already bound (e.g., when coming back via breadcrumbs), clone to drop old listeners
    if (workflow.dataset.hrFlowBound) {
        const clone = workflow.cloneNode(true);
        workflow.parentNode.replaceChild(clone, workflow);
        workflow = clone;
    }
    workflow.dataset.hrFlowBound = '1';

    const secondaryAttendance = workflow.querySelector('.secondary-badges-attendance');
    const secondaryPayrollConfig = workflow.querySelector('.secondary-badges-payroll-config');
    const secondaryPayroll = workflow.querySelector('.secondary-badges-payroll');
    const secondaryApproval = workflow.querySelector('.secondary-badges-approval');
    const secondaryPaySalary = workflow.querySelector('.secondary-badges-pay-salary');
    const secondaryGovt = workflow.querySelector('.secondary-badges-govt');
    const secondaryAll = [
        secondaryAttendance,
        secondaryPayrollConfig,
        secondaryPayroll,
        secondaryApproval,
        secondaryPaySalary,
        secondaryGovt,
    ].filter(Boolean);
    const attendance = workflow.querySelector('.badge-attendance');
    const payrollConfig = workflow.querySelector('.badge-payroll-config');
    const payroll = workflow.querySelector('.badge-payroll');
    const approval = workflow.querySelector('.badge-approval');
    const paySalary = workflow.querySelector('.badge-pay-salary');
    const government = workflow.querySelector('.badge-government');

    // Tertiary panel elements
    const panel = document.getElementById('tertiary-panel');
    const panelTitle = document.getElementById('tertiary-panel-title');
    const panelItems = document.getElementById('tertiary-items');
    const panelClose = document.getElementById('tertiary-panel-close');

    // Hard-disable pointer events on the containers themselves
    secondaryAll.forEach((sec) => {
        if (sec) {
            sec.style.pointerEvents = 'none';
        }
    });

    // Check admin status once
    const adminCheck = user.hasGroup('base.group_system').catch(() => false);

    let isRestoring = false;

    const runTertiaryAction = async (route, closePanelOnSuccess = true) => {
        try {
            const action = await callModel('hr.flow.wizard', 'get_tertiary_action', [route]);
            if (action && action.type) {
                doAction(action);
                if (closePanelOnSuccess && action.target !== 'new') {
                    closePanel();
                }
            }
        } catch (e) {
            console.error('HR Flow: failed to run tertiary action', route, e);
        }
    };

    const openGovtMonthlyDialog = () => {
        // Create a simple modal for monthly government reports
        const existing = document.getElementById('govt-monthly-modal');
        if (existing) {
            existing.remove();
        }

        const buttons = [
            { label: _t('Download BHXH630'), route: 'govt-monthly-bhxh630' },
            { label: _t('Download BHXHDSTK01-DV_595'), route: 'govt-monthly-bhxhdstk01' },
            { label: _t('Download Bảng kê D01-TS'), route: 'govt-monthly-d01' },
            { label: _t('Download Báo giảm lao động'), route: 'govt-monthly-giam' },
            { label: _t('Download Báo tăng lao động'), route: 'govt-monthly-tang' },
        ];

        const overlay = document.createElement('div');
        overlay.id = 'govt-monthly-modal';
        overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);z-index:2000;display:flex;align-items:center;justify-content:center;';

        const dialog = document.createElement('div');
        dialog.className = 'govt-monthly-modal';
        dialog.style.cssText = 'background:#fff;border-radius:12px;padding:24px;min-width:400px;max-width:600px;box-shadow:0 20px 60px rgba(0,0,0,0.3);';

        const header = document.createElement('div');
        header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;';
        header.innerHTML = `<h3 style="margin:0;font-size:18px;font-weight:700;">${_t('Monthly Generated Tax Reports')}</h3>`;

        const closeBtn = document.createElement('button');
        closeBtn.style.cssText = 'background:#f1f5f9;border:none;border-radius:50%;width:36px;height:36px;cursor:pointer;display:flex;align-items:center;justify-content:center;';
        closeBtn.innerHTML = '<i class="fa fa-times"></i>';
        closeBtn.addEventListener('click', () => overlay.remove());
        header.appendChild(closeBtn);

        const content = document.createElement('div');
        content.className = 'govt-monthly-dialog';

        buttons.forEach((btn) => {
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'govt-monthly-button';
            button.innerHTML = `<i class="fa fa-file-excel-o"></i><span>${btn.label}</span>`;
            button.addEventListener('click', () => runTertiaryAction(btn.route, false));
            content.appendChild(button);
        });

        dialog.appendChild(header);
        dialog.appendChild(content);
        overlay.appendChild(dialog);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.remove();
        });
        document.body.appendChild(overlay);
    };

    const openPanel = async (key, ctx = {}) => {
        if (!panel) return;
        const data = tertiaryData[key] || { title: 'Quick Actions', items: [] };
        const isAdmin = await adminCheck;
        const items = isAdmin ? data.items : data.items.filter((item) => !adminRoutes.has(item.route));
        panelTitle.textContent = data.title;
        panelItems.innerHTML = '';
        items.forEach((item) => {
            const card = document.createElement('div');
            card.className = 'tertiary-card' + (item.disabled ? ' is-disabled' : '');
            if (item.className) {
                item.className.split(' ').forEach((cls) => card.classList.add(cls));
            }
            card.innerHTML =
                '<i class="fa ' + item.icon + ' tertiary-card-icon"></i>' +
                '<p class="tertiary-card-title">' + item.label + '</p>' +
                '<p class="tertiary-card-desc">' + item.desc + '</p>';
            if (item.disabled) {
                card.title = 'Access required';
            } else if (item.route) {
                card.addEventListener('click', () => {
                    if (!isRestoring) {
                        saveState(ctx.primary || key, ctx.secondary || item.route, key);
                    }
                    if (item.route === 'govt-monthly-generated') {
                        openGovtMonthlyDialog();
                        return;
                    }
                    runTertiaryAction(item.route, true);
                });
                card.style.cursor = 'pointer';
                card.title = 'Open';
            }
            panelItems.appendChild(card);
        });
        panel.classList.remove('hidden');
        panel.classList.add('open');
        if (!isRestoring) {
            saveState(ctx.primary || key, ctx.secondary || null, key);
        }
    };

    const closePanel = (doClear = false) => {
        if (!panel) return;
        panel.classList.remove('open');
        panel.classList.add('hidden');
        if (doClear) {
            clearState();
        }
    };

    if (panelClose) {
        panelClose.addEventListener('click', () => closePanel(true));
        panelClose.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                closePanel(true);
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closePanel(true);
    });

    // Bind tertiary panel data-attribute click handlers
    workflow.querySelectorAll('[data-tertiary]').forEach((el) => {
        const handler = (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            const key = el.getAttribute('data-tertiary');
            openPanel(key);
        };
        el.addEventListener('click', handler);
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                handler(e);
            }
        });
    });

    const hideAllSecondary = (alsoClear = false) => {
        secondaryAll.forEach((sec) => sec && sec.classList.add('hide-secondary'));
        if (alsoClear) {
            closePanel(true);
        }
    };
    const showSecondary = (sec) => {
        if (sec) sec.classList.remove('hide-secondary');
    };

    // Start hidden
    hideAllSecondary();

    // CLICK-ONLY INTERACTIONS

    // 1. Attendance: Click to open tertiary panel directly (tiles, no circles)
    if (attendance) {
        attendance.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('attendance', { primary: 'attendance' });
        });
    }

    // 2. Payroll Configuration: Click to open tertiary panel directly
    if (payrollConfig) {
        payrollConfig.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('payroll_config', { primary: 'payroll_config' });
        });
    }

    // 3. Payroll: Click to open tertiary panel directly
    if (payroll) {
        payroll.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('payroll', { primary: 'payroll' });
        });
    }

    // 4. Approval: Click to open tertiary panel
    if (approval) {
        approval.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('approval', { primary: 'approval' });
        });
    }

    // 5. Pay Salary: Click to open tertiary panel directly
    if (paySalary) {
        paySalary.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('pay_salary', { primary: 'pay_salary' });
        });
    }

    // 6. Government: Click to open tertiary panel directly
    if (government) {
        government.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('govt', { primary: 'govt' });
        });
    }

    // 7. Workforce Planning: Click to open tertiary panel directly
    const workforcePlanning = workflow.querySelector('.badge-workforce-planning');
    if (workforcePlanning) {
        workforcePlanning.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            openPanel('workforce_planning', { primary: 'workforce_planning' });
        });
    }

    // 8. Analytics: Click to open HR Analytics Dashboard directly
    const analytics = workflow.querySelector('.badge-analytics');
    if (analytics) {
        analytics.addEventListener('click', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.stopImmediatePropagation) {
                e.stopImmediatePropagation();
            }
            hideAllSecondary(true);
            try {
                const action = await callModel('hr.flow.wizard', 'get_tertiary_action', ['analytics-dashboard']);
                if (action && action.type) {
                    doAction(action);
                    saveState('analytics', null, null);
                }
            } catch (err) {
                console.error('HR Flow: analytics action failed', err);
            }
        });
    }

    // Restore last state if any
    const restoreState = () => {
        const state = loadState();
        if (!state || (!state.primary && !state.panel)) {
            return;
        }
        isRestoring = true;
        hideAllSecondary();
        if (state.primary === 'attendance' && secondaryAttendance) {
            showSecondary(secondaryAttendance);
            if (state.panel) {
                openPanel(state.panel, { primary: 'attendance', secondary: state.secondary || state.panel });
            }
        } else if (state.panel) {
            openPanel(state.panel, { primary: state.primary, secondary: state.secondary });
        }
        isRestoring = false;
    };
    restoreState();
};

whenReady(() => {
    // Initial bind
    bindWorkflow();

    // Rebind if the form is re-rendered (e.g., returning via breadcrumbs)
    let rebindTimer;
    const observer = new MutationObserver(() => {
        clearTimeout(rebindTimer);
        rebindTimer = setTimeout(() => {
            const workflow = document.querySelector('.circular-workflow');
            if (workflow && !workflow.dataset.hrFlowBound) {
                bindWorkflow();
            }
        }, 100);
    });
    observer.observe(document.body, { childList: true, subtree: true });
});
