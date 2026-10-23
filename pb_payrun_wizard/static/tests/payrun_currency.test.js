/** @odoo-module **/
/**
 * SCHEMECTX P1 — the Scope panel follows the card that was picked.
 *
 * The defect: one currency was decided once, for the whole screen, from the
 * company. Picking an India scheme left "VND" on the panel and a dong sign on
 * every amount. The three pieces that must never drift apart are the chosen
 * card, the currency shown and the sign written in front of a number, so all
 * three are pure functions of the card and are asserted here.
 */
import { describe, expect, test } from "@odoo/hoot";
import {
    formatMoney,
    moneyLabel,
    schemeMoney,
} from "@pb_payrun_wizard/js/payrun_wizard";

describe.current.tags("headless");

const INDIA = { id: 2, name: "Rize India Payroll",
    currency: { id: 21, name: "INR", symbol: "₹", position: "before", decimals: 2 } };
const VIETNAM = { id: 1, name: "Rize Vietnam",
    // exactly as the server sends it: base data records dong AFTER the number
    currency: { id: 23, name: "VND", symbol: "₫", position: "after", decimals: 0 } };
const DEFAULTS = { currency: VIETNAM.currency };

test("picking another card changes the money on the Scope panel", () => {
    expect(moneyLabel(schemeMoney(VIETNAM, DEFAULTS))).toBe("VND · ₫");
    expect(moneyLabel(schemeMoney(INDIA, DEFAULTS))).toBe("INR · ₹");
});

test("with no card picked the panel keeps the payload's opening answer", () => {
    expect(moneyLabel(schemeMoney(null, DEFAULTS))).toBe("VND · ₫");
});

test("an older server that sends a bare name still renders a currency", () => {
    const money = schemeMoney(null, { currency: "VND" });
    expect(money.name).toBe("VND");
    expect(money.symbol).toBe("₫");
    expect(moneyLabel(money)).toBe("VND · ₫");
});

test("amounts carry the chosen scheme's sign, never a hard-coded one", () => {
    const india = schemeMoney(INDIA, DEFAULTS);
    const viet = schemeMoney(VIETNAM, DEFAULTS);
    expect(formatMoney(india, 4500)).toBe("₹5K");
    expect(formatMoney(india, 12_000_000)).toBe("₹12.0M");
    expect(formatMoney(viet, 12_000_000)).toBe("₫12.0M");
    expect(formatMoney(india, 900)).toBe("₹900");
});

test("the sign follows the scheme; where the sign sits does not", () => {
    // `res.currency` records dong as written AFTER the number. Every screen in
    // this product writes it in front, and this phase must not flip every
    // Vietnamese amount while it is fixing India.
    const viet = schemeMoney(VIETNAM, DEFAULTS);
    expect(viet.position).toBe("after");
    expect(formatMoney(viet, 12_000_000)).toBe("₫12.0M");
    expect(formatMoney(viet, 4500)).toBe("₫5K");
});

test("a currency with no symbol falls back to its name, never to a dong sign", () => {
    const bare = { name: "KHR", symbol: "", position: "after", decimals: 0 };
    expect(formatMoney(bare, 500)).toBe("KHR500");
    expect(moneyLabel(bare)).toBe("KHR");
});
