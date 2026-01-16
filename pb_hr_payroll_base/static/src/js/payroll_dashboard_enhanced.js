/* Enhanced Payroll Dashboard JavaScript - Professional Indonesia Integration */

odoo.define('pb_hr_payroll_base.enhanced_dashboard', function (require) {
    'use strict';

    var AbstractAction = require('web.AbstractAction');
    var core = require('web.core');
    var framework = require('web.framework');
    var session = require('web.session');
    var utils = require('web.utils');
    var ajax = require('web.ajax');
    var Dialog = require('web.Dialog');
    var KanbanController = require('web.KanbanController');
    var KanbanView = require('web.KanbanView');
    var viewRegistry = require('web.view_registry');

    var _t = core._t;
    var QWeb = core.qweb;

    /**
     * Enhanced Payroll Dashboard Controller
     */
    var EnhancedDashboardController = KanbanController.extend({
        className: 'o_kanban_dashboard_payroll_enhanced',
        
        events: _.extend({}, KanbanController.prototype.events, {
            'click .country-card-enhanced': '_onCountryCardClick',
            'click .dashboard-access-btn': '_onDashboardAccess',
            'click .request-access-btn': '_onRequestAccess',
            'mouseenter .payroll-country-card-enhanced': '_onCardHover',
            'mouseleave .payroll-country-card-enhanced': '_onCardLeave',
        }),

        /**
         * Initialize enhanced dashboard
         */
        init: function (parent, model, renderer, params) {
            this._super.apply(this, arguments);
            this.accessRights = {};
            this.countryData = {};
            this.animationQueue = [];
        },

        /**
         * Start the enhanced dashboard
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._loadAccessRights();
                self._initializeAnimations();
                self._setupCountryCards();
                self._loadDashboardData();
            });
        },

        /**
         * Load user access rights for countries
         */
        _loadAccessRights: function () {
            var self = this;
            return this._rpc({
                model: 'payroll.dashboard',
                method: 'get_user_access_rights',
                args: [session.uid],
            }).then(function (result) {
                self.accessRights = result || {};
                self._updateAccessIndicators();
            }).catch(function (error) {
                console.warn('Failed to load access rights:', error);
                // Default access rights
                self.accessRights = {
                    'VN': true,
                    'ID': true,
                    'IN': true,
                    'SG': false,
                    'MY': false
                };
                self._updateAccessIndicators();
            });
        },

        /**
         * Update access indicators on country cards
         */
        _updateAccessIndicators: function () {
            var self = this;
            this.$('.payroll-country-card-enhanced').each(function () {
                var $card = $(this);
                var country = $card.data('country');
                var hasAccess = self.accessRights[country];
                
                var $indicator = $card.find('.access-status-badge');
                var $tick = $card.find('.access-tick');
                var $btn = $card.find('.dashboard-access-btn');
                
                if (hasAccess) {
                    $card.removeClass('no-access').addClass('has-access');
                    $indicator.removeClass('no-access').addClass('has-access');
                    $tick.text('✓');
                    $btn.prop('disabled', false).text('Access Dashboard');
                } else {
                    $card.removeClass('has-access').addClass('no-access');
                    $indicator.removeClass('has-access').addClass('no-access');
                    $tick.text('🔒');
                    $btn.prop('disabled', true).text('Request Access');
                    
                    // Add no-access overlay
                    if (!$card.find('.no-access-overlay').length) {
                        $card.append(self._createNoAccessOverlay(country));
                    }
                }
            });
        },

        /**
         * Create no-access overlay for restricted countries
         */
        _createNoAccessOverlay: function (country) {
            var countryNames = {
                'SG': 'Singapore',
                'MY': 'Malaysia',
                'TH': 'Thailand',
                'PH': 'Philippines'
            };
            
            var countryName = countryNames[country] || country;
            
            return $(`
                <div class="no-access-overlay">
                    <div class="no-access-message">
                        <h4>🔒 Access Required</h4>
                        <p>You don't have permission to access ${countryName} payroll system.</p>
                        <button class="contact-admin-btn" data-country="${country}">
                            Contact Administrator
                        </button>
                    </div>
                </div>
            `);
        },

        /**
         * Initialize enhanced animations
         */
        _initializeAnimations: function () {
            var self = this;
            
            // Staggered card animations
            this.$('.payroll-country-card-enhanced').each(function (index) {
                $(this).css('animation-delay', (index * 0.1) + 's');
                $(this).addClass('fade-in-enhanced');
            });

            // Flag floating animations with random delays
            this.$('.country-flag-large').each(function () {
                var delay = Math.random() * 2;
                $(this).css('animation-delay', delay + 's');
            });

            // Pulse access indicators
            setTimeout(function () {
                self.$('.access-status-badge').addClass('animated-pulse');
            }, 1000);
        },

        /**
         * Setup country cards with enhanced interactions
         */
        _setupCountryCards: function () {
            var self = this;
            
            // Add click ripple effect
            this.$('.payroll-country-card-enhanced').on('click', function (e) {
                if (!$(this).hasClass('no-access')) {
                    self._addRippleEffect($(this), e);
                }
            });

            // Add enhanced hover effects
            this.$('.payroll-country-card-enhanced').hover(
                function () {
                    $(this).addClass('hovered');
                    $(this).find('.country-flag-large').addClass('flag-wave-active');
                },
                function () {
                    $(this).removeClass('hovered');
                    $(this).find('.country-flag-large').removeClass('flag-wave-active');
                }
            );

            // Setup contact admin buttons
            this.$('.contact-admin-btn').on('click', function (e) {
                e.stopPropagation();
                var country = $(this).data('country');
                self._showAccessRequestDialog(country);
            });
        },

        /**
         * Add ripple effect to card
         */
        _addRippleEffect: function ($card, event) {
            var $ripple = $('<div class="ripple-effect"></div>');
            var cardRect = $card[0].getBoundingClientRect();
            var x = event.clientX - cardRect.left;
            var y = event.clientY - cardRect.top;
            
            $ripple.css({
                position: 'absolute',
                left: x + 'px',
                top: y + 'px',
                width: '0',
                height: '0',
                borderRadius: '50%',
                background: 'rgba(102, 126, 234, 0.3)',
                transform: 'translate(-50%, -50%)',
                animation: 'ripple-expand 0.6s ease-out',
                pointerEvents: 'none',
                zIndex: 10
            });
            
            $card.css('position', 'relative').append($ripple);
            
            setTimeout(function () {
                $ripple.remove();
            }, 600);
        },

        /**
         * Load dashboard data for each country
         */
        _loadDashboardData: function () {
            var self = this;
            return this._rpc({
                model: 'payroll.dashboard',
                method: 'get_dashboard_summary',
                args: [],
            }).then(function (data) {
                self.countryData = data || {};
                self._updateCountryStats();
            });
        },

        /**
         * Update country statistics on cards
         */
        _updateCountryStats: function () {
            var self = this;
            _.each(this.countryData, function (data, country) {
                var $card = self.$('.payroll-country-card-enhanced[data-country="' + country + '"]');
                if ($card.length) {
                    $card.find('.stat-value').each(function (index) {
                        var $stat = $(this);
                        var value;
                        switch (index) {
                            case 0:
                                value = data.total_employees || 0;
                                break;
                            case 1:
                                value = self._formatCurrency(data.total_payroll || 0, data.currency);
                                break;
                        }
                        self._animateValue($stat, value);
                    });
                }
            });
        },

        /**
         * Animate value changes
         */
        _animateValue: function ($element, newValue) {
            var currentValue = parseInt($element.text()) || 0;
            var targetValue = parseInt(newValue) || 0;
            
            if (currentValue === targetValue) return;
            
            var steps = 30;
            var stepValue = (targetValue - currentValue) / steps;
            var currentStep = 0;
            
            var interval = setInterval(function () {
                currentStep++;
                currentValue += stepValue;
                
                if (currentStep >= steps) {
                    $element.text(newValue);
                    clearInterval(interval);
                } else {
                    $element.text(Math.round(currentValue));
                }
            }, 50);
        },

        /**
         * Format currency values
         */
        _formatCurrency: function (amount, currency) {
            currency = currency || 'USD';
            var formatter = new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: currency,
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            });
            return formatter.format(amount);
        },

        /**
         * Get correct currency symbol for each country
         */
        _getCurrencySymbol: function (country) {
            var currencySymbols = {
                'VN': '₫',     // Vietnamese Dong
                'ID': 'Rp',    // Indonesian Rupiah  
                'IN': '₹',     // Indian Rupee
                'SG': 'S$',    // Singapore Dollar
                'MY': 'RM',    // Malaysian Ringgit
                'TH': '฿',     // Thai Baht
                'PH': '₱'      // Philippine Peso
            };
            return currencySymbols[country] || '$';
        },

        /**
         * FIXED: Format currency with correct symbols per country
         */
        _formatCurrencyByCountry: function (amount, country) {
            var symbol = this._getCurrencySymbol(country);
            var formattedAmount = new Intl.NumberFormat('en-US', {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            }).format(amount);
            
            return symbol + ' ' + formattedAmount;
        },


        /**
         * Handle country card click
         */
        _onCountryCardClick: function (event) {
            var $card = $(event.currentTarget);
            var country = $card.data('country');
            
            if ($card.hasClass('no-access')) {
                this._showAccessRequestDialog(country);
                return;
            }
            
            this._navigateToCountryDashboard(country);
        },

        /**
         * Handle dashboard access button click
         */
        _onDashboardAccess: function (event) {
            event.stopPropagation();
            var $btn = $(event.currentTarget);
            var $card = $btn.closest('.payroll-country-card-enhanced');
            var country = $card.data('country');
            
            if ($btn.prop('disabled')) {
                this._showAccessRequestDialog(country);
                return;
            }
            
            this._showLoadingOverlay();
            this._navigateToCountryDashboard(country);
        },

        /**
         * Handle access request button click
         */
        _onRequestAccess: function (event) {
            event.stopPropagation();
            var country = $(event.currentTarget).data('country');
            this._showAccessRequestDialog(country);
        },

        /**
         * Navigate to country-specific dashboard
         */
        _navigateToCountryDashboard: function (country) {
            var self = this;

            // Show loading for better UX
            this._showLoadingOverlay();

            this._rpc({
                model: 'payroll.dashboard',
                method: 'get_country_dashboard_action',
                args: [country],
            }).then(function (action) {
                self.do_action(action);
            }).catch(function (error) {
                self._hideLoadingOverlay();
                self._showErrorDialog('Failed to load dashboard: ' + error.message);
            });
        },

        /**
         * Show access request dialog
         */
        _showAccessRequestDialog: function (country) {
            var self = this;
            var countryNames = {
                'VN': 'Vietnam',
                'ID': 'Indonesia', 
                'IN': 'India',
                'SG': 'Singapore',
                'MY': 'Malaysia',
                'TH': 'Thailand',
                'PH': 'Philippines'
            };
            
            var countryName = countryNames[country] || country;
            
            var dialog = new Dialog(this, {
                title: _t('Access Request Required'),
                size: 'medium',
                $content: $(QWeb.render('PayrollAccessRequestDialog', {
                    country: country,
                    countryName: countryName
                })),
                buttons: [
                    {
                        text: _t('Send Request'),
                        classes: 'btn-primary',
                        close: true,
                        click: function () {
                            self._sendAccessRequest(country);
                        }
                    },
                    {
                        text: _t('Cancel'),
                        close: true
                    }
                ]
            });
            
            dialog.open();
        },

        /**
         * Send access request to administrator
         */
        _sendAccessRequest: function (country) {
            var self = this;
            
            return this._rpc({
                model: 'payroll.dashboard',
                method: 'send_access_request',
                args: [session.uid, country],
            }).then(function (result) {
                if (result.success) {
                    self._showSuccessNotification(
                        _t('Access request sent successfully'),
                        _t('Your request for ' + country + ' payroll access has been sent to the administrator.')
                    );
                } else {
                    self._showErrorDialog(result.message || _t('Failed to send access request'));
                }
            }).catch(function (error) {
                self._showErrorDialog(_t('Error sending access request: ') + error.message);
            });
        },

        /**
         * Show loading overlay
         */
        _showLoadingOverlay: function () {
            var $overlay = $(`
                <div class="loading-overlay active">
                    <div class="loading-content">
                        <div class="spinner"></div>
                        <div class="loading-text">Loading payroll dashboard...</div>
                    </div>
                </div>
            `);
            
            $('body').append($overlay);
        },

        /**
         * Hide loading overlay
         */
        _hideLoadingOverlay: function () {
            $('.loading-overlay').removeClass('active').fadeOut(300, function () {
                $(this).remove();
            });
        },

        /**
         * Show success notification
         */
        _showSuccessNotification: function (title, message) {
            this.displayNotification({
                type: 'success',
                title: title,
                message: message,
                sticky: false
            });
        },

        /**
         * Show error dialog
         */
        _showErrorDialog: function (message) {
            Dialog.alert(this, message, {
                title: _t('Error'),
            });
        },

        /**
         * Handle card hover
         */
        _onCardHover: function (event) {
            var $card = $(event.currentTarget);
            $card.addClass('hover-enhanced');
            
            // Trigger flag animation
            $card.find('.country-flag-large').addClass('flag-hover-active');
        },

        /**
         * Handle card leave
         */
        _onCardLeave: function (event) {
            var $card = $(event.currentTarget);
            $card.removeClass('hover-enhanced');
            
            // Stop flag animation
            $card.find('.country-flag-large').removeClass('flag-hover-active');
        },

    });

    /**
     * Enhanced Dashboard View
     */
    var EnhancedDashboardView = KanbanView.extend({
        config: _.extend({}, KanbanView.prototype.config, {
            Controller: EnhancedDashboardController,
        }),
    });

    // Register the enhanced view
    viewRegistry.add('payroll_dashboard_enhanced', EnhancedDashboardView);

    /**
     * Enhanced Dashboard Action
     */
    var EnhancedDashboardAction = AbstractAction.extend({
        template: 'PayrollEnhancedDashboard',
        className: 'o_payroll_enhanced_dashboard',

        events: {
            'click .country-selector-btn': '_onCountrySelect',
            'click .analytics-btn': '_onAnalyticsView',
            'click .refresh-btn': '_onRefreshData',
        },

        init: function (parent, context) {
            this._super(parent, context);
            this.dashboardData = {};
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._loadDashboardData();
                self._initializeCharts();
            });
        },

        _loadDashboardData: function () {
            var self = this;
            return this._rpc({
                model: 'payroll.dashboard',
                method: 'get_enhanced_dashboard_data',
                args: [],
            }).then(function (data) {
                self.dashboardData = data;
                self._updateDashboard();
            });
        },

        _updateDashboard: function () {
            // Update dashboard with new data
            this._updateMetrics();
            this._updateCharts();
            this._updateRecentActivity();
        },

        _updateMetrics: function () {
            var data = this.dashboardData;
            this.$('.metric-employees .metric-value').text(data.total_employees || 0);
            this.$('.metric-payroll .metric-value').text(this._formatCurrency(data.total_payroll || 0));
            this.$('.metric-countries .metric-value').text(data.active_countries || 0);
        },

        _updateCharts: function () {
            // Implement chart updates
            if (this.charts) {
                _.each(this.charts, function (chart) {
                    chart.destroy();
                });
            }
            this._initializeCharts();
        },

        _initializeCharts: function () {
            // Initialize Chart.js charts
            this.charts = {};
            this._createPayrollTrendChart();
            this._createCountryComparisonChart();
        },

        _createPayrollTrendChart: function () {
            var ctx = this.$('#payrollTrendChart')[0];
            if (!ctx) return;
            
            this.charts.payrollTrend = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: this.dashboardData.trend_labels || [],
                    datasets: [{
                        label: 'Total Payroll',
                        data: this.dashboardData.trend_data || [],
                        borderColor: '#21435F',
                        backgroundColor: 'rgba(33, 67, 95, 0.1)',
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        },

        _createCountryComparisonChart: function () {
            var ctx = this.$('#countryComparisonChart')[0];
            if (!ctx) return;
            
            this.charts.countryComparison = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: this.dashboardData.country_labels || [],
                    datasets: [{
                        data: this.dashboardData.country_data || [],
                        backgroundColor: [
                            '#21435F',
                            '#336087',
                            '#4A759B',
                            '#667eea',
                            '#764ba2'
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'right'
                        }
                    }
                }
            });
        },

        _formatCurrency: function (amount) {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD',
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
            }).format(amount);
        },

        _onCountrySelect: function (event) {
            var country = $(event.currentTarget).data('country');
            // Handle country selection
        },

        _onAnalyticsView: function () {
            this.do_action('payroll_analytics_approval.action_payroll_analytics_dashboard');
        },

        _onRefreshData: function () {
            this._loadDashboardData();
        },

    });

    // Register the action
    core.action_registry.add('payroll_enhanced_dashboard', EnhancedDashboardAction);

    return {
        EnhancedDashboardController: EnhancedDashboardController,
        EnhancedDashboardView: EnhancedDashboardView,
        EnhancedDashboardAction: EnhancedDashboardAction,
    };

});

