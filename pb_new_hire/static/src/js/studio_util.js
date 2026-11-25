/** @odoo-module **/
/**
 * New Hire Studio (NEWHIRE P1) — small shared helpers.
 *
 * Icons: `ic()` returns a NEW markup() every call and `t-out` of a new markup
 * re-inserts the DOM on every render, so every icon comes from ONE cache here.
 * Unknown names silently render a tick: the static test checks every spelling.
 * Numbers go through the web client's own formatter (the user's language,
 * never the browser's — WS42).
 */
import { markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";
import { localization } from "@web/core/l10n/localization";
import { ic } from "@pb_import_kit/js/import_icons";

const { DateTime } = luxon;

export const MODEL = "pb.new.hire";
export const ACTION_XMLID = "pb_new_hire.action_new_hire_studio";
export const STUDIO_TAG = "pb_new_hire_studio";

const ICON_CACHE = new Map();
export function icon(name, size = 16) {
    const key = `${name}:${size}`;
    if (!ICON_CACHE.has(key)) {
        ICON_CACHE.set(key, ic(name, size));
    }
    return ICON_CACHE.get(key);
}

export function errorText(error) {
    return (error && (error.data?.message || error.message)) || _t("Something went wrong. Please try again.");
}

export function isAccessError(error) {
    const name = error?.data?.name || error?.exceptionName || "";
    return /AccessError/.test(name);
}

export function esc(text) {
    return String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const RICH = new Map();
/** A translated sentence with `%(key)s` values: `bold` ones in <b>, all escaped.
 *  Cached by its text so `t-out` keeps the same DOM while it does not change. */
export function rich(template, bold = {}, plain = {}) {
    const vals = {};
    for (const [k, v] of Object.entries(plain)) {
        vals[k] = esc(v);
    }
    for (const [k, v] of Object.entries(bold)) {
        vals[k] = `<b>${esc(v)}</b>`;
    }
    const html = esc(template).replace(/%\((\w+)\)s/g, (m, k) => (k in vals ? vals[k] : m));
    if (!RICH.has(html)) {
        if (RICH.size > 400) {
            RICH.clear();
        }
        RICH.set(html, markup(html));
    }
    return RICH.get(html);
}

export function firstName(name) {
    return String(name || "").trim().split(/\s+/)[0] || "";
}

export function initials(name) {
    const w = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!w.length) {
        return "";
    }
    return (w[0][0] + (w.length > 1 ? w[w.length - 1][0] : "")).toUpperCase();
}

/** "Mon 7 Dec" (short) or "Monday 7 December 2026" (long), in the user's language. */
export function fmtDay(iso, long = false) {
    if (!iso) {
        return "";
    }
    const d = DateTime.fromISO(iso);
    if (!d.isValid) {
        return "";
    }
    return long
        ? d.toLocaleString({ weekday: "long", day: "numeric", month: "long", year: "numeric" })
        : d.toLocaleString({ weekday: "short", day: "numeric", month: "short", year: d.year === DateTime.now().year ? undefined : "numeric" });
}

export function isoAfter(a, b) {
    return Boolean(a && b && a > b);
}

/** 5200.5 -> "5,200.50" with the currency's decimals. */
export function moneyNumber(value, cur) {
    const digits = cur && Number.isInteger(cur.decimals) ? cur.decimals : 2;
    return formatFloat(Number(value) || 0, { digits: [69, digits] });
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
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ts);
    return frac === null ? grouped : `${grouped}${dp}${frac}`;
}

/**
 * P2: answers several components need. Each reads the `nh` it is GIVEN, so a
 * component passes its own reactive copy and re-renders when they change
 * (reading through another component's state subscribes that one only).
 */
export function weekNameOf(nh) {
    const weeks = (nh.sched && nh.sched.weeks) || [];
    const w = weeks.find((x) => x.id === nh.draft.week_id);
    return w ? w.name : "";
}
export function siteNameOf(nh) {
    const s = ((nh.data && nh.data.sites) || []).find((x) => x.id === nh.draft.work_location_id);
    return s ? s.name : "";
}
/** Required own fields of this country still empty (they block Send). */
export function ownMissingOf(nh) {
    const w = nh.welcome;
    const own = nh.draft.own || {};
    return ((w && w.own_fields) || []).filter((f) => f.supported && f.required && f.kind !== "bool")
        .filter((f) => {
            const v = own[f.name];
            return v === undefined || v === null || v === false || String(v).trim() === "";
        });
}

export function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
}
