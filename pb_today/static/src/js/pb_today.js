/** @odoo-module **/
/**
 * The Today board — mockup B's canvas: tile strip → filtered people list →
 * driver map card, as a standalone hub (the Mission Control shell around it is
 * P3).
 *
 * It replaces two surfaces and copies neither. Live Attendance was the right
 * idea in a 2013 body: four status columns you could look at and nothing you
 * could do. The Workforce Dashboard was Chart.js in a form view. Today keeps
 * the status idea, throws the charts away on purpose (deep analytics belong to
 * Insights / Explorer — Today is triage, not reporting), and makes every tile
 * and every row a door:
 *
 *   tile   → filters the list to that state
 *   avatar → the shared person drawer (<WfPersonWeek/>, the same panel the Time
 *            hub opens — one copy, W6)
 *   late / not-started row → files a correction and lands in the Time hub's
 *            Exceptions lens PRE-FILTERED to that person (§2.4)
 *   map card → the embedded DriverMap; "Open map →" swaps to the full-height
 *            Map view inside this same hub (W17 — one component, two mounts)
 *
 * Department, day and search come from the shared wf_context (W4). Today is the
 * `day` segment's first and only consumer (§2.3); the Time hub stays
 * week-scoped.
 */
import { Component, useState, useEffect, onWillStart, onWillUpdateProps, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfContextBar } from "@pb_wf_kit/js/wf_context_bar";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { WfPersonWeek } from "@pb_wf_kit/js/wf_person_week";
import { WF_ROW_CAP } from "@pb_wf_kit/js/wf_rows";
import { DriverMap } from "@pb_driver_checkin/js/driver_map";

const MODEL = "pb.today";
const HUB_MODEL = "pb.time.hub";
const POLL_MS = 30000;
const VIEW_KEY = "pbtd.view.v1";
const STATES = ["on_shift", "late", "not_started", "checked_out", "on_leave"];

export class PbToday extends Component {
    static template = "pb_today.PbToday";
    static components = { WfContextBar, WfDrawer, WfPersonWeek, DriverMap };
    static props = {
        action: { type: Object, optional: true },
        // W17 (P3a): Mission Control owns the page title and the shared context
        // bar, so `embedded` suppresses those two and NOTHING else — every
        // facade call, every tile and every door stay exactly as they are.
        embedded: { type: Boolean, optional: true },
        // P3a §3.5: inside the shell the Time hand-off is a LENS SWITCH, not a
        // doAction to a separate action. The host passes a stable callback;
        // standalone it is absent and the old doAction path runs unchanged.
        // Called from a CLICK handler only (W21/W21.1).
        onHandOff: { type: Function, optional: true },
        // P3b §3.6 — one palette instruction, consumed by nonce. Always an
        // object, never null: a TYPED optional prop rejects null (W35).
        pbCmd: { type: Object, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false, pbCmd: { name: "", nonce: 0 } };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        this.ctxSvc = useService("wf_context");
        this.wf = useState(this.ctxSvc.state);

        this.state = useState({
            data: null,
            loading: true,
            // which tile is drilled; null = everybody the day is about
            filter: null,
            // "board" | "map" — the map card's "Open map →" toggles this
            view: this._restoreView(),
            person: null,
            personLoading: false,
            // A person already pinned on the shared context (the officer came
            // from the Time hub, or a reload restored one) is CONTEXT, not a
            // request to open a drawer over the board. Today shows no person
            // chip either — a drawer nobody asked for, over a filter nobody can
            // see, is the worst of both.
            drawerHidden: !!this.ctxSvc.state.personId,
        });

        // Stable handler identities: fresh inline arrows make OWL treat a
        // child's props as changed and recreate it, restarting its onWillStart
        // fetch — the refetch loop the Weekly Entry cockpit had to fix once.
        this._h = {
            onFileCorrection: () => this.fileCorrectionForPinned(),
            onOpenProfile: () => this.openProfile(),
        };

        // Board follows the shared context (department / day). onChange rather
        // than a render dependency, because a context change must REFETCH.
        const off = this.ctxSvc.onChange(() => this._load());
        onWillUnmount(off);

        // The drawer is driven by ctx.personId, so every person door lands on
        // one code path. Nothing is fetched while it is closed.
        useEffect(
            (personId, weekStart, hidden) => {
                if (!hidden) { this._loadPerson(personId, weekStart); }
            },
            () => [this.wf.personId, this.wf.weekStart, this.state.drawerHidden],
        );

        this._timer = setInterval(() => this._load(true), POLL_MS);
        onWillUnmount(() => { clearInterval(this._timer); this._timer = null; });

        this._cmdNonce = 0;
        onWillUpdateProps((next) => { this._applyPbCmd(next.pbCmd); });
        onWillStart(async () => {
            await this._load();
            this._applyPbCmd(this.props.pbCmd);
        });
    }

