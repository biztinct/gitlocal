/** @odoo-module **/
/**
 * RECORDS R1 — the pay-data step's "Update Payobook / This run only" choice.
 *
 * The three things that must never drift apart are the CHOICE, the LABEL on the
 * button and the ARGUMENT the server is called with. They are pure functions of
 * the mode for exactly that reason, so they can be asserted here without
 * mounting the wizard or standing up an ORM.
 */
import { describe, expect, test } from "@odoo/hoot";
import {
    attachArgs,
    continueLabel,
    freshSheetMode,
    isOneTime,
    MODE_ONCE,
    MODE_UPDATE,
    nextSheetMode,
    SHEET_MODES,
    exceptionNames,
    importDoor,
    notInPayobookHeading,
    splitExceptions,
} from "@pb_payrun_wizard/js/payrun_wizard";

describe.current.tags("headless");

test("the default is to update the records", () => {
    expect(freshSheetMode()).toBe(MODE_UPDATE);
    expect(isOneTime(freshSheetMode())).toBe(false);
    expect(SHEET_MODES).toEqual([MODE_UPDATE, MODE_ONCE]);
});

test("arrow keys move between the two cards and wrap", () => {
    expect(nextSheetMode(MODE_UPDATE, "ArrowRight")).toBe(MODE_ONCE);
    expect(nextSheetMode(MODE_UPDATE, "ArrowDown")).toBe(MODE_ONCE);
    expect(nextSheetMode(MODE_ONCE, "ArrowLeft")).toBe(MODE_UPDATE);
    expect(nextSheetMode(MODE_ONCE, "ArrowUp")).toBe(MODE_UPDATE);
    // wrapping, so the group can be cycled with one key
    expect(nextSheetMode(MODE_ONCE, "ArrowRight")).toBe(MODE_UPDATE);
    expect(nextSheetMode(MODE_UPDATE, "ArrowLeft")).toBe(MODE_ONCE);
    expect(nextSheetMode(MODE_UPDATE, "Home")).toBe(MODE_UPDATE);
    expect(nextSheetMode(MODE_UPDATE, "End")).toBe(MODE_ONCE);
});

test("any other key leaves the choice alone", () => {
    for (const key of ["Tab", "a", "Escape", "PageDown", "Enter", " "]) {
        expect(nextSheetMode(MODE_ONCE, key)).toBe(MODE_ONCE);
        expect(nextSheetMode(MODE_UPDATE, key)).toBe(MODE_UPDATE);
    }
});

test("the button says which run you are about to do", () => {
    expect(continueLabel(MODE_UPDATE)).toBe("Continue with this file");
    expect(continueLabel(MODE_ONCE)).toBe("Continue — this run only");
    // and never names the engine (white-label rule)
    for (const mode of SHEET_MODES) {
        expect(continueLabel(mode).toLowerCase().includes("odoo")).toBe(false);
    }
});

test("attach_spreadsheet is called with the mode as its 7th argument", () => {
    const base = [7, 3, "Yg==", "march.xlsx", "2026-03-01", "2026-03-31"];
    const update = attachArgs(...base, MODE_UPDATE);
    const once = attachArgs(...base, MODE_ONCE);

    expect(update.length).toBe(7);
    expect(once.length).toBe(7);
    // the first six are untouched — a pre-R1 server call, unchanged
    expect(update.slice(0, 6)).toEqual(base);
    expect(once.slice(0, 6)).toEqual(base);
    expect(update[6]).toBe(false);
    expect(once[6]).toBe(true);
});

// =====================================================================
//  RECORDS R4 — D4: "not in Payobook yet" is one fact, not N exceptions
//
//  The Review step used to list every unmatched row beside every other
//  exception, which made thirty rows read as thirty problems. They are one
//  problem with one next step, and the next step is the door that ADDS people
//  — never the Records Desk, which has nothing to edit for somebody who does
//  not exist yet.
// =====================================================================

test("the unmatched rows come out of the flat list exactly once", () => {
    // `attach_spreadsheet` returns them BOTH ways: inside `errors` (which the
    // flat list has always shown) and separately so they can be counted. A row
    // that appeared in both would be a person flagged twice.
    const unmatched = [
        { emp: "R1 Nobody", why: "This person is not in Payobook yet." },
        { emp: "R2 Nobody", why: "This person is not in Payobook yet." },
    ];
    const exceptions = [
        ...unmatched,
        { emp: "Real Person", why: "Net is negative." },
    ];
    const split = splitExceptions(exceptions, unmatched);
    expect(split.missing).toHaveLength(2);
    expect(split.rest).toHaveLength(1);
    expect(split.rest[0].emp).toBe("Real Person");
});

test("nothing unmatched leaves the exception list exactly as it was", () => {
    const exceptions = [{ emp: "Real Person", why: "Net is zero." }];
    const split = splitExceptions(exceptions, []);
    expect(split.missing).toEqual([]);
    expect(split.rest).toEqual(exceptions);
    // …and a run with no file at all is still the empty case, not a crash.
    expect(splitExceptions(undefined, undefined).rest).toEqual([]);
});

test("the heading counts the people and says what happened to them", () => {
    expect(notInPayobookHeading(1)).toBe(
        "1 person in the file is not in Payobook yet — they were listed, not paid");
    expect(notInPayobookHeading(30)).toBe(
        "30 people in the file are not in Payobook yet — they were listed, not paid");
    // and never names the engine (white-label rule)
    for (const n of [1, 30]) {
        expect(notInPayobookHeading(n).toLowerCase().includes("odoo")).toBe(false);
    }
});

test("the 'Add these people' door is offered only where it exists", () => {
    const registered = { contains: (key) => key === "pb_import_wizard" };
    const bare = { contains: () => false };
    expect(importDoor(registered)).toBe("pb_import_wizard.action_pb_import_wizard");
    expect(importDoor(bare)).toBe("");
    // A registry that throws is a database without the door, not a crash on
    // the Review step of a finished pay run.
    expect(importDoor({ contains: () => { throw new Error("nope"); } })).toBe("");
    expect(importDoor(null)).toBe("");
});

test("Copy names copies the names, one per line", () => {
    expect(exceptionNames([{ emp: "A One" }, { emp: "B Two" }]))
        .toBe("A One\nB Two");
    // A row that named nobody has no name to copy and does not leave a blank.
    expect(exceptionNames([{ emp: "" }, { emp: "B Two" }])).toBe("B Two");
    expect(exceptionNames([])).toBe("");
});
