/** @odoo-module **/
/**
 * SCHEMECTX P3 — edit mode, in the DOM and in the pure helpers.
 *
 * Two halves, for the same reason the rest of this suite has two halves. The
 * pure half proves the sentences and the ordering without a server. The
 * mounted half proves the things only the DOM can say: that the starter cards
 * are GONE on a configuration that already exists, that the country really is
 * locked rather than merely marked locked, that the lanes reorder from the
 * keyboard, and that the page which closes an edit says what changed.
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, press, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { patchTranslations } from "@web/../tests/_framework/translation_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import { StepStart } from "@pb_blueprint/js/step_start";
import {
    SettingsCards, StepSaved, laneOrder, laneSentence, laneWarnings,
    settingLabel, settingsGroupFor,
} from "@pb_blueprint/js/edit_cards";

describe.current.tags("desktop");
defineMailModels();
patchTranslations();

const NOOP = () => {};

function startProps(over = {}) {
    return {
        form: { name: "Rize Vietnam Payroll", country_code: "VN",
                cycle_type: "regular", effective_from: "2026-09-01",
                template_key: "" },
        situations: { audiences: ["local"], reallife: [] },
        starters: {
            ok: true, country: "VN", has_template: true,
            currencies: { VN: { name: "VND", symbol: "₫" },
                          IN: { name: "INR", symbol: "₹" } },
            fx_hint: {},
            starters: [{ key: "vn_complete_2026", kind: "template",
                         name: "Vietnam · Complete", desc: "Everything",
                         certified: true, version: "2026.1",
                         component_count: 37, rate_table_count: 1 }],
        },
        countries: [{ code: "VN", label: "Vietnam" },
                    { code: "IN", label: "India" }],
        cycles: [{ value: "regular", label: "Regular payroll" }],
        company: "Rize Vietnam",
        created: true,
        mode: "edit",
        builtFrom: "Built in the components grid",
        countryLocked: true,
        countryLockReason: "This configuration has already paid people, so its country cannot be changed.",
        busy: false,
        progress: [],
        onSet: NOOP, onPickStarter: NOOP, onToggleAudience: NOOP,
        onToggleReallife: NOOP, onUnlock: NOOP, onRetry: NOOP,
        ...over,
    };
}

function settingsProps(over = {}) {
    return {
        group: "connect",
        values: {
            connector_id: false, payroll_journal_id: false,
            debit_account_id: false, credit_account_id: false,
            source_priority: "api,excel,records",
            source_api_enabled: true, source_excel_enabled: true,
            source_records_enabled: false,
        },
        meta: {
            connectors: [{ id: 3, name: "Rize HR" }],
            journals: [{ id: 9, name: "Payroll journal" }],
            accounts: [{ id: 41, name: "6420 Staff costs" }],
            components: [{ id: 11, col: "A", code: "BASICPAY", name: "Basic pay" }],
            proration_bases: [{ value: "calendar", label: "Calendar Days" }],
            source_lane_counts: { api: 4, excel: 12, records: 6 },
        },
        locks: { pay_logic: true, country: false },
        mode: "edit",
        busy: false,
        error: "",
        onSet: NOOP, onCommit: NOOP,
        ...over,
    };
}

// ==================================================================
describe("the pure helpers", () => {

    test("each step owns the settings that belong to it", () => {
        expect(settingsGroupFor("start")).toBe("advanced");
        expect(settingsGroupFor("rules")).toBe("automation");
        expect(settingsGroupFor("connect")).toBe("connect");
        // Outputs, Test and Finish carry none: a settings card on the page
        // that reports what was built is a card in the wrong conversation.
        expect(settingsGroupFor("outputs")).toBe("");
        expect(settingsGroupFor("test")).toBe("");
        expect(settingsGroupFor("finish")).toBe("");
    });

    test("a stored order is always three lanes, whatever was stored", () => {
        expect(laneOrder("records,api,excel")).toEqual(["records", "api", "excel"]);
        // A half-written value, a lane that was dropped, and nothing at all:
        // all three have to come back as a complete order or the screen shows
        // two lanes and silently loses the third.
        expect(laneOrder("records")).toEqual(["records", "api", "excel"]);
        expect(laneOrder("")).toEqual(["api", "excel", "records"]);
        expect(laneOrder("nonsense,excel")).toEqual(["excel", "api", "records"]);
    });

    test("the sentence changes meaning when records win", () => {
        const lanes = (order, off = []) => laneOrder(order).map((key, i) => ({
            key, rank: i + 1, count: 0, on: !off.includes(key),
            label: key, sub: "",
        }));
        expect(laneSentence(lanes("records,api,excel")))
            .toInclude("never overwritten");
        expect(laneSentence(lanes("api,excel,records")))
            .toInclude("only where every higher one is silent");
        expect(laneSentence(lanes("api,excel,records", ["api", "excel", "records"])))
            .toInclude("Every source is off");
    });

    test("switching a lane off says what falls through, counted", () => {
        const lanes = [
            { key: "api", on: false, count: 4, label: "Connected system" },
            { key: "excel", on: false, count: 0, label: "Spreadsheet" },
            { key: "records", on: true, count: 6, label: "Payobook records" },
        ];
        const warnings = laneWarnings(lanes);
        // Only the lane that is BOTH off and actually feeding something. A
        // warning about a lane nothing reads is a warning people learn to
        // ignore.
        expect(warnings).toHaveLength(1);
        expect(warnings[0]).toInclude("Connected system");
    });

    test("every field a change is reported under has a name people read", () => {
        expect(settingLabel("payroll_journal_id")).toBe("Payroll journal");
        expect(settingLabel("use_proration")).toBe("Part-month pay");
        expect(settingLabel("source_priority")).toBe("Which source wins");
        // Never the field name itself, for anything the cards can change.
        expect(settingLabel("retro_component_id")).not.toBe("retro_component_id");
    });
});

// ==================================================================
describe("the Start step in edit mode", () => {

    test("the starter cards are gone and Built from takes their place", async () => {
        await mountWithCleanup(StepStart, { props: startProps() });
        await animationFrame();
        expect(".pbbp-starters").toHaveCount(0);
        expect(".pbbp-builtfrom").toHaveCount(1);
        expect(queryAllTexts(".pbbp-builtfrom .pbbp-card-head p"))
            .toEqual(["Built in the components grid"]);
    });

    test("a country that has paid somebody is locked, and says why", async () => {
        await mountWithCleanup(StepStart, { props: startProps() });
        await animationFrame();
        expect("#pbbp-country").toHaveCount(0);
        expect(".pbbp-locked").toHaveCount(1);
        // No "Change" link: it would lead to a refusal, which is a dead end.
        expect(".pbbp-changelink").toHaveCount(0);
        expect(queryFirst(".pbbp-lockwhy").textContent)
            .toInclude("already paid people");
    });

    test("a country nobody has been paid under is still a choice", async () => {
        await mountWithCleanup(StepStart, {
            props: startProps({ countryLocked: false, countryLockReason: "" }),
        });
        await animationFrame();
        expect("#pbbp-country").toHaveCount(1);
        expect(".pbbp-lockwhy").toHaveCount(0);
    });

    test("the money chip still answers, in edit mode too", async () => {
        await mountWithCleanup(StepStart, { props: startProps() });
        await animationFrame();
        expect(queryFirst(".pbbp-money-chip").textContent).toInclude("₫ VND");
    });
});

// ==================================================================
describe("the settings cards", () => {

    test("edit mode opens them; create mode folds them away", async () => {
        await mountWithCleanup(SettingsCards, { props: settingsProps() });
        await animationFrame();
        expect(".pbbp-setgrp-body").toHaveCount(1);
        expect(".pbbp-lane").toHaveCount(3);
    });

    test("a new configuration gets the same cards, folded", async () => {
        await mountWithCleanup(SettingsCards, {
            props: settingsProps({ mode: "create" }),
        });
        await animationFrame();
        expect(".pbbp-setgrp-body").toHaveCount(0);
        await click(".pbbp-setgrp-head");
        await animationFrame();
        expect(".pbbp-setgrp-body").toHaveCount(1);
    });

    test("the lanes are ranked and a lane that is off says so", async () => {
        await mountWithCleanup(SettingsCards, { props: settingsProps() });
        await animationFrame();
        expect(queryAllTexts(".pbbp-lane-rank")).toEqual(["1", "2", "3"]);
        expect(".pbbp-lane.is-off").toHaveCount(1);
        // Records are off and six components read them: that has to be said.
        expect(queryAllTexts(".pbbp-note.is-warn").join(" "))
            .toInclude("Payobook records");
    });

    test("a lane reorders from the keyboard alone", async () => {
        const saved = [];
        await mountWithCleanup(SettingsCards, {
            props: settingsProps({
                onSet: (field, value) => saved.push([field, value]),
            }),
        });
        await animationFrame();
        // Focus the second lane and press the up arrow: no mouse anywhere.
        const lanes = document.querySelectorAll(".pbbp-lane");
        lanes[1].focus();
        await press("ArrowUp");
        await animationFrame();
        expect(saved).toHaveLength(1);
        expect(saved[0]).toEqual(["source_priority", "excel,api,records"]);
    });

    test("part-month pay will not be switched on with nothing to prorate", async () => {
        const committed = [];
        await mountWithCleanup(SettingsCards, {
            props: settingsProps({
                group: "automation",
                values: { use_proration: true, proration_component_ids: [],
                          proration_rounding: 2, use_auto_retro: false },
                onCommit: (fields) => committed.push(fields),
            }),
        });
        await animationFrame();
        expect(queryAllTexts(".pbbp-note.is-warn").join(" "))
            .toInclude("at least one component");
        // Picking the first component sends the PAIR, because the engine
        // refuses the toggle on its own (SC12).
        await click(".pbbp-chip-btn");
        await animationFrame();
        expect(committed).toHaveLength(1);
        expect(committed[0]).toEqual(["use_proration", "proration_component_ids"]);
    });
});

// ==================================================================
describe("the page that closes an edit", () => {

    test("it lists what changed, from what, to what", async () => {
        await mountWithCleanup(StepSaved, {
            props: {
                changes: [
                    { field: "payroll_journal_id", label: "Payroll journal",
                      before: "Not set", after: "Payroll journal" },
                    { field: "use_proration", label: "Part-month pay",
                      before: "Not set", after: "On" },
                ],
                configName: "Rize Vietnam Payroll",
                schemeState: "active", schemeStateLabel: "Active",
                locks: { pay_logic: true },
                busy: false, onSave: NOOP, onGrid: NOOP,
            },
        });
        await animationFrame();
        expect(".pbbp-changes tbody tr").toHaveCount(2);
        expect(queryAllTexts(".pbbp-changes .pbbp-now"))
            .toEqual(["Payroll journal", "On"]);
        // The one reassurance somebody editing a live configuration needs.
        expect(queryAllTexts(".pbbp-note").join(" "))
            .toInclude("Nothing about what people are paid was touched");
    });

    test("a sitting that changed nothing says exactly that", async () => {
        await mountWithCleanup(StepSaved, {
            props: {
                changes: [], configName: "Rize India Payroll",
                schemeState: "draft", schemeStateLabel: "Draft",
                locks: {}, busy: false, onSave: NOOP, onGrid: NOOP,
            },
        });
        await animationFrame();
        expect(".pbbp-changes").toHaveCount(0);
        expect(queryAllTexts(".pbim-empty b")).toEqual(["Nothing changed"]);
    });
});
