/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { translatedTerms, translationLoaded } from "@web/core/l10n/translation";

import {
    bandRange, bandRows, effectiveRate, group, percentFromRate, rateFromPercent,
    showValue, sortBands, taxFor, validateBands, amount,
} from "@pb_blueprint/js/tax_math";

// BP28 — a unit test has no server to fetch translations from, and reading a
// `_t()` label throws until the runner is told they are loaded. English is the
// source language, so "loaded with nothing" is exactly right.
beforeEach(() => {
    translatedTerms[translationLoaded] = true;
});

const s = (v) => String(v);

/** The seven-band Vietnamese monthly schedule, in the order it is read. */
const VN = [
    { lower: 0, rate: 0.05 },
    { lower: 5000000, rate: 0.10 },
    { lower: 10000000, rate: 0.15 },
    { lower: 18000000, rate: 0.20 },
    { lower: 32000000, rate: 0.25 },
    { lower: 52000000, rate: 0.30 },
    { lower: 80000000, rate: 0.35 },
];

describe("the tax a set of bands gives", () => {
    test("three incomes worked out by hand", () => {
        // 5,000,000 x 5% = 250,000.
        expect(taxFor(VN, 5000000)).toBe(250000);
        // 250,000 + 5,000,000 x 10% = 750,000.
        expect(taxFor(VN, 10000000)).toBe(750000);
        // 750,000 + 8,000,000 x 15% = 1,950,000.
        expect(taxFor(VN, 18000000)).toBe(1950000);
    });

    test("a band edge and the dong either side of it", () => {
        expect(taxFor(VN, 4999000)).toBe(249950);
        expect(taxFor(VN, 5001000)).toBe(250100);
    });

    test("the top band has no upper limit", () => {
        // 18,150,000 fills every band below 80m; then 20m at 35%.
        expect(taxFor(VN, 100000000)).toBe(18150000 + 7000000);
    });

    test("no income, no tax, and never a negative one", () => {
        expect(taxFor(VN, 0)).toBe(0);
        expect(taxFor(VN, -1000)).toBe(0);
        expect(taxFor([], 50000000)).toBe(0);
    });

    test("the effective rate is the tax over the income", () => {
        expect(Math.round(effectiveRate(VN, 40000000) * 10000) / 100).toBe(13.63);
        expect(effectiveRate(VN, 0)).toBe(0);
    });

    test("the bands are read lowest first however they arrive", () => {
        const shuffled = [VN[3], VN[0], VN[2], VN[1]];
        expect(sortBands(shuffled).map((b) => b.lower))
            .toEqual([0, 5000000, 10000000, 18000000]);
        expect(taxFor(shuffled, 10000000)).toBe(750000);
    });
});

describe("the upper bound nobody has to type", () => {
    test("each band ends where the next one starts", () => {
        const rows = bandRows(VN);
        expect(rows[0].upper).toBe(5000000);
        expect(rows[1].lower).toBe(5000000);
        expect(rows[2].upper).toBe(18000000);
    });

    test("the last band has no upper bound at all", () => {
        const rows = bandRows(VN);
        expect(rows[rows.length - 1].upper).toBe(null);
        expect(rows[rows.length - 1].last).toBe(true);
    });

    test("an overlap cannot be expressed, because there is one number", () => {
        // Move a band's start and the band below it follows automatically:
        // there is no second number that could disagree.
        const moved = VN.map((b, i) => (i === 2 ? { ...b, lower: 12000000 } : b));
        const rows = bandRows(moved);
        expect(rows[1].upper).toBe(12000000);
        expect(rows[2].lower).toBe(12000000);
        for (let i = 0; i + 1 < rows.length; i++) {
            expect(rows[i].upper).toBe(rows[i + 1].lower);
        }
    });

    test("a band reads as a range, and the top one as an open end", () => {
        const rows = bandRows(VN);
        expect(s(bandRange(rows[0]))).toBe("0 – 5,000,000");
        expect(s(bandRange(rows[6]))).toInclude("80,000,000");
    });
});

describe("what the server would refuse", () => {
    test("a coherent schedule is accepted", () => {
        expect(validateBands(VN)).toBe("");
    });

    test("two bands starting at the same amount", () => {
        const bad = [{ lower: 0, rate: 0.05 }, { lower: 0, rate: 0.1 }];
        expect(s(validateBands(bad))).toInclude("same amount");
    });

    test("a rate outside nought to a hundred", () => {
        expect(s(validateBands([{ lower: 0, rate: 1.5 }])))
            .toInclude("between 0 and 100");
    });

    test("a first band that does not start at zero", () => {
        expect(s(validateBands([{ lower: 1000000, rate: 0.05 }])))
            .toInclude("start at zero");
    });

    test("no bands at all", () => {
        expect(s(validateBands([]))).toInclude("at least one band");
    });
});

describe("numbers as people type and read them", () => {
    test("a percentage round-trips without a floating-point tail", () => {
        expect(percentFromRate(0.075)).toBe(7.5);
        expect(rateFromPercent("7.5")).toBe(0.075);
        expect(rateFromPercent("21.5%")).toBe(0.215);
        expect(rateFromPercent("nonsense")).toBe(null);
    });

    test("commas and spaces are theirs, not ours", () => {
        expect(amount("46,800,000")).toBe(46800000);
        expect(amount(" 1 500 ")).toBe(1500);
        expect(amount("")).toBe(null);
        expect(amount("twelve")).toBe(null);
    });

    test("money is grouped and a rate is shown as a percentage", () => {
        expect(group(46800000)).toBe("46,800,000");
        expect(showValue(0.08, "percentage")).toBe("8%");
        expect(showValue(15500000, "currency")).toBe("15,500,000");
    });
});
