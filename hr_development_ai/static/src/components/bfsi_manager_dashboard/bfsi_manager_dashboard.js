/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

/* ── Chart.js state ── */
let chartJSLoaded = false;
let chartInstances = {};

/* Load Inter font once (CSS itself is loaded via web.assets_backend in manifest) */
if (!document.getElementById('bfsi-font-inter')) {
    const fontLink = document.createElement('link');
    fontLink.rel = 'stylesheet';
    fontLink.id = 'bfsi-font-inter';
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap';
    document.head.appendChild(fontLink);
}

const CHART_COLORS = {
    primary: '#7C3AED',
    primaryLight: 'rgba(124, 58, 237, 0.15)',
    indigo: '#4F46E5',
    success: '#10B981',
    successLight: 'rgba(16, 185, 129, 0.15)',
    warning: '#F59E0B',
    warningLight: 'rgba(245, 158, 11, 0.15)',
    danger: '#EF4444',
    dangerLight: 'rgba(239, 68, 68, 0.15)',
    info: '#3B82F6',
    infoLight: 'rgba(59, 130, 246, 0.15)',
    palette: [
        '#7C3AED', '#3B82F6', '#10B981', '#F59E0B', '#EF4444',
        '#6366F1', '#8B5CF6', '#14B8A6', '#F97316', '#EC4899',
    ],
};

const loadChartJS = async () => {
    if (chartJSLoaded) return true;
    try {
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js';
        document.head.appendChild(script);
        await new Promise((ok, fail) => {
            script.onload = ok;
            script.onerror = fail;
        });
        chartJSLoaded = true;
        return true;
    } catch (e) {
        console.error('BfsiDash: failed to load Chart.js', e);
        return false;
    }
};

const destroyChart = (key) => {
    if (chartInstances[key]) {
        try { chartInstances[key].destroy(); } catch (_) { }
        delete chartInstances[key];
    }
};

/**
 * BFSI Manager Dashboard — Premium UI
 *
 * Features:
 * - Premium gradient header with KPI summary strip
 * - Card-based team grid with SVG score rings
 * - Click-to-open banker detail modal with tabs
 * - Chart.js charts (distribution, ranking, radar, trend)
 * - Quick filters and sort controls
 */
export class BfsiManagerDashboard extends Component {
    static template = "hr_development_ai.BfsiManagerDashboard";
    static props = ["*"];

