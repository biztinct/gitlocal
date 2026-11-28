/** @odoo-module **/
import { formatFloat, insertThousandsSep } from "@web/core/utils/numbers";
import { localization } from "@web/core/l10n/localization";
import { ic } from "@pb_import_kit/js/import_icons";

const ICON_CACHE = new Map();
export function icon(name, size = 16) {
    const key = `${name}:${size}`;
    if (!ICON_CACHE.has(key)) {
        ICON_CACHE.set(key, ic(name, size));
    }
    return ICON_CACHE.get(key);
}

/** 5200.5 -> "5,200.50" with the currency's decimals. */
export function moneyNumber(value, cur) {
    const compactRupees = cur?.builder && cur.name === "INR" && Number.isInteger(value);
    const digits = compactRupees ? 0 : (cur && Number.isInteger(cur.decimals) ? cur.decimals : 2);
    return formatFloat(Number(value) || 0, { digits: [69, digits], grouping: cur?.builder && cur.name === "INR" ? [3, 2, 0] : localization.grouping });
}

/** 5200.5 -> "$ 5,200.50" / "5.200,50 ₫", as the currency writes itself. */
export function money(value, cur) {
    if (!cur) {
        return moneyNumber(value, cur);
    }
    const n = moneyNumber(value, cur);
    const sym = cur.symbol || cur.name || "";
    return cur.position === "before" ? `${sym} ${n}` : `${n} ${sym}`;
}

/**
 * What a half-typed wage box means: a number, or null (never NaN or "" —
 * WS18). Thousands separators and spaces are ignored; the user's decimal
 * point is read as the decimal point.
 */
export function parseMoney(text) {
    const dp = localization.decimalPoint || ".";
    const ts = localization.thousandsSep || ",";
    let s = String(text ?? "").trim();
    if (!s) {
        return null;
    }
    if (ts) {
        s = s.split(ts).join("");
    }
    s = s.replace(/\s/g, "");
    if (dp !== ".") {
        s = s.split(dp).join(".");
    }
    s = s.replace(/[^0-9.]/g, "");
    if (!s || s === ".") {
        return null;
    }
    const n = Number.parseFloat(s);
    return Number.isFinite(n) ? n : null;
}

/** The wage box while typing: whole part grouped, the decimals as typed. */
export function groupTyped(text, cur) {
    const dp = localization.decimalPoint || ".";
    const ts = localization.thousandsSep || ",";
    const raw = String(text ?? "");
    const cut = raw.indexOf(dp);
    const whole = (cut >= 0 ? raw.slice(0, cut) : raw).replace(/[^0-9]/g, "").replace(/^0+(?=\d)/, "");
    const decimals = cur && Number.isInteger(cur.decimals) ? cur.decimals : 2;
    const frac = cut >= 0 && decimals > 0 ? raw.slice(cut + 1).replace(/[^0-9]/g, "").slice(0, decimals) : null;
    const grouped = insertThousandsSep(whole, ts, cur?.builder && cur.name === "INR" ? [3, 2, 0] : localization.grouping);
    return frac === null ? grouped : `${grouped}${dp}${frac}`;
}
