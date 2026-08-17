/** @odoo-module **/
/**
 * wf_context — the ONE place a Workforce surface reads its department, week,
 * person and search text from (W4). P0 ships the service + the bar; P1's Today
 * board and Time hub and P3's Mission Control shell consume the same instance,
 * which is what makes "change the week once, every panel follows" possible
 * without any cockpit knowing about another.
 *
 * State is persisted to localStorage so a hard reload restores the officer's
 * working context instead of dumping them back on "this week, all departments".
 */
import { reactive } from "@odoo/owl";
import { registry } from "@web/core/registry";

export const WF_CTX_KEY = "pbwf.ctx.v1";

// --------------------------------------------------------------- date helpers
// LOCAL-date maths only. toISOString() converts to UTC first, so a Monday picked
// at 06:00 in UTC+7 serializes as the previous Sunday and the server is asked
// for the wrong week — a real defect already fixed once in the Weekly Entry
// cockpit; the shared service must not reintroduce it.
export function isoLocal(dt) {
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, "0");
    const d = String(dt.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

export function parseLocal(str) {
    const [y, m, d] = String(str || "").split("-").map(Number);
    if (!y || !m || !d) { return new Date(); }
    return new Date(y, m - 1, d);
}

/** ISO date of the Monday of the week containing `d` (Date or "YYYY-MM-DD"). */
export function monday(d) {
    const dt = d instanceof Date ? new Date(d) : parseLocal(d);
    const day = dt.getDay();                      // 0 = Sunday
    dt.setDate(dt.getDate() - day + (day === 0 ? -6 : 1));
    return isoLocal(dt);
}

/** ISO date `days` after `startISO` (used for the week-end label). */
export function addDays(startISO, days) {
    const dt = parseLocal(startISO);
    dt.setDate(dt.getDate() + days);
    return isoLocal(dt);
}

/** "Aug 11 – 17" / "Aug 28 – Sep 3" — compact, month repeated only when it changes. */
export function weekLabel(startISO) {
    const s = parseLocal(startISO);
    const e = parseLocal(addDays(startISO, 6));
    const mo = (dt) => dt.toLocaleDateString("en-US", { month: "short" });
    return s.getMonth() === e.getMonth()
        ? `${mo(s)} ${s.getDate()} – ${e.getDate()}`
        : `${mo(s)} ${s.getDate()} – ${mo(e)} ${e.getDate()}`;
}

/** "Mon Aug 11" — the day pill's label. */
export function dayLabel(dayISO) {
    return parseLocal(dayISO).toLocaleDateString("en-US", {
        weekday: "short", month: "short", day: "numeric",
    });
}

/** 0 = Monday … 6 = Sunday. The week is Monday-based everywhere in the kit. */
export function weekdayIndex(dayISO) {
    const wd = parseLocal(dayISO).getDay();     // 0 = Sunday
    return wd === 0 ? 6 : wd - 1;
}

/**
 * The `day` INVARIANT: `day` always sits inside `[weekStart, weekStart+6]`.
 *
 * Clamping keeps the WEEKDAY (mockup A's "‹ Wed 13 ›" stays a Wednesday when
 * the officer pages to the next week), which is always possible because both
 * ends are Monday-based — so this is a total function, never a fallback to
 * weekStart. Exported because it is the piece worth unit-testing (T1).
 */
export function clampDayToWeek(dayISO, weekStartISO) {
    return addDays(weekStartISO, weekdayIndex(dayISO));
}

/** Normalize an arbitrary day input to a local ISO date, or null when unusable. */
export function normalizeDay(value) {
    if (value instanceof Date) { return isoLocal(value); }
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) { return null; }
    const d = parseLocal(value);
    // parseLocal rolls invalid components over (2026-02-31 → Mar 3); re-serialize
    // so callers can only ever store a real calendar day.
    return isoLocal(d);
}

// ------------------------------------------------------------------- defaults
function defaults() {
    const now = new Date();
    return {
        departmentId: false,
        weekStart: monday(now),
        personId: false,
        search: "",
        // P1a: the Time hub's lenses (and P1b's Today board) need ONE focused
        // day inside the context week — the week stays the canonical range and
        // day-scoped lenses derive from this.
        day: isoLocal(now),
    };
}