    setup() {

        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            // Dashboard state
            isLoading: true,
            error: null,

            // Manager info
            managerId: null,
            managerName: '',
            branchId: null,
            branchName: '',

            // Team data
            teamMembers: [],
            needsCoachingCount: 0,

            // Summary metrics
            avgTeamScore: 0,
            totalSessions: 0,
            actionPlanCompletion: 0,

            // Filters
            sortBy: 'rank',
            sortOrder: 'asc',
            filterPriority: 'all',

            // Banker Detail Modal
            showBankerModal: false,
            bankerDetail: null,
            modalTab: 'profile',

            // Coaching/Plans filter state
            coachingFilter: 'this_month',
            coachingDateFrom: '',
            coachingDateTo: '',
            plansFilter: 'this_month',
            plansDateFrom: '',
            plansDateTo: '',

            // Banker self-performance mode
            isBankerMode: false,
            bankerSelf: null,
            myPerformance: null,
        });

        onWillStart(async () => {
            await this.loadManagerContext();
            await this.loadTeamData();
        });

        onMounted(async () => {
            this.state.isLoading = false;
            // Render dashboard charts after data is loaded
            if (this.state.isBankerMode) {
                await this.renderBankerMiniCharts();
            } else {
                await this.renderDashboardCharts();
            }
        });
    }

    /* ━━━ ROLE DISPLAY HELPER ━━━ */

    formatRole(banker) {
        if (banker.job_id && banker.job_id[1]) return banker.job_id[1];
        const ROLE_LABELS = {
            'rm': 'Relationship Manager',
            'branch_manager': 'Branch Manager',
            'regional_manager': 'Regional Manager',
            'telesales': 'Telesales Agent',
            'field_sales': 'Field Sales Officer',
            'loan_officer': 'Loan Officer',
            'insurance_advisor': 'Insurance Advisor',
            'wealth_manager': 'Wealth Manager',
            'banker': 'Banker',
        };
        return ROLE_LABELS[banker.banker_type] || banker.banker_type || 'Banker';
    }

    /* ━━━ SCORE RING HELPERS ━━━ */

    getScoreRingDasharray() {
        const circumference = 2 * Math.PI * 16; // r=16
        return `${circumference} ${circumference}`;
    }

    getScoreRingOffset(score) {
        const circumference = 2 * Math.PI * 16;
        const pct = Math.min(100, Math.max(0, score || 0)) / 100;
        return circumference - (pct * circumference);
    }

    getScoreRingClass(score) {
        if (score >= 75) return 'bfsi-score-high';
        if (score >= 50) return 'bfsi-score-medium';
        return 'bfsi-score-low';
    }

    getScoreBadgeClass(score) {
        if (score >= 75) return 'low';
        if (score >= 50) return 'medium';
        return 'critical';
    }

    getBadgeClass(badge) {
        const d = this.state.bankerDetail || {};
        switch (badge) {
            case 'top_performer': return (d.score || 0) >= 80 ? 'earned' : 'locked';
            case 'podium': return (d.rank || 99) <= 3 ? 'earned' : 'locked';
            case 'climber': return (d.movement || 0) >= 3 ? 'earned' : 'locked';
            case 'coach_fav': return (d.sessions_count || 0) >= 5 ? 'earned' : 'locked';
            case 'action_taker': return (d.plans_count || 0) >= 1 ? 'earned' : 'locked';
            case 'excellence': return (d.score || 0) >= 90 ? 'earned' : 'locked';
            default: return 'locked';
        }
    }

    /* ━━━ DATA LOADING ━━━ */

    async loadManagerContext() {
        try {
            // Use server-side method that uses sudo() to bypass
            // hr.employee public profile field restrictions
            const ctx = await this.orm.call(
                'hr.employee',
                'get_dashboard_context',
                []
            );

            if (ctx.error) {
                this.state.error = ctx.error;
                return;
            }

            this.state.managerId = ctx.id;
            this.state.managerName = ctx.name;
            this.state.branchId = ctx.branch_id || false;
            this.state.branchName = ctx.branch_name || '';

            if (ctx.is_manager) {
                this.state.isBankerMode = false;

                // Populate team data from server context
                this.state.teamMembers = ctx.team_members || [];

                // Calculate summary metrics
                const bankers = this.state.teamMembers;
                this.state.needsCoachingCount = bankers.filter(
                    b => b.coaching_priority === 'high' || b.coaching_priority === 'critical'
                ).length;

                if (bankers.length > 0) {
                    this.state.avgTeamScore = bankers.reduce(
                        (sum, b) => sum + (b.latest_overall_score || 0), 0
                    ) / bankers.length;

                    this.state.totalSessions = bankers.reduce(
                        (sum, b) => sum + (b.coaching_sessions_received || 0), 0
                    );

                    const withPlans = bankers.filter(b => b.active_action_plan_count > 0);
                    if (withPlans.length > 0) {
                        this.state.actionPlanCompletion = withPlans.reduce(
                            (sum, b) => sum + (b.action_plan_completion_rate || 0), 0
                        ) / withPlans.length;
                    }
                }
            } else {
                // Banker mode - show personal dashboard
                this.state.isBankerMode = true;
                this.state.bankerSelf = ctx;
            }
        } catch (error) {
            console.error('Error loading manager context:', error);
            this.state.error = 'Failed to load dashboard data';
        }
    }

    async loadTeamData() {
        // For manager mode, team data is already loaded in loadManagerContext
        if (!this.state.isBankerMode) {
            return;
        }

        // Banker mode: load personal performance data
        await this._loadBankerSelfData();
    }

    /* ━━━ BANKER SELF-PERFORMANCE DATA ━━━ */

    async _loadBankerSelfData() {
        try {
            const empId = this.state.managerId;

            // Load KPI history
            const kpis = await this.orm.searchRead(
                'bfsi.performance.kpi',
                [['employee_id', '=', empId]],
                ['overall_score', 'revenue', 'conversions', 'period_date',
                    'branch_rank', 'rank_movement', 'coaching_priority'],
                { order: 'period_date desc', limit: 12 }
            );

            // Load coaching sessions
            let sessions = [];
            try {
                sessions = await this.orm.searchRead(
                    'hr.coaching.session',
                    [['employee_id', '=', empId]],
                    ['name', 'session_date', 'session_type', 'state'],
                    { order: 'session_date desc', limit: 10 }
                );
            } catch (_) { }

            // Load action plans
            let plans = [];
            try {
                plans = await this.orm.searchRead(
                    'bfsi.action.plan',
                    [['employee_id', '=', empId]],
                    ['name', 'state', 'progress_percentage', 'create_date', 'action_item_count'],
                    { order: 'create_date desc', limit: 5 }
                );
            } catch (_) { }

            const emp = this.state.bankerSelf;
            this.state.myPerformance = {
                score: emp.latest_overall_score || 0,
                rank: emp.current_month_rank || '-',
                movement: emp.rank_movement || 0,
                priority: emp.coaching_priority || 'low',
                sessions_count: emp.coaching_sessions_received || 0,
                plans_count: emp.active_action_plan_count || 0,
                plan_completion: emp.action_plan_completion_rate || 0,
                kpi_history: kpis,
                sessions: sessions,
                plans: plans,
            };
        } catch (error) {
            console.error('Error loading banker self data:', error);
            this.state.error = 'Failed to load your performance data';
        }
    }

    /**
     * Group KPI history by month for collapsible display
     */
    get groupedKpiHistory() {
        const kpis = this.state.myPerformance?.kpi_history || [];
        const groups = {};
        const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'];

        for (const kpi of kpis) {
            const dateStr = kpi.period_date || '';
            if (!dateStr) continue;
            const parts = dateStr.split('-');
            const year = parts[0];
            const monthIdx = parseInt(parts[1], 10) - 1;
            const monthLabel = `${MONTHS[monthIdx] || parts[1]} ${year}`;
            if (!groups[monthLabel]) {
                groups[monthLabel] = { label: monthLabel, sortKey: dateStr.slice(0, 7), items: [], expanded: true };
            }
            groups[monthLabel].items.push(kpi);
        }

        // Sort groups descending
        return Object.values(groups).sort((a, b) => b.sortKey.localeCompare(a.sortKey));
    }

    toggleKpiGroup(groupLabel) {
        // Toggle group expansion in the grouped view
        if (!this._kpiGroupState) this._kpiGroupState = {};
        this._kpiGroupState[groupLabel] = !this._kpiGroupState[groupLabel];
        // Force re-render
        this.state.myPerformance = { ...this.state.myPerformance };
    }

    isKpiGroupCollapsed(groupLabel) {
        if (!this._kpiGroupState) return false;
        return !!this._kpiGroupState[groupLabel];
    }

    /* ━━━ BANKER MINI TREND CHARTS ━━━ */

    async renderBankerMiniCharts() {
        const kpis = this.state.myPerformance?.kpi_history || [];
        if (!kpis.length) return;
        if (!await loadChartJS()) return;

        // Wait for DOM
        await new Promise(r => setTimeout(r, 300));

        // Reverse so oldest first for chart X axis
        const sorted = [...kpis].reverse();
        const labels = sorted.map(k => {
            const d = k.period_date || '';
            return d.slice(5); // MM-DD
        });

        const miniOpts = (yReverse = false) => ({
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false }, tooltip: { enabled: true, mode: 'index', intersect: false } },
            scales: {
                x: { display: false },
                y: { display: false, reverse: yReverse },
            },
            elements: {
                point: { radius: 0, hoverRadius: 3 },
                line: { tension: 0.4, borderWidth: 2 },
                bar: { borderRadius: 3 },
            },
            interaction: { mode: 'nearest', axis: 'x', intersect: false },
        });

        // 1) Score Trend (area)
        const scoreCanvas = document.getElementById('banker_score_trend');
        if (scoreCanvas) {
            destroyChart('banker_score');
            const ctx = scoreCanvas.getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, 0, 70);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.3)');
            gradient.addColorStop(1, 'rgba(99, 102, 241, 0.02)');
            chartInstances['banker_score'] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        data: sorted.map(k => Math.round(k.overall_score || 0)),
                        borderColor: '#6366F1',
                        backgroundColor: gradient,
                        fill: true,
                    }]
                },
                options: miniOpts(),
            });
        }

        // 2) Revenue Trend (bar)
        const revCanvas = document.getElementById('banker_revenue_trend');
        if (revCanvas) {
            destroyChart('banker_revenue');
            const ctx = revCanvas.getContext('2d');
            chartInstances['banker_revenue'] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        data: sorted.map(k => k.revenue || 0),
                        backgroundColor: 'rgba(16, 185, 129, 0.5)',
                        borderColor: '#10B981',
                        borderWidth: 1,
                    }]
                },
                options: miniOpts(),
            });
        }

        // 3) Rank Trend (line - reversed Y so lower=higher)
        const rankCanvas = document.getElementById('banker_rank_trend');
        if (rankCanvas) {
            destroyChart('banker_rank');
            const ctx = rankCanvas.getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, 0, 70);
            gradient.addColorStop(0, 'rgba(245, 158, 11, 0.25)');
            gradient.addColorStop(1, 'rgba(245, 158, 11, 0.02)');
            chartInstances['banker_rank'] = new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        data: sorted.map(k => k.branch_rank || 0),
                        borderColor: '#F59E0B',
                        backgroundColor: gradient,
                        fill: true,
                    }]
                },
                options: miniOpts(true), // reversed Y
            });
        }

        // 4) Conversions (bar)
        const convCanvas = document.getElementById('banker_conversions_trend');
        if (convCanvas) {
            destroyChart('banker_conv');
            const ctx = convCanvas.getContext('2d');
            chartInstances['banker_conv'] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels,
                    datasets: [{
                        data: sorted.map(k => k.conversions || 0),
                        backgroundColor: 'rgba(124, 58, 237, 0.45)',
                        borderColor: '#7C3AED',
                        borderWidth: 1,
                    }]
                },
                options: miniOpts(),
            });
        }
    }

    /* ━━━ DASHBOARD CHARTS ━━━ */

    async renderDashboardCharts() {
        if (!this.state.teamMembers.length) return;
        if (!await loadChartJS()) return;

        // Wait for DOM
        await new Promise(r => setTimeout(r, 300));

        this.renderDistributionChart();
        this.renderRankingChart();
    }

    renderDistributionChart() {
        const ctx = document.getElementById('bfsiChartDistribution');
        if (!ctx) return;

        const members = this.state.teamMembers;
        const buckets = { 'Excellent (90+)': 0, 'Good (75-89)': 0, 'Average (50-74)': 0, 'Needs Improvement (<50)': 0 };

        members.forEach(m => {
            const s = m.latest_overall_score || 0;
            if (s >= 90) buckets['Excellent (90+)']++;
            else if (s >= 75) buckets['Good (75-89)']++;
            else if (s >= 50) buckets['Average (50-74)']++;
            else buckets['Needs Improvement (<50)']++;
        });

        destroyChart('distribution');
        chartInstances.distribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: Object.keys(buckets),
                datasets: [{
                    data: Object.values(buckets),
                    backgroundColor: [CHART_COLORS.success, CHART_COLORS.info, CHART_COLORS.warning, CHART_COLORS.danger],
                    borderWidth: 0,
                    hoverOffset: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 12, usePointStyle: true, pointStyle: 'circle', font: { size: 11, family: 'Inter' } },
                    },
                },
            },
        });
    }

    renderRankingChart() {
        const ctx = document.getElementById('bfsiChartRanking');
        if (!ctx) return;

        const members = this.state.teamMembers.slice(0, 10); // Top 10
        const labels = members.map(m => m.name.split(' ').slice(-1)[0]); // Last name
        const scores = members.map(m => m.latest_overall_score || 0);

        const colors = scores.map(s => {
            if (s >= 75) return CHART_COLORS.success;
            if (s >= 50) return CHART_COLORS.warning;
            return CHART_COLORS.danger;
        });

        const bgColors = scores.map(s => {
            if (s >= 75) return CHART_COLORS.successLight;
            if (s >= 50) return CHART_COLORS.warningLight;
            return CHART_COLORS.dangerLight;
        });

        destroyChart('ranking');
        chartInstances.ranking = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Score',
                    data: scores,
                    backgroundColor: bgColors,
                    borderColor: colors,
                    borderWidth: 2,
                    borderRadius: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        ticks: { font: { size: 10, family: 'Inter' } },
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 10, family: 'Inter' } },
                    },
                },
            },
        });
    }

    /* ━━━ BANKER DETAIL MODAL ━━━ */

    async openBankerDetail(bankerId) {
        this.state.showBankerModal = true;
        this.state.bankerDetail = null;
        this.state.modalTab = 'profile';

        try {
            // Get full banker data
            const [banker] = await this.orm.searchRead(
                'hr.employee',
                [['id', '=', bankerId]],
                ['id', 'name', 'job_id', 'banker_type', 'current_month_rank',
                    'rank_movement', 'latest_overall_score', 'coaching_priority',
                    'coaching_sessions_received', 'active_action_plan_count'],
                { limit: 1 }
            );

            if (!banker) {
                this.state.showBankerModal = false;
                return;
            }

            // Get KPI history
            const kpis = await this.orm.searchRead(
                'bfsi.performance.kpi',
                [['employee_id', '=', bankerId]],
                ['overall_score', 'revenue', 'conversions', 'period_date',
                    'deviation_score', 'coaching_priority'],
                { order: 'period_date desc', limit: 6 }
            );

            // Get coaching sessions (all, no limit)
            let sessions = [];
            try {
                sessions = await this.orm.searchRead(
                    'hr.coaching.session',
                    [['employee_id', '=', bankerId]],
                    ['name', 'session_date', 'session_type', 'state', 'discussion_notes'],
                    { order: 'session_date desc' }
                );
            } catch (_) { }

            // Get action plans (all, no limit)
            let plans = [];
            try {
                plans = await this.orm.searchRead(
                    'bfsi.action.plan',
                    [['employee_id', '=', bankerId]],
                    ['name', 'state', 'progress_percentage', 'create_date', 'action_item_count'],
                    { order: 'create_date desc' }
                );
            } catch (_) { }

            // Build detail object
            const stateLabels = {
                'draft': 'Draft', 'committed': 'Committed',
                'in_progress': 'In Progress', 'completed': 'Completed',
                'cancelled': 'Cancelled',
            };

            this.state.bankerDetail = {
                id: banker.id,
                name: banker.name,
                role: this.formatRole(banker),
                rank: banker.current_month_rank,
                movement: banker.rank_movement,
                score: banker.latest_overall_score || 0,
                priority: banker.coaching_priority,
                sessions_count: banker.coaching_sessions_received || 0,
                plans_count: banker.active_action_plan_count || 0,

                kpi_history: kpis.map(k => ({
                    id: k.id,
                    period: k.period_date || '-',
                    score: k.overall_score || 0,
                    revenue: k.revenue || 0,
                    conversions: k.conversions || 0,
                })),

                sessions: sessions.map(s => ({
                    id: s.id,
                    date: s.session_date || '-',
                    raw_date: s.session_date || '',
                    type: s.session_type || 'General',
                    notes: s.name || s.discussion_notes || '',
                })),

                plans: plans.map(p => ({
                    id: p.id,
                    name: p.name || 'Unnamed Plan',
                    state: p.state || 'draft',
                    state_label: stateLabels[p.state] || p.state || 'Draft',
                    completion: p.progress_percentage || 0,
                    create_date: p.create_date || '',
                    item_count: p.action_item_count || 0,
                })),
            };

            // Reset filters
            this.state.coachingFilter = 'this_month';
            this.state.plansFilter = 'this_month';

            // Render modal charts after data is available
            await new Promise(r => setTimeout(r, 300));
            await this.renderModalCharts();

        } catch (error) {
            console.error('Error loading banker detail:', error);
            this.notification.add('Failed to load banker details', { type: 'danger' });
            this.state.showBankerModal = false;
        }
    }

    closeBankerModal() {
        this.state.showBankerModal = false;
        this.state.bankerDetail = null;
        destroyChart('modalRadar');
        destroyChart('modalTrend');
    }

    async switchModalTab(tab) {
        this.state.modalTab = tab;
        if (tab === 'performance') {
            // Wait for OWL to render the canvas elements
            await new Promise(r => setTimeout(r, 100));
            await this.renderModalCharts();
        }
    }

    openRecord(model, id) {
        this.closeBankerModal();
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: model,
            res_id: id,
            views: [[false, 'form']],
            target: 'current',
        });
    }

    /* ━━━ FILTER HELPERS ━━━ */

    _getDateRange(filterType) {
        const now = new Date();
        let from, to;
        if (filterType === 'this_month') {
            from = new Date(now.getFullYear(), now.getMonth(), 1);
            to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
        } else if (filterType === 'last_month') {
            from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            to = new Date(now.getFullYear(), now.getMonth(), 0);
        }
        const fmt = (d) => d.toISOString().slice(0, 10);
        return { from: fmt(from), to: fmt(to) };
    }

    _filterByDate(items, dateField, filterType, customFrom, customTo) {
        if (filterType === 'this_month' || filterType === 'last_month') {
            const range = this._getDateRange(filterType);
            return items.filter(item => {
                const d = (item[dateField] || '').slice(0, 10);
                return d >= range.from && d <= range.to;
            });
        }
        if (filterType === 'custom' && customFrom && customTo) {
            return items.filter(item => {
                const d = (item[dateField] || '').slice(0, 10);
                return d >= customFrom && d <= customTo;
            });
        }
        return items; // 'all' or custom without dates
    }

    get filteredSessions() {
        const sessions = this.state.bankerDetail?.sessions || [];
        if (this.state.coachingFilter === 'all' || this.state.coachingFilter === 'custom' && (!this.state.coachingDateFrom || !this.state.coachingDateTo)) {
            if (this.state.coachingFilter !== 'custom') return sessions;
            return sessions;
        }
        return this._filterByDate(
            sessions, 'raw_date', this.state.coachingFilter,
            this.state.coachingDateFrom, this.state.coachingDateTo
        );
    }

    get filteredPlans() {
        const plans = this.state.bankerDetail?.plans || [];
        if (this.state.plansFilter === 'all' || this.state.plansFilter === 'custom' && (!this.state.plansDateFrom || !this.state.plansDateTo)) {
            if (this.state.plansFilter !== 'custom') return plans;
            return plans;
        }
        return this._filterByDate(
            plans, 'create_date', this.state.plansFilter,
            this.state.plansDateFrom, this.state.plansDateTo
        );
    }

    filterSessions(filterType) {
        if (filterType === 'all') {
            // Open list view in Odoo
            const empId = this.state.bankerDetail?.id;
            this.closeBankerModal();
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Coaching Sessions',
                res_model: 'hr.coaching.session',
                views: [[false, 'list'], [false, 'form']],
                domain: [['employee_id', '=', empId]],
                context: { group_by: ['session_date:month'] },
                target: 'current',
            });
            return;
        }
        this.state.coachingFilter = filterType;
    }

    filterPlans(filterType) {
        if (filterType === 'all') {
            const empId = this.state.bankerDetail?.id;
            this.closeBankerModal();
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: 'Action Plans',
                res_model: 'bfsi.action.plan',
                views: [[false, 'list'], [false, 'form']],
                domain: [['employee_id', '=', empId]],
                context: { group_by: ['create_date:month'] },
                target: 'current',
            });
            return;
        }
        this.state.plansFilter = filterType;
    }

    onCoachingDateChange(field, ev) {
        if (field === 'from') this.state.coachingDateFrom = ev.target.value;
        else this.state.coachingDateTo = ev.target.value;
    }

    onPlansDateChange(field, ev) {
        if (field === 'from') this.state.plansDateFrom = ev.target.value;
        else this.state.plansDateTo = ev.target.value;
    }

    applyCustomSessionFilter() {
        // Force re-render by toggling filter
        this.state.coachingFilter = '';
        this.state.coachingFilter = 'custom';
    }

    applyCustomPlanFilter() {
        this.state.plansFilter = '';
        this.state.plansFilter = 'custom';
    }

    /* ━━━ MODAL CHARTS ━━━ */

    async renderModalCharts() {
        if (!this.state.bankerDetail) return;
        if (!await loadChartJS()) return;

        await new Promise(r => setTimeout(r, 200));

        this.renderModalRadarChart();
        this.renderModalTrendChart();
    }

    renderModalRadarChart() {
        const ctx = document.getElementById('bfsiModalRadar');
        if (!ctx) return;

        const detail = this.state.bankerDetail;
        const kpiData = detail.kpi_history[0]; // Latest KPI

        // Use available KPI data for categories
        const categories = ['Score', 'Revenue', 'Conversions'];
        const values = kpiData ? [
            Math.min(100, kpiData.score || 0),
            Math.min(100, kpiData.revenue || 0),
            Math.min(100, kpiData.conversions || 0),
        ] : [detail.score, 0, 0];

        destroyChart('modalRadar');
        chartInstances.modalRadar = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: categories,
                datasets: [{
                    label: detail.name,
                    data: values,
                    borderColor: CHART_COLORS.primary,
                    backgroundColor: CHART_COLORS.primaryLight,
                    borderWidth: 2,
                    pointBackgroundColor: CHART_COLORS.primary,
                    pointRadius: 4,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { stepSize: 25, font: { size: 9, family: 'Inter' } },
                        grid: { color: 'rgba(0,0,0,0.06)' },
                        angleLines: { color: 'rgba(0,0,0,0.06)' },
                        pointLabels: { font: { size: 10, family: 'Inter', weight: '600' } },
                    },
                },
                plugins: { legend: { display: false } },
            },
        });
    }

    renderModalTrendChart() {
        const ctx = document.getElementById('bfsiModalTrend');
        if (!ctx) return;

        const history = [...(this.state.bankerDetail.kpi_history || [])].reverse();
        const labels = history.map(k => k.period);
        const scores = history.map(k => k.score);

        destroyChart('modalTrend');
        chartInstances.modalTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Score',
                    data: scores,
                    borderColor: CHART_COLORS.primary,
                    backgroundColor: CHART_COLORS.primaryLight,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: CHART_COLORS.primary,
                    pointHoverRadius: 8,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: 'rgba(0,0,0,0.04)' },
                        ticks: { font: { size: 10, family: 'Inter' } },
                    },
                    x: {
                        grid: { display: false },
                        ticks: { font: { size: 9, family: 'Inter' } },
                    },
                },
            },
        });
    }

    /* ━━━ FILTER / SORT ━━━ */

    get filteredTeam() {
        let team = [...this.state.teamMembers];

        if (this.state.filterPriority !== 'all') {
            team = team.filter(b => b.coaching_priority === this.state.filterPriority);
        }

        team.sort((a, b) => {
            let valA, valB;
            switch (this.state.sortBy) {
                case 'rank':
                    valA = a.current_month_rank || 999;
                    valB = b.current_month_rank || 999;
                    break;
                case 'score':
                    valA = a.latest_overall_score || 0;
                    valB = b.latest_overall_score || 0;
                    break;
                case 'priority':
                    const priorityOrder = { critical: 1, high: 2, medium: 3, low: 4 };
                    valA = priorityOrder[a.coaching_priority] || 5;
                    valB = priorityOrder[b.coaching_priority] || 5;
                    break;
                default:
                    valA = a.current_month_rank || 999;
                    valB = b.current_month_rank || 999;
            }
            return this.state.sortOrder === 'desc' ? valB - valA : valA - valB;
        });

        return team;
    }

    /* ━━━ HELPERS ━━━ */

    getScoreBadgeClass(score) {
        if (score >= 90) return 'badge-success';
        if (score >= 75) return 'badge-primary';
        if (score >= 60) return 'badge-warning';
        return 'badge-danger';
    }

    getPriorityBadgeClass(priority) {
        switch (priority) {
            case 'critical': return 'badge-danger';
            case 'high': return 'badge-warning';
            case 'medium': return 'badge-info';
            case 'low': return 'badge-success';
            default: return 'badge-secondary';
        }
    }

    getRankMovement(movement) {
        if (movement > 0) {
            return { icon: 'fa-arrow-up', class: 'up', text: `+${movement}` };
        } else if (movement < 0) {
            return { icon: 'fa-arrow-down', class: 'down', text: movement.toString() };
        }
        return { icon: 'fa-minus', class: 'flat', text: '-' };
    }

    sortBy(field) {
        if (this.state.sortBy === field) {
            this.state.sortOrder = this.state.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.sortBy = field;
            this.state.sortOrder = 'asc';
        }
    }

    filterByPriority(priority) {
        this.state.filterPriority = priority;
    }

    /* ━━━ ACTIONS ━━━ */

    async startCoachingSession(bankerId) {
        try {
            const result = await this.orm.call(
                'hr.employee',
                'action_start_ai_coaching',
                [bankerId]
            );
            if (result && typeof result === 'object') {
                if (!result.views) {
                    result.views = [[false, 'form']];
                }
                this.action.doAction(result);
            } else {
                this.notification.add('Coaching session started', { type: 'success' });
                await this.refresh();
            }
        } catch (error) {
            console.error('Error starting coaching session:', error);
            this.notification.add('Failed to start coaching session', { type: 'danger' });
        }
    }

    async generateStrategy(bankerId) {
        try {
            const result = await this.orm.call(
                'hr.employee',
                'action_generate_coaching_strategy',
                [bankerId]
            );
            if (result && typeof result === 'object') {
                if (!result.views) {
                    result.views = [[false, 'form']];
                }
                this.action.doAction(result);
            } else {
                this.notification.add('Strategy generated', { type: 'success' });
                await this.refresh();
            }
        } catch (error) {
            console.error('Error generating strategy:', error);
            this.notification.add('Failed to generate coaching strategy', { type: 'danger' });
        }
    }

    viewBankerKpis(bankerId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Performance KPIs',
            res_model: 'bfsi.performance.kpi',
            views: [[false, 'list'], [false, 'form']],
            domain: [['employee_id', '=', bankerId]],
        });
    }

    viewBankerActionPlans(bankerId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Action Plans',
            res_model: 'bfsi.action.plan',
            views: [[false, 'list'], [false, 'form']],
            domain: [['employee_id', '=', bankerId]],
        });
    }

    async refresh() {
        this.state.isLoading = true;
        Object.keys(chartInstances).forEach(destroyChart);
        await this.loadTeamData();
        this.state.isLoading = false;
        await this.renderDashboardCharts();
        this.notification.add('Dashboard refreshed', { type: 'success' });
    }

    filterByCritical() {
        this.state.filterPriority = this.state.filterPriority === 'critical' ? 'all' : 'critical';
    }

    viewAllKPIs() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Performance KPIs',
            res_model: 'bfsi.performance.kpi',
            views: [[false, 'list'], [false, 'form']],
            domain: this.state.branchId ? [['branch_id', '=', this.state.branchId]] : [],
            context: { group_by: ['period_date:month'] },
        });
    }

    viewAllStrategies() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Coaching Strategies',
            res_model: 'bfsi.coaching.strategy',
            views: [[false, 'list'], [false, 'form']],
            domain: [['branch_id', '=', this.state.branchId]],
        });
    }

    viewAllSessions() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Active Plans',
            res_model: 'bfsi.action.plan',
            views: [[false, 'list'], [false, 'form']],
            domain: [['state', 'in', ['committed', 'in_progress']]],
            context: { group_by: ['create_date:month', 'employee_id'] },
        });
    }
}

// Register as action for menu access
registry.category("actions").add("bfsi_manager_dashboard", BfsiManagerDashboard);
