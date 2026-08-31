/** @odoo-module **/
/**
 * `pb_exits_board` — the Exits lens on the Lifecycle hub.
 *
 * The Journeys board answers "what is running" and the New joiners board
 * answers "who is arriving". This one answers the question an HR coordinator
 * asks on the last Friday of a month: WHO IS LEAVING, and is there any reason
 * their last payment cannot go out. So a row is a PERSON, and the four things
 * beside their name are the four things that hold the money — the clearances,
 * the equipment, the checklist and the settlement itself.
 *
 * THE CLEARANCE GRID IS THE HERO. Four lights per person, clickable, and a
 * click opens a dialog that signs the desk off with a note. Everything else on
 * the row is a door to a screen that already exists.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change anything.
 * `pb.exits._require_write()` and `pb.exit.clearance._can_clear()` are the
 * boundary; `state.canWrite` only decides whether a control is OFFERED, because
 * an offer the server would refuse is worse than no offer (W29).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** How a clearance reads as a light. */
const CLEARANCE_CLS = {
    cleared: "ok",
    pending: "wait",
    na: "na",
    missing: "missing",
};

/** What a clearance light says when you hover it. */
const CLEARANCE_WORD = {
    cleared: _t("signed off"),
    pending: _t("still open"),
    na: _t("nothing to sign off"),
    missing: _t("no row yet"),
};

export class PbExitsBoard extends Component {
    static template = "pb_offboarding.PbExitsBoard";
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
            countries: [],
            departments: [],
            months: [],
            depts: [],
            capped: false,

            // filters
            q: "",
            country: "all",
            dept: "all",
            month: "all",
            blockedOnly: false,

