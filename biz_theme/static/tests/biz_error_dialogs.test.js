/** @odoo-module **/
/**
 * MAPFIX Phase C — the non-developer view of an error carries nothing technical.
 *
 * These pin the three promises MF-C1 makes, none of which any server-side test
 * can see:
 *
 *   T1  developer mode OFF — no technical expander, no "Copy details", and no
 *       occurrence of the vendor word anywhere in the rendered dialog;
 *   T2  developer mode ON  — the expander is back (the affordance is
 *       deliberately kept) and its payload is brand-scrubbed;
 *   T3  the scrub happens in the COMPONENT, so it covers the registry-routed
 *       UserError path that never touches the fallback handlers — plus the two
 *       stock dialogs that are still reachable directly (WarningDialog with no
 *       title, RedirectWarningDialog).
 */
import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { click, queryAllTexts, queryText } from "@odoo/hoot-dom";
import {
    makeDialogMockEnv,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { WarningDialog } from "@web/core/errors/error_dialogs";

import { BizErrorDialog, stripOdoo } from "@biz_theme/js/biz_error_dialogs";

describe.current.tags("desktop");

const USER_ERROR_PROPS = {
    exceptionName: "odoo.exceptions.UserError",
    message: "Please specify the Primary Key Column to use for all worksheets.",
    name: "odoo.exceptions.UserError",
    traceback: "Traceback (most recent call last):\n  Odoo Server Error\n  boom",
    close() {},
};

async function mountBiz(props = {}) {
    const env = await makeDialogMockEnv();
    await mountWithCleanup(BizErrorDialog, {
        env,
        props: { ...USER_ERROR_PROPS, ...props },
    });
}

test("T1 — no developer mode: nothing technical is offered", async () => {
    patchWithCleanup(odoo, { debug: "" });
    await mountBiz();

    expect(".biz-err").toHaveCount(1);
    // the actionable sentence is still shown
    expect(".biz-err__message").toHaveText(USER_ERROR_PROPS.message);
    // ...and nothing else is
    expect(".biz-err__details").toHaveCount(0);
    expect(".biz-err__details-toggle").toHaveCount(0);
    expect(".biz-err__copy").toHaveCount(0);
    expect(queryAllTexts("footer button")).toEqual(["OK"]);
    expect(queryText(".biz-err")).not.toMatch(/odoo/i);
});

test("T2 — developer mode: the expander is kept and its payload is scrubbed", async () => {
    patchWithCleanup(odoo, { debug: "1" });
    await mountBiz();

    expect(".biz-err__details-toggle").toHaveCount(1);
    expect(".biz-err__copy").toHaveCount(1);
    await click(".biz-err__details-toggle");
    await animationFrame();
    const details = queryText(".biz-err__details-body");
    // technical identifiers survive (developers need them); the BRAND does not
    expect(details).toInclude("odoo.exceptions.UserError");
    expect(details).not.toMatch(/\bOdoo\s/);
});

test("T3a — the message is scrubbed on the registry-routed path", async () => {
    patchWithCleanup(odoo, { debug: "" });
    await mountBiz({ message: "Odoo Server Error: the sheet could not be read." });
    expect(".biz-err__message").toHaveText("Server Error: the sheet could not be read.");
});

test("T3b — a title-less WarningDialog never reads as branded", async () => {
    const env = await makeDialogMockEnv();
    await mountWithCleanup(WarningDialog, {
        env,
        props: { message: "This record cannot be saved.", close() {} },
    });
    expect(queryText(".modal-title")).toBe("Warning");
    expect(queryText(".modal")).not.toMatch(/odoo/i);
});

test("T3c — stripOdoo leaves technical identifiers alone", () => {
    expect(stripOdoo("Odoo Warning")).toBe("Warning");
    expect(stripOdoo("Odoo Server Error")).toBe("Server Error");
    expect(stripOdoo("An error whose details cannot be accessed by the Odoo framework has occurred.")).toBe(
        "An error whose details cannot be accessed by the framework has occurred."
    );
    expect(stripOdoo("odoo.exceptions.UserError")).toBe("odoo.exceptions.UserError");
    expect(stripOdoo(null)).toBe(null);
});
