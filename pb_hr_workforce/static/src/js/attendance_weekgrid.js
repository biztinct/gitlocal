/** @odoo-module **/
/**
 * Weekly Entry cockpit — WOW overtime + regular-hours grid for the HR/manager
 * persona. Composes the generic <WeekGrid/> with a live OT-ceiling rail and a
 * submit/approve tray. pbim-tokenized (.pbim.wfg). No employee self-entry.
 *
 * ONE component, TWO mount points (W17): the client action `pb_attendance_weekgrid`
 * keeps working exactly as before, and pb_time_hub mounts the same class with
 * `embedded="true"` as its Week Grid lens. `embedded` suppresses ONLY the chrome
 * the hub already owns — the title and the <WfContextBar/> — never any logic or
 * facade call, so there is no lens fork to keep in sync (W6).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { WeekGrid } from "@biz_week_grid/js/week_grid";
import { WfContextBar } from "@pb_wf_kit/js/wf_context_bar";
// isoLocal is still needed here for the month/year OT-ceiling keys. The rest of
// the local-date helpers (parseLocal / monday / week labels) moved to the kit,
// next to the week nav that uses them. NEVER round-trip a wall-clock day through
// toISOString() — it converts to UTC and slips the date in any non-UTC timezone.
import { isoLocal } from "@pb_wf_kit/js/wf_context_service";

const MODEL = "hr.attendance.weekentry";
const OT_TYPES = ["weekday", "weekend", "holiday", "night"];

export class AttendanceWeekGrid extends Component {
    static template = "pb_hr_workforce.AttendanceWeekGrid";
    static components = { WeekGrid, WfContextBar };
    static props = {
        action: { type: Object, optional: true },
        // mounted as a hub lens rather than as a standalone client action
        embedded: { type: Boolean, optional: true },
        // host-supplied doors (W5): the person drawer, and "this employee is
        // over their overtime ceiling — take me to the exceptions queue".
        onPerson: { type: Function, optional: true },
        onEscalate: { type: Function, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false };

    setup() {
        this.actionService = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");

        // Department + week are SHARED state now (W4): they live in wf_context,
        // are rendered by <WfContextBar/>, and survive a reload. useState() on
        // the service's reactive object subscribes this component, so a change
        // made in the bar re-renders the cockpit and rolls paramsKey, which is
        // what makes the grid refetch.
        this.ctx = useService("wf_context");
        this.wf = useState(this.ctx.state);

        this.state = useState({
            railOpen: true,
            focusEmp: null,
            reloadNonce: 0,
            // fetched context used by the rail + tray (reactive → drives live bars)
            ceilings: {},
            liveDelta: {},   // empId -> {mtd, ytd} unsaved OT deltas
            summary: { draft_count: 0, draft_hours: 0, draft_ids: [], pending_count: 0, pending_ids: [] },
            truncated: 0,
            saving: false,
        });

        this._rowsById = {};   // empId -> {label, sublabel}
        this._tokenMap = {};   // "empId|dayISO" -> attendance write_date token
        this._lastDeltaStr = "{}";
        this._bootstrap = null; // payload pre-fetched by the cockpit for the child's first load
        this._monthKey = isoLocal(new Date()).slice(0, 7);
        this._yearKey = String(new Date().getFullYear());

        // adapter bridges the generic grid to the weekentry RPCs. The FIRST call
        // (the child's onWillStart) is served the payload the cockpit already
        // fetched — so no parent-state mutation happens during child mount (which
        // would remount the child in a fetch loop). Later reloads hit the RPC.
        this.adapter = {
            fetch: () => {
                if (this._bootstrap) { const d = this._bootstrap; this._bootstrap = null; return Promise.resolve(d); }
                return this._doFetch();
            },
            save: (payload) => this._save(payload),
            // No client-side validate hook: precise per-cell cap warnings would
            // need the grid's per-cell edit ledger duplicated here, and the two
            // authoritative cap surfaces already cover it — the live rail bars
            // (aggregate, reactive) and the save-time month+year over-cap
            // confirm. The server re-validates every write regardless (rail 1).
        };
        // STABLE prop references — passing fresh inline arrows / {} each render
        // makes OWL treat the child's props as changed every time and recreate
        // it, which restarts its onWillStart fetch (an infinite loop). Bind once.
        this._gridParams = {};
        this._h = {
            onData: this.onGridData.bind(this),
            onDirty: this.onDirty.bind(this),
            onFocus: this.onFocusRow.bind(this),
            onSaved: this.onGridSaved.bind(this),
            // Only hand the grid a row door when the host actually has one —
            // standalone there is nothing to open, and a button that does
            // nothing is worse than no button.
            onRowOpen: this.props.onPerson ? (id) => this.props.onPerson(id) : undefined,
            // The cell editor's live budget bar + advisory warnings. PURE and
            // SYNCHRONOUS by contract — it reads the ceilings this cockpit
            // already fetched and the dirty ledger the grid already told us
            // about, so opening an editor costs no RPC (§3.2).
            editorInfo: this.editorInfo.bind(this),
        };
        this._dirtyList = [];

        onWillStart(async () => {
            // The department list is the context bar's job now; the cockpit only
            // fetches its own bootstrap (own lifecycle → safe to set state).
            this._bootstrap = await this._doFetch();
        });
    }

    // ------------------------------------------------------------------ rpc
    async _rpc(method, args = []) {
        return rpc(`/web/dataset/call_kw/${MODEL}/${method}`, {
            model: MODEL, method, args, kwargs: {},
        });
    }

    get paramsKey() {
        return `${this.wf.weekStart}|${this.wf.departmentId || ""}|${this.state.reloadNonce}`;
    }

    // translatable empty-state text handed to the generic <WeekGrid/> (a plain
    // string prop, so it must come through _t here rather than the template).
    get emptyText() {
        return _t("No employees with entries this week — adjust the department or week.");
    }

    /** Does this cockpit have tray content of its own? The grid's tray shows
     *  itself whenever there are staged edits; this keeps the ONE bar on
     *  screen when the only thing to say is "12 awaiting approval". */
    get hasQueue() {
        return (this.state.summary.draft_count > 0
                || this.state.summary.pending_count > 0);
    }

    async _doFetch() {
        const data = await this._rpc("get_week_entries", [
            this.wf.weekStart, this.wf.departmentId || false, false,
        ]);
        // capture context for the rail / tray / token map
        this.state.ceilings = data.ceilings || {};
        this.state.summary = data.summary || this.state.summary;
        this.state.truncated = data.truncated || 0;
        this.state.liveDelta = {};
        this._lastDeltaStr = "{}";
        this._rowsById = {};
        this._tokenMap = {};
        this._monthKey = isoLocal(new Date()).slice(0, 7);  // ceiling reflects current month
        for (const row of data.rows || []) {
            this._rowsById[row.id] = { label: row.label, sublabel: row.sublabel };
            for (const [iso, cell] of Object.entries(row.cells || {})) {
                const reg = (cell.measures || {}).reg;
                if (reg && reg.token !== undefined) {
                    this._tokenMap[`${row.id}|${iso}`] = reg.token || "";
                }
            }
        }
        if (this.state.truncated) {
            this.notif.add(
                _t("Showing the first 200 employees. Narrow by department to see the rest."),
                { type: "warning" });
        }
        return data;
    }

    async _save(payload) {
        // enrich REG cells with their fetched concurrency token (rail 7)
        const cells = (payload.cells || []).map((c) => {
            if (c.measure === "reg") {
                return { ...c, token: this._tokenMap[`${c.rowId}|${c.dayISO}`] ?? "" };
            }
            return c;
        });
        // ceiling over-cap confirm before committing OT that breaches a cap (rail 5)
        const breach = this._overCapAfterSave();
        if (breach) {
            const msg = breach.kind === "year"
                ? _t("%(name)s exceeds the annual overtime cap of %(cap)s h. Submit anyway?",
                     { name: breach.name, cap: breach.cap })
                : _t("%(name)s exceeds the monthly overtime cap of %(cap)s h. Submit anyway?",
                     { name: breach.name, cap: breach.cap });
            const ok = await this._confirm(msg);
            if (!ok) { return { results: [] }; }  // user cancelled → nothing saved
        }
        this.state.saving = true;
        let res;
        try {
            res = await this._rpc("save_week_entries", [{ cells }]);
        } finally {
            this.state.saving = false;
        }
        const results = (res && res.results) || [];
        // translate the server's terse reason CODES into human cell messages
        // (the grid surfaces r.error verbatim in the cell tooltip/ring) — a
        // trip day refusal must read as a sentence, not the bare token "trip".
        const REASONS = {
            trip: _t("On an authorized business trip — attendance is automatic here."),
            bounds: _t("Hours must be between 0 and 24."),
            stale: _t("This cell changed since you loaded it — refresh and retry."),
            multi: _t("Multiple attendance records — edit on the attendance form."),
            notgrid: _t("Not a grid entry — edit on the attendance form."),
            notapplicable: _t("This overtime type doesn't apply on this day."),
            locked: _t("Already submitted or approved — locked."),
            noemp: _t("Employee not found."),
            badmeasure: _t("Unknown measure."),
            exc: _t("Could not be saved."),
        };
        const fails = results.filter((r) => !r.ok);
        for (const r of fails) {
            if (r.error && REASONS[r.error]) { r.error = REASONS[r.error]; }
        }
        if (fails.length) {
            // if the only failures are trip-day refusals, say so plainly
            const allTrip = fails.every((r) => r.error === REASONS.trip);
            this.notif.add(
                allTrip
                    ? REASONS.trip
                    : fails.length + " " + _t("cell(s) could not be saved — see the highlighted cells."),
                { type: allTrip ? "warning" : "danger" });
        } else if (results.length) {
            this.notif.add(_t("Saved."), { type: "success" });
        }
        return res;
    }

    // -------------------------------------------------------- live ceilings
    onDirty(list) {
        // recompute per-employee unsaved OT deltas → drives the live rail bars.
        // Only commit to reactive state when it actually changed (the empty-list
        // call fired during the child's mount must NOT setState — that would
        // remount the grid, C-gotcha).
        //
        // The raw list is kept on a PLAIN field (not reactive state, for the
        // same reason): the cell editor's ceiling bar has to subtract the cell
        // it is itself editing from the employee's staged total, or it would
        // count those hours twice the moment a second edit lands on the same
        // day.
        this._dirtyList = list;
        const delta = {};
        for (const d of list) {
            if (!OT_TYPES.includes(d.measureKey)) { continue; }
            const diff = Number(d.value) - Number(d.prevValue || 0);
            if (!diff) { continue; }
            const inMonth = (d.dayISO || "").slice(0, 7) === this._monthKey;
            const inYear = (d.dayISO || "").slice(0, 4) === this._yearKey;
            delta[d.rowId] = delta[d.rowId] || { mtd: 0, ytd: 0 };
            if (inMonth) { delta[d.rowId].mtd += diff; }
            if (inYear) { delta[d.rowId].ytd += diff; }
        }
        const s = JSON.stringify(delta);
        if (s !== this._lastDeltaStr) {
            this._lastDeltaStr = s;
            this.state.liveDelta = delta;
        }
    }

    onFocusRow(empId) { this.state.focusEmp = empId; }

    onGridData(data) {
        // ceilings/summary already captured in _fetch; nothing extra needed
    }

    async onGridSaved() {
        // grid reloads itself on full success; refresh rail/tray context too
    }

    liveCeiling(empId) {
        const base = this.state.ceilings[empId] || { mtd: 0, ytd: 0, cap_month: 40, cap_year: 200 };
        const dl = this.state.liveDelta[empId] || { mtd: 0, ytd: 0 };
        return {
            mtd: Math.max(0, base.mtd + dl.mtd),
            ytd: Math.max(0, base.ytd + dl.ytd),
            cap_month: base.cap_month,
            cap_year: base.cap_year,
        };
    }

    // -------------------------------------------------------- cell editor
    /**
     * What the cell editor shows beside its steppers: this employee's live
     * MONTHLY overtime budget and the advisory consequences of the values
     * currently in the panel.
     *
     * Pure, synchronous, no RPC — the ceilings arrived with `get_week_entries`
     * and the staged edits arrived through `onDirty`. Deliberately ADVISORY:
     * an over-ceiling entry is something an officer may legitimately record,
     * and the server's Phase-K `_split` already decides what happens to it, so
     * the panel says what that will be instead of refusing the entry. The
     * blocking question is still asked once, at save time, by the existing
     * over-cap confirm — one dialog per commit, not one per keystroke.
     */
    editorInfo({ rowId, dayISO, values, prev }) {
        const base = this.state.ceilings[rowId]
            || { mtd: 0, ytd: 0, cap_month: 40, cap_year: 200 };
        const inMonth = (dayISO || "").slice(0, 7) === this._monthKey;

        // staged OT hours on this employee's OTHER days this month
        let others = 0;
        for (const d of this._dirtyList) {
            if (String(d.rowId) !== String(rowId)) { continue; }
            if (!OT_TYPES.includes(d.measureKey)) { continue; }
            if (d.dayISO === dayISO) { continue; }   // this day is `values`
            if ((d.dayISO || "").slice(0, 7) !== this._monthKey) { continue; }
            others += Number(d.value || 0) - Number(d.prevValue || 0);
        }
        // and the cell the panel is holding right now
        let here = 0;
        for (const t of OT_TYPES) {
            if (!(t in values)) { continue; }
            here += Number(values[t] || 0) - Number((prev || {})[t] || 0);
        }

        const cap = base.cap_month || 0;
        const used = Math.max(0, base.mtd + others + (inMonth ? here : 0));
        const warnings = [];
        if (cap && used > cap) {
            const over = Math.round((used - cap) * 10) / 10;
            warnings.push({
                tone: "warn",
                text: _t(
                    "%(h)s h past the monthly ceiling of %(cap)s h. The excess is "
                    + "recorded as bonus hours, not overtime pay — you can still "
                    + "enter it.", { h: over, cap: cap }),
            });
        }
        const capY = base.cap_year || 0;
        const usedY = Math.max(0, base.ytd + others + here);
        if (capY && usedY > capY) {
            warnings.push({
                tone: "bad",
                text: _t("Also past this employee's annual ceiling of %s h.", capY),
            });
        }
        return {
            ceiling: { label: _t("Overtime this month"), used, cap },
            warnings,
        };
    }

    _overCapAfterSave() {
        // returns {name, kind, cap} if any employee's live total breaches its
        // MONTHLY or ANNUAL cap (the annual cap must gate too — a burst of OT
        // can clear the month budget yet blow the yearly statutory ceiling).
        for (const [empId, dl] of Object.entries(this.state.liveDelta)) {
            if (!dl.mtd && !dl.ytd) { continue; }
            const c = this.liveCeiling(empId);
            const name = (this._rowsById[empId] || {}).label || _t("employee");
            if (dl.mtd && c.cap_month && c.mtd > c.cap_month) {
                return { name, kind: "month", cap: c.cap_month };
            }
            if (dl.ytd && c.cap_year && c.ytd > c.cap_year) {
                return { name, kind: "year", cap: c.cap_year };
            }
        }
        return null;
    }

    // ------------------------------------------------------------ rail data
    get focusCeiling() {
        if (!this.state.focusEmp) { return null; }
        const c = this.liveCeiling(this.state.focusEmp);
        const meta = this._rowsById[this.state.focusEmp] || {};
        return { ...c, name: meta.label || "", sub: meta.sublabel || "" };
    }
    get leaderboard() {
        const rows = [];
        for (const [empId, base] of Object.entries(this.state.ceilings)) {
            const c = this.liveCeiling(empId);
            const pct = c.cap_month ? c.mtd / c.cap_month : 0;
            rows.push({
                id: empId,
                name: (this._rowsById[empId] || {}).label || "",
                mtd: c.mtd, cap: c.cap_month, pct,
            });
        }
        rows.sort((a, b) => b.pct - a.pct);
        return rows.slice(0, 6).filter((r) => r.mtd > 0);
    }
    /** Is this employee at or over their monthly overtime ceiling? */
    isOverCap(v, cap) { return !!(cap && v >= cap); }

    /** The over-cap door: hand the employee to the host's exceptions queue. */
    escalate(empId) {
        if (this.props.onEscalate) { this.props.onEscalate(empId); }
    }

    barPct(v, cap) { return cap ? Math.min(100, Math.round((v / cap) * 100)) : 0; }
    barTone(v, cap) {
        const p = cap ? v / cap : 0;
        if (p >= 0.9) { return "danger"; }
        if (p >= 0.75) { return "warn"; }
        return "ok";
    }
    fmtH(v) { return (Math.round((v || 0) * 10) / 10); }

    // -------------------------------------------------------- toolbar / tray
    // Department select, week nav and the week label are all <WfContextBar/>
    // now — the cockpit keeps only the controls that are genuinely its own.
    toggleRail() { this.state.railOpen = !this.state.railOpen; }

    async submitAll() {
        try {
            const r = await this._rpc("submit_week", [
                this.wf.weekStart, this.wf.departmentId || false, false]);
            this.notif.add((r.submitted || 0) + " " + _t("overtime request(s) submitted."),
                { type: "success" });
            await this._reloadContext();
        } catch (e) {
            this.notif.add(e.data ? e.data.message : (e.message || _t("Submit failed.")),
                { type: "danger" });
        }
    }
    async approvePending() {
        const ids = this.state.summary.pending_ids || [];
        if (!ids.length) { return; }
        try {
            const r = await this._rpc("approve_requests", [ids]);
            this.notif.add((r.approved || 0) + " " + _t("overtime request(s) approved."),
                { type: "success" });
            await this._reloadContext();
        } catch (e) {
            this.notif.add(e.data ? e.data.message : (e.message || _t("Approval failed.")),
                { type: "danger" });
        }
    }
    _reloadContext() {
        // bump the nonce → paramsKey changes → <WeekGrid> refetches via the
        // adapter (which refreshes our ceilings/summary in _fetch).
        this.state.reloadNonce += 1;
    }

    _confirm(message) {
        return new Promise((resolve) => {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Overtime ceiling exceeded"),
                body: message,
                confirmLabel: _t("Submit anyway"),
                cancelLabel: _t("Cancel"),
                confirm: () => resolve(true),
                cancel: () => resolve(false),
            });
        });
    }
}

registry.category("actions").add("pb_attendance_weekgrid", AttendanceWeekGrid);
