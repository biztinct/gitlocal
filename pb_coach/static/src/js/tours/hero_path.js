/** @odoo-module **/

import { registry } from "@web/core/registry";

// The flagship end-to-end tour. Dashboard intro → a full Formula Studio
// deep-dive (the WOW) → run a pay run → review on the kanban → PayAI.
// (The stand-alone "Explore the formula engine" tour still exists separately.)
registry.category("pb_coach.tours").add("hero_path", {
    name: "Take the tour",
    summary: "The full Payobook journey",
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
            body: "Payobook computes pay from Excel-style formula configs — not rigid salary structures. Let's look under the hood.",
            action: "observe",
        },

        // ---------- Formula Studio deep-dive ----------
        {
            navigate: "pb_formula_studio.action_pb_formula_studio",
            selector: '[data-coach="fs-config"]',
            waitFor: '[data-coach="fs-config"]',
            title: "Welcome to Formula Studio",
            body: "A live, visual spreadsheet engine. Switch between your 12 division configs (Retail, IT, Construction…) right here.",
            action: "observe",
            placement: "bottom",
        },
        {
            selector: '[data-coach="fs-components"]',
            title: "Every component, one list",
            body: "Inputs, earnings, deductions and totals. Click any to open it — the coloured tag shows its type. Toggle the arrows to see live dependency lines.",
            action: "observe",
            placement: "right",
        },
        {
            selector: '[data-coach="fs-formula"]',
            waitFor: '[data-coach="fs-formula"]',
            timeout: 4000,
            title: "The formula, in plain English",
            body: "No cryptic cell refs — components read by name, colour-coded by type. Click any chip to jump straight to that component.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-namesletters"]',
            waitFor: '[data-coach="fs-namesletters"]',
            timeout: 4000,
            title: "Names or Letters",
            body: "Prefer spreadsheet style? Flip to Letters (A, B, C…) and back to friendly Names — same formula, your choice.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-deps"]',
            title: "Full traceability",
            body: "“Depends on” and “Used by” map exactly how this number connects to the rest of payroll — nothing hidden.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-flow"]',
            waitFor: '[data-coach="fs-flow"]',
            timeout: 4000,
            title: "Watch it calculate",
            body: "The calculation flow shows how the result is built, step by step, down to the final output. Click it (or Expand) to go full-screen — scroll to zoom, drag to pan.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-preview"]',
            title: "Live preview — real numbers",
            body: "Every component computes in real time for a sample employee. Tap the sample name to cycle employees and watch the values recalculate instantly.",
            action: "observe",
            placement: "left",
        },
        {
            selector: '[data-coach="fs-editai"]',
            title: "Edit with PayAI",
            body: "Change a formula just by describing it in plain English. Editing is off in this shared demo — ask the Payobook team for a private, fully-editable trial.",
            action: "observe",
        },

        // ---------- Run a pay run ----------
        {
            navigate: "pb_payrun_wizard.action_pb_payrun_wizard",
            selector: '[data-coach="pw-division"]',
            waitFor: '[data-coach="pw-division"]',
            title: "Now let's run payroll",
            body: "Pick a division. The wizard automatically loads that division's formula config and eligible employees.",
            action: "observe",
        },
        {
            selector: '[data-coach="pw-compute"]',
            title: "Compute the run",
            body: "This generates a draft payslip for every eligible employee via the formula engine — gross, allowances, statutory (BHXH/PIT) and net.",
            action: "observe",
        },
        {
            navigate: "pb_payruns.action_pb_payruns_kanban",
            title: "Review & approve",
            body: "Every pay run lives on this board. A run moves Draft → HR review → GM approval → Done across the columns — each step gated to the right role, so nothing is paid without sign-off.",
            action: "observe",
        },

        // ---------- PayAI ----------
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
