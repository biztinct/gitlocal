/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { translatedTerms, translationLoaded } from "@web/core/l10n/translation";

import {
    FILTER_KEYS, VERDICTS, filterLabel, filterHint, badgeLabel, groupLabel,
    flowNodes, fmtValue, formulaText, isLongFormula, coverageLine,
    coverageIsComplete, evidenceChip, lastRunLine, agoFrom, verdictPill,
    runPlan, runHeadline, chainMore, beyondRecipes, filterRows, windowOf,
    peopleCount, sourcedLine,
} from "@pb_blueprint/js/outputs_text";

// BP28 / BP37 — a unit test has no server to fetch translations from, and a
// `_t()` label is a String OBJECT whose `valueOf()` refuses to answer until the
// runner is told they are loaded. Every label in `outputs_text.js` is built
// INSIDE a function, so with this flag set nothing here can hit the lazy path.
translatedTerms[translationLoaded] = true;
beforeEach(() => {
    translatedTerms[translationLoaded] = true;
});

const s = (v) => String(v);

describe("outputs — the filter chips", () => {
    test("nine chips, in the order they are read, final first", () => {
        expect(FILTER_KEYS[0]).toBe("final");
        expect(FILTER_KEYS.at(-1)).toBe("all");
        expect(FILTER_KEYS.length).toBe(9);
    });

    test("every chip has a label and a hint of its own", () => {
        const labels = new Set();
        const hints = new Set();
        for (const key of FILTER_KEYS) {
            const label = s(filterLabel(key));
            const hint = s(filterHint(key));
            expect(label).not.toBe("");
            expect(hint).not.toBe("");
            expect(labels.has(label)).toBe(false);
            expect(hints.has(hint)).toBe(false);
            labels.add(label);
            hints.add(hint);
        }
    });

    test("the words are the ones on the screen, not the ones in the code", () => {
        expect(s(filterLabel("final"))).toBe("Final outputs");
        expect(s(filterLabel("manual"))).toBe("Edited by hand");
        expect(s(filterLabel("intermediate"))).toBe("Behind the scenes");
    });
});

describe("outputs — badges and groups", () => {
    test("every badge says where the calculation came from", () => {
        expect(s(badgeLabel("generated"))).toBe("From your settings");
        expect(s(badgeLabel("manual"))).toBe("Written as Excel");
        expect(s(badgeLabel("review"))).toBe("Needs a decision");
        expect(s(badgeLabel("problem"))).toBe("Problem");
    });

    test("an unknown badge reads as generated, never as a problem", () => {
        expect(s(badgeLabel("nonsense"))).toBe("From your settings");
    });

    test("groups keep the words the Pay rules step uses", () => {
        expect(s(groupLabel("earning"))).toBe("Earnings");
        expect(s(groupLabel("helper"))).toBe("Inputs & fixed values");
    });
});

describe("outputs — the money-flow strip", () => {
    test("four nodes, the last one carrying the two numbers", () => {
        const nodes = flowNodes({ inputs: 79, components: 38, rules: 114 },
                                { net: 27035000, employer_cost: 36950000 });
        expect(nodes.length).toBe(4);
        expect(nodes[0].n).toBe(79);
        expect(nodes[1].n).toBe(38);
        expect(nodes[2].n).toBe(114);
        expect(nodes[3].n).toBe(null);
        expect(nodes[3].net).toBe(27035000);
        expect(nodes[3].employer).toBe(36950000);
    });

    test("every node knows which chips it lights up", () => {
        const nodes = flowNodes({}, {});
        expect(nodes[0].filters).toEqual(["inputs"]);
        expect(nodes[1].filters).toEqual(["earning", "deduction", "benefit"]);
        expect(nodes[3].filters).toEqual(["final"]);
    });

    test("one of a thing is not called things", () => {
        const nodes = flowNodes({ inputs: 1, components: 1, rules: 1 }, {});
        expect(s(nodes[0].label)).toBe("input & fixed value");
        expect(s(nodes[1].label)).toBe("component");
        expect(s(nodes[2].label)).toBe("calculation");
    });

    test("a configuration with nothing in it still makes four nodes", () => {
        const nodes = flowNodes(undefined, undefined);
        expect(nodes.length).toBe(4);
        expect(nodes[0].n).toBe(0);
        expect(nodes[3].net).toBe(null);
    });
});

