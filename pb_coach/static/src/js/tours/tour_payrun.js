/** @odoo-module **/

import { registry } from "@web/core/registry";

// Focused, hands-on pay-run tour. Jumps straight to the wizard.
registry.category("pb_coach.tours").add("tour_payrun", {
    name: "Run a pay run",
    summary: "Generate payslips for a division",
    steps: [
        {
            navigate: "pb_payrun_wizard.action_pb_payrun_wizard",
            selector: '[data-coach="pw-division"]',
            title: "Step 1 — choose a division",
            body: "Select the division to pay. Each division has its own formula config (mid-cycle and end-cycle).",
            action: "observe",
        },
        {
            selector: '[data-coach="pw-compute"]',
            title: "Step 2 — compute",
            body: "Generate the draft payslips for everyone in that division. The formula engine does the maths in seconds.",
            action: "observe",
        },
        {
            selector: '[data-coach="payai-pill"]',
            title: "Next — review & approve",
            body: "After computing, open the run to review payslips and submit for HR then GM approval. Ask PayAI if you get stuck.",
            action: "observe",
            placement: "left",
        },
    ],
});
