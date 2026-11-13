/** @odoo-module **/

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { translatedTerms, translationLoaded } from "@web/core/l10n/translation";

import { cutoffValue, identityRows, paydayValue }
    from "@pb_blueprint/js/finish_text";

// BP28 / BP37 — a unit test has no server to fetch translations from, and a
// `_t()` label is a String OBJECT whose `valueOf()` refuses to answer until the
// runner is told they are loaded.
translatedTerms[translationLoaded] = true;
beforeEach(() => {
    translatedTerms[translationLoaded] = true;
});

const s = (v) => String(v);

describe("the review page — how the cut-off reads", () => {
    test("each rule reads as the promise it is, not as a number", () => {
        expect(s(cutoffValue({
            cutoff_rule: "fixed", cutoff_rule_label: "A fixed day of the month",
            cutoff_day: 20,
        }))).toBe("A fixed day of the month — day 20");

        expect(s(cutoffValue({
            cutoff_rule: "last_working",
            cutoff_rule_label: "The last working day of the month",
        }))).toBe("The last working day of the month");

        expect(s(cutoffValue({
            cutoff_rule: "before_payday",
            cutoff_rule_label: "A set number of working days before payday",
            cutoff_days_before: 3,
        }))).toBe("3 working days before payday");
    });

    test("one day before payday is not \"1 days\"", () => {
        expect(s(cutoffValue({
            cutoff_rule: "before_payday",
            cutoff_rule_label: "A set number of working days before payday",
            cutoff_days_before: 1,
        }))).toBe("1 working day before payday");
    });

    test("a configuration saved before the rule existed still reads right", () => {
        // No rule and no label — only the day it has always carried. Printing
        // nothing there would make the upgrade look like it lost the setting.
        expect(s(cutoffValue({ cutoff_day: 20 }))).toBe("Day 20 of the month");
        expect(s(cutoffValue({}))).toBe("");
    });

    test("the cut-off row is on the review page and is never empty-labelled", () => {
        const rows = identityRows({
            name: "Rize Vietnam",
            calendar: { cutoff_rule: "last_working",
                        cutoff_rule_label: "The last working day of the month",
                        payday_rule: "last_working",
                        payday_rule_label: "The last working day of the month" },
        });
        const cutoff = rows.find((r) => r.key === "cutoff");
        expect(cutoff).toBeTruthy();
        expect(s(cutoff.value)).toBe("The last working day of the month");
        // Every row that survives the filter has something to show.
        for (const row of rows) {
            expect(s(row.value)).not.toBe("");
        }
    });

    test("the cut-off and the payday read as the same kind of sentence", () => {
        const cal = {
            cutoff_rule: "fixed", cutoff_rule_label: "A fixed day of the month",
            cutoff_day: 20,
            payday_rule: "fixed", payday_rule_label: "A fixed day of the month",
            payday_day: 25,
        };
        expect(s(cutoffValue(cal))).toBe("A fixed day of the month — day 20");
        expect(s(paydayValue(cal))).toBe("A fixed day of the month — day 25");
    });
});
