/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * The sentence, in English — and nothing else.
 *
 * No components, no services, no server. Everything here turns a rule into
 * words a payroll manager can read, or turns what they typed into something
 * the server will accept. A hoot test can assert every one of them in a
 * millisecond, which is the point: the words are the product.
 */

/** The five group tabs, in the order they are read. */
export const GROUP_TABS = [
    { key: "earning", label: _t("Earnings") },
    { key: "deduction", label: _t("Deductions") },
    { key: "benefit", label: _t("Benefits & employer costs") },
    { key: "helper", label: _t("Inputs & fixed values") },
    { key: "total", label: _t("Totals") },
];

/** The three tabs of the Pay rules step. */
export const RULE_TABS = [
    { key: "components", label: _t("Components") },
    { key: "tax", label: _t("Tax & protection") },
    { key: "calendar", label: _t("Calendar & payment") },
];

/** What each amount is called, in one short phrase. */
export function kindLabel(kind) {
    return {
        input: _t("An approved amount"),
        fixed: _t("A fixed amount"),
        contract: _t("Contract salary"),
        percent_contract: _t("A share of contract salary"),
        percent_of: _t("A share of another component"),
        role: _t("An amount per grade"),
        hourly: _t("Hours at an hourly rate"),
        annual_ratio: _t("A yearly payment, by service"),
        linked: _t("The same as another component"),
        sum_group: _t("Everything in a group, added up"),
        bracket: _t("Worked out from the tax bands"),
        insurance_base: _t("Insurable pay, capped"),
        taxable_base: _t("Income the tax bands apply to"),
        net_total: _t("Take-home pay"),
        employer_total: _t("What the employer pays in total"),
        manual: _t("Written as Excel"),
    }[kind] || _t("An approved amount");
}

export function prorationLabel(value) {
    return {
        none: _t("nothing"),
        working_days: _t("paid working days"),
        calendar_days: _t("paid calendar days"),
    }[value] || _t("nothing");
}

export function taxLabel(value) {
    return {
        taxable: _t("Taxable"),
        exempt: _t("Tax free"),
        qualified: _t("Tax free with evidence"),
        annual_cap: _t("Tax free up to a yearly limit"),
        entitlement: _t("Tax free within the entitlement"),
        inherit: _t("Follows the original component"),
    }[value] || _t("Taxable");
}

export function insuranceLabel(value) {
    return {
        included: _t("In the insurance base"),
        excluded: _t("Not in the insurance base"),
        inherit: _t("Insurance follows the original"),
        review: _t("Insurance still to be decided"),
    }[value] || _t("Not in the insurance base");
}

export function frequencyLabel(value) {
    return {
        monthly: _t("Every pay run"),
        annual: _t("Paid once a year"),
        adhoc: _t("Paid when approved"),
        scheme: _t("Paid by scheme"),
    }[value] || _t("Every pay run");
}

export function cashLabel(value) {
    return value === "noncash" ? _t("A benefit, not cash") : _t("Paid in cash");
}

export function groupLabel(key) {
    const row = GROUP_TABS.find((g) => g.key === key);
    return row ? row.label : key;
}

/**
 * "Contract salary · Prorated by working days · Taxable" — the one line under
 * a component's name. Deliberately the same shape the server produces, so a
 * row looks identical whether it was just edited or just loaded.
 */
export function summaryOf(recipe) {
    if (!recipe || !recipe.amount) {
        return _t("Nothing is worked out yet");
    }
    const bits = [kindLabel(recipe.amount.kind)];
    if (recipe.proration === "working_days") {
        bits.push(_t("Prorated by working days"));
    } else if (recipe.proration === "calendar_days") {
        bits.push(_t("Prorated by calendar days"));
    }
    const treat = recipe.treatment || {};
    if (recipe.group === "earning" || recipe.group === "benefit") {
        bits.push(taxLabel(treat.tax));
    }
    if (recipe.frequency && recipe.frequency !== "monthly") {
        bits.push(frequencyLabel(recipe.frequency));
    }
    return bits.join(" · ");
}

/** The chips beside the "Tax, insurance & payout details" disclosure. */
export function treatmentChips(recipe) {
    const treat = (recipe && recipe.treatment) || {};
    const out = [taxLabel(treat.tax), cashLabel(treat.cash)];
    if (treat.insurance === "included" || treat.insurance === "review") {
        out.push(insuranceLabel(treat.insurance));
    }
    if (treat.tax_bearer === "employer") {
        out.push(_t("The employer pays the tax"));
    }
    return out;
}

/**
 * A code from a name: "Site allowance" -> "SITEALLOW".
 *
 * Capital letters and digits only, at most 12 characters, never starting with
 * a digit. Accents are folded rather than deleted — "Chi trả phép" losing its
 * accented letters is how a code turned into three characters of nonsense.
 * The server has the last word (it also checks uniqueness); this is what the
 * person watches appear as they type.
 */
export function codeFromName(name) {
    const folded = (name || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/Đ/g, "D")
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, "");
    const trimmed = folded.replace(/^[0-9]+/, "");
    return trimmed.slice(0, 12);
}

/** True when the server will accept this code without argument. */
export function codeIsValid(code) {
    return /^[A-Z][A-Z0-9]{2,11}$/.test(code || "");
}

/** The reason a code is refused, in words. Empty string when it is fine. */
export function codeProblem(code, taken) {
    const value = code || "";
    if (!value) {
        return _t("Give the component a short code.");
    }
    if (!/^[A-Z]/.test(value)) {
        return _t("A code has to start with a capital letter.");
    }
    if (!/^[A-Z0-9]+$/.test(value)) {
        return _t("A code can only use capital letters and digits.");
    }
    if (value.length < 3) {
        return _t("A code needs at least three characters.");
    }
    if (value.length > 12) {
        return _t("A code can be at most twelve characters.");
    }
    if ((taken || []).includes(value)) {
        return _t("Another component already uses that code.");
    }
    return "";
}

/** The dot beside a row: the word first, the reason second. */
export function healthWord(health) {
    return {
        ok: _t("OK"),
        review: _t("Needs a decision"),
        problem: _t("Problem"),
    }[health] || _t("OK");
}

/** Which detail controls the chosen amount needs. */
export function detailFor(kind) {
    return {
        fixed: ["value"],
        percent_contract: ["percent"],
        percent_of: ["base", "percent"],
        role: ["grades"],
        hourly: ["rate_pct"],
        annual_ratio: ["payout_month"],
        linked: ["link"],
        bracket: ["table", "base"],
        insurance_base: ["cap"],
        sum_group: ["of"],
    }[kind] || [];
}

/** A number the server will accept: finite, or null. */
export function num(raw) {
    if (raw === "" || raw === null || raw === undefined) {
        return null;
    }
    const n = Number(String(raw).replace(/[\s,]/g, ""));
    return Number.isFinite(n) ? n : null;
}

/** A deep-enough copy for editing a recipe without touching the stored one. */
export function cloneRecipe(recipe) {
    return JSON.parse(JSON.stringify(recipe || {}));
}

/** Two recipes, compared by value — the unsaved-changes guard. */
export function sameRecipe(a, b) {
    return JSON.stringify(a || null) === JSON.stringify(b || null);
}
