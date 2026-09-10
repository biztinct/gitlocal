/** @odoo-module **/
/**
 * The steps, MOUNTED — against a mocked `pb.blueprint.studio` and no server.
 *
 * Everything else in this suite is pure: a hundred and nine tests over the
 * words, the numbers and the rules that decide them. What a pure test cannot
 * see is the half of a screen that only exists in the DOM — that a disabled
 * button really is disabled, that a refusal is PRINTED rather than only
 * returned, that pressing a link asks the server for the right thing, and that
 * a component asked for by id actually opens.
 *
 * Two surfaces are mounted here: the Finish step (B6) and the Components tab
 * (B2's, which has waited four phases for this fixture). The fixture is
 * `blueprint_fixture.js` and it is deliberately small — no assertion below
 * depends on a number a server would have had to work out.
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAll, queryAllTexts, queryFirst } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { patchTranslations } from "@web/../tests/_framework/translation_test_helpers";
// `mountWithCleanup` boots the real service stack, and on a database with mail
// installed that stack reaches for `discuss.channel` before any component of
// ours renders. A test-bundle-only import; nothing in the addon knows mail
// exists.
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

import { StepFinish } from "@pb_blueprint/js/step_finish";
import { ComponentsTab } from "@pb_blueprint/js/components_tab";
import {
    componentsData, decision, finishData, mockStudio, reason,
} from "./blueprint_fixture";

describe.current.tags("desktop");
defineMailModels();
patchTranslations();

const NOOP = () => {};

async function mountFinish(handlers = {}, props = {}) {
    const calls = mockStudio(handlers);
    await mountWithCleanup(StepFinish, {
        props: {
            configId: 7, revision: 4, reloadKey: 0, runSignal: 0,
            onFinished: NOOP, onGo: NOOP, onGrid: NOOP, onDiscard: NOOP,
            onRevision: NOOP, onChanged: NOOP, ...props,
        },
    });
    await animationFrame();
    return calls;
}

// ==================================================================
describe("the Finish step, mounted", () => {

    test("it draws the tiles, the identity and the optional tasks", async () => {
        await mountFinish();
        // The three tiles count UP, so the digits mid-flight are not the claim:
        // that all three are on screen with a label of their own is.
        expect(".pbbp-fintile").toHaveCount(3);
        expect(queryAllTexts(".pbbp-fintile-l")).toEqual(
            ["Pay components", "Formula rules", "Inputs"]);

        const rows = queryAllTexts(".pbbp-sum dt");
        expect(rows).toInclude("Payday");
        expect(rows).toInclude("Inputs close on");
        expect(rows).toInclude("Bank identifier");
        expect(queryAllTexts(".pbbp-sum dd")).toInclude(
            "The last working day of the month");

        // Three optional tasks, each with a word of its own.
        expect(".pbbp-fin-opt li").toHaveCount(3);
        expect(queryAllTexts(".pbbp-fin-opt .pbbp-cn-pill")).toEqual(
            ["Done", "Skipped", "Already in place"]);
    });

    test("nothing is waiting for a decision, and it says so in a sentence",
         async () => {
        await mountFinish();
        expect(".pbbp-fin-dec").toHaveCount(0);
        expect(queryFirst(".pbim-empty.is-slim").textContent).toInclude(
            "Nothing is waiting for a decision");
    });

    test("an open decision is listed, counted, and has a door", async () => {
        const calls = await mountFinish({
            bp_finish_data: () => finishData({
                decisions: [decision(), decision({ key: "sample-9", kind: "scenario",
                    title: "Joined mid-month", code: "", rule_id: 0,
                    step: "test", tab: "", text: "Nobody has agreed to these numbers.",
                    action: "Go to Test" })],
                decisions_total: 5,
            }),
        });
        expect(".pbbp-fin-dec li").toHaveCount(2);
        expect(queryFirst(".pbbp-fin-open").textContent).toBe("5 open");
        // The list was cut, and it says so rather than pretending it was all.
        expect(queryAllTexts(".pbim-note").join(" ")).toInclude("3 more decisions");
        void calls;
    });

    test("pressing a decision's door names the step that settles it", async () => {
        const went = [];
        await mountFinish({
            bp_finish_data: () => finishData({
                decisions: [decision()], decisions_total: 1,
            }),
        }, { onGo: (step, opts) => went.push([step, opts]) });
        await click(".pbbp-fin-dec li .pbim-btn");
        await animationFrame();
        expect(went).toHaveLength(1);
        expect(went[0][0]).toBe("rules");
        expect(went[0][1].tab).toBe("components");
        expect(went[0][1].ruleId).toBe(42);
    });

    test("a blocked gate disables the button AND prints every reason",
         async () => {
        await mountFinish({
            bp_finish_data: () => finishData({
                gate: { ok: false, reasons: [reason(), reason({
                    code: "failed", text: "2 checks need attention.",
                    action: "Go to Test" })] },
            }),
        });
        expect(".pbbp-fin-cta-b .pbim-btn.primary").toHaveProperty("disabled", true);
        // Printed on the page, beside the button that refused — never only in
        // a toast, which is a reason a person cannot re-read.
        expect(".pbbp-fin-block li").toHaveCount(2);
        expect(queryAllTexts(".pbbp-fin-block li").join(" ")).toInclude(
            "2 checks need attention.");
        expect(queryFirst(".pbbp-card.is-block h2").textContent)
            .toBe("2 things to fix before you can finish");
    });

    test("a ready gate finishes, and tells the shell to open the configuration",
         async () => {
        const done = [];
        const calls = await mountFinish({}, { onFinished: (id) => done.push(id) });
        await click(".pbbp-fin-cta-b .pbim-btn.primary");
        await animationFrame();
        expect(calls.map((c) => c[0])).toInclude("bp_finish");
        expect(done).toEqual([7]);
    });

    test("a refusal from the server is shown on the page, not swallowed",
         async () => {
        await mountFinish({
            bp_finish: () => ({ ok: false, reason: "The checks have not been run yet.",
                                gate: { ok: false, reasons: [reason({
                                    code: "not_run",
                                    text: "The checks have not been run yet." })] } }),
        });
        await click(".pbbp-fin-cta-b .pbim-btn.primary");
        await animationFrame();
        expect(queryFirst(".pbbp-fin-cta-t .pbbp-err").textContent)
            .toBe("The checks have not been run yet.");
    });

    test("a finished setup reads back, and offers to be revisited", async () => {
        const calls = await mountFinish({
            bp_finish_data: () => finishData({
                finished: true, state: "finished",
                identity: { ...finishData().identity,
                            finished_by: "Mai", finished_at: "2026-09-10 09:00:00" },
            }),
        });
        expect(".pbbp-fin-done").toHaveCount(1);
        expect(queryFirst(".pbbp-fin-done b").textContent).toBe("Setup complete");
        expect(queryFirst(".pbbp-fin-cta-b .pbim-btn.primary").textContent.trim())
            .toBe("Open the configuration");

        // "Revisit the setup" sits beside the primary button, and there is
        // exactly ONE of it: it was drawn twice on the first build (once in the
        // banner, once here), which is two answers to the same question.
        expect(".pbbp-fin-cta-b .pbbp-changelink").toHaveCount(1);
        await click(".pbbp-fin-cta-b .pbbp-changelink");
        await animationFrame();
        expect(calls.map((c) => c[0])).toInclude("bp_reopen");
    });

    test("a page that cannot be read says so, and offers to try again",
         async () => {
        await mountFinish({
            bp_finish_data: () => ({ ok: false,
                reason: "That configuration no longer exists." }),
        });
        expect(".pbbp-alert.is-err").toHaveCount(1);
        expect(queryFirst(".pbbp-alert.is-err p").textContent)
            .toBe("That configuration no longer exists.");
        expect(".pbbp-fin-cta-b").toHaveCount(0);
    });
});

// ==================================================================
describe("the Components tab, mounted", () => {

    async function mountComponents(handlers = {}, props = {}) {
        const calls = mockStudio(handlers);
        await mountWithCleanup(ComponentsTab, {
            props: {
                configId: 7, revision: 4, sampleId: 5, sampleName: "Full month",
                currency: "VND", reloadKey: 0, search: "",
                openRule: 0, openTick: 0,
                onChanged: NOOP, onRevision: NOOP, onGrid: NOOP, ...props,
            },
        });
        await animationFrame();
        return calls;
    }

    test("every component is a row that says what it does", async () => {
        await mountComponents();
        expect(".pbbp-cmp-row").toHaveCount(3);
        const subs = queryAllTexts(".pbbp-cmp-sub");
        expect(subs[0]).toInclude("Contract salary");
        expect(subs[1]).toInclude("Written as Excel");
        // A rule somebody typed is badged as theirs, and a rule with an
        // unanswered question is not badged as ready.
        expect(queryAllTexts(".pbbp-cmp-badge")).toInclude("Written as Excel");
    });

    test("nothing matches a search, and the answer quotes what was typed",
         async () => {
        await mountComponents({}, { search: "zzzz" });
        expect(".pbbp-cmp-row").toHaveCount(0);
        expect(queryFirst(".pbbp-cmp-empty").textContent).toInclude("zzzz");
    });

    test("a component asked for by id opens its editor, and only that one",
         async () => {
        const calls = await mountComponents({
            bp_component_get: () => ({ ok: false,
                reason: "That component no longer exists." }),
        }, { openRule: 13, openTick: 1 });
        await animationFrame();
        const asked = calls.filter((c) => c[0] === "bp_component_get");
        expect(asked).toHaveLength(1);
        expect(asked[0][1]).toEqual([13]);
        // And the sheet is on screen with the server's own words in it.
        expect(".pbbp-se").toHaveCount(1);
        expect(queryFirst(".pbbp-se-boot.is-stop p").textContent)
            .toBe("That component no longer exists.");
    });

    test("nothing opens when nobody asked for a component", async () => {
        const calls = await mountComponents();
        expect(".pbbp-se").toHaveCount(0);
        expect(calls.filter((c) => c[0] === "bp_component_get")).toHaveLength(0);
    });

    test("a configuration with nothing in it is not told to search harder",
         async () => {
        await mountComponents({
            bp_components: () => componentsData({
                groups: { earning: [], deduction: [], benefit: [], helper: [],
                          total: [] },
                counts: { included: 0, removed: 0 },
            }),
        });
        expect(".pbbp-cmp-row").toHaveCount(0);
        const empty = queryFirst(".pbbp-cmp-empty").textContent;
        expect(empty).not.toInclude("matches");
        expect(queryAll(".pbbp-cmp-row")).toHaveLength(0);
    });
});