/* Additional CSS animations for enhanced effects */
if (typeof document !== 'undefined') {
    var style = document.createElement('style');
    style.textContent = `
        @keyframes ripple-expand {
            to {
                width: 400px;
                height: 400px;
                opacity: 0;
            }
        }
        
        .flag-hover-active {
            animation: flagWaveEnhanced 0.8s ease-in-out infinite !important;
        }
        
        .hover-enhanced {
            transform: translateY(-10px) scale(1.02) !important;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2) !important;
        }
        
        .animated-pulse .access-status-badge {
            animation: accessPulse 2s infinite;
        }
        
        .fade-in-enhanced {
            animation: fadeInEnhanced 0.6s ease-out forwards;
            opacity: 0;
        }
    `;
    document.head.appendChild(style);
}

/* QWeb Templates for Enhanced Dashboard */
if (typeof QWeb !== 'undefined') {
    QWeb.add_template(`
        <templates>
            <!-- Access Request Dialog Template -->
            <t t-name="PayrollAccessRequestDialog">
                <div class="access-request-dialog">
                    <div class="text-center mb-4">
                        <i class="fa fa-lock fa-4x text-danger mb-3"></i>
                        <h4>Access Required</h4>
                        <p class="text-muted">
                            You need administrator permission to access the <strong t-esc="countryName"/> payroll system.
                        </p>
                    </div>
                    
                    <div class="alert alert-info">
                        <i class="fa fa-info-circle mr-2"></i>
                        Your request will be sent to the system administrator for approval.
                        You will be notified once access is granted.
                    </div>
                    
                    <div class="form-group">
                        <label for="requestReason">Reason for Access (Optional):</label>
                        <textarea id="requestReason" class="form-control" rows="3" 
                                  placeholder="Please explain why you need access to this payroll system..."></textarea>
                    </div>
                </div>
            </t>
            
            <!-- Enhanced Dashboard Template -->
            <t t-name="PayrollEnhancedDashboard">
                <div class="o_payroll_enhanced_dashboard">
                    <div class="dashboard-header-enhanced">
                        <div class="container-fluid">
                            <div class="row align-items-center">
                                <div class="col-md-8">
                                    <h1 class="dashboard-title-enhanced">Multi-Country Payroll System</h1>
                                    <p class="dashboard-subtitle-enhanced">Professional payroll management across regions</p>
                                </div>
                                <div class="col-md-4 text-right">
                                    <button class="btn btn-outline-primary refresh-btn">
                                        <i class="fa fa-refresh mr-2"></i>Refresh Data
                                    </button>
                                    <button class="btn btn-primary analytics-btn ml-2">
                                        <i class="fa fa-chart-bar mr-2"></i>Analytics
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="dashboard-content-enhanced">
                        <div class="container-fluid">
                            <!-- Key Metrics Row -->
                            <div class="row mb-4">
                                <div class="col-lg-3 col-md-6 mb-3">
                                    <div class="metric-card-enhanced metric-employees">
                                        <div class="metric-icon">
                                            <i class="fa fa-users"></i>
                                        </div>
                                        <div class="metric-value">0</div>
                                        <div class="metric-label">Total Employees</div>
                                    </div>
                                </div>
                                <div class="col-lg-3 col-md-6 mb-3">
                                    <div class="metric-card-enhanced metric-payroll">
                                        <div class="metric-icon">
                                            <i class="fa fa-money"></i>
                                        </div>
                                        <div class="metric-value">$0</div>
                                        <div class="metric-label">Total Payroll</div>
                                    </div>
                                </div>
                                <div class="col-lg-3 col-md-6 mb-3">
                                    <div class="metric-card-enhanced metric-countries">
                                        <div class="metric-icon">
                                            <i class="fa fa-globe"></i>
                                        </div>
                                        <div class="metric-value">0</div>
                                        <div class="metric-label">Active Countries</div>
                                    </div>
                                </div>
                                <div class="col-lg-3 col-md-6 mb-3">
                                    <div class="metric-card-enhanced metric-growth">
                                        <div class="metric-icon">
                                            <i class="fa fa-trending-up"></i>
                                        </div>
                                        <div class="metric-value">0%</div>
                                        <div class="metric-label">Monthly Growth</div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Charts Row -->
                            <div class="row mb-4">
                                <div class="col-lg-8 mb-3">
                                    <div class="chart-card-enhanced">
                                        <div class="chart-header">
                                            <h5>Payroll Trend</h5>
                                            <p class="text-muted">Monthly payroll comparison</p>
                                        </div>
                                        <div class="chart-container">
                                            <canvas id="payrollTrendChart"></canvas>
                                        </div>
                                    </div>
                                </div>
                                <div class="col-lg-4 mb-3">
                                    <div class="chart-card-enhanced">
                                        <div class="chart-header">
                                            <h5>Country Distribution</h5>
                                            <p class="text-muted">Payroll by country</p>
                                        </div>
                                        <div class="chart-container">
                                            <canvas id="countryComparisonChart"></canvas>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Country Selector Row -->
                            <div class="row">
                                <div class="col-12">
                                    <div class="country-selector-enhanced">
                                        <div class="section-header">
                                            <h4>Select Country Dashboard</h4>
                                            <p class="text-muted">Choose your region to access specific payroll features</p>
                                        </div>
                                        
                                        <div class="countries-grid-enhanced">
                                            <div class="country-card-mini" data-country="VN">
                                                <div class="country-flag">🇻🇳</div>
                                                <div class="country-name">Vietnam</div>
                                                <button class="btn btn-sm btn-primary country-selector-btn" data-country="VN">
                                                    Access
                                                </button>
                                            </div>
                                            <div class="country-card-mini" data-country="ID">
                                                <div class="country-flag">🇮🇩</div>
                                                <div class="country-name">Indonesia</div>
                                                <button class="btn btn-sm btn-primary country-selector-btn" data-country="ID">
                                                    Access
                                                </button>
                                            </div>
                                            <div class="country-card-mini" data-country="IN">
                                                <div class="country-flag">🇮🇳</div>
                                                <div class="country-name">India</div>
                                                <button class="btn btn-sm btn-primary country-selector-btn" data-country="IN">
                                                    Access
                                                </button>
                                            </div>
                                            <div class="country-card-mini no-access" data-country="SG">
                                                <div class="country-flag">🇸🇬</div>
                                                <div class="country-name">Singapore</div>
                                                <button class="btn btn-sm btn-secondary country-selector-btn" data-country="SG" disabled>
                                                    Request
                                                </button>
                                            </div>
                                            <div class="country-card-mini no-access" data-country="MY">
                                                <div class="country-flag">🇲🇾</div>
                                                <div class="country-name">Malaysia</div>
                                                <button class="btn btn-sm btn-secondary country-selector-btn" data-country="MY" disabled>
                                                    Request
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </t>
        </templates>
    `);
}
