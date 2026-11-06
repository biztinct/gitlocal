/** @odoo-module **/
import { describe, expect, test } from "@odoo/hoot";
import { PayrunWizard } from "@pb_payrun_wizard/js/payrun_wizard";

describe.current.tags("headless");
const methods = PayrunWizard.prototype;
const card = { id: 7, name: "India payroll" };
function subject() {
    return {
        chosenScheme: card, hasStatusFilter: false,
        state: { form: { formula_config_id: 7, date_start: "2026-08-01", date_end: "2026-08-31",
                         name: "India payroll · August 2026" }, scheme: {}, who: {} },
        _periodLabel: methods._periodLabel,
    };
}

test("changing dates refreshes scope and updates an automatic month label", () => {
    const wizard = subject(); let refreshes = 0;
    wizard.refreshWho = () => refreshes++;
    methods.onField.call(wizard, "date_start", { target: { value: "2026-09-01" } });
    methods.onField.call(wizard, "date_end", { target: { value: "2026-09-30" } });
    expect(refreshes).toBe(2);
    expect(wizard.state.form.name).toBe("India payroll · September 2026");
});

test("changing dates preserves the user's custom batch name", () => {
    const wizard = subject(); wizard.refreshWho = () => {};
    wizard.state.form.name = "August client comparison TEST";
    methods.onField.call(wizard, "date_start", { target: { value: "2026-09-01" } });
    expect(wizard.state.form.name).toBe("August client comparison TEST");
});

test("picking a scheme refreshes the employee preview as well as its gate", () => {
    const wizard = subject(); let refreshed = 0; let cleared = false;
    wizard.refreshWho = () => refreshed++;
    wizard._refreshGate = (clear) => { cleared = clear; };
    methods.pickScheme.call(wizard, card);
    expect(refreshed).toBe(1); expect(cleared).toBe(true);
});

test("scheme coverage is requested for the selected period", async () => {
    const wizard = subject(); let payload;
    wizard.orm = { silent: { call: async (model, method, args) => {
        payload = args[0]; return { covered: 27 };
    } } };
    await methods.refreshScheme.call(wizard);
    expect(payload).toEqual({ formula_config_id: 7, statuses: null,
        date_start: "2026-08-01", date_end: "2026-08-31" });
    expect(wizard.state.scheme.preview.covered).toBe(27);
});

test("a scheme without status filters still refreshes dated coverage", async () => {
    const wizard = subject(); let refreshed = 0;
    wizard.refreshScheme = async () => refreshed++;
    await methods.refreshWho.call(wizard);
    expect(refreshed).toBe(1);
});

test("status-filtered scope and scheme coverage refresh together", async () => {
    const wizard = subject(); let payload; let refreshed = 0;
    wizard.hasStatusFilter = true; wizard.chosenStatuses = ["Active"];
    wizard.state.who.search = "";
    wizard.orm = { call: async (model, method, args) => {
        payload = args[0]; return { total: 27 };
    } };
    wizard.refreshScheme = () => refreshed++;
    await methods.refreshWho.call(wizard);
    expect(payload).toEqual({ statuses: ["Active"], search: "", formula_config_id: 7,
        date_start: "2026-08-01", date_end: "2026-08-31" });
    expect(wizard.state.who.preview.total).toBe(27); expect(refreshed).toBe(1);
});

test("an older employee request cannot replace the newly selected period", async () => {
    const wizard = subject(); const replies = []; let refreshed = 0;
    wizard.hasStatusFilter = true; wizard.chosenStatuses = ["Active"];
    wizard.orm = { call: () => new Promise(resolve => replies.push(resolve)) };
    wizard.refreshScheme = () => refreshed++;
    const older = methods.refreshWho.call(wizard);
    wizard.state.form.date_start = "2026-09-01";
    const newer = methods.refreshWho.call(wizard);
    replies[1]({ total: 26 }); await newer;
    replies[0]({ total: 101 }); await older;
    expect(wizard.state.who.preview.total).toBe(26);
    expect(refreshed).toBe(1);
});

test("an older scheme request cannot replace the newly selected period", async () => {
    const wizard = subject(); const replies = [];
    wizard.orm = { silent: { call: () => new Promise(resolve => replies.push(resolve)) } };
    const older = methods.refreshScheme.call(wizard);
    wizard.state.form.date_start = "2026-09-01";
    const newer = methods.refreshScheme.call(wizard);
    replies[1]({ covered: 26 }); await newer;
    replies[0]({ covered: 27 }); await older;
    expect(wizard.state.scheme.preview.covered).toBe(26);
});

test("the selected scheme count uses this period, including an empty population", () => {
    const wizard = subject();
    wizard.state.who.picked = [];
    wizard.chosenScheme = { ...card, covered: 27 };
    const count = Object.getOwnPropertyDescriptor(PayrunWizard.prototype, "eligibleCount").get;
    wizard.state.scheme.preview = { covered: 26 };
    expect(count.call(wizard)).toBe(26);
    wizard.state.scheme.preview = { covered: 0 };
    expect(count.call(wizard)).toBe(0);
});
