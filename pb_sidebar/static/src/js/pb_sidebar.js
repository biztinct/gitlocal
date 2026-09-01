/** @odoo-module **/

import { Component, useState, onMounted, onWillUnmount, markup } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import {
    applySidebarMode,
    clearSidebarMode,
    getSidebarMode,
    toggleSidebarMode,
} from "@biz_theme/js/biz_sidebar_state";

// ---- Lucide icon set (inline SVG paths; matches the Payobook POC) ----
const ICONS = {
    home:'<path d="M3 9.2 12 3l9 6.2"/><path d="M5 10v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V10"/><path d="M9 21v-6h6v6"/>',
    calendar:'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
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
    // ---- Sudima field-HR program icons (phases A–E; shield already above) ----
    "map-pin":'<path d="M20 10c0 4.4-8 12-8 12s-8-7.6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    truck:'<path d="M14 18V6a1 1 0 0 0-1-1H2v13"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.62l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    table:'<path d="M12 3v18"/><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/>',
    plane:'<path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z"/>',
    scan:'<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
    // ---- Phase F (Pay & Deliver) ----
    send:'<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    landmark:'<path d="M10 18v-7M14 18v-7M6 18v-7M18 18v-7M4 22h16M12 2 2 7h20z"/>',
    // ---- Workforce redesign P1b (the Option-A rail) ----
    // The rail's icon set is FIXED and inline: a name that is not here renders
    // as a plain circle, silently. Every `icon` value a pb.sidebar.item record
    // ships must exist in this object.
    activity:'<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
    umbrella:'<path d="M22 12a10.06 10.06 0 0 0-20 0Z"/><path d="M12 12v8a2 2 0 0 0 4 0"/><path d="M12 2v1"/>',
    inbox:'<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    // ---- IA redesign Cycle 5 (the rail cutover) ----
    // GROW > Learn. The Journey's leaf used `compass` while Workforce's Mission
    // Control used it too; on a five-section rail the two sat four rows apart
    // drawn identically. This set is CLOSED — a name that is not in it renders a
    // plain circle with no error anywhere — so a new icon on a rail item is
    // always two edits, and `test_every_rail_icon_exists_in_the_fixed_set` is
    // what catches the second one being forgotten.
    "book-open":'<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    // ---- Phase J (Audit & Compliance) ----
    "scroll-text":'<path d="M15 12h-5"/><path d="M15 8h-5"/><path d="M19 17V5a2 2 0 0 0-2-2H4"/><path d="M8 21h12a2 2 0 0 0 2-2v-1a1 1 0 0 0-1-1H11a1 1 0 0 0-1 1v1a2 2 0 1 1-4 0V5a2 2 0 1 0-4 0v2a1 1 0 0 0 1 1h3"/>',
    // ---- RIZE P0 (Employee Lifecycle) ----
    // OPERATE > Lifecycle. Lucide `refresh-cw`: a cycle, which is what a
    // lifecycle is, and visibly different from `rotate`/`activity` at 20px.
    // Added HERE and nowhere else — this set is CLOSED, a name that is not in
    // it renders a plain circle with no error anywhere, and
    // `test_every_rail_icon_exists_in_the_fixed_set` is what catches a rail
    // item shipping without its path.
    "refresh-cw":'<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
};

// App (root-menu) xmlids that own the Payobook sidebar. In any other app the
// sidebar hides and Odoo's native top menus return.
const PAYROLL_APPS = new Set([
    "om_hr_payroll.menu_hr_payroll_root",
    "pb_hr_payroll_base.menu_payroll_backup_root",
]);

export class PbSidebar extends Component {
    static template = "pb_sidebar.PbSidebar";
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.menuService = useService("menu");
        this.dialog = useService("dialog");

        const name = user.name || window.odoo?.session_info?.name || "User";
        this.userName = name;
        this.userInitials = name.split(" ").filter(Boolean).map(p => p[0]).join("")
            .substring(0, 2).toUpperCase() || "U";

        this.state = useState({
            sections: [],
            activeItemId: null,
            expandedItems: {},
            collapsedSections: this._loadCollapsed(),
            loaded: false,
            visible: false,
        });

        this._xmlidIndex = {};
        this._tagIndex = {};
        this._modelIndex = {};
        this._childParent = {};
        this._itemSection = {};
        this._homeAction = null;

