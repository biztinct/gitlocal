/** @odoo-module **/
/**
 * Workforce P1a — T1: the wf_context `day` field and its week invariant.
 *
 * These assert the PURE helpers plus the reconciliation rules of `set()`, which
 * are the pieces every P1 lens depends on:
 *   • `day` always sits inside [weekStart, weekStart+6];
 *   • paging the week keeps the WEEKDAY (Wed stays Wed);
 *   • a bare `day` patch drags the week to that day's Monday;
 *   • a patch carrying both lets weekStart win and clamps the day.
 *
 * All maths is LOCAL-date (never toISOString) — see the service header.
 */
import { describe, expect, test } from "@odoo/hoot";
import {
    addDays,
    clampDayToWeek,
    isoLocal,
    monday,
    normalizeDay,
    weekdayIndex,
    wfContextService,
    WF_CTX_KEY,
} from "@pb_wf_kit/js/wf_context_service";

describe.current.tags("headless");

/** A service instance with a clean localStorage — no Odoo env needed. */
function makeCtx() {
    try { window.localStorage.removeItem(WF_CTX_KEY); } catch { /* private mode */ }
    return wfContextService.start();
}

// ------------------------------------------------------------------ helpers
test("weekdayIndex is Monday-based", () => {
    expect(weekdayIndex("2026-08-17")).toBe(0);   // Monday
    expect(weekdayIndex("2026-08-19")).toBe(2);   // Wednesday
    expect(weekdayIndex("2026-08-23")).toBe(6);   // Sunday
});

test("clampDayToWeek keeps the weekday, never falls back to Monday", () => {
    // Wed 2026-08-19 clamped into the PREVIOUS week → Wed 2026-08-12
    expect(clampDayToWeek("2026-08-19", "2026-08-10")).toBe("2026-08-12");
    // Sunday is the 7th day of a Monday-based week, not the 1st
    expect(clampDayToWeek("2026-08-23", "2026-08-10")).toBe("2026-08-16");
    // already inside → unchanged
    expect(clampDayToWeek("2026-08-19", "2026-08-17")).toBe("2026-08-19");
});

test("normalizeDay rejects junk and re-serializes rolled-over dates", () => {
    expect(normalizeDay("2026-08-19")).toBe("2026-08-19");
    expect(normalizeDay("not-a-date")).toBe(null);
    expect(normalizeDay(12345)).toBe(null);
    expect(normalizeDay("")).toBe(null);
    expect(normalizeDay("2026-02-31")).toBe("2026-03-03");   // rolled, then stored as real
    expect(normalizeDay(new Date(2026, 7, 19))).toBe("2026-08-19");
});

// -------------------------------------------------------------- the service
test("day defaults to today and sits inside the default week", () => {
    const ctx = makeCtx();
    const today = isoLocal(new Date());
    expect(ctx.state.day).toBe(today);
    expect(ctx.state.weekStart).toBe(monday(today));
    expect(clampDayToWeek(ctx.state.day, ctx.state.weekStart)).toBe(ctx.state.day);
});

test("changing the week clamps the day into it, same weekday", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-17", day: "2026-08-19" });   // Wed
    expect(ctx.state.day).toBe("2026-08-19");

    ctx.set({ weekStart: "2026-08-24" });                      // next week
    expect(ctx.state.day).toBe("2026-08-26");                  // still Wednesday
    expect(ctx.state.weekStart).toBe("2026-08-24");

    ctx.shiftWeek(-14);
    expect(ctx.state.weekStart).toBe("2026-08-10");
    expect(ctx.state.day).toBe("2026-08-12");                  // still Wednesday
});

test("a non-Monday weekStart is normalized before the day is clamped", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-20", day: "2026-08-19" });   // Thursday given
    expect(ctx.state.weekStart).toBe("2026-08-17");            // → its Monday
    expect(ctx.state.day).toBe("2026-08-19");                  // Wed, inside
});

test("a bare day patch drags the week to that day's Monday", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-17" });
    ctx.set({ day: "2026-09-03" });                            // Thu, two weeks on
    expect(ctx.state.weekStart).toBe("2026-08-31");
    expect(ctx.state.day).toBe("2026-09-03");
});

test("shiftDay walks off the end of the week and takes the week with it", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-17", day: "2026-08-23" });   // Sunday
    ctx.shiftDay(1);
    expect(ctx.state.day).toBe("2026-08-24");
    expect(ctx.state.weekStart).toBe("2026-08-24");
    ctx.shiftDay(-1);
    expect(ctx.state.day).toBe("2026-08-23");
    expect(ctx.state.weekStart).toBe("2026-08-17");
});

test("weekStart wins when a patch carries both", () => {
    const ctx = makeCtx();
    // day belongs to a different week → clamped into the patch's week
    ctx.set({ weekStart: "2026-08-17", day: "2026-09-03" });   // Thu
    expect(ctx.state.weekStart).toBe("2026-08-17");
    expect(ctx.state.day).toBe("2026-08-20");                  // Thu of THIS week
});

test("today() jumps both the week and the day to now", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2020-01-06", day: "2020-01-09" });
    ctx.today();
    const now = isoLocal(new Date());
    expect(ctx.state.day).toBe(now);
    expect(ctx.state.weekStart).toBe(monday(now));
});

test("a junk day patch is ignored rather than corrupting the context", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-17", day: "2026-08-19" });
    expect(ctx.set({ day: "garbage" })).toBe(false);
    expect(ctx.state.day).toBe("2026-08-19");
});

test("day survives a reload and is re-clamped from storage", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-17", day: "2026-08-19" });
    const reloaded = wfContextService.start();                 // reads localStorage
    expect(reloaded.state.day).toBe("2026-08-19");
    expect(reloaded.state.weekStart).toBe("2026-08-17");

    // a hand-edited payload whose day is outside the week is repaired on load
    window.localStorage.setItem(WF_CTX_KEY, JSON.stringify({
        weekStart: "2026-08-17", day: "2026-09-03",
    }));
    const repaired = wfContextService.start();
    expect(repaired.state.day).toBe("2026-08-20");             // Thu of that week
});

test("onChange fires for a day-only change", () => {
    const ctx = makeCtx();
    ctx.set({ weekStart: "2026-08-17", day: "2026-08-19" });
    let seen = 0;
    const off = ctx.onChange(() => { seen += 1; });
    ctx.set({ day: "2026-08-20" });
    expect(seen).toBe(1);
    ctx.set({ day: "2026-08-20" });     // no-op → no notification
    expect(seen).toBe(1);
    off();
    ctx.set({ day: "2026-08-21" });
    expect(seen).toBe(1);
});

test("addDays / isoLocal never round-trip through UTC", () => {
    // The whole point of the local-date helpers: a Monday picked at 00:30 in a
    // positive-offset tz must not serialize as the previous Sunday.
    const d = new Date(2026, 7, 17, 0, 30);
    expect(isoLocal(d)).toBe("2026-08-17");
    expect(addDays("2026-08-17", 6)).toBe("2026-08-23");
    expect(monday("2026-08-23")).toBe("2026-08-17");
});
