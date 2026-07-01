/** @odoo-module **/

import { registry } from "@web/core/registry";

// Formula-engine mini-tour (read-only explorer).
registry.category("pb_coach.tours").add("tour_formula", {
    name: "Explore the formula engine",
    summary: "See how pay is calculated",
    steps: [
        {
            navigate: "pb_hr_payroll_formula.action_formula_config",
            title: "Excel-style formula configs",
            body: "This is where payroll logic lives. Each config is a grid of components — inputs, constants and formulas — just like a spreadsheet.",
            action: "observe",
        },
        {
            title: "Twelve configs, one per division & cycle",
            body: "The demo ships six divisions × two cycles (mid & end). Each column is a salary component; formulas reference each other by code (BASIC, GROSS, PIT…).",
            action: "observe",
        },
        {
            selector: '[data-coach="payai-pill"]',
            title: "Ask PayAI to explain a formula",
            body: "Try “what is a formula config?” — PayAI breaks any component down in plain language.",
            action: "observe",
            placement: "left",
        },
    ],
});
