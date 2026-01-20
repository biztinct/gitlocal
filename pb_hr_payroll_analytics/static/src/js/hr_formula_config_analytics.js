/* Salary Structure Analytics Dashboard - Formula Config Analytics Controller */

odoo.define('pb_hr_payroll_analytics.FormulaConfigAnalytics', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var rpc = require('web.rpc');

    // Load Chart Library
    var ChartLib;
    try {
        ChartLib = require('pb_hr_payroll_analytics.Charts');
    } catch (e) {
        ChartLib = window.ChartLib || {};
    }

    // Color palettes for charts and cards
    var colorPalettes = {
        primary: ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6', '#1abc9c', '#e91e63', '#00bcd4'],
        pastel: ['#FFB6C1', '#87CEEB', '#98FB98', '#FFD700', '#DDA0DD', '#87CEFA', '#FFA07A', '#98D8C8'],
        categoryType: {
            'basic': '#3498db',
            'allowance': '#2ecc71',
            'deduction': '#e74c3c',
            'tax': '#f39c12',
            'social_security': '#9b59b6',
            'net': '#1abc9c',
            'employer_cost': '#e91e63'
        },
        gradient: [
            'rgba(102, 126, 234, 0.8)',
            'rgba(118, 75, 162, 0.8)',
            'rgba(17, 153, 142, 0.8)',
            'rgba(56, 239, 125, 0.8)',
            'rgba(235, 51, 73, 0.8)',
            'rgba(244, 92, 67, 0.8)',
            'rgba(79, 172, 254, 0.8)',
            'rgba(0, 242, 254, 0.8)'
        ],
        // Light pastel card styles with borders and glow (2 shades lighter backgrounds)
        cardStyles: [
            { bg: 'linear-gradient(135deg, #fdf4ff 0%, #fae8ff 100%)', border: '#d946ef', text: '#86198f', glow: 'rgba(217, 70, 239, 0.3)' },
            { bg: 'linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%)', border: '#3b82f6', text: '#1e40af', glow: 'rgba(59, 130, 246, 0.3)' },
            { bg: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)', border: '#10b981', text: '#065f46', glow: 'rgba(16, 185, 129, 0.3)' },
            { bg: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)', border: '#f59e0b', text: '#92400e', glow: 'rgba(245, 158, 11, 0.3)' },
            { bg: 'linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%)', border: '#ec4899', text: '#9d174d', glow: 'rgba(236, 72, 153, 0.3)' },
            { bg: 'linear-gradient(135deg, #f0fdfa 0%, #ccfbf1 100%)', border: '#14b8a6', text: '#115e59', glow: 'rgba(20, 184, 166, 0.3)' },
            { bg: 'linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%)', border: '#6366f1', text: '#3730a3', glow: 'rgba(99, 102, 241, 0.3)' },
            { bg: 'linear-gradient(135deg, #fff7ed 0%, #fed7aa 100%)', border: '#f97316', text: '#9a3412', glow: 'rgba(249, 115, 22, 0.3)' }
        ]
    };

    // Format currency for display
    var formatCurrency = function (amount) {
        if (!amount && amount !== 0) return '0';
        if (Math.abs(amount) >= 1000000) {
            return (amount / 1000000).toFixed(1) + 'M';
        } else if (Math.abs(amount) >= 1000) {
            return (amount / 1000).toFixed(1) + 'K';
        }
        return amount.toFixed(0);
    };

    // Category type labels
    var categoryTypeLabels = {
        'basic': 'Basic Salary',
        'allowance': 'Allowances',
        'deduction': 'Deductions',
        'tax': 'Taxes',
        'social_security': 'Social Security',
        'net': 'Net Salary',
        'employer_cost': 'Employer Costs'
    };

    // Cycle type labels (display values)
    var cycleTypeLabels = {
        'regular': 'Regular',
        'end_cycle': 'End Cycle',
        'mid_cycle': 'Mid Cycle',
        'bonus': 'Bonus',
        'thirteenth': '13th Month',
        'special': 'Special'
    };

    // Format cycle type for display
    var formatCycleType = function (cycleType) {
        if (!cycleType) return 'Regular';
        return cycleTypeLabels[cycleType] || cycleType.replace(/_/g, ' ').replace(/\b\w/g, function (l) { return l.toUpperCase(); });
    };

    // =================================================================
    // FORMULA CONFIG ANALYTICS CONTROLLER
    // =================================================================

    var FormulaConfigAnalyticsController = FormController.extend({
        events: _.extend({}, FormController.prototype.events, {
            'click .config-card': '_onConfigClick',
            'click .department-card': '_onDepartmentClick',
            'click .nav-link': '_onTabClick',
            'change [name="period_type"]': '_onFilterChange',
            'change [name="date_from"]': '_onFilterChange',
            'change [name="date_to"]': '_onFilterChange'
        }),

        init: function () {
            this._super.apply(this, arguments);
            this.charts = {};
            this.chartJSLoaded = false;
            this.currentData = {};
        },

        willStart: function () {
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadChartJS()
            ]);
        },

        start: function () {
            return this._super.apply(this, arguments).then(() => {
                setTimeout(() => this._setupDashboard(), 500);
            });
        },

        on_attach_callback: function () {
            var self = this;
            setTimeout(function () {
                self._setupDashboard();
            }, 300);
        },

        destroy: function () {
            this._destroyAllCharts();
            this._super.apply(this, arguments);
        },

        // =================================================================
        // CHART.JS LOADING
        // =================================================================

        _loadChartJS: function () {
            var self = this;
            return new Promise(function (resolve) {
                if (window.Chart) {
                    self.chartJSLoaded = true;
                    resolve();
                    return;
                }

                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                script.onload = function () {
                    self.chartJSLoaded = true;
                    resolve();
                };
                script.onerror = function () {
                    resolve();
                };
                document.head.appendChild(script);
            });
        },

        // =================================================================
        // DASHBOARD SETUP
        // =================================================================

        _setupDashboard: function () {
            var self = this;
            var recordData = this.model.get(this.handle).data;
            var activeView = recordData.active_view || 'hierarchy';

            // Load appropriate view based on active_view state
            switch (activeView) {
                case 'hierarchy':
                    this._loadHierarchyView();
                    break;
                case 'consolidated':
                    this._loadConsolidatedView();
                    // Switch to consolidated tab if not already active
                    setTimeout(function () {
                        self._activateTabByName('consolidated');
                    }, 200);
                    break;
                case 'config_detail':
                    this._loadHierarchyView(); // Still load hierarchy for context
                    this._loadConfigDetailView();
                    // Switch to config_detail tab if not already active
                    setTimeout(function () {
                        self._activateTabByName('config_detail');
                    }, 200);
                    break;
                case 'department_detail':
                    this._loadDepartmentDetailView();
                    // Switch to department_detail tab if not already active
                    setTimeout(function () {
                        self._activateTabByName('department_detail');
                    }, 200);
                    break;
                default:
                    this._loadHierarchyView();
            }
        },

        _activateTabByName: function (tabName) {
            // Tab activation for Odoo 16 notebook
            var self = this;

            // Map of page names to their expected tab text
            var tabTextMap = {
                'hierarchy': 'Hierarchy Home',
                'consolidated': 'Consolidated View',
                'config_detail': 'Salary Details',
                'department_detail': 'Department Detail'
            };

            // Method 1: Find by page name attribute
            var tabs = this.el.querySelectorAll('.o_notebook .nav-link');
            var pages = this.el.querySelectorAll('.o_notebook .tab-pane');
            var targetIndex = -1;

            // Check if pages have name attribute directly
            pages.forEach(function (page, index) {
                var pageName = page.getAttribute('name');
                var pageId = page.getAttribute('id') || '';
                // Check name attribute or if ID contains the tab name
                if (pageName === tabName || pageId.toLowerCase().includes(tabName.replace('_', ''))) {
                    targetIndex = index;
                }
            });

            // Method 2: If not found by name, try matching tab text
            if (targetIndex < 0) {
                var expectedText = tabTextMap[tabName] || tabName.replace(/_/g, ' ');
                tabs.forEach(function (tab, index) {
                    var tabText = tab.textContent.trim();
                    if (tabText.toLowerCase() === expectedText.toLowerCase()) {
                        targetIndex = index;
                    }
                });
            }

            if (targetIndex >= 0 && tabs[targetIndex]) {
                tabs[targetIndex].click();

                // Also ensure the tab content is visible
                setTimeout(function () {
                    // Remove active from all tabs and panes
                    tabs.forEach(function (t) { t.classList.remove('active'); });
                    pages.forEach(function (p) { p.classList.remove('active', 'show'); });

                    // Add active to target
                    if (tabs[targetIndex]) tabs[targetIndex].classList.add('active');
                    if (pages[targetIndex]) {
                        pages[targetIndex].classList.add('active', 'show');
                    }
                }, 50);
            }
        },

        // =================================================================
        // HIERARCHY VIEW
        // =================================================================

        _loadHierarchyView: function (forceRender) {
            var self = this;
            var recordData = this.model.get(this.handle).data;
            var hierarchyJson = recordData.hierarchy_data_json;
            var activeView = recordData.active_view || 'hierarchy';

            // Skip auto-render during _setupDashboard if not in hierarchy view
            // But always render when called explicitly (e.g., from tab click)
            if (!forceRender && activeView !== 'hierarchy' && activeView !== 'config_detail') {
                return;
            }

            if (!hierarchyJson) {
                // Clear loading message
                var configsGrid = document.getElementById('configs-grid');
                if (configsGrid) {
                    configsGrid.innerHTML = '<div style="text-align: center; color: #95a5a6; padding: 40px; grid-column: 1/-1;">' +
                        '<i class="fa fa-info-circle" style="font-size: 30px;"></i>' +
                        '<p>No hierarchy data available. Try refreshing.</p></div>';
                }
                return;
            }

            try {
                var data = JSON.parse(hierarchyJson);
                this.currentData.hierarchy = data;
                this._renderHierarchy(data);
            } catch (e) {
                // JSON parsing error - silent fail
            }
        },

        _renderHierarchy: function (data) {
            var self = this;

            // Render Config Cards
            var configsGrid = document.getElementById('configs-grid');
            if (configsGrid && data.configs) {
                configsGrid.innerHTML = '';

                if (data.configs.length === 0) {
                    configsGrid.innerHTML = '<div style="text-align: center; color: #95a5a6; padding: 40px; grid-column: 1/-1;">' +
                        '<i class="fa fa-info-circle" style="font-size: 30px;"></i>' +
                        '<p>No active salary configs found for this company.</p></div>';
                    return;
                }

                data.configs.forEach(function (config, index) {
                    var card = document.createElement('div');
                    card.className = 'config-card';
                    card.dataset.configId = config.id;

                    // Get pastel card style for this card
                    var cardStyle = colorPalettes.cardStyles[index % colorPalettes.cardStyles.length];

                    card.style.cssText = 'background: ' + cardStyle.bg + '; border-radius: 12px; padding: 0; cursor: pointer; ' +
                        'border: 3px solid ' + cardStyle.border + '; ' +
                        'box-shadow: 0 0 20px ' + cardStyle.glow + ', 0 4px 15px ' + cardStyle.glow + '; ' +
                        'transition: transform 0.3s, box-shadow 0.3s; overflow: hidden;';

                    card.innerHTML =
                        '<div style="background: ' + cardStyle.border + '20; padding: 15px; border-bottom: 2px solid ' + cardStyle.border + '40;">' +
                            '<div style="display: flex; align-items: center; gap: 10px;">' +
                                '<i class="fa fa-file-text" style="font-size: 24px; color: ' + cardStyle.text + ';"></i>' +
                                '<div>' +
                                    '<h5 style="margin: 0; font-size: 16px; font-weight: 700; color: ' + cardStyle.text + ';">' + config.name + '</h5>' +
                                    '<span style="opacity: 0.8; font-size: 12px; color: ' + cardStyle.text + ';">' + (config.code || '') + '</span>' +
                                '</div>' +
                            '</div>' +
                        '</div>' +
                        '<div style="padding: 15px;">' +
                            '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;">' +
                                '<div style="text-align: center; padding: 10px; background: rgba(255,255,255,0.7); border-radius: 8px; border: 1px solid ' + cardStyle.border + '40;">' +
                                    '<div style="font-size: 11px; color: ' + cardStyle.text + '; opacity: 0.8;">Country</div>' +
                                    '<div style="font-size: 14px; font-weight: bold; color: ' + cardStyle.text + ';">' + (config.country_code || '-') + '</div>' +
                                '</div>' +
                                '<div style="text-align: center; padding: 10px; background: rgba(255,255,255,0.7); border-radius: 8px; border: 1px solid ' + cardStyle.border + '40;">' +
                                    '<div style="font-size: 11px; color: ' + cardStyle.text + '; opacity: 0.8;">Cycle</div>' +
                                    '<div style="font-size: 14px; font-weight: bold; color: ' + cardStyle.text + ';">' + formatCycleType(config.cycle_type) + '</div>' +
                                '</div>' +
                            '</div>' +
                            '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">' +
                                '<div style="text-align: center; padding: 10px; background: rgba(255,255,255,0.7); border-radius: 8px; border: 1px solid ' + cardStyle.border + '40;">' +
                                    '<div style="font-size: 11px; color: ' + cardStyle.text + '; opacity: 0.8;">Employees</div>' +
                                    '<div style="font-size: 18px; font-weight: bold; color: ' + cardStyle.text + ';">' + config.employee_count + '</div>' +
                                '</div>' +
                                '<div style="text-align: center; padding: 10px; background: rgba(255,255,255,0.7); border-radius: 8px; border: 1px solid ' + cardStyle.border + '40;">' +
                                    '<div style="font-size: 11px; color: ' + cardStyle.text + '; opacity: 0.8;">Departments</div>' +
                                    '<div style="font-size: 18px; font-weight: bold; color: ' + cardStyle.text + ';">' + config.departments.length + '</div>' +
                                '</div>' +
                            '</div>' +
                            '<div style="margin-top: 15px; padding-top: 15px; border-top: 2px solid ' + cardStyle.border + '30; text-align: center;">' +
                                '<div style="font-size: 12px; color: ' + cardStyle.text + '; opacity: 0.8;">Total Cost</div>' +
                                '<div style="font-size: 20px; font-weight: bold; color: ' + cardStyle.text + ';">' + formatCurrency(config.total_cost) + '</div>' +
                            '</div>' +
                        '</div>' +
                        '<div style="background: rgba(255,255,255,0.5); padding: 10px 15px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid ' + cardStyle.border + '30;">' +
                            '<span style="color: ' + cardStyle.text + '; font-size: 12px; opacity: 0.8;">Click to drill down</span>' +
                            '<i class="fa fa-chevron-right" style="color: ' + cardStyle.border + ';"></i>' +
                        '</div>';

                    // Store card style for hover effects
                    card.dataset.glowColor = cardStyle.glow;
                    card.dataset.borderColor = cardStyle.border;

                    // Hover effects with enhanced glow
                    card.onmouseenter = function () {
                        this.style.transform = 'translateY(-5px)';
                        this.style.boxShadow = '0 0 30px ' + this.dataset.glowColor + ', 0 8px 25px ' + this.dataset.glowColor;
                    };
                    card.onmouseleave = function () {
                        this.style.transform = 'translateY(0)';
                        this.style.boxShadow = '0 0 20px ' + this.dataset.glowColor + ', 0 4px 15px ' + this.dataset.glowColor;
                    };

                    configsGrid.appendChild(card);
                });
            }
        },

        _onConfigClick: function (ev) {
            var configId = parseInt(ev.currentTarget.dataset.configId);
            var self = this;

            // Find config in current data
            var config = this.currentData.hierarchy.configs.find(function (c) {
                return c.id === configId;
            });

            if (config) {
                // Show departments in the hierarchy view (inline)
                this._showDepartmentsForConfig(config);
                // Store current config for later use
                this.currentData.selectedConfig = config;
            }

            // Call backend to update state
            rpc.query({
                model: 'hr.formula.config.analytics',
                method: 'action_navigate_to_config',
                args: [[this.model.get(this.handle).res_id], configId]
            });
        },

        _showDepartmentsForConfig: function (config) {
            var self = this;
            var deptsGrid = document.getElementById('departments-grid');

            if (!deptsGrid) return;

            deptsGrid.style.display = 'block';
            deptsGrid.innerHTML = '<h4 style="grid-column: 1/-1; color: #334155; margin-bottom: 15px;">' +
                '<i class="fa fa-sitemap"></i> Departments in <strong>' + config.name + '</strong></h4>';
            deptsGrid.style.cssText += 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; ' +
                'margin-top: 30px; padding: 25px; background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border-radius: 12px; ' +
                'border: 2px solid #e2e8f0;';

            if (config.departments.length === 0) {
                deptsGrid.innerHTML += '<div style="text-align: center; color: #64748b; padding: 20px;">' +
                    '<p>No departments found for this config.</p></div>';
                return;
            }

            config.departments.forEach(function (dept, index) {
                var style = colorPalettes.cardStyles[index % colorPalettes.cardStyles.length];
                var card = document.createElement('div');
                card.className = 'department-card';
                card.dataset.configId = config.id;
                card.dataset.departmentId = dept.id;
                card.style.cssText = 'background: ' + style.bg + '; border-radius: 10px; padding: 18px; cursor: pointer; ' +
                    'border: 3px solid ' + style.border + '; ' +
                    'box-shadow: 0 0 15px ' + style.glow + ', 0 4px 12px ' + style.glow + '; ' +
                    'transition: all 0.3s ease;';

                card.innerHTML =
                    '<div style="font-weight: bold; color: ' + style.text + '; margin-bottom: 10px; font-size: 14px;">' +
                        '<i class="fa fa-users" style="margin-right: 6px;"></i>' + dept.name +
                    '</div>' +
                    '<div style="display: flex; justify-content: space-between; font-size: 12px; color: ' + style.text + '; opacity: 0.85;">' +
                        '<span><i class="fa fa-user" style="margin-right: 4px;"></i>' + dept.employee_count + ' employees</span>' +
                        '<span style="font-weight: bold;">' + formatCurrency(dept.gross_pay) + '</span>' +
                    '</div>';

                card.onmouseenter = function () {
                    this.style.transform = 'translateY(-3px) scale(1.02)';
                    this.style.boxShadow = '0 0 25px ' + style.glow + ', 0 8px 20px ' + style.glow;
                };
                card.onmouseleave = function () {
                    this.style.transform = 'translateY(0) scale(1)';
                    this.style.boxShadow = '0 0 15px ' + style.glow + ', 0 4px 12px ' + style.glow;
                };

                deptsGrid.appendChild(card);
            });
        },

        _onDepartmentClick: function (ev) {
            var configId = parseInt(ev.currentTarget.dataset.configId);
            var departmentId = parseInt(ev.currentTarget.dataset.departmentId);
            var self = this;
            var resId = this.model.get(this.handle).res_id;

            // Show loading indicator
            var deptsGrid = document.getElementById('departments-grid');
            if (deptsGrid) {
                deptsGrid.innerHTML = '<div style="text-align: center; padding: 20px; color: #3498db;">' +
                    '<i class="fa fa-spinner fa-spin" style="font-size: 24px;"></i>' +
                    '<p>Loading department details...</p></div>';
            }

            rpc.query({
                model: 'hr.formula.config.analytics',
                method: 'action_navigate_to_department',
                args: [[resId], configId, departmentId]
            }).then(function (result) {
                return self.reload();
            }).then(function () {
                // Directly activate department_detail tab and load content
                setTimeout(function () {
                    self._activateTabByName('department_detail');
                    self._loadDepartmentDetailView();
                }, 400);
            }).catch(function (error) {
                if (deptsGrid) {
                    deptsGrid.innerHTML = '<div style="text-align: center; padding: 20px; color: #e74c3c;">' +
                        '<i class="fa fa-exclamation-triangle" style="font-size: 24px;"></i>' +
                        '<p>Error loading department. Please try again.</p></div>';
                }
            });
        },

        _activateTab: function (tabName) {
            var self = this;

            // Map of tab names to their display text (for fallback matching)
            var tabTextMap = {
                'hierarchy': 'Hierarchy Home',
                'consolidated': 'Consolidated View',
                'config_detail': 'Salary Details',
                'department_detail': 'Department Detail'
            };

            // Method 1: Find by data-bs-target containing the page name
            var tabLink = document.querySelector('.nav-link[data-bs-target*="' + tabName + '"]');

            // Method 2: Try href attribute
            if (!tabLink) {
                tabLink = document.querySelector('.nav-link[href*="' + tabName + '"]');
            }

            // Method 3: Try name attribute directly
            if (!tabLink) {
                tabLink = document.querySelector('.nav-link[name="' + tabName + '"]');
            }

            // Method 4: Find the page element and get its associated tab
            if (!tabLink) {
                var pageDiv = document.querySelector('.tab-pane[name="' + tabName + '"]');
                if (!pageDiv) {
                    pageDiv = document.querySelector('[id*="' + tabName + '"].tab-pane');
                }
                if (pageDiv) {
                    var pageId = pageDiv.getAttribute('id');
                    if (pageId) {
                        tabLink = document.querySelector('.nav-link[data-bs-target="#' + pageId + '"]') ||
                                  document.querySelector('.nav-link[href="#' + pageId + '"]');
                    }
                }
            }

            // Method 5: Search by text content
            if (!tabLink) {
                var expectedText = tabTextMap[tabName] || tabName.replace('_', ' ');
                var allTabLinks = document.querySelectorAll('.nav-link');
                allTabLinks.forEach(function (link) {
                    if (link.textContent.trim().toLowerCase() === expectedText.toLowerCase()) {
                        tabLink = link;
                    }
                });
            }

            if (tabLink) {
                // Use setTimeout to ensure DOM is ready
                setTimeout(function () {
                    tabLink.click();
                    // Also try to manually add active class in case click doesn't work
                    var allTabLinks = document.querySelectorAll('.nav-link');
                    allTabLinks.forEach(function (l) {
                        l.classList.remove('active');
                    });
                    tabLink.classList.add('active');

                    // Show the corresponding pane
                    var targetId = tabLink.getAttribute('data-bs-target') || tabLink.getAttribute('href');
                    if (targetId) {
                        var allPanes = document.querySelectorAll('.tab-pane');
                        allPanes.forEach(function (pane) {
                            pane.classList.remove('show', 'active');
                        });
                        var targetPane = document.querySelector(targetId);
                        if (targetPane) {
                            targetPane.classList.add('show', 'active');
                        }
                    }

                    // Now load the view content
                    self._loadDepartmentDetailView();
                }, 100);
            }
        },

        // =================================================================
        // CONSOLIDATED VIEW
        // =================================================================

        _loadConsolidatedView: function () {
            var recordData = this.model.get(this.handle).data;
            var consolidatedJson = recordData.consolidated_data_json;

            if (!consolidatedJson) return;

            try {
                var data = JSON.parse(consolidatedJson);
                this._renderConsolidatedCharts(data);
                this._renderComponentsTable(data);
            } catch (e) {
                // JSON parsing error - silent fail
            }
        },

        _renderConsolidatedCharts: function (data) {
            var self = this;

            // Chart 1: Components by Category Type (Doughnut)
            if (data.grouped_by_type && document.getElementById('chart-consolidated-category')) {
                var labels = [];
                var values = [];
                var colors = [];

                Object.keys(data.grouped_by_type).forEach(function (catType) {
                    labels.push(categoryTypeLabels[catType] || catType);
                    values.push(data.grouped_by_type[catType].total);
                    colors.push(colorPalettes.categoryType[catType] || '#95a5a6');
                });

                this._destroyChart('chart-consolidated-category');
                this._createDoughnutChart('chart-consolidated-category', labels, values, colors);
            }

            // Chart 2: Top Components (Bar)
            if (data.components && document.getElementById('chart-consolidated-components')) {
                // Sort by total and take top 10
                var sortedComponents = data.components
                    .filter(function (c) { return c.total !== 0; })
                    .sort(function (a, b) { return Math.abs(b.total) - Math.abs(a.total); })
                    .slice(0, 10);

                var labels = sortedComponents.map(function (c) { return c.name; });
                var values = sortedComponents.map(function (c) { return c.total; });

                this._destroyChart('chart-consolidated-components');
                this._createBarChart('chart-consolidated-components', labels, values);
            }
        },

        _renderComponentsTable: function (data) {
            var table = document.getElementById('consolidated-components-table');
            if (!table || !data.components) return;

            var tbody = table.querySelector('tbody');
            if (!tbody) return;

            tbody.innerHTML = '';

            // Sort by category type then by total
            var sortedComponents = data.components.sort(function (a, b) {
                if (a.category_type !== b.category_type) {
                    return (a.category_type || '').localeCompare(b.category_type || '');
                }
                return Math.abs(b.total) - Math.abs(a.total);
            });

            sortedComponents.forEach(function (c) {
                var row = document.createElement('tr');
                var amountClass = c.total < 0 ? 'text-danger' : (c.total > 0 ? 'text-success' : '');

                row.innerHTML =
                    '<td><code>' + c.code + '</code></td>' +
                    '<td>' + c.name + '</td>' +
                    '<td>' + c.category + '</td>' +
                    '<td><span class="badge" style="background: ' + (colorPalettes.categoryType[c.category_type] || '#95a5a6') + '; color: white;">' +
                        (categoryTypeLabels[c.category_type] || c.category_type) + '</span></td>' +
                    '<td class="text-right ' + amountClass + '" style="font-weight: bold;">' + formatCurrency(c.total) + '</td>';

                tbody.appendChild(row);
            });
        },

        // =================================================================
        // CONFIG DETAIL VIEW
        // =================================================================

        _loadConfigDetailView: function () {
            var recordData = this.model.get(this.handle).data;
            var configJson = recordData.config_detail_data_json;

            if (!configJson) return;

            try {
                var data = JSON.parse(configJson);
                this._renderConfigDetailCharts(data);
                this._renderConfigDepartments(data);
            } catch (e) {
                // JSON parsing error - silent fail
            }
        },

        _renderConfigDetailCharts: function (data) {
            var self = this;

            // Chart: Components for this config (clickable to open pivot)
            if (data.components && document.getElementById('chart-config-components')) {
                var nonZeroComponents = data.components.filter(function (c) { return c.total !== 0; });
                var labels = nonZeroComponents.map(function (c) { return c.name; });
                var values = nonZeroComponents.map(function (c) { return Math.abs(c.total); });

                this._destroyChart('chart-config-components');
                this._createDoughnutChart('chart-config-components', labels, values, colorPalettes.primary, function (event, elements) {
                    if (elements && elements.length > 0) {
                        // Click on chart segment opens the config pivot
                        self._openConfigPivot();
                    }
                });
            }

            // Chart: By Department (clickable to drill down to department)
            if (data.departments && document.getElementById('chart-config-departments')) {
                // Aggregate totals by department
                var deptTotals = {};
                data.components.forEach(function (c) {
                    Object.keys(c.by_department || {}).forEach(function (dept) {
                        if (!deptTotals[dept]) deptTotals[dept] = 0;
                        deptTotals[dept] += Math.abs(c.by_department[dept]);
                    });
                });

                var deptLabels = Object.keys(deptTotals);
                var deptValues = deptLabels.map(function (d) { return deptTotals[d]; });

                this._destroyChart('chart-config-departments');
                this._createBarChart('chart-config-departments', deptLabels, deptValues, function (event, elements) {
                    if (elements && elements.length > 0) {
                        var clickedIndex = elements[0].index;
                        var deptName = deptLabels[clickedIndex];
                        // Find department ID and navigate
                        self._openDepartmentPivotByName(deptName);
                    }
                });
            }
        },

        _renderConfigDepartments: function (data) {
            var self = this;
            var grid = document.getElementById('config-departments-grid');
            if (!grid || !data.departments) return;

            grid.innerHTML = '';

            // Store department info for click handling
            var deptInfo = data.department_info || [];

            data.departments.forEach(function (deptName, index) {
                var style = colorPalettes.cardStyles[index % colorPalettes.cardStyles.length];
                var card = document.createElement('div');
                card.className = 'config-dept-card';
                card.dataset.departmentName = deptName;

                card.style.cssText = 'background: ' + style.bg + '; border-radius: 10px; padding: 18px; text-align: center; ' +
                    'cursor: pointer; border: 3px solid ' + style.border + '; ' +
                    'box-shadow: 0 0 15px ' + style.glow + ', 0 4px 12px ' + style.glow + '; ' +
                    'transition: all 0.3s ease;';

                card.innerHTML = '<i class="fa fa-building-o" style="color: ' + style.text + '; font-size: 18px; margin-bottom: 8px; display: block;"></i>' +
                    '<span style="font-weight: 700; color: ' + style.text + '; font-size: 14px;">' + deptName + '</span>';

                // Hover effects
                card.onmouseenter = function () {
                    this.style.transform = 'translateY(-3px) scale(1.02)';
                    this.style.boxShadow = '0 0 25px ' + style.glow + ', 0 8px 20px ' + style.glow;
                };
                card.onmouseleave = function () {
                    this.style.transform = 'translateY(0) scale(1)';
                    this.style.boxShadow = '0 0 15px ' + style.glow + ', 0 4px 12px ' + style.glow;
                };

                // Click to open pivot for this department
                card.onclick = function () {
                    self._openDepartmentPivotByName(deptName);
                };

                grid.appendChild(card);
            });
        },

        _openConfigPivot: function () {
            // Call the server action to open pivot view
            var self = this;
            var resId = this.model.get(this.handle).res_id;

            rpc.query({
                model: 'hr.formula.config.analytics',
                method: 'action_open_config_pivot',
                args: [[resId]]
            }).then(function (action) {
                self.do_action(action);
            });
        },

        _openDepartmentPivotByName: function (deptName) {
            // Call the server action to open pivot view filtered by department name
            var self = this;
            var resId = this.model.get(this.handle).res_id;

            rpc.query({
                model: 'hr.formula.config.analytics',
                method: 'action_open_pivot_by_department_name',
                args: [[resId], deptName]
            }).then(function (action) {
                self.do_action(action);
            });
        },

        // =================================================================
        // TAB NAVIGATION
        // =================================================================

        _onTabClick: function (ev) {
            var tabName = ev.currentTarget.getAttribute('name') ||
                          ev.currentTarget.closest('.nav-link')?.getAttribute('name') ||
                          ev.currentTarget.getAttribute('href')?.replace('#', '');

            var self = this;
            setTimeout(function () {
                switch (tabName) {
                    case 'hierarchy':
                        // Force render when user explicitly clicks hierarchy tab
                        self._loadHierarchyView(true);
                        break;
                    case 'consolidated':
                        self._loadConsolidatedView();
                        break;
                    case 'config_detail':
                        self._loadConfigDetailView();
                        break;
                    case 'department_detail':
                        self._loadDepartmentDetailView();
                        break;
                }
            }, 100);
        },

        _onFilterChange: function () {
            this.reload();
        },

        // =================================================================
        // CHART HELPERS
        // =================================================================

        _createDoughnutChart: function (elementId, labels, data, colors, onClick) {
            if (!window.Chart || !document.getElementById(elementId)) return;

            var ctx = document.getElementById(elementId).getContext('2d');
            this.charts[elementId] = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: labels,
                    datasets: [{
                        data: data,
                        backgroundColor: colors || colorPalettes.primary,
                        borderColor: '#fff',
                        borderWidth: 2
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    onClick: onClick || null,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: { padding: 15, font: { size: 11 }, usePointStyle: true }
                        },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    var sum = context.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                    var percentage = ((context.parsed / sum) * 100).toFixed(1);
                                    return context.label + ': ' + formatCurrency(context.parsed) + ' (' + percentage + '%)';
                                }
                            }
                        }
                    }
                }
            });

            // Add cursor pointer style when clickable
            if (onClick) {
                document.getElementById(elementId).style.cursor = 'pointer';
            }
        },

        _createBarChart: function (elementId, labels, data, onClick) {
            if (!window.Chart || !document.getElementById(elementId)) return;

            var ctx = document.getElementById(elementId).getContext('2d');
            this.charts[elementId] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Amount',
                        data: data,
                        backgroundColor: colorPalettes.gradient,
                        borderColor: colorPalettes.primary,
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    indexAxis: 'y',
                    onClick: onClick || null,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    return formatCurrency(context.parsed.x);
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                callback: function (value) { return formatCurrency(value); }
                            }
                        }
                    }
                }
            });

            // Add cursor pointer style when clickable
            if (onClick) {
                document.getElementById(elementId).style.cursor = 'pointer';
            }
        },

        _destroyChart: function (elementId) {
            if (this.charts[elementId]) {
                this.charts[elementId].destroy();
                delete this.charts[elementId];
            }
        },

        _destroyAllCharts: function () {
            var self = this;
            Object.keys(this.charts).forEach(function (key) {
                if (self.charts[key]) {
                    self.charts[key].destroy();
                }
            });
            this.charts = {};
        },

        // =================================================================
        // DEPARTMENT DETAIL VIEW
        // =================================================================

        _loadDepartmentDetailView: function () {
            var recordData = this.model.get(this.handle).data;
            var deptJson = recordData.department_detail_data_json;

            if (!deptJson || deptJson === '{}') {
                // Show message in the table
                var table = document.getElementById('employee-breakdown-table');
                if (table) {
                    var tbody = table.querySelector('tbody');
                    if (tbody) {
                        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #95a5a6; padding: 40px;">' +
                            '<i class="fa fa-info-circle" style="font-size: 24px;"></i>' +
                            '<p>No employee data available for the selected department and period.</p></td></tr>';
                    }
                }
                return;
            }

            try {
                var data = JSON.parse(deptJson);
                this._renderEmployeeTable(data);
            } catch (e) {
                // JSON parsing error - silent fail
            }
        },

        _renderEmployeeTable: function (data) {
            var table = document.getElementById('employee-breakdown-table');
            if (!table || !data.employees) return;

            // Get all unique component codes
            var componentCodes = [];
            data.employees.forEach(function (emp) {
                Object.keys(emp.components || {}).forEach(function (code) {
                    if (componentCodes.indexOf(code) === -1) {
                        componentCodes.push(code);
                    }
                });
            });

            // Update table header
            var thead = table.querySelector('thead tr');
            if (thead) {
                thead.innerHTML = '<th>Employee</th><th>Job Title</th>';
                componentCodes.forEach(function (code) {
                    thead.innerHTML += '<th class="text-right">' + code + '</th>';
                });
            }

            // Update table body
            var tbody = table.querySelector('tbody');
            if (tbody) {
                tbody.innerHTML = '';

                data.employees.forEach(function (emp) {
                    var row = document.createElement('tr');
                    row.innerHTML = '<td><strong>' + emp.name + '</strong></td>' +
                        '<td>' + (emp.job_title || '-') + '</td>';

                    componentCodes.forEach(function (code) {
                        var amount = emp.components[code] ? emp.components[code].total : 0;
                        var amountClass = amount < 0 ? 'text-danger' : '';
                        row.innerHTML += '<td class="text-right ' + amountClass + '">' + formatCurrency(amount) + '</td>';
                    });

                    tbody.appendChild(row);
                });
            }
        }
    });

    // =================================================================
    // REGISTER FORM VIEW
    // =================================================================

    var FormulaConfigAnalyticsFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: FormulaConfigAnalyticsController
        })
    });

    var viewRegistry = require('web.view_registry');
    viewRegistry.add('formula_config_analytics_dashboard', FormulaConfigAnalyticsFormView);

    return {
        Controller: FormulaConfigAnalyticsController,
        FormView: FormulaConfigAnalyticsFormView
    };
});
