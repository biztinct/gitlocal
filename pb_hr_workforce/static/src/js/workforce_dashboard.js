/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
/**
 * Workforce Dashboard Charts — Odoo 19 compatible
 * Polls for the dashboard form, reads chart data via RPC, renders Chart.js charts.
 */

import { whenReady } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { loadBundle } from "@web/core/assets";

let chartInstances = {};
let chartJSLoaded = false;
let lastDashId = null;

/* ──────────── Helpers ──────────── */

const destroyAllCharts = () => {
    Object.values(chartInstances).forEach(c => {
        try { c.destroy(); } catch (_) { }
    });
    chartInstances = {};
};

const parseJSON = (raw) => {
    if (!raw) return {};
    try { return JSON.parse(raw); } catch (_) { return {}; }
};

const COLORS = {
    primary: '#3282b8',
    primaryLight: 'rgba(50, 130, 184, 0.15)',
    success: '#2e7d32',
    successLight: 'rgba(46, 125, 50, 0.15)',
    warning: '#e65100',
    warningLight: 'rgba(230, 81, 0, 0.15)',
    danger: '#c62828',
    dangerLight: 'rgba(198, 40, 40, 0.15)',
    palette: [
        '#3282b8', '#2e7d32', '#e65100', '#c62828',
        '#6a1b9a', '#00838f', '#f57f17', '#1565c0',
        '#4e342e', '#37474f',
    ],
};

/* ──────────── Chart Creators ──────────── */

const createAttendanceChart = (ctx, data) => {
    const labels = Object.keys(data);
    const values = Object.values(data);
    if (chartInstances.attendance) chartInstances.attendance.destroy();
    chartInstances.attendance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Check-ins',
                data: values,
                backgroundColor: labels.map((_, i) =>
                    i < 5 ? COLORS.primaryLight : COLORS.warningLight),
                borderColor: labels.map((_, i) =>
                    i < 5 ? COLORS.primary : COLORS.warning),
                borderWidth: 2,
                borderRadius: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.05)' },
                    ticks: { stepSize: 1 },
                },
                x: {
                    grid: { display: false },
                },
            },
        },
    });
};

const createHoursTrendChart = (ctx, data) => {
    const labels = data.map(d => d.week);
    const values = data.map(d => d.hours);
    if (chartInstances.hoursTrend) chartInstances.hoursTrend.destroy();
    chartInstances.hoursTrend = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: _t("Total Hours"),
                data: values,
                borderColor: COLORS.primary,
                backgroundColor: COLORS.primaryLight,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointBackgroundColor: COLORS.primary,
                pointHoverRadius: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0,0,0,0.05)' },
                },
                x: { grid: { display: false } },
            },
        },
    });
};

const createOTDeptChart = (ctx, data) => {
    const labels = Object.keys(data);
    const values = Object.values(data);
    if (chartInstances.otDept) chartInstances.otDept.destroy();
    chartInstances.otDept = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: _t("OT Hours"),
                data: values,
                backgroundColor: COLORS.palette.slice(0, labels.length).map(c => c + '33'),
                borderColor: COLORS.palette.slice(0, labels.length),
                borderWidth: 2,
                borderRadius: 8,
            }],
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
                y: { grid: { display: false } },
            },
        },
    });
};

const createLeavesChart = (ctx, data) => {
    const labels = Object.keys(data);
    const values = Object.values(data);
    if (chartInstances.leaves) chartInstances.leaves.destroy();

    if (!labels.length) {
        // Empty state
        ctx.parentElement.innerHTML += '<div style="text-align:center;color:#9ca3af;padding:40px;">No leave data for this period</div>';
        return;
    }

    chartInstances.leaves = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: COLORS.palette.slice(0, labels.length),
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
                    labels: { padding: 16, usePointStyle: true, pointStyle: 'circle' },
                },
            },
        },
    });
};

/* ──────────── Main Setup ──────────── */

// Chart.js ships with Odoo in the LAZY `web.chartjs_lib` bundle. Injecting a
// jsDelivr <script> instead sent every dashboard visit to a third party, broke
// on any offline/air-gapped install, and silently pinned a version we do not
// control. loadBundle serves it from this server.
const loadChartJS = async () => {
    if (chartJSLoaded || (window.Chart && window.Chart.version)) {
        chartJSLoaded = true;
        return true;
    }
    try {
        await loadBundle("web.chartjs_lib");
        chartJSLoaded = !!window.Chart;
        return chartJSLoaded;
    } catch (e) {
        console.error('WorkforceDash: failed to load Chart.js', e);
        return false;
    }
};

const setupDashboard = async () => {
    const dash = document.querySelector('.workforce-dashboard');
    if (!dash) return;

    // Extract record ID from URL
    const hashMatch = window.location.hash.match(/id=(\d+)/);
    const pathMatch = window.location.pathname.match(/\/(\d+)(?:\/|$)/);
    const recordId = hashMatch ? parseInt(hashMatch[1]) : (pathMatch ? parseInt(pathMatch[1]) : null);

    if (!recordId || recordId === lastDashId) return;
    lastDashId = recordId;

    console.log('WorkforceDash: rendering charts for record', recordId);

    // Fetch chart data via RPC
    let chartData = {};
    try {
        const result = await rpc(`/web/dataset/call_kw/hr.workforce.dashboard/read`, {
            model: 'hr.workforce.dashboard',
            method: 'read',
            args: [[recordId], ['chart_data']],
            kwargs: {},
        });
        if (result && result[0]) {
            chartData = parseJSON(result[0].chart_data);
        }
    } catch (e) {
        console.error('WorkforceDash: RPC failed', e);
        return;
    }

    // Load Chart.js
    if (!await loadChartJS()) return;

    // Wait a tick for DOM to be ready
    await new Promise(r => setTimeout(r, 200));

    // Render charts
    const ctx1 = document.getElementById('wfChartAttendance');
    const ctx2 = document.getElementById('wfChartHoursTrend');
    const ctx3 = document.getElementById('wfChartOTDept');
    const ctx4 = document.getElementById('wfChartLeaves');

    if (ctx1 && chartData.attendance_by_day) {
        createAttendanceChart(ctx1, chartData.attendance_by_day);
    }
    if (ctx2 && chartData.hours_trend) {
        createHoursTrendChart(ctx2, chartData.hours_trend);
    }
    if (ctx3 && chartData.ot_by_department) {
        createOTDeptChart(ctx3, chartData.ot_by_department);
    }
    if (ctx4 && chartData.leave_by_type) {
        createLeavesChart(ctx4, chartData.leave_by_type);
    }
};

/* ──────────── Poll for Dashboard ──────────── */

whenReady(() => {
    const observer = new MutationObserver(() => {
        requestAnimationFrame(setupDashboard);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    // Initial check
    setTimeout(setupDashboard, 1000);
});
