/** @odoo-module **/
/**
 * R23 (FS-7) — when anybody publishes a Form builder screen, this browser
 * forgets the screen designs it keeps (the web client caches every form's
 * design on disk), so "Full details" and the full contract form show a
 * hidden or renamed standard field the next time they open, without a page
 * reload. The open host screens re-read themselves through `useFormStudio`.
 */
import { registry } from "@web/core/registry";
import { rpcBus } from "@web/core/network/rpc";

export const formStudioViewsService = {
    dependencies: ["bus_service"],
    start(env, { bus_service }) {
        bus_service.subscribe("pb_form_studio/published", () => {
            rpcBus.trigger("CLEAR-CACHES", "get_views");
        });
    },
};

registry.category("services").add("pb_form_studio_views", formStudioViewsService);
