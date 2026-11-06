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
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

/** Cards per page; "Show N more" loads the next one. */
const PAGE = 60;

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
            total: 0,               // everybody leaving
            glanceFilters: {},      // what each figure means as a filter
            depts: [],

            // the page the filter panel produced (FILTER wave 2)
            rows: [],
            rowsTotal: 0,
            listLoaded: false,
            loadingMore: false,
            stepCounts: {},

            // the open leaver
            drawer: null,
            drawerBusy: false,

            // dialogs — one at a time, each one plain state
            clearing: null,
            farewell: null,
            kt: null,
        });

        // The shared filter panel (pb_filter_kit): it owns the filters, the
        // counts and the views; this board loads one page of cards for
        // kit.query, counted and filtered on the server (no 300-row cap).
        this.kit = useFilterKit({
            model: "pb.exits",
            noun: _t("people leaving"),
            onChange: () => this.loadPage(),
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------------ read
    /** The numbers line and the flags — counted over everybody leaving,
     *  whatever is filtered. */
    async load() {
        try {
            const d = await this.orm.call("pb.exits", "get_board_head", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                kpis: d.kpis || {},
                total: d.total || 0,
                glanceFilters: d.glance_filters || {},
                depts: d.depts || [],
                loaded: true,
            });
        } catch (e) {
            // Reported, never swallowed into a decoration (W40).
            console.warn("pb_offboarding: could not read the board", e);
            this.state.loaded = true;
            this.state.allowed = false;
        }
    }

    /** One page of cards (and, on the first, the step counts) for the
     *  panel's current filters. A reply for an older filter state is dropped. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.exits", "get_board_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.rowsTotal = d.total;
            if (!more) { this.state.stepCounts = d.steps || {}; }
            this.state.listLoaded = true;
        } catch (e) {
            console.warn("pb_offboarding: could not load the cards", e);
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add(_t("The leavers could not be loaded. Try again in a moment."),
                               { type: "warning" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }

    get hasMore() { return this.state.rows.length < this.state.rowsTotal; }

    get nextPage() { return Math.min(PAGE, this.state.rowsTotal - this.state.rows.length); }

    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    async refresh() {
        await Promise.all([this.load(), this.kit.refresh()]);
        if (this.state.drawer) {
            await this.openExit(this.state.drawer.leaver.id);
        }
    }

    /** Back to everybody leaving (the first view). */
    showAll() { this.kit.toggleFilters({}); }

    /** Why the list is empty, in one translatable sentence (R34). */
    get emptyText() {
        if (this.kit.chips.length) {
            return this.state.total === 1
                ? _t("There is 1 person leaving, but they do not fit every filter you have set. Remove a filter above, or start again from everybody.")
                : _t("There are %s people leaving, but none of them fits every filter you have set. Remove a filter above, or start again from everybody.",
                     this.fmtInt(this.state.total));
        }
        if (this.kit.search) {
            return _t("Nobody matches “%s”. Check the spelling, or search by job or team.", this.kit.search);
        }
        return _t("Nothing could be listed just now. Show everybody to start again.");
    }

    /** "Something is holding this exit up" — the card's amber edge. */
    isBlocked(row) {
        if (row.ff.closed) { return false; }
        return !!(row.assets
            || row.clearances.some((c) => c.state === "pending")
            || row.overdue
            || row.kt_open);
    }

    // ----------------------------------------------------- the quiet board
    //
    // One slim line of numbers instead of a row of tiles, and the four steps
    // a leaver moves through. A leaver is at EXACTLY ONE step, so the step
    // counts add up to what the panel lists. A figure that filters ticks
    // exactly its filters in the panel (and lights the view tab with the
    // same filters); pressing it again shows everyone.
    glanceRun(key) {
        const f = this.state.glanceFilters[key];
        return f ? () => this.kit.toggleFilters(f) : null;
    }

    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(this.state.glanceFilters || {})) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "leaving", n: k.leaving || 0, label: _t("Leaving this month"), tone: "",
              run: this.glanceRun("leaving") },
            { key: "gone", n: k.gone || 0, label: _t("Last day has passed"), tone: "",
              run: this.glanceRun("gone") },
            { key: "blocked", n: k.blocked || 0, label: _t("Settlements held up"), tone: tone(k.blocked, "rose"),
              run: this.glanceRun("blocked") },
            { key: "clearances", n: k.clearances || 0, label: _t("Clearances still open"), tone: tone(k.clearances, "amber"),
              run: this.glanceRun("clearances") },
            { key: "assets", n: k.assets || 0, label: _t("Items not back yet"), tone: tone(k.assets, "amber"),
              run: this.glanceRun("assets") },
            // LEARN REFRESH step 6 — worked out, waiting for a person to check
            // it and send it for approval
            { key: "to_check", n: k.to_check || 0, label: _t("Settlements to check"), tone: tone(k.to_check, "amber"),
              run: this.glanceRun("to_check") },
        ];
    }

    /** Notice → signing off → ready to settle → settled. */
    stepOf(r) {
        if (r.ff.closed) { return "settled"; }
        if (r.ff.id && r.ff.ready) { return "ready"; }
        const gone = !!r.lwd && r.days !== null && r.days < 0;
        return gone ? "signoff" : "notice";
    }

    get stepDefs() {
        return [
            { key: "notice", title: _t("Working their notice"), sub: _t("Last day still ahead") },
            { key: "signoff", title: _t("Signing off"), sub: _t("Gone, sign-offs or items still open") },
            { key: "ready", title: _t("Ready to settle"), sub: _t("The last payment can go out") },
            { key: "settled", title: _t("Settled"), sub: _t("Settlement closed") },
        ];
    }

    /** The four steps, counted on the server for the panel's filters
     *  (everything except the step itself), so they follow the filters. */
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const c = counts[st.key] || {};
            const at = { length: c.n || 0 };
            const waiting = c.waiting || 0;
            return {
                ...st,
                n: String(i + 1).padStart(2, "0"),
                count: at.length,
                countLabel: at.length === 1 ? _t("1 person") : _t("%s people", at.length),
                flag: !waiting ? "" : waiting === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", waiting),
                flagTone: "",
                on: this.stepIsOn(st.key),
            };
        });
    }

    stepIsOn(key) {
        const v = this.kit.values("step");
        return v.length === 1 && String(v[0]) === key;
    }

    /** A step narrows the panel's list to that step, keeping every other
     *  filter; pressing the lit step again lifts it. */
    pickStep(key) {
        if (this.stepIsOn(key)) { this.kit.clear("step"); } else { this.kit.only("step", key); }
    }

    stepMeta(r) {
        const defs = this.stepDefs;
        const index = defs.findIndex((st) => st.key === this.stepOf(r));
        return {
            label: _t("Step %s of %s", index + 1, defs.length),
            title: defs[index].title,
            marks: defs.map((st, j) => (j < index ? "done" : j === index ? "here" : "")),
        };
    }

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
        if (row.ff.issue && ["draft", "returned"].includes(row.ff.state)) {
            return { cls: "err", text: _t("Settlement could not be worked out") };
        }
        if (row.ff.to_check) {
            return { cls: "warn", text: _t("Settlement ready to check") };
        }
        if (row.ff.state === "pending") {
            return { cls: "info", text: _t("Settlement waiting for approval") };
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

    async sendSettlement(row) {
        if (await this.call("send_settlement", [row.ff.id],
                            _t("Settlement sent for approval."))) {
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
            const n = (c, one, many) => c + " " + (c === 1 ? one : many);
            this.notif.add(
                _t("%(steps)s ran, %(pings)s sent, %(made)s filled in.",
                   { steps: n(res.auto_steps || 0, _t("step"), _t("steps")),
                     pings: n(res.kt_pings || 0, _t("reminder"), _t("reminders")),
                     made: n(res.clearances_made || 0, _t("clearance"),
                             _t("clearances")) }),
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
