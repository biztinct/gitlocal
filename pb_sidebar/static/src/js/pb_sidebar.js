/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount, markup } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";

// ---- Lucide icon set (inline SVG paths; matches the Payobook POC) ----
const ICONS = {
    home:'<path d="M3 9.2 12 3l9 6.2"/><path d="M5 10v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V10"/><path d="M9 21v-6h6v6"/>',
    calendar:'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    receipt:'<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    zap:'<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    download:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    file:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "file-text":'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8M16 17H8M10 9H8"/>',
    calculator:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M8 6h8"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/>',
    layers:'<path d="m12 2 9 4.5-9 4.5-9-4.5L12 2Z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 17 9 4.5 9-4.5"/>',
    shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
    percent:'<line x1="19" x2="5" y1="5" y2="19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
    "trending-up":'<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "clipboard-check":'<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
    lock:'<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    building:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
    database:'<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    compass:'<circle cx="12" cy="12" r="10"/><polygon points="16.2 7.8 14.1 14.1 7.8 16.2 9.9 9.9 16.2 7.8"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    circle:'<circle cx="12" cy="12" r="9"/>',
};

export class PbSidebar extends Component {
    static template = "pb_sidebar.PbSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");

        const name = window.odoo?.session_info?.name || "User";
        this.userName = name;
        this.userInitials = name.split(" ").filter(Boolean).map(p => p[0]).join("")
            .substring(0, 2).toUpperCase() || "U";

        this.state = useState({
            sections: [],
            activeItemId: null,
            expandedItems: {},
            loaded: false,
        });

        this._xmlidIndex = {};
        this._tagIndex = {};
        this._modelIndex = {};
        this._childParent = {};
        this._homeAction = null;

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._resolveActive());

        onMounted(async () => {
            document.body.classList.add("has-pb-sidebar");
            await this._load();
            this._resolveActive();
        });
        onWillUnmount(() => document.body.classList.remove("has-pb-sidebar"));
    }

    iconSvg(name) {
        const path = ICONS[name] || ICONS.circle;
        return markup(`<svg class="pb-ic" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`);
    }

    async _load() {
        const data = await this.orm.call("pb.sidebar.item", "get_sidebar_data", []);
        this.state.sections = data;
        this.state.loaded = true;
        this._buildIndex();
    }

    _buildIndex() {
        this._xmlidIndex = {}; this._tagIndex = {}; this._modelIndex = {}; this._childParent = {};
        const idx = (item) => {
            if (item.action_xmlid) this._xmlidIndex[item.action_xmlid] = item.id;
            if (item.action_tag) this._tagIndex[item.action_tag] = item.id;
            for (const x of item.match_action_xmlids || []) this._xmlidIndex[x] = item.id;
            for (const t of item.match_action_tags || []) this._tagIndex[t] = item.id;
            for (const m of item.match_models || []) this._modelIndex[m] = item.id;
            if (!this._homeAction && item.action_xmlid) this._homeAction = item.action_xmlid;
        };
        for (const s of this.state.sections) {
            for (const item of s.items) {
                idx(item);
                for (const c of item.children || []) { idx(c); this._childParent[c.id] = item.id; }
            }
        }
    }

    _resolveActive() {
        const ctrl = this.actionService.currentController;
        if (!ctrl || !ctrl.action) return;
        const a = ctrl.action;
        let found;
        if (a.xml_id && this._xmlidIndex[a.xml_id] !== undefined) found = this._xmlidIndex[a.xml_id];
        else if (a.tag && this._tagIndex[a.tag] !== undefined) found = this._tagIndex[a.tag];
        else if (a.res_model && this._modelIndex[a.res_model] !== undefined) found = this._modelIndex[a.res_model];
        if (found !== undefined) {
            this.state.activeItemId = found;
            const pid = this._childParent[found];
            if (pid !== undefined && !this.state.expandedItems[pid]) {
                this.state.expandedItems = { ...this.state.expandedItems, [pid]: true };
            }
        }
    }

    onItemClick(item) {
        if (item.children && item.children.length) {
            this.state.expandedItems = { ...this.state.expandedItems, [item.id]: !this.state.expandedItems[item.id] };
        } else {
            this.navigateTo(item);
        }
    }

    navigateTo(item) {
        this.state.activeItemId = item.id;
        const ref = item.action_xmlid || item.action_tag;
        if (ref) this.actionService.doAction(ref, { clearBreadcrumbs: true });
    }

    navigateHome() {
        if (this._homeAction) this.actionService.doAction(this._homeAction, { clearBreadcrumbs: true });
        else window.location.href = "/odoo";
    }

    isActive(id) { return this.state.activeItemId === id; }
    isExpanded(id) { return !!this.state.expandedItems[id]; }
}
