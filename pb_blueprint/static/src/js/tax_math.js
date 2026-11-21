/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

/**
 * Tax bands, as arithmetic — and nothing else.
 *
 * No components, no services, no server. The point of a "try an income" slider
 * is that the answer appears as the handle moves, which means the sum has to
 * happen in the browser; the point of putting it HERE is that the same sum can
 * be checked against a figure somebody worked out on paper, in a millisecond.
 *
 * It is deliberately the same piecewise arithmetic the server compiles into
 * every payslip (`compile_brackets_excel`): each band charges its own rate on
 * the slice of income inside it, and the bands below it are already paid for.
 */

/** Bands in the order they apply, lowest start first. */
export function sortBands(bands) {
    return [...(bands || [])].sort((a, b) => Number(a.lower) - Number(b.lower));
}

/**
 * The table as it is READ: each row gains the upper bound of its band, which
 * is simply where the next band starts. Deriving it is what makes an overlap
 * impossible — there is no second number to get wrong.
 */
export function bandRows(bands) {
    const sorted = sortBands(bands);
    return sorted.map((band, index) => ({
        index,
        lower: Number(band.lower) || 0,
        rate: Number(band.rate) || 0,
        upper: index + 1 < sorted.length ? Number(sorted[index + 1].lower) : null,
        last: index + 1 === sorted.length,
    }));
}

/** The tax on one income, worked out band by band. */
export function taxFor(bands, income) {
    const rows = bandRows(bands);
    const value = Number(income) || 0;
    if (!rows.length || value <= 0) {
        return 0;
    }
    let total = 0;
    for (const row of rows) {
        if (value <= row.lower) {
            break;
        }
        const top = row.upper === null ? value : Math.min(value, row.upper);
        total += (top - row.lower) * row.rate;
    }
    return Math.max(0, total);
}

/** Tax as a share of the income it was worked out on, 0 when there is none. */
export function effectiveRate(bands, income) {
    const value = Number(income) || 0;
    if (value <= 0) {
        return 0;
    }
    return taxFor(bands, value) / value;
}

/**
 * Why this set of bands cannot be saved, in one sentence — or "".
 *
 * The same three answers the server gives, so the button greys out for the
 * reason the server would have given anyway. The server still decides.
 */
export function validateBands(bands) {
    const rows = sortBands(bands);
    if (!rows.length) {
        return _t("A tax table needs at least one band.");
    }
    for (const band of rows) {
        const rate = Number(band.rate);
        if (!Number.isFinite(rate) || rate < 0 || rate > 1) {
            return _t("A rate is a percentage between 0 and 100.");
        }
        const lower = Number(band.lower);
        if (!Number.isFinite(lower) || lower < 0) {
            return _t("A band cannot start below zero.");
        }
    }
    const seen = new Set();
    for (const band of rows) {
        const lower = Number(band.lower);
        if (seen.has(lower)) {
            return _t("Two bands start at the same amount.");
        }
        seen.add(lower);
    }
    if (Number(rows[0].lower) !== 0) {
        return _t("The first band has to start at zero, or income below it would not be taxed at all.");
    }
    return "";
}

/** "0 to 5,000,000" / "80,000,000 and above" — the band, in words. */
export function bandRange(row, formatter) {
    const fmt = formatter || ((n) => Number(n).toLocaleString("en-US"));
    if (row.last) {
        return _t("%s and above", fmt(row.lower));
    }
    return `${fmt(row.lower)} – ${fmt(row.upper)}`;
}

/** A percentage a person types, as the fraction the server stores. */
export function rateFromPercent(text) {
    const n = Number(String(text === undefined ? "" : text).replace(/[\s,%]/g, ""));
    return Number.isFinite(n) ? n / 100 : null;
}

/** And back again, without the floating-point tail. */
export function percentFromRate(rate) {
    return Math.round((Number(rate) || 0) * 1000000) / 10000;
}

/** A number a person typed, or null. Commas and spaces are theirs, not ours. */
export function amount(text) {
    if (text === "" || text === null || text === undefined) {
        return null;
    }
    const n = Number(String(text).replace(/[\s,]/g, ""));
    return Number.isFinite(n) ? n : null;
}

/** 46,800,000 — grouped, never in scientific notation. */
export function group(value, decimals = 0) {
    return Number(value || 0).toLocaleString("en-US", {
        maximumFractionDigits: decimals,
        minimumFractionDigits: 0,
    });
}

/** How one statutory value is shown: money grouped, a rate as a percentage. */
export function showValue(value, format) {
    if (format === "percentage") {
        return `${percentFromRate(value)}%`;
    }
    if (format === "integer" || format === "number") {
        return group(value, 2);
    }
    return group(value);
}
