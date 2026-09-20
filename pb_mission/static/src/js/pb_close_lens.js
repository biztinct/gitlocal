/** @odoo-module **/
/**
 * <PbCloseLens/> — mockup C, living inside Mission Control (P4 WP-4).
 *
 * The eighth lens, and the only one that is not an existing cockpit mounted
 * with `embedded="true"` (W17): there was no Close surface to embed. It is
 * built here rather than as a standalone cockpit because the whole point of the
 * ritual is that it happens WITHOUT leaving the room — the officer fixes a flag
 * on the Time lens, comes back, waives another, and locks the week, all against
 * one department and one week that never reset (W4).
 *
 * WHAT IT OWNS, AND WHAT IT DOES NOT
 * ----------------------------------
 *   * it owns the board, the chips, the review dialog and the CTA;
 *   * it owns NO context: department, week and search come from `wf_context`,
 *     and the only door out is `props.onHandOff` into the Time lens's own W26
 *     arrival protocol — the shell already knows how to do that (`pb_cmd` is
 *     the shell -> lens direction; this is the lens -> shell one, and it is a
 *     CLICK handler, never a mount hook, W21.1);
 *   * it owns no drawer: `ownsPersonDrawer` is not set for this lens, so the
 *     shell's shared <WfPersonWeek/> serves it.
 *
 * MOUNT HOOKS READ, CLICK HANDLERS WRITE (W21/W21.1)
 * ---------------------------------------------------
 * This is the rule with teeth here, because unlike every other lens this one
 * can LOCK A WEEK. `onWillStart`, the `wf_context` subscription and every
 * re-fetch call `get_close_data`, which has no write path in it at all. The
 * three mutations — `review_flag`, `lock_days`, `unlock_days` — appear only
 * inside `t-on-click` handlers, and `pb_mission/tests/test_static.py` asserts
 * that none of them is reachable from `setup()`.
 *
 * NO INVENTED COLOUR, NO HARDCODED TOLERANCE
 * -------------------------------------------
 * Every tone is a class name resolved to a `--pbim-*` token in the stylesheet
 * (W1), and the stat strip's "within N-min tolerance" reads `data.tolerance`
 * off the payload — a literal 10 in the template would keep saying 10 after an
 * admin changed the rule.
 */
