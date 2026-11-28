import { expect, test } from "@odoo/hoot";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { localization } from "@web/core/l10n/localization";
import { groupTyped, parseMoney } from "@pb_pay_builder/js/pay_format";

test("a pasted monthly or annual amount keeps every group of digits", () => {
    patchWithCleanup(localization, { grouping: [3, 0], decimalPoint: ",", thousandsSep: "." });
    const dong = { name: "VND", decimals: 0, builder: true };
    const rupee = { name: "INR", decimals: 2, builder: true };
    for (const input of ["31.000.000", "31,000,000", "31000000"]) {
        expect(groupTyped(input, dong)).toBe("31.000.000");
        expect(parseMoney(groupTyped(input, dong))).toBe(31000000);
    }
    expect(parseMoney(groupTyped("12,00,000", rupee))).toBe(1200000);
    expect(parseMoney(groupTyped("1.234,50", rupee))).toBe(1234.5);
});