            // the open leaver
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, each one plain state
            clearing: null,
            farewell: null,
            kt: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.exits", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                kpis: d.kpis || {},
                rows: d.rows || [],
                countries: d.countries || [],
                departments: d.departments || [],
                months: d.months || [],
                depts: d.depts || [],
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_offboarding: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openExit(this.state.drawer.leaver.id);
        }
    }

    // --------------------------------------------------------------- filters
    get visibleRows() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.country !== "all" && r.country !== this.state.country) {
                return false;
            }
            if (this.state.dept !== "all" && r.dept !== this.state.dept) {
                return false;
            }
            if (this.state.month !== "all" && r.month !== this.state.month) {
                return false;
            }
            if (this.state.blockedOnly && !this.isBlocked(r)) {
                return false;
            }
            if (!q) { return true; }
            return (r.employee + " " + (r.job || "") + " " + (r.dept || ""))
                .toLowerCase().includes(q);
        });
    }

    /** "Something is holding this exit up" — the one filter that matters. */
    isBlocked(row) {
        if (row.ff.closed) { return false; }
        return !!(row.assets
            || row.clearances.some((c) => c.state === "pending")
            || row.overdue
            || row.kt_open);
    }

    get hasFilters() {
        return this.state.q || this.state.country !== "all"
            || this.state.dept !== "all" || this.state.month !== "all"
            || this.state.blockedOnly;
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", country: "all", dept: "all", month: "all",
            blockedOnly: false,
        });
    }

    onSearch(ev) { this.state.q = ev.target.value; }
    setCountry(id) { this.state.country = this.state.country === id ? "all" : id; }
    setDept(id) { this.state.dept = this.state.dept === id ? "all" : id; }
    setMonth(id) { this.state.month = this.state.month === id ? "all" : id; }
    toggleBlocked() { this.state.blockedOnly = !this.state.blockedOnly; }

    // ------------------------------------------------------------ formatting
    clearanceCls(state) { return CLEARANCE_CLS[state] || "missing"; }

    clearanceTitle(cell) {
        const word = CLEARANCE_WORD[cell.state] || CLEARANCE_WORD.missing;
        const owner = cell.owner ? " · " + cell.owner : "";
        // ONE expression: a sentence split across several t-esc nodes loses the
        // whitespace between them (R34).
        return cell.label + " — " + word + owner;
    }

    /** The settlement chip, as a word and a tone. */
    ffChip(row) {
        if (row.ff.closed) {
            return { cls: "ok", text: _t("Settlement closed") };
        }
        if (!row.ff.id) {
            return { cls: "muted", text: _t("No settlement yet") };
        }
        if (row.ff.ready) {
            return { cls: "warn", text: _t("Ready to close") };
        }
        return { cls: "err", text: _t("Held up") };
    }

    day(value) {
        if (!value) { return "—"; }
        try {
            const d = new Date(value + "T00:00:00");
            return d.toLocaleDateString(undefined,
                { day: "numeric", month: "short" });
        } catch (e) { return value; }
    }

    monthLabel(value) {
        if (!value) { return ""; }
        try {
            const d = new Date(value + "-01T00:00:00");
            return d.toLocaleDateString(undefined,
                { month: "short", year: "numeric" });
        } catch (e) { return value; }
    }

    // --------------------------------------------------------------- plumbing
    fail(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work. Try again in a moment.");
        this.notif.add(msg, { type: "danger" });
    }

    async call(method, args, okMessage) {
        try {
            const res = await this.orm.call("pb.exits", method, args);
            if (okMessage) { this.notif.add(okMessage, { type: "success" }); }
            return res === undefined ? true : res;
        } catch (e) {
            this.fail(e);
            return false;
        }
    }

    // ------------------------------------------------------------- the drawer
    async openExit(caseId) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.exits", "get_exit", [caseId]);
        } catch (e) {
            this.fail(e);
            this.state.drawer = null;
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() { this.state.drawer = null; }

    get drawerOpenTasks() {
        if (!this.state.drawer) { return []; }
        return this.state.drawer.tasks.filter(
            (t) => ["pending", "in_progress", "blocked"].includes(t.state));
    }

    get drawerDoneTasks() {
        if (!this.state.drawer) { return []; }
        return this.state.drawer.tasks.filter(
            (t) => ["done", "skipped"].includes(t.state));
    }

    // ------------------------------------------------------ sign a desk off
    askClear(row, cell) {
        if (!cell.id) {
            this.notif.add(
                _t("This exit has no clearance rows yet. Open the leaving checklist and they are created."),
                { type: "warning" });
            return;
        }
        if (cell.state !== "pending") {
            this.notif.add(
                _t("%(desk)s was already answered for %(who)s.",
                   { desk: cell.label, who: row.employee }),
                { type: "info" });
            return;
        }
        this.state.clearing = {
            id: cell.id,
            desk: cell.label,
            who: row.employee,
            owner: cell.owner || "",
            note: "",
            busy: false,
        };
    }

    onClearNote(ev) { this.state.clearing.note = ev.target.value; }
    cancelClear() { this.state.clearing = null; }

    async doClear(notNeeded = false) {
        const c = this.state.clearing;
        if (!c || c.busy) { return; }
        c.busy = true;
        const ok = await this.call(
            "clear_clearance", [c.id, c.note || false, notNeeded]);
        if (ok) {
            this.state.clearing = null;
            this.notif.add(
                notNeeded
                    ? _t("%s has nothing to sign off — noted.", c.desk)
                    : _t("%s signed off.", c.desk),
                { type: "success" });
            await this.refresh();
        } else if (this.state.clearing) {
            this.state.clearing.busy = false;
        }
    }

    // ------------------------------------------------------- the handover
    askKt(row) {
        this.state.kt = {
            caseId: row.id,
            who: row.employee,
            topic: "",
            link: "",
            busy: false,
        };
    }

    onKtTopic(ev) { this.state.kt.topic = ev.target.value; }
    onKtLink(ev) { this.state.kt.link = ev.target.value; }
    cancelKt() { this.state.kt = null; }

    async saveKt() {
        const k = this.state.kt;
        if (!k || k.busy) { return; }
        if (!(k.topic || "").trim()) {
            this.notif.add(_t("Say what is being handed over."),
                           { type: "warning" });
            return;
        }
        k.busy = true;
        const ok = await this.call(
            "add_kt_item", [k.caseId, k.topic, false, k.link || false]);
        if (ok) {
            this.state.kt = null;
            this.notif.add(_t("Added to the handover list."),
                           { type: "success" });
            await this.refresh();
        } else if (this.state.kt) {
            this.state.kt.busy = false;
        }
    }

    async settleKt(item, done) {
        if (await this.call("settle_kt_item", [item.id, done])) {
            await this.refresh();
        }
    }

    async nudgeKt(row) {
        if (await this.call("nudge_kt", [row.id],
                            _t("Reminder sent."))) {
            await this.refresh();
        }
    }

    // ------------------------------------------------------- the farewell
    askFarewell(row) {
        const drawer = this.state.drawer;
        const draft = (drawer && drawer.farewell && drawer.farewell.draft) || "";
        this.state.farewell = {
            taskId: row.farewell_task_id,
            who: row.employee,
            text: draft,
            busy: false,
        };
    }

    onFarewellText(ev) { this.state.farewell.text = ev.target.value; }
    cancelFarewell() { this.state.farewell = null; }

    async saveFarewell() {
        const f = this.state.farewell;
        if (!f || f.busy) { return; }
        f.busy = true;
        const ok = await this.call("set_farewell_note", [f.taskId, f.text]);
        if (ok) {
            this.state.farewell = null;
            this.notif.add(_t("The wording is saved. It goes out on the day."),
                           { type: "success" });
            await this.refresh();
        } else if (this.state.farewell) {
            this.state.farewell.busy = false;
        }
    }

    // ------------------------------------------------------------- the doing
    async runStep(task) {
        if (await this.call("run_step_now", [task.id],
                            _t("Done — and the step is ticked."))) {
            await this.refresh();
        }
    }

    async closeSettlement(row) {
        // The server raises the plain-English refusal naming exactly what is
        // outstanding, so there is no client-side pre-check here on purpose:
        // a second opinion would only ever disagree with the one that counts.
        if (await this.call("close_settlement", [row.ff.id],
                            _t("Settlement closed."))) {
            await this.refresh();
        }
    }

    async sendInvite(row) {
        if (await this.call("send_exit_invite", [row.id],
                            _t("The exit questionnaire has been sent."))) {
            await this.refresh();
        }
    }

    async runAutomation() {
        const res = await this.call("run_automation", []);
        if (res) {
            this.notif.add(
                _t("%(steps)s step(s) ran, %(pings)s handover reminder(s) sent.",
                   { steps: res.auto_steps || 0, pings: res.kt_pings || 0 }),
                { type: "success" });
            await this.refresh();
        }
    }

    // ------------------------------------------------------------ the doors
    async openCase(row) {
        const act = await this.call("open_case_action", [row.id]);
        if (act) { this.action.doAction(act); }
    }

    async openSettlement(row) {
        const act = await this.call("open_settlement_action", [row.employee_id]);
        if (act) { this.action.doAction(act); }
    }

    async openResignation(row) {
        if (!row.resignation_id) { return; }
        const act = await this.call("open_resignation_action",
                                    [row.resignation_id]);
        if (act) { this.action.doAction(act); }
    }

    openClearances() {
        this.action.doAction("pb_offboarding.action_pb_exit_clearance");
    }

    openPolicies() {
        this.action.doAction("pb_offboarding.action_pb_notice_policy");
    }
}

registry.category("actions").add("pb_exits_board", PbExitsBoard);
