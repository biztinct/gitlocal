/** @odoo-module **/
/**
 * How a number is said out loud in the Decision Room.
 *
 * One rule runs through the whole screen: **never more than three significant
 * digits on a tile**. A CEO reading "₫1.25B" takes it in at a glance; the same
 * number written out is a wall of digits nobody compares. The full figure is
 * still there, in the `title` of whatever shows the short one.
 *
 * Two shapes, decided by the company's own currency:
 *   * a currency with no decimal places (₫, ¥, ₩) reads ₫1.25B / ₫840M /
 *     ₫12.5M / ₫950k;
 *   * a currency with decimals ($, €, S$) reads $1.25m / $840k / $1,250.
 *
 * The symbol LEADS in the short form whichever side the company writes it,
 * because a compacted number and a trailing symbol read as two things. The
 * long form (`exact`) honours the company's own side.
 *
 * NOTE FOR THE NODE CHECKS: this file imports nothing, and the module marker
 * on line 1 is only a comment — so `tools/decision_engine_check.mjs` loads this
 * file, and the engine beside it, exactly as they ship.
 */

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_LONG = ["January", "February", "March", "April", "May", "June",
                     "July", "August", "September", "October", "November",
                     "December"];

const MINUS = "−";     // a real minus sign, not a hyphen

export const monthShort = (i) => MONTHS[((i % 12) + 12) % 12];
export const monthLong = (i) => MONTHS_LONG[((i % 12) + 12) % 12];
export { MONTHS, MONTHS_LONG };

function group(n, digits = 0) {
    return n.toLocaleString("en-US", {
        minimumFractionDigits: digits, maximumFractionDigits: digits,
    });
}

/**
 * Three significant digits, with no decoration: 1.25 / 1.4 / 12.5 / 125.
 * A trailing zero is dropped, because "1.40" reads as a precision the number
 * has not got and costs a character on a tile that has none to spare.
 */
function three(n) {
    if (n >= 100) { return group(Math.round(n)); }
    const text = group(n, n >= 10 ? 1 : 2);
    return text.includes(".")
        ? text.replace(/0+$/, "").replace(/\.$/, "") : text;
}

/**
 * Build the whole formatter set for one company's currency.
 * @param {{symbol:string, position:string, decimals:number, code:string}} cur
 */
export function makeFormat(cur) {
    const currency = cur || {};
    const symbol = currency.symbol || "";
    const decimals = Number(currency.decimals) || 0;
    const after = currency.position === "after";
    const whole = decimals === 0;
    // [when to switch, what to divide by, what to call it]. A currency with
    // no decimal places counts in millions and billions because that is how
    // its speakers say it out loud; a decimal one does not reach for "m"
    // until a million, and never abbreviates a four-figure sum.
    const SCALES = whole
        ? [[1e9, 1e9, "B"], [1e6, 1e6, "M"], [1e3, 1e3, "k"]]
        : [[1e6, 1e6, "m"], [1e4, 1e3, "k"]];

    /** The short form. Always the one on a tile. */
    function money(value, opts = {}) {
        const v = Number(value) || 0;
        const sign = v < 0 ? MINUS : (opts.plus && v > 0 ? "+" : "");
        const a = Math.abs(v);
        for (const [from, size, suffix] of SCALES) {
            if (a >= from) {
                return `${sign}${symbol}${three(a / size)}${suffix}`;
            }
        }
        return `${sign}${symbol}${group(Math.round(a))}`;
    }

    /** The whole figure, on the side this company writes its symbol. */
    function exact(value) {
        const v = Number(value) || 0;
        const sign = v < 0 ? MINUS : "";
        const body = group(Math.abs(v), decimals);
        return after ? `${sign}${body} ${symbol}` : `${sign}${symbol}${body}`;
    }

    /** A change in money, always signed, "no change" said in words. */
    function signedMoney(value) {
        const v = Number(value) || 0;
        if (Math.abs(v) < 1) { return `${symbol}0`; }
        return money(v, { plus: true });
    }

    function pct(value, digits = 1) {
        const v = Number(value) || 0;
        return `${v < 0 ? MINUS : ""}${Math.abs(v).toFixed(digits)}%`;
    }

    /** A change measured in percentage points. */
    function pp(value, digits = 1) {
        const v = Number(value) || 0;
        if (Math.abs(v) < 0.05) { return "0.0 pp"; }
        return `${v < 0 ? MINUS : "+"}${Math.abs(v).toFixed(digits)} pp`;
    }

    function int(value, opts = {}) {
        const v = Math.round(Number(value) || 0);
        const sign = v < 0 ? MINUS : (opts.plus && v > 0 ? "+" : "");
        return `${sign}${group(Math.abs(v))}`;
    }

    /** "+24 people" / "no change". */
    function people(value) {
        const v = Math.round(Number(value) || 0);
        if (!v) { return "0 people"; }
        return `${int(v, { plus: true })} ${Math.abs(v) === 1 ? "person" : "people"}`;
    }

    return { money, exact, signedMoney, pct, pp, int, people, symbol,
             decimals, code: currency.code || "" };
}

/** Never trust a name into markup. */
export function esc(value) {
    return String(value === undefined || value === null ? "" : value)
        .replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;",
            '"': "&quot;", "'": "&#39;",
        }[c]));
}

export { MINUS };
