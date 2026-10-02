/** @odoo-module **/
/**
 * "tonight 22:00–01:00" — a time window, said the way a person would say it.
 *
 * WHY THIS IS NOT A DATE FORMAT. The reader of a maintenance notice has exactly
 * one question: is this happening to me now, later today, or on some other day?
 * A stamp like "2026-09-03 22:00:00 → 2026-09-04 01:00:00" makes them work that
 * out for themselves, twice, in the middle of doing something else. So the
 * answer is a phrase, and the phrase changes with the answer:
 *
 *   same evening, today        "tonight 22:00–01:00"
 *   same day, not the evening  "today 09:00–11:00"
 *   tomorrow                   "tomorrow 22:00–01:00"
 *   anything else              "Thu 22:00 – Fri 01:00"
 *
 * IN THE READER'S OWN CLOCK. The platform writes the window in UTC; this reads
 * it back in the browser's time zone, so a customer in Ho Chi Minh City and one
 * in Singapore each see the hour their own wall clock will show. That is the
 * whole reason the rendering lives in the browser rather than being baked into
 * the message on the way out.
 *
 * ONE IMPLEMENTATION, TWO SCREENS. The platform owner's composer previews the
 * notice with this same function, through the same component, so the sentence
 * he approves is the sentence the customer gets.
 */
import { _t } from "@web/core/l10n/translation";

/** "22:00", in the browser's locale and time zone. */
function hhmm(d) {
    try {
        return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    } catch {
        return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
    }
}

/** "Thu", in the browser's locale. */
function shortDay(d) {
    try {
        return d.toLocaleDateString(undefined, { weekday: "short" });
    } catch {
        return "";
    }
}

/**
 * Parse what the platform wrote.
 *
 * The value crosses the wire as the framework's own "YYYY-MM-DD HH:MM:SS" in
 * UTC — a shape `new Date()` reads as LOCAL time in some browsers and refuses
 * outright in others, which would silently shift every window by the reader's
 * offset. So the UTC marker is put back before parsing, rather than trusted.
 */
export function parseStamp(v) {
    if (!v) { return null; }
    if (v instanceof Date) { return isNaN(v.getTime()) ? null : v; }
    let s = String(v).trim();
    if (!s) { return null; }
    if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$/.test(s)) {
        s = s.replace(" ", "T") + (s.length === 16 ? ":00" : "") + "Z";
    }
    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
}

/** Are these two moments on the same calendar day, locally? */
function sameDay(a, b) {
    return a.getFullYear() === b.getFullYear()
        && a.getMonth() === b.getMonth()
        && a.getDate() === b.getDate();
}

/** Midnight-to-midnight distance in days: 0 today, 1 tomorrow, -1 yesterday. */
function dayOffset(from, to) {
    const a = new Date(from.getFullYear(), from.getMonth(), from.getDate());
    const b = new Date(to.getFullYear(), to.getMonth(), to.getDate());
    return Math.round((b - a) / 86400000);
}

/**
 * The window as a phrase.
 *
 * @param {string|Date} starts  UTC stamp, or a Date
 * @param {string|Date} [ends]  UTC stamp, or a Date; may be missing
 * @param {Date} [now]          injected so a test can pin "today"
 * @returns {string} "" when there is no window at all — the caller then shows
 *                   the notice without a time line rather than an empty one.
 */
export function renderRange(starts, ends, now = new Date()) {
    const a = parseStamp(starts);
    const b = parseStamp(ends);
    if (!a && !b) { return ""; }
    if (!a) { return _t("until %(time)s", { time: hhmm(b) }); }
    if (!b) {
        const off0 = dayOffset(now, a);
        if (off0 === 0) { return _t("from %(time)s today", { time: hhmm(a) }); }
        if (off0 === 1) { return _t("from %(time)s tomorrow", { time: hhmm(a) }); }
        return _t("from %(day)s %(time)s", { day: shortDay(a), time: hhmm(a) });
    }
    const off = dayOffset(now, a);
    // "Evening" starts at 18:00 — the hour after which a Vietnamese payroll
    // office is empty, which is when every maintenance window is scheduled.
    const evening = a.getHours() >= 18;
    if (off === 0 && evening) {
        return _t("tonight %(from)s–%(to)s", { from: hhmm(a), to: hhmm(b) });
    }
    if (off === 0 && sameDay(a, b)) {
        return _t("today %(from)s–%(to)s", { from: hhmm(a), to: hhmm(b) });
    }
    if (off === 1) {
        return _t("tomorrow %(from)s–%(to)s", { from: hhmm(a), to: hhmm(b) });
    }
    if (sameDay(a, b)) {
        return _t("%(day)s %(from)s–%(to)s",
                  { day: shortDay(a), from: hhmm(a), to: hhmm(b) });
    }
    return _t("%(dayFrom)s %(from)s – %(dayTo)s %(to)s",
              { dayFrom: shortDay(a), from: hhmm(a),
                dayTo: shortDay(b), to: hhmm(b) });
}
