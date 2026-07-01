/** @odoo-module **/

import { registry } from "@web/core/registry";

// Formula Studio deep-dive. Opens the real Studio cockpit (which defaults to
// Cards view with the first formula component selected) and walks its features.
registry.category("pb_coach.tours").add("tour_formula", {
    name: "Explore the formula engine",
    summary: "How pay is really calculated",
    steps: [
        {
            navigate: "pb_formula_studio.action_pb_formula_studio",
            selector: '[data-coach="fs-config"]',
            waitFor: '[data-coach="fs-config"]',
            title: "Welcome to Formula Studio",
            body: "This is where every salary rule lives — a live, visual spreadsheet engine. Switch between your 12 division configs (Retail, IT, Construction…) right here.",
            action: "observe",
            placement: "bottom",
        },
        {
            selector: '[data-coach="fs-components"]',
            title: "Every component, one list",
            body: "Inputs, earnings, deductions and totals. Click any component to open it — the coloured type tag tells you what it is at a glance.",
            action: "observe",
            placement: "right",
        },
        {
            selector: '[data-coach="fs-arrows"]',
            title: "See the dependencies",
            body: "Flip on the arrows to draw live connector lines between components — instantly see what feeds what across the whole config.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-components"]',
            title: "Double-click an arrow to jump",
            body: "With the arrows on, double-click any connector arrow and this list scrolls straight to the component it links — the row pulses so it's easy to spot.",
            action: "observe",
            placement: "right",
        },
        {
            selector: '[data-coach="fs-card"]',
            title: "The component card",
            body: "Each rule shows its column, code, category and a Valid check — so you always know the maths is sound.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-formula"]',
            waitFor: '[data-coach="fs-formula"]',
            timeout: 4000,
            title: "The formula, in plain English",
            body: "No cryptic cell refs — every component reads by its own name, colour-coded by type.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-formula"]',
            title: "Jump from the formula",
            body: "Click any component named inside the formula and the list on the left scrolls right to it — no hunting for what a rule depends on.",
            action: "observe",
            placement: "top",
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
            body: "The calculation flow shows how the result is built, step by step, down to the final output. Click it (or Expand) to go full-screen — then scroll to zoom and drag to pan.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-preview"]',
            title: "Live preview — real numbers",
            body: "Every component computes in real time for a sample employee. Tap the sample name to cycle employees and watch all the values recalculate instantly.",
            action: "observe",
            placement: "left",
        },
        {
            selector: '[data-coach="fs-add"]',
            title: "Add anything",
            body: "Need a new allowance or deduction? The + adds a component; you can even import a whole sheet from Excel with one click.",
            action: "observe",
            placement: "right",
        },
        {
            selector: '[data-coach="fs-editai"]',
            title: "Edit with PayAI",
            body: "Change a formula just by describing it in plain English. Editing is switched off in this shared demo — ask the Payobook team for a private, fully-editable trial.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-views"]',
            title: "Cards, Grid, Test & Settings",
            body: "Switch to a spreadsheet Grid, run Test samples to validate every rule, or open Settings — all from here.",
            action: "observe",
        },
        {
            selector: '[data-coach="fs-payai"]',
            title: "PayAI is always here",
            body: "Ask PayAI to explain any rule or draft a new one. That's Formula Studio — Excel-grade power, zero spreadsheets.",
            action: "observe",
            placement: "left",
        },
    ],
});
