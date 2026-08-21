/** @odoo-module **/
/**
 * The Rule Composer — Integrations Cycle 8, WP-3.
 *
 * Everything asserted here is a rule whose failure is INVISIBLE on a
 * screenshot: a suggestion that quietly replaced a key the user typed, a value
 * that travelled with a unary operator, a stale preview overwriting a newer
 * one, a sentence assembled from fragments that reads perfectly in English and
 * can never be translated. A screenshot pass finds none of them.
 *
 * Most of it is PURE — the composer's kernel is exported for exactly that
 * reason. Two cases mount, because "no save affordance" is a claim about the
 * DOM and cannot be made about a getter.
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
// `mountWithCleanup` starts the REAL service stack, and on a database with mail
// installed that stack reaches for `discuss.channel` before this component ever
// renders. A test-bundle-only import (W150 rule 1); nothing in the addon knows
// mail exists.
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import {
    DEFAULT_UNARY_OPS,
    PreviewPump,
    RuleComposer,
    blankSpec,
    emitSpec,
    keyAfterRename,
    railSentence,
    readOnlyReason,
    suggestOutputKey,
    toFormula,
    toSteps,
} from "@pb_integrations/js/rule_composer";

describe.current.tags("desktop");
defineMailModels();

// ------------------------------------------------------------------ helpers

/** A manual clock, so the debounce is tested without waiting 260 ms for it. */
function manualClock() {
    const queued = new Map();
    let next = 1;
    return {
        setTimeout: (fn) => { const id = next++; queued.set(id, fn); return id; },
        clearTimeout: (id) => { queued.delete(id); },
        /**
         * Fire everything currently queued, in the order it was queued — and
         * deliberately WITHOUT awaiting them. The pump's callback awaits its
         * own RPC, so awaiting it here would hang on the very case this file
         * exists to test: a request that has not answered yet.
         */
        tick() {
            const fns = [...queued.values()];
            queued.clear();
            for (const fn of fns) { fn(); }
        },
        get pending() { return queued.size; },
    };
}

function payload(over = {}) {
    return {
        ok: true, can_edit: true, is_admin: false,
        connector: { id: 7, name: "Test system" },
        feeds: [{ data_type: "attendance", label: "Attendance", rows: 3,
                  synced: true, fields_known: true }],
        fields: {
            attendance: [
                { path: "totalWorkedHours", label: "Total worked hours",
                  sample: "28800", type: "string", provenance: "store",
                  feed_type: "attendance" },
            ],
        },
        nested_tables: [], samples: {}, synthetic: [], rule: null,
        recipes: [],
        vocabulary: {
            operators: [
                { op: "is", label: "is", unary: false },
                { op: "present", label: "is present", unary: true },
            ],
            units: [{ unit: "number", label: "a number" }],
            rule_types: [{ kind: "sum", label: "Sum Field Across Records" }],
            joins: [{ join: "all", label: "all of these" }],
        },
        functions: [{ name: "HOURS", help: "H:MM text as hours" }],
        ai: { llm: false },
        ...over,
    };
}

