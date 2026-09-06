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
 * AND A THIRD SHAPE, when the person reading is Vietnamese. Vietnamese
 * finance does not say "B": it says **tỷ**, **triệu**, **nghìn**, and it
 * writes ₫2.200 tỷ where English writes ₫2,200B — the separators are the
 * other way round. A room that shows a Vietnamese CEO "₫2,200B" is a room
 * that made them do arithmetic before they could read their own plan.
 *
 * The symbol LEADS in the short form whichever side the company writes it,
 * because a compacted number and a trailing symbol read as two things. The
 * long form (`exact`) honours the company's own side.
 *
 * NOTE FOR THE NODE CHECKS: this file imports nothing, and the module marker
 * on line 1 is only a comment — so `tools/decision_engine_check.mjs` loads this
 * file, and the engine beside it, exactly as they ship. The translator is
 * INJECTED (`useTranslator`) rather than imported, for the same reason: the
 * `_t()` calls below are still found by the string extractor, and node still
 * gets plain English.
 */

/**
 * The room's translator.
 *
 * Replaced at load time by `decision_room.js` with the platform's own `_t`.
 * The fallback is not a stub: it interpolates, so every sentence in this file
 * and in the engine reads correctly under `node` with no Odoo present.
 */
let _t = (text, params) => interpolate(text, params);

export function interpolate(text, params) {
    const raw = String(text === undefined || text === null ? "" : text);
    if (params === undefined || params === null) { return raw; }
    // The platform's own two rules, mirrored exactly, so a sentence reads the
    // same under `node` as it does on screen: with a dictionary only
    // `%(key)s` is replaced and `%%` is left alone; with a single value `%s`
    // is replaced and `%%` becomes one per cent sign.
    if (typeof params === "object" && !Array.isArray(params)) {
        return raw.replace(/%\(([^)]+)\)s/g,
            (hit, key) => (key in params ? String(params[key]) : ""));
    }
    let out = "";
    for (let i = 0; i < raw.length; i++) {
        if (raw[i] === "%" && raw[i + 1] === "%") { out += "%"; i++; continue; }
        if (raw[i] === "%" && raw[i + 1] === "s") {
            out += String(params); i++; continue;
        }
        out += raw[i];
    }
    return out;
}

export function useTranslator(fn) {
    if (typeof fn === "function") { _t = fn; }
}

const MONTHS_SHORT_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const MINUS = "−";     // a real minus sign, not a hyphen

const wrap = (i) => ((i % 12) + 12) % 12;

/** The twelve months, in the reader's language, built on every call. */
export function monthShort(i) {
    return [_t("Jan"), _t("Feb"), _t("Mar"), _t("Apr"), _t("May"), _t("Jun"),
            _t("Jul"), _t("Aug"), _t("Sep"), _t("Oct"), _t("Nov"),
            _t("Dec")][wrap(i)];
}

export function monthLong(i) {
    return [_t("January"), _t("February"), _t("March"), _t("April"),
            _t("May"), _t("June"), _t("July"), _t("August"),
            _t("September"), _t("October"), _t("November"),
            _t("December")][wrap(i)];
}

/** Twelve of anything, for a loop that only needs a length and a stable key. */
export const MONTHS = MONTHS_SHORT_EN;

/** Is this reader Vietnamese? The only question the formatter asks of `lang`. */
export function isVietnamese(lang) {
    return String(lang || "").toLowerCase().startsWith("vi");
}

/**
 * Grouped digits, with the separators this language actually writes.
 *
 * Done by hand rather than through `toLocaleString`, because the answer has to
 * be identical in a browser, in a headless test and under `node` with a
 * cut-down ICU — and a money figure that changes shape between them is a
 * money figure nobody can test.
 */
function group(n, digits = 0, sep = ",", dec = ".") {
    const value = Number(n) || 0;
    const fixed = Math.abs(value).toFixed(digits);
    const parts = fixed.split(".");
    const whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, sep);
    return (value < 0 ? MINUS : "") + whole
        + (parts[1] ? dec + parts[1] : "");
}