        useBus(this.env.bus, "ACTION_MANAGER:UI-UPDATED", () => this._onUiUpdated());

        this.uid = user.userId;

        onMounted(async () => {
            applySidebarMode(getSidebarMode(this.uid));
            await this._load();
            this._onUiUpdated();
        });
        onWillUnmount(() => {
            document.body.classList.remove("has-pb-sidebar");
            clearSidebarMode();
        });
    }

    // Pin/unpin the icon rail (biz_theme behavior layer; persisted per user)
    toggleCollapse() {
        toggleSidebarMode(this.uid);
    }

    _onUiUpdated() {
        this._resolveVisibility();
        this._resolveActive();
        // On a direct URL load / browser refresh, getCurrentApp() can resolve a
        // tick after the action update — re-check a few times so the sidebar still
        // appears on payroll screens without needing a manual app click.
        [0, 150, 400].forEach((ms) => setTimeout(() => this._resolveVisibility(), ms));
    }

    // Show the sidebar inside a payroll app OR whenever a Payobook cockpit action
    // is on screen. The latter matters when a screen is reached via doAction from
    // another app (e.g. the coach tour opening the dashboard from Discuss) — the
    // app menu isn't switched, so getCurrentApp() alone would wrongly hide us.
    _resolveVisibility() {
        let app = null;
        try { app = this.menuService.getCurrentApp(); } catch (e) { /* ignore */ }
        let visible = !!(app && PAYROLL_APPS.has(app.xmlid));
        if (!visible) {
            const ctrl = this.actionService.currentController;
            const a = ctrl && ctrl.action;
            const isPb = (s) => typeof s === "string" &&
                // `pb_` catches tags and xmlids; `pb.` catches res_models —
                // a cockpit that opens `pb.probation.review` is every bit as
                // much ours as one whose tag is `pb_probation_board`, and
                // leaving the dotted form out is what first hid the rail
                // behind "Open the review".
                (s.startsWith("pb_") || s.startsWith("pb.") ||
                 s.includes("pb_hr_payroll") ||
                 // match both underscore (tag/xmlid) and dotted (res_model) forms,
                 // e.g. res_model "hr.payslip.run" opened via doAction from the wizard.
                 s.includes("hr_payslip") || s.includes("hr.payslip"));
            if (a && (isPb(a.tag) || isPb(a.xml_id) || isPb(a.res_model))) {
                visible = true;
            }
            // ...and any surface the RAIL ITSELF CLAIMS, whatever it is called.
            //
            // The name test above is a heuristic, and there is exactly one
            // client action in the product it gets wrong: the Payroll Report's
            // tag is `payroll_report_dashboard`, which starts with neither
            // `pb_` nor anything else the list recognises — so opening that
            // cockpit by bookmark hid the whole sidebar, and the IA cutover's
            // highlight matrix could not light the Insights item because there
            // was no rail on screen to light. Asking the match indexes instead
            // is the same question without the guesswork: if a rail entry says
            // it owns this surface, the rail belongs on it.
            if (!visible && a && this._isClaimed(a)) {
                visible = true;
            }
            // ...and STAY on screen for anything opened FROM one of our
            // surfaces.
            //
            // Everything above asks "is THIS action ours", which a drill-down
            // fails: the cockpits open ordinary records — `pb.probation.review`
            // (dotted, so the `pb_` prefix test misses it), and worse
            // `hr.contract`, `hr.employee`, `pb.hr.letter`, which are not ours
            // by name at all and never can be. The rail therefore vanished the
            // moment anybody pressed "Open the review" or "Their record", and
            // Odoo's native app menu took its place — the product changing
            // its own chrome halfway through a click-through.
            //
            // The stack answers the question the name cannot. Odoo 19 keeps
            // the WHOLE breadcrumb in the path — a review reached from the
            // probation board is at `/bizapp/pb_probation_board/
            // pb.probation.review/4` — so if any ancestor segment is a surface
            // the rail owns, the rail belongs on this screen too. Reading the
            // URL (rather than remembering "it was visible a moment ago") is
            // deliberate: it survives a refresh and a pasted link, and it goes
            // false by itself the moment the user leaves for another app.
            if (!visible) visible = this._openedFromOurs();
        }
        if (this.state.visible !== visible) this.state.visible = visible;
        document.body.classList.toggle("has-pb-sidebar", visible);
    }

    /**
     * Is any ANCESTOR of the current screen a rail surface? Splits the action
     * path into its segments, drops the last one (that is the screen itself —
     * already judged above, and judging it twice here would let a bare
     * `/bizapp/hr.contract/1` typed from nowhere show the rail), and asks the
     * same two questions of what is left: does a rail item claim it, or does
     * it read as ours by name.
     *
     * Segments are `<tag>` or `<res.model>/<id>`; ids are skipped by the
     * claim/name tests anyway, so no parsing beyond the split is needed.
     */
    _openedFromOurs() {
        let path = "";
        try { path = window.location.pathname || ""; } catch (e) { return false; }
        const segs = path.split("/").filter(Boolean);
        // /bizapp/<a>/<b>/<id> → ancestors are everything but the trailing
        // screen. A depth-1 path has no ancestor and returns false here.
        const ancestors = segs.slice(1, -1);
        return ancestors.some((s) =>
            this._tagIndex[s] !== undefined ||
            this._xmlidIndex[s] !== undefined ||
            this._modelIndex[s] !== undefined ||
            s.startsWith("pb_") || s.startsWith("pb.") ||
            s.includes("pb_hr_payroll") ||
            s.includes("hr_payslip") || s.includes("hr.payslip"));
    }

    /**
     * Does any rail item claim this action? Reads the same three flat indexes
     * `_resolveActive` resolves the highlight from, so visibility and
     * highlighting can never disagree about whether a surface belongs to the
     * rail. Safe before `_load()` — the indexes start as empty objects.
     */
    _isClaimed(action) {
        return (action.xml_id && this._xmlidIndex[action.xml_id] !== undefined)
            || (action.tag && this._tagIndex[action.tag] !== undefined)
            || (action.res_model && this._modelIndex[action.res_model] !== undefined);
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
        this._xmlidIndex = {}; this._tagIndex = {}; this._modelIndex = {};
        this._childParent = {}; this._itemSection = {};
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
                idx(item); this._itemSection[item.id] = s.id;
                for (const c of item.children || []) { idx(c); this._childParent[c.id] = item.id; this._itemSection[c.id] = s.id; }
            }
        }
    }

    // ---- Section collapse / expand ----
    _loadCollapsed() {
        try { return JSON.parse(window.localStorage.getItem("pb_sidebar_collapsed") || "{}") || {}; }
        catch (e) { return {}; }
    }
    _persistCollapsed() {
        try { window.localStorage.setItem("pb_sidebar_collapsed", JSON.stringify(this.state.collapsedSections)); }
        catch (e) { /* ignore */ }
    }
    hasSectionHeader(section) { return section.show_label || section.restricted; }
    isSectionCollapsed(section) {
        if (section.restricted) return true;        // locked → forced collapsed
        if (!section.show_label) return false;      // no header → always shown
        return !!this.state.collapsedSections[section.id];
    }
    toggleSection(section) {
        if (section.restricted) {
            this.dialog.add(AlertDialog, {
                title: _t("Available in the full platform"),
                body: section.restriction_reason ||
                    _t("This functionality is available in the full Payobook platform. Please contact Payobook to arrange a personalised demonstration."),
                confirmLabel: _t("Got it"),
            });
            return;
        }
        if (!section.show_label) return;
        this.state.collapsedSections = {
            ...this.state.collapsedSections,
            [section.id]: !this.state.collapsedSections[section.id],
        };
        this._persistCollapsed();
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
            // Reveal the section holding the active item (no-op for locked sections).
            const secId = this._itemSection[found];
            if (secId !== undefined && this.state.collapsedSections[secId]) {
                this.state.collapsedSections = { ...this.state.collapsedSections, [secId]: false };
                this._persistCollapsed();
            }
        }
    }

    onItemClick(item) {
        if (item.restricted) {
            this.dialog.add(AlertDialog, {
                title: _t("Available in the full platform"),
                body: item.restriction_reason ||
                    _t("This functionality is available in the full Payobook platform. Please contact Payobook to arrange a personalised demonstration."),
                confirmLabel: _t("Got it"),
            });
            return;
        }
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
