/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// The current backend request always checks current permissions. Reloading
// also replaces the user service's cached group checks and every open hub.
registry.category("services").add("pb_access_refresh", {
    dependencies: ["bus_service", "notification", "orm"],
    async start(env, { bus_service: bus, notification, orm }) {
        let revision = await orm.call("pb.access", "access_revision", []).catch(() => null);
        let announced = false;
        let hasInput = false;
        window.addEventListener("input", () => { hasInput = true; }, { capture: true });
        bus.subscribe("pb_access_changed", ({ revision: next }) => {
            if (next === revision || announced) return;
            revision = next;
            announced = true;
            if (!hasInput && !document.querySelector(".o_form_dirty, .pbim-modal, .modal.show")) {
                window.location.reload();
                return;
            }
            // Preserve an unsaved form. A persistent, explicit refresh action
            // avoids silently discarding the user's work on another screen.
            notification.add(_t("Your access has changed. Refresh to load your updated screens."), {
                type: "info", sticky: true,
                buttons: [{ name: _t("Refresh screens"), primary: true,
                            onClick: () => window.location.reload() }],
            });
            env.bus.trigger("PB_SIDEBAR:RELOAD");
        });
        return {};
    },
});
