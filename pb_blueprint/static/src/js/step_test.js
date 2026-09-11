/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted,
         onWillUpdateProps, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import { STEP_META } from "./blueprint_steps";
import { EvidenceChip } from "./evidence_chip";
import {
    fmtValue, verdictPill, runPlan, runHeadline, coverageLine,
    coverageIsComplete, beyondRecipes, evidenceChip, peopleCount, sourcedLine,
} from "./outputs_text";

/**
 * Step 5 — Test: try the days that aren't ordinary.
 *
 * One button runs everything, and then every scenario says in words whether it
 * passed and, when it did not, which component disagreed and by how much. The
 * part that makes this evidence rather than decoration is the confirmation
 * gate: a scenario whose expected numbers nobody has agreed to is PENDING, and
 * pending is not passed — because the numbers the engine produces today are
 * only a hypothesis about what a payroll should pay.
 *
 * The moment a formula, a fixed value or a tax band changes afterwards, the
 * evidence says so in amber on this step, on the components list and on the tax
 * tab. A green tick against rules that have since moved is the one thing a
 * screen like this must never show.
 */
export class StepTest extends Component {
    static template = "pb_blueprint.StepTest";
    static components = { EvidenceChip };
    static props = {
        configId: { type: [Number, Boolean] },
        revision: { type: Number, optional: true },
        currency: { type: String, optional: true },
        reloadKey: { type: Number, optional: true },
        // The pay panel's own "Run the checks" bumps this rather than running a
        // second copy of the call: the step owns the checks, the revision and
        // every refusal, so it is the one that runs them.
        runSignal: { type: Number, optional: true },
        onRevision: { type: Function },
        onBusy: { type: Function },
        onTests: { type: Function },       // hands the payload to the scoreboard
        onChanged: { type: Function },
        onGrid: { type: Function },
        onInspect: { type: Function },     // walk back to a component's detail
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.modalRef = useRef("modal");

        this.state = useState({
            loading: true,
            error: "",
            data: null,
            running: false,
            busy: "",              // the id a call is running for, or a word
            open: 0,               // the scenario whose detail sheet is open
            detail: null,
            confirmFor: 0,         // the scenario whose confirm sheet is open
            picks: null,           // the boundary modal's payload
            picked: [],            // the keys ticked in it
            picksOpen: false,
            // {sample_id: true} for the verdicts the last run CHANGED.
            moved: {},
            // The scenario whose name is being edited, and what has been typed.
            renaming: 0,
            renameValue: "",
            showOther: false,      // the boundary modal's second group
            realOpen: false,
            real: null,            // {runs, run_id, people, reason}
            realRows: null,        // one person's numbers
            realBusy: false,
            realLabel: "",
            realPayslip: 0,
        });

        // Nothing is handed to the parent until this step is ON SCREEN.
        //
        // `onTests` sets state on the shell, and state on the shell re-renders
        // this component. Called from `onWillStart` that is a loop with no end
        // and no symptom: Owl cancels the render, rebuilds the child, which
        // asks again — the step simply never appears, and there is no error in
        // the console to explain why (BP41). After mount the same call costs
        // exactly one extra render and settles.
        this._live = false;

        onWillStart(async () => {
            await this.load();
            this.state.loading = false;
        });

        onMounted(() => {
            this._live = true;
            if (this.state.data) { this.props.onTests(this.state.data); }
        });

        onWillUpdateProps(async (next) => {
            if (next.reloadKey !== this.props.reloadKey) { await this.load(); }
            if ((next.runSignal || 0) !== (this.props.runSignal || 0)) {
                await this.run();
            }
        });

        useEffect((el) => { if (el) { el.focus(); } }, () => [this.modalRef.el]);
    }

    ic(name, size = 16) { return ic(name, size); }

