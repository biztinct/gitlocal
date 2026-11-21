/** @odoo-module **/
// WDGAP PR-A — the Studio flowchart calculator (parser + evaluator), moved out
// of formula_studio.js unchanged so it can be tested on its own, plus the date
// functions it was missing.
//
// The date part is a SMALL MIRROR of
// pb_hr_payroll_formula/formula_engine/excel_semantics.py (excel_date …
// excel_eomonth, excel_int, date_operand). The flowchart is a quick on-screen
// illustration of a formula — payslips are never worked out here — but it must
// not show a different number from the engine. The SAME cases
// (pb_hr_payroll_formula/tools/date_function_cases.json) run against this file
// in pb_formula_studio/tools/date_functions_battery.mjs and against the engine
// in excel_semantics_battery.py. Change one, run both.
//
// Chosen over routing the flowchart through the server: the flowchart shows a
// value on EVERY node of the tree, which a server round-trip per node (or a
// new per-node evaluation RPC) would make a much larger change.
//
// Dates are Excel serial numbers (1900 system; serial 60 is Excel's phantom
// 29 Feb 1900). Blank, unreadable or out-of-range dates answer 0; nothing here
// throws. Self-contained (no imports) so node can load it for the battery.

const DAY_MS = 86400000;
const SERIAL_MAX = 2958465; // 31 Dec 9999
const ISO_RE = /^\s*(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ][0-9:.]+)?\s*$/;

function utc(y, m, d) {
    // Date.UTC treats years 0..99 as 1900+; setUTCFullYear avoids that.
    const t = new Date(Date.UTC(2000, 0, 1));
    t.setUTCFullYear(y, m - 1, d);
    return t.getTime();
}
const BASE_EARLY = utc(1899, 12, 31);
const BASE = utc(1899, 12, 30);
const MARCH_1900 = utc(1900, 3, 1);

function num(v) {
    if (v === null || v === undefined || v === "" || v === false) return null;
    if (v === true) return 1;
    if (typeof v === "number") return isFinite(v) ? v : null;
    const s = String(v).trim().replace(/\s/g, "");
    if (!s) return null;
    const n = Number(s.endsWith("%") ? s.slice(0, -1) : s);
    if (!isFinite(n)) return null;
    return s.endsWith("%") ? n / 100 : n;
}

function whole(v) {
    const n = num(v);
    return n === null ? 0 : Math.trunc(n);
}

export function ymdToSerial(year, month, day) {
    let y = Math.trunc(year), m = Math.trunc(month), d = Math.trunc(day);
    if (y >= 0 && y < 1900) y += 1900;
    const m0 = m - 1;
    y += Math.floor(m0 / 12);
    const mm = ((m0 % 12) + 12) % 12 + 1;
    if (y < 1900 || y > 9999) return null;
    const first = utc(y, mm, 1);
    const firstSerial = first < MARCH_1900
        ? Math.round((first - BASE_EARLY) / DAY_MS)
        : Math.round((first - BASE) / DAY_MS);
    const serial = firstSerial + d - 1;
    if (serial < 0 || serial > SERIAL_MAX) return null;
    return serial;
}

export function serialToYmd(serial) {
    const s = Math.trunc(serial);
    if (s === 60) return [1900, 2, 29];
    const t = new Date((s < 60 ? BASE_EARLY : BASE) + s * DAY_MS);
    return [t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate()];
}

export function toSerial(v) {
    let serial;
    if (v === null || v === undefined || v === "" || v === false) return null;
    if (typeof v === "string" && ISO_RE.test(v)) {
        const [, y, m, d] = v.match(ISO_RE).map(Number);
        const real = new Date(utc(y, m, d));
        if (real.getUTCFullYear() !== y || real.getUTCMonth() + 1 !== m || real.getUTCDate() !== d) return null;
        serial = ymdToSerial(y, m, d);
    } else {
        const n = num(v);
        if (n === null) return null;
        serial = Math.floor(n);
    }
    if (serial === null || serial < 1 || serial > SERIAL_MAX) return null;
    return serial;
}

/** A reference inside a date function: a date text reads as its serial. */
export function dateOperand(v) {
    if (typeof v === "string" && ISO_RE.test(v)) {
        const s = toSerial(v);
        return s === null ? 0 : s;
    }
    const n = num(v);
    return n === null ? 0 : n;
}

function guard(fn) {
    return (...args) => {
        try {
            const r = fn(...args);
            return (r === null || r === undefined || Number.isNaN(r)) ? 0 : r;
        } catch {
            return 0;
        }
    };
}

