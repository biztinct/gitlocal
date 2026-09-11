/** @odoo-module **/
/**
 * ERRORS E2-3 — the last moment before a toast is drawn.
 *
 * Seam 3 wraps the notification service so every message and title passes the
 * shared rewrite rules. It exists because seam 1 rewrites a translation
 * TEMPLATE and never its interpolated argument, which is exactly where the ~64
 * legacy `_('Error: %s') % str(e)` call sites put a raw Python failure.
 *
 * The brand here is the module default ("BizApp"): these tests run with no
 * <meta name="biz-brand"> in the document, which is what readBrand() falls back
 * to.
 */
import { describe, expect, test } from "@odoo/hoot";
import { markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { notificationService } from "@web/core/notifications/notification_service";

describe.current.tags("headless");

const BRAND = "BizApp";
let seq = 0;

/**
 * Start the (patched) notification service against a throwaway container, so
 * each test gets its own store and never collides with the real one.
 */
function startNotifications() {
    const key = `BizDebrandTestContainer${++seq}`;
    const service = notificationService.start.call(
        { notificationContainer: { name: key } },
        {},
        {}
    );
    const store = registry.category("main_components").get(key).props.notifications;
    return {
        service,
        last() {
            const all = Object.values(store);
            return all[all.length - 1];
        },
    };
}

test("N1 — a message naming the vendor is rewritten on its way to the screen", () => {
    const { service, last } = startNotifications();
    service.add("Error: Odoo is unable to merge the generated PDFs.");
    expect(last().props.message).toBe(
        `Error: ${BRAND} is unable to merge the generated PDFs.`
    );
});

test("N2 — the TITLE is rewritten too", () => {
    const { service, last } = startNotifications();
    service.add("The import stopped.", { title: "Odoo Import Error", type: "danger" });
    expect(last().props.title).toBe(`${BRAND} Import Error`);
    expect(last().props.type).toBe("danger");
});

test("N3 — a clean notification is untouched, object identity and all", () => {
    const { service, last } = startNotifications();
    const options = { title: "Pay run confirmed", type: "success" };
    service.add("Nothing to rewrite here.", options);
    expect(last().props.message).toBe("Nothing to rewrite here.");
    expect(last().props.title).toBe("Pay run confirmed");
});

test("N4 — a markup message is not flattened into a plain string", () => {
    const { service, last } = startNotifications();
    const html = markup("<b>Odoo</b> could not read the file");
    service.add(html);
    // Left exactly as handed over: a Markup is a String SUBCLASS carrying
    // already-escaped HTML, and flattening it would double-escape the page.
    expect(last().props.message).toBe(html);
    expect(typeof last().props.message).not.toBe("string");
});

test("N5 — both call shapes work: (message, options) and options-only", () => {
    const { service, last } = startNotifications();
    service.add("Odoo says no");
    expect(last().props.message).toBe(`${BRAND} says no`);

    service.add({ message: "Odoo says no again", title: "Odoo Warning" });
    expect(last().props.message.message).toBe(`${BRAND} says no again`);
    expect(last().props.message.title).toBe(`${BRAND} Warning`);
});