/**
 * Three significant digits, with no decoration: 1.25 / 1.4 / 12.5 / 125.
 * A trailing zero is dropped, because "1.40" reads as a precision the number
 * has not got and costs a character on a tile that has none to spare.
 */
function three(n, sep, dec) {
    if (n >= 100) { return group(Math.round(n), 0, sep, dec); }
    const text = group(n, n >= 10 ? 1 : 2, sep, dec);
    if (!text.includes(dec)) { return text; }
    return text.replace(/0+$/, "").replace(new RegExp(`\\${dec}$`), "");
}

/** k / m / b / t, in the units a person actually types. */
const SUFFIX = { k: 1e3, m: 1e6, b: 1e9, t: 1e12 };

/** The same, in the words Vietnamese finance uses out loud. */
const SUFFIX_VI = { nghin: 1e3, trieu: 1e6, ty: 1e9 };

/** "tỷ" and "tỉ" and "trieu" are one word once the marks come off. */
function fold(text) {
    return String(text)
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/đ/g, "d").replace(/Đ/g, "D")
        .toLowerCase();
}

/**
 * Read a money box the way a person writes one.
 *
 * Nobody types ₫2,200,000,000,000 and nobody reads it back. So the box shows
 * "₫2,200B" — or "₫2.200 tỷ" — and accepts every shape of the same thing:
 * `2200000000000`, `2,200 B`, `2.2 t`, `2200b`, `1.5m`, `2.200 tỷ`,
 * `840 trieu`, `2,2 tỷ`, with or without the company's own currency symbol
 * and with either kind of minus sign.
 *
 * Returns `null` — never 0, and never NaN — when the text is not a number at
 * all, so the caller can KEEP THE OLD VALUE rather than silently zero a
 * revenue target because somebody's cat sat on the keyboard.
 *
 * @param {string} text    what is in the box
 * @param {string} symbol  the company's currency symbol, if it has one
 * @param {string} lang    the reader's language, so "." can be told from ","
 * @returns {number|null}
 */
