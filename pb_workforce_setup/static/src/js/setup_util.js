/** @odoo-module **/
/**
 * Workforce setup (WFSETUP P1) — small shared helpers.
 *
 * Icons: `ic()` returns a NEW markup() every call, and `t-out` of a new markup
 * re-inserts the DOM on every render (facts K6), so every icon the screen
 * shows comes from ONE cache here. Unknown names silently render a tick (K7):
 * the static test checks every `ic(...)` / `icon(...)` spelling.
 */
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const ICON_CACHE = new Map();

export function icon(name, size = 16) {
    const key = `${name}:${size}`;
    if (!ICON_CACHE.has(key)) {
        ICON_CACHE.set(key, ic(name, size));
    }
    return ICON_CACHE.get(key);
}

export const MODEL = "pb.workforce.setup";

/** Monday first, like every working week on this screen. */
export function dayNames() {
    return [_t("Mon"), _t("Tue"), _t("Wed"), _t("Thu"), _t("Fri"), _t("Sat"), _t("Sun")];
}

/** "07:30" -> 450. Anything unreadable -> null. */
export function toMin(text) {
    const m = /^(\d{1,2}):(\d{2})$/.exec(String(text || "").trim());
    if (!m) {
        return null;
    }
    const h = Number(m[1]);
    const mm = Number(m[2]);
    return h < 24 && mm < 60 ? h * 60 + mm : null;
}

/** Length of a shift in minutes; an end at or before the start is the next day. */
export function spanOf(start, end) {
    const a = toMin(start);
    const b = toMin(end);
    if (a === null || b === null) {
        return 0;
    }
    let d = b - a;
    if (d <= 0) {
        d += 1440;
    }
    return a === b ? 0 : d;
}

export function endsNextDay(start, end) {
    const a = toMin(start);
    const b = toMin(end);
    return a !== null && b !== null && a !== b && b <= a;
}

/** "07:30 to 16:30" */
export function timeRange(start, end) {
    return _t("%(start)s to %(end)s", { start, end });
}

/** 480 -> "8 h", 450 -> "7.5 h". */
export function hrs(minutes) {
    const v = Math.round((minutes || 0) / 6) / 10;
    return `${Number.isInteger(v) ? v : v.toFixed(1)} h`;
}

/**
 * The 24-hour bar: one or two coloured segments (two when the shift runs past
 * midnight) and the pale unpaid-break gap in the middle of the working time.
 * Percent strings, ready for a style attribute.
 */
export function barParts(start, end, breakMinutes) {
    const a = toMin(start);
    const d = spanOf(start, end);
    if (a === null || !d) {
        return { segments: [], gap: null };
    }
    const pc = (v) => `${(v / 1440) * 100}%`;
    const e = a + d;
    const segments = e <= 1440
        ? [{ key: "a", left: pc(a), width: pc(d) }]
        : [{ key: "a", left: pc(a), width: pc(1440 - a) }, { key: "b", left: "0%", width: pc(e - 1440) }];
    const brk = Math.max(0, Math.min(Number(breakMinutes) || 0, d));
    let gap = null;
    if (brk > 0) {
        const bs = (a + Math.round((d - brk) / 2)) % 1440;
        gap = { left: pc(bs), width: pc(Math.min(brk, 1440 - bs)) };
    }
    return { segments, gap };
}

export function errorText(error) {
    return (error && (error.data?.message || error.message)) || _t("Something went wrong. Please try again.");
}

export function deepClone(value) {
    return JSON.parse(JSON.stringify(value));
}