import {
    Component, useState, onWillStart, onWillUpdateProps, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.close";
/** The widest scheduled-vs-actual bar, in px — geometry, not chrome. */
const BAR_MAX = 108;

export class PbCloseLens extends Component {
    static template = "pb_mission.PbCloseLens";
    static props = {
        // W17's flag, kept for symmetry with the other seven lenses even though
        // this one has no standalone mount: a future rail item would need it.
        embedded: { type: Boolean, optional: true },
        // lens -> shell hand-off (the "Fix" door). A CLICK calls it, never a
        // lifecycle hook — a child writing host state during its mount
        // invalidates the host's render fiber and loops forever (W21).
        onHandOff: { type: Function, optional: true },
        // the person DOOR (W5). It goes through the shell rather than through
        // `wf_context` directly, because the shell also has to un-hide its
        // shared drawer: a pre-existing pin is context, an explicit click is a
        // request (W26's corollary).
        onOpenPerson: { type: Function, optional: true },
        // the shell's `pb_cmd` channel. A TYPED optional prop still rejects
        // `null`, so the default is a non-null literal (W35/W44).
        pbCmd: { type: Object, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: true, pbCmd: { name: "", nonce: 0 } };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ctxSvc = useService("wf_context");
        // useState on the service's reactive is what subscribes this lens to a
        // week change made anywhere else in the workspace (W4/W16).
        this.wf = useState(this.ctxSvc.state);

        // Memo for the bar scale — see `_barPeak`. Plain instance fields, not
        // state: they are derived from state and nothing renders off them.
        this._peakFor = null;
        this._peak = 1;

        this.state = useState({
            loading: true,
            failed: "",
            data: null,
            busy: false,
            // the "Approve as-is" dialog: the row it is about, plus its note
            reviewFor: null,
            reviewNote: "",
            // the "Review all N…" dialog (P7). Holds the KIND summary row it
            // is about, so the copy can name the kind and the count.
            bulkFor: null,
            bulkNote: "",
            // what a bulk waive actually did — kept on screen until dismissed,
            // because "37 reviewed, 2 skipped" is the whole point of the
            // action and a toast that fades takes the second number with it.
            bulkResult: null,
            // the "Reopen…" dialog: the reason is REQUIRED and RECORDED (W42)
            reopenOpen: false,
            reopenReason: "",
            // TABLE-only view state. Deliberately not in `wf_context`: the
            // week, the department and the search are the WORKSPACE's context
            // and every lens shares them (W4), but "show me the missing punches
            // on page 2" is one officer's position inside one table and would
            // be meaningless to the Time lens.
            filterKind: false,
            filterReviewed: false,
            page: 1,
        });

        // A context change is a RE-READ, never a write. The subscription is
        // registered in setup and torn down with the component.
        //
        // It also resets the PAGE. A new week or department is a different set
        // of rows, and "page 4" carried across into a two-page result is how a
        // table greets an officer with an empty screen and no explanation. The
        // kind/reviewed chips deliberately survive: those express what the
        // officer is working on, and re-picking "missing punches" for every
        // department in turn is exactly the tedium the chips exist to remove.
        const off = this.ctxSvc.onChange(() => {
            this.state.page = 1;
            this.load();
        });
        onWillUnmount(off);

        // W44: consumed by NONCE, so the shell never has to be told, and the
        // lens may re-read the prop as often as OWL restarts its mount.
        this._cmdNonce = this.props.pbCmd ? this.props.pbCmd.nonce : 0;
        onWillUpdateProps((next) => { this._applyPbCmd(next.pbCmd); });
        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 14) { return ic(n, s); }

    // ------------------------------------------------------------------ data
    /**
     * The ONE read. `get_close_data` is officer-gated server-side and has no
     * write path, which is what makes it safe to call from a mount hook and on
     * every context change.
     *
     * W40: the catch narrows nothing. It records the server's own words on the
     * surface and warns on the console, rather than quietly retiring a control.
     */
    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(MODEL, "get_close_data", [], {
                department_id: this.wf.departmentId || false,
                week_start: this.wf.weekStart,
                search: this.wf.search || "",
                kind: this.state.filterKind || false,
                reviewed: this.state.filterReviewed || false,
                page: this.state.page,
            });
            this.state.data = data;
            this.state.failed = "";
        } catch (e) {
            this.state.data = null;
            this.state.failed = (e && e.data && e.data.message)
                || _t("The Close board could not be loaded.");
            console.warn("pb_mission: the Close board could not load", e);
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * A lens ignoring an unknown command is CORRECT behaviour (W44). The one
     * verb this lens implements is `lock_week`, and it is registered in the
     * palette only because the affordance below really exists.
     */
    _applyPbCmd(cmd) {
        if (!cmd || !cmd.name || cmd.nonce === this._cmdNonce) { return; }
        this._cmdNonce = cmd.nonce;
        if (cmd.name === "lock_week") { this.lockWeek(); }
    }

    // ----------------------------------------------------------- accessors
    get d() { return this.state.data || {}; }
    get days() { return this.d.days || []; }
    get stats() { return this.d.stats || {}; }
    get rows() { return this.d.flagged || []; }
    get handoff() { return this.d.handoff || {}; }
    get checklist() { return this.d.checklist || []; }

    get weekTitle() {
        return _t("Close week %s", this.d.week_no || "");
    }

    /** "…within N-min tolerance" — N is read from the payload, never a
     *  literal, so the strip cannot keep quoting a threshold an admin has
     *  since changed. */
    get toleranceLabel() {
        const t = this.d.tolerance || {};
        return _t("Auto-approved · within %s-min tolerance", t.minutes ?? "—");
    }

    get flaggedLabel() {
        const n = this.stats.flagged || 0;
        return n === 1 ? _t("1 flagged remains") : _t("%s flagged remain", n);
    }

    get kinds() { return this.d.kinds || []; }

    /** "Showing 26–50 of 137" — the honest sentence W45 is about. Every number
     *  in it comes off the payload; none is `rows.length`. */
    get rangeLabel() {
        const total = this.d.filtered_total || 0;
        const shown = this.d.flagged_shown || 0;
        if (!total) { return ""; }
        const from = ((this.d.page || 1) - 1) * (this.d.page_size || 25) + 1;
        return _t("Showing %(from)s–%(to)s of %(total)s", {
            from, to: from + shown - 1, total });
    }

    get pages() { return this.d.pages || 1; }
    get page() { return this.d.page || 1; }
    get canPrev() { return this.page > 1; }
    get canNext() { return this.page < this.pages; }

    /** Is the table showing something narrower than the week? The chips row
     *  renders a "clear" affordance only when there is something to clear. */
    get isFiltered() {
        return !!(this.state.filterKind || this.state.filterReviewed);
    }

    /** The kind currently filtered to, as its summary row — the bulk button
     *  lives beside the chips and needs the count. */
    get activeKind() {
        return this.kinds.find((k) => k.kind === this.state.filterKind) || null;
    }

    /**
     * Scheduled / actual bar widths in px. Geometry, not chrome (W3's
     * distinction — these are data marks, so they may carry a scale).
     *
     * The peak is memoised against the payload that produced it: the template
     * calls this TWICE PER ROW, and recomputing a max over 200 rows each time
     * is 80 000 comparisons per render for a number that cannot change between
     * two of them.
     */
    get _barPeak() {
        if (this._peakFor !== this.state.data) {
            this._peakFor = this.state.data;
            this._peak = Math.max(
                1, ...this.rows.map((r) => Math.max(r.sched || 0, r.actual || 0)));
        }
        return this._peak;
    }

    barWidth(hours) {
        return Math.max(3, Math.round((BAR_MAX * (hours || 0)) / this._barPeak));
    }

    deltaTone(row) {
        const v = row.delta || 0;
        if (v < -0.05) { return "rose"; }
        if (v > 0.05) { return "amber"; }
        return "slate";
    }

    deltaLabel(row) {
        const v = row.delta || 0;
        const s = Math.abs(v).toFixed(1);
        if (v > 0.05) { return `+${s}`; }
        if (v < -0.05) { return `−${s}`; }
        return "0.0";
    }

    hours(v) {
        return Number(v || 0).toLocaleString(undefined, {
            minimumFractionDigits: 1, maximumFractionDigits: 1 });
    }

    money(v) {
        const n = Number(v || 0);
        return `${this.handoff.currency || ""}${n.toLocaleString(undefined, {
            maximumFractionDigits: 0 })}`;
    }

    rowKey(row) { return `${row.employee_id}:${row.date}:${row.kind}`; }

    // ================================================================ writes
    // Everything below is reachable ONLY from a t-on-click (W21.1).

    /**
     * "Fix" — hand the officer to the Time lens's Exceptions queue with this
     * person pinned. W26's protocol, `pb_focus: "queue"` so the pin acts as a
     * FILTER and the shell does not pop a drawer over the very queue it just
     * sent them to read.
     */
    fix(row) {
        this.ctxSvc.set({ personId: row.employee_id });
        if (this.props.onHandOff) {
            this.props.onHandOff("time", {
                pb_lens: "exceptions", pb_focus: "queue" });
        }
    }

    // -------------------------------------------------- table view controls
    // These are WRITES to local view state and reads from the server; they are
    // click handlers like everything else below (W21.1).
    setKind(kind) {
        this.state.filterKind = this.state.filterKind === kind ? false : kind;
        this.state.page = 1;
        this.load();
    }

    setReviewed(mode) {
        this.state.filterReviewed =
            this.state.filterReviewed === mode ? false : mode;
        this.state.page = 1;
        this.load();
    }

    clearFilters() {
        this.state.filterKind = false;
        this.state.filterReviewed = false;
        this.state.page = 1;
        this.load();
    }

    goPage(delta) {
        const next = this.page + delta;
        if (next < 1 || next > this.pages) { return; }
        this.state.page = next;
        this.load();
    }

    openReview(row) {
        this.state.reviewFor = row;
        this.state.reviewNote = "";
    }

    // ------------------------------------------------------- the bulk waive
    /** Offered per KIND and only for the OPEN ones — waiving a row that is
     *  already waived is not a decision, and counting it would inflate the
     *  number in the button. */
    openBulk(k) {
        if (!this.d.can_review || !k || !k.open) { return; }
        this.state.bulkFor = k;
        this.state.bulkNote = "";
        this.state.bulkResult = null;
    }

    cancelBulk() {
        this.state.bulkFor = null;
        this.state.bulkNote = "";
    }

    onBulkNote(ev) { this.state.bulkNote = ev.target.value; }

    dismissBulkResult() { this.state.bulkResult = null; }

    /**
     * One note, one kind, every open row of it on this board.
     *
     * The result is put ON THE SURFACE rather than into a toast: the server
     * reports what it could not waive (the no-self-review rule is enforced per
     * row and survives a batch), and a notification that fades after four
     * seconds is not where you put the sentence "2 of these were yours".
     */
    async confirmBulk() {
        const k = this.state.bulkFor;
        if (!k || this.state.busy) { return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "review_kind", [], {
                kind: k.kind,
                note: this.state.bulkNote.trim(),
                department_id: this.wf.departmentId || false,
                week_start: this.wf.weekStart,
                search: this.wf.search || "",
            });
            this.state.bulkFor = null;
            this.state.bulkNote = "";
            this.state.bulkResult = res;
            const n = (res && res.reviewed) || 0;
            this.notif.add(
                n === 1 ? _t("1 flag reviewed") : _t("%s flags reviewed", n),
                { type: (res && res.skipped && res.skipped.length)
                    ? "warning" : "success" });
            await this.load();
        } catch (e) {
            this._error(e);
        } finally {
            this.state.busy = false;
        }
    }

    cancelReview() {
        this.state.reviewFor = null;
        this.state.reviewNote = "";
    }

    onReviewNote(ev) { this.state.reviewNote = ev.target.value; }

    /** The note is OPTIONAL here, and the placeholder says so — the model
     *  stores it either way, so there is nothing to lie about (W42). */
    async confirmReview() {
        const row = this.state.reviewFor;
        if (!row || this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "review_flag", [
                row.employee_id, row.date, row.kind,
                this.state.reviewNote.trim(),
            ]);
            this.state.reviewFor = null;
            this.state.reviewNote = "";
            this.notif.add(_t("Reviewed · %s", row.name), { type: "success" });
            await this.load();
        } catch (e) {
            this._error(e);
        } finally {
            this.state.busy = false;
        }
    }

    /** One day chip clicked. Locking is idempotent; reopening needs a reason,
     *  so a locked chip opens the reopen dialog instead of toggling silently. */
    async toggleDay(day) {
        if (!this.d.can_manage_locks || this.state.busy) { return; }
        if (day.locked) {
            this.state.reopenOpen = { days: [day.iso], label: day.sublabel };
            this.state.reopenReason = "";
            return;
        }
        await this._lock([day.iso]);
    }

    /** The CTA: lock every day of the week that is not locked yet. */
    async lockWeek() {
        if (!this.d.can_lock || !this.d.can_manage_locks || this.state.busy) {
            return;
        }
        const todo = this.days
            .filter((x) => !x.locked && !x.is_future).map((x) => x.iso);
        if (!todo.length) { return; }
        await this._lock(todo, _t("Week closed and handed to payroll"));
    }

    async _lock(days, reason) {
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "lock_days",
                                            [days, reason || false]);
            const n = ((res && res.locked) || []).length;
            this.notif.add(
                n === 1 ? _t("1 day locked") : _t("%s days locked", n),
                { type: "success" });
            await this.load();
        } catch (e) {
            this._error(e);
        } finally {
            this.state.busy = false;
        }
    }

    openReopen() {
        if (!this.d.can_manage_locks) { return; }
        this.state.reopenOpen = {
            days: this.days.filter((x) => x.locked).map((x) => x.iso),
            label: _t("the whole week"),
        };
        this.state.reopenReason = "";
    }

    cancelReopen() {
        this.state.reopenOpen = false;
        this.state.reopenReason = "";
    }

    onReopenReason(ev) { this.state.reopenReason = ev.target.value; }

    /** The reason is REQUIRED because it is RECORDED — the button is DISABLED
     *  without it rather than validating on submit, so nobody composes a
     *  reopen that is then rejected (W42's first corollary). */
    get canConfirmReopen() {
        return !!this.state.reopenReason.trim();
    }

    async confirmReopen() {
        if (!this.canConfirmReopen || this.state.busy) { return; }
        const target = this.state.reopenOpen;
        if (!target || !target.days.length) { return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "unlock_days", [
                target.days, this.state.reopenReason.trim()]);
            const n = ((res && res.unlocked) || []).length;
            this.state.reopenOpen = false;
            this.state.reopenReason = "";
            this.notif.add(
                n === 1 ? _t("1 day reopened") : _t("%s days reopened", n),
                { type: "warning" });
            await this.load();
        } catch (e) {
            this._error(e);
        } finally {
            this.state.busy = false;
        }
    }

    /** A person is a door (W5) — the shell's shared drawer opens for it. */
    openPerson(row) {
        if (this.props.onOpenPerson) {
            this.props.onOpenPerson(row.employee_id);
            return;
        }
        this.ctxSvc.set({ personId: row.employee_id });
    }

    _error(e) {
        this.notif.add((e && e.data && e.data.message) || (e && e.message)
            || _t("Something went wrong."), { type: "danger" });
    }
}
