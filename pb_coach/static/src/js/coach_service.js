/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

/**
 * pb_coach service — the tour-flow state machine.
 *
 * Holds a single shared reactive state that the (globally mounted) CoachOverlay
 * observes and renders. Anyone — a cockpit button, the AI copilot, the welcome
 * modal — can drive the tour by calling `useService("pb_coach").start(id)`.
 *
 * Tours live in the `pb_coach.tours` registry category:
 *   { name, steps: [ { selector, title, body, action, placement, ... } ] }
 */
export const coachService = {
    dependencies: ["action"],
    start(env, { action }) {
        const state = reactive({
            active: false,      // a tour is running
            tourId: null,
            name: "",
            steps: [],
            index: 0,
            mode: "interactive", // "interactive" | "autoplay"
            welcome: false,      // first-run welcome modal open
        });

        const tours = registry.category("pb_coach.tours");

        function list() {
            return tours.getEntries().map(([id, t]) => ({ id, name: t.name, summary: t.summary || "" }));
        }

        function start(tourId, opts = {}) {
            const tour = tours.get(tourId, null);
            if (!tour || !(tour.steps || []).length) {
                console.warn("[pb_coach] unknown/empty tour:", tourId);
                return false;
            }
            state.welcome = false;
            state.tourId = tourId;
            state.name = tour.name || "";
            state.steps = tour.steps;
            state.index = 0;
            state.mode = opts.mode || "interactive";
            state.active = true;
            return true;
        }

        function stop() {
            state.active = false;
            state.tourId = null;
            state.steps = [];
            state.index = 0;
        }

        function next() {
            if (state.index < state.steps.length - 1) {
                state.index += 1;
            } else {
                stop();
            }
        }
        function back() { if (state.index > 0) state.index -= 1; }
        function goTo(i) { if (i >= 0 && i < state.steps.length) state.index = i; }
        function setMode(m) { state.mode = m === "autoplay" ? "autoplay" : "interactive"; }
        function isLast() { return state.index >= state.steps.length - 1; }
        function current() { return state.steps[state.index] || null; }

        function openWelcome() { state.welcome = true; }
        function closeWelcome() { state.welcome = false; }

        // Map the currently-displayed cockpit to its most relevant tour, so the
        // launcher can offer "Tour this screen".
        function screenTourId() {
            let a = null;
            try { a = action.currentController && action.currentController.action; } catch (e) { /* */ }
            if (!a) return null;
            const tag = a.tag || "";
            const xid = a.xml_id || "";
            const model = a.res_model || "";
            if (tag === "pb_payrun_wizard") return "tour_payrun";
            if (tag === "pb_dashboard") return "hero_path";
            if (tag.includes("formula") || xid.includes("formula")) return "tour_formula";
            if (model === "hr.payslip.run" || model === "hr.payslip" || xid.includes("payslip_run")) return "tour_payslips";
            return null;
        }

        async function navigate(ref) {
            if (!ref) return;
            try {
                await action.doAction(ref, { clearBreadcrumbs: true });
            } catch (e) {
                console.warn("[pb_coach] navigate failed:", ref, e);
            }
        }

        return {
            state, tours, action,
            list, start, stop, next, back, goTo, setMode, isLast, current,
            openWelcome, closeWelcome, navigate, screenTourId,
        };
    },
};

registry.category("services").add("pb_coach", coachService);