function monthsBetween(sy, sm, sd, ey, em, ed) {
    let months = (ey - sy) * 12 + (em - sm);
    if (ed < sd) months -= 1;
    return months;
}

function addMonths(serial, months, endOfMonth) {
    const [y0, m0, d] = serialToYmd(serial);
    const total = m0 - 1 + months;
    const y = y0 + Math.floor(total / 12);
    const m = ((total % 12) + 12) % 12 + 1;
    if (y < 1900 || y > 9999) return null;
    const last = ymdToSerial(y, m + 1, 0);
    if (endOfMonth) return last;
    return Math.min(ymdToSerial(y, m, 1) + d - 1, last);
}

export const DATE_FUNCTIONS = {
    INT: guard((x) => { const n = num(x); return n === null ? 0 : Math.floor(n); }),
    DATE: guard((y, m, d) => ymdToSerial(whole(y), whole(m), whole(d))),
    YEAR: guard((v) => { const s = toSerial(v); return s ? serialToYmd(s)[0] : 0; }),
    MONTH: guard((v) => { const s = toSerial(v); return s ? serialToYmd(s)[1] : 0; }),
    DAY: guard((v) => { const s = toSerial(v); return s ? serialToYmd(s)[2] : 0; }),
    DAYS: guard((end, start) => {
        const e = toSerial(end), s = toSerial(start);
        return (e === null || s === null) ? 0 : e - s;
    }),
    DATEDIF: guard((start, end, unit) => {
        const s = toSerial(start), e = toSerial(end);
        if (s === null || e === null || s > e) return 0;
        const u = String(unit || "").trim().toUpperCase();
        const [sy, sm, sd] = serialToYmd(s);
        const [ey, em, ed] = serialToYmd(e);
        const months = monthsBetween(sy, sm, sd, ey, em, ed);
        if (u === "D") return e - s;
        if (u === "M") return months;
        if (u === "Y") return Math.floor(months / 12);
        if (u === "YM") return ((months % 12) + 12) % 12;
        if (u === "MD") return ed >= sd ? ed - sd : e - ymdToSerial(ey, em - 1, sd);
        if (u === "YD") {
            let anniversary = ymdToSerial(ey, sm, sd);
            if (anniversary > e) anniversary = ymdToSerial(ey - 1, sm, sd);
            return e - anniversary;
        }
        return 0;
    }),
    EDATE: guard((start, months) => {
        const s = toSerial(start);
        return s === null ? 0 : addMonths(s, whole(months), false);
    }),
    EOMONTH: guard((start, months) => {
        const s = toSerial(start);
        return s === null ? 0 : addMonths(s, whole(months), true);
    }),
};

/** Names whose arguments are dates (a date text reads as a date there). */
export const DATE_ARGUMENT_FUNCTIONS = new Set(["YEAR", "MONTH", "DAY", "DAYS", "DATEDIF", "EDATE", "EOMONTH"]);

// ---------------------------------------------------------------------------
// The flowchart parser and evaluator (was FormulaStudio.parseFormula/evalNode)
// ---------------------------------------------------------------------------

