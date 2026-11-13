/** @odoo-module **/
/**
 * `pb_assets` — the Assets board.
 *
 * One table of everything the company owns and lends out, and one drawer that
 * opens the whole life of a single item: who has had it, what state it was in
 * each way, and what can be done with it next.
 *
 * The shape is `pb_journeys`', which is `pb_people`': an `AbstractModel` facade
 * behind every read, `props.embedded` dropping the H1 when the hub is already
 * saying "People › Assets" above it, and the kit's `.pbim-*` primitives for
 * every surface, so this screen re-tints with the rest of the product.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change the register.
 * The facade's `_require_write()` is the boundary; `state.canWrite` only decides
 * whether a control is OFFERED, because an offer the server would refuse is
 * worse than no offer.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;

/** The colour a status wears, everywhere it appears. */
const TONE = {
    spare: "info",
    assigned: "ok",
    repair: "warn",
    to_scrap: "warn",
    scrapped: "muted",
    deactivated: "muted",
};

const WARRANTY_LABEL = {
    ok: _t("In warranty"),
    soon: _t("Warranty ending"),
    over: _t("Out of warranty"),
    none: "",
};

export class PbAssetsBoard extends Component {
    static template = "pb_assets.PbAssetsBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            kpis: {},
            rows: [],
            categories: [],
            countries: [],
            countriesAll: [],
            states: [],
            kinds: [],
            facets: {},
            requests: {},
            homeCountryId: 0,

            // the register the filter panel produced, one page at a time
            total: 0,
            listLoaded: false,
            loadingMore: false,

            // what the reader is looking at
            segment: "items",       // items | requests
            reqStep: "",            // the numbered request step being shown

            // selection for the bulk bar: ids, each one's kind, and whether
            // it is "everything matching" (all pages) rather than ticks
            picked: [],
            pickedKind: {},
            pickedAll: false,
            pickedCapped: false,
            matching: false,

            // the open item
            drawer: null,