describe("outputs — numbers and formulas", () => {
    test("a number is grouped, and nothing is an em dash", () => {
        expect(fmtValue(30000000)).toBe("30,000,000");
        expect(fmtValue(0)).toBe("0");
        expect(fmtValue(null)).toBe("—");
        expect(fmtValue(undefined)).toBe("—");
    });

    test("a negative number keeps a real minus sign", () => {
        expect(fmtValue(-7500)).toBe("− 7,500");
    });

    test("an input says it is given, a fixed value shows its amount", () => {
        expect(s(formulaText({ column_type: "input" })))
            .toBe("Given to the payroll");
        expect(s(formulaText({ column_type: "constant", constant_value: 15500000 })))
            .toBe("15,500,000");
        expect(s(formulaText({ column_type: "formula", excel_codes: "=A+B" })))
            .toBe("=A+B");
        expect(s(formulaText({ column_type: "formula", excel_codes: "" })))
            .toBe("Nothing is worked out yet");
    });

    test("only a formula long enough to hide something offers to show all", () => {
        expect(isLongFormula({ excel_codes: "=SIBASE*SIRATE" })).toBe(false);
        expect(isLongFormula({ excel_codes: "=".padEnd(60, "X") })).toBe(true);
    });
});

describe("outputs — search and windowing", () => {
    const rows = [
        { name: "Personal income tax", code: "PIT", excel_codes: "=BRACKET(VNTAX,TAXABLE)", letter: "BY" },
        { name: "Take-home pay", code: "NET", excel_codes: "=GROSS-EEDED-PIT", letter: "CN" },
        { name: "Phone allowance", code: "PHONEALLOW", excel_codes: "=ROUND(500000,0)", letter: "AY" },
    ];

    test("nothing typed is everything shown", () => {
        expect(filterRows(rows, "").length).toBe(3);
        expect(filterRows(rows, "   ").length).toBe(3);
    });

    test("a search reaches the name, the code and the calculation", () => {
        expect(filterRows(rows, "phone").map((r) => r.code)).toEqual(["PHONEALLOW"]);
        expect(filterRows(rows, "pit").map((r) => r.code)).toEqual(["PIT", "NET"]);
        expect(filterRows(rows, "bracket").map((r) => r.code)).toEqual(["PIT"]);
    });

    test("a column letter matches only when it is the whole search", () => {
        expect(filterRows(rows, "cn").map((r) => r.code)).toEqual(["NET"]);
    });

    test("a window paints a slice and keeps the scrollbar honest", () => {
        const w = windowOf(400, 0, 600, 46, 6);
        expect(w.first).toBe(0);
        expect(w.top).toBe(0);
        expect(w.last).toBeGreaterThan(12);
        expect(w.bottom).toBe((400 - w.last) * 46);
    });

    test("scrolled down, the spacers add up to what is not painted", () => {
        const w = windowOf(400, 4600, 600, 46, 6);
        expect(w.first).toBe(94);
        expect(w.top).toBe(94 * 46);
        expect(w.top + (w.last - w.first) * 46 + w.bottom).toBe(400 * 46);
    });

    test("a short list is never windowed away", () => {
        const w = windowOf(3, 0, 600, 46);
        expect(w.first).toBe(0);
        expect(w.last).toBe(3);
        expect(w.bottom).toBe(0);
    });
});

describe("test — coverage in words", () => {
    test("only the parts that have something in them are named", () => {
        expect(s(coverageLine({ total: 21, asserted: 18, exercised: 2,
                                untested_count: 1 })))
            .toBe("18 of 21 calculations are checked by a confirmed scenario · 2 are used on the way · 1 is untested");
        expect(s(coverageLine({ total: 21, asserted: 21, exercised: 0,
                                untested_count: 0 })))
            .toBe("21 of 21 calculations are checked by a confirmed scenario");
    });

    test("one of something is not called several", () => {
        expect(s(coverageLine({ total: 4, asserted: 1, exercised: 1,
                                untested_count: 1 })))
            .toBe("1 of 4 calculations is checked by a confirmed scenario · 1 is used on the way · 1 is untested");
    });

    test("nothing to check is said in words, never as zero of zero", () => {
        expect(s(coverageLine({ total: 0 })))
            .toBe("There are no calculations to check yet.");
        expect(s(coverageLine(undefined)))
            .toBe("There are no calculations to check yet.");
    });

    test("complete coverage is worth saying out loud, and empty is not", () => {
        expect(coverageIsComplete({ total: 21, untested_count: 0 })).toBe(true);
        expect(coverageIsComplete({ total: 21, untested_count: 1 })).toBe(false);
        expect(coverageIsComplete({ total: 0, untested_count: 0 })).toBe(false);
    });
});

