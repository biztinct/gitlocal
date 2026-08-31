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
            capped: false,

            // what the reader is looking at
            segment: "items",       // items | requests

            // filters
            q: "",
            kind: "all",
            status: "all",
            categoryId: 0,
            countryId: 0,

            // selection for the bulk bar
            picked: [],

            // the open item
            drawer: null,

            // dialogs — one at a time, each one plain state
            add: null,
            hand: null,
            back: null,
            ask: null,
            bulk: null,
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
                rows: d.rows || [],
                categories: d.categories || [],
                countries: d.countries || [],
                countriesAll: d.countries_all || d.countries || [],
                states: d.states || [],
                kinds: d.kinds || [],
                facets: d.facets || {},
                requests: d.requests || {},
                homeCountryId: d.home_country_id || 0,
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            console.warn("pb_assets: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        const openId = this.state.drawer && this.state.drawer.asset.id;
        await this.load();
        if (openId) { await this.openAsset(openId); }
    }

    // --------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.kind !== "all" && r.kind !== this.state.kind) {
                return false;
            }
            if (this.state.status !== "all" && r.state !== this.state.status) {
                return false;
            }
            if (this.state.categoryId && r.category_id !== this.state.categoryId) {
                return false;
            }
            if (this.state.countryId && r.country_id !== this.state.countryId) {
                return false;
            }
            if (!q) { return true; }
            return (r.code + " " + r.name + " " + (r.serial || "") + " "
                + (r.employee || "") + " " + (r.category || "") + " "
                + (r.model_name || "")).toLowerCase().includes(q);
        });
    }

    get hasFilters() {
        return this.state.q || this.state.kind !== "all"
            || this.state.status !== "all" || this.state.categoryId
            || this.state.countryId;
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", kind: "all", status: "all", categoryId: 0, countryId: 0,
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setKind(id) { this.state.kind = this.state.kind === id ? "all" : id; }
    setStatus(id) { this.state.status = this.state.status === id ? "all" : id; }
    setCategory(id) {
        this.state.categoryId = this.state.categoryId === id ? 0 : id;
    }
    onCountry(ev) { this.state.countryId = Number(ev.target.value) || 0; }
    setSegment(seg) { this.state.segment = seg; }

    /** Only the statuses this board is actually showing — an empty filter is
     *  a promise the screen cannot keep. */
    get statusChips() {
        const counts = this.state.facets.state || {};
        return this.state.states.filter((s) => counts[s.id]);
    }

    get categoryChips() {
        const counts = this.state.facets.category || {};
        return this.state.categories.filter((c) => counts[c.id]);
    }

    countFor(bucket, id) {
        return (this.state.facets[bucket] || {})[id] || 0;
    }

    // ------------------------------------------------------------- selection
    isPicked(id) { return this.state.picked.includes(id); }

    togglePick(id) {
        const at = this.state.picked.indexOf(id);
        if (at === -1) { this.state.picked.push(id); }
        else { this.state.picked.splice(at, 1); }
    }

    pickAllVisible() {
        const ids = this.visibleRows.map((r) => r.id);
        const allOn = ids.every((id) => this.state.picked.includes(id));
        this.state.picked = allOn ? [] : ids;
    }

    clearPicked() { this.state.picked = []; }

    /** The statuses every picked item could legally take. A mixed selection of
     *  laptops and email accounts offers only what both can do. */
    get bulkStates() {
        const picked = this.state.rows.filter(
            (r) => this.state.picked.includes(r.id));
        if (!picked.length) { return []; }
        const digital = picked.some((r) => r.kind === "digital");
        const tangible = picked.some((r) => r.kind === "tangible");
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
            await this.load();
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
            this.state.picked = [];
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
