/** HR Flow hover & tertiary panel interactions */
odoo.define('pb_hr_flow.hr_flow_hover', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');
    const rpc = require('web.rpc');
    const core = require('web.core');
    const session = require('web.session');
    const Dialog = require('web.Dialog');

    domReady(function () {
        const STORAGE_KEY = 'hr_flow_state';
        const _t = core._t;
        const adminRoutes = new Set([
            'payroll-retro',
            'payroll-test',
            'pay-salary-payments',
            'pay-salary-journals',
        ]);
        const adminCheck = session.user_has_group('base.group_system').catch(function () { return false; });

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
            const nonAttendance = workflow.querySelectorAll('.primary-badge:not(.badge-attendance), .center-badge');
            const attendance = workflow.querySelector('.badge-attendance');
            const payrollConfig = workflow.querySelector('.badge-payroll-config');
            const payroll = workflow.querySelector('.badge-payroll');
            const approval = workflow.querySelector('.badge-approval');
            const paySalary = workflow.querySelector('.badge-pay-salary');
            const government = workflow.querySelector('.badge-government');

            // Tertiary panel data
            const panel = document.getElementById('tertiary-panel');
            const panelTitle = document.getElementById('tertiary-panel-title');
            const panelItems = document.getElementById('tertiary-items');
            const panelClose = document.getElementById('tertiary-panel-close');

            // Hard-disable pointer events on the containers themselves (only badges should receive events)
            secondaryAll.forEach((sec) => {
                if (sec) {
                    sec.style.pointerEvents = 'none';
                }
            });

            const tertiaryData = {
                payroll_config: {
                    title: _t('Payroll Configuration'),
                    items: [
                        { label: _t('Connector'), icon: 'fa-plug', desc: _t('HRIS/Excel connectors'), disabled: false, route: 'payroll-connector' },
                        { label: _t('Configure Salary'), icon: 'fa-sliders', desc: _t('Formulas & structures'), disabled: false, route: 'payroll-config' },
                        { label: _t('Payslip Configuration'), icon: 'fa-cogs', desc: _t('Identifiers & labels'), disabled: false, route: 'payroll-payslip-config' },
                        { label: _t('Employee/Contract Mapping'), icon: 'fa-exchange', desc: _t('Map fields to components'), disabled: false, route: 'payroll-employee-contract-mapping' },
                        { label: _t('Mid-Cycle Mapping'), icon: 'fa-random', desc: _t('Map mid-cycle to end-cycle'), disabled: false, route: 'payroll-cycle-mapping' },
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
            };

            let isRestoring = false;
            let monthlyDialog = null;

            const runTertiaryAction = (route, closePanelOnSuccess = true) => {
                rpc.query({
                    model: 'hr.flow.wizard',
                    method: 'get_tertiary_action',
                    args: [route],
                }).then((action) => {
                    if (action && action.type) {
                        action.context = Object.assign({}, session.user_context || {}, action.context || {});
                        const payload = { action: action, options: {} };
                        core.bus.trigger('do-action', payload);
                        if (closePanelOnSuccess && action.target !== 'new') {
                            closePanel();
                        }
                    }
                });
            };

            const openGovtMonthlyDialog = () => {
                if (monthlyDialog) {
                    monthlyDialog.close();
                    monthlyDialog = null;
                }
                const $content = $('<div/>', { class: 'govt-monthly-dialog' });
                const buttons = [
                    { label: _t('Download BHXH630'), route: 'govt-monthly-bhxh630' },
                    { label: _t('Download BHXHDSTK01-DV_595'), route: 'govt-monthly-bhxhdstk01' },
                    { label: _t('Download Bảng kê D01-TS'), route: 'govt-monthly-d01' },
                    { label: _t('Download Báo giảm lao động'), route: 'govt-monthly-giam' },
                    { label: _t('Download Báo tăng lao động'), route: 'govt-monthly-tang' },
                ];
                buttons.forEach((btn) => {
                    const $btn = $('<button/>', {
                        type: 'button',
                        class: 'govt-monthly-button',
                    });
                    $btn.append($('<i/>', { class: 'fa fa-file-excel-o' }));
                    $btn.append($('<span/>').text(btn.label));
                    $btn.on('click', () => runTertiaryAction(btn.route, false));
                    $content.append($btn);
                });
                monthlyDialog = new Dialog(null, {
                    title: _t('Monthly Generated Tax Reports'),
                    $content: $content,
                    buttons: [{ text: _t('CLOSE'), close: true }],
                    size: 'medium',
                });
                monthlyDialog.open();
                const applyDialogClass = () => {
                    if (monthlyDialog && monthlyDialog.$modal) {
                        monthlyDialog.$modal.addClass('govt-monthly-modal');
                    }
                };
                applyDialogClass();
                setTimeout(applyDialogClass, 0);
            };

            const openPanel = (key, ctx = {}) => {
                if (!panel) return;
                const data = tertiaryData[key] || { title: 'Quick Actions', items: [] };
                adminCheck.then(function (isAdmin) {
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
                            card.addEventListener('click', function () {
                                // Persist state so breadcrumb return restores this panel/secondary
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
                });
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

            // no details button anymore

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') closePanel(true);
            });

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

            // CLICK-ONLY INTERACTIONS (No Hover)

            // 1. Attendance: Click to toggle secondary badges visibility
            if (attendance) {
                attendance.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.stopImmediatePropagation) {
                        e.stopImmediatePropagation();
                    }
                    // Toggle attendance secondary badges
                    if (!secondaryAttendance) {
                        return;
                    }
                    if (secondaryAttendance.classList.contains('hide-secondary')) {
                        hideAllSecondary(true);
                        showSecondary(secondaryAttendance);
                    } else {
                        hideAllSecondary(true);
                    }
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

            // 4. Approval: Click to open approval dashboard (direct action, not tertiary panel)
            if (approval) {
                approval.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.stopImmediatePropagation) {
                        e.stopImmediatePropagation();
                    }
                    hideAllSecondary(true);
                    rpc.query({
                        model: 'hr.flow.wizard',
                        method: 'get_tertiary_action',
                        args: ['approval-pending'],
                    }).then((action) => {
                        if (action && action.type) {
                            action.context = Object.assign({}, session.user_context || {}, action.context || {});
                            const payload = { action: action, options: {} };
                            core.bus.trigger('do-action', payload);
                            saveState('approval', null, null);
                        }
                    });
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

            // 7. Analytics: Click to open HR Analytics Dashboard directly
            const analytics = workflow.querySelector('.badge-analytics');
            if (analytics) {
                analytics.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (e.stopImmediatePropagation) {
                        e.stopImmediatePropagation();
                    }
                    hideAllSecondary(true);
                    rpc.query({
                        model: 'hr.flow.wizard',
                        method: 'get_tertiary_action',
                        args: ['analytics-dashboard'],
                    }).then((action) => {
                        if (action && action.type) {
                            action.context = Object.assign({}, session.user_context || {}, action.context || {});
                            const payload = { action: action, options: {} };
                            core.bus.trigger('do-action', payload);
                            saveState('analytics', null, null);
                        }
                    });
                });
            }

            // Restore last state if any (runs after handlers are bound so helpers are in scope)
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

        // Initial bind
        bindWorkflow();

        // Rebind if the form is re-rendered (e.g., returning via breadcrumbs)
        // Use debounce to prevent infinite loop from MutationObserver
        let rebindTimer;
        const observer = new MutationObserver(() => {
            clearTimeout(rebindTimer);
            rebindTimer = setTimeout(() => {
                const workflow = document.querySelector('.circular-workflow');
                // Only rebind if workflow exists and is not already bound
                if (workflow && !workflow.dataset.hrFlowBound) {
                    bindWorkflow();
                }
            }, 100);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
});