// ================================================ T1 — the output-key promise
test("the output key is suggested from the name, and never overwrites a typed one", () => {
    // Capitals and digits only: an underscore or a substring collision makes
    // the formula converter rewrite the shorter code inside the longer and work
    // out 0, which is why the server REFUSES those shapes rather than warning.
    expect(suggestOutputKey("Overtime 150% — hours")).toBe("OVERTIME150HOURS");
    expect(suggestOutputKey("worked_hours")).toBe("WORKEDHOURS");
    expect(suggestOutputKey("dependants (count)")).toBe("DEPENDANTSCOUNT");
    expect(suggestOutputKey("")).toBe("");
    // Capped, so the key stays readable inside a formula.
    expect(suggestOutputKey("a".repeat(40)).length).toBe(20);

    // Untouched: the suggestion follows the name.
    expect(keyAfterRename("Overtime 150", "OLD", false)).toBe("OVERTIME150");
    // Touched: it does NOT. This is the whole assertion — a convenience that
    // corrects the user is not a convenience.
    expect(keyAfterRename("Overtime 150", "OTHRS150", true)).toBe("OTHRS150");
    expect(keyAfterRename("anything at all", "", true)).toBe("");

    // The server stopped upper-casing the key before validating it, so a
    // lowercase one is now REFUSED with the correct spelling in the message.
    // The suggestion is therefore never lowercase in the first place…
    expect(suggestOutputKey("othrs150")).toBe("OTHRS150");
    // …and `emitSpec` passes a hand-typed key through UNCHANGED rather than
    // quietly correcting it. Papering over a refusal on the client is how a
    // rule ends up being enforced by a coercion nobody is told about.
    expect(emitSpec({ ...blankSpec(), output_key: "c8lower" }).output_key)
        .toBe("c8lower");
});

// ============================================ T2 — the lane switch loses nothing
test("guided to formula and back keeps the value steps", () => {
    const draft = {
        ...blankSpec(),
        builder_mode: "guided",
        value_steps: [
            { field: "totalWorkedHours", contains: "seconds" },
            { field: "paidLeaveHours", contains: "hmm" },
        ],
    };

    const out = toFormula(draft);
    // Out of the draft — a half-built step under a formula makes the formula
    // unsaveable, because the save validator refuses a step with no field.
    expect(out.draft.builder_mode).toBe("excel");
    expect(out.draft.value_steps).toEqual([]);
    // …and held beside it.
    expect(out.stash.length).toBe(2);
    expect(out.stash[1].contains).toBe("hmm");

    // The formula lane does not post them either.
    const formulaSpec = emitSpec({ ...out.draft, excel_formula: "[a]/3600" });
    expect(formulaSpec.value_steps).toEqual([]);
    expect(formulaSpec.excel_formula).toBe("[a]/3600");

    const back = toSteps(out.draft, out.stash);
    expect(back.builder_mode).toBe("guided");
    expect(back.value_steps.length).toBe(2);
    expect(back.value_steps[0].field).toBe("totalWorkedHours");
    expect(back.value_steps[1].contains).toBe("hmm");

    // The stash is a copy, not the same rows: mutating what came back must not
    // reach into the stash and change what a second switch would restore.
    back.value_steps[0].field = "somethingElse";
    expect(out.stash[0].field).toBe("totalWorkedHours");
});

// ================================================ T3 — a unary op posts no value
test("a unary operator sends no value, and count sends no steps", () => {
    const spec = emitSpec({
        ...blankSpec(),
        rule_type: "sum",
        source_data_type: "attendance",
        filter_conditions: {
            join: "all",
            rows: [
                // A value LEFT BEHIND by a previous operator. It must not travel.
                { field: "PitNumber", op: "present", value: "150%" },
                { field: "OT_Type", op: "is", value: "150%" },
            ],
        },
        value_steps: [{ field: "Actual_Pay_Hour", contains: "number" }],
    });

    expect(spec.filter_conditions.rows[0].value).toBe(undefined);
    expect("value" in spec.filter_conditions.rows[0]).toBe(false);
    expect(spec.filter_conditions.rows[1].value).toBe("150%");
    expect(spec.value_steps.length).toBe(1);

    // The set is the payload's, not a hardcode: a tenth operator arriving on
    // the server needs no change in the client.
    const custom = emitSpec(
        { ...blankSpec(), filter_conditions: { join: "all",
            rows: [{ field: "f", op: "is", value: "v" }] } },
        new Set(["is"]));
    expect("value" in custom.filter_conditions.rows[0]).toBe(false);
    expect(DEFAULT_UNARY_OPS.has("blank")).toBe(true);

    // `count` has no per-record value at all, and a half-filled step stashed
    // under one would make the rule unsaveable with no visible cause.
    const counted = emitSpec({
        ...blankSpec(), rule_type: "count",
        value_steps: [{ field: "", contains: "number" }],
    });
    expect(counted.value_steps).toEqual([]);
});

