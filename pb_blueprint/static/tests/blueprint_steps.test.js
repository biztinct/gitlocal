/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import {
    STEPS, STEP_META, nextStep, prevStep, stepNumber, isDone, continueLabel,
    fmtShort, fmtFull, deltaLabel, toNumber, toggle, freshSituations,
    firstOfNextMonth, savedAgo, freshToken, AUDIENCES, REALLIFE,
} from "@pb_blueprint/js/blueprint_steps";

// `_t()` returns a lazily translated string, not a primitive, so every
// assertion about a LABEL goes through String() — comparing the object with
// `===` would fail for a reason that has nothing to do with the label.
const s = (v) => String(v);

describe("guided setup — the journey", () => {
    test("six steps, in one order, keyed not numbered", () => {
        expect(STEPS).toEqual(["start", "rules", "connect", "outputs", "test", "finish"]);
        for (const key of STEPS) {
            expect(STEP_META[key]).toBeTruthy();
            expect(s(STEP_META[key].label)).not.toBe("");
            expect(s(STEP_META[key].hint)).not.toBe("");
            expect(s(STEP_META[key].title)).not.toBe("");
        }
    });

    test("next and previous never walk off either end", () => {
        expect(nextStep("start")).toBe("rules");
        expect(nextStep("outputs")).toBe("test");
        expect(nextStep("finish")).toBe("finish");
        expect(prevStep("rules")).toBe("start");
        expect(prevStep("start")).toBe("start");
        // An unknown key lands somewhere real rather than throwing.
        expect(nextStep("nonsense")).toBe("start");
        expect(prevStep("nonsense")).toBe("start");
    });

    test("step numbers are 1-based and match the rail", () => {
        expect(stepNumber("start")).toBe(1);
        expect(stepNumber("connect")).toBe(3);
        expect(stepNumber("finish")).toBe(6);
        expect(stepNumber("nonsense")).toBe(1);
    });

    test("a step is done once it has been passed", () => {
        expect(isDone("start", "rules")).toBe(true);
        expect(isDone("rules", "rules")).toBe(false);
        expect(isDone("outputs", "rules")).toBe(false);
    });

    test("the primary button says where it goes, never just Continue", () => {
        expect(s(continueLabel("start"))).toBe("Continue to pay rules");
        expect(s(continueLabel("rules"))).toBe("Continue to connect");
        expect(s(continueLabel("test"))).toBe("Continue to finish");
        expect(s(continueLabel("finish"))).toBe("Finish & open");
        for (const key of STEPS) {
            expect(s(continueLabel(key)).toLowerCase()).not.toBe("continue");
        }
    });
});

describe("guided setup — the numbers on the pay panel", () => {
    test("the headline is short enough to set at 36px", () => {
        expect(fmtShort(31160000)).toBe("31.16m");
        expect(fmtShort(950000)).toBe("950k");
        expect(fmtShort(1200000000)).toBe("1.2bn");
        expect(fmtShort(1200)).toBe("1,200");
        expect(fmtShort(0)).toBe("0");
    });

    test("a missing number is a dash, never a zero", () => {
        // Zero and "we do not have this" are different facts, and showing the
        // second as the first is how a blank canvas looks like a bug.
        expect(fmtShort(null)).toBe("—");
        expect(fmtShort(undefined)).toBe("—");
        expect(fmtShort("")).toBe("—");
        expect(fmtFull(null)).toBe("—");
        expect(fmtShort(0)).not.toBe("—");
    });

    test("a negative number uses a real minus sign", () => {
        expect(fmtShort(-2500000)).toBe("−2.5m");
        expect(fmtFull(-1234.5)).toBe("− 1,234.5");
        expect(fmtFull(1234567)).toBe("1,234,567");
    });

    test("the delta chip is absent when there is nothing to say", () => {
        expect(deltaLabel(null, 5)).toBe(null);
        expect(deltaLabel(5, null)).toBe(null);
        expect(deltaLabel(5, 5)).toBe(null);
    });

    test("the delta chip names the direction and the size", () => {
        expect(deltaLabel(30000000, 31200000)).toEqual({ text: "+1.2m", up: true });
        expect(deltaLabel(31200000, 30840000)).toEqual({ text: "−360k", up: false });
    });

    test("only a finite number reaches the server", () => {
        expect(toNumber("30,000,000")).toBe(30000000);
        expect(toNumber("1 500")).toBe(1500);
        expect(toNumber("")).toBe(null);
        expect(toNumber("twelve")).toBe(null);
        expect(toNumber("1e400")).toBe(null);
        expect(toNumber(0)).toBe(0);
    });
});

describe("guided setup — the Start step's choices", () => {
    test("local employees are ticked, the first two situations are on", () => {
        const fresh = freshSituations();
        expect(fresh.audiences).toEqual(["local"]);
        expect(fresh.reallife).toEqual(["joiners", "annual"]);
    });

    test("every tile and check has a key, an icon and words", () => {
        for (const a of AUDIENCES) {
            expect(a.key).toBeTruthy();
            expect(a.icon).toBeTruthy();
            expect(s(a.label)).not.toBe("");
            expect(s(a.hint)).not.toBe("");
        }
        for (const r of REALLIFE) {
            expect(r.key).toBeTruthy();
            expect(s(r.label)).not.toBe("");
        }
    });

    test("toggling returns a new list and never mutates the old one", () => {
        const before = ["local"];
        const after = toggle(before, "netpay");
        expect(before).toEqual(["local"]);
        expect(after).toEqual(["local", "netpay"]);
        expect(toggle(after, "local")).toEqual(["netpay"]);
        expect(toggle(undefined, "local")).toEqual(["local"]);
    });

    test("effective from defaults to the first of next month", () => {
        expect(firstOfNextMonth(new Date(2026, 8, 10))).toBe("2026-10-01");
        expect(firstOfNextMonth(new Date(2026, 11, 31))).toBe("2027-01-01");
    });
});

describe("guided setup — saying when it was saved", () => {
    test("plain words, never a timestamp", () => {
        expect(s(savedAgo(0))).toBe("saved just now");
        expect(s(savedAgo(20 * 1000))).toBe("saved just now");
        expect(s(savedAgo(2 * 60 * 1000))).toBe("saved 2 min ago");
        expect(s(savedAgo(60 * 60 * 1000))).toBe("saved 1 hour ago");
        expect(s(savedAgo(5 * 60 * 60 * 1000))).toBe("saved 5 hours ago");
        expect(s(savedAgo(26 * 60 * 60 * 1000))).toBe("saved 1 day ago");
    });
});

describe("guided setup — the setup key", () => {
    test("two journeys never share a key", () => {
        // The whole idempotency promise rests on this: the same key returns the
        // same draft, so two different journeys must never mint the same one.
        const keys = new Set(Array.from({ length: 200 }, () => freshToken()));
        expect(keys.size).toBe(200);
        expect(freshToken().startsWith("bp-")).toBe(true);
    });
});
