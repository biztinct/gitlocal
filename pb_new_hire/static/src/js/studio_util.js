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
import { browser } from "@web/core/browser/browser";
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

/**
 * P3a — step 5's shared answers (plain functions over the caller's own `nh`,
 * NH27). The list itself is the server's (`details_options`); these only
 * read the choices and what was typed.
 */
export const DOC_CHOICES = ["ask", "have", "skip", "later", "number", "hiring"];
export const FILE_MIMES = ["image/png", "image/jpeg", "application/pdf"];
export const FILE_MAX = 10 * 1024 * 1024;
export const FILES_MAX = 50 * 1024 * 1024;

export function docItemsOf(nh) {
    return (nh.docs && nh.docs.items) || [];
}
export function docChoiceOf(nh, item) {
    const c = (nh.draft.items || {})[item.key];
    if (!DOC_CHOICES.includes(c) || (c === "ask" && !item.can_ask) || (c === "later" && item.can_ask)
            || (c === "skip" && !item.can_skip) || (c === "have" && !item.can_have)
            || (c === "number" && !item.can_number) || (c === "hiring" && !item.can_hiring)) {
        return item.default;
    }
    return c;
}
/** How a source choice is described in the review, progress tally and record preview. */
export function docSummaryChoiceOf(nh, item) {
    const choice = docChoiceOf(nh, item);
    return item.tallyAs?.[choice] || choice;
}
function isEmail(text) {
    return String(text || "").includes("@");
}
/** A typed value; the personal phone of step 1 is the one source for it. */
export function haveValueOf(nh, name) {
    const have = nh.draft.have || {};
    if (name === "private_phone" && have[name] === undefined && nh.draft.personal && !isEmail(nh.draft.personal)) {
        return nh.draft.personal;
    }
    return have[name];
}
function blank(v) {
    return v === undefined || v === null || v === false || String(v).trim() === "";
}
/** P7: which country's format the bank row follows — the one HR picked,
 *  else the Country of work's (`item.bank.default`). */
export function bankFormatOf(nh, item) {
    const chosen = (nh.draft.have || {}).bank_format;
    const bank = item.bank || {};
    return chosen && (bank.fields || {})[chosen] ? chosen : bank.default;
}
/** The boxes of a row. P7: the bank row's follow its account's country
 *  (the bank check's one definition, built on the server). */
export function docFieldsOf(nh, item) {
    if (item.key === "bank" && item.bank && item.bank.fields) {
        return item.bank.fields[bankFormatOf(nh, item)] || item.fields;
    }
    return item.fields;
}
/** What an "I have it" row still lacks: "" | "fields" | "file" | "again" | "expiry".
 *  P3b: "I have the number" (merged card rows) needs the number only. */
export function docGapOf(nh, item) {
    const choice = docChoiceOf(nh, item);
    if (choice !== "have" && choice !== "number") {
        return "";
    }
    const fields = docFieldsOf(nh, item).filter((f) => !(item.key === "bank"
        && (f.name === "account_holder" || f.name === "bank_format")));
    const required = fields.filter((f) => f.required);
    if (required.some((f) => blank(haveValueOf(nh, f.name)))) {
        return "fields";
    }
    if (!required.length && !item.upload && fields.length && fields.every((f) => blank(haveValueOf(nh, f.name)))) {
        return "fields";
    }
    if (item.upload && choice === "have") {
        const meta = (nh.draft.file_meta || {})[item.key];
        if (!(nh.files || {})[item.key]) {
            return meta && meta.name ? "again" : "file";
        }
        if (item.upload.needs_expiry && !(meta && meta.expiry_date)) {
            return "expiry";
        }
    }
    return "";
}
export function docGapsOf(nh) {
    return docItemsOf(nh).filter((i) => docGapOf(nh, i));
}
/** How many rows each side gives. "I have the number" counts for both: the
 *  number is with you, the card is asked. */
export function docTallyOf(nh) {
    const out = { ask: 0, have: 0, skip: 0, later: 0 };
    for (const item of docItemsOf(nh)) {
        const c = docSummaryChoiceOf(nh, item);
        if (c === "number") {
            out.ask += 1;
            out.have += 1;
        } else if (c === "hiring") {
            out.have += 1;              // P4: the paper sent in Hiring
        } else {
            out[c] += 1;
        }
    }
    return out;
}
/** What the new person is asked for: `[{key, label, need}]` — on a
 *  number-only card row, the card. */
export function docAskedOf(nh) {
    const out = [];
    for (const item of docItemsOf(nh)) {
        const c = docChoiceOf(nh, item);
        if (c === "ask") {
            // P4: a card that came across from Hiring — only its number is asked
            out.push({ key: item.key, label: item.ask_label || item.label, need: item.need, icon: item.icon });
        } else if (c === "number") {
            out.push({ key: item.key, label: item.upload.label, need: item.need, icon: item.icon });
        }
    }
    return out;
}

/**
 * P3b: put text on the clipboard. True when it got there. Never waits more
 * than 1.5 s: a browser can leave the promise pending (a tab without focus,
 * a permission prompt), and then the caller shows the text to copy by hand.
 */
export async function copyText(text) {
    const clip = browser.navigator && browser.navigator.clipboard;
    if (!clip || !clip.writeText) {
        return false;
    }
    const timeout = new Promise((resolve) => setTimeout(() => resolve(false), 1500));
    const write = clip.writeText(text).then(() => true, () => false);
    return Promise.race([write, timeout]);
}

export function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
}