    ic(n, s = 15) { return ic(n, s); }

    // ------------------------------------------------------------- views
    _restoreView() {
        try {
            const v = window.localStorage.getItem(VIEW_KEY);
            if (v === "map" || v === "board") { return v; }
        } catch { /* private mode */ }
        return "board";
    }

    setView(v) {
        if (this.state.view === v) { return; }
        this.state.view = v;
        try { window.localStorage.setItem(VIEW_KEY, v); } catch { /* private mode */ }
    }

    /**
     * The `pb_cmd` channel (P3b §3.6).
     *
     * Mission Control forwards ONE palette instruction as a prop with a NONCE,
     * and this lens tracks the last nonce it ran. That is the whole protocol,
     * and it is shaped that way on purpose: a "consumed" callback would be a
     * CHILD writing HOST state from a mount hook, which is the bug that cost
     * P1a 591 junk records and then bit a second time on a keyed child
     * (W21/W21.1). Nothing here writes anything but this component's own state,
     * and an unknown command is ignored — a lens that does not implement a verb
     * is not an error.
     */
    _applyPbCmd(cmd) {
        if (!cmd || !cmd.nonce || cmd.nonce === this._cmdNonce) { return; }
        this._cmdNonce = cmd.nonce;
        if (cmd.name === "map") { this.setView("map"); }
    }

    // -------------------------------------------------------------- data
    /**
     * @param {boolean} silent  a poll tick: no spinner, no error toast. A 30 s
     *   background refresh that pops a red toast because the laptop's wifi
     *   blinked is worse than a stale board.
     */
    async _load(silent = false) {
        if (!silent) { this.state.loading = true; }
        const call = silent ? this.orm.silent : this.orm;
        try {
            const data = await call.call(MODEL, "get_today_data", [
                this.wf.departmentId || false, this.wf.day,
            ]);
            this.state.data = data;
        } catch (e) {
            if (!silent) {
                this.state.data = null;
                this.notif.add((e && e.data && e.data.message)
                    || _t("Could not load the board."), { type: "danger" });
            }
        } finally {
            if (!silent) { this.state.loading = false; }
        }
    }

    refresh() { this._load(); }

    get tiles() {
        const t = (this.state.data && this.state.data.tiles) || {};
        return [
            { key: "on_shift", label: _t("On shift"), tone: "green",
              n: t.on_shift || 0 },
            { key: "late", label: _t("Late"), tone: "rose", n: t.late || 0 },
            { key: "not_started", label: _t("Not started"), tone: "amber",
              n: t.not_started || 0 },
            { key: "checked_out", label: _t("Checked out"), tone: "cyan",
              n: t.checked_out || 0 },
            { key: "on_leave", label: _t("On leave"), tone: "slate",
              n: t.on_leave || 0 },
        ];
    }

    get total() {
        return ((this.state.data && this.state.data.tiles) || {}).total || 0;
    }

    /**
     * P8 — the Team pulse tile.
     *
     * Deliberately NOT in `tiles` above: those five are states of the day and
     * every one of them is a FILTER on the people list. A pulse average filters
     * nothing and drills into nothing, so putting it in that strip would have
     * made it a door that opens onto an empty room (W5/W29).
     *
     * The anonymity floor is resolved SERVER-side inside `get_pulse_tile`,
     * which returns no figures at all below it — this getter cannot decide to
     * show a number it was never given, which is the point. `shown: false` and
     * an absent key (pb_ess_workforce not installed) are the same answer here.
     */
    get pulse() {
        const p = this.state.data && this.state.data.pulse;
        return p && p.shown ? p : null;
    }

