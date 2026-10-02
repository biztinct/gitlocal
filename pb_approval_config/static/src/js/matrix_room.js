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
        this.openTarget = (this.props.action && this.props.action.params) || {};

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
            peopleFocus: {},
            scopeFor: null,
            importOpen: false,
            importBusy: false,
            importResult: null,
            // "No approval needed" for many rows at once
            bulkOpen: false,
            bulkPicked: {},
            bulkExceptions: true,
            bulkMoneyOk: false,
            bulkReason: "",
            bulkBusy: false,
            bulkInfo: null,
            bulkShowSkipped: false,
            bulkDone: null,
            flash: {},
        });

        this.onEscape = this.onEscape.bind(this);
        onWillStart(async () => {
            await this.load();
            const workflowId = Number(this.openTarget.workflow_id || 0);
            const processKey = this.openTarget.process_key || "";
            const row = this.allRows.find((one) => one.process_key === processKey);
            this.state.builderFor = workflowId || (row && row.workflow_id) || 0;
            if (!this.state.builderFor && processKey) {
                this.state.search = row ? row.name : processKey;
            }
        });
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
        if (this.state.bulkOpen) { this.closeBulk(); return; }
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
        return ["live", "draft", "needs", "soon", "covered"].map((key) => ({
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

    // ============================================ many rows, one press
    /**
     * "No approval needed" for everything the filters show.
     *
     * THE BUTTON FOLLOWS THE FILTERS, BECAUSE THE FILTERS ARE THE SELECTION.
     * All areas means every process; choosing Pay means the Pay rows and no
     * others; a search narrows it again. Nothing changes on the press itself:
     * it opens a review drawer that lists every row it would switch, each one
     * a tick that can be taken off, and the rows it leaves alone with the
     * reason. Only the drawer's own button changes anything, and the Matrix
     * then offers to put it all back.
     */
    get shownRows() {
        return this.visibleAreas.flatMap((area) => area.rows);
    }

    get bulkCandidates() {
        return this.shownRows.filter((row) => !row.bulk);
    }

    get bulkFiltered() {
        return this.state.area !== "all" || this.state.status !== "all"
            || Boolean(this.state.search.trim());
    }

    get bulkAreaName() {
        const area = (this.data.areas || []).find(
            (one) => one.key === this.state.area);
        return area ? area.name : "";
    }

    get bulkButtonLabel() {
        if (!this.bulkFiltered) {
            return _t("No approval needed for all");
        }
        if (this.state.status === "all" && !this.state.search.trim()
                && this.bulkAreaName) {
            return _t("No approval needed for all %s", this.bulkAreaName);
        }
        return _t("No approval needed for these");
    }

    get bulkButtonTitle() {
        if (!this.data.can_publish) {
            return _t("Only somebody who may publish approval routes can do this.");
        }
        if (!this.bulkCandidates.length) {
            return _t("Every process shown already needs no approval, or has nothing of its own to switch off.");
        }
        return _t("Review the list first. Nothing changes until you confirm.");
    }

    /** The drawer's list: the rows it would switch, grouped by area. */
    get bulkGroups() {
        const out = [];
        for (const area of this.visibleAreas) {
            const rows = area.rows.filter((row) => !row.bulk);
            if (rows.length) { out.push({ key: area.key, name: area.name,
                                          icon: area.icon, rows }); }
        }
        return out;
    }

    /** The rows it leaves alone, by reason. */
    get bulkSkipped() {
        const reasons = {
            fast: _t("Already needs no approval"),
            covered: _t("Decided with another process"),
            soon: _t("Not connected yet, so nothing is checked"),
        };
        const out = [];
        for (const key of ["fast", "covered", "soon"]) {
            const rows = this.shownRows.filter((row) => row.bulk === key);
            if (rows.length) { out.push({ key, label: reasons[key], rows }); }
        }
        return out;
    }

    get bulkSkippedCount() {
        return this.bulkSkipped.reduce((n, group) => n + group.rows.length, 0);
    }

    get bulkPickedRows() {
        return this.bulkCandidates.filter(
            (row) => this.state.bulkPicked[row.process_key]);
    }

    get bulkMoneyRows() {
        return this.bulkPickedRows.filter((row) => row.money);
    }

    get bulkExceptionCount() {
        return this.bulkPickedRows.reduce(
            (n, row) => n + (row.exceptions || 0), 0);
    }

    get bulkWaiting() {
        const info = this.state.bulkInfo;
        if (!info) { return 0; }
        return (info.rows || []).filter(
            (row) => this.state.bulkPicked[row.process_key])
            .reduce((n, row) => n + row.waiting, 0);
    }

    get bulkCanApply() {
        return this.bulkPickedRows.length > 0 && !this.state.bulkBusy
            && (!this.bulkMoneyRows.length || this.state.bulkMoneyOk);
    }

    get bulkScopeLine() {
        if (!this.bulkFiltered) {
            return _t("Every process in the Matrix");
        }
        if (this.state.status === "all" && !this.state.search.trim()
                && this.bulkAreaName) {
            return _t("Every %s process", this.bulkAreaName);
        }
        return _t("The processes your filters show");
    }

    // Whole sentences, so each one translates as a sentence.
    get bulkShownLine() {
        return _t("%s shown", this.shownRows.length);
    }

    get bulkChosenLine() {
        return _t("%s of %s chosen", this.bulkPickedRows.length,
                  this.bulkCandidates.length);
    }

    get bulkSkippedLine() {
        return _t("%s shown but left as they are", this.bulkSkippedCount);
    }

    get bulkExceptionLine() {
        return this.bulkExceptionCount === 1
            ? _t("Include the 1 part of the business with its own route.")
            : _t("Include the %s parts of the business with their own route.",
                 this.bulkExceptionCount);
    }

    get bulkWaitingLine() {
        return _t("Requests already waiting (%s) keep the route they started on. Only new ones skip the check.",
                  this.bulkWaiting);
    }

    get bulkMoneyLine() {
        return _t("Money leaves the company on %s.",
                  this.bulkMoneyRows.map((row) => row.name).join(", "));
    }

    get bulkApplyLine() {
        return _t("Switch off approval for %s", this.bulkPickedRows.length);
    }

    get bulkDoneLine() {
        const n = this.state.bulkDone ? this.state.bulkDone.done.length : 0;
        return n === 1
            ? _t("1 process now needs no approval. It still shows up in History each time it is used.")
            : _t("%s processes now need no approval. Each one still shows up in History when it is used.", n);
    }

    bulkGroupAllOn(group) {
        return group.rows.every((row) => this.state.bulkPicked[row.process_key]);
    }

    async openBulk() {
        if (!this.data.can_publish || !this.bulkCandidates.length) { return; }
        const picked = {};
        for (const row of this.bulkCandidates) { picked[row.process_key] = true; }
        this.state.bulkPicked = picked;
        this.state.bulkExceptions = true;
        this.state.bulkMoneyOk = false;
        this.state.bulkReason = "";
        this.state.bulkShowSkipped = false;
        this.state.bulkInfo = null;
        this.state.bulkOpen = true;
        try {
            this.state.bulkInfo = await this.orm.call(
                "pb.approval.matrix", "bulk_no_approval_preview",
                [this.bulkCandidates.map((row) => row.process_key), false]);
        } catch {
            // The drawer still works without the counts; it only says less.
            this.state.bulkInfo = null;
        }
    }

    closeBulk() {
        if (this.state.bulkBusy) { return; }
        this.state.bulkOpen = false;
    }

    toggleBulkSkipped() {
        this.state.bulkShowSkipped = !this.state.bulkShowSkipped;
    }

    setBulkField(name, value) { this.state[name] = value; }

    toggleBulkRow(row) {
        this.state.bulkPicked[row.process_key]
            = !this.state.bulkPicked[row.process_key];
    }

    toggleBulkGroup(group) {
        const on = !this.bulkGroupAllOn(group);
        for (const row of group.rows) {
            this.state.bulkPicked[row.process_key] = on;
        }
    }

    toggleBulkAll() {
        const on = this.bulkPickedRows.length !== this.bulkCandidates.length;
        for (const row of this.bulkCandidates) {
            this.state.bulkPicked[row.process_key] = on;
        }
    }

    async applyBulk() {
        if (!this.bulkCanApply) { return; }
        const keys = this.bulkPickedRows.map((row) => row.process_key);
        this.state.bulkBusy = true;
        try {
            const result = await this.orm.call(
                "pb.approval.matrix", "set_no_approval_bulk", [keys], {
                    company_id: false,
                    include_exceptions: this.state.bulkExceptions,
                    reason: this.state.bulkReason,
                    confirmations: this.bulkMoneyRows.length ? ["money_fast"] : [],
                });
            this.state.bulkBusy = false;
            this.state.bulkOpen = false;
            this.state.bulkDone = result;
            const flash = {};
            for (const row of result.done) { flash[row.process_key] = true; }
            this.state.flash = flash;
            await this.load();
            setTimeout(() => { this.state.flash = {}; }, 2600);
            if (result.skipped.length) {
                this.notif.add(
                    _t("%s could not be switched: %s", result.skipped.length,
                       result.skipped.map((row) => `${row.name} (${row.why})`).join(", ")),
                    { type: "warning" });
            }
        } catch (error) {
            this.state.bulkBusy = false;
            this.notif.add(
                (error.data && error.data.message)
                    || _t("Approval could not be switched off."),
                { type: "danger" });
        }
    }

    async undoBulk() {
        const done = this.state.bulkDone;
        if (!done || this.state.bulkBusy) { return; }
        this.state.bulkBusy = true;
        try {
            const result = await this.orm.call(
                "pb.approval.matrix", "undo_no_approval_bulk",
                [done.undo, false]);
            this.state.bulkDone = null;
            this.notif.add(
                _t("The checks are back on %s processes.", result.restored),
                { type: "success" });
            await this.load();
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                    || _t("The checks could not be put back."),
                { type: "danger" });
        } finally {
            this.state.bulkBusy = false;
        }
    }

    dismissBulkDone() { this.state.bulkDone = null; }

    // ============================================================== acting
    setTab(key) {
        this.state.tab = key;
        this.state.builderFor = 0;
        if (key !== "people") { this.state.peopleFocus = {}; }
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

    toggleImport() {
        this.state.importOpen = !this.state.importOpen;
        if (!this.state.importOpen) { this.state.importResult = null; }
    }

    // ================================================== the spreadsheet door
    /**
     * Read the approvals sheet of a setup workbook into DRAFT routes.
     *
     * Nothing is published and no account is ever guessed from a name: every
     * person in the workbook comes back as a suggestion somebody has to point
     * at a real login before it means anything.
     */
    async onImportFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        this.state.importBusy = true;
        this.state.importResult = null;
        try {
            const content = await this.readAsBase64(file);
            const result = await this.orm.call(
                "pb.approval.matrix.import", "run", [content]);
            this.state.importResult = result;
            this.notif.add(result.sentence, { type: "success" });
            await this.load();
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                    || _t("That workbook could not be read."),
                { type: "danger" });
        } finally {
            this.state.importBusy = false;
            ev.target.value = "";
        }
    }

    readAsBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const raw = String(reader.result || "");
                resolve(raw.slice(raw.indexOf(",") + 1));
            };
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(file);
        });
    }

    /** Give one suggested name a real account. */
    async resolvePerson(person, userId) {
        if (!userId) { return; }
        try {
            await this.orm.call("pb.approval.matrix.import", "resolve_person",
                                [person.id, userId]);
            person.state = "resolved";
            this.notif.add(_t("%s now holds that responsibility.",
                              person.name_text), { type: "success" });
            await this.load();
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                    || _t("That person could not be given the responsibility."),
                { type: "danger" });
        }
    }

    get importPeople() {
        const result = this.state.importResult;
        return ((result && result.people) || []).filter(
            (p) => p.state === "proposed");
    }

    get importRows() {
        const result = this.state.importResult;
        return (result && result.made) || [];
    }

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
        // An OBJECT and never null: a typed optional prop still rejects null,
        // which is a hard validation error in dev mode (W35).
        this.state.peopleFocus = roleKey
            ? { role_key: roleKey, scope_key: scopeKey || "" } : {};
    }
}

registry.category("actions").add("pb_approval_matrix", PbApprovalMatrix);
