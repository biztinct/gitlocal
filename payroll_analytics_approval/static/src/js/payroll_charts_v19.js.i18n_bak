/** @odoo-module **/
/**
 * Payroll Analytics Dashboard Charts — Odoo 19 compatible
 * Standalone DOM-based approach: detects when the analytics dashboard form
 * is rendered, reads JSON field data from the DOM, and renders Chart.js charts.
 */

import { whenReady } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

let chartInstances = {};
let chartJSLoaded = false;
let lastRecordId = null;

/* ────────────────────── helpers ────────────────────── */

const loadChartJS = () => new Promise((resolve, reject) => {
    if (typeof Chart !== 'undefined') { chartJSLoaded = true; resolve(); return; }
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js';
    s.onload = () => { chartJSLoaded = true; resolve(); };
    s.onerror = () => reject(new Error('Chart.js failed to load'));
    document.head.appendChild(s);
});

const destroyAllCharts = () => {
    Object.values(chartInstances).forEach(c => { try { c.destroy(); } catch (_) { } });
    chartInstances = {};
};

const fmt = (v) => new Intl.NumberFormat().format(Math.round(v));

const parseJSON = (raw) => {
    if (!raw || !raw.trim()) return null;
    try { return JSON.parse(raw); } catch (_) { return null; }
};

/* ───────────────── Chart Rendering ───────────────── */

const COLORS = [
    'rgba(54, 162, 235, 0.8)',
    'rgba(255, 99, 132, 0.8)',
    'rgba(255, 205, 86, 0.8)',
    'rgba(75, 192, 192, 0.8)',
    'rgba(153, 102, 255, 0.8)',
    'rgba(255, 159, 64, 0.8)',
    'rgba(199, 199, 199, 0.8)',
    'rgba(83, 102, 255, 0.8)',
    'rgba(255, 99, 255, 0.8)',
    'rgba(99, 255, 132, 0.8)',
    'rgba(255, 159, 132, 0.8)',
    'rgba(132, 255, 159, 0.8)',
];

const createComponentChart = (ctx, components) => {
    const labels = [], data = [];
    for (const [code, comp] of Object.entries(components)) {
        if (comp && comp.total > 0) {
            labels.push(comp.name || code);
            data.push(comp.total);
        }
    }
    if (!data.length) { showNoData(ctx); return; }
    chartInstances.components = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: COLORS.slice(0, data.length),
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { padding: 15, usePointStyle: true, font: { size: 11 } } },
                tooltip: { callbacks: { label: (c) => `${c.label}: ${fmt(c.parsed)}` } },
            },
            animation: { animateScale: true, animateRotate: true, duration: 800 },
        },
    });
};

