/** @odoo-module **/

import { Component, onWillStart, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { rpc } from "@web/core/network/rpc";
import { session } from "@web/session";

/**
 * HR Development Dashboard Component
 * A comprehensive dashboard showing employee development metrics, charts, and activities
 */
export class HRDevelopmentDashboard extends Component {
    static template = "hr_development_ai.DevelopmentDashboard";
    static props = ["*"];

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        // Get user ID from session
        this.userId = session.uid;

        this.skillsCategoryChart = useRef("skillsCategoryChart");
        this.skillsLevelChart = useRef("skillsLevelChart");
        this.learningChart = useRef("learningChart");

        this.state = useState({
            isLoading: true,
            employee: {},
            skills: {},
            learning: {},
            certifications: {},
            coaching: {},
            mentorship: {},
            developmentPlans: {},
            recentActivities: [],
            skillGaps: [],
            charts: {},
            teamStats: {},
            showTeamView: false,
        });

        this.charts = {};

        onWillStart(async () => {
            await this.loadChartJS();
            await this.loadDashboardData();
        });

        onMounted(() => {
            this.initializeCharts();
        });
    }

    async loadChartJS() {
        if (typeof Chart === 'undefined') {
            await loadJS("https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js");
        }
    }

    async loadDashboardData() {
        try {
            const data = await rpc("/web/dataset/call_kw/hr.development.dashboard/get_dashboard_stats", {
                model: "hr.development.dashboard",
                method: "get_dashboard_stats",
                args: [],
                kwargs: {},
            });

            this.state.employee = data.employee || {};
            this.state.skills = data.skills || {};
            this.state.learning = data.learning || {};
            this.state.certifications = data.certifications || {};
            this.state.coaching = data.coaching || {};
            this.state.mentorship = data.mentorship || {};
            this.state.developmentPlans = data.development_plans || {};
            this.state.recentActivities = data.recent_activities || [];
            this.state.skillGaps = data.skill_gaps || [];
            this.state.charts = data.charts || {};
            this.state.teamStats = data.team_stats || {};
            this.state.isLoading = false;
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.isLoading = false;
            this.notification.add("Error loading dashboard data", { type: "danger" });
        }
    }

    initializeCharts() {
        if (typeof Chart === 'undefined') {
            console.warn("Chart.js not loaded");
            return;
        }

        this._initSkillsCategoryChart();
        this._initSkillsLevelChart();
        this._initLearningChart();
    }

    _initSkillsCategoryChart() {
        const ctx = this.skillsCategoryChart.el;
        if (!ctx || !this.state.charts.skills_by_category) return;

        const data = this.state.charts.skills_by_category;

        if (this.charts.skillsCategory) {
            this.charts.skillsCategory.destroy();
        }

        this.charts.skillsCategory = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: [{
                    data: data.data || [],
                    backgroundColor: data.colors || [
                        '#3498db', '#2ecc71', '#f39c12', '#e74c3c', '#9b59b6', '#1abc9c'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    title: {
                        display: false
                    }
                }
            }
        });
    }

    _initSkillsLevelChart() {
        const ctx = this.skillsLevelChart.el;
        if (!ctx || !this.state.charts.skills_by_level) return;

        const data = this.state.charts.skills_by_level;

        if (this.charts.skillsLevel) {
            this.charts.skillsLevel.destroy();
        }

        this.charts.skillsLevel = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: 'Skills by Proficiency',
                    data: data.data || [],
                    backgroundColor: data.colors || [
                        '#e74c3c', '#f39c12', '#f1c40f', '#2ecc71', '#27ae60'
                    ],
                    borderWidth: 0,
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        },
                        grid: {
                            display: true,
                            color: 'rgba(0,0,0,0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    _initLearningChart() {
        const ctx = this.learningChart.el;
        if (!ctx || !this.state.charts.learning_completion) return;

        const data = this.state.charts.learning_completion;

        if (this.charts.learning) {
            this.charts.learning.destroy();
        }

        this.charts.learning = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Completed', 'In Progress', 'Not Started'],
                datasets: [{
                    data: [data.completed || 0, data.in_progress || 0, data.not_started || 0],
                    backgroundColor: ['#27ae60', '#f39c12', '#bdc3c7'],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    }
                }
            }
        });
    }

    // Action handlers
    _getEmployeeId() {
        return this.state.employee && this.state.employee.id ? this.state.employee.id : null;
    }

    _ensureEmployee() {
        const employeeId = this._getEmployeeId();
        if (!employeeId) {
            this.notification.add("Employee record not found for your user.", { type: "warning" });
            return null;
        }
        return employeeId;
    }

    openSkills() {
        const employeeId = this._ensureEmployee();
        if (!employeeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "My Skills",
            res_model: "hr.employee.skill",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["employee_id", "=", employeeId]],
            context: {}
        });
    }

    openLearning() {
        const employeeId = this._ensureEmployee();
        if (!employeeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "My Learning",
            res_model: "hr.learning.enrollment",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["employee_id", "=", employeeId]],
            context: {}
        });
    }

    openCertifications() {
        const employeeId = this._ensureEmployee();
        if (!employeeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "My Certifications",
            res_model: "hr.certification",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["employee_id", "=", employeeId]],
            context: {}
        });
    }

    openCoaching() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "AI Coaching",
            res_model: "ai.coaching.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: {}
        });
    }

    openMentorship() {
        const employeeId = this._ensureEmployee();
        if (!employeeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "My Mentorships",
            res_model: "hr.mentorship",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [
                "|",
                ["mentor_id", "=", employeeId],
                ["mentee_id", "=", employeeId]
            ],
            context: {}
        });
    }

    openDevelopmentPlans() {
        const employeeId = this._ensureEmployee();
        if (!employeeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "My Development Plans",
            res_model: "hr.development.plan",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["employee_id", "=", employeeId]],
            context: {}
        });
    }

    openSkillGaps() {
        const employeeId = this._ensureEmployee();
        if (!employeeId) return;
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Skill Gaps",
            res_model: "hr.skill.gap",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain: [["employee_id", "=", employeeId]],
            context: {}
        });
    }

    openCareerPaths() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Career Paths",
            res_model: "hr.career.path",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            context: {}
        });
    }

    openLearningPaths() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Learning Paths",
            res_model: "hr.learning.path",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            context: {}
        });
    }

    toggleTeamView() {
        this.state.showTeamView = !this.state.showTeamView;
    }

    openTeamMember(memberId) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Employee Profile",
            res_model: "hr.employee",
            res_id: memberId,
            view_mode: "form",
            views: [[false, "form"]],
            context: {}
        });
    }

    async refreshDashboard() {
        this.state.isLoading = true;
        await this.loadDashboardData();
        this.initializeCharts();
    }
}

// Register as a client action
registry.category("actions").add("hr_development_dashboard", HRDevelopmentDashboard);