function load() {
    const d = defaults();
    let raw = null;
    try { raw = JSON.parse(browserStorage()?.getItem(WF_CTX_KEY) || "null"); }
    catch { raw = null; }
    if (!raw || typeof raw !== "object") { return d; }
    // Validate every field: a stale or hand-edited payload must never be able to
    // push a bad department id or a non-Monday week into a cockpit's RPC.
    const out = { ...d };
    if (Number.isInteger(raw.departmentId) && raw.departmentId > 0) {
        out.departmentId = raw.departmentId;
    }
    if (Number.isInteger(raw.personId) && raw.personId > 0) {
        out.personId = raw.personId;
    }
    if (typeof raw.weekStart === "string" && /^\d{4}-\d{2}-\d{2}$/.test(raw.weekStart)) {
        out.weekStart = monday(raw.weekStart);
    }
    if (typeof raw.search === "string") {
        out.search = raw.search.slice(0, 128);
    }
    // `day` is an additive field (no storage migration, W-key unchanged): a
    // payload written by the P0 build simply has none, and the default stands.
    const day = normalizeDay(raw.day);
    if (day) { out.day = day; }
    // restore the invariant even for a hand-edited payload
    out.day = clampDayToWeek(out.day, out.weekStart);
    return out;
}

function browserStorage() {
    // Private-browsing / disabled-storage safe: localStorage access itself can throw.
    try { return window.localStorage; } catch { return null; }
}

// -------------------------------------------------------------------- service
export const wfContextService = {
    dependencies: [],
    start() {
        const state = reactive(load());
        const subs = new Set();

        function persist() {
            const st = browserStorage();
            if (!st) { return; }
            try {
                st.setItem(WF_CTX_KEY, JSON.stringify({
                    departmentId: state.departmentId,
                    weekStart: state.weekStart,
                    personId: state.personId,
                    search: state.search,
                    day: state.day,
                }));
            } catch { /* quota / private mode — context just stops surviving reloads */ }
        }

        return {
            state,

            /**
             * Merge a patch, normalize, persist, notify. Unknown keys are ignored.
             *
             * **W16: this is the ONLY write door.** `state` stays a plain exposed
             * reactive because every consumer needs `useState(ctx.state)` to
             * subscribe — but assigning to it directly (`ctx.state.weekStart = x`)
             * skips normalization, the day invariant, persistence AND the
             * onChange fan-out, so the other cockpits silently desync. Reviews
             * and the T4 grep reject direct assignment.
             *
             * Reconciliation between `weekStart` and `day` (§2.3):
             *   • weekStart in the patch wins → `day` is clamped into it;
             *   • day alone → the week follows the day (weekStart = its Monday);
             *   • neither → the stored invariant already holds.
             */
            set(patch = {}) {
                let changed = false;
                for (const [k, v] of Object.entries(patch)) {
                    if (!(k in state)) { continue; }
                    let val = v;
                    if (k === "weekStart" && v) { val = monday(v); }
                    if (k === "day") {
                        val = normalizeDay(v);
                        if (!val) { continue; }     // junk day → keep the current one
                    }
                    if (state[k] !== val) { state[k] = val; changed = true; }
                }
                if ("weekStart" in patch || !("day" in patch)) {
                    const clamped = clampDayToWeek(state.day, state.weekStart);
                    if (state.day !== clamped) { state.day = clamped; changed = true; }
                } else if ("day" in patch) {
                    const wk = monday(state.day);
                    if (state.weekStart !== wk) { state.weekStart = wk; changed = true; }
                }
                if (!changed) { return false; }
                persist();
                // A throwing subscriber must not stop the others from updating.
                for (const cb of [...subs]) {
                    try { cb(state); } catch (e) { console.error("wf_context subscriber failed", e); }
                }
                return true;
            },

            /** Subscribe to changes. Returns an unsubscribe function. */
            onChange(cb) {
                if (typeof cb !== "function") { return () => {}; }
                subs.add(cb);
                return () => subs.delete(cb);
            },

            /** Week navigation helpers — every consumer shifts weeks identically. */
            shiftWeek(days) { return this.set({ weekStart: addDays(state.weekStart, days) }); },
            /** Day navigation: stepping off either end drags the week with it. */
            shiftDay(days) { return this.set({ day: addDays(state.day, days) }); },
            today() {
                const now = new Date();
                return this.set({ weekStart: monday(now), day: isoLocal(now) });
            },

            reset() { return this.set(defaults()); },
        };
    },
};

registry.category("services").add("wf_context", wfContextService);
