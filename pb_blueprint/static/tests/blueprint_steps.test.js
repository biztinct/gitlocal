/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { translatedTerms, translationLoaded } from "@web/core/l10n/translation";

import {
    STEPS, STEP_META, nextStep, prevStep, stepNumber, isDone, continueLabel,
    continueTarget, backTarget,
    fmtShort, fmtFull, deltaLabel, toNumber, toggle, freshSituations,
    firstOfNextMonth, savedAgo, freshToken, AUDIENCES, REALLIFE,
} from "@pb_blueprint/js/blueprint_steps";

// `_t()` returns a lazily translated string, not a primitive, so every
// assertion about a LABEL goes through String() — comparing the object with
// `===` would fail for a reason that has nothing to do with the label.
const s = (v) => String(v);

// BP28 — reading a `_t()` label THROWS ("translations have not been loaded")
// until the runner is told they are: a unit test has no server to fetch them
// from. English is the source language, so "loaded with nothing" is exactly
// right — every term falls through to its own source string.
// BP28 / BP29 — reading a `_t()` label throws ("translations have not been
// loaded") because a unit test has no server to fetch them from. Setting the
// flag at import time and again before every test fixes it for the labels this
// module reads from `recipe_text`, but NOT for the four tests below that read
// `blueprint_steps`' own module-level labels: see the B3 report, deferred item
// 4. Left in place because it is the documented fix and it is correct.
translatedTerms[translationLoaded] = true;
beforeEach(() => {
    translatedTerms[translationLoaded] = true;
});

describe("guided setup — the journey", () => {
    test("six steps, in one order, keyed not numbered", () => {
        expect(STEPS).toEqual(["start", "rules", "connect", "outputs", "test", "finish"]);
        for (const key of STEPS) {
            expect(Boolean(STEP_META[key])).toBe(true);
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

    test("a step made of tabs is walked tab by tab before it is left", () => {
        const a = continueTarget("rules", "components");
        expect(a.kind).toBe("tab");
        expect(a.tab).toBe("tax");
        expect(s(a.label)).toBe("Continue to Tax & protection");

        const b = continueTarget("rules", "tax");
        expect(b.kind).toBe("tab");
        expect(b.tab).toBe("calendar");
        expect(s(b.label)).toBe("Continue to Calendar & payment");

        // Only the LAST tab leaves the step — this is the whole point: the
        // button can no longer walk past two screens of unseen decisions.
        const c = continueTarget("rules", "calendar");
        expect(c.kind).toBe("step");
        expect(c.step).toBe("connect");
        expect(s(c.label)).toBe("Continue to connect");
    });

    test("a step with no tabs is unchanged", () => {
        for (const key of ["start", "connect", "outputs", "test", "finish"]) {
            const t = continueTarget(key, "");
            expect(t.kind).toBe("step");
            expect(s(t.label)).toBe(s(continueLabel(key)));
        }
    });

    test("no tab is skipped when the stored tab key is unknown", () => {
        // A draft saved by an older version, or a tab that has since been
        // renamed: the walk starts at the beginning rather than jumping out.
        const t = continueTarget("rules", "somethingelse");
        expect(t.kind).toBe("tab");
        expect(t.tab).toBe("tax");
    });

    test("Back walks the same tabs in reverse", () => {
        expect(backTarget("rules", "calendar")).toEqual({ kind: "tab", tab: "tax" });
        expect(backTarget("rules", "tax")).toEqual({ kind: "tab", tab: "components" });
        // From the first tab it leaves the step, so Continue and Back are
        // exact opposites everywhere on the strip.
        expect(backTarget("rules", "components")).toEqual({ kind: "step", step: "start" });
        expect(backTarget("outputs", "")).toEqual({ kind: "step", step: "connect" });
    });

    test("Continue and Back undo each other on every tab", () => {
        for (const tab of ["components", "tax"]) {
            const fwd = continueTarget("rules", tab);
            expect(fwd.kind).toBe("tab");
            expect(backTarget("rules", fwd.tab)).toEqual({ kind: "tab", tab });
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
            expect(Boolean(a.key)).toBe(true);
            expect(Boolean(a.icon)).toBe(true);
            expect(s(a.label)).not.toBe("");
            expect(s(a.hint)).not.toBe("");
        }
        for (const r of REALLIFE) {
            expect(Boolean(r.key)).toBe(true);
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
