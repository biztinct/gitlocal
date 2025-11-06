odoo.define('pb_hr_payroll_demand.workforce_dashboard_action', function (require) {
    'use strict';

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');
    const rpc = require('web.rpc');
    const session = require('web.session');

    const _t = core._t;

    const WorkforceDashboardAction = AbstractAction.extend({
        template: 'pb_hr_payroll_demand.WorkforceDashboard',

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.actionContext = action.context || {};
            this.filters = {
                year: this.actionContext.default_year || false,
                capability: this.actionContext.default_capability_id || false,
                role: this.actionContext.default_role_id || false,
            };
            this.filterOptions = { years: [], capabilities: [], roles: [] };
            this.charts = {};
        },

        willStart: function () {
            return Promise.all([
                this._super.apply(this, arguments),
                rpc.query({
                    model: 'pb.workforce.demand.plan',
                    method: 'get_dashboard_filters',
                    args: [],
                }).then(result => {
                    this.filterOptions = result || {};
                }),
            ]);
        },

        start: function () {
            return this._super.apply(this, arguments).then(() => {
                this._renderFilters();
                setTimeout(() => this._refresh(), 350);
            });
        },

        events: {
            'click .pb-dashboard-refresh': '_onRefreshClick',
            'change select[data-filter="year"]': '_onFilterChange',
            'change select[data-filter="capability"]': '_onFilterChange',
            'change select[data-filter="role"]': '_onFilterChange',
        },

        _renderFilters: function () {
            const $year = this.$('select[data-filter="year"]');
            const $capability = this.$('select[data-filter="capability"]');
            const $role = this.$('select[data-filter="role"]');

            this._renderSelect($year, (this.filterOptions.years || []).map(year => ({
                value: year,
                label: year,
            })), _t('All Years'));
            this._renderSelect($capability, (this.filterOptions.capabilities || []).map(cap => ({
                value: cap.id,
                label: cap.name,
            })), _t('All Capabilities'));
            this._renderSelect($role, (this.filterOptions.roles || []).map(role => ({
                value: role.id,
                label: role.name,
            })), _t('All Roles'));

            if (this.filters.year) {
                $year.val(String(this.filters.year));
            }
            if (this.filters.capability) {
                $capability.val(String(this.filters.capability));
            }
            if (this.filters.role) {
                $role.val(String(this.filters.role));
            }
        },

        _renderSelect: function ($element, options, placeholder) {
            $element.empty();
            $element.append($('<option>', { value: '', text: placeholder || _t('All') }));
            options.forEach(option => {
                $element.append($('<option>', { value: option.value, text: option.label }));
            });
        },

        _refresh: function () {
            this.$el.addClass('o_loading');
            return rpc.query({
                model: 'pb.workforce.demand.plan',
                method: 'get_dashboard_snapshot',
                args: [],
                kwargs: this._getPayload(),
            }).then(data => {
                this._updateDashboard(data || {});
            }).finally(() => {
                this.$el.removeClass('o_loading');
            });
        },

        _getPayload: function () {
            const payload = {};
            if (this.filters.year) {
                payload.year = parseInt(this.filters.year, 10);
            }
            if (this.filters.capability) {
                payload.capability_id = parseInt(this.filters.capability, 10);
            }
            if (this.filters.role) {
                payload.role_id = parseInt(this.filters.role, 10);
            }
            return payload;
        },

        _updateDashboard: function (data) {
            this._updateMetrics(data.totals || {});
            this._updateStates(data.states || {});
            this._updateQuadrants(data.quadrants || {});
            this._updateVarianceTable(data.top_variances || []);
            this._renderTrendChart(data.month_series || []);
        },

        _updateMetrics: function (totals) {
            const formatter = new Intl.NumberFormat(this._getLocale(), { maximumFractionDigits: 0 });
            this.currencyName = totals.currency_name || this.currencyName || 'USD';
            const currencyFormatter = this._getCurrencyFormatter();

            const safeText = value => (value === undefined || value === null ? '0' : value);

            this.$('#pb-metric-plan-count').text(safeText(formatter.format(totals.plan_count || 0)));
            this.$('#pb-metric-role-count').text(safeText(formatter.format(totals.role_count || 0)));
            this.$('#pb-metric-capability-count').text(safeText(formatter.format(totals.capability_count || 0)));
            this.$('#pb-metric-total-headcount').text(safeText(formatter.format(totals.total_headcount || 0)));
            this.$('#pb-metric-total-cost').text(safeText(currencyFormatter(totals.total_cost || 0)));
            this.$('#pb-metric-variance').text(safeText(currencyFormatter(totals.variance_amount || 0)));
        },

        _updateStates: function (states) {
            this.$('#pb-plan-state-grid .pb-status-card').each(function () {
                const $card = $(this);
                const state = $card.data('state');
                const value = states[state] || 0;
                $card.find('.pb-status-value').text(value);
            });
        },

        _updateQuadrants: function (quadrants) {
            this.$('#pb-quadrant-grid .pb-segmentation-card').each(function () {
                const $card = $(this);
                const key = $card.data('quadrant');
                const value = quadrants[key] || 0;
                $card.find('.pb-segmentation-value').text(value);
            });
        },

        _updateVarianceTable: function (rows) {
            const $tbody = this.$('#pb-variance-table');
            $tbody.empty();
            if (!rows.length) {
                $tbody.append(
                    $('<tr>', { class: 'pb-empty-row' }).append(
                        $('<td>', { colspan: 6, text: _t('No significant variance detected.') })
                    )
                );
                return;
            }
            const currencyFormatter = this._getCurrencyFormatter();
            rows.forEach(row => {
                const $tr = $('<tr>');
                $tr.append($('<td>').text(row.plan_name));
                $tr.append($('<td>').text(row.role));
                $tr.append($('<td>').text(row.capability));
                $tr.append($('<td>', { class: 'text-end' }).text(currencyFormatter(row.variance_amount)));
                $tr.append($('<td>', { class: 'text-end' }).text(`${this._formatPercent(row.variance_percent)}%`));
                $tr.append($('<td>', { class: 'text-center' }).text(this._formatState(row.state)));
                $tbody.append($tr);
            });
        },

        _renderTrendChart: function (series) {
            if (typeof Chart === 'undefined') {
                console.warn('pb_hr_payroll_demand Chart.js still undefined');
                return;
            }
            const $canvas = this.$('#pb-demand-trend-chart');
            if (!$canvas.length) {
                console.warn('pb_hr_payroll_demand trend canvas missing');
                return;
            }
            const canvasEl = $canvas[0];
            const labels = series.map(item => item.month);
            const employees = series.map(item => item.employees || 0);
            const costs = series.map(item => item.cost || 0);

            const container = canvasEl.parentNode;
            const containerWidth = container ? (container.offsetWidth || container.clientWidth || 1024) : 1024;
            const desiredHeight = Math.max(container ? (container.offsetHeight || container.clientHeight || 320) : 320, 240);
            canvasEl.width = containerWidth;
            canvasEl.height = desiredHeight;
            canvasEl.style.width = containerWidth + 'px';
            canvasEl.style.height = desiredHeight + 'px';

            const context = canvasEl.getContext('2d');
            if (!context) {
                console.warn('pb_hr_payroll_demand canvas context not available');
                return;
            }

            window.requestAnimationFrame(() => {
                if (this.charts.trend) {
                    this.charts.trend.data.labels = labels;
                    this.charts.trend.data.datasets[0].data = employees;
                    this.charts.trend.data.datasets[1].data = costs;
                    this.charts.trend.update();
                    return;
                }

                this.charts.trend = new Chart(context, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [
                            {
                                label: _t('Employees Needed'),
                                data: employees,
                                borderColor: '#2563eb',
                                backgroundColor: 'rgba(37, 99, 235, 0.15)',
                                fill: true,
                                tension: 0.35,
                                yAxisID: 'y',
                            },
                            {
                                label: _t('Planned Cost'),
                                data: costs,
                                borderColor: '#22c55e',
                                backgroundColor: 'rgba(34, 197, 94, 0.15)',
                                fill: true,
                                tension: 0.35,
                                yAxisID: 'y1',
                            },
                        ],
                    },
                    options: {
                        responsive: false,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                            },
                            tooltip: {
                                mode: 'index',
                                intersect: false,
                            },
                        },
                        scales: {
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                beginAtZero: true,
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                beginAtZero: true,
                                grid: {
                                    drawOnChartArea: false,
                                },
                            },
                        },
                    },
                });
            });
        },

        _getLocale: function () {
            const lang = (session.user_context.lang || 'en_US').replace(/_/g, '-');
            try {
                new Intl.NumberFormat(lang);
                return lang;
            } catch (e) {
                return 'en-US';
            }
        },

        _getCurrencyFormatter: function () {
            const lang = this._getLocale();
            const currency = this.currencyName || 'USD';
            const formatter = new Intl.NumberFormat(lang, {
                style: 'currency',
                currency: currency,
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            });
            return amount => formatter.format(amount || 0);
        },

        _formatPercent: function (value) {
            const formatter = new Intl.NumberFormat(this._getLocale(), {
                minimumFractionDigits: 0,
                maximumFractionDigits: 1,
            });
            return formatter.format(value || 0);
        },

        _formatState: function (state) {
            const mapping = {
                draft: _t('Draft'),
                review: _t('In Review'),
                approved: _t('Approved'),
                archived: _t('Archived'),
            };
            return mapping[state] || state || '';
        },

        _onRefreshClick: function () {
            this._refresh();
        },

        _onFilterChange: function (ev) {
            const $target = $(ev.currentTarget);
            const key = $target.data('filter');
            const value = $target.val();
            this.filters[key] = value || false;
            if (key === 'capability' && !value) {
                this.filters.role = false;
                this.$('select[data-filter="role"]').val('');
            }
            this._refresh();
        },
    });

    core.action_registry.add('pb_workforce_dashboard', WorkforceDashboardAction);

    return WorkforceDashboardAction;
});
