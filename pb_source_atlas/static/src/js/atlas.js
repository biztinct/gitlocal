/** @odoo-module **/
/**
 * Source Atlas — where every number in a pay run came from.
 *
 * Three views over ONE state: the lanes a run's values arrived through, the
 * employees x components grid tinted by those lanes, and the journey of a single
 * value from the key it arrived on to net pay.
 *
 * RPC facade: pb.source.atlas (read-only). Icons come from the shared kit
 * registry — a per-module icon map is how a design system stops being one.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.source.atlas";
const COL_PAGE = 18; // components rendered at once — the DOM stays small (C8)
const ROW_PAGE = 40; // rows rendered at once; the window is taken server-side

const ROLE_META = {
    earning: { label: _t("Adds to net pay"), tone: "pos" },
    deduction: { label: _t("Taken off net pay"), tone: "neg" },
    net: { label: _t("Net pay"), tone: "net" },
    employer_cost: { label: _t("Employer cost"), tone: "cost" },
    info: { label: _t("Information only"), tone: "info" },
    mixed: { label: _t("Both added and taken off"), tone: "info" },
};

export class PbSourceAtlas extends Component {
    static template = "pb_source_atlas.Atlas";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.roleMeta = ROLE_META;

        const params = this.props.action?.params || {};
        const ctx = this.props.action?.context || {};
        this.runId = params.run_id || ctx.active_id || 0;

        this.state = useState({
            loading: true,
            error: "",
            view: "lanes",
            atlas: null,
            grid: null,
            gridLoading: false,
            offset: 0,
            search: "",
            laneFilter: "",
            band: "",
            compSearch: "",
            colOffset: 0,
            journey: null,
            journeyLoading: false,
            journeyKey: "",
            downloading: "",
        });

        this._searchToken = 0;
        onWillStart(() => this.load());
    }

    // ---------------------------------------------------------------- data
    async load() {
        this.state.loading = true;
        this.state.error = "";
        try {
            this.state.atlas = await this.orm.call(MODEL, "get_run_atlas", [this.runId]);
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || _t("Could not read this pay run.");
        }
        this.state.loading = false;
    }

    async loadGrid() {
        this.state.gridLoading = true;
        const token = ++this._searchToken;
        try {
            const grid = await this.orm.call(MODEL, "get_grid", [this.runId], {
                offset: this.state.offset,
                limit: ROW_PAGE,
                search: this.state.search,
                lane: this.state.laneFilter || null,
                band: this.state.band || null,
            });
            // A superseded request must never overwrite a newer answer (C8).
            if (token === this._searchToken) {
                this.state.grid = grid;
            }
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || _t("Could not read the grid.");
        }
        if (token === this._searchToken) {
            this.state.gridLoading = false;
        }
    }

    // ---------------------------------------------------------------- views
    async showLanes() {
        this.state.view = "lanes";
    }

    async showGrid() {
        this.state.view = "grid";
        this.state.grid || (await this.loadGrid());
    }

    async focusLane(laneKey) {
        this.state.laneFilter = this.state.laneFilter === laneKey ? "" : laneKey;
        this.state.offset = 0;
        this.state.colOffset = 0;
        this.state.view = "grid";
        await this.loadGrid();
    }

    async setBand(band) {
        this.state.band = this.state.band === band ? "" : band;
        this.state.colOffset = 0;
        await this.loadGrid();
    }

    onSearch(ev) {
        this.state.search = ev.target.value || "";
        this.state.offset = 0;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.loadGrid(), 260);
    }

    onComponentSearch(ev) {
        this.state.compSearch = ev.target.value || "";
        this.state.colOffset = 0;
    }

    async pageRows(delta) {
        const next = this.state.offset + delta * ROW_PAGE;
        this.state.offset = Math.max(0, Math.min(next, Math.max(0, (this.state.grid?.total || 1) - 1)));
        await this.loadGrid();
    }

    pageCols(delta) {
        const next = this.state.colOffset + delta * COL_PAGE;
        this.state.colOffset = Math.max(0, Math.min(next, Math.max(0, this.visibleComponents.length - 1)));
    }

    // ---------------------------------------------------------------- journey
    async openJourney(slipId, code) {
        this.state.journeyLoading = true;
        this.state.journeyKey = `${slipId}:${code}`;
        try {
            this.state.journey = await this.orm.call(MODEL, "get_journey", [this.runId, slipId, code]);
        } catch (error) {
            this.notif.add(error?.data?.message || error?.message || _t("Could not trace that value."), {
                type: "danger",
            });
        }
        this.state.journeyLoading = false;
    }

    closeJourney() {
        this.state.journey = null;
        this.state.journeyKey = "";
    }

    async reanchor(code) {
        const slipId = this.state.journey?.slip_id;
        return slipId ? this.openJourney(slipId, code) : undefined;
    }

    // ---------------------------------------------------------------- download
    async download(lane) {
        this.state.downloading = lane;
        try {
            const act = await this.orm.call(MODEL, "download_lane", [this.runId, lane]);
            await this.action.doAction(act);
        } catch (error) {
            this.notif.add(error?.data?.message || error?.message || _t("Nothing to export."), {
                type: "warning",
            });
        }
        this.state.downloading = "";
    }

    async runPayroll() {
        await this.action.doAction("pb_payrun_wizard.action_pb_payrun_wizard");
    }

    // ---------------------------------------------------------------- getters
    get colPage() {
        return COL_PAGE;
    }

    get run() {
        return this.state.atlas?.run || {};
    }

    get lanes() {
        return this.state.atlas?.lanes || [];
    }

    get activeLanes() {
        return this.lanes.filter((l) => !l.muted);
    }

    get bands() {
        return this.state.atlas?.bands || [];
    }

    get components() {
        return this.state.atlas?.components || [];
    }

    /** Components the grid may show, after the lane / band / text filters. */
    get visibleComponents() {
        const term = (this.state.compSearch || "").trim().toUpperCase();
        return this.components.filter((c) => {
            const laneOk = !this.state.laneFilter || (c.lanes || {})[this.state.laneFilter];
            const bandOk = !this.state.band || c.band === this.state.band;
            const textOk = !term || c.code.toUpperCase().includes(term) || (c.name || "").toUpperCase().includes(term);
            return laneOk && bandOk && textOk;
        });
    }

    /** The window of columns actually rendered. */
    get windowComponents() {
        return this.visibleComponents.slice(this.state.colOffset, this.state.colOffset + COL_PAGE);
    }

    get rows() {
        return this.state.grid?.rows || [];
    }

    get rowRangeLabel() {
        const total = this.state.grid?.total || 0;
        if (!total) {
            return _t("no employees");
        }
        const from = this.state.offset + 1;
        const to = Math.min(this.state.offset + this.rows.length, total);
        return _t("%(from)s–%(to)s of %(total)s employees", { from, to, total });
    }

    get colRangeLabel() {
        const total = this.visibleComponents.length;
        if (!total) {
            return _t("no components match");
        }
        const from = this.state.colOffset + 1;
        const to = Math.min(this.state.colOffset + COL_PAGE, total);
        return _t("%(from)s–%(to)s of %(total)s components", { from, to, total });
    }

    get journeyHops() {
        return this.state.journey?.hops || [];
    }

    laneMeta(key) {
        return this.lanes.find((l) => l.key === key) || { label: key, tone: "slate", icon: "minusCircle" };
    }

    cellOf(row, code) {
        return (row.cells || {})[code];
    }

    // ---------------------------------------------------------------- format
    money(value) {
        const currency = this.state.atlas?.currency || this.state.journey?.currency || {};
        const n = Number(value || 0);
        const text = new Intl.NumberFormat(undefined, {
            maximumFractionDigits: currency.decimals ?? 2,
            minimumFractionDigits: 0,
        }).format(n);
        return currency.position === "before" ? `${currency.symbol || ""}${text}` : `${text}${currency.symbol ? " " + currency.symbol : ""}`;
    }

    num(value) {
        if (value === null || value === undefined || value === "") {
            return "—";
        }
        if (typeof value === "number") {
            return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value);
        }
        return String(value);
    }

    short(value, length = 14) {
        const text = this.num(value);
        return text.length > length ? `${text.slice(0, length - 1)}…` : text;
    }

    roleTone(role) {
        return (ROLE_META[role] || {}).tone || "info";
    }

    roleLabel(role) {
        return (ROLE_META[role] || {}).label || _t("Not classified");
    }
}

registry.category("actions").add("pb_source_atlas_cockpit", PbSourceAtlas);
