/** @odoo-module **/
/**
 * `pb_goals_board` — the Goals lens on the People hub.
 *
 * ONE BOARD, TWO READERS, AND THE SERVER DECIDES WHICH. A manager opening this
 * sees their own team; the HR team sees the company. That is not a switch on
 * the screen and it is not two lenses — it is the record rules doing what
 * record rules are for, with one honest sentence at the top saying whose
 * sheets are on the board. A screen that asks somebody to choose a scope they
 * do not have is a screen with a dead end in it.
 *
 * NOTHING HERE RECOMPUTES A NUMBER. The server works out every figure, every
 * ratio and the order the rows come in; a second opinion written in JavaScript
 * would only ever disagree with the one that counts.
 *
 * PROBLEM FIRST (R113). The rows arrive ranked by what somebody has to DO
 * about them — sent back, never written, waiting on a manager, waiting on HR,
 * then the ones that are finished — and never by the spelling of the status,
 * which is alphabetical order pretending to be lifecycle order (R50).
 *
 * EVERY COLLECTION IN THE INITIAL STATE IS A COLLECTION (R195): a panel is
 * rendered ONCE over the initial state before the `await` that fetches its
 * data has resolved, so a `{}` where the template reads `.length` throws
 * "Cannot read properties of undefined", which the theme shows as a generic
 * "something went wrong" dialog with nothing useful in the console.
 *
 * Every icon comes from the shared `ic()` registry in pb_import_kit — the set
 * is CLOSED and an unknown name renders a plain circle with no error, so a
 * name used here is a name that is in that file.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The chip colour for each status. Problem first, and never by spelling. */
const STATE_TONE = {
    returned: "bad",
    draft: "wait",
    submitted: "wait",
    manager_ok: "wait",
    refused: "bad",
    locked: "ok",
};

const STATE_ICON = {
    returned: "undo",
    draft: "pencil",
    submitted: "clock",
    manager_ok: "clock",
    refused: "xCircle",
    locked: "lock",
};

