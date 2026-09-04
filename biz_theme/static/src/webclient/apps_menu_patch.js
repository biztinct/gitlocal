import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { NavBar } from "@web/webclient/navbar/navbar";

/**
 * Apps menu grid launcher — state + filtering behind the template inheritance
 * in apps_menu.xml. The stock dropdown markup is replaced by a searchable
 * icon grid; selection still flows through the stock
 * onNavBarDropdownItemSelection, so routing/hotkeys are untouched.
 */
patch(NavBar.prototype, {
    setup() {
        super.setup();
        this.vuApps = useState({ query: "" });
    },

    get vuFilteredApps() {
        const apps = this.menuService.getApps();
        const q = this.vuApps.query.trim().toLowerCase();
        if (!q) {
            return apps;
        }
        return apps.filter((app) => (app.name || "").toLowerCase().includes(q));
    },

    onNavBarDropdownItemSelection(menu) {
        this.vuApps.query = "";
        return super.onNavBarDropdownItemSelection(menu);
    },

    vuOnAppsSearchKeydown(ev) {
        if (ev.key === "Enter") {
            // Open the first matching app
            ev.preventDefault();
            ev.stopPropagation();
            const first = ev.target
                .closest(".vu-apps-panel")
                ?.querySelector(".vu-apps-item");
            first?.click();
        } else if (ev.key === "Escape" && this.vuApps.query) {
            // First Escape clears the filter; second one closes the dropdown
            ev.preventDefault();
            ev.stopPropagation();
            this.vuApps.query = "";
        }
    },
});
