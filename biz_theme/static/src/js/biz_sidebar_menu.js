/** @odoo-module **/
/**
 * biz_theme — zero-config, menu-driven left sidebar.
 *
 * Renders the current app's ir.ui.menu tree as a dark left sidebar (same
 * visual family as the Payobook pb_sidebar) without any custom records or
 * JavaScript in the consuming app:
 *
 *   level-2 menus WITH children  → collapsible sections
 *   level-2 menus without children → items in a leading section
 *   level-3+ menus               → items (deeper levels flattened)
 *
 * Group-based visibility is free: the menu service only ever receives the
 * menus the current user may see (ir.ui.menu groups_id, filtered server-side).
 *
 * Enablement: ir.config_parameter `biz_theme.menu_sidebar_apps` — comma
 * separated root-menu xml_ids (exposed via session_info). Empty = off.
 * Apps with a bespoke sidebar (e.g. pb_sidebar) simply aren't listed.
 */

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { user } from "@web/core/user";
import { WebClient } from "@web/webclient/webclient";
import {
    applySidebarMode,
    clearSidebarMode,
    getSidebarMode,
    toggleSidebarMode,
} from "@biz_theme/js/biz_sidebar_state";

// Lucide path data — keyword-matched to menu names, initial-letter fallback.
const ICON_PATHS = {
    home: "m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10",
    users: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M23 21v-2a4 4 0 0 0-3-3.87 M16 3.13a4 4 0 0 1 0 7.75 M12 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    calendar: "M8 2v4 M16 2v4 M3 10h18 M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z",
    settings: "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0z",
    file: "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z M14 2v4a2 2 0 0 0 2 2h4",
    chart: "M3 3v16a2 2 0 0 0 2 2h16 M18 17V9 M13 17V5 M8 17v-3",
    shield: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
    card: "M2 5h20v14H2z M2 10h20",
    package: "m7.5 4.27 9 5.15 M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.3 7l8.7 5 8.7-5 M12 22V12",
    clock: "M12 6v6l4 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z",
    zap: "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z",
    database: "M12 8c4.97 0 9-1.34 9-3s-4.03-3-9-3-9 1.34-9 3 4.03 3 9 3z M21 12c0 1.66-4 3-9 3s-9-1.34-9-3 M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5",
    dot: "M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
};

const ICON_KEYWORDS = [
    [/dash|overview|home/i, "home"],
    [/employee|people|user|member|team|contact|customer|partner/i, "users"],
    [/calendar|schedule|planning|shift|roster|leave|holiday/i, "calendar"],
    [/setting|config|technical|admin/i, "settings"],
    [/report|analytic|insight|statistic|chart/i, "chart"],
    [/document|file|payslip|invoice|form|template/i, "file"],
    [/security|access|role|compliance|statutory|tax|insurance/i, "shield"],
    [/pay|salary|wage|bank|account|payment|money|expense/i, "card"],
    [/product|inventory|stock|asset|package/i, "package"],
    [/time|attendance|timesheet|history|log/i, "clock"],
    [/run|action|automation|process|integration/i, "zap"],
    [/data|import|export|record|master/i, "database"],
];

export function iconForMenu(name) {
    for (const [re, icon] of ICON_KEYWORDS) {
        if (re.test(name || "")) {
            return ICON_PATHS[icon];
        }
    }
    return ICON_PATHS.dot;
}

export class BizSidebar extends Component {
    static template = "biz_theme.BizSidebar";
    static props = {};

    setup() {
        this.menuService = useService("menu");
        this.state = useState({
            activeId: null,
            collapsedSections: {},
        });
        this.uid = user.userId;
        this._loadSectionState();
        useBus(this.env.bus, "MENUS:APP-CHANGED", () => this._syncBody());
        this._syncBody();
        onWillUnmount(() => {
            document.body.classList.remove("biz-has-menu-sidebar");
            clearSidebarMode();
        });
    }

    get app() {
        return this.menuService.getCurrentApp();
    }

    get visible() {
        const apps = session.biz_menu_sidebar_apps || [];
        const app = this.app;
        // Never stack on screens owned by a bespoke sidebar (e.g. pb_sidebar)
        if (document.body.classList.contains("has-pb-sidebar")) {
            return false;
        }
        return !!(app && app.xmlid && apps.includes(app.xmlid));
    }

    /** [{ id, name, isSection, items: [{ id, name, iconPath }] }] */
    get sections() {
        const app = this.app;
        if (!app) {
            return [];
        }
        const tree = this.menuService.getMenuAsTree(app.id);
        const loose = [];
        const sections = [];
        for (const child of tree.childrenTree || []) {
            if ((child.childrenTree || []).length) {
                sections.push({
                    id: child.id,
                    name: child.name,
                    isSection: true,
                    items: this._flatten(child.childrenTree),
                });
            } else {
                loose.push(this._item(child));
            }
        }
        if (loose.length) {
            sections.unshift({
                id: "loose",
                name: app.name,
                isSection: sections.length > 0,
                items: loose,
            });
        }
        return sections;
    }

    _flatten(children) {
        const items = [];
        for (const child of children) {
            items.push(this._item(child));
            if ((child.childrenTree || []).length) {
                items.push(...this._flatten(child.childrenTree).map((i) => ({ ...i, sub: true })));
            }
        }
        return items;
    }

    _item(menu) {
        return {
            id: menu.id,
            name: menu.name,
            iconPath: iconForMenu(menu.name),
            sub: false,
        };
    }

    _syncBody() {
        document.body.classList.toggle("biz-has-menu-sidebar", this.visible);
        if (this.visible) {
            applySidebarMode(getSidebarMode(this.uid));
        }
    }

    onItemClick(item) {
        this.state.activeId = item.id;
        this.menuService.selectMenu(item.id);
    }

    toggleCollapse() {
        toggleSidebarMode(this.uid);
    }

    // ------------------------------------------------------------------
    // Section collapse (persisted per user + app)
    // ------------------------------------------------------------------
    get _sectionStorageKey() {
        const app = this.app;
        return `biz.sidebar.sections.${this.uid || "anon"}.${(app && app.xmlid) || "app"}`;
    }

    _loadSectionState() {
        try {
            const stored = window.localStorage.getItem(this._sectionStorageKey);
            if (stored) {
                this.state.collapsedSections = JSON.parse(stored);
            }
        } catch {
            this.state.collapsedSections = {};
        }
    }

    isSectionCollapsed(sectionId) {
        return !!this.state.collapsedSections[sectionId];
    }

    toggleSection(sectionId) {
        this.state.collapsedSections = {
            ...this.state.collapsedSections,
            [sectionId]: !this.state.collapsedSections[sectionId],
        };
        try {
            window.localStorage.setItem(
                this._sectionStorageKey,
                JSON.stringify(this.state.collapsedSections)
            );
        } catch {
            // private mode — collapse state just won't persist
        }
    }
}

patch(WebClient, {
    components: {
        ...WebClient.components,
        BizSidebar,
    },
});
