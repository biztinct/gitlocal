/** @odoo-module **/
/**
 * The Approval Matrix — every check the business makes, on one screen.
 *
 * THE HERO IS THE LIST ITSELF. Every process that can need a sign-off, grouped
 * the way somebody sees the product rather than the way the data is stored:
 * Pay, Money out, Pay data, People, Time, Setup & rules, Platform. Each row
 * says WHO signs it off in words — "HR lead · Finance approver · Country
 * director (600m and above)" — so nobody has to open a workflow to learn what
 * it does.
 *
 * A ROW IS ONLY "IN USE" WHEN BOTH HALVES ARE TRUE: its route is published AND
 * the feature behind it is wired up to the engine. A row that is not wired up
 * says so and can be drafted but never published, so nothing on this screen can
 * pretend to be protecting something it is not.
 *
 * "N PROCESSES NEED PEOPLE" IS THE BAR THAT MATTERS. A published route with a
 * part of the business that has nobody named is not a working route: requests
 * from there will stop. That is counted at the top and filters the list in one
 * press.
 *
 * THREE TABS AND NO MORE. Matrix (what happens), People & backups (who it
 * reaches), History (what changed). The builder opens over the first one and
 * comes back to it.
 *
 * THE RULES THIS FILE KEEPS
 *   * Every icon comes from the shared `ic()` set — no emoji, no glyph arrows.
 *   * Every sentence is ONE expression: JavaScript has no implicit string
 *     concatenation and a Python habit here kills the whole asset bundle.
 *   * Escape is registered with `{ capture: true }`, because the platform's own
 *     hotkey service listens on `window` and stops propagation for the keys it
 *     claims — Escape among them.
 *   * The component names itself with `setDisplayName`: a client action with no
 *     control panel otherwise draws a breadcrumb crumb reading "Unnamed" over
 *     anything it opens.
 */