            // dialogs — one at a time, each one plain state
            add: null,
            hand: null,
            back: null,
            ask: null,
            bulk: null,
        });

        // The shared filter panel (pb_filter_kit): it owns the filters, the
        // counts and the views; this board only loads a page for kit.query.
        this.kit = useFilterKit({
            model: "pb.assets",
            noun: _t("items"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.assets", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                kpis: d.kpis || {},
                categories: d.categories || [],
                countries: d.countries || [],
                countriesAll: d.countries_all || d.countries || [],
                states: d.states || [],
                kinds: d.kinds || [],
                facets: d.facets || {},
                requests: d.requests || {},
                homeCountryId: d.home_country_id || 0,
                loaded: true,
            });
        } catch (e) {
            console.warn("pb_assets: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    /** One page of the register for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.assets", "get_asset_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.total = d.total;
            this.state.listLoaded = true;
            if (!more) {
                // the filters changed: "everything matching" no longer means
                // what it meant, and a tick on an item nobody can see is a
                // bulk change nobody asked for (R6)
                if (this.state.pickedAll) {
                    this.clearPicked();
                } else {
                    const ids = new Set(d.rows.map((r) => r.id));
                    this.state.picked = this.state.picked.filter((id) => ids.has(id));
                }
            }
        } catch (e) {
            if (this.kit.isCurrent(q.seq)) {
                console.warn("pb_assets: could not read the register page", e);
                this.notif.add(_t("The register could not be listed. Try again in a moment."), { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() { return this.state.rows.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    /** The numbers, the counts and the page, in place; the drawer follows. */
    async refresh() {
        const openId = this.state.drawer && this.state.drawer.asset.id;
        await Promise.all([this.load(), this.kit.refresh()]);
        if (openId) { await this.openAsset(openId); }
    }

    // --------------------------------------------------------------- filters
    get visibleRows() { return this.state.rows; }

    get hasFilters() {
        return Boolean(this.kit.activeCount || this.kit.search);
    }

    clearFilters() { this.kit.toggleFilters({}); }

    setSegment(seg) { this.state.segment = seg; }

    /** A figure that filters: the register, filtered exactly like its view. */
    glancePick(filters) {
        return () => {
            this.state.segment = "items";
            this.kit.toggleFilters(filters);
        };
    }

    get glanceFilters() {
        return {
            assigned: { status: ["assigned"], kind: ["tangible"] },
            spare: { status: ["spare"], kind: ["tangible"] },
            repair: { status: ["repair"] },
            digital: { status: ["assigned"], kind: ["digital"] },
        };
    }

    // ------------------------------------------------------ the quiet board
    //
    // The Hiring look: one slim line of numbers instead of a row of tiles
    // (grey at zero, a colour only when somebody must act), and on the
    // Requests tab a numbered strip of the steps a request moves through.
    // The register itself gets no strip: an item goes round and round
    // between spare, with somebody and in for repair — that is not a line.
    get glance() {
        const k = this.state.kpis || {};
        const f = this.glanceFilters;
        return [
            { key: "total", n: k.total || 0, label: _t("Items on the books"), tone: "", run: this.glancePick({}) },
            { key: "assigned", n: k.assigned || 0, label: _t("Out with people"), tone: "", run: this.glancePick(f.assigned) },
            { key: "spare", n: k.spare || 0, label: _t("Spare in the cupboard"), tone: "", run: this.glancePick(f.spare) },
            { key: "repair", n: k.repair || 0, label: _t("Under repair"), tone: "", run: this.glancePick(f.repair) },
            { key: "digital", n: k.digital_live || 0, label: _t("Accounts live"), tone: "", run: this.glancePick(f.digital) },
            { key: "leavers", n: k.leavers_holding || 0, label: _t("Leavers still holding"), tone: k.leavers_holding ? "rose" : "", run: null },
        ];
    }

    get glanceOn() {
        if (this.state.segment !== "items" || !this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.glanceFilters)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    /** A request is at EXACTLY one step: "Decided" holds both the approved
     *  and the turned-down ones, so the four counts add up. */
    get requestStepDefs() {
        return [
            { key: "draft", title: _t("Being written"), states: ["draft"] },
            { key: "submitted", title: _t("With the manager"), states: ["submitted"] },
            { key: "manager_approved", title: _t("With the asset team"), states: ["manager_approved"] },
            { key: "decided", title: _t("Decided"), states: ["approved", "refused"] },
        ];
    }

    get requestRows() {
        return (this.state.requests && this.state.requests.rows) || [];
    }

    get requestSteps() {
        const rows = this.requestRows;
        return this.requestStepDefs.map((st, i) => {
            const at = rows.filter((r) => st.states.includes(r.state));
            const approved = at.filter((r) => r.state === "approved");
            const refused = at.length - approved.length;
            const toHand = approved.filter((r) => !["delivered", "confirmed"].includes(r.fulfilment)).length;
            return {
                key: st.key,
                title: st.title,
                n: String(i + 1).padStart(2, "0"),
                count: at.length,
                countLabel: at.length === 1 ? _t("1 request") : _t("%s requests", at.length),
                sub: st.key === "decided" && at.length
                    ? _t("%s approved · %s turned down", approved.length, refused) : "",
                flag: st.key === "decided" && toHand
                    ? (toHand === 1 ? _t("1 approved, still to hand over") : _t("%s approved, still to hand over", toHand))
                    : "",
                on: this.state.reqStep === st.key,
            };
        });
    }

    pickRequestStep(key) {
        this.state.reqStep = this.state.reqStep === key ? "" : key;
    }

    get visibleRequests() {
        const st = this.requestStepDefs.find((x) => x.key === this.state.reqStep);
        return st ? this.requestRows.filter((r) => st.states.includes(r.state)) : this.requestRows;
    }

    get requestShowing() {
        const all = this.requestRows.length;
        const st = this.requestStepDefs.find((x) => x.key === this.state.reqStep);
        if (!st) {
            return { all: true, text: !all ? _t("No requests yet")
                : all === 1 ? _t("Showing the 1 request · press a step to narrow it")
                : _t("Showing all %s requests · press a step to narrow it", all) };
        }
        return { all: false, text: _t("Showing %s of %s requests at %s", this.visibleRequests.length, all, st.title) };
    }

    // ------------------------------------------------------------- selection
    isPicked(id) { return this.state.picked.includes(id); }

    togglePick(id) {
        const row = this.state.rows.find((r) => r.id === id);
        const at = this.state.picked.indexOf(id);
        if (at === -1) {
            this.state.picked.push(id);
            if (row) { this.state.pickedKind[id] = row.kind; }
        } else {
            this.state.picked.splice(at, 1);
        }
        this.state.pickedAll = false;
        this.state.pickedCapped = false;
    }

    /** The header tick: every item on the page shown (or none again). */
    pickAllVisible() {
        const rows = this.visibleRows;
        const allOn = rows.length && rows.every((r) => this.state.picked.includes(r.id));
        if (allOn) { this.clearPicked(); return; }
        this.state.picked = rows.map((r) => r.id);
        this.state.pickedKind = Object.fromEntries(rows.map((r) => [r.id, r.kind]));
        this.state.pickedAll = false;
        this.state.pickedCapped = false;
    }

    get allVisiblePicked() {
        const rows = this.visibleRows;
        return !!rows.length && rows.every((r) => this.state.picked.includes(r.id));
    }

    /** More match than the page holds, and the page is all ticked: offer the rest. */
    get canPickMatching() {
        return !this.state.pickedAll && this.allVisiblePicked && this.state.total > this.state.rows.length;
    }

    /** "Select everything matching (N)": every page, from one server call (R6). */
    async pickMatching() {
        if (this.state.matching) { return; }
        this.state.matching = true;
        const q = this.kit.query;
        try {
            const res = await this.orm.call("pb.assets", "matching_ids", [], {
                filters: q.filters, search: q.search,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.picked = res.ids || [];
            this.state.pickedKind = Object.fromEntries(
                Object.entries(res.kinds || {}).map(([k, v]) => [Number(k), v]));
            this.state.pickedAll = true;
            this.state.pickedCapped = !!res.capped;
        } catch (e) {
            this.fail(e);
        } finally {
            this.state.matching = false;
        }
    }

    clearPicked() {
        this.state.picked = [];
        this.state.pickedKind = {};
        this.state.pickedAll = false;
        this.state.pickedCapped = false;
    }

    /** The statuses every picked item could legally take. A mixed selection of
     *  laptops and email accounts offers only what both can do. */
    get bulkStates() {
        if (!this.state.picked.length) { return []; }
        const kinds = this.state.picked.map((id) => this.state.pickedKind[id] || "tangible");
        const digital = kinds.includes("digital");
        const tangible = kinds.includes("tangible");
        return this.state.states.filter((s) => {
            if (s.id === "assigned") { return false; }
            if (digital && !["spare", "deactivated"].includes(s.id)) {
                return false;
            }
            if (tangible && s.id === "deactivated") { return false; }
            return true;
        });
    }

    // ------------------------------------------------------------ formatting
    tone(s) { return TONE[s] || "muted"; }
    warrantyLabel(w) { return WARRANTY_LABEL[w] || ""; }

    catIcon(row) { return ic(row.icon || "package", 15); }

    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short", year: "numeric" });
        } catch (e) { return value; }
    }

    money(row) {
        if (!row.cost) { return ""; }
        const n = Math.round(row.cost).toLocaleString();
        return row.currency ? `${n} ${row.currency}` : n;
    }

    /** The comparison figure, worded so nobody mistakes it for the price paid.
     *  Built here and not in the template: OWL compiles template expressions
     *  against the component, so a bare `Math` in there is an undefined lookup,
     *  not the global. */
    usd(row) {
        if (!row.cost_usd) { return ""; }
        return _t("about %s USD", Math.round(row.cost_usd).toLocaleString());
    }

    // ------------------------------------------------------------- the drawer
    async openAsset(assetId) {
        try {
            this.state.drawer = await this.orm.call(
                "pb.assets", "get_asset", [assetId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    // --------------------------------------------------------------- actions
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            const res = await this.orm.call("pb.assets", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return res === undefined ? true : res;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    // ---- give it to somebody / move it on ----
    handAsk(mode) {
        const row = this.state.drawer.asset;
        this.state.hand = {
            mode,                       // "assign" | "transfer"
            assetId: row.id,
            term: "", results: [], empId: 0, empName: "",
            conditionOut: "", conditionIn: "",
            busy: false,
        };
        this.handSearch();
    }

    async handSearch() {
        const h = this.state.hand;
        if (!h) { return; }
        try {
            h.results = await this.orm.call(
                "pb.assets", "search_employees", [h.term || ""]);
        } catch (e) { h.results = []; }
    }

    onHandInput(ev) {
        this.state.hand.term = ev.target.value;
        this.state.hand.empId = 0;
        this.handSearch();
    }

    pickHandEmployee(emp) {
        const h = this.state.hand;
        h.empId = emp.id;
        h.empName = emp.name;
        h.term = emp.name;
        h.results = [];
    }

    async handSubmit() {
        const h = this.state.hand;
        if (!h.empId) {
            this.notif.add(_t("Choose the person first."), { type: "warning" });
            return;
        }
        h.busy = true;
        const ok = h.mode === "transfer"
            ? await this.call("transfer",
                [h.assetId, h.empId, h.conditionIn, h.conditionOut],
                _t("Moved across."))
            : await this.call("assign",
                [h.assetId, h.empId, h.conditionOut],
                _t("Handed over."));
        if (ok) {
            this.state.hand = null;
            await this.refresh();
        } else if (this.state.hand) {
            this.state.hand.busy = false;
        }
    }

    handCancel() { this.state.hand = null; }

    // ---- take it back ----
    backAsk(entry) {
        this.state.back = { assignmentId: entry.id, who: entry.employee,
                            condition: "" };
    }

    async backSubmit() {
        const b = this.state.back;
        this.state.back = null;
        if (await this.call("return_asset", [b.assignmentId, b.condition],
                            _t("Taken back."))) {
            await this.refresh();
        }
    }

    backCancel() { this.state.back = null; }

    // ---- change the status ----
    async setState(stateId) {
        if (await this.call("set_state",
                            [this.state.drawer.asset.id, stateId],
                            _t("Status changed."))) {
            await this.refresh();
        }
    }

    // ---- add an item ----
    /** The category a new item most likely is: the first PHYSICAL one, because
     *  a register is mostly laptops and an alphabetical list is not an opinion. */
    get defaultCategoryId() {
        const cats = this.state.categories;
        const first = cats.find((c) => c.kind === "tangible") || cats[0];
        return first ? first.id : 0;
    }

    /** Where the reader works, then wherever the register already has things. */
    get defaultCountryId() {
        if (this.state.homeCountryId) { return this.state.homeCountryId; }
        const first = this.state.countries[0] || this.state.countriesAll[0];
        return first ? first.id : 0;
    }

    addAsk() {
        this.state.add = {
            name: "", categoryId: this.defaultCategoryId,
            countryId: this.defaultCountryId,
            serial: "", modelName: "", cost: "", purchaseDate: "",
            warrantyEnd: "", invoiceRef: "", supplierNote: "",
            isReused: false, notes: "", busy: false,
        };
    }

    async addSave() {
        const a = this.state.add;
        if (!a.name.trim()) {
            this.notif.add(_t("Give the item a name first."),
                           { type: "warning" });
            return;
        }
        if (!a.categoryId || !a.countryId) {
            this.notif.add(_t("Choose the category and the country."),
                           { type: "warning" });
            return;
        }
        a.busy = true;
        const res = await this.call("create_asset", [{
            name: a.name, category_id: a.categoryId, country_id: a.countryId,
            serial: a.serial, model_name: a.modelName,
            cost: Number(a.cost) || 0,
            purchase_date: a.purchaseDate || false,
            warranty_end: a.warrantyEnd || false,
            invoice_ref: a.invoiceRef, supplier_note: a.supplierNote,
            is_reused: a.isReused, notes: a.notes,
        }]);
        if (res && res.id) {
            this.state.add = null;
            this.notif.add(_t("Added as %s.", res.code || ""),
                           { type: "success" });
            await Promise.all([this.load(), this.kit.refresh()]);
            await this.openAsset(res.id);
        } else if (this.state.add) {
            this.state.add.busy = false;
        }
    }

    addCancel() { this.state.add = null; }

    // ---- ask for something ----
    askOpen() {
        this.state.ask = {
            term: "", results: [], empId: 0, empName: "",
            categoryId: this.defaultCategoryId,
            neededBy: "", justification: "", busy: false,
        };
        this.askSearch();
    }

    async askSearch() {
        const a = this.state.ask;
        if (!a) { return; }
        try {
            a.results = await this.orm.call(
                "pb.assets", "search_employees", [a.term || ""]);
        } catch (e) { a.results = []; }
    }

    onAskInput(ev) {
        this.state.ask.term = ev.target.value;
        this.state.ask.empId = 0;
        this.askSearch();
    }

    pickAskEmployee(emp) {
        const a = this.state.ask;
        a.empId = emp.id;
        a.empName = emp.name;
        a.term = emp.name;
        a.results = [];
    }

    async askSubmit() {
        const a = this.state.ask;
        if (!a.empId) {
            this.notif.add(_t("Choose who it is for."), { type: "warning" });
            return;
        }
        a.busy = true;
        const res = await this.call("create_request", [{
            employee_id: a.empId, category_id: a.categoryId,
            needed_by: a.neededBy || false,
            justification: a.justification, submit: true,
        }]);
        if (res && res.id) {
            this.state.ask = null;
            this.notif.add(
                res.spare
                    ? _t("Asked for — and there is one spare already: %s.",
                         res.spare)
                    : _t("Asked for. It is with the approvers now."),
                { type: "success" });
            await this.load();
            this.state.segment = "requests";
        } else if (this.state.ask) {
            this.state.ask.busy = false;
        }
    }

    askCancel() { this.state.ask = null; }

    // ---- the bulk bar ----
    bulkAsk() {
        const options = this.bulkStates;
        if (!options.length) {
            this.notif.add(
                _t("These items cannot all take the same status. Pick items of "
                   + "one kind."), { type: "warning" });
            return;
        }
        this.state.bulk = { stateId: options[0].id, busy: false };
    }

    async bulkSubmit() {
        const b = this.state.bulk;
        b.busy = true;
        const res = await this.call(
            "bulk_set_state", [this.state.picked.slice(), b.stateId]);
        this.state.bulk = null;
        if (res) {
            this.notif.add(
                res.refused && res.refused.length
                    ? _t("%(done)s changed. %(left)s could not be: %(why)s",
                         { done: res.done, left: res.refused.length,
                           why: res.refused.join("; ") })
                    : _t("%s item(s) changed.", res.done),
                { type: res.refused && res.refused.length ? "warning"
                                                          : "success" });
            this.clearPicked();
            await this.refresh();
        }
    }

    bulkCancel() { this.state.bulk = null; }

    // ---- files ----
    /**
     * Every cut goes through one method, so a file can never be scoped more
     * widely than the board the reader is looking at: the facade re-applies
     * the same company domain it used to build the rows.
     */
    async exportFile(kind, kwargs = {}) {
        let res;
        try {
            res = await this.orm.call("pb.assets", "export", [kind], kwargs);
        } catch (e) {
            this.fail(e);
            return;
        }
        if (!res || !res.ok) {
            this.notif.add((res && res.msg)
                || _t("That file could not be built."), { type: "warning" });
            return;
        }
        this.download(res);
        this.notif.add(_t("%s row(s) in the file.", res.rows),
                       { type: "success" });
    }

    /** Just what this one person has had. */
    exportEmployee(employeeId) {
        return this.exportFile("employee", { employee_id: employeeId });
    }

    /** The register as it is filtered now: every page, not just this one. */
    exportFiltered() {
        const q = this.kit.query;
        return this.exportFile("inventory", { filters: q.filters, search: q.search });
    }

    /** Just the items ticked on the board. */
    exportPicked() {
        return this.exportFile("inventory",
                               { asset_ids: this.state.picked.slice() });
    }

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

    // ------------------------------------------------------------ the doors
    openRequests() {
        this.action.doAction("pb_assets.action_pb_asset_request");
    }

    openCategories() {
        this.action.doAction("pb_assets.action_pb_asset_category");
    }
}

registry.category("actions").add("pb_assets", PbAssetsBoard);
