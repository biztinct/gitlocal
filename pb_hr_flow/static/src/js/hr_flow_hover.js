/** HR Flow hover & tertiary panel interactions */
odoo.define('pb_hr_flow.hr_flow_hover', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');
    const rpc = require('web.rpc');
    const core = require('web.core');
    const session = require('web.session');
    const Dialog = require('web.Dialog');

    domReady(function () {
        console.log('[HR Flow] JS loaded');
        const STORAGE_KEY = 'hr_flow_state';

        const loadState = () => {
            try {
                return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
            } catch (e) {
                console.warn('[HR Flow] Failed to load state', e);
                return null;
            }
        };

        const saveState = (primary, secondary, panelKey) => {
            const payload = { primary: primary || null, secondary: secondary || null, panel: panelKey || null };
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
            console.log('[HR Flow] State saved', payload);
        };

        const clearState = () => {
            sessionStorage.removeItem(STORAGE_KEY);
            console.log('[HR Flow] State cleared');
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
            console.log('[HR Flow] Workflow found and bound');

            const secondaryAttendance = workflow.querySelector('.secondary-badges-attendance');
            const secondaryPayroll = workflow.querySelector('.secondary-badges-payroll');
            const secondaryApproval = workflow.querySelector('.secondary-badges-approval');
            const secondaryPaySalary = workflow.querySelector('.secondary-badges-pay-salary');
            const secondaryGovt = workflow.querySelector('.secondary-badges-govt');
            const secondaryAll = [secondaryAttendance, secondaryPayroll, secondaryApproval, secondaryPaySalary, secondaryGovt].filter(Boolean);
            const nonAttendance = workflow.querySelectorAll('.primary-badge:not(.badge-attendance), .center-badge');
            const attendance = workflow.querySelector('.badge-attendance');
            const payroll = workflow.querySelector('.badge-payroll');
            const approval = workflow.querySelector('.badge-approval');
            const paySalary = workflow.querySelector('.badge-pay-salary');
            const government = workflow.querySelector('.badge-government');

            // Tertiary panel data
            const panel = document.getElementById('tertiary-panel');
            const panelTitle = document.getElementById('tertiary-panel-title');
            const panelItems = document.getElementById('tertiary-items');
            const panelClose = document.getElementById('tertiary-panel-close');

            console.log('[HR Flow] Workflow found, binding handlers');
            console.log('[HR Flow] Primaries found', {
                attendance: !!attendance,
                payroll: !!payroll,
                approval: !!approval,
                paySalary: !!paySalary,
                government: !!government,
            });
            console.log('[HR Flow] Secondary containers', {
                attendance: !!secondaryAttendance,
                payroll: !!secondaryPayroll,
                approval: !!secondaryApproval,
                paySalary: !!secondaryPaySalary,
                government: !!secondaryGovt,
            });

            // Hard-disable pointer events on the containers themselves (only badges should receive events)
            secondaryAll.forEach((sec) => {
                if (sec) {
                    sec.style.pointerEvents = 'none';
                }
            });

            const tertiaryData = {
                payroll: {
                    title: 'Payroll',
                    items: [
                        { label: 'Connector', icon: 'fa-plug', desc: 'HRIS/Excel connectors', disabled: false, route: 'payroll-connector' },
                        { label: 'Configure Salary', icon: 'fa-sliders', desc: 'Formulas & structures', disabled: false, route: 'payroll-config' },
                        { label: 'Payslip Configuration', icon: 'fa-cogs', desc: 'Identifiers & labels', disabled: false, route: 'payroll-payslip-config' },
                        { label: 'Employee/Contract Mapping', icon: 'fa-exchange', desc: 'Map fields to components', disabled: false, route: 'payroll-employee-contract-mapping' },
                        { label: 'Mid-Cycle Mapping', icon: 'fa-random', desc: 'Map mid-cycle to end-cycle', disabled: false, route: 'payroll-cycle-mapping' },
                        { label: 'Test Calculation', icon: 'fa-flask', desc: 'Sample data & validation', disabled: false, route: 'payroll-test' },
                        { label: 'Batch Compute', icon: 'fa-play-circle', desc: 'Import & compute batches', disabled: false, route: 'payroll-batch' },
                        { label: 'Batch Workflow', icon: 'fa-filter', desc: 'Payslip batches & runs', disabled: false, route: 'payroll-batch-workflow' },
                        { label: 'Payslip List', icon: 'fa-list', desc: 'All payslips', disabled: false, route: 'payroll-payslip' },
                        { label: 'Full and Final', icon: 'fa-file-pdf-o', desc: 'Final settlement report', disabled: false, route: 'payroll-full-and-final' },
                        { label: 'Salary Analytics', icon: 'fa-bar-chart', desc: 'Component analysis & insights', disabled: false, route: 'payroll-salary-analytics' },
                    ],
                },
                approval: {
                    title: 'Payroll Approval',
                    items: [
                        { label: 'Pending Queue', icon: 'fa-clock-o', desc: 'Approve current period', disabled: false, route: 'approval-pending' },
                        { label: 'History', icon: 'fa-history', desc: 'Past approvals & audits', disabled: false, route: 'approval-history' },
                        { label: 'Rules', icon: 'fa-gavel', desc: 'Validation & thresholds', disabled: false, route: 'approval-rules' },
                    ],
                },
                pay_salary: {
                    title: 'Pay Salary',
                    items: [
                        { label: 'Bank Export', icon: 'fa-bank', desc: 'Generate payment files', disabled: false, route: 'pay-salary-bank' },
                        { label: 'Payments', icon: 'fa-money', desc: 'Review payments', disabled: false, route: 'pay-salary-payments' },
                        { label: 'Journals', icon: 'fa-book', desc: 'Accounting entries', disabled: false, route: 'pay-salary-journals' },
                    ],
                },
                overtime: {
                    title: 'Overtime',
                    items: [
                        { label: 'Request Overtime', icon: 'fa-send', desc: 'Submit overtime request', disabled: false, route: 'overtime-request' },
                        { label: 'Approve Overtime', icon: 'fa-check-square', desc: 'Manager approval queue', disabled: false, route: 'overtime-approve' },
                        { label: 'Overtime Policy/Rules', icon: 'fa-balance-scale', desc: 'Configure rates and caps', disabled: false, route: 'overtime-rules' },
                        { label: 'Overtime Analytics', icon: 'fa-bar-chart', desc: 'Hours and costs overview', disabled: false, route: 'overtime-analytics' },
                        { label: 'Overtime Settings', icon: 'fa-cog', desc: 'Geofence/reasons & defaults', disabled: false, route: 'overtime-settings' },
                    ],
                },
                shift: {
                    title: 'Shift',
                    items: [
                        { label: 'Shift Planning', icon: 'fa-calendar', desc: 'Plan and manage shifts', disabled: false, route: 'shift-calendar' },
                        { label: 'Shift Templates', icon: 'fa-clone', desc: 'Reusable shift patterns', disabled: false, route: 'shift-templates' },
                        { label: 'Shift Calendar', icon: 'fa-calendar-check-o', desc: 'My shift calendar', disabled: false, route: 'shift-my-calendar' },
                        { label: 'Shift Settings', icon: 'fa-sliders', desc: 'Locations, geofence, reasons', disabled: false, route: 'shift-settings' },
                    ],
                },
                timesheet: {
                    title: 'Timesheet',
                    items: [
                        { label: 'My Timesheets', icon: 'fa-table', desc: 'Enter and submit hours', disabled: false, route: 'timesheet-mine' },
                        { label: 'Timesheet Approvals', icon: 'fa-check', desc: 'Manager validation queue', disabled: false, route: 'timesheet-approvals' },
                        { label: 'Timesheet Reports', icon: 'fa-area-chart', desc: 'Pivot/list by employee', disabled: false, route: 'timesheet-reports' },
                        { label: 'Timesheet Settings', icon: 'fa-cog', desc: 'Period locks and rules', disabled: false, route: 'timesheet-settings' },
                    ],
                },
                leaves: {
                    title: 'Leaves',
                    items: [
                        { label: 'Leave Dashboard', icon: 'fa-dashboard', desc: 'Leave overview', disabled: false, route: 'leaves-dashboard' },
                        { label: 'Accrual Plan', icon: 'fa-list-alt', desc: 'Accrual policies', disabled: false, route: 'leaves-accrual' },
                        { label: 'Public Holidays', icon: 'fa-calendar', desc: 'Holiday calendar', disabled: false, route: 'leaves-public-holidays' },
                        { label: 'Approvals', icon: 'fa-check-square-o', desc: 'Leave requests', disabled: false, route: 'leaves-approvals' },
                    ],
                },
                govt: {
                    title: 'Government Reports',
                    items: [
                        { label: 'Monthly Generated Tax Reports', icon: 'fa-calendar', desc: 'Báo cáo thuế tháng', disabled: false, route: 'govt-monthly-generated', className: 'tertiary-card-wide' },
                        { label: 'BHXH630', icon: 'fa-file-excel-o', desc: 'Ốm đau/Thai sản', disabled: false, route: 'govt-bhxh630' },
                        { label: 'BHXHDSTK01-DV_595', icon: 'fa-file-excel-o', desc: 'Mẫu 595', disabled: false, route: 'govt-bhxhdstk01' },
                        { label: 'Bảng kê D01-TS', icon: 'fa-file-excel-o', desc: 'D01-TS', disabled: false, route: 'govt-d01' },
                        { label: 'Báo giảm lao động', icon: 'fa-file-excel-o', desc: 'Giảm LĐ', disabled: false, route: 'govt-giam' },
                        { label: 'Báo tăng lao động', icon: 'fa-file-excel-o', desc: 'Tăng LĐ', disabled: false, route: 'govt-tang' },
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
                console.log('[HR Flow] Action resolved for route', route, action);
                if (action && action.type) {
                    action.context = Object.assign({}, session.user_context || {}, action.context || {});
                    const payload = { action: action, options: {} };
                    console.log('[HR Flow] Triggering do-action payload', payload);
                    core.bus.trigger('do-action', payload);
                    if (closePanelOnSuccess && action.target !== 'new') {
                        closePanel();
                    }
                } else {
                    console.warn('[HR Flow] No action resolved for', route, action);
                }
            }).catch((err) => {
                console.error('[HR Flow] Failed to resolve action', route, err);
            });
        };

        const openGovtMonthlyDialog = () => {
            if (monthlyDialog) {
                monthlyDialog.close();
                monthlyDialog = null;
            }
            const $content = $('<div/>', { class: 'govt-monthly-dialog' });
            const buttons = [
                { label: 'Download BHXH630', route: 'govt-monthly-bhxh630' },
                { label: 'Download BHXHDSTK01-DV_595', route: 'govt-monthly-bhxhdstk01' },
                { label: 'Download Bảng kê D01-TS', route: 'govt-monthly-d01' },
                { label: 'Download Báo giảm lao động', route: 'govt-monthly-giam' },
                { label: 'Download Báo tăng lao động', route: 'govt-monthly-tang' },
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
                title: 'Monthly Generated Tax Reports',
                $content: $content,
                buttons: [{ text: 'CLOSE', close: true }],
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
            panelTitle.textContent = data.title;
            panelItems.innerHTML = '';
                data.items.forEach((item) => {
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
                            console.log('[HR Flow] Tertiary card click -> route', item.route);
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
            console.log('[HR Flow] Panel opened for', key, 'ctx', ctx);
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
                console.log('[HR Flow] Tertiary element clicked:', key);
                openPanel(key);
            };
            console.log('[HR Flow] Binding tertiary click', el.getAttribute('data-tertiary'));
            el.addEventListener('click', handler);
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    handler(e);
                }
            });
        });

        const hideAllSecondary = (alsoClear = false) => {
            console.log('[HR Flow] Hiding all secondary rings');
            secondaryAll.forEach((sec) => sec && sec.classList.add('hide-secondary'));
            if (alsoClear) {
                closePanel(true);
            }
        };
        const showSecondary = (sec) => {
            if (sec) sec.classList.remove('hide-secondary');
            console.log('[HR Flow] Showing secondary ring', sec && sec.className);
        };

        // Start hidden
        hideAllSecondary();

        // Debug: log any click inside workflow to ensure events are firing
        workflow.addEventListener('click', (e) => {
            console.log('[HR Flow] Workflow click detected on', e.target && e.target.className);
        });

        // CLICK-ONLY INTERACTIONS (No Hover)

        // 1. Attendance: Click to toggle secondary badges visibility
        if (attendance) {
            attendance.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
                console.log('[HR Flow] Attendance clicked - toggling secondary badges');
                // Toggle attendance secondary badges
                if (!secondaryAttendance) {
                    console.warn('[HR Flow] Attendance secondary container missing');
                    return;
                }
                console.log('[HR Flow] Attendance secondary class BEFORE', secondaryAttendance.className);
                if (secondaryAttendance.classList.contains('hide-secondary')) {
                    hideAllSecondary(true);
                    showSecondary(secondaryAttendance);
                } else {
                    hideAllSecondary(true);
                }
                console.log('[HR Flow] Attendance secondary class AFTER', secondaryAttendance.className);
            });
            console.log('[HR Flow] Attendance handler bound');
        }

        // 2. Payroll: Click to open tertiary panel directly
        if (payroll) {
            payroll.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
                console.log('[HR Flow] Payroll clicked - opening tertiary panel');
                hideAllSecondary(true);
                openPanel('payroll', { primary: 'payroll' });
            });
            console.log('[HR Flow] Payroll handler bound');
        }

        // 3. Approval: Click to open approval dashboard (direct action, not tertiary panel)
        if (approval) {
            approval.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
                console.log('[HR Flow] Approval clicked - opening approval dashboard');
                hideAllSecondary(true);
                rpc.query({
                    model: 'hr.flow.wizard',
                    method: 'get_tertiary_action',
                    args: ['approval-pending'],
                }).then((action) => {
                    console.log('[HR Flow] Approval action resolved', action);
                    if (action && action.type) {
                        action.context = Object.assign({}, session.user_context || {}, action.context || {});
                        const payload = { action: action, options: {} };
                        console.log('[HR Flow] Triggering approval do-action payload', payload);
                        core.bus.trigger('do-action', payload);
                        saveState('approval', null, null);
                    } else {
                        console.warn('[HR Flow] No action resolved for approval-pending', action);
                    }
                }).catch((err) => {
                    console.error('[HR Flow] Failed to resolve approval action', err);
                });
            });
            console.log('[HR Flow] Approval handler bound');
        }

        // 4. Pay Salary: Click to open tertiary panel directly
        if (paySalary) {
            paySalary.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
                console.log('[HR Flow] Pay Salary clicked - opening tertiary panel');
                hideAllSecondary(true);
                openPanel('pay_salary', { primary: 'pay_salary' });
            });
            console.log('[HR Flow] Pay Salary handler bound');
        }

        // 5. Government: Click to open tertiary panel directly
        if (government) {
            government.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
                console.log('[HR Flow] Government clicked - opening tertiary panel');
                hideAllSecondary(true);
                openPanel('govt', { primary: 'govt' });
            });
            console.log('[HR Flow] Government handler bound');
        }

        // 6. Analytics: Click to open HR Analytics Dashboard directly
        const analytics = workflow.querySelector('.badge-analytics');
        if (analytics) {
            analytics.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.stopImmediatePropagation) {
                    e.stopImmediatePropagation();
                }
                console.log('[HR Flow] Analytics clicked - opening analytics dashboard');
                hideAllSecondary(true);
                rpc.query({
                    model: 'hr.flow.wizard',
                    method: 'get_tertiary_action',
                    args: ['analytics-dashboard'],
                }).then((action) => {
                    console.log('[HR Flow] Analytics action resolved', action);
                    if (action && action.type) {
                        action.context = Object.assign({}, session.user_context || {}, action.context || {});
                        const payload = { action: action, options: {} };
                        console.log('[HR Flow] Triggering analytics do-action payload', payload);
                        core.bus.trigger('do-action', payload);
                        saveState('analytics', null, null);
                    } else {
                        console.warn('[HR Flow] No action resolved for analytics-dashboard', action);
                    }
                }).catch((err) => {
                    console.error('[HR Flow] Failed to resolve analytics action', err);
                });
            });
            console.log('[HR Flow] Analytics handler bound');
        }

        // Restore last state if any (runs after handlers are bound so helpers are in scope)
        const restoreState = () => {
            const state = loadState();
            if (!state || (!state.primary && !state.panel)) {
                return;
            }
            console.log('[HR Flow] Restoring state', state);
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
                    console.log('[HR Flow] Detected new workflow, rebinding');
                    bindWorkflow();
                }
            }, 100);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
});