export function parseCompact(text, symbol = "", lang = "") {
    let raw = String(text === undefined || text === null ? "" : text).trim();
    if (!raw) { return null; }
    if (symbol) { raw = raw.split(symbol).join(""); }
    raw = fold(raw)
        .replace(/−/g, "-")     // a real minus sign
        .replace(/[\s ']/g, "");
    // The unit word first, because it is what decides how the digits in front
    // of it are punctuated.
    const hit = /^([+-]?)([\d.,]+)(nghin|trieu|ty|k|m|b|t)?$/.exec(raw);
    if (!hit) { return null; }
    const word = hit[3] || "";
    const vietnameseWord = word in SUFFIX_VI;
    // A Vietnamese unit word settles it whatever the interface language is;
    // otherwise the reader's own language decides which mark is the decimal.
    const viStyle = vietnameseWord || (isVietnamese(lang) && !word)
        || (isVietnamese(lang) && !(word in SUFFIX));
    let digits = hit[2];
    if (viStyle) {
        digits = digits.replace(/\./g, "").replace(/,/g, ".");
    } else {
        digits = digits.replace(/,/g, "");
    }
    if (!/^\d+(\.\d+)?$/.test(digits)) { return null; }
    const scale = vietnameseWord ? SUFFIX_VI[word]
        : (word ? SUFFIX[word] : 1);
    if (word && scale === undefined) { return null; }
    const value = Number(digits) * (scale || 1);
    if (!Number.isFinite(value)) { return null; }
    return hit[1] === "-" ? -value : value;
}

/**
 * Build the whole formatter set for one company's currency, in one language.
 *
 * @param {{symbol:string, position:string, decimals:number, code:string}} cur
 * @param {string} lang  the reader's language code, e.g. "vi_VN"
 */
export function makeFormat(cur, lang = "") {
    const currency = cur || {};
    const symbol = currency.symbol || "";
    const decimals = Number(currency.decimals) || 0;
    const after = currency.position === "after";
    const whole = decimals === 0;
    const vi = isVietnamese(lang);
    const sep = vi ? "." : ",";
    const dec = vi ? "," : ".";
    // [when to switch, what to divide by, what to call it, what to put
    // between the number and the word]. A currency with no decimal places
    // counts in millions and billions because that is how its speakers say it
    // out loud; a decimal one does not reach for "m" until a million, and
    // never abbreviates a four-figure sum. Vietnamese says the word in full,
    // with a space, because "2.200tỷ" is not how anybody writes it.
    const SCALES = vi && whole
        ? [[1e9, 1e9, "tỷ", " "], [1e6, 1e6, "triệu", " "],
           [1e3, 1e3, "nghìn", " "]]
        : (whole
            ? [[1e9, 1e9, "B", ""], [1e6, 1e6, "M", ""], [1e3, 1e3, "k", ""]]
            : [[1e6, 1e6, "m", ""], [1e4, 1e3, "k", ""]]);

    /** The short form. Always the one on a tile. */
    function money(value, opts = {}) {
        const v = Number(value) || 0;
        const sign = v < 0 ? MINUS : (opts.plus && v > 0 ? "+" : "");
        const a = Math.abs(v);
        for (const [from, size, suffix, gap] of SCALES) {
            if (a >= from) {
                return `${sign}${symbol}${three(a / size, sep, dec)}`
                    + `${gap}${suffix}`;
            }
        }
        return `${sign}${symbol}${group(Math.round(a), 0, sep, dec)}`;
    }

    /** The whole figure, on the side this company writes its symbol. */
    function exact(value) {
        const v = Number(value) || 0;
        const sign = v < 0 ? MINUS : "";
        const body = group(Math.abs(v), decimals, sep, dec);
        return after ? `${sign}${body} ${symbol}` : `${sign}${symbol}${body}`;
    }

    /** A change in money, always signed, "no change" said in words. */
    function signedMoney(value) {
        const v = Number(value) || 0;
        if (Math.abs(v) < 1) { return `${symbol}0`; }
        return money(v, { plus: true });
    }

    function fixed(value, digits) {
        return group(value, digits, sep, dec);
    }

    function pct(value, digits = 1) {
        const v = Number(value) || 0;
        return `${v < 0 ? MINUS : ""}${fixed(Math.abs(v), digits)}%`;
    }

    /**
     * A change measured in percentage points.
     *
     * "pp" is an English abbreviation, and a Vietnamese reader has no reason
     * to know it — so the unit is a translated term like every other word on
     * the screen, and the number in front of it keeps this language's marks.
     */
    function pp(value, digits = 1) {
        const v = Number(value) || 0;
        if (Math.abs(v) < 0.05) {
            return _t("%(value)s pp", { value: `0${dec}0` });
        }
        const body = `${v < 0 ? MINUS : "+"}${fixed(Math.abs(v), digits)}`;
        return _t("%(value)s pp", { value: body });
    }

    function int(value, opts = {}) {
        const v = Math.round(Number(value) || 0);
        const sign = v < 0 ? MINUS : (opts.plus && v > 0 ? "+" : "");
        return `${sign}${group(Math.abs(v), 0, sep, dec)}`;
    }

    /** "+24 people" / "no change". */
    function people(value) {
        const v = Math.round(Number(value) || 0);
        if (!v) { return _t("0 people"); }
        const n = int(v, { plus: true });
        return Math.abs(v) === 1
            ? _t("%(n)s person", { n }) : _t("%(n)s people", { n });
    }

    /**
     * The step one arrow press moves, in the unit the box is SHOWING.
     *
     * Pressing up on "₫2,200B" should give "₫2,201B" and not
     * "₫2,200.000001B" — the increment has to be the unit under the cursor,
     * which is the scale the value is displayed at and not a fixed number.
     */
    function step(value) {
        const a = Math.abs(Number(value) || 0);
        for (const [from, size] of SCALES) {
            if (a >= from) { return size; }
        }
        return whole ? 1000 : 1;
    }

    return { money, compact: money, exact, signedMoney, pct, pp, int, people,
             step, fixed, parse: (text) => parseCompact(text, symbol, lang),
             symbol, decimals, lang, vi, code: currency.code || "" };
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