    get pulseFace() {
        const a = this.pulse && this.pulse.avg;
        if (!a) { return ""; }
        if (a >= 4.5) { return "smilePlus"; }
        if (a >= 3.5) { return "smile"; }
        if (a >= 2.5) { return "meh"; }
        return "frown";
    }

    get updatedAt() { return (this.state.data && this.state.data.updated_at) || ""; }

    get truncated() { return (this.state.data && this.state.data.truncated) || 0; }

    get rowCap() { return WF_ROW_CAP; }

    // ------------------------------------------------------------- rows
    /**
     * The visible list: the drilled tile, then the context's free-text search.
     *
     * Search filters ROWS, never tiles. The tiles are the day's truth; a search
     * box that silently changed the counts would make the board unusable as a
     * headcount (and the officer would never know it had).
     */
    get rows() {
        let rows = (this.state.data && this.state.data.rows) || [];
        const f = this.state.filter;
        if (f === "late") {
            rows = rows.filter((r) => r.is_late);
        } else if (f) {
            rows = rows.filter((r) => r.state === f);
        }
        const q = (this.wf.search || "").trim().toLowerCase();
        if (q) {
            rows = rows.filter(
                (r) => (r.name || "").toLowerCase().includes(q)
                    || (r.job || "").toLowerCase().includes(q)
                    || (r.dept || "").toLowerCase().includes(q));
        }
        return rows;
    }

    get listTitle() {
        const f = this.state.filter;
        if (!f) { return _t("Everyone today"); }
        const tile = this.tiles.find((t) => t.key === f);
        return (tile && tile.label) || _t("Everyone today");
    }

    setFilter(key) {
        if (!STATES.includes(key)) { return; }
        // clicking the drilled tile again clears the drill
        this.state.filter = this.state.filter === key ? null : key;
    }

    clearFilter() { this.state.filter = null; }

    stateLabel(row) {
        return {
            on_shift: _t("On shift"),
            checked_out: _t("Checked out"),
            not_started: _t("Not started"),
            on_leave: row.leave_type || _t("On leave"),
        }[row.state] || row.state;
    }

    stateTone(row) {
        return { on_shift: "green", checked_out: "cyan",
                 not_started: "amber", on_leave: "slate" }[row.state] || "slate";
    }

    /** "Shift 08:00–16:00 · in 08:19" / "· not in" — the row's one-line story. */
    rowStory(row) {
        const bits = [];
        if (row.shift_label) { bits.push(row.shift_label); }
        if (row.check_in && row.check_out) {
            bits.push(_t("in %(a)s · out %(b)s", { a: row.check_in, b: row.check_out }));
        } else if (row.check_in) {
            bits.push(_t("in %s", row.check_in));
        } else if (row.state === "on_leave") {
            bits.push(row.leave_type || _t("on leave"));
        } else {
            bits.push(_t("not in"));
        }
        return bits.join(" · ");
    }

    // ------------------------------------------------------- person door
    openPerson(employeeId) {
        if (!employeeId) { return; }
        this.state.drawerHidden = false;
        this.ctxSvc.set({ personId: employeeId });
    }

    closePerson() {
        this.state.drawerHidden = false;
        this.ctxSvc.set({ personId: false });
    }

    get drawerOpen() { return !!this.wf.personId && !this.state.drawerHidden; }

