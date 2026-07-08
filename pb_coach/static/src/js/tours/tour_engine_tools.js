/** @odoo-module **/

import { registry } from "@web/core/registry";

// Import Confidence + Mid/End Mapping walkthroughs. These features live inside
// backend wizards (the multi-sheet Excel importer and the cycle-mapping wizard)
// which can't be opened cold from a tour, so the steps spotlight their anchors
// when that wizard is on screen and fall back to a centered explainer card
// otherwise — the coach never dead-ends on a missing target.

registry.category("pb_coach.tours").add("tour_import", {
    name: "Import an Excel sheet with confidence",
    summary: "Preview, score and fix before anything commits",
    steps: [
        {
            title: "Import Confidence",
            body: "When you import an Excel workbook of salary rules, Payobook doesn't just trust it — it converts every formula, then shows you exactly how clean the result is before a single component is saved. Open a config's importer (the + in Formula Studio) and land on the Resolution Preview page to follow along.",
            action: "observe",
        },
        {
            selector: '[data-coach="imp-confidence"]',
            waitFor: '[data-coach="imp-confidence"]',
            timeout: 3000,
            title: "A confidence score, not a leap of faith",
            body: "Every import gets a percentage score from how cleanly its formulas resolved, how many references stayed intact, and how sane the sample numbers look. Rows shown in red reference something that couldn't be mapped and quietly became 0 — the exact trap this catches.",
            action: "observe",
            placement: "bottom",
        },
        {
            selector: '[data-coach="imp-actions"]',
            waitFor: '[data-coach="imp-actions"]',
            timeout: 3000,
            title: "Fix it before you commit — or ask AI",
            body: "Pick a Fix on any broken row (map it to the right component, or point it at a reference) and hit Apply Fixes — the score climbs as you go. Or tap AI review to have PayAI rank what's most suspicious and why. Nothing is written until you finish; abandon the preview and your config is untouched.",
            action: "observe",
        },
    ],
});

registry.category("pb_coach.tours").add("tour_mapping", {
    name: "Map mid-cycle pay to end-cycle",
    summary: "Auto-suggest component matches across two configs",
    steps: [
        {
            title: "Mid → End cycle mapping",
            body: "Run payroll twice a month? Components in your mid-cycle config need to line up with the end-cycle one. Instead of matching dozens of rules by hand, Payobook proposes the pairings for you. Open the Mid/End mapping wizard and pick both configs to follow along.",
            action: "observe",
        },
        {
            selector: '[data-coach="map-intro"]',
            waitFor: '[data-coach="map-intro"]',
            timeout: 3000,
            title: "Matched by code, then by name",
            body: "Auto-suggest first pairs components with the same code (a perfect 1.0 match), then falls back to name similarity for the rest — and skips anything you've already mapped. Every suggestion shows its confidence and the reason it was matched.",
            action: "observe",
            placement: "bottom",
        },
        {
            selector: '[data-coach="map-actions"]',
            waitFor: '[data-coach="map-actions"]',
            timeout: 3000,
            title: "Suggest, review, accept all",
            body: "Click Suggest Mappings to generate the proposals, review each one, then Accept All to create every mapping at 90%+ confidence in a single click — or accept and reject them individually. You stay in control; the machine just does the tedious first pass.",
            action: "observe",
        },
    ],
});