const createComparisonChart = (ctx, components, comparison) => {
    const labels = [], currentData = [], previousData = [];
    for (const [code, comp] of Object.entries(components)) {
        if (comp && comp.total > 0) {
            labels.push(comp.name || code);
            currentData.push(comp.total);
            const prev = comparison && comparison.previous_month && comparison.previous_month[code];
            previousData.push(prev ? prev.total || 0 : 0);
        }
    }
    if (!currentData.length) { showNoData(ctx); return; }
    chartInstances.comparison = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Current', data: currentData, backgroundColor: 'rgba(102, 187, 106, 0.8)', borderColor: 'rgba(102, 187, 106, 1)', borderWidth: 2 },
                { label: 'Previous', data: previousData, backgroundColor: 'rgba(149, 165, 166, 0.8)', borderColor: 'rgba(149, 165, 166, 1)', borderWidth: 2 },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, ticks: { callback: (v) => fmt(v) } },
                x: { ticks: { maxRotation: 45 } },
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt(c.parsed.y)}` } },
            },
            animation: { duration: 800 },
        },
    });
};

const createVarianceChart = (ctx, components, comparison) => {
    const labels = [], varData = [], colors = [];
    let hasVariance = false;
    for (const [code, comp] of Object.entries(components)) {
        if (comp && comp.total > 0) {
            labels.push(comp.name || code);
            const v = (comparison && comparison.variance && comparison.variance[code]) || 0;
            varData.push(v);
            if (Math.abs(v) > 0.1) hasVariance = true;
            colors.push(
                v > 5 ? 'rgba(76,175,80,0.8)' :
                    v < -5 ? 'rgba(244,67,54,0.8)' :
                        Math.abs(v) > 0.1 ? 'rgba(255,193,7,0.8)' :
                            'rgba(149,165,166,0.8)'
            );
        }
    }
    if (!varData.length || !hasVariance) {
        const p = ctx.parentElement;
        if (p) p.innerHTML = '<div class="text-center text-muted p-4"><i class="fa fa-info-circle fa-2x mb-2"></i><p>No significant variance</p></div>';
        return;
    }
    chartInstances.variance = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Variance %', data: varData, backgroundColor: colors, borderWidth: 2 }] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: true, ticks: { callback: (v) => v + '%' } },
                x: { ticks: { maxRotation: 45 } },
            },
            plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (c) => 'Variance: ' + c.parsed.y.toFixed(1) + '%' } },
            },
            animation: { duration: 800 },
        },
    });
};

const showNoData = (ctx) => {
    const p = ctx.parentElement;
    if (p) p.innerHTML = '<div class="text-center text-muted p-4"><i class="fa fa-info-circle fa-2x mb-2"></i><p>No data for this chart</p></div>';
};

/* ────── Anomaly Alerts ────── */
const renderAlerts = (alerts) => {
    const container = document.getElementById('anomaly-alerts-container');
    if (!container) return;
    if (!Array.isArray(alerts) || !alerts.length) {
        container.innerHTML = '<div class="alert alert-success"><i class="fa fa-check-circle"></i> No anomalies detected</div>';
        return;
    }
    container.innerHTML = alerts.map(a => {
        const cls = a.severity === 'high' ? 'danger' : a.severity === 'medium' ? 'warning' : 'info';
        const icon = a.severity === 'high' ? 'fa-exclamation-triangle' : 'fa-warning';
        return `<div class="alert alert-${cls}"><i class="fa ${icon}"></i> <strong>${a.component_name || a.component || ''}</strong><br>${a.message || ''}</div>`;
    }).join('');
};

/* ────── Analysis Table ────── */
const renderTable = (components, comparison) => {
    const tbody = document.getElementById('analysis-table-body');
    if (!tbody) return;
    tbody.innerHTML = Object.entries(components).map(([code, comp]) => {
        if (!comp) return '';
        const cur = comp.total || 0;
        const prev = (comparison && comparison.previous_month && comparison.previous_month[code]) ? comparison.previous_month[code].total || 0 : 0;
        const v = (comparison && comparison.variance && comparison.variance[code]) || 0;
        const vClass = v > 0 ? 'text-success' : v < 0 ? 'text-danger' : 'text-muted';
        const badge = Math.abs(v) > 20 ? 'badge-danger' : Math.abs(v) > 10 ? 'badge-warning' : 'badge-success';
        const status = Math.abs(v) > 20 ? 'Alert' : Math.abs(v) > 10 ? 'Warning' : 'Normal';
        return `<tr>
            <td><strong>${comp.name || code}</strong></td>
            <td>${fmt(cur)}</td><td>${fmt(prev)}</td>
            <td>${fmt(comp.average || 0)}</td>
            <td class="${vClass}"><strong>${v.toFixed(1)}%</strong></td>
            <td><span class="badge ${badge}">${status}</span></td>
        </tr>`;
    }).join('');
};

/* ────── Recommendations ────── */
const renderRecommendations = (components, comparison, alerts) => {
    const recList = document.getElementById('recommendations-list');
    const warnList = document.getElementById('warnings-list');
    if (!recList || !warnList) return;

    const recs = [];
    const warns = [];
    if (comparison) {
        if (comparison.trend === 'increasing') recs.push('Overall payroll is trending upward — consider budget implications');
        if (comparison.trend === 'decreasing') recs.push('Overall payroll is trending downward — good cost management');
        if (comparison.variance) {
            for (const [code, v] of Object.entries(comparison.variance)) {
                if (Math.abs(v) > 30) warns.push(`Large variance in ${(components[code] && components[code].name) || code} (${v.toFixed(1)}%)`);
            }
        }
    }
    if (!Array.isArray(alerts)) alerts = [];
    if (!alerts.length) recs.push('No anomalies detected — payroll appears consistent');
    alerts.filter(a => a && a.severity === 'high').forEach(a => warns.push(a.message));
    if (!recs.length) { recs.push('Review all components carefully before approval'); }
    if (!warns.length) { warns.push('No critical issues detected'); }

    recList.innerHTML = recs.map(r => `<li><i class="fa fa-check text-success"></i> ${r}</li>`).join('');
    warnList.innerHTML = warns.map(w => `<li><i class="fa fa-warning text-warning"></i> ${w}</li>`).join('');
};

/* ────────────────── Main Setup ────────────────── */

const setupDashboard = async () => {
    // Only run on the analytics dashboard form
    const dashboard = document.querySelector('.analytics-dashboard');
    if (!dashboard) return;

    // Extract record ID — Odoo 19 uses various URL formats
    let recordId = null;

    // Strategy 1: Hash-based URL (#id=3)
    const hashMatch = window.location.hash.match(/[?&]id=(\d+)/);
    if (hashMatch) recordId = parseInt(hashMatch[1]);

    // Strategy 2: Path-based URL (/odoo/.../3 or /web#id=3)
    if (!recordId) {
        const pathMatch = window.location.pathname.match(/\/(\d+)(?:\/|$)/);
        if (pathMatch) recordId = parseInt(pathMatch[1]);
    }

    // Strategy 3: Hash without ? (#action=...&id=3 or just #id=3)
    if (!recordId) {
        const hashMatch2 = window.location.hash.match(/id=(\d+)/);
        if (hashMatch2) recordId = parseInt(hashMatch2[1]);
    }

    // Strategy 4: Look for .o_form_view data attributes or breadcrumb info
    if (!recordId) {
        const formView = document.querySelector('.o_form_view');
        if (formView) {
            const resId = formView.dataset.resId || formView.getAttribute('data-res-id');
            if (resId) recordId = parseInt(resId);
        }
    }

    // Strategy 5: Extract from action params in session storage
    if (!recordId) {
        try {
            const url = new URL(window.location.href);
            // Odoo 19 may store ID in the URL differently
            for (const [key, val] of url.searchParams) {
                if (key === 'id') { recordId = parseInt(val); break; }
            }
        } catch (_) { }
    }

    // Strategy 6: Fallback — query the model for ready analytics
    if (!recordId) {
        try {
            const ids = await rpc('/web/dataset/call_kw/payroll.analytics/search', {
                model: 'payroll.analytics',
                method: 'search',
                args: [[['state', 'in', ['ready', 'approved']]]],
                kwargs: { limit: 1 },
            });
            if (ids && ids.length) recordId = ids[0];
        } catch (_) { }
    }

    if (!recordId) {
        console.log('PayrollCharts: could not determine record ID');
        return;
    }

    console.log('PayrollCharts: using record ID', recordId);

    // Fetch record data via RPC (invisible fields don't render in Odoo 19 DOM)
    let recordData;
    try {
        const results = await rpc(`/web/dataset/call_kw/payroll.analytics/read`, {
            model: 'payroll.analytics',
            method: 'read',
            args: [[recordId], ['salary_components', 'comparison_data', 'employee_metrics', 'anomaly_alerts']],
            kwargs: {},
        });
        recordData = results && results[0];
    } catch (e) {
        console.error('PayrollCharts: failed to fetch record data', e);
        return;
    }

    if (!recordData) return;

    const components = parseJSON(recordData.salary_components);
    const comparison = parseJSON(recordData.comparison_data);
    const metrics = parseJSON(recordData.employee_metrics);
    const alerts = parseJSON(recordData.anomaly_alerts);

    if (!components || Object.keys(components).length === 0) {
        console.log('PayrollCharts: no salary_components data');
        return;
    }

    // Ensure Chart.js is loaded
    if (!chartJSLoaded) {
        try { await loadChartJS(); } catch (e) {
            console.error('Failed to load Chart.js', e);
            return;
        }
    }

    // Hydrate component names via RPC if possible
    const codes = Object.keys(components).filter(c => {
        const n = components[c] && components[c].name;
        return !n || n.toUpperCase() === c.toUpperCase();
    });
    if (codes.length) {
        try {
            const nameMap = await rpc(`/web/dataset/call_kw/payroll.analytics/get_component_name_map`, {
                model: 'payroll.analytics',
                method: 'get_component_name_map',
                args: [[recordId], codes],
                kwargs: {},
            });
            if (nameMap) {
                for (const [code, name] of Object.entries(nameMap)) {
                    if (components[code]) components[code].name = name || components[code].name;
                }
            }
        } catch (_) { }
    }

    // Destroy old charts
    destroyAllCharts();

    // Render charts
    const ctx1 = document.getElementById('componentsChart');
    const ctx2 = document.getElementById('comparisonChart');
    const ctx3 = document.getElementById('varianceChart');

    if (ctx1) createComponentChart(ctx1, components);
    if (ctx2) createComparisonChart(ctx2, components, comparison || {});
    if (ctx3) createVarianceChart(ctx3, components, comparison || {});

    // Render other sections
    renderAlerts(Array.isArray(alerts) ? alerts : []);
    renderTable(components, comparison || {});
    renderRecommendations(components, comparison || {}, alerts || []);
};

/* ────────────────── Auto-detect dashboard ────────────────── */

whenReady(() => {
    let timer;
    const observer = new MutationObserver(() => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            const dashboard = document.querySelector('.analytics-dashboard');
            if (dashboard && !dashboard.dataset.chartsLoaded) {
                dashboard.dataset.chartsLoaded = '1';
                setupDashboard();
            }
        }, 600);
    });
    observer.observe(document.body, { childList: true, subtree: true });

    // Initial check
    setTimeout(setupDashboard, 1000);
});