    get meta() { return STEP_META.test; }

    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(reason || _t("The server could not be reached."),
                           { type: "danger" });
            return { ok: false, reason };
        }
    }

    async load() {
        const res = await this.rpc("bp_tests", [this.props.configId]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("The checks could not be read. Reload the page to try again.");
            return;
        }
        this.state.error = "";
        this._apply(res);
    }

    _apply(res) {
        this.state.data = res;
        if (res.revision !== undefined) { this.props.onRevision(res.revision); }
        // The pay panel becomes the scoreboard on this step, and it reads the
        // same answer this list does rather than asking again — but only once
        // there is a screen to read it on (see `_live` above).
        if (this._live) { this.props.onTests(res); }
    }

    // ==================================================================
    // Reading
    // ==================================================================
    get data() { return this.state.data || {}; }
    get samples() { return this.data.samples || []; }
    get tally() { return this.data.tally || {}; }
    get evidence() { return this.data.evidence || {}; }
    get editable() { return this.data.editable !== false; }
    get canWrite() { return this.data.can_write !== false; }

    get headline() { return runHeadline(this.samples); }

    get plan() { return runPlan(this.samples); }

    get chip() { return evidenceChip(this.evidence); }

    get coverage() { return this.data.coverage || {}; }

    get coverageLine() { return coverageLine(this.coverage); }

    get coverageComplete() { return coverageIsComplete(this.coverage); }

    get untested() { return (this.coverage.untested || []); }

    get recipes() { return beyondRecipes(); }

    pill(verdict) { return verdictPill(verdict); }

    value(v) { return fmtValue(v); }


    peopleCount(n) { return peopleCount(n); }

    sourcedLine(n) { return sourcedLine(n); }

    get pending() {
        return this.samples.filter((s) => s.verdict === "pending"
                                       || s.verdict === "not_run");
    }

    get canConfirmAll() {
        return this.canWrite && this.pending.length > 1;
    }

    /** Nothing to check at all — the one state this step must not be blank in. */
    get isEmpty() { return !this.samples.length; }

    get emptyLine() {
        return _t("There is nothing to check yet. Add the boundary cases this configuration branches on, or a sample employee of your own, and the checks have something to run against.");
    }

    /**
     * Remember which scenarios came back with a different verdict.
     *
     * Compared against what was on SCREEN a moment ago, so the movement says
     * "this one changed" and not "this one exists". Cleared after a second, and
     * never applied at all for somebody who has asked their system to stop
     * animating.
     */
    _markMoved(res) {
        const before = {};
        for (const row of (this.state.data && this.state.data.samples) || []) {
            before[row.id] = row.verdict;
        }
        const moved = {};
        for (const row of (res && res.samples) || []) {
            if (before[row.id] && before[row.id] !== row.verdict) {
                moved[row.id] = true;
            }
        }
        if (!Object.keys(moved).length || this.stillness) { return; }
        this.state.moved = moved;
        if (this._movedTimer) { clearTimeout(this._movedTimer); }
        this._movedTimer = setTimeout(() => { this.state.moved = {}; }, 1200);
    }

    /** True when this person has asked their system not to animate. */
    get stillness() {
        try {
            return !!(window.matchMedia
                && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
        } catch (e) {
            return false;
        }
    }

    // ==================================================================
    // Naming a scenario
    // ==================================================================
    /**
     * "Edge BASIC=46799999 (−1)" is the engine's name for a boundary case, and
     * it is the right name for the machine that made it. A person reading a
     * list of eleven checks needs "Just under the insurance ceiling" (B5's own
     * "with one more hour"). A rename is not in the evidence key, so nothing
     * goes stale for it.
     */
    startRename(row) {
        if (!this.canWrite) { return; }
        this.state.renaming = row.id;
        this.state.renameValue = row.name || "";
    }

    cancelRename() {
        this.state.renaming = 0;
        this.state.renameValue = "";
    }

    onRenameKey(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();          // Enter on the step means "continue"
            this.saveRename();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();          // Escape here closes the input, not the step
            this.cancelRename();
        }
    }

    async saveRename() {
        const id = this.state.renaming;
        const name = (this.state.renameValue || "").trim();
        if (!id || !name) { this.cancelRename(); return; }
        this.state.busy = "rename";
        const res = await this.rpc("bp_rename_sample",
                                   [this.props.configId, id, name,
                                    this.props.revision || 0]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("That scenario could not be renamed."), { type: "warning" });
            return;
        }
        this.cancelRename();
        this._apply(res);
    }

    // ==================================================================
    // Running
    // ==================================================================
    async run() {
        if (this.state.running) { return; }
        this.state.running = true;
        this.props.onBusy(true);
        const res = await this.rpc("bp_run_checks",
                                   [this.props.configId, this.props.revision || 0]);
        this.state.running = false;
        this.props.onBusy(false);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("The checks could not be run."), { type: "warning", sticky: true });
            return;
        }
        // Which verdicts this run actually CHANGED. The pills for those and
        // no others get one short movement — the single moment on this step
        // where something is worth pointing at (B5's own "with one more hour").
        this._markMoved(res);
        this._apply(res);
        const tally = res.tally || {};
        if (tally.attention) {
            this.notif.add(
                tally.attention === 1
                    ? _t("1 check needs attention.")
                    : _t("%s checks need attention.", tally.attention),
                { type: "warning" });
            return;
        }
        if (tally.pending) {
            this.notif.add(
                _t("Everything ran. Confirm the numbers you expect and they count as evidence."),
                { type: "info" });
            return;
        }
        this.notif.add(
            tally.passed === 1 ? _t("1 check passed.")
                               : _t("%s checks passed.", tally.passed),
            { type: "success" });
    }

    // ==================================================================
    // Confirming
    // ==================================================================
    async openConfirm(sample) {
        this.state.confirmFor = sample.id;
        this.state.busy = "detail";
        const res = await this.rpc("bp_test_detail",
                                   [this.props.configId, sample.id]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.state.confirmFor = 0;
            this.notif.add((res && res.reason)
                || _t("That scenario could not be opened."), { type: "warning" });
            return;
        }
        this.state.detail = res;
    }

    closeConfirm() {
        this.state.confirmFor = 0;
        this.state.detail = null;
    }

    async confirmOne() {
        const id = this.state.confirmFor;
        this.closeConfirm();
        await this._confirm([id]);
    }

    async confirmAll() {
        await this._confirm("all");
    }

    async _confirm(which) {
        this.state.busy = "confirm";
        const res = await this.rpc("bp_confirm_expected", [
            this.props.configId, which, this.props.revision || 0]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("Those numbers could not be confirmed."),
                { type: "warning", sticky: true });
            return;
        }
        this._apply(res);
        const n = res.confirmed || 0;
        this.notif.add(
            n === 1 ? _t("Confirmed. That scenario now counts as evidence.")
                    : _t("%s scenarios confirmed. They now count as evidence.", n),
            { type: "success" });
    }

    // ==================================================================
    // Opening one scenario
    // ==================================================================
    async openDetail(sample) {
        this.state.open = sample.id;
        this.state.busy = "detail";
        const res = await this.rpc("bp_test_detail",
                                   [this.props.configId, sample.id]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.state.open = 0;
            this.notif.add((res && res.reason)
                || _t("That scenario could not be opened."), { type: "warning" });
            return;
        }
        this.state.detail = res;
    }

    closeDetail() {
        this.state.open = 0;
        this.state.detail = null;
    }

    get detailRows() {
        const rows = ((this.state.detail || {}).rows) || [];
        return rows.filter((r) => r.expected !== null || r.input !== null
                                  || r.column_type === "formula");
    }

    get detailChanged() {
        return ((this.state.detail || {}).rows || []).filter(
            (r) => r.expected !== null && r.passed === false);
    }

    /**
     * Offer the way out only where there is something to get out of.
     *
     * A scenario that passes has nothing to re-take, and offering it there
     * would put "agree to whatever it says" next to a green tick — which is
     * how somebody presses it without reading it.
     */
    get canRetake() {
        const d = this.state.detail || {};
        return !!d.can_write && this.detailChanged.length > 0;
    }

    /**
     * "Take today's numbers as the ones to expect."
     *
     * Deliberately one scenario at a time and deliberately wordy: this is how
     * a wrong calculation gets blessed as a right one, so the person has to
     * mean it.
     */
    async retakeExpected() {
        const id = this.state.open;
        if (!id || this.state.busy) return;
        this.state.busy = "retake";
        const res = await this.rpc("bp_retake_expected",
                                   [this.props.configId, id,
                                    this.props.revision || 0]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("Those numbers could not be taken."),
                { type: "warning", sticky: true });
            return;
        }
        this.closeDetail();
        this._apply(res);
        this.notif.add(
            _t("“%s” now expects the numbers it works out today.",
               res.retaken || ""),
            { type: "success" });
    }

    // ==================================================================
    // Boundary cases
    // ==================================================================
    async openPicks() {
        this.state.busy = "picks";
        const res = await this.rpc("bp_boundary_picks", [this.props.configId]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("The boundary cases could not be worked out."),
                { type: "warning" });
            return;
        }
        this.state.picks = res;
        this.state.picked = (res.picks || [])
            .filter((p) => p.recommended && !p.exists).map((p) => p.key);
        this.state.showOther = false;
        this.state.picksOpen = true;
    }

    closePicks() { this.state.picksOpen = false; }

    get recommendedPicks() {
        return ((this.state.picks || {}).picks || []).filter((p) => p.recommended);
    }

    get otherPicks() {
        return ((this.state.picks || {}).picks || []).filter((p) => !p.recommended);
    }

    isPicked(pick) { return this.state.picked.includes(pick.key); }

    togglePick(pick) {
        if (pick.exists) { return; }
        this.state.picked = this.isPicked(pick)
            ? this.state.picked.filter((k) => k !== pick.key)
            : [...this.state.picked, pick.key];
    }

    get pickedLine() {
        const n = this.state.picked.length;
        if (!n) { return _t("Nothing chosen yet."); }
        return n === 1
            ? _t("1 edge chosen — that adds 3 scenarios.")
            : _t("%(n)s edges chosen — that adds %(rows)s scenarios.",
                 { n, rows: n * 3 });
    }

    async addBoundaries() {
        if (!this.state.picked.length) { return; }
        this.state.busy = "picks";
        const res = await this.rpc("bp_add_boundaries", [
            this.props.configId, this.state.picked, this.props.revision || 0]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("Those checks could not be added."),
                { type: "warning", sticky: true });
            return;
        }
        this.state.picksOpen = false;
        this._apply(res);
        this.props.onChanged(res);
        const created = res.created || 0;
        const skipped = res.skipped || 0;
        if (!created && skipped) {
            this.notif.add(
                _t("Those edges were already covered, so nothing was added."),
                { type: "info" });
            return;
        }
        this.notif.add(
            skipped
                ? _t("%(added)s scenarios added · %(skipped)s were already there.",
                     { added: created, skipped })
                : _t("%s scenarios added. Confirm their numbers to make them count.",
                     created),
            { type: "success" });
    }

    // ==================================================================
    // A real person
    // ==================================================================
    async openReal() {
        this.state.realOpen = true;
        this.state.realBusy = true;
        this.state.realRows = null;
        const res = await this.rpc("bp_real_people", [this.props.configId]);
        this.state.realBusy = false;
        if (!res || !res.ok) {
            this.state.realOpen = false;
            this.notif.add((res && res.reason)
                || _t("The pay runs could not be read."), { type: "warning" });
            return;
        }
        this.state.real = res;
    }

    closeReal() {
        this.state.realOpen = false;
        this.state.realRows = null;
        this.state.realPayslip = 0;
    }

    async onPickRun(ev) {
        const runId = Number(ev.target.value);
        if (!runId) { return; }
        this.state.realBusy = true;
        const res = await this.rpc("bp_real_run_people",
                                   [this.props.configId, runId]);
        this.state.realBusy = false;
        if (res && res.ok) {
            this.state.real = { ...this.state.real, run_id: runId,
                                people: res.people };
            this.state.realRows = null;
        }
    }

    async onPickPerson(person) {
        this.state.realBusy = true;
        this.state.realRows = null;
        const res = await this.rpc("bp_real_preview",
                                   [this.props.configId, person.payslip_id, true]);
        this.state.realBusy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("That person's numbers could not be worked out."),
                { type: "warning" });
            return;
        }
        this.state.realRows = res.rows || [];
        this.state.realLabel = res.label || "";
        this.state.realPayslip = res.payslip_id || 0;
    }

    get realShown() {
        return (this.state.realRows || []).filter(
            (r) => r.column_type !== "constant");
    }

    async keepReal() {
        if (!this.state.realPayslip) { return; }
        this.state.realBusy = true;
        const res = await this.rpc("bp_real_keep", [
            this.props.configId, this.state.realPayslip, this.props.revision || 0]);
        this.state.realBusy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason)
                || _t("That person could not be kept as a scenario."),
                { type: "warning", sticky: true });
            return;
        }
        this.closeReal();
        this._apply(res);
        this.props.onChanged(res);
        this.notif.add(
            _t("Kept as a scenario, with the name removed. It is under “Yours” below."),
            { type: "success" });
    }

    // ==================================================================
    // Keys
    // ==================================================================
    onKeydown(ev) {
        if (ev.key === "Enter") { ev.stopPropagation(); }
        if (ev.key !== "Escape") { return; }
        ev.stopPropagation();
        if (this.state.picksOpen) { this.closePicks(); return; }
        if (this.state.realOpen) { this.closeReal(); return; }
        if (this.state.confirmFor) { this.closeConfirm(); return; }
        if (this.state.open) { this.closeDetail(); }
    }

    /**
     * "1 is untested: NIGHTPREM" — and the code is a door.
     *
     * A coverage line that names a component nobody has checked, and then makes
     * you go and find it, is a line that reports a problem and hands you none of
     * the way to fix it. This walks back to the outputs table with that
     * component already open.
     */
    onInspect(row) {
        if (row && row.rule_id) { this.props.onInspect(row.rule_id); }
    }
}