    async _loadPerson(personId, weekStart) {
        if (!personId) {
            this.state.person = null;
            return;
        }
        this.state.personLoading = true;
        try {
            // The Time hub's facade, unchanged: one person-week contract for
            // every Workforce surface (pb_time_hub/models/time_hub.py).
            const data = await this.orm.call(HUB_MODEL, "get_person_week",
                                             [personId, weekStart]);
            // A late reply must not paint over a person the officer has since
            // changed, or a drawer they have since closed.
            if (this.wf.personId !== personId) { return; }
            this.state.person = data && data.employee ? data : null;
            if (!this.state.person) {
                this.notif.add(_t("That employee is not available in this company."),
                    { type: "warning" });
                this.ctxSvc.set({ personId: false });
            }
        } catch (e) {
            this.state.person = null;
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not load that person."), { type: "danger" });
        } finally {
            this.state.personLoading = false;
        }
    }

    get drawerTitle() {
        const p = this.state.person;
        return (p && p.employee.name) || _t("Loading…");
    }

    get drawerSubtitle() {
        const p = this.state.person;
        if (!p) { return ""; }
        return [p.employee.job, p.employee.dept, p.employee.badge]
            .filter((x) => x).join(" · ");
    }

    /** Native-form escape as a DIALOG with a return path (W5). */
    openProfile() {
        const p = this.state.person;
        if (!p) { return; }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: p.employee.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    // ------------------------------------------------ correction hand-off
    fileCorrectionForPinned() {
        const p = this.state.person;
        if (!p) { return; }
        this.fileCorrection({ id: p.employee.id });
    }

    /**
     * The "File correction" door (§2.4): pin the person on the shared context
     * and hand over to the Time hub's Exceptions lens, which lands FILTERED to
     * them because it reads that same context (W4).
     *
     * **This board never writes.** The correction record is minted one click
     * later, by the Exceptions lens's own composer, on a row the officer has
     * actually looked at. That is deliberate, and it is not squeamishness: a
     * triage board is polled every 30 s and clicked reflexively, and P1a proved
     * how fast a write reachable from a hot surface turns into junk rows (591
     * of them in 90 seconds). A door that only navigates cannot do that, and it
     * makes `pb.today` a strictly read-only facade — nothing on Today can dirty
     * a live payroll database.
     */
    fileCorrection(row) {
        if (!row || !row.id) { return; }
        const day = (this.state.data && this.state.data.day) || this.wf.day;
        // Pin BEFORE navigating: the lens reads the context on ITS mount, so
        // the pin has to be there first. Passing `day` drags the context week
        // to that day's week (wf_context.set's rule) — exactly the week the
        // Time hub should open on.
        this.ctxSvc.set({ personId: row.id, day });
        // The W26 arrival payload, written ONCE and used by both routes so the
        // shell and the standalone board cannot drift: `pb_lens` names the lens,
        // `pb_focus: "queue"` says the pinned person is a FILTER over there, not
        // a drawer to pop on top of the queue we just sent the officer to read.
        const arrival = { pb_lens: "exceptions", pb_focus: "queue" };
        if (this.props.onHandOff) {
            // Embedded (P3a §3.5): Time is a sibling lens, so leaving the board
            // must not leave the workspace. This runs in a click handler, so the
            // host state write is safe (W21.1 — mount hooks READ, handlers WRITE).
            this.props.onHandOff("time", arrival);
            return;
        }
        this.actionService.doAction("pb_time_hub.action_pb_time_hub", {
            additionalContext: arrival,
        });
    }

    // ------------------------------------------------------ empty states
    get emptyState() {
        const d = this.state.data;
        if (this.state.loading) { return null; }
        if (!d) {
            return { icon: "alert", title: _t("The board could not load"),
                     sub: _t("Refresh to try again. If it keeps failing you may not have attendance-officer access.") };
        }
        if (!d.tiles.total) {
            return d.is_today
                ? { icon: "sunrise", title: _t("Nothing scheduled yet"),
                    sub: _t("No shifts, punches or leave on this day. Publish a roster in Schedule and this board fills up.") }
                : { icon: "calendar", title: _t("Nothing on this day"),
                    sub: _t("No shifts, punches or leave were recorded. Try another day, or clear the department filter.") };
        }
        if (!this.rows.length) {
            return { icon: "checkCircle", title: _t("Nobody in this state"),
                     sub: _t("Pick another tile, or clear the filter to see everyone.") };
        }
        return null;
    }
}

registry.category("actions").add("pb_today", PbToday);
