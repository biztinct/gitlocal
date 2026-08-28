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
import { ComponentTreatmentBoard } from "@pb_formula_studio/js/component_treatment";

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
    static components = { ComponentTreatmentBoard };

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

    /**
     * Back to the pay run this Atlas is about.
     *
     * The cockpit is a client action opened from the run's form, and in
     * full-screen mode Odoo's own breadcrumb is hidden — so the only way back
     * was the browser button, which is not an affordance anyone should have to
     * find. This is the same move the "Batch Payslips" breadcrumb makes on the
     * form itself.
     */
    async backToRun() {
        // POP the breadcrumb rather than push a new one: `doAction` would put
        // the run form ON TOP of the cockpit and leave a trail reading
        // `Batch Payslips > Payroll June 2026 > Where the numbers come from >
        // Payroll June 2026`.
        //
        // `env.config.breadcrumbs` INCLUDES the current controller as its last
        // entry, so "more than one" is what says there is somewhere to go back
        // to; `historyBack` is the web client's own back and pops exactly one.
        const crumbs = this.env.config?.breadcrumbs || [];
        if (crumbs.length > 1 && this.env.config?.historyBack) {
            return this.env.config.historyBack();
        }
        if (crumbs.length > 1) {
            return this.action.restore(crumbs[crumbs.length - 2].jsId);
        }
        // Opened straight from a URL, so there is nothing to pop back to.
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.payslip.run",
            res_id: this.runId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---------------------------------------------------------------- views
    async showLanes() {
        this.state.view = "lanes";
    }

    async showGrid() {
        this.state.view = "grid";
        this.state.grid || (await this.loadGrid());
    }

    showTypes() {
        this.state.view = "types";
    }

    // ------------------------------------------- VALUEKIND: component setup
    /**
     * The board itself moved to Settings -> Integrations -> Mappings (P5).
     *
     * What it edits belongs to the SCHEME: change a pay role while standing in
     * June's pay run and you have changed July, August and every run already
     * computed. The Atlas is where you NOTICE that something is wrong — the
     * amber "stored differently" banner is genuinely about THIS run — so it
     * still shows the board, read-only, and sends you to the one place that
     * can change it. `ComponentTreatmentBoard` is one implementation rendered
     * in two hosts, so the two can never disagree.
     */
    get treatmentConfigId() {
        return this.state.atlas?.config_ids?.[0] || false;
    }

    openTreatment() {
        this.action.doAction("pb_formula_studio.action_pb_mapping_studio", {
            // `pb_config`, not `pb_config_id` — the Studio's arrival keys are
            // pb_mode / pb_connector / pb_endpoint / pb_config.
            additionalContext: { pb_mode: "treatment",
                                 pb_config: this.treatmentConfigId },
        });
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

    /**
     * Format a value by what it IS, not by what JavaScript thinks its type is.
     *
     * `num()` groups every JS number, which is right for an amount and wrong for
     * an employee code — 11450 is a name, and "11,450" is a name nobody has. The
     * kind comes from the component's `value_kind` (server-side ladder), so this
     * is a rendering of a decision, never a second guess at it.
     */
    kindly(value, kind) {
        if (value === null || value === undefined || value === "") {
            return "—";
        }
        // An unset Char reads as `false` through the ORM, so a text field with
        // nothing in it arrives here as the boolean. Only a yes/no field means
        // the word.
        if (value === false && kind !== "boolean") {
            return "—";
        }
        switch (kind) {
            case "identifier":
                // Verbatim. Leading zeros, if they survived, are the point.
                return String(value);
            case "text":
            case "boolean":
                return String(value);
            case "date":
                return this.dateText(value);
            case "money":
                return typeof value === "number" ? this.money(value) : String(value);
            case "quantity":
            case "rate":
                return this.num(value);
            default:
                return this.num(value);
        }
    }

    /** A date in the reader's own format (vi-VN → 04-04-2022), or as it arrived. */
    dateText(value) {
        const text = String(value).trim();
        const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!iso) {
            return text;
        }
        const parsed = new Date(Number(iso[1]), Number(iso[2]) - 1, Number(iso[3]));
        if (Number.isNaN(parsed.getTime())) {
            return text;
        }
        return new Intl.DateTimeFormat(this.localeName, {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }).format(parsed);
    }

    get localeName() {
        // The user's language, so a Vietnamese reader gets dd-mm-yyyy without
        // this component owning a date-format table of its own.
        return (this.env.services.user?.lang || navigator.language || "en-US").replace("_", "-");
    }

    short(value, length = 14, kind = null) {
        const text = kind ? this.kindly(value, kind) : this.num(value);
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
