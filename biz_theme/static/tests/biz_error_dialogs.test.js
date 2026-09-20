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
import { registry } from "@web/core/registry";

import {
    BizErrorDialog,
    bizRpcFallbackHandler,
    stripOdoo,
} from "@biz_theme/js/biz_error_dialogs";
import { RPCError } from "@web/core/network/rpc";
import { UncaughtPromiseError } from "@web/core/errors/error_service";

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

// ---------------------------------------------------------------------------
// ERRORS E2-1 — on the portal the calm dialog must win over the stock toast.
//
// The frontend bundle carries web/static/src/public/error_notifications.js,
// which core's rpcErrorHandler consults BEFORE the dialog registry. Every name
// we claim has to be off it, or the visitor gets a notification titled "Odoo
// Session Expired" and none of the work above is ever reached.
// ---------------------------------------------------------------------------
const BIZ_CLAIMED = [
    "odoo.http.SessionExpiredException",
    "werkzeug.exceptions.Forbidden",
    "504",
    "odoo.exceptions.AccessError",
    "odoo.exceptions.AccessDenied",
    "odoo.exceptions.UserError",
    "odoo.exceptions.ValidationError",
    "odoo.exceptions.MissingError",
];

test("E1 — every name we draw a dialog for is off the notification registry", () => {
    const notifications = registry.category("error_notifications");
    const dialogs = registry.category("error_dialogs");
    for (const name of BIZ_CLAIMED) {
        expect(notifications.contains(name)).toBe(false, {
            message: `${name} would still be shown as a plain toast`,
        });
        expect(dialogs.get(name)).toBe(BizErrorDialog, {
            message: `${name} is no longer routed to the calm dialog`,
        });
    }
});

test("E2 — a notification key we do NOT claim is left to notify", () => {
    // The removal has to be by name. Anything else registered for a toast —
    // MailDeliveryException, a third-party module — must still get one, which
    // means our fallback handler stands down and core's takes over.
    const notifications = registry.category("error_notifications");
    notifications.add("third.party.Boom", { title: "Boom", type: "warning" });
    const env = {
        services: {
            dialog: { add: () => expect.step("dialog") },
            notification: { add: () => expect.step("notification") },
        },
    };
    const { error, originalError } = rpcPair("third.party.Boom");
    expect(bizRpcFallbackHandler(env, error, originalError)).toBe(false, {
        message: "we stole a notification key that was not ours",
    });
    expect.verifySteps([]);
    notifications.remove("third.party.Boom");
});

/** Build the (error, originalError) pair core's handlers are called with. */
function rpcPair(exceptionName) {
    const originalError = new RPCError("boom");
    originalError.exceptionName = exceptionName;
    originalError.data = { message: "boom", arguments: ["boom"], context: {} };
    originalError.code = 200;
    const error = new UncaughtPromiseError();
    error.unhandledRejectionEvent = { preventDefault() {} };
    return { error, originalError };
}

test("E3 — a session-expired error opens the calm dialog, and adds no toast", async () => {
    const opened = [];
    const toasted = [];
    const env = {
        services: {
            dialog: { add: (Component, props) => opened.push({ Component, props }) },
            notification: { add: (message) => toasted.push(message) },
        },
    };
    for (const name of ["odoo.http.SessionExpiredException", "werkzeug.exceptions.Forbidden"]) {
        const { error, originalError } = rpcPair(name);
        expect(bizRpcFallbackHandler(env, error, originalError)).toBe(true, {
            message: `${name} was not handled by our fallback`,
        });
    }
    expect(opened.length).toBe(2);
    expect(opened.every((o) => o.Component === BizErrorDialog)).toBe(true);
    expect(toasted.length).toBe(0);
});

test("E4 — the calm session screen says our sentence and offers a way back in", async () => {
    patchWithCleanup(odoo, { debug: "" });
    await mountBiz({
        exceptionName: "odoo.http.SessionExpiredException",
        message: "Your Odoo session expired. The current page is about to be refreshed.",
        name: "odoo.http.SessionExpiredException",
    });
    expect(queryText(".biz-err__title")).toBe("Your session ended");
    expect(queryAllTexts("footer button")).toEqual(["Sign in again"]);
    expect(queryText(".biz-err")).not.toMatch(/odoo/i);
    // Nothing technical on a session screen, in any mode.
    expect(".biz-err__details-toggle").toHaveCount(0);
});
