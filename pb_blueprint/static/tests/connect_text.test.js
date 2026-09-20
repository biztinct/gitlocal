/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { translatedTerms, translationLoaded } from "@web/core/l10n/translation";

import {
    CONNECT_TASKS, LANES, statusPill, statusHint, laneLabel, coverageLine,
    payslipLine, changedLine, removedLine, manageLater, canMarkDone,
    connectProgress,
} from "@pb_blueprint/js/connect_text";

// BP28 / BP37 — a unit test has no server to fetch translations from, and a
// `_t()` label is a String OBJECT whose `valueOf()` refuses to answer until the
// runner is told they are loaded. English is the source language, so "loaded
// with nothing" is exactly right: every term falls through to its own source.
//
// Every label in `connect_text.js` is built INSIDE a function, on purpose, so
// with this flag set the module hands back ordinary strings and nothing in this
// suite can ever hit the lazy path (BP37).
translatedTerms[translationLoaded] = true;
beforeEach(() => {
    translatedTerms[translationLoaded] = true;
});

const s = (v) => String(v);

describe("connect — the status words", () => {
    test("three tasks and four lanes, in one order", () => {
        expect(CONNECT_TASKS).toEqual(["mapping", "payslip", "approvals"]);
        expect(LANES).toEqual(["api", "excel", "records", "cycle"]);
    });

    test("every status has a word and a class of its own", () => {
        const seen = new Set();
        for (const key of ["not_started", "in_progress", "configured",
                           "skipped", "needs_review", "info"]) {
            const pill = statusPill(key);
            expect(pill.key).toBe(key);
            expect(s(pill.label)).not.toBe("");
            expect(seen.has(pill.cls)).toBe(false);
            seen.add(pill.cls);
        }
    });

    test("anything unknown reads as not started, never as done", () => {
        expect(statusPill("nonsense").key).toBe("not_started");
        expect(statusPill(undefined).key).toBe("not_started");
    });

    test("the pill says the word a person would say", () => {
        expect(s(statusPill("configured").label)).toBe("Done");
        expect(s(statusPill("needs_review").label)).toBe("Needs another look");
        expect(s(statusPill("info").label)).toBe("Already in place");
    });

    test("only the states that need explaining carry a hint", () => {
        expect(s(statusHint("in_progress"))).not.toBe("");
        expect(s(statusHint("skipped"))).not.toBe("");
        expect(s(statusHint("needs_review"))).not.toBe("");
        expect(statusHint("not_started")).toBe("");
        expect(statusHint("configured")).toBe("");
    });

    test("a card never says nothing is connected while something is", () => {
        // Found in the browser, on the first return from the mapping screen:
        // the coverage line said "1 of 52 inputs has a source" and the hint
        // under it said nothing was connected yet.
        expect(s(statusHint("in_progress", 0))).toBe(
            "You opened it, and nothing is connected yet.");
        expect(s(statusHint("in_progress", 1))).toBe(
            "Mark it done when you are happy with it.");
    });

    test("every lane has words, and an unknown one has none", () => {
        for (const lane of LANES) {
            expect(s(laneLabel(lane))).not.toBe("");
        }
        expect(laneLabel("nonsense")).toBe("");
    });
});

describe("connect — the coverage line", () => {
    test("nothing to map is said in words, never as 0 of 0", () => {
        expect(s(coverageLine({ inputs: 0, mapped: 0 }))).toBe(
            "This configuration has no inputs to map yet.");
        expect(s(coverageLine(undefined))).toBe(
            "This configuration has no inputs to map yet.");
    });

    test("only the lanes with something in them are named", () => {
        const line = s(coverageLine({
            inputs: 19, mapped: 12,
            by_lane: { api: 4, excel: 6, records: 2, cycle: 0 },
        }));
        expect(line).toBe("12 of 19 inputs have a source · 4 from the connected "
                          + "system · 6 from spreadsheets · 2 from employee records");
        expect(line.includes("carried from the mid-month run")).toBe(false);
    });

    test("one is singular", () => {
        expect(s(coverageLine({ inputs: 19, mapped: 1, by_lane: { api: 1 } })))
            .toBe("1 of 19 inputs has a source · 1 from the connected system");
    });

    test("nothing connected still says how many are waiting", () => {
        expect(s(coverageLine({ inputs: 19, mapped: 0, by_lane: {} })))
            .toBe("0 of 19 inputs have a source");
    });

    test("the mid-month carry is a lane like any other", () => {
        expect(s(coverageLine({ inputs: 3, mapped: 1, by_lane: { cycle: 1 } })))
            .toBe("1 of 3 inputs has a source · 1 carried from the mid-month run");
    });
});

