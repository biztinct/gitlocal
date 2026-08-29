/** @odoo-module **/
/**
 * The Records Desk.
 *
 * Three zones and two drawers, in the order somebody thinks:
 *
 *     WHO      the left rail — search and facets over the roster
 *     WHAT     the top strip — the fields this scheme MAPS, and only those
 *     THE GRID what those people currently hold, and what they will hold
 *     REVIEW   every staged change as `old → new`, then Apply
 *     HISTORY  every apply anybody has made, each with an Undo that stays
 *
 * The desk stages and the server decides. Nothing on this screen writes: an
 * edit lands in the grid's `dirty` map, a debounced `preview_changes` marks the
 * ones the server would refuse and says why in the cell, and `apply_changes`
 * re-runs the whole evaluation server-side before it writes a thing. The
 * client's opinion is a preview, never a promise.
 *
 * It mounts two ways and behaves the same in both: as the People hub's Records
 * lens (props arrive through the lens definition) and as its own client action
 * (props arrive as `action.params` / `action.context`). Both spellings are read
 * in `arrivalParams`, because a deep link into the desk is R3's whole door and
 * a surface that only works inside one host is a surface that has to be forked.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { RdCellEditor } from "@pb_records/js/records_cells";
import {
    RecordsGrid, createGridState, dirtyCount, setForRows, clearSelection, PAGE,
} from "@pb_records/js/records_grid";
import {
    RdDropZone, RdFileReview, fileApplyLabel, fileSummaryLine,
} from "@pb_records/js/records_import";

const FIELDS_KEY = (configId) => `pb_records.fields.${configId}`;

export class PbRecordsDesk extends Component {
    static template = "pb_records.PbRecordsDesk";
    static components = { RecordsGrid, RdCellEditor, RdDropZone, RdFileReview };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            error: "",
            schemes: [],
            configId: 0,
            schemeOpen: false,
            groups: [],
            statuses: [],
            canWrite: { employee: true, contract: true },
            picked: [],                 // card ids, in pick order
            filters: {
                q: "", department_ids: [], job_ids: [],
                contract_states: [], statuses: [], employee_ids: [],
            },
            handPicked: 0,              // arrived with a selection from People
            facets: { departments: [], jobs: [], contract_states: [], statuses: [] },
            rowsLoading: false,
            review: false,
            history: false,
            historyRows: [],
            applying: false,
            note: "",
            preview: { items: [], counts: { ok: 0, same: 0, refused: 0, people: 0 } },
            previewing: false,
            setFor: null,               // { fieldId, scope }
            toast: null,                // { text, applyId }
            railOpen: true,
            // The field board is a PICKER, not a permanent header. On a scheme
            // that maps 42 destinations it is taller than the grid, so it
            // collapses to the picked set the moment there is one — the
            // "hide fields" gesture every database tool has.
            stripOpen: true,
            pulse: false,
            // --------------------------------------------------------- R3
            exportOpen: false,      // the Export split button's menu
            exporting: "",          // "data" | "template" while building
            dragging: false,        // a file is over the desk
            // The dropped file, from `import_peek` — read, never written.
            file: {
                open: false, name: "", busy: false, error: "", empty: false,
                summary: null, changes: [], items: [], unmatched: [],
                identity: "", wrongScheme: false, truncated: false,
            },
        });

        this.grid = useState(createGridState());
        this._pages = new Set();
        this._searchTimer = null;
        this._previewTimer = null;

        useExternalListener(window, "click", () => {
            this.state.schemeOpen = false;
            this.state.exportOpen = false;
            this.grid.menu = -1;
        });
        // Apply on Cmd/Ctrl-Enter, from anywhere in the drawer. A review a
        // person has read is a review they want to commit without reaching for
        // the mouse, and the shortcut is the same one every editor uses to send.
        useExternalListener(window, "keydown", (ev) => {
            if (!(ev.ctrlKey || ev.metaKey) || ev.key !== "Enter") { return; }
            if (this.state.file.open) { ev.preventDefault(); this.applyFile(); }
            else if (this.state.review) { ev.preventDefault(); this.apply(); }
        });

        onWillStart(async () => { await this.boot(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- arrival
    /**
     * Where the desk was told to start.
     *
     * `action.params` is how a client action is opened with a payload;
     * `action.context` is how `openHub` carries one across `doAction`; and a
     * hub LENS receives neither, because <HubShell/> hands a lens only
     * `{embedded, ...def.props}` — so the People hub reads the context and
     * passes it in as plain props. All three spellings land here.
     */
    get arrivalParams() {
        const action = this.props.action || {};
        const fromAction = { ...(action.context || {}), ...(action.params || {}) };
        return {
            config_id: this.props.configId ?? fromAction.records_config_id ?? 0,
            employee_ids: this.props.employeeIds ?? fromAction.records_employee_ids ?? null,
            field_ids: this.props.fieldIds ?? fromAction.records_field_ids ?? null,
        };
    }

    async boot() {
        const arrival = this.arrivalParams;
        try {
            const info = await this.orm.call("pb.records.desk", "get_schemes", []);
            this.state.schemes = info.schemes || [];
            this.state.configId = Number(arrival.config_id) || info.default_id || 0;
        } catch (e) {
            this.state.error = e.message?.data?.message || String(e);
            this.state.loading = false;
            return;
        }
        if (Array.isArray(arrival.employee_ids) && arrival.employee_ids.length) {
            this.state.filters.employee_ids = arrival.employee_ids.map(Number);
            this.state.handPicked = arrival.employee_ids.length;
        }
        await this.loadFields(arrival.field_ids);
        await this.reload();
        this.state.loading = false;
    }

    // -------------------------------------------------------------- fields
    async loadFields(preferred) {
        const data = await this.orm.call("pb.records.desk", "get_fields",
                                         [this.state.configId]);
        this.state.groups = data.groups || [];
        this.state.statuses = data.statuses || [];
        this.state.canWrite = data.can_write || { employee: true, contract: true };
        const known = new Set(this.allCards.map((c) => c.id));
        let picked = (preferred || []).filter((id) => known.has(id));
        if (!picked.length) {
            picked = this.restorePicked().filter((id) => known.has(id));
        }
        this.state.picked = picked;
        this.state.stripOpen = picked.length === 0;
        this.syncColumns();
    }

    toggleStrip() { this.state.stripOpen = !this.state.stripOpen; }

    get pickedCards() {
        const byId = Object.fromEntries(this.allCards.map((c) => [c.id, c]));
        return this.state.picked.map((id) => byId[id]).filter(Boolean);
    }

    get stripSummary() {
        return _t("%(picked)s of %(total)s picked",
                  { picked: this.state.picked.length, total: this.allCards.length });
    }

    get allCards() {
        return this.state.groups.flatMap((g) => g.fields);
    }

    get mappedNothing() { return this.allCards.length === 0; }

    restorePicked() {
        try {
            const raw = window.localStorage.getItem(FIELDS_KEY(this.state.configId));
            return raw ? JSON.parse(raw) : [];
        } catch { return []; }
    }

    rememberPicked() {
        try {
            window.localStorage.setItem(FIELDS_KEY(this.state.configId),
                                        JSON.stringify(this.state.picked));
        } catch { /* private mode */ }
    }

    syncColumns() {
        const byId = Object.fromEntries(this.allCards.map((c) => [c.id, c]));
        this.grid.columns = this.state.picked.map((id) => byId[id]).filter(Boolean);
    }

    isPicked(id) { return this.state.picked.includes(id); }

    async togglePicked(card) {
        const i = this.state.picked.indexOf(card.id);
        if (i >= 0) { this.state.picked.splice(i, 1); }
        else { this.state.picked.push(card.id); }
        this.rememberPicked();
        this.syncColumns();
        await this.reload();
    }

    hideColumn(fieldId) {
        const i = this.state.picked.indexOf(fieldId);
        if (i >= 0) {
            this.state.picked.splice(i, 1);
            this.rememberPicked();
            this.syncColumns();
            this.reload();
        }
    }

    async onScheme(id) {
        this.state.schemeOpen = false;
        if (this.state.configId === id) { return; }
        this.state.configId = id;
        this.grid.dirty = {};
        this.grid.refusals = {};
        this.grid.undoStack = [];
        this.grid.redoStack = [];
        await this.loadFields(null);
        await this.reload();
    }

    get schemeName() {
        const hit = this.state.schemes.find((s) => s.id === this.state.configId);
        return hit ? hit.name : _t("Pick a pay scheme");
    }

    // --------------------------------------------------------------- rows
    async reload() {
        this._pages = new Set();
        this.grid.rows = [];
        this.grid.total = 0;
        this.grid.loading = true;
        clearSelection(this.grid);
        this.grid.focus = { r: -1, c: -1 };
        await this.fetchPage(0, true);
        this.grid.loading = false;
    }

    async fetchPage(offset, first = false) {
        if (this._pages.has(offset)) { return; }
        this._pages.add(offset);
        this.state.rowsLoading = true;
        try {
            const data = await this.orm.call("pb.records.desk", "search_people", [], {
                config_id: this.state.configId,
                filters: this.plainFilters(),
                field_ids: this.state.picked,
                offset,
                limit: PAGE,
                // The chips are the same for every page of one match set, and
                // counting them is the expensive half of the call (RD11).
                with_facets: first,
            });
            if (first || this.grid.total !== data.total) {
                const rows = new Array(data.total).fill(null);
                for (let i = 0; i < this.grid.rows.length; i++) {
                    if (this.grid.rows[i]) { rows[i] = this.grid.rows[i]; }
                }
                this.grid.rows = rows;
                this.grid.total = data.total;
            }
            data.rows.forEach((row, i) => { this.grid.rows[offset + i] = row; });
            if (data.facets) { this.state.facets = data.facets; }
        } catch (e) {
            this._pages.delete(offset);
            this.state.error = e.message?.data?.message || String(e);
        } finally {
            this.state.rowsLoading = false;
        }
    }

    plainFilters() {
        const f = this.state.filters;
        return {
            q: f.q, department_ids: [...f.department_ids], job_ids: [...f.job_ids],
            contract_states: [...f.contract_states], statuses: [...f.statuses],
            employee_ids: [...f.employee_ids],
        };
    }

    onNeedPage(offset) { this.fetchPage(offset); }

    // ------------------------------------------------------------- filters
    onSearch(ev) {
        this.state.filters.q = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.reload(), 250);
    }

    toggleFacet(kind, id) {
        const list = this.state.filters[kind];
        const i = list.indexOf(id);
        if (i >= 0) { list.splice(i, 1); } else { list.push(id); }
        this.reload();
    }

    isFacetOn(kind, id) { return this.state.filters[kind].includes(id); }

    clearHandPicked() {
        this.state.filters.employee_ids = [];
        this.state.handPicked = 0;
        this.reload();
    }

    clearFilters() {
        this.state.filters = {
            q: "", department_ids: [], job_ids: [],
            contract_states: [], statuses: [], employee_ids: [],
        };
        this.state.handPicked = 0;
        this.reload();
    }

    get anyFilter() {
        const f = this.state.filters;
        return !!(f.q || f.department_ids.length || f.job_ids.length
                  || f.contract_states.length || f.statuses.length
                  || f.employee_ids.length);
    }

    toggleRail() { this.state.railOpen = !this.state.railOpen; }

    // ------------------------------------------------------------ staging
    get counts() { return dirtyCount(this.grid); }

    /**
     * "1 change on 1 person", never "1 changes on 1 people".
     *
     * Both forms are written out rather than interpolated into one, because a
     * count is the thing a person reads twice before pressing Apply and a
     * sentence that cannot count is a sentence they stop trusting. Every
     * counted string on this surface goes through here.
     */
    n(count, one, many) { return count === 1 ? _t(one) : _t(many, count); }

    get reviewLabel() {
        const c = this.counts;
        if (!c.values) { return _t("Nothing to review yet"); }
        return this.n(c.values, "Review 1 change", "Review %s changes");
    }

    get matchLine() {
        const n = this.grid.total;
        if (n === 1) { return _t("1 person matches"); }
        return _t("%s people match", n);
    }

    /**
     * Ask the server what it would do. Debounced, and never blocking: a person
     * typing down a column must not wait for a round trip per keystroke, and a
     * refusal is a red dot with a sentence, not a modal.
     */
    onGridChanged() {
        const c = this.counts;
        if (c.values > 0 && !this.state.pulse) {
            this.state.pulse = true;
            setTimeout(() => { this.state.pulse = false; }, 900);
        }
        clearTimeout(this._previewTimer);
        this._previewTimer = setTimeout(() => this.runPreview(), 400);
    }

    changeList() {
        return Object.values(this.grid.dirty).map((d) => ({
            emp_id: d.empId, field_id: d.fieldId, value: d.value,
        }));
    }

    async runPreview() {
        const changes = this.changeList();
        if (!changes.length) {
            this.state.preview = { items: [], counts: { ok: 0, same: 0, refused: 0, people: 0 } };
            this.grid.refusals = {};
            return;
        }
        this.state.previewing = true;
        try {
            const data = await this.orm.call("pb.records.desk", "preview_changes", [], {
                config_id: this.state.configId, changes,
            });
            this.state.preview = data;
            const refusals = {};
            for (const item of data.items) {
                if (item.status === "refused") {
                    refusals[`${item.emp_id}|${item.field_id}`] = item.why;
                }
            }
            this.grid.refusals = refusals;
        } catch (e) {
            this.state.error = e.message?.data?.message || String(e);
        } finally {
            this.state.previewing = false;
        }
    }

    async onPasted(count) {
        this.notif.add(this.n(count, "Pasted 1 cell", "Pasted %s cells"),
                       { type: "info" });
    }

    async onLookup(comodel, term) {
        return this.orm.call("pb.records.desk", "lookup_m2o", [], {
            comodel, term: term || "", limit: 12,
        });
    }

    async onSelectAllMatching() {
        const ids = await this.orm.call("pb.records.desk", "matching_ids", [], {
            filters: this.plainFilters(),
        });
        this.grid.selected = ids;
        this.grid.allMatching = true;
    }

    // --------------------------------------------------- "Set for everyone"
    openSetFor(fieldId, scope) { this.state.setFor = { fieldId, scope }; }
    closeSetFor() { this.state.setFor = null; }

    get setForCard() {
        if (!this.state.setFor) { return null; }
        return this.allCards.find((c) => c.id === this.state.setFor.fieldId) || null;
    }

    get setForTargets() {
        if (!this.state.setFor) { return []; }
        if (this.state.setFor.scope === "selected") { return [...this.grid.selected]; }
        return this.grid.rows.filter(Boolean).map((r) => r.id);
    }

    get setForTitle() {
        if (!this.state.setFor) { return ""; }
        const count = this.setForTargets.length;
        return this.state.setFor.scope === "selected"
            ? this.n(count, "Set for the one person selected",
                     "Set for everyone selected — %s people")
            : this.n(count, "Set for the one person shown",
                     "Set for all %s people shown");
    }

    applySetFor(value, label) {
        const targets = this.setForTargets;
        const fieldId = this.state.setFor.fieldId;
        this.closeSetFor();
        if (!targets.length) { return; }
        const count = setForRows(this.grid, targets, fieldId, value, label);
        this.onGridChanged();
        this.notif.add(
            this.n(count, "1 cell filled in — nothing is saved until you apply.",
                   "%s cells filled in — nothing is saved until you apply."),
            { type: "info" });
    }

    /** `undefined`, never `null` — a typed optional prop rejects null (W35). */
    get setForLookup() {
        const card = this.setForCard;
        if (!card || card.ttype !== "many2one") { return undefined; }
        return (term) => this.onLookup(card.m2o.comodel, term);
    }

    // -------------------------------------------------------------- review
    openReview() {
        if (!this.counts.values) { return; }
        // One drawer at a time — the grid's changes and a file's changes are
        // two different things to approve, and stacking them would let Apply
        // mean either.
        this.state.file.open = false;
        this.state.review = true;
        this.runPreview();
    }

    closeReview() { this.state.review = false; }

    get reviewGroups() {
        const byPerson = new Map();
        for (const item of this.state.preview.items) {
            if (item.status === "same") { continue; }
            if (!byPerson.has(item.emp_id)) {
                byPerson.set(item.emp_id, { id: item.emp_id, name: item.emp_name, rows: [] });
            }
            byPerson.get(item.emp_id).rows.push(item);
        }
        return [...byPerson.values()];
    }

    get reviewSummary() {
        const c = this.state.preview.counts || {};
        const parts = [
            this.n(c.ok || 0, "1 change", "%s changes") + " "
            + this.n(c.people || 0, "on 1 person", "on %s people"),
        ];
        if (c.refused) {
            parts.push(this.n(c.refused, "1 needs a look", "%s need a look"));
        }
        if (c.same) { parts.push(_t("%s already set", c.same)); }
        return parts.join(" · ");
    }

    get applyLabel() {
        const c = this.state.preview.counts || {};
        if (c.refused) {
            return _t("Apply %(ok)s · leave %(bad)s", { ok: c.ok || 0, bad: c.refused });
        }
        return this.n(c.ok || 0, "Apply 1 change", "Apply %s changes");
    }

    get canApply() { return (this.state.preview.counts || {}).ok > 0; }

    onNote(ev) { this.state.note = ev.target.value; }

    async apply() {
        if (!this.canApply || this.state.applying) { return; }
        this.state.applying = true;
        let result = null;
        try {
            result = await this.orm.call("pb.records.desk", "apply_changes", [], {
                config_id: this.state.configId,
                changes: this.changeList(),
                note: this.state.note,
            });
        } catch (e) {
            // A failed apply wrote NOTHING — the whole method is one
            // transaction — and saying so is the difference between "try again"
            // and "check what got through first".
            this.notif.add(
                _t("Nothing was changed — the update could not be sent. %s",
                   e.message?.data?.message || ""),
                { type: "danger", sticky: true });
            this.state.applying = false;
            return;
        }
        this.state.applying = false;
        this.state.review = false;
        this.state.note = "";

        // The refused ones STAY staged, so the grid still shows the work that is
        // not finished. Everything written is dropped from the staged set.
        const stillBad = new Set((result.refused || [])
            .map((r) => `${r.emp_id}|${r.field_id}`));
        const dirty = {};
        for (const [key, value] of Object.entries(this.grid.dirty)) {
            if (stillBad.has(key)) { dirty[key] = value; }
        }
        this.grid.dirty = dirty;
        this.grid.undoStack = [];
        this.grid.redoStack = [];

        this.state.toast = {
            text: this.n(result.written, "Updated 1 value", "Updated %s values")
                  + " " + this.n(result.people, "on 1 person", "on %s people"),
            applyId: result.apply_id,
        };
        setTimeout(() => {
            if (this.state.toast && this.state.toast.applyId === result.apply_id) {
                this.state.toast = null;
            }
        }, 10000);
        await this.reloadKeepingPlace();
        this.runPreview();
    }

    async reloadKeepingPlace() {
        const loaded = [...this._pages];
        this._pages = new Set();
        this.grid.rows = new Array(this.grid.total).fill(null);
        for (const offset of loaded.sort((a, b) => a - b)) {
            await this.fetchPage(offset, offset === 0);
        }
    }

    // ---------------------------------------------------------------- undo
    async undoApply(applyId) {
        const res = await this.orm.call("pb.records.desk", "undo_apply", [applyId]);
        if (!res.ok) {
            this.notif.add(res.msg, { type: "warning" });
            return;
        }
        const bits = [this.n(res.restored, "Put 1 value back", "Put %s values back")];
        if (res.skipped_changed_since) {
            bits.push(this.n(res.skipped_changed_since,
                             "1 was changed by somebody else since and was left alone",
                             "%s were changed by somebody else since and were left alone"));
        }
        this.notif.add(bits.join(" · "), { type: "success" });
        this.state.toast = null;
        await this.loadHistory();
        await this.reloadKeepingPlace();
    }

    // ------------------------------------------------------------- history
    async openHistory() {
        this.state.history = true;
        await this.loadHistory();
    }

    closeHistory() { this.state.history = false; }

    histLine(h) {
        return this.n(h.count_values, "1 value", "%s values") + " "
             + this.n(h.count_people, "on 1 person", "on %s people");
    }

    async loadHistory() {
        const data = await this.orm.call("pb.records.desk", "get_history", [], { limit: 20 });
        this.state.historyRows = data.applies || [];
    }

    // =====================================================================
    //  R3 — the desk as a file, and that file back as the desk
    // =====================================================================
    /**
     * Export what is on screen. Two shapes, one method.
     *
     * `data` is the grid, detached: the people the filters match and the
     * columns that are picked, with their values in the words the grid shows
     * them in. `template` is the same file with the value cells empty — the
     * shape you hand somebody who is going to fill it in.
     *
     * The download is a Blob, not a controller: the bytes are already in hand
     * from the RPC and a controller would be a second, unauthenticated way to
     * read the same rows (the `pb_people.bulkExport` precedent).
     */
    async exportFile(mode) {
        this.state.exportOpen = false;
        if (this.state.exporting) { return; }
        if (!this.state.picked.length) {
            this.notif.add(
                _t("Pick a field first — a file needs a column to carry."),
                { type: "warning" });
            return;
        }
        this.state.exporting = mode;
        if (this.grid.total > 400) {
            this.notif.add(
                this.n(this.grid.total, "Building the file for 1 person…",
                       "Building the file for %s people…"), { type: "info" });
        }
        let res = null;
        try {
            res = await this.orm.call("pb.records.desk", "export_records", [], {
                config_id: this.state.configId,
                filters: this.plainFilters(),
                field_ids: this.state.picked,
                mode,
            });
        } catch (e) {
            this.state.exporting = "";
            this.notif.add(
                _t("The file could not be built. %s",
                   e.message?.data?.message || ""),
                { type: "danger", sticky: true });
            return;
        }
        this.state.exporting = "";
        if (!res.ok) {
            this.notif.add(res.msg, { type: "warning" });
            return;
        }
        this.download(res);
        if (res.truncated) {
            // The cap is never silent: a file that quietly stops at 10,000 is a
            // file somebody re-imports believing it is the whole roster.
            this.notif.add(
                _t("%(shown)s of %(total)s people are in the file — that is "
                   + "the most one file holds. Filter to a department and "
                   + "export again for the rest.",
                   { shown: res.rows, total: res.total }),
                { type: "warning", sticky: true });
        } else {
            this.notif.add(
                mode === "template"
                    ? _t("Blank template downloaded — %s columns to fill in.",
                         res.columns)
                    : this.n(res.rows, "Downloaded — 1 person in the file.",
                             "Downloaded — %s people in the file."),
                { type: "success" });
        }
    }

    /** base64 to a saved file, without ever leaving the page. */
    download(res) {
        const binary = window.atob(res.file_b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: res.mimetype });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = res.filename;
        link.click();
        URL.revokeObjectURL(url);
    }

    toggleExportMenu() { this.state.exportOpen = !this.state.exportOpen; }

    // ------------------------------------------------------------- dropping
    onDeskDragOver(ev) {
        if (!ev.dataTransfer || !(ev.dataTransfer.types || []).includes("Files")) {
            return;
        }
        ev.preventDefault();
        this.state.dragging = true;
    }

    onDeskDragLeave(ev) {
        // Only when the pointer has actually left the desk, not when it crosses
        // on to a child (`relatedTarget` inside means it has not).
        if (ev.relatedTarget && ev.currentTarget.contains(ev.relatedTarget)) {
            return;
        }
        this.state.dragging = false;
    }

    onDeskDrop(ev) {
        if (!ev.dataTransfer || !ev.dataTransfer.files
            || !ev.dataTransfer.files.length) { return; }
        ev.preventDefault();
        this.state.dragging = false;
        this.takeFile(ev.dataTransfer.files[0]);
    }

    /**
     * Read the file in the browser, then ask the server what it MEANS.
     *
     * Nothing is written by this: `import_peek` parses, matches and calls the
     * same `preview_changes` the grid calls. The drawer that opens is the
     * review drawer, in file mode.
     */
    takeFile(file) {
        if (!file) { return; }
        const f = this.state.file;
        this.state.review = false;      // one drawer at a time
        Object.assign(f, {
            open: true, busy: true, error: "", name: file.name, empty: false,
            summary: null, changes: [], items: [], unmatched: [],
            identity: "", wrongScheme: false, truncated: false,
        });
        this.state.note = "";
        const reader = new FileReader();
        reader.onerror = () => {
            f.busy = false;
            f.error = _t("That file could not be read from this computer. "
                         + "Try saving it again and dropping it back.");
        };
        reader.onload = async () => {
            const b64 = String(reader.result).split(",")[1] || "";
            try {
                const res = await this.orm.call(
                    "pb.records.desk", "import_peek", [], {
                        config_id: this.state.configId,
                        file_b64: b64,
                        filename: file.name,
                    });
                f.busy = false;
                if (!res.ok) {
                    f.error = res.msg;
                    f.summary = { columns_ignored: res.columns_ignored || [] };
                    return;
                }
                Object.assign(f, {
                    empty: !!res.empty,
                    error: res.empty ? res.msg : "",
                    summary: res.summary,
                    changes: res.changes || [],
                    items: res.items || [],
                    unmatched: res.unmatched || [],
                    identity: res.identity || "",
                    wrongScheme: !!res.wrong_scheme,
                    truncated: !!res.truncated,
                });
            } catch (e) {
                f.busy = false;
                f.error = e.message?.data?.message
                    || _t("The file could not be read. Nothing has changed.");
            }
        };
        reader.readAsDataURL(file);
    }

    closeFile() {
        // Cancel discards: nothing was ever written, and saying so is what
        // makes dropping a file safe enough to try.
        this.state.file.open = false;
        this.state.file.changes = [];
        this.state.note = "";
    }

    get fileSummaryLine() {
        const f = this.state.file;
        if (f.busy) { return _t("Reading %s…", f.name); }
        if (f.error) { return f.error; }
        return fileSummaryLine(f.summary || {});
    }

    get fileApplyLabel() { return fileApplyLabel(this.state.file.summary || {}); }

    get canApplyFile() {
        return !!(this.state.file.summary
                  && this.state.file.summary.changes_ok
                  && !this.state.applying);
    }

    /**
     * Bind an unmatched row to a person by hand.
     *
     * Its values move into `changes` live and the whole file is re-previewed,
     * because a bound row can still be refused — a wrong choice for a selection
     * is a wrong choice however the row found its person.
     */
    async bindRow(index, picked) {
        const f = this.state.file;
        const row = f.unmatched[index];
        if (!row || !picked || !picked.id) { return; }
        for (const [fieldId, value] of Object.entries(row.values || {})) {
            f.changes.push({ emp_id: picked.id, field_id: fieldId, value });
        }
        f.unmatched.splice(index, 1);
        await this.repreviewFile(picked.label);
    }

    async repreviewFile(name) {
        const f = this.state.file;
        f.busy = true;
        try {
            const data = await this.orm.call(
                "pb.records.desk", "preview_changes", [], {
                    config_id: this.state.configId, changes: f.changes,
                });
            f.items = data.items;
            f.summary = Object.assign({}, f.summary, {
                changes_ok: data.counts.ok,
                changes_same: data.counts.same,
                changes_refused: data.counts.refused,
                people_changed: data.counts.people,
                people_matched: (f.summary.people_matched || 0) + 1,
                people_unmatched: f.unmatched.length,
            });
            if (name) {
                this.notif.add(_t("Row matched to %s.", name), { type: "info" });
            }
        } catch (e) {
            f.error = e.message?.data?.message || String(e);
        } finally {
            f.busy = false;
        }
    }

    async onLookupPeople(term) {
        return this.orm.call("pb.records.desk", "lookup_people", [], {
            term: term || "", limit: 10,
        });
    }

    /**
     * Apply the file — through `apply_changes`, and through nothing else.
     *
     * Same method, same whitelist, same audit row, same Undo as the grid. The
     * only difference is the word `import` on the audit row and the file's name
     * in the note when nobody typed one.
     */
    async applyFile() {
        if (!this.canApplyFile) { return; }
        const f = this.state.file;
        this.state.applying = true;
        let result = null;
        try {
            result = await this.orm.call("pb.records.desk", "apply_changes", [], {
                config_id: this.state.configId,
                changes: f.changes,
                note: (this.state.note || "").trim()
                      || _t("Imported %s", f.name),
                source: "import",
            });
        } catch (e) {
            this.state.applying = false;
            this.notif.add(
                _t("Nothing was changed — the update could not be sent. %s",
                   e.message?.data?.message || ""),
                { type: "danger", sticky: true });
            return;
        }
        this.state.applying = false;
        this.state.note = "";
        f.open = false;
        this.state.toast = {
            text: this.n(result.written, "Updated 1 value", "Updated %s values")
                  + " " + this.n(result.people, "on 1 person", "on %s people"),
            applyId: result.apply_id,
        };
        setTimeout(() => {
            if (this.state.toast && this.state.toast.applyId === result.apply_id) {
                this.state.toast = null;
            }
        }, 10000);
        await this.reloadKeepingPlace();
    }

    // ---------------------------------------------------------------- doors
    openMapping() {
        this.action.doAction("pb_formula_studio.action_pb_formula_studio", {})
            .catch(() => this.notif.add(
                _t("The Mapping screen is not installed on this database."),
                { type: "warning" }));
    }

    // ---------------------------------------------------------------- copy
    get exportLabel() {
        return this.state.exporting === "template"
            ? _t("Building…")
            : this.state.exporting ? _t("Building…") : _t("Export");
    }

    get exportCountLabel() {
        return this.n(this.grid.total, "1 person", "%s people");
    }

    get wrongSchemeLine() {
        return _t("This file was exported from a different pay scheme. The "
                  + "columns that match this one are used; the rest are "
                  + "listed under Ignored columns.");
    }

    get filePlaceholder() {
        return _t("Why? optional — the file's name is used if you leave this "
                  + "empty");
    }

    /** `undefined`, never `null` — a typed optional prop rejects null (W35). */
    get fileLookup() {
        return (term) => this.onLookupPeople(term);
    }

    get title() { return _t("Records Desk"); }
    get subtitle() {
        return _t("Update the employee, contract and bank details your pay "
                  + "scheme reads — one person or hundreds at once.");
    }
    get emptyFieldsTitle() {
        return _t("This scheme doesn't map any employee, contract or bank fields yet");
    }
    get emptyFieldsBody() {
        return _t("The desk only offers fields your pay scheme actually reads, so "
                  + "there is nothing to change until a column is wired to one. "
                  + "Wire one in Mapping and it appears here.");
    }
    get noFieldsPickedTitle() { return _t("Pick a field to start"); }
    get noFieldsPickedBody() {
        return _t("Choose one above and it becomes a column you can type down.");
    }
    get noPeopleTitle() { return _t("Nobody matches those filters"); }
    get noPeopleBody() {
        return _t("Widen the search on the left, or clear the filters and start again.");
    }
}

registry.category("actions").add("pb_records_desk", PbRecordsDesk);