// ======================================== T4 — the debounce and the supersede
test("three rapid edits apply exactly one preview", async () => {
    const clock = manualClock();
    const seen = [];
    const applied = [];
    const pump = new PreviewPump(
        (spec) => { seen.push(spec); return Promise.resolve({ ok: true, result: spec.n }); },
        (res) => applied.push(res),
        { delay: 260, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout });

    pump.schedule({ n: 1 });
    pump.schedule({ n: 2 });
    pump.schedule({ n: 3 });
    // Only the last one is still queued; the first two were cleared.
    expect(clock.pending).toBe(1);

    clock.tick();
    await animationFrame();
    expect(seen.length).toBe(1);
    expect(seen[0].n).toBe(3);
    expect(applied.length).toBe(1);
    expect(applied[0].result).toBe(3);
});

test("a stale response never overwrites a newer one", async () => {
    const clock = manualClock();
    const applied = [];
    // Two deferreds, resolved in the WRONG order — which is the ordinary case
    // on a slow first query and a fast second one, and it draws a plausible
    // wrong number with no error anywhere.
    const gates = [];
    const pump = new PreviewPump(
        (spec) => new Promise((resolve) => gates.push(() => resolve(
            { ok: true, result: spec.n }))),
        (res) => applied.push(res.result),
        { delay: 0, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout });

    pump.schedule({ n: "old" });
    clock.tick();                       // fires the first run, which now hangs
    await animationFrame();
    pump.schedule({ n: "new" });
    clock.tick();                       // fires the second run
    await animationFrame();

    expect(gates.length).toBe(2);
    gates[1]();                         // the NEWER answer arrives first
    await animationFrame();
    gates[0]();                         // …and the older one lands afterwards
    await animationFrame();

    expect(applied).toEqual(["new"]);   // the stale one was dropped, not applied
});

test("cancel drops what is pending and what is in flight", async () => {
    const clock = manualClock();
    const applied = [];
    let release;
    const pump = new PreviewPump(
        () => new Promise((resolve) => { release = () => resolve({ ok: true }); }),
        (res) => applied.push(res),
        { delay: 0, setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout });

    pump.schedule({});
    clock.tick();
    await animationFrame();
    pump.cancel();
    release();
    await animationFrame();
    expect(applied.length).toBe(0);
});

// ================================================== T5 — the two read-only cases
test("a python rule and a non-manager both open read-only, with different sentences", () => {
    const pythonRule = { ...blankSpec(), builder_mode: "python", has_python: true };
    const pythonNote = readOnlyReason(payload(), pythonRule);
    expect(pythonNote).toBeTruthy();
    // The neutral product voice: never the name of the platform underneath.
    expect(pythonNote.toLowerCase().includes("odoo")).toBe(false);

    const lockedNote = readOnlyReason(payload({ can_edit: false }), blankSpec());
    expect(lockedNote).toBeTruthy();
    expect(lockedNote.toLowerCase().includes("odoo")).toBe(false);

    // Two different refusals mean opposite things to the reader — one is about
    // the RULE, the other about the READER — so they must not share a sentence.
    expect(pythonNote).not.toBe(lockedNote);

    // A guided rule for a manager is editable, which is the case that proves
    // the two above are not simply "always read-only".
    expect(readOnlyReason(payload(), blankSpec())).toBe("");
});

