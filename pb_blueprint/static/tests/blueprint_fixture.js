/** @odoo-module **/

import { onRpc } from "@web/../tests/web_test_helpers";

/**
 * A mocked `pb.blueprint.studio`, so a step can be MOUNTED in a test.
 *
 * B2, B3, B4 and B5 each deferred this, and each deferred it for the same
 * honest reason: the pure layer — every sentence the steps say — is covered by
 * a hundred and nine tests that need no server, and one fixture is worth
 * building once for several surfaces rather than four times for one. This is
 * that fixture, and B6 is the last chance to build it inside this programme.
 *
 * What it is: `onRpc(model, method, handler)` intercepts the call_kw route the
 * ORM service uses, so a component that does
 * `orm.call("pb.blueprint.studio", "bp_finish_data", [7])` gets the payload
 * named here and never knows the difference. The AbstractModel does not have to
 * exist in the mock server's own data — the route match is on the pair of
 * strings.
 *
 * What it is NOT: a second implementation of the server. Every payload below is
 * the SHAPE the real methods return, kept deliberately small, and nothing in a
 * mounted test may assert a NUMBER that only the server could have worked out.
 * The arithmetic is proven in Python, against the real engine; what is proven
 * here is that the component draws what it is given, and that a person can
 * press what the screen appears to offer.
 */

/** The Finish step's payload, with everything green unless you say otherwise. */
export function finishData(over = {}) {
    return {
        ok: true,
        revision: 4,
        state: "draft",
        finished: false,
        editable: true,
        has_payslips: false,
        counts: { components: 111, formulas: 43, inputs: 61, constants: 7,
                  samples: 5 },
        identity: {
            name: "Vietnam · Monthly payroll",
            code: "VIETNAM_MONTHLY_PAYROLL",
            company: "Payobook Vietnam JSC",
            country: "Vietnam",
            cycle: "Regular payroll",
            effective_from: "2026-10-01",
            starter: "Vietnam · Complete",
            situations: ["Local employees", "Joiners & leavers"],
            calendar: {
                cutoff_day: 20,
                payday_rule: "last_working",
                payday_rule_label: "The last working day of the month",
                payday_day: 25,
                late_inputs: "next_cycle",
                late_label: "It waits for the next pay run",
            },
            payment: { currency: "VND", bank_id_type: "domestic",
                       bank_label: "Domestic account number" },
            pack: { id: 3, name: "Vietnam Statutory Parameters 2026",
                    version: "2026.1", effective_date: "2026-01-01",
                    authority: "", state: "published", item_count: 12 },
            pack_aligned: true,
            pack_differ: 0,
            finished_by: "",
            finished_at: "",
        },
        decisions: [],
        decisions_total: 0,
        checks: { ok: true, hash: "abc", tests_hash: "abc", ever_run: true,
                  stale: false, passed: 11, failed: 0, pending: 0, not_run: 0,
                  checks: 11, run_at: "2026-09-10 09:00:00",
                  run_by: "Mai", stored: true },
        optional: [
            { task: "mapping", label: "Source mapping", status: "configured",
              mapped: 12, total: 52 },
            { task: "payslip", label: "Payslip layout", status: "skipped",
              mapped: 0, total: 111 },
            { task: "approvals", label: "Approvals", status: "info",
              mapped: 0, total: 0 },
        ],
        gate: { ok: true, reasons: [] },
        ...over,
    };
}

/** One open decision, of whichever kind the test is about. */
export function decision(over = {}) {
    return {
        key: "component-42-insurance",
        kind: "component",
        title: "Other company benefits",
        code: "OTHERBEN",
        text: "Choose the insurance treatment",
        step: "rules",
        tab: "components",
        rule_id: 42,
        task: "",
        action: "Open this component",
        ...over,
    };
}

/** One refusal, as the gate sends it. */
export function reason(over = {}) {
    return {
        code: "stale",
        text: "Something changed since the checks were last run, so what they "
            + "proved is no longer what this configuration says. Run them again.",
        step: "test",
        tab: "",
        action: "Run the checks",
        ...over,
    };
}

/** The Components tab's payload — five groups, however many rows you want. */
export function componentsData(over = {}) {
    const rows = over.rows || [
        componentRow({ id: 11, code: "SALARYPAID", name: "Basic salary for the "
                       + "days worked", value: 30000000 }),
        componentRow({ id: 12, code: "PHONEALLOW", name: "Phone allowance",
                       value: 500000, source: "manual",
                       summary: "Written as Excel · =ROUND(750000,0)" }),
        componentRow({ id: 13, code: "OTHERBEN", name: "Other company benefits",
                       value: 0, health: "review",
                       health_text: "Choose the insurance treatment",
                       review: [{ code: "insurance",
                                  text: "Choose the insurance treatment" }] }),
    ];
    delete over.rows;
    return {
        ok: true,
        groups: { earning: rows, deduction: [], benefit: [], helper: [],
                  total: [] },
        removed: [],
        counts: { included: rows.length, removed: 0 },
        sample_values: {},
        sample_id: 5,
        revision: 4,
        currency: "VND",
        ...over,
    };
}

/** One row of it. */
export function componentRow(over = {}) {
    return {
        id: 11,
        code: "SALARYPAID",
        name: "Basic salary",
        column_type: "formula",
        letter: "AR",
        group: "earning",
        source: "generated",
        summary: "Contract salary · prorated by paid working days · Taxable",
        health: "ok",
        health_text: "Ready",
        review: [],
        value: 30000000,
        locked: false,
        template_key: "",
        on_payslip: true,
        ...over,
    };
}

/**
 * Register the mock. Call it inside a test, BEFORE mounting.
 *
 * `calls` is filled with `[method, args]` for every call the component makes,
 * so a test can prove that pressing a button reached the server at all — which
 * is the half of a gate a pure test can never see.
 */
export function mockStudio(handlers = {}) {
    const calls = [];
    const defaults = {
        bp_finish_data: () => finishData(),
        bp_finish: () => ({ ok: true, config_id: 7, already: false }),
        bp_reopen: () => ({ ok: true, config_id: 7, already: false }),
        bp_components: () => componentsData(),
        bp_component_get: () => ({ ok: false, reason: "not part of this test" }),
        bp_evidence: () => finishData().checks,
    };
    const all = { ...defaults, ...handlers };
    for (const [method, handler] of Object.entries(all)) {
        onRpc("pb.blueprint.studio", method, ({ args }) => {
            calls.push([method, args]);
            return handler({ args });
        });
    }
    return calls;
}
