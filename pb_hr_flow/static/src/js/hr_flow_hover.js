/** HR Flow hover & tertiary panel interactions */
odoo.define('pb_hr_flow.hr_flow_hover', function (require) {
    'use strict';
    const domReady = require('web.dom_ready');
    const rpc = require('web.rpc');
    const core = require('web.core');

    domReady(function () {
        console.log('[HR Flow] JS loaded');

        const bindWorkflow = () => {
            const workflow = document.querySelector('.circular-workflow');
            if (!workflow || workflow.dataset.hrFlowBound) {
                return;
            }
            workflow.dataset.hrFlowBound = '1';
            console.log('[HR Flow] Workflow found and bound');

            const secondary = workflow.querySelector('.secondary-badges');
            const nonAttendance = workflow.querySelectorAll('.primary-badge:not(.badge-attendance), .center-badge');
            const attendance = workflow.querySelector('.badge-attendance');

            // Tertiary panel data
            const panel = document.getElementById('tertiary-panel');
            const panelTitle = document.getElementById('tertiary-panel-title');
            const panelItems = document.getElementById('tertiary-items');
            const panelClose = document.getElementById('tertiary-panel-close');

            console.log('[HR Flow] Workflow found, binding handlers');

            const tertiaryData = {
                overtime: {
                    title: 'Overtime',
                    items: [
                        { label: 'Request Overtime', icon: 'fa-send', desc: 'Submit overtime request', disabled: false, route: 'overtime-request' },
                        { label: 'Approve Overtime', icon: 'fa-check-square', desc: 'Manager approval queue', disabled: false, route: 'overtime-approve' },
                        { label: 'Overtime Policy/Rules', icon: 'fa-balance-scale', desc: 'Configure rates and caps', disabled: false, route: 'overtime-rules' },
                        { label: 'Overtime Schedules', icon: 'fa-calendar-plus-o', desc: 'Plan OT by date/shift', disabled: false, route: 'overtime-schedules' },
                        { label: 'Overtime Analytics', icon: 'fa-bar-chart', desc: 'Hours and costs overview', disabled: false, route: 'overtime-analytics' },
                        { label: 'Overtime Settings', icon: 'fa-cog', desc: 'Geofence/reasons & defaults', disabled: false, route: 'overtime-settings' },
                    ],
                },
                shift: {
                    title: 'Shift',
                    items: [
                        { label: 'Shift Calendar', icon: 'fa-calendar', desc: 'Assign and manage shifts', disabled: false, route: 'shift-calendar' },
                        { label: 'Shift Templates', icon: 'fa-clone', desc: 'Reusable shift patterns', disabled: false, route: 'shift-templates' },
                        { label: 'Shift Swap/Requests', icon: 'fa-exchange', desc: 'Employee swap/change requests', disabled: false, route: 'shift-swap' },
                        { label: 'Shift Compliance', icon: 'fa-shield', desc: 'Conflicts and rest checks', disabled: false, route: 'shift-compliance' },
                        { label: 'Shift Attendance', icon: 'fa-clock-o', desc: 'Attendance filtered by shift', disabled: false, route: 'shift-attendance' },
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
            };

        const openPanel = (key) => {
            if (!panel) return;
            const data = tertiaryData[key] || { title: 'Quick Actions', items: [] };
            panelTitle.textContent = data.title;
            panelItems.innerHTML = '';
            data.items.forEach((item) => {
                const card = document.createElement('div');
                card.className = 'tertiary-card' + (item.disabled ? ' is-disabled' : '');
                card.innerHTML =
                    '<i class="fa ' + item.icon + ' tertiary-card-icon"></i>' +
                    '<p class="tertiary-card-title">' + item.label + '</p>' +
                    '<p class="tertiary-card-desc">' + item.desc + '</p>';
                if (item.disabled) {
                    card.title = 'Access required';
                } else if (item.route) {
                    card.addEventListener('click', function () {
                        rpc.query({
                            model: 'hr.flow.wizard',
                            method: 'get_tertiary_action',
                            args: [item.route],
                        }).then((action) => {
                            if (action && action.type) {
                                // Open full screen (target provided by server)
                                core.bus.trigger('do-action', { action: action });
                                closePanel();
                            } else {
                                console.warn('[HR Flow] No action resolved for', item.route);
                            }
                        }).catch((err) => {
                            console.error('[HR Flow] Failed to resolve action', item.route, err);
                        });
                    });
                    card.style.cursor = 'pointer';
                    card.title = 'Open';
                }
                panelItems.appendChild(card);
            });
            panel.classList.remove('hidden');
            panel.classList.add('open');
            console.log('[HR Flow] Panel opened for', key);
        };

        const closePanel = () => {
            if (!panel) return;
            panel.classList.remove('open');
            panel.classList.add('hidden');
        };

        if (panelClose) {
            panelClose.addEventListener('click', closePanel);
            panelClose.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    closePanel();
                }
            });
        }

        // no details button anymore

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closePanel();
        });

        workflow.querySelectorAll('[data-tertiary]').forEach((el) => {
            const handler = (e) => {
                e.preventDefault();
                const key = el.getAttribute('data-tertiary');
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

        const hideSecondary = () => {
            if (secondary) secondary.classList.add('hide-secondary');
        };
        const showSecondary = () => {
            if (secondary) secondary.classList.remove('hide-secondary');
        };

        nonAttendance.forEach((el) => {
            el.addEventListener('mouseenter', hideSecondary);
            el.addEventListener('mouseleave', showSecondary);
        });

        if (attendance) {
            attendance.addEventListener('mouseenter', showSecondary);
        }

        workflow.addEventListener('mouseleave', showSecondary);
        };

        // Initial bind
        bindWorkflow();

        // Rebind if the form is re-rendered (e.g., returning via breadcrumbs)
        const observer = new MutationObserver(() => bindWorkflow());
        observer.observe(document.body, { childList: true, subtree: true });
    });
});
