/** @odoo-module **/
/**
 * `pb_goals_numbers` — the Goals lens on Insights.
 *
 * FIVE QUESTIONS, IN THE ORDER SOMEBODY ASKS THEM. Is anybody writing goals;
 * is anybody talking about them; is the work moving; is the plan still the
 * plan; and what did the year come out at. The middle one is the reason this
 * screen exists — a goal year where nobody has a monthly conversation is a
 * goal year that is not happening, and nothing else on any screen would say
 * so.
 *
 * NOTHING HERE RECOMPUTES A NUMBER. Every figure, every percentage and the
 * order the rows come in are the server's; a second opinion written in
 * JavaScript would only ever disagree with the one that counts. The helpers
 * below are presentation only — a bar's width relative to the widest bar, and
 * a dash where there is genuinely no answer.
 *
 * `props = ["*"]` because the hub shell injects `embedded: true` and a
 * component with a narrow props list refuses to mount over it. The template
 * consumes it in exactly two places: a modifier class on the root and the
 * hero it suppresses, which is the whole of the embedded contract.
 *
 * EVERY COLLECTION IN THE INITIAL STATE IS A COLLECTION (R195) and every
 * nested object carries the keys the template reads: a panel is rendered once
 * over the initial state before the first `await` resolves, and a `{}` where
 * the template reads `.length` throws inside OWL with nothing useful in the
 * console.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbGoalsNumbers extends Component {
    static template = "pb_goals.PbGoalsNumbers";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            allowed: true,
            busy: false,
            empty: true,
            why: "",
            headline: "",
            cycle: "",
            cycleId: 0,
            cycles: [],
            total: 0,
            tiles: [],
            rungs: [],
            byManager: [],
            byDepartment: [],
            bands: [],
            changes: { total: 0, kinds: [], sentence: "" },
            lists: { departments: [], managers: [] },
            filters: { department_id: 0, manager_id: 0 },
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    get anyFilter() {
        const f = this.state.filters;
        return !!(f.department_id || f.manager_id);
    }

    /** Only the filters somebody has actually set. An empty one is not one. */
    activeFilters() {
        const out = {};
        if (this.state.filters.department_id) {
            out.department_id = this.state.filters.department_id;
        }
        if (this.state.filters.manager_id) {
            out.manager_id = this.state.filters.manager_id;
        }
        return out;
    }

    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals.analytics", "get_numbers",
                [this.state.cycleId || null, this.activeFilters()]);
            if (d.allowed === false) {
                Object.assign(this.state, {
                    loaded: true, allowed: false, why: d.why || "" });
                return;
            }
            Object.assign(this.state, {
                loaded: true,
                allowed: true,
                empty: !!d.empty,
                headline: d.headline || "",
                cycle: d.cycle || "",
                cycleId: d.cycle_id || 0,
                cycles: d.cycles || [],
                total: d.total || 0,
                tiles: d.tiles || [],
                rungs: d.rungs || [],
                byManager: d.by_manager || [],
                byDepartment: d.by_department || [],
                bands: d.bands || [],
                changes: Object.assign(
                    { total: 0, kinds: [], sentence: "" }, d.changes || {}),
                lists: Object.assign(
                    { departments: [], managers: [] }, d.lists || {}),
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            this.state.why = _t("The goal numbers could not be read.");
            console.warn("pb_goals: the numbers could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    async pickCycle(ev) {
        this.state.cycleId = Number(ev.target.value) || 0;
        await this.load();
    }

    async setFilter(key, value) {
        this.state.filters[key] = Number(value) || 0;
        await this.load();
    }

    async clearFilters() {
        this.state.filters = { department_id: 0, manager_id: 0 };
        await this.load();
    }

    // =================================================================
    //  presentation only — nothing here is a figure
    // =================================================================
    /** A dash where there is genuinely no answer, never a nought (R207). */
    pct(value) {
        if (value === null || value === undefined || value === "") {
            return "—";
        }
        return `${value}%`;
    }

    score(value) {
        if (value === null || value === undefined || value === "") {
            return "—";
        }
        return String(value);
    }

    /** The widest bar in a table is 100%; everything else is relative. */
    share(rows, value) {
        let top = 0;
        for (const row of rows) {
            if (Number(row.sheets || 0) > top) { top = Number(row.sheets); }
        }
        if (!top) { return 0; }
        return Math.round((Number(value || 0) / top) * 100);
    }

    /** Compliance decides the colour, and the thresholds are the server's. */
    complianceTone(value) {
        if (value === null || value === undefined) { return ""; }
        if (value >= 90) { return "ok"; }
        return value < 60 ? "bad" : "warn";
    }

    // =================================================================
    //  the spreadsheet
    // =================================================================
    async download() {
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.goals.analytics", "export_xlsx",
                [this.state.cycleId || null, this.activeFilters()]);
            if (!res || !res.file_b64) { return; }
            // A BLOB AND NOT A CONTROLLER: the bytes are already in hand, so
            // the browser saves them without leaving the page and nothing is
            // left behind on the server. An export is a copy somebody takes
            // away, not a record.
            const binary = window.atob(res.file_b64);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i);
            }
            const blob = new Blob([bytes], { type: res.mimetype });
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = res.filename || "goals.xlsx";
            link.click();
            URL.revokeObjectURL(url);
            this.notif.add(_t("The spreadsheet has been downloaded."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(
                (e && e.data && e.data.message)
                    || _t("The spreadsheet could not be built."),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  the doors
    // =================================================================
    async openCheckins(managerId) {
        const action = await this.orm.call(
            "pb.goals.analytics", "open_checkins",
            [this.state.cycleId || null, managerId || null]);
        await this.action.doAction(action);
    }

    async openChanges() {
        const action = await this.orm.call(
            "pb.goals.analytics", "open_changes", [this.state.cycleId || null]);
        await this.action.doAction(action);
    }
}

registry.category("actions").add("pb_goals_numbers", PbGoalsNumbers);