test("a CONVERTED rule keeps its old program as provenance and stays editable", () => {
    // Found on the live abm board, by opening the one rule the whole cycle was
    // for. Cycle 8's migration converts DEPCOUNT and WORKEDHRS to guided steps
    // and DELIBERATELY leaves `python_code` in place, so the generated sentence
    // can be checked against what the legacy actually did — which makes
    // `has_python` TRUE on a rule that is not in the advanced lane at all.
    // Reading that key as a lane locked the owner out of both of them.
    const converted = {
        ...blankSpec(),
        builder_mode: "guided",
        rule_type: "sum",
        value_steps: [
            { field: "totalWorkedHours", contains: "seconds" },
            { field: "paidLeaveHours", contains: "hmm" },
        ],
        has_python: true,
        python_code: "total = 0.0\nfor r in records:\n    ...\nresult = total\n",
        plain_summary: "Adds up totalWorkedHours plus paidLeaveHours over Attendance records",
    };
    expect(readOnlyReason(payload(), converted)).toBe("");

    // …and the lane is decided by builder_mode ALONE, in both directions.
    expect(readOnlyReason(payload(), { ...converted, builder_mode: "python" }))
        .toBeTruthy();
    expect(readOnlyReason(payload(), { ...blankSpec(), has_python: false }))
        .toBe("");
});

test("a python rule renders no save affordance", async () => {
    onRpc("pb.integrations", "rule_composer_data", () => payload({
        rule: { ...blankSpec(), id: 4, name: "WORKEDHRS", output_key: "WORKEDHRS",
                builder_mode: "python", has_python: true,
                plain_summary: "Advanced rule, maintained by your administrator." },
    }));
    await mountWithCleanup(RuleComposer, {
        props: { connectorId: 7, ruleId: 4, onClose: () => {}, onSaved: () => {} },
    });
    await animationFrame();
    // The claim is about the DOM, which is why this one mounts: a getter that
    // returns false is not evidence that no button was drawn.
    expect(".itgrc .pbim-btn.primary").toHaveCount(0);
    expect(".itgrc-summary").toHaveCount(1);
});

test("a non-manager payload renders no save affordance either", async () => {
    onRpc("pb.integrations", "rule_composer_data", () => payload({
        can_edit: false,
        rule: { ...blankSpec(), id: 5, name: "OTHRS150", output_key: "OTHRS150",
                source_data_type: "attendance" },
    }));
    onRpc("pb.integrations", "rule_preview", () => ({
        ok: true, synthetic: false, result: 0, records_in: 0, matched: 0,
        valued: 0, rows: [], summary: "",
    }));
    await mountWithCleanup(RuleComposer, {
        props: { connectorId: 7, ruleId: 5, onClose: () => {}, onSaved: () => {} },
    });
    await animationFrame();
    expect(".itgrc .pbim-btn.primary").toHaveCount(0);
    expect(".itgrc-add").toHaveCount(0);      // no "+ add condition" either
    expect(".itgrc-ro").toHaveCount(1);       // and it says so, in a sentence
});

// ============================================ T6 — one sentence, one msgid (W80)
test("the proof-rail sentence is ONE template with named placeholders", () => {
    const calls = [];
    const spy = (template, params) => {
        calls.push([template, params]);
        return String(template).replace(
            /%\((\w+)\)s/g, (_m, key) => String(params[key]));
    };

    const out = railSentence(
        { records_in: 24, matched: 5, result: 10.5 }, spy);

    // ONE call. A translator cannot reorder fragments, and word order is the
    // first thing that differs between languages — so a sentence carrying three
    // numbers is the one that must never be assembled from `t-esc` nodes.
    expect(calls.length).toBe(1);
    const [template, params] = calls[0];
    // NAMED placeholders, which is what lets the order change at all.
    expect(template).toMatch(/%\(records\)s/);
    expect(template).toMatch(/%\(matched\)s/);
    expect(template).toMatch(/%\(result\)s/);
    expect(Object.keys(params).sort()).toEqual(["matched", "records", "result"]);
    expect(out).toBe("24 records → 5 match → 10.5");

    // A rail with nothing computed yet says so rather than printing a blank
    // where a number belongs.
    expect(railSentence({}, spy)).toBe("0 records → 0 match → —");
});
