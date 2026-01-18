/* Salary Structure Analytics Dashboard - Formula Config Analytics Controller */

console.log('[Formula Config Analytics] Dashboard.js file loaded');

odoo.define('pb_hr_payroll_analytics.FormulaConfigAnalytics', function (require) {
    'use strict';

    console.log('[Formula Config Analytics] Module definition starting...');

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var rpc = require('web.rpc');

    // Load Chart Library
    var ChartLib;
    try {
        ChartLib = require('pb_hr_payroll_analytics.Charts');
        console.log('[Formula Config Analytics] ChartLib loaded successfully');
    } catch (e) {
        console.warn('[Formula Config Analytics] ChartLib not available, will use fallback');
        ChartLib = window.ChartLib || {};
    }

    // Color palettes for charts
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
            console.log('[Formula Config Analytics] Controller init');
            this._super.apply(this, arguments);
            this.charts = {};
            this.chartJSLoaded = false;
            this.currentData = {};
        },

        willStart: function () {
            console.log('[Formula Config Analytics] willStart');
            return Promise.all([
                this._super.apply(this, arguments),
                this._loadChartJS()
            ]);
        },

        start: function () {
            console.log('[Formula Config Analytics] start');
            return this._super.apply(this, arguments).then(() => {
                setTimeout(() => this._setupDashboard(), 500);
            });
        },

        on_attach_callback: function () {
            console.log('[Formula Config Analytics] View re-attached');
            var self = this;
            setTimeout(function () {
                self._setupDashboard();
            }, 300);
        },

        destroy: function () {
            console.log('[Formula Config Analytics] Destroying charts');
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
                    console.log('[Formula Config Analytics] Chart.js already loaded');
                    self.chartJSLoaded = true;
                    resolve();
                    return;
                }

                console.log('[Formula Config Analytics] Loading Chart.js from CDN...');
                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
                script.onload = function () {
                    console.log('[Formula Config Analytics] Chart.js loaded successfully');
                    self.chartJSLoaded = true;
                    resolve();
                };
                script.onerror = function () {
                    console.error('[Formula Config Analytics] Failed to load Chart.js');
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
            console.log('[Formula Config Analytics] Setting up dashboard');
            var recordData = this.model.get(this.handle).data;
            var activeView = recordData.active_view || 'hierarchy';

            console.log('[Formula Config Analytics] Active view:', activeView);

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
            console.log('[Formula Config Analytics] _activateTabByName:', tabName);

            // Map of page names to their expected tab text
            var tabTextMap = {
                'hierarchy': 'Hierarchy Home',
                'consolidated': 'Consolidated View',
                'config_detail': 'Config Detail',
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

            console.log('[Formula Config Analytics] Tab target index:', targetIndex, 'Total tabs:', tabs.length);

            if (targetIndex >= 0 && tabs[targetIndex]) {
                console.log('[Formula Config Analytics] Clicking tab:', tabs[targetIndex].textContent);
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
            } else {
                console.log('[Formula Config Analytics] Could not find tab. Available tabs:');
                tabs.forEach(function (t, i) {
                    console.log('  Tab', i, ':', t.textContent.trim());
                });
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
                console.log('[Formula Config Analytics] Skipping hierarchy auto-render, active view:', activeView);
                return;
            }

            if (!hierarchyJson) {
                console.log('[Formula Config Analytics] No hierarchy data available');
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
                console.error('[Formula Config Analytics] Error parsing hierarchy data:', e);
            }
        },

        _renderHierarchy: function (data) {
            var self = this;
            console.log('[Formula Config Analytics] Rendering hierarchy with', data.configs.length, 'configs');

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
                    card.style.cssText = 'background: white; border-radius: 12px; padding: 0; cursor: pointer; ' +
                        'box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.3s, box-shadow 0.3s; overflow: hidden;';

                    var gradientColors = colorPalettes.gradient[index % colorPalettes.gradient.length];

                    card.innerHTML =
                        '<div style="background: ' + gradientColors + '; padding: 15px; color: white;">' +
                            '<div style="display: flex; align-items: center; gap: 10px;">' +
                                '<i class="fa fa-file-text" style="font-size: 24px;"></i>' +
                                '<div>' +
                                    '<h5 style="margin: 0; font-size: 16px;">' + config.name + '</h5>' +
                                    '<span style="opacity: 0.9; font-size: 12px;">' + (config.code || '') + '</span>' +
                                '</div>' +
                            '</div>' +
                        '</div>' +
                        '<div style="padding: 15px;">' +
                            '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px;">' +
                                '<div style="text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px;">' +
                                    '<div style="font-size: 11px; color: #7f8c8d;">Country</div>' +
                                    '<div style="font-size: 14px; font-weight: bold; color: #2c3e50;">' + (config.country_code || '-') + '</div>' +
                                '</div>' +
                                '<div style="text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px;">' +
                                    '<div style="font-size: 11px; color: #7f8c8d;">Cycle</div>' +
                                    '<div style="font-size: 14px; font-weight: bold; color: #2c3e50;">' + (config.cycle_type || 'regular') + '</div>' +
                                '</div>' +
                            '</div>' +
                            '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">' +
                                '<div style="text-align: center; padding: 10px; background: #e8f4fd; border-radius: 8px;">' +
                                    '<div style="font-size: 11px; color: #3498db;">Employees</div>' +
                                    '<div style="font-size: 18px; font-weight: bold; color: #2980b9;">' + config.employee_count + '</div>' +
                                '</div>' +
                                '<div style="text-align: center; padding: 10px; background: #e8f6ef; border-radius: 8px;">' +
                                    '<div style="font-size: 11px; color: #27ae60;">Departments</div>' +
                                    '<div style="font-size: 18px; font-weight: bold; color: #229954;">' + config.departments.length + '</div>' +
                                '</div>' +
                            '</div>' +
                            '<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #ecf0f1; text-align: center;">' +
                                '<div style="font-size: 12px; color: #7f8c8d;">Total Cost</div>' +
                                '<div style="font-size: 20px; font-weight: bold; color: #2c3e50;">' + formatCurrency(config.total_cost) + '</div>' +
                            '</div>' +
                        '</div>' +
                        '<div style="background: #f8f9fa; padding: 10px 15px; display: flex; justify-content: space-between; align-items: center;">' +
                            '<span style="color: #7f8c8d; font-size: 12px;">Click to drill down</span>' +
                            '<i class="fa fa-chevron-right" style="color: #3498db;"></i>' +
                        '</div>';

                    // Hover effects
                    card.onmouseenter = function () {
                        this.style.transform = 'translateY(-5px)';
                        this.style.boxShadow = '0 8px 25px rgba(0,0,0,0.15)';
                    };
                    card.onmouseleave = function () {
                        this.style.transform = 'translateY(0)';
                        this.style.boxShadow = '0 4px 15px rgba(0,0,0,0.1)';
                    };

                    configsGrid.appendChild(card);
                });
            }
        },

        _onConfigClick: function (ev) {
            var configId = parseInt(ev.currentTarget.dataset.configId);
            var self = this;

            console.log('[Formula Config Analytics] Config clicked:', configId);

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
            }).then(function () {
                console.log('[Formula Config Analytics] Navigation state updated');
                // Optionally reload to show config_detail tab with charts
                // self.reload().then(function () {
                //     setTimeout(function () { self._activateTab('config_detail'); }, 300);
                // });
            });
        },

        _showDepartmentsForConfig: function (config) {
            var self = this;
            var deptsGrid = document.getElementById('departments-grid');

            if (!deptsGrid) return;

            deptsGrid.style.display = 'block';
            deptsGrid.innerHTML = '<h4 style="grid-column: 1/-1; color: #2c3e50; margin-bottom: 15px;">' +
                '<i class="fa fa-sitemap"></i> Departments in <strong>' + config.name + '</strong></h4>';
            deptsGrid.style.cssText += 'display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; ' +
                'margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 10px;';

            if (config.departments.length === 0) {
                deptsGrid.innerHTML += '<div style="text-align: center; color: #95a5a6; padding: 20px;">' +
                    '<p>No departments found for this config.</p></div>';
                return;
            }

            config.departments.forEach(function (dept, index) {
                var card = document.createElement('div');
                card.className = 'department-card';
                card.dataset.configId = config.id;
                card.dataset.departmentId = dept.id;
                card.style.cssText = 'background: white; border-radius: 8px; padding: 15px; cursor: pointer; ' +
                    'border-left: 4px solid ' + colorPalettes.primary[index % colorPalettes.primary.length] + '; ' +
                    'box-shadow: 0 2px 8px rgba(0,0,0,0.08); transition: transform 0.2s;';

                card.innerHTML =
                    '<div style="font-weight: bold; color: #2c3e50; margin-bottom: 8px;">' +
                        '<i class="fa fa-users" style="margin-right: 5px;"></i>' + dept.name +
                    '</div>' +
                    '<div style="display: flex; justify-content: space-between; font-size: 12px; color: #7f8c8d;">' +
                        '<span>' + dept.employee_count + ' employees</span>' +
                        '<span style="color: #27ae60; font-weight: bold;">' + formatCurrency(dept.gross_pay) + '</span>' +
                    '</div>';

                card.onmouseenter = function () {
                    this.style.transform = 'translateX(5px)';
                };
                card.onmouseleave = function () {
                    this.style.transform = 'translateX(0)';
                };

                deptsGrid.appendChild(card);
            });
        },

        _onDepartmentClick: function (ev) {
            var configId = parseInt(ev.currentTarget.dataset.configId);
            var departmentId = parseInt(ev.currentTarget.dataset.departmentId);
            var self = this;
            var resId = this.model.get(this.handle).res_id;

            console.log('[Formula Config Analytics] Department clicked:', departmentId, 'Config:', configId, 'Record ID:', resId);

            // Show loading indicator
            var deptsGrid = document.getElementById('departments-grid');
            if (deptsGrid) {
                deptsGrid.innerHTML = '<div style="text-align: center; padding: 20px; color: #3498db;">' +
                    '<i class="fa fa-spinner fa-spin" style="font-size: 24px;"></i>' +
                    '<p>Loading department details...</p></div>';
            }

            console.log('[Formula Config Analytics] Making RPC call to action_navigate_to_department...');

            rpc.query({
                model: 'hr.formula.config.analytics',
                method: 'action_navigate_to_department',
                args: [[resId], configId, departmentId]
            }).then(function (result) {
                console.log('[Formula Config Analytics] RPC call successful, result:', result);
                console.log('[Formula Config Analytics] Calling reload...');
                return self.reload();
            }).then(function () {
                console.log('[Formula Config Analytics] Reload completed successfully');
                // Directly activate department_detail tab and load content
                // Don't rely on on_attach_callback or active_view field
                console.log('[Formula Config Analytics] Directly activating department_detail tab');
                setTimeout(function () {
                    self._activateTabByName('department_detail');
                    self._loadDepartmentDetailView();
                }, 400);
            }).catch(function (error) {
                console.error('[Formula Config Analytics] Error navigating to department:', error);
                console.error('[Formula Config Analytics] Error details:', JSON.stringify(error));
                if (deptsGrid) {
                    deptsGrid.innerHTML = '<div style="text-align: center; padding: 20px; color: #e74c3c;">' +
                        '<i class="fa fa-exclamation-triangle" style="font-size: 24px;"></i>' +
                        '<p>Error loading department. Please try again.</p></div>';
                }
            });
        },

        _activateTab: function (tabName) {
            var self = this;
            console.log('[Formula Config Analytics] Attempting to activate tab:', tabName);

            // Map of tab names to their display text (for fallback matching)
            var tabTextMap = {
                'hierarchy': 'Hierarchy Home',
                'consolidated': 'Consolidated View',
                'config_detail': 'Config Detail',
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
                console.log('[Formula Config Analytics] Found tab link, clicking:', tabLink);
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
            } else {
                console.log('[Formula Config Analytics] Could not find tab:', tabName);
                console.log('[Formula Config Analytics] Available tabs:', document.querySelectorAll('.nav-link'));
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
                console.error('[Formula Config Analytics] Error parsing consolidated data:', e);
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
                console.error('[Formula Config Analytics] Error parsing config detail data:', e);
            }
        },

        _renderConfigDetailCharts: function (data) {
            // Chart: Components for this config
            if (data.components && document.getElementById('chart-config-components')) {
                var nonZeroComponents = data.components.filter(function (c) { return c.total !== 0; });
                var labels = nonZeroComponents.map(function (c) { return c.name; });
                var values = nonZeroComponents.map(function (c) { return Math.abs(c.total); });

                this._destroyChart('chart-config-components');
                this._createDoughnutChart('chart-config-components', labels, values, colorPalettes.primary);
            }

            // Chart: By Department
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
                this._createBarChart('chart-config-departments', deptLabels, deptValues);
            }
        },

        _renderConfigDepartments: function (data) {
            var grid = document.getElementById('config-departments-grid');
            if (!grid || !data.departments) return;

            grid.innerHTML = '';

            data.departments.forEach(function (deptName, index) {
                var card = document.createElement('div');
                card.style.cssText = 'background: #f8f9fa; border-radius: 8px; padding: 15px; text-align: center; ' +
                    'border-left: 4px solid ' + colorPalettes.primary[index % colorPalettes.primary.length] + ';';
                card.innerHTML = '<i class="fa fa-building-o" style="color: ' + colorPalettes.primary[index % colorPalettes.primary.length] + ';"></i> ' +
                    '<span style="font-weight: bold;">' + deptName + '</span>';
                grid.appendChild(card);
            });
        },

        // =================================================================
        // TAB NAVIGATION
        // =================================================================

        _onTabClick: function (ev) {
            var tabName = ev.currentTarget.getAttribute('name') ||
                          ev.currentTarget.closest('.nav-link')?.getAttribute('name') ||
                          ev.currentTarget.getAttribute('href')?.replace('#', '');

            console.log('[Formula Config Analytics] Tab clicked:', tabName);

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
            console.log('[Formula Config Analytics] Filter changed, reloading...');
            this.reload();
        },

        // =================================================================
        // CHART HELPERS
        // =================================================================

        _createDoughnutChart: function (elementId, labels, data, colors) {
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
        },

        _createBarChart: function (elementId, labels, data) {
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
            console.log('[Formula Config Analytics] Loading department detail view');
            var recordData = this.model.get(this.handle).data;
            var deptJson = recordData.department_detail_data_json;

            console.log('[Formula Config Analytics] Department JSON data:', deptJson ? deptJson.substring(0, 200) + '...' : 'null');

            // Check if we have a selected department
            var selectedDept = recordData.selected_department_id;
            var selectedConfig = recordData.selected_config_id;
            console.log('[Formula Config Analytics] Selected config:', selectedConfig, 'department:', selectedDept);

            if (!deptJson || deptJson === '{}') {
                console.log('[Formula Config Analytics] No department detail data available');
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
                console.log('[Formula Config Analytics] Parsed department data:', data.department, 'employees:', data.employee_count);
                this._renderEmployeeTable(data);
            } catch (e) {
                console.error('[Formula Config Analytics] Error parsing department detail data:', e);
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

    console.log('[Formula Config Analytics] Module registered successfully');

    return {
        Controller: FormulaConfigAnalyticsController,
        FormView: FormulaConfigAnalyticsFormView
    };
});
