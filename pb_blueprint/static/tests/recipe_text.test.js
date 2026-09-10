/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";

import {
    GROUP_TABS, RULE_TABS, summaryOf, treatmentChips, codeFromName,
    codeIsValid, codeProblem, healthWord, detailFor, num, cloneRecipe,
    sameRecipe, kindLabel, taxLabel, prorationLabel, frequencyLabel,
    groupLabel,
} from "@pb_blueprint/js/recipe_text";

// `_t()` returns a lazily translated object, so every assertion about a LABEL
// goes through String() — `===` on the object fails for a reason that has
// nothing to do with the words.
const s = (v) => String(v);

const recipe = (over = {}) => ({
    v: 1,
    group: "earning",
    audience: "all",
    amount: { kind: "contract" },
    proration: "none",
    frequency: "monthly",
    sign: 1,
    round: "0",
    treatment: { cash: "cash", tax: "taxable", insurance: "excluded" },
    ...over,
});

describe("guided setup — the words on a pay rule", () => {
    test("five groups and three tabs, each with real words", () => {
        expect(GROUP_TABS.map((g) => g.key)).toEqual([
            "earning", "deduction", "benefit", "helper", "total"]);
        expect(RULE_TABS.map((t) => t.key)).toEqual([
            "components", "tax", "calendar"]);
        for (const row of [...GROUP_TABS, ...RULE_TABS]) {
            expect(s(row.label)).not.toBe("");
        }
        expect(s(groupLabel("benefit"))).toBe("Benefits & employer costs");
    });

    test("summaryOf reads like a sentence, for six different rules", () => {
        expect(s(summaryOf(recipe({ proration: "working_days" }))))
            .toBe("Contract salary · Prorated by working days · Taxable");

        expect(s(summaryOf(recipe({
            amount: { kind: "fixed", value: 500000 },
            treatment: { cash: "cash", tax: "exempt", insurance: "excluded" },
        })))).toBe("A fixed amount · Tax free");

        expect(s(summaryOf(recipe({
            amount: { kind: "hourly", rate_pct: 150 },
            treatment: { cash: "cash", tax: "qualified", insurance: "excluded" },
        })))).toBe("Hours at an hourly rate · Tax free with evidence");

        expect(s(summaryOf(recipe({
            group: "deduction",
            amount: { kind: "percent_of", base: "SIBASE", rate_code: "SIRATE" },
            treatment: { tax: "exempt" },
        })))).toBe("A share of another component");

        expect(s(summaryOf(recipe({
            amount: { kind: "annual_ratio", payout_month: 1 },
            frequency: "annual",
        })))).toBe("A yearly payment, by service · Taxable · Paid once a year");

        expect(s(summaryOf(recipe({ group: "total", amount: { kind: "net_total" } }))))
            .toBe("Take-home pay");

        // No rule at all is a state with words, never a blank line.
        expect(s(summaryOf(null))).toBe("Nothing is worked out yet");
    });

    test("the disclosure chips say tax, cash and anything unusual", () => {
        const chips = treatmentChips(recipe()).map(s);
        expect(chips).toEqual(["Taxable", "Paid in cash"]);

        const review = treatmentChips(recipe({
            treatment: { cash: "noncash", tax: "exempt", insurance: "review",
                         tax_bearer: "employer" },
        })).map(s);
        expect(review).toEqual([
            "Tax free", "A benefit, not cash", "Insurance still to be decided",
            "The employer pays the tax"]);
    });

    test("a code comes from the name, folded and capped at twelve", () => {
        expect(codeFromName("Site allowance")).toBe("SITEALLOWANC");
        expect(codeFromName("Uniform")).toBe("UNIFORM");
        expect(codeFromName("13th month")).toBe("THMONTH");
        // Vietnamese accents are FOLDED, never deleted: deleting them is how a
        // real component code became three characters of nonsense.
        expect(codeFromName("Phụ cấp")).toBe("PHUCAP");
        expect(codeFromName("Chi trả phép năm")).toBe("CHITRAPHEPNA");
        expect(codeFromName("")).toBe("");
    });

    test("codeIsValid and codeProblem agree, and say why", () => {
        expect(codeIsValid("SITEALLOW")).toBe(true);
        expect(codeIsValid("AB")).toBe(false);
        expect(codeIsValid("1ABC")).toBe(false);
        expect(s(codeProblem("SITEALLOW", []))).toBe("");
        expect(s(codeProblem("", []))).toBe("Give the component a short code.");
        expect(s(codeProblem("AB", []))).toBe("A code needs at least three characters.");
        expect(s(codeProblem("BASIC", ["BASIC"])))
            .toBe("Another component already uses that code.");
        // Every refusal is a sentence, never a pattern.
        for (const bad of ["", "AB", "1ABC", "ABCDEFGHIJKLM"]) {
            expect(s(codeProblem(bad, [])).endsWith(".")).toBe(true);
        }
    });

    test("the health dot has a word for every state", () => {
        expect(s(healthWord("ok"))).toBe("OK");
        expect(s(healthWord("review"))).toBe("Needs a decision");
        expect(s(healthWord("problem"))).toBe("Problem");
        expect(s(healthWord("something else"))).toBe("OK");
    });

    test("each amount asks for exactly the details it needs", () => {
        expect(detailFor("contract")).toEqual([]);
        expect(detailFor("fixed")).toEqual(["value"]);
        expect(detailFor("percent_of")).toEqual(["base", "percent"]);
        expect(detailFor("bracket")).toEqual(["table", "base"]);
        expect(detailFor("role")).toEqual(["grades"]);
    });

    test("numbers survive commas and refuse nonsense", () => {
        expect(num("2,000,000")).toBe(2000000);
        expect(num("")).toBe(null);
        expect(num("twelve")).toBe(null);
        expect(num(0)).toBe(0);
    });

    test("editing a copy never touches the stored rule", () => {
        const original = recipe();
        const copy = cloneRecipe(original);
        copy.amount.kind = "fixed";
        expect(original.amount.kind).toBe("contract");
        expect(sameRecipe(original, cloneRecipe(original))).toBe(true);
        expect(sameRecipe(original, copy)).toBe(false);
    });

    test("no option label leaks a code word", () => {
        const words = [];
        for (const kind of ["input", "fixed", "contract", "percent_contract",
                            "percent_of", "role", "hourly", "annual_ratio",
                            "linked", "sum_group", "bracket", "insurance_base",
                            "taxable_base", "net_total", "employer_total"]) {
            words.push(s(kindLabel(kind)));
        }
        for (const value of ["taxable", "exempt", "qualified", "annual_cap",
                             "entitlement", "inherit"]) {
            words.push(s(taxLabel(value)));
        }
        for (const value of ["none", "working_days", "calendar_days"]) {
            words.push(s(prorationLabel(value)));
        }
        for (const value of ["monthly", "annual", "adhoc", "scheme"]) {
            words.push(s(frequencyLabel(value)));
        }
        const banned = /\b(odoo|schema|schemas|blueprint|blueprints|config|configs|rule set|recipe|json|excel_formula|column_letter)\b/i;
        for (const word of words) {
            expect(word).not.toBe("");
            expect(banned.test(word)).toBe(false);
            // Never an identifier: a label a person reads has spaces or is one
            // ordinary word, and never an underscore.
            expect(word.includes("_")).toBe(false);
        }
    });
});