export class PbGoalsBoard extends Component {
    static template = "pb_goals.PbGoalsBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");

        this.state = useState({
            loaded: false,
            allowed: true,
            busy: false,
            why: "",
            isHr: false,
            scope: "",
            headline: "",
            today: "",
            cycles: [],
            cycleId: 0,
            rows: [],
            stats: [],
            bar: [],
            facets: { departments: [], managers: [] },
            states: [],
            remindersOn: true,
            myPage: false,
            filters: { state: "", department_id: 0, manager_id: 0, q: "",
                       mine: false },
            // The drawer. Every nested object carries the keys the template
            // reads, because the drawer is rendered before its payload lands.
            open: false,
            sheet: { goals: [], history: [], ok: false },
            weights: {},
            weightTotal: 0,
            weightsOk: false,
            weightWord: "",
            backNote: "",
            backOpen: false,
            bulk: null,
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    tone(key) { return STATE_TONE[key] || "wait"; }
    stateIcon(key) { return STATE_ICON[key] || "circle"; }

    get cycle() {
        return this.state.cycles.find((c) => c.id === this.state.cycleId)
            || null;
    }

    /**
     * The drawer's one-line subtitle.
     *
     * BUILT HERE AND NOT IN THE TEMPLATE. `[a, b, c].filter(Boolean)` is
     * ordinary JavaScript and dies inside an OWL template with *"undefined is
     * not a function"* — the compiled expression runs in a restricted scope
     * that does not carry `Boolean`, and the whole component then fails to
     * render with the real cause two levels down an OwlError's `cause`. The
     * drawer simply never opened. Anything a template needs that is not a
     * property or a method of the component belongs in the component.
     */
    get drawerSub() {
        const s = this.state.sheet;
        return [s.job, s.department, s.cycle].filter((v) => !!v).join(" · ");
    }

    get anyFilter() {
        const f = this.state.filters;
        return !!(f.state || f.department_id || f.manager_id || f.q || f.mine);
    }

    // =================================================================
    //  reading
    // =================================================================
    async load() {
        this.state.busy = true;
        try {
            const f = this.state.filters;
            const payload = { cycle_id: this.state.cycleId };
            if (f.state) { payload.state = f.state; }
            if (f.department_id) { payload.department_id = f.department_id; }
            if (f.manager_id) { payload.manager_id = f.manager_id; }
            if (f.q) { payload.q = f.q; }
            if (f.mine) { payload.mine = true; }
            const d = await this.orm.call("pb.goals", "get_board", [payload]);
            if (d.allowed === false) {
                Object.assign(this.state, {
                    loaded: true, allowed: false, why: d.why || "" });
                return;
            }
            Object.assign(this.state, {
                loaded: true,
                allowed: true,
                isHr: !!d.is_hr,
                scope: d.scope || "",
                headline: d.headline || "",
                today: d.today || "",
                cycles: d.cycles || [],
                cycleId: d.cycle_id || 0,
                rows: d.rows || [],
                stats: d.stats || [],
                bar: d.bar || [],
                facets: d.facets || { departments: [], managers: [] },
                states: d.states || [],
                remindersOn: d.reminders_on !== false,
                myPage: !!d.my_page,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            this.state.why = _t("The goals board could not be read.");
            console.warn("pb_goals: the board could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    async pickCycle(id) {
        this.state.cycleId = Number(id) || 0;
        await this.load();
    }

    /** A chip that is already on is a chip that turns off — otherwise the
     *  only way back to everything is a page reload, which is a dead end. */
    async setFilter(key, value) {
        const current = this.state.filters[key];
        const blank = key === "state" ? "" : 0;
        this.state.filters[key] =
            String(current) === String(value) ? blank : value;
        await this.load();
    }

    async toggleMine() {
        this.state.filters.mine = !this.state.filters.mine;
        await this.load();
    }

    onSearch(ev) {
        this.state.filters.q = ev.target.value || "";
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.load(), 260);
    }

    async clearFilters() {
        this.state.filters = { state: "", department_id: 0, manager_id: 0,
                               q: "", mine: false };
        await this.load();
    }

    // =================================================================
    //  the drawer
    // =================================================================
    async openSheet(id) {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.goals", "get_set", [id]);
            if (!d.ok) {
                this.notif.add(d.why || _t("That one could not be opened."),
                               { type: "warning" });
                return;
            }
            this.state.sheet = Object.assign(
                { goals: [], history: [] }, d);
            this.state.weights = {};
            for (const goal of d.goals || []) {
                this.state.weights[goal.id] = goal.weight;
            }
            this.state.weightTotal = d.weight_total || 0;
            this.state.weightsOk = !!d.weights_ok;
            this.state.weightWord = "";
            this.state.backNote = "";
            this.state.backOpen = false;
            this.state.open = true;
        } catch (e) {
            this.notif.add(_t("That one could not be opened."),
                           { type: "danger" });
            console.warn("pb_goals: the drawer could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    closeDrawer() {
        this.state.open = false;
    }

    /** The running total moves as the manager types, so nobody has to add up
     *  four numbers in their head to find out why the button is off. */
    onWeight(goalId, ev) {
        const value = Math.max(0, Math.min(100, Number(ev.target.value) || 0));
        this.state.weights[goalId] = value;
        let total = 0;
        for (const key of Object.keys(this.state.weights)) {
            total += Number(this.state.weights[key]) || 0;
        }
        this.state.weightTotal = Math.round(total * 10) / 10;
        this.state.weightsOk = Math.abs(total - 100) < 0.01;
    }

    async saveWeights() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "set_weights",
                [this.state.sheet.id, this.state.weights]);
            this.state.weightTotal = d.weight_total;
            this.state.weightsOk = !!d.weights_ok;
            this.state.weightWord = d.sentence || "";
            this.notif.add(d.sentence || _t("Saved."),
                           { type: d.weights_ok ? "success" : "warning" });
            await this.load();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    static reason(e) {
        return (e && e.data && e.data.message)
            || (e && e.message) || _t("That did not work.");
    }

    async sendBack() {
        const note = (this.state.backNote || "").trim();
        if (!note) {
            this.notif.add(
                _t("Write what you would like changed — a sheet that comes "
                   + "back with no note is a sheet somebody has to guess "
                   + "about."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "send_back", [this.state.sheet.id, note]);
            this.notif.add(d.sentence || _t("Sent back."),
                           { type: "success" });
            this.state.open = false;
            await this.load();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  the doors
    // =================================================================
    async openRecord(id) {
        const action = await this.orm.call("pb.goals", "open_set", [id]);
        await this.action.doAction(action);
    }

    async openCycles() {
        const action = await this.orm.call("pb.goals", "open_cycles", []);
        await this.action.doAction(action);
    }

    async openTemplates() {
        const action = await this.orm.call("pb.goals", "open_templates", []);
        await this.action.doAction(action);
    }

    // =================================================================
    //  opening a year for everybody
    // =================================================================
    /** IT SAYS HOW MANY BEFORE IT MAKES ANY (R54). A button that writes to
     *  four thousand people has to be a button somebody presses twice. */
    async askBulk() {
        if (!this.state.cycleId) { return; }
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "preview_open_for_everyone",
                [this.state.cycleId]);
            this.state.bulk = d;
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    closeBulk() { this.state.bulk = null; }

    async doBulk() {
        this.state.busy = true;
        try {
            const d = await this.orm.call(
                "pb.goals", "open_for_everyone", [this.state.cycleId]);
            this.notif.add(d.sentence || _t("Done."), { type: "success" });
            this.state.bulk = null;
            await this.load();
        } catch (e) {
            this.notif.add(this.constructor.reason(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * A figure a person reads, with the thousands in it.
     *
     * A Vietnamese revenue target is ten digits long, and ten digits with no
     * separators is a number nobody reads — they count the noughts. Trailing
     * zeroes after the point are dropped so "40" stays "40".
     */
    num(value) {
        const n = Number(value || 0);
        if (!isFinite(n)) { return "0"; }
        return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    /** One key result's figures, as the one string the drawer prints. */
    krWords(kr) {
        const parts = [this.num(kr.current)];
        if (kr.target) { parts.push("/ " + this.num(kr.target)); }
        if (kr.measure) { parts.push(kr.measure); }
        return parts.join(" ");
    }

    /** The widest bar in a table is 100%; everything else is relative to it. */
    share(value, top) {
        if (!top) { return 0; }
        return Math.round((Number(value || 0) / Number(top)) * 100);
    }
}

registry.category("actions").add("pb_goals_board", PbGoalsBoard);
