/** @odoo-module **/

import { registry } from "@web/core/registry";

// Pay-runs & payslips mini-tour.
registry.category("pb_coach.tours").add("tour_payslips", {
    name: "Pay runs & payslips",
    summary: "Browse runs and approvals",
    steps: [
        {
            navigate: "pb_payruns.action_pb_payruns_kanban",
            title: "Every pay run in one place",
            body: "A visual board of every run — June is live in Draft, earlier months are Done. Each run holds one payslip per employee for that period and cycle.",
            action: "observe",
        },
        {
            title: "The approval flow",
            body: "Runs move across the columns Draft → HR review → GM approval → Done. Only the right role can advance each step — that's the built-in control.",
            action: "observe",
        },
        {
            selector: '[data-coach="payai-pill"]',
            title: "Payslips are formula-driven",
            body: "Open any payslip to see the components the formula engine produced. Ask PayAI to explain any line.",
            action: "observe",
            placement: "left",
        },
    ],
});
