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