/** Excel text -> a small tree ({t: num|str|ref|range|op|cmp|fn}), or null. */
export function parseFormula(formula) {
    const toks = [];
    const re = /\s*("[^"]*"|[A-Za-z_]+(?=\()|[A-Za-z]+\d+|\d+\.?\d*|<=|>=|<>|[-+*/^&(),:<>=])/g;
    let m; const f = (formula || "").replace(/^=/, "");
    while ((m = re.exec(f))) toks.push(m[1]);
    let p = 0;
    const peek = () => toks[p];
    const next = () => toks[p++];
    const parseExpr = () => parseCmp();
    const parseCmp = () => { let l = parseAdd(); while (["<", ">", "<=", ">=", "<>", "="].includes(peek())) { const op = next(); l = { t: "cmp", op, l, r: parseAdd() }; } return l; };
    const parseAdd = () => { let l = parseMul(); while (["+", "-"].includes(peek())) { const op = next(); l = { t: "op", op, l, r: parseMul() }; } return l; };
    const parseMul = () => { let l = parseUnary(); while (["*", "/"].includes(peek())) { const op = next(); l = { t: "op", op, l, r: parseUnary() }; } return l; };
    const parseUnary = () => { if (peek() === "-") { next(); return { t: "op", op: "-", l: { t: "num", v: 0 }, r: parseUnary() }; } return parsePrimary(); };
    const parsePrimary = () => {
        const tk = peek();
        // never consume a delimiter as a value (keeps IF arg lists intact)
        if (tk === undefined || tk === "," || tk === ")") return { t: "num", v: 0 };
        if (tk === "(") { next(); const e = parseExpr(); if (peek() === ")") next(); return e; }
        if (tk[0] === '"') { next(); return { t: "str", v: tk.slice(1, -1) }; }
        if (/^[A-Za-z]+\d+$/.test(tk)) {
            next(); const col = tk.replace(/\d+$/, "").toUpperCase();
            if (peek() === ":" && /^[A-Za-z]+\d+$/.test(toks[p + 1] || "")) {
                next(); const end = next().replace(/\d+$/, "").toUpperCase();
                return { t: "range", start: col, end };
            }
            return { t: "ref", col };
        }
        if (/^\d/.test(tk)) { next(); return { t: "num", v: parseFloat(tk) }; }
        if (/^[A-Za-z_]+$/.test(tk)) {
            const name = next().toUpperCase(); const args = [];
            if (peek() === "(") { next(); if (peek() !== ")") { args.push(parseExpr()); while (peek() === ",") { next(); args.push(parseExpr()); } } if (peek() === ")") next(); }
            return { t: "fn", name, args };
        }
        next(); return { t: "num", v: 0 };
    };
    try { return parseExpr(); } catch (e) { return null; }
}

/**
 * The value of a tree node. ``ctx.values`` is column letter -> value (the
 * preview's numbers; a date component's value is its date text) and
 * ``ctx.expandRange(start, end)`` lists the letters of a range.
 *
 * ``inDate`` is true inside a date function's arguments: there a column that
 * holds a date reads as the date (as the engine does); everywhere else a
 * node evaluates exactly as before PR-A.
 */
export function evalFlowNode(a, ctx, inDate = false) {
    const ev = (x) => evalFlowNode(x, ctx, inDate);
    try {
        if (!a) return 0;
        if (a.t === "num") return a.v;
        if (a.t === "str") return 0;
        if (a.t === "ref") {
            const v = ctx.values[a.col];
            if (inDate) return dateOperand(v);
            // A text value (a date component's "2024-01-15", a grade) is 0 in
            // arithmetic, as in the engine — it used to be glued on as text.
            if (typeof v === "string") { const n = num(v); return n === null ? 0 : n; }
            return v || 0;
        }
        if (a.t === "op") { const l = ev(a.l), r = ev(a.r); return a.op === "+" ? l + r : a.op === "-" ? l - r : a.op === "*" ? l * r : a.op === "/" ? (r ? l / r : 0) : a.op === "^" ? Math.pow(l, r) : 0; }
        if (a.t === "cmp") { const l = ev(a.l), r = ev(a.r), o = a.op; return (o === ">" ? l > r : o === "<" ? l < r : o === ">=" ? l >= r : o === "<=" ? l <= r : o === "<>" ? l !== r : l === r) ? 1 : 0; }
        if (a.t === "range") return ctx.expandRange(a.start, a.end).reduce((s, col) => s + (ctx.values[col] || 0), 0);
        if (a.t === "fn") {
            const n = a.name;
            if (DATE_FUNCTIONS[n]) {
                const dateArgs = inDate || DATE_ARGUMENT_FUNCTIONS.has(n);
                const args = (a.args || []).map(x => x.t === "str" ? x.v : evalFlowNode(x, ctx, dateArgs));
                return DATE_FUNCTIONS[n](...args);
            }
            const g = (a.args || []).flatMap(x => x.t === "range" ? ctx.expandRange(x.start, x.end).map(col => ({ t: "ref", col })) : [x]);
            if (n === "IF") return ev(g[0]) ? ev(g[1]) : ev(g[2] || { t: "num", v: 0 });
            if (n === "SUM") return g.reduce((s, x) => s + ev(x), 0);
            if (n === "MAX") return Math.max(...g.map(x => ev(x)));
            if (n === "MIN") return Math.min(...g.map(x => ev(x)));
            if (n === "ROUND") { const v = ev(g[0]), d = g[1] ? ev(g[1]) : 0, f = Math.pow(10, d); return Math.round(v * f) / f; }
            if (n === "IFERROR") { const v = ev(g[0]); return isFinite(v) ? v : ev(g[1] || { t: "num", v: 0 }); }
            return ev(g[0] || { t: "num", v: 0 });
        }
        return 0;
    } catch (e) { return 0; }
}
