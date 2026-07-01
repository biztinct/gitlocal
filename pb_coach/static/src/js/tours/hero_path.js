/** @odoo-module **/

import { registry } from "@web/core/registry";

// The flagship end-to-end tour. Steps target `data-coach="..."` anchors added
// to the dashboard, the pay-run wizard and the PayAI pill.
registry.category("pb_coach.tours").add("hero_path", {
    name: "Take the tour",
    summary: "The full Payobook journey, ~2 min",
    steps: [
        {
            selector: '[data-coach="dash-hero"]',
            navigate: "pb_dashboard.action_pb_dashboard",
            title: "Welcome to your command centre",
            body: "This is the Payobook dashboard — the pulse of your whole payroll operation in one screen.",
            action: "observe",
            placement: "bottom",
        },
        {
            selector: '[data-coach="dash-kpis"]',
            title: "Your payroll at a glance",
            body: "Headcount, monthly cost, approvals waiting and active formula configs — all live, always current.",
            action: "observe",
        },
        {
            selector: '[data-coach="dash-formula"]',
            title: "Formula-driven payroll",
            body: "Payobook computes pay from Excel-style formula configs — not rigid salary structures. Twelve configs power this Vietnam demo.",
            action: "observe",
        },
        {
            selector: '[data-coach="dash-runpayroll"]',
            title: "Let's run payroll",
            body: "Click Run Payroll to open the guided pay-run wizard.",
            action: "click",
            placement: "bottom",
        },
        {
            selector: '[data-coach="pw-division"]',
            waitFor: '[data-coach="pw-division"]',
            title: "Pick a division",
            body: "Choose which division to pay. The wizard automatically loads that division's formula config and eligible employees.",
            action: "observe",
        },
        {
            selector: '[data-coach="pw-compute"]',
            title: "Compute the run",
            body: "This generates a draft payslip for every eligible employee via the formula engine — gross, allowances, statutory (BHXH/PIT) and net.",
            action: "observe",
        },
        {
            navigate: "pb_hr_payroll_base.action_hr_payslip_run_payroll",
            title: "Review & approve",
            body: "Every pay run lives here. A run moves Draft → Submit → HR review → GM approval → Done — each step gated to the right role, so nothing is paid without sign-off.",
            action: "observe",
        },
        {
            navigate: "pb_hr_payroll_analytics.action_open_hr_analytics_dashboard",
            title: "See the whole picture",
            body: "Workforce Analytics turns every run into live dashboards — cost by division, headcount, overtime and statutory trends.",
            action: "observe",
        },
        {
            selector: '[data-coach="payai-pill"]',
            navigate: "pb_dashboard.action_pb_dashboard",
            title: "Meet PayAI, your copilot",
            body: "Ask “how do I run payroll?” anytime. PayAI answers step-by-step and can even replay any tour for you. That's it — you're ready to explore!",
            action: "observe",
            placement: "left",
        },
    ],
});
