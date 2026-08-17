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

// ------------------------------------------------------------------- defaults
function defaults() {
    return { departmentId: false, weekStart: monday(new Date()), personId: false, search: "" };
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
                }));
            } catch { /* quota / private mode — context just stops surviving reloads */ }
        }

        return {
            state,

            /** Merge a patch, normalize, persist, notify. Unknown keys are ignored. */
            set(patch = {}) {
                let changed = false;
                for (const [k, v] of Object.entries(patch)) {
                    if (!(k in state)) { continue; }
                    const val = k === "weekStart" && v ? monday(v) : v;
                    if (state[k] !== val) { state[k] = val; changed = true; }
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
            today() { return this.set({ weekStart: monday(new Date()) }); },

            reset() { return this.set(defaults()); },
        };
    },
};

registry.category("services").add("wf_context", wfContextService);