describe("connect — the payslip line", () => {
    test("an empty configuration says so rather than showing zeroes", () => {
        expect(s(payslipLine({ total: 0 }))).toBe(
            "There are no components to place yet.");
    });

    test("placed, tray and sections, and nothing that is zero", () => {
        expect(s(payslipLine({ total: 38, placed: 31, tray: 7, sections: 4 })))
            .toBe("31 of 38 components placed · 7 in the tray · 4 sections");
        expect(s(payslipLine({ total: 38, placed: 0, tray: 0, sections: 0 })))
            .toBe("0 of 38 components placed");
        expect(s(payslipLine({ total: 38, placed: 1, tray: 1, sections: 1 })))
            .toBe("1 of 38 components placed · 1 in the tray · 1 section");
    });
});

describe("connect — what changed since", () => {
    test("nothing changed says nothing at all", () => {
        expect(changedLine("mapping", [])).toBe("");
        expect(changedLine("mapping", undefined)).toBe("");
        expect(removedLine([])).toBe("");
    });

    test("the codes are named, because a count alone is not actionable", () => {
        expect(s(changedLine("mapping", ["OTWD", "OTWE", "OTHOL"]))).toBe(
            "3 components were added since you mapped: OTWD, OTWE, OTHOL");
        expect(s(changedLine("mapping", ["OTWD"]))).toBe(
            "1 component was added since you mapped: OTWD");
    });

    test("the payslip says arranged, not mapped", () => {
        expect(s(changedLine("payslip", ["A", "B"])).includes(
            "arranged the payslip")).toBe(true);
    });

    test("a long list is cut, and says it was cut", () => {
        const many = ["A", "B", "C", "D", "E", "F", "G", "H"];
        const line = s(changedLine("mapping", many));
        expect(line.includes("and 2 more")).toBe(true);
        expect(line.includes("H,")).toBe(false);
    });

    test("something that was placed and has gone is a different sentence", () => {
        expect(s(removedLine(["PHONEALLOW"]))).toBe(
            "1 component you had placed has gone since: PHONEALLOW");
        expect(s(removedLine(["A", "B"])).includes("2 components")).toBe(true);
    });
});

describe("connect — what a person may press", () => {
    test("mark as done appears only once there is something to be done about", () => {
        expect(canMarkDone("mapping", { mapping: { mapped: 0 } })).toBe(false);
        expect(canMarkDone("mapping", { mapping: { mapped: 1 } })).toBe(true);
        expect(canMarkDone("payslip", { payslip: { placed: 0 } })).toBe(false);
        expect(canMarkDone("payslip", { payslip: { placed: 3 } })).toBe(true);
        expect(canMarkDone("mapping", undefined)).toBe(false);
    });

    test("every card says where to find the same tool later", () => {
        for (const task of CONNECT_TASKS) {
            expect(s(manageLater(task)).startsWith("Manage later:")).toBe(true);
        }
    });

    test("progress counts the two tasks that are work", () => {
        expect(connectProgress({ mapping: "configured", payslip: "skipped" }))
            .toEqual({ done: 1, total: 2 });
        expect(connectProgress({ mapping: "configured", payslip: "configured" }))
            .toEqual({ done: 2, total: 2 });
        expect(connectProgress({})).toEqual({ done: 0, total: 2 });
        // "Approvals" is information, so it can never make this number move.
        expect(connectProgress({ approvals: "info" })).toEqual({ done: 0, total: 2 });
    });
});