import {
    Component, onMounted, onWillStart, onWillUnmount, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { ApprovalBuilder } from "@pb_approval_config/js/builder";
import { PeopleTab } from "@pb_approval_config/js/people_tab";
import { HistoryTab } from "@pb_approval_config/js/history_tab";
import { ApprovalSchemePanel } from "@pb_approval_config/js/scheme_panel";
import { statusMeta } from "@pb_approval_config/js/sentence";

export class PbApprovalMatrix extends Component {
    static template = "pb_approval_config.PbApprovalMatrix";
    static components = {
        HubBackChip, ApprovalBuilder, PeopleTab, HistoryTab,
        ApprovalSchemePanel,
    };
    static props = ["*"];

    setup() {
        this.ic = ic;
        this.statusMeta = statusMeta;
        this.orm = useService("orm");
        this.notif = useService("notification");

        // Read ONCE, from props, never written back (the shell's rule).
        this.back = hubBack(this.props);

        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("Approval Matrix"));
        }

        this.state = useState({
            loading: true,
            failed: "",
            tab: "matrix",
            data: null,
            search: "",
            area: "all",
            status: "all",
            presetsOpen: false,
            presetFor: "",
            builderFor: 0,
            peopleFocus: null,
            scopeFor: null,
            importOpen: false,
        });

        this.onEscape = this.onEscape.bind(this);
        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            window.addEventListener("keydown", this.onEscape,
                                    { capture: true });
        });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this.onEscape,
                                       { capture: true });
        });
    }

    onEscape(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.scopeFor) { this.state.scopeFor = null; return; }
        if (this.state.importOpen) { this.state.importOpen = false; return; }
        if (this.state.presetsOpen) { this.state.presetsOpen = false; }
    }

    // ============================================================== reading
    async load() {
        this.state.loading = true;
        this.state.failed = "";
        try {
            this.state.data = await this.orm.call(
                "pb.approval.matrix", "get_matrix", [false]);
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("The Approval Matrix could not be opened.");
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data || { areas: [], attention: { count: 0 },
                                    presets: [] };
    }

    get tabs() {
        return [
            { key: "matrix", icon: "workflow", label: _t("Matrix") },
            { key: "people", icon: "users", label: _t("People & backups"),
              count: this.data.attention ? this.data.attention.count : 0 },
            { key: "history", icon: "history", label: _t("History") },
        ];
    }

    get allRows() {
        return (this.data.areas || []).flatMap((area) => area.rows || []);
    }

    get counts() {
        const counts = {};
        for (const row of this.allRows) {
            counts[row.status] = (counts[row.status] || 0) + 1;
        }
        return counts;
    }

    get statusChips() {
        return ["live", "draft", "needs", "soon"].map((key) => ({
            key, label: statusMeta(key).label, count: this.counts[key] || 0,
        }));
    }

    /** The areas, with only the rows the filters let through. */
    get visibleAreas() {
        const term = this.state.search.trim().toLowerCase();
        const out = [];
        for (const area of this.data.areas || []) {
            const rows = (area.rows || []).filter((row) => {
                if (this.state.area !== "all" && row.area !== this.state.area) {
                    return false;
                }
                if (this.state.status !== "all"
                        && row.status !== this.state.status) {
                    return false;
                }
                if (!term) { return true; }
                const haystack = [
                    row.name, row.applies, row.sub,
                    ...(row.route_labels || []),
                ].join(" ").toLowerCase();
                return haystack.includes(term);
            });
            if (rows.length) { out.push({ ...area, rows }); }
        }
        return out;
    }

    get nothingMatches() {
        return !this.state.loading && this.visibleAreas.length === 0;
    }

    // ============================================================== acting
    setTab(key) {
        this.state.tab = key;
        this.state.builderFor = 0;
        if (key !== "people") { this.state.peopleFocus = null; }
    }

    setArea(key) { this.state.area = key; }
    setStatus(key) { this.state.status = key; }
    onSearch(ev) { this.state.search = ev.target.value; }

    clearFilters() {
        this.state.search = "";
        this.state.area = "all";
        this.state.status = "all";
    }

    reviewSetup() {
        this.state.status = "needs";
        this.state.tab = "matrix";
    }

    togglePresets(processKey) {
        this.state.presetFor = processKey || "";
        this.state.presetsOpen = !this.state.presetsOpen;
    }

    toggleImport() { this.state.importOpen = !this.state.importOpen; }

    /** Open a row: its builder if it has a route, the starting points if not. */
    async openRow(row) {
        if (row.workflow_id) {
            this.state.builderFor = row.workflow_id;
            return;
        }
        if (!row.connected) {
            this.notif.add(
                _t("%s is not wired up to approvals yet. You can write its route now; publishing waits until it is.", row.name),
                { type: "info" });
        }
        this.togglePresets(row.process_key);
    }

    async usePreset(presetKey) {
        const processKey = this.state.presetFor;
        if (!processKey) {
            this.notif.add(
                _t("Choose which kind of request this route is for, by opening its row."),
                { type: "info" });
            return;
        }
        try {
            const made = await this.orm.call(
                "pb.approval.matrix", "create_workflow",
                [presetKey, processKey, false]);
            this.state.presetsOpen = false;
            this.state.builderFor = made.workflow_id;
            this.notif.add(
                _t("A draft was created. Nothing is published until you say so."),
                { type: "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That draft could not be created."),
                { type: "danger" });
        }
    }

    openScope(row) {
        this.state.scopeFor = row;
    }

    closeScope() { this.state.scopeFor = null; }

    /** Come back from the builder, and read the grid again — it has changed. */
    async closeBuilder() {
        this.state.builderFor = 0;
        await this.load();
    }

    openPeople(roleKey, scopeKey) {
        this.state.builderFor = 0;
        this.state.tab = "people";
        this.state.peopleFocus = roleKey
            ? { role_key: roleKey, scope_key: scopeKey || "" } : null;
    }
}

registry.category("actions").add("pb_approval_matrix", PbApprovalMatrix);