describe("test — the evidence chip", () => {
    test("never run is not a warning", () => {
        const chip = evidenceChip({ ever_run: false });
        expect(chip.cls).toBe("is-idle");
        expect(s(chip.text)).toBe("Not checked yet");
    });

    test("stale beats everything, including a full pass", () => {
        const chip = evidenceChip({ ever_run: true, stale: true, passed: 12,
                                    failed: 0, pending: 0 });
        expect(chip.cls).toBe("is-stale");
        expect(s(chip.text)).toBe("Changed since the last check — run it again");
    });

    test("a failure outranks a pending confirmation", () => {
        const chip = evidenceChip({ ever_run: true, failed: 3, pending: 2 });
        expect(chip.cls).toBe("is-bad");
        expect(s(chip.text)).toBe("3 checks need attention");
    });

    test("waiting says what it is waiting for", () => {
        const chip = evidenceChip({ ever_run: true, failed: 0, pending: 1 });
        expect(chip.cls).toBe("is-wait");
        expect(s(chip.text)).toBe("1 check is waiting for you to confirm it");
    });

    test("all green says how many", () => {
        const chip = evidenceChip({ ever_run: true, passed: 12 });
        expect(chip.cls).toBe("is-good");
        expect(s(chip.text)).toBe("12 checks passed");
    });

    test("a chip with no evidence at all still renders something", () => {
        expect(evidenceChip(undefined).cls).toBe("is-idle");
    });
});

describe("test — when it last ran", () => {
    const now = Date.parse("2026-09-10T12:00:00Z");

    test("a timestamp becomes something a person would say", () => {
        expect(s(agoFrom("2026-09-10 11:58:00", now))).toBe("2 min ago");
        expect(s(agoFrom("2026-09-10 11:59:40", now))).toBe("just now");
        expect(s(agoFrom("2026-09-10 09:00:00", now))).toBe("3 hours ago");
        expect(s(agoFrom("2026-09-09 12:00:00", now))).toBe("1 day ago");
    });

    test("no timestamp is an empty string, never the word undefined", () => {
        expect(agoFrom("", now)).toBe("");
        expect(agoFrom(null, now)).toBe("");
        expect(agoFrom("not a date", now)).toBe("");
    });

    test("the line is absent until there is something to report", () => {
        expect(lastRunLine({ ever_run: false })).toBe("");
        expect(s(lastRunLine({ ever_run: true, run_at: "2026-09-10 11:58:00",
                               run_by: "Mai" }))).toMatch(/Mai/);
    });
});

describe("test — verdicts and the run card", () => {
    test("four verdicts, each with a word and a look of its own", () => {
        const seen = new Set();
        for (const key of VERDICTS) {
            const pill = verdictPill(key);
            expect(pill.key).toBe(key);
            expect(s(pill.label)).not.toBe("");
            expect(seen.has(pill.cls)).toBe(false);
            seen.add(pill.cls);
        }
    });

    test("anything unknown reads as not checked, never as passed", () => {
        expect(verdictPill("nonsense").key).toBe("not_run");
        expect(verdictPill(undefined).key).toBe("not_run");
    });

    test("the run plan names each kind that is actually there", () => {
        const samples = [
            { kind: "starter" }, { kind: "starter" }, { kind: "boundary" },
            { kind: "boundary" }, { kind: "boundary" }, { kind: "yours" },
        ];
        expect(s(runPlan(samples)))
            .toBe("the starting point's 2 scenarios · 3 boundary cases · 1 of your own");
    });

    test("a kind with nothing in it is not named at all", () => {
        expect(s(runPlan([{ kind: "yours" }]))).toBe("1 of your own");
        expect(s(runPlan([]))).toBe("");
    });

    test("the headline counts what will actually run", () => {
        expect(s(runHeadline([{}, {}, {}]))).toBe("One click. 3 meaningful checks.");
        expect(s(runHeadline([{}]))).toBe("One click. 1 meaningful check.");
        expect(s(runHeadline([]))).toBe("Nothing to check yet.");
    });
});

describe("test — a real person", () => {
    test("one of something is never called several", () => {
        expect(s(peopleCount(902))).toBe("902 people");
        expect(s(peopleCount(1))).toBe("1 person");
        expect(s(peopleCount(0))).toBe("0 people");
    });

    test("how much of this person is real, in words", () => {
        expect(s(sourcedLine(3))).toBe("3 values came from a real source");
        expect(s(sourcedLine(1))).toBe("1 value came from a real source");
        expect(s(sourcedLine(0))).toBe("no value came from a real source");
    });
});

describe("test — the honest parts", () => {
    test("a chain that had to stop says how much it left out", () => {
        expect(chainMore(0)).toBe("");
        expect(s(chainMore(1))).toBe("and 1 more further away");
        expect(s(chainMore(7))).toBe("and 7 more further away");
    });

    test("five recipes, each with a title and a sentence, and no buttons", () => {
        const rows = beyondRecipes();
        expect(rows.length).toBe(5);
        for (const row of rows) {
            expect(s(row.title)).not.toBe("");
            expect(s(row.text)).not.toBe("");
            expect(row.action).toBe(undefined);
        }
    });
});
