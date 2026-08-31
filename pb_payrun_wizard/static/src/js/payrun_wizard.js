/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { IC as KIT_IC } from "@pb_import_kit/js/import_icons";

// The shared Lucide registry first, this wizard's own five last, so every glyph
// the standalone screen already rendered is byte-identical and the pay-data step
// gets `upload`/`file`/`checkCircle` without a second icon file (C11: Lucide, never emoji).
const IC = {
    ...KIT_IC,
    check:'<path d="M20 6 9 17l-5-5"/>',
    calendar:'<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    zap:'<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    alert:'<path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    arrow:'<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
};

// NETROLE P3: the rail is now built from KEYS, not from a fixed array of three
// labels. "Pay data" appears only when a scheme actually binds components to
// spreadsheet columns, and on every database where none does, `stepKeys` is the
// original three and every step number means exactly what it always meant.
const STEP_LABELS = {
    period: "Select period",
    data: "Pay data",
    compute: "Compute",
    review: "Review exceptions",
};
const STEPS_PLAIN = ["period", "compute", "review"];
const STEPS_SHEET = ["period", "data", "compute", "review"];

// ---------------------------------------------------------------- RECORDS R1
// "Update Payobook" vs "This run only". The two modes and the three things that
// follow from a mode are PURE functions of it, exported so they can be asserted
// headlessly (hoot) without mounting the wizard — and so the screen, the button
// and the server call can never disagree about what was chosen.
export const MODE_UPDATE = "update";
export const MODE_ONCE = "once";
export const SHEET_MODES = [MODE_UPDATE, MODE_ONCE];

/** The pay-data step's slice of state, so "the default is update" is one fact. */
export function freshSheetMode() { return MODE_UPDATE; }

/** Radio-group keyboard: arrows/Home/End move, anything else leaves it alone. */
export function nextSheetMode(mode, key) {
    const i = Math.max(0, SHEET_MODES.indexOf(mode));
    switch (key) {
        case "ArrowRight": case "ArrowDown":
            return SHEET_MODES[(i + 1) % SHEET_MODES.length];
        case "ArrowLeft": case "ArrowUp":
            return SHEET_MODES[(i - 1 + SHEET_MODES.length) % SHEET_MODES.length];
        case "Home": return SHEET_MODES[0];
        case "End": return SHEET_MODES[SHEET_MODES.length - 1];
        default: return mode;
    }
}

/** The primary button says which run you are about to do — never just "Continue". */
export function continueLabel(mode) {
    return mode === MODE_ONCE ? "Continue — this run only" : "Continue with this file";
}

/** True when the chosen mode must leave every record untouched. */
export function isOneTime(mode) { return mode === MODE_ONCE; }

/**
 * The positional arguments `attach_spreadsheet` is called with. The 7th is the
 * one-time flag; building it here is what the hoot test asserts.
 */
export function attachArgs(runId, configId, fileB64, fileName, dateStart, dateEnd, mode) {
    return [runId, configId, fileB64, fileName, dateStart, dateEnd, isOneTime(mode)];
}

// ---------------------------------------------------------------- RECORDS R4
// D4 — "not in Payobook yet" is ONE fact about the file, not N exceptions.
//
// A one-time file feeds this run and saves nothing, so a row for somebody the
// system has never heard of cannot be paid and cannot be created: it is listed
// and left. Thirty of those rows read as thirty separate problems, which is
// what the flat list made them. They are one problem — "these people are not on
// the payroll yet" — with one next step, and the next step is NOT the Records
// Desk (there is nothing to edit for a person who does not exist). It is the
// Import door, which is what adds people, and it appears only where that door
// actually exists on the database.

/**
 * Split the run's exceptions into the unmatched block and everything else.
 *
 * The two arrive overlapping — `attach_spreadsheet` returns the unmatched rows
 * both inside `errors` (so the flat list has always shown them) and separately
 * (so they can be counted) — and a row must appear in exactly one place here,
 * or the same person is a problem twice.
 */
export function splitExceptions(exceptions, unmatched) {
    const missing = unmatched || [];
    const claimed = new Set(missing.map((u) => [u.emp, u.why].join("|")));
    const rest = (exceptions || []).filter(
        (e) => !claimed.has([e.emp, e.why].join("|")));
    return { missing, rest };
}

/** The heading over the block — a sentence, with the count inside it. */
export function notInPayobookHeading(count) {
    return count === 1
        ? "1 person in the file is not in Payobook yet — they were listed, not paid"
        : `${count} people in the file are not in Payobook yet — they were listed, not paid`;
}

/**
 * The door that adds people, or "" when this database has no such door.
 *
 * Probed through the ACTIONS REGISTRY rather than by trying the action and
 * catching: an offer that fails when it is taken is worse than an offer that
 * was never made, and `pb_import_wizard` is not a dependency of this module.
 */
export function importDoor(actions) {
    try {
        return actions && actions.contains("pb_import_wizard")
            ? "pb_import_wizard.action_pb_import_wizard" : "";
    } catch {
        return "";
    }
}

/** The names, one per line — what "Copy names" puts on the clipboard. */
export function exceptionNames(missing) {
    return (missing || []).map((u) => u.emp).filter(Boolean).join("\n");
}

export class PayrunWizard extends Component {
    static template = "pb_payrun_wizard.PayrunWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        this.state = useState({
            step: 1, loading: false, busyMsg: "",
            defaults: null, form: { name: "", date_start: "", date_end: "", struct_id: null, division: null },
            summary: null,
            progress: null,   // { done, total } during chunked compute → determinate bar
            // NETROLE P3 — the month's spreadsheet.
            // VALUEKIND P4 — who this run covers. `statuses` is null until the
            // defaults arrive, then it is the set of employment statuses ticked.
            who: {
                statuses: null,     // Set-like object {status: true}
                search: "",
                picked: [],         // explicit shortlist, empty = "everyone above"
                preview: null,      // { total, employees, … }
                loading: false,
                open: false,        // the "just a few people" panel
            },
            sheet: {
                gate: null,        // spreadsheet_gate(): null / {wanted:false} / {wanted:true, …}
                file_b64: "", file_name: "",
                preflight: null,   // coverage of the chosen file
                checking: false,   // reading headings
                dragging: false,
                error: "",         // the server's own refusal, shown on the step
                skipped: false,    // the user looked at the list and went on without a file
                // RECORDS R1 — 'update' (save the values to the records) or
                // 'once' (feed this run and change nothing). Chosen in front of
                // the coverage list, never assumed.
                mode: freshSheetMode(),
            },
        });
        onWillStart(async () => {
            // The gate is a read of the schemes, not of the period, so it rides
            // alongside the defaults rather than costing the user a round trip.
            const [d, gate] = await Promise.all([
                this.orm.call("pb.payrun.wizard", "get_defaults", []),
                this.orm.silent
                    .call("pb.payrun.wizard", "spreadsheet_gate", [{}])
                    .catch(() => ({ wanted: false })),
            ]);
            this.state.defaults = d;
            this.state.sheet.gate = gate || { wanted: false };
            this.state.form.name = d.name;
            this.state.form.date_start = d.date_start;
            this.state.form.date_end = d.date_end;
            this.state.form.division = d.division || null;
            // Demo batch name carries the selected configuration so runs for
            // different divisions are distinguishable (e.g. "…June 2026 — Retail").
            if (d.is_demo) this.state.form.name = this._demoName();
            // Tick the statuses the source says are still employed. A default,
            // shown on screen and changeable — never a filter applied quietly.
            const opts = d.statuses || [];
            if (opts.length) {
                const ticks = {};
                for (const o of opts) {
                    ticks[o.value] = !!o.default;
                }
                this.state.who.statuses = ticks;
                this.refreshWho();
            }
        });
    }

    ic(n, s = 16) { return markup(`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${IC[n] || IC.check}</svg>`); }
    vnd(n) { n = n || 0; if (n >= 1e9) return "₫" + (n / 1e9).toFixed(1) + "B"; if (n >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M"; if (n >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K"; return "₫" + Math.round(n); }
    get wantsSheet() { const g = this.state.sheet.gate; return !!(g && g.wanted); }
    // SC-4 — the scheme's source lanes, from the gate payload. Everything
    // defaults ON so an old server changes nothing about this screen.
    get lanes() {
        const g = this.state.sheet.gate;
        return (g && g.lanes)
            || { api: true, excel: true, records: true, records_first: false };
    }

    // ------------------------------------------------------ RECORDS R4 (D4)
    /** The rows that named somebody Payobook has never heard of. */
    get missingPeople() { return (this.state.summary && this.state.summary.unmatched) || []; }

    get missingHeading() { return notInPayobookHeading(this.missingPeople.length); }

    /** Every exception, however it is grouped — what "Need review" counts. */
    get needReview() {
        const s = this.state.summary || {};
        return (s.flagged || 0) + (s.exceptions ? s.exceptions.length : 0)
            + this.missingPeople.length;
    }

    /** "" when this database has no Import door, and then no button is offered. */
    get importDoorAction() { return importDoor(registry.category("actions")); }

    openImportWizard() {
        const door = this.importDoorAction;
        if (!door) { return; }
        this.action.doAction(door, { clearBreadcrumbs: true })
            .catch(() => this.notif.add(
                "The Import screen is not installed on this database.",
                { type: "warning" }));
    }

    async copyMissingNames() {
        const text = exceptionNames(this.missingPeople);
        if (!text) { return; }
        try {
            await navigator.clipboard.writeText(text);
        } catch {
            // A clipboard a browser refuses is not a dead end: the same text
            // goes into a selected textarea the user can copy by hand.
            const area = document.createElement("textarea");
            area.value = text;
            area.style.position = "fixed";
            area.style.opacity = "0";
            document.body.appendChild(area);
            area.select();
            try { document.execCommand("copy"); } catch { /* nothing else to try */ }
            area.remove();
        }
        this.notif.add(
            this.missingPeople.length === 1
                ? "1 name copied." : `${this.missingPeople.length} names copied.`,
            { type: "info" });
    }
    get stepKeys() { return this.wantsSheet ? STEPS_SHEET : STEPS_PLAIN; }
    get steps() { return this.stepKeys.map((k) => STEP_LABELS[k]); }
    get stepKey() { return this.stepKeys[this.state.step - 1] || "period"; }
    gotoKey(k) { const i = this.stepKeys.indexOf(k); if (i >= 0) { this.state.step = i + 1; } }
    back() { if (this.state.step > 1) { this.state.step -= 1; } }

    onField(f, ev) { this.state.form[f] = ev.target.value; }
    onDivision(ev) {
        this.state.form.division = ev.target.value;
        const di = this.divInfo;
        if (!di || !this.state.defaults) return;
        // Keep the (read-only, for demo) batch name in step with the chosen
        // configuration. Demo names keep the locked showcase period but append the
        // division so each division's run is uniquely named.
        if (this.state.defaults.is_demo) {
            this.state.form.name = this._demoName();
        } else {
            this.state.form.name = `Payroll ${di.name} ${this._periodLabel()}`;
        }
    }
    _demoName() {
        const base = (this.state.defaults && this.state.defaults.name) || "Demo Payroll June 2026";
        const di = this.divInfo;
        return di ? `${base} — ${di.name}` : base;
    }
    _periodLabel() {
        const d = this.state.form.date_start;
        if (!d) return "";
        const dt = new Date(d + "T00:00:00");
        return dt.toLocaleString("en-US", { month: "long", year: "numeric" });
    }
    get divInfo() {
        const ds = (this.state.defaults && this.state.defaults.divisions) || [];
        return ds.find(x => x.key === this.state.form.division) || null;
    }
    // ------------------------------------------------- VALUEKIND P4: who
    get statusOptions() { return this.state.defaults?.statuses || []; }
    get hasStatusFilter() { return this.statusOptions.length > 0; }

    get chosenStatuses() {
        const t = this.state.who.statuses;
        return t ? Object.keys(t).filter((k) => t[k]) : null;
    }

    toggleStatus(value) {
        const t = this.state.who.statuses;
        if (!t) { return; }
        t[value] = !t[value];
        this.refreshWho();
    }

    onWhoSearch(ev) {
        this.state.who.search = ev.target.value;
        clearTimeout(this._whoTimer);
        this._whoTimer = setTimeout(() => this.refreshWho(), 260);
    }

    togglePicked(id) {
        const picked = this.state.who.picked;
        const at = picked.indexOf(id);
        if (at >= 0) { picked.splice(at, 1); } else { picked.push(id); }
    }

    clearPicked() { this.state.who.picked = []; }

    /** Live count, so nobody presses Run Payroll and then discovers the scope. */
    async refreshWho() {
        if (!this.hasStatusFilter) { return; }
        this.state.who.loading = true;
        try {
            this.state.who.preview = await this.orm.call(
                "pb.payrun.wizard", "eligible_preview",
                [{ statuses: this.chosenStatuses, search: this.state.who.search }]
            );
        } catch (error) {
            this.state.who.preview = null;
        }
        this.state.who.loading = false;
    }

    get eligibleCount() {
        if (this.hasStatusFilter && this.state.who.preview) {
            return this.state.who.picked.length || this.state.who.preview.total;
        }
        return this.divInfo ? this.divInfo.eligible : (this.state.defaults ? this.state.defaults.eligible : 0);
    }

    // ---------------- NETROLE P3: the month's spreadsheet ----------------
    get sheetComponents() {
        const g = this.state.sheet.gate;
        return (g && g.components) || [];
    }
    get sheetReady() {
        const p = this.state.sheet.preflight;
        return !!(p && p.ok);
    }

    // ---------------- RECORDS R3: the way out to the Records Desk -----------
    /**
     * The desk exists on this database, and its JS actually shipped.
     *
     * The server can resolve an `ir.actions.client` record whose component
     * never registered, and opening one of those is a blank screen rather than
     * nothing at all — so the presence probe is the REGISTRY
     * (`plan_launcher.js:204`), not the action. A database without
     * `pb_records` shows no line.
     */
    get hasRecordsDesk() {
        return registry.category("actions").contains("pb_records_desk");
    }

    openRecordsDesk() {
        const configId = (this.state.sheet.gate
                          && this.state.sheet.gate.config_id) || 0;
        this.action.doAction("pb_records.action_pb_records_desk", {
            additionalContext: { records_config_id: configId },
            clearBreadcrumbs: false,
        }).catch(() => this.notif.add(
            _t("The Records Desk is not installed on this database."),
            { type: "warning" }));
    }

    // ---------------- RECORDS R1: update the records, or just this run -------
    get sheetOnce() { return isOneTime(this.state.sheet.mode); }
    get sheetContinueLabel() { return continueLabel(this.state.sheet.mode); }

    setSheetMode(mode) {
        if (SHEET_MODES.includes(mode)) { this.state.sheet.mode = mode; }
    }

    /** Radio-group semantics: arrows move the choice, Enter/Space confirm it. */
    onModeKey(ev, mode) {
        if (ev.key === "Enter" || ev.key === " " || ev.key === "Spacebar") {
            ev.preventDefault();
            this.setSheetMode(mode);
            return;
        }
        const next = nextSheetMode(this.state.sheet.mode, ev.key);
        if (next !== this.state.sheet.mode) {
            ev.preventDefault();
            this.setSheetMode(next);
            // Keep the focus with the choice the person just made, or the arrow
            // keys stop working after the first press.
            const root = ev.currentTarget.closest(".pw-modes");
            const el = root && root.querySelector(`[data-mode="${next}"]`);
            if (el) { el.focus(); }
        }
    }

    onDragOver(ev) { ev.preventDefault(); this.state.sheet.dragging = true; }
    onDragLeave(ev) { ev.preventDefault(); this.state.sheet.dragging = false; }
    onDrop(ev) {
        ev.preventDefault();
        this.state.sheet.dragging = false;
        const f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        this._takeFile(f);
    }
    onSheetFile(ev) {
        const f = ev.target.files && ev.target.files[0];
        this._takeFile(f);
    }
    // RD56 — one button, and it does exactly what it says: writes the
    // connected system's values onto the matching employee and contract
    // records. It creates NO payslips; the run is computed afterwards exactly
    // as it always was.
    async updateRecordsFromFeed() {
        this.state.sheet.recordsBusy = true;
        this.state.sheet.recordsMsg = "";
        this.state.sheet.error = "";
        try {
            const r = await this.orm.call(
                "pb.payrun.wizard", "update_records_from_feed",
                [{ ...this.state.form }]);
            if (r && r.ok) {
                this.state.sheet.recordsMsg = r.msg || "";
            } else {
                this.state.sheet.error = (r && r.msg) || "";
            }
        } catch (e) {
            console.warn("pb_payrun_wizard: record update failed", e);
            this.state.sheet.error = "The records could not be updated.";
        } finally {
            this.state.sheet.recordsBusy = false;
        }
    }

    clearSheetFile() {
        Object.assign(this.state.sheet, {
            file_b64: "", file_name: "", preflight: null, error: "",
        });
    }

    _takeFile(f) {
        if (!f) { return; }
        const reader = new FileReader();
        reader.onload = () => {
            this.state.sheet.file_b64 = String(reader.result).split(",")[1] || "";
            this.state.sheet.file_name = f.name;
            this.state.sheet.preflight = null;
            this.state.sheet.error = "";
            this._preflight();
        };
        reader.readAsDataURL(f);
    }

    async _preflight() {
        const s = this.state.sheet;
        const configId = (s.gate && s.gate.config_id) || null;
        if (!configId || !s.file_b64) { return; }
        s.checking = true;
        try {
            const res = await this.orm.silent.call(
                "pb.payrun.wizard", "preflight_spreadsheet",
                [configId, s.file_b64, s.file_name]);
            s.preflight = res;
            // A file that cannot be read is refused HERE, with the reason, and
            // is never carried into a run (C7 — no silent fallback).
            s.error = res && res.ok ? "" : ((res && res.msg) || "This file could not be read.");
        } catch (e) {
            s.preflight = null;
            s.error = "This file could not be read.";
        } finally {
            s.checking = false;
        }
    }

    // "Run without a spreadsheet" — a choice made while looking at the list of
    // components that will fall back, never a silent default.
    runWithoutSheet() {
        Object.assign(this.state.sheet, {
            skipped: true, file_b64: "", file_name: "", preflight: null, error: "",
        });
        return this.toCompute();
    }

    continueWithSheet() {
        this.state.sheet.skipped = false;
        return this.toCompute();
    }

    // Step 1's primary action: the pay-data step when a scheme wants a file,
    // the compute it always was when none does.
    async advanceFromPeriod() {
        if (this.wantsSheet) { return this.gotoKey("data"); }
        return this.toCompute();
    }

    async toCompute() {
        // Create + compute a (draft) run, guarding existing payroll.
        this.gotoKey("compute");
        this.state.loading = true;
        this.state.busyMsg = "Creating run and computing payslips…";
        try {
            await this._compute(false);
        } catch (e) {
            this.notif.add("Could not compute the run. See server logs.", { type: "danger" });
            this.gotoKey("period");
        } finally {
            this.state.loading = false;
            this.state.progress = null;
        }
    }

    // Chunked compute: prepare the run once, then compute in batches so the modal
    // shows a real % progress bar. All calls go through orm.silent so Odoo's
    // global loading overlay stays hidden — the modal shows its own progress
    // (no more "two spinners"). Each batch commits independently on the server.
    async _compute(force) {
        const sheet = this.state.sheet;
        const payload = { ...this.state.form, force_clean: force };
        if (sheet.skipped) { payload.spreadsheet_skipped = true; }
        // VALUEKIND P4 — who the person chose. Absent when the scheme names no
        // employment-status component, in which case the server takes no view
        // and the run covers exactly who it always did.
        if (this.hasStatusFilter) {
            payload.statuses = this.chosenStatuses;
            if (this.state.who.picked.length) {
                payload.employee_ids = [...this.state.who.picked];
            }
        }
        // Freshen the connected systems BEFORE anything is computed. A pay run
        // that computes first and syncs never is a pay run on stale data, and
        // the failure is silent because the numbers still look like numbers.
        // It never blocks: a feed that is down is reported and the run goes on,
        // because the file and the contract fallbacks may well be enough.
        //
        // One step per (system, kind of data), so the screen can NAME what it
        // is waiting on and count it. A single blocking call behind a spinner
        // reading "Creating run and computing payslips…" was describing the
        // wrong activity and gave no sense of how long it would take.
        this.state.progress = null;
        const sync = { ran: false, connectors: [], errors: [] };
        let plan = { steps: [] };
        try {
            plan = await this.orm.silent.call(
                "pb.payrun.wizard", "sync_plan", [payload]);
        } catch (e) {
            console.warn("pb_payrun_wizard: could not plan the feed sync", e);
        }
        const steps = (plan && plan.steps) || [];
        // Components wired to a feed field that names no endpoint. Nothing can
        // fetch them, so they fall to their default every run while the run
        // reports success — the exact shape of the failure this whole step
        // exists to make visible.
        sync.unroutable = (plan && plan.unroutable) || [];
        for (let i = 0; i < steps.length; i++) {
            // Reuse the wizard's own progress bar rather than inventing a
            // second kind of waiting. It already renders done/total and a
            // percentage; all this needed was to be counted.
            this.state.busyMsg = "Syncing " + steps[i].label + "…";
            this.state.progress = { done: i, total: steps.length };
            try {
                const r = await this.orm.silent.call(
                    "pb.payrun.wizard", "sync_step", [steps[i], payload]);
                // RD55 — a feed already fetched for this period is not synced
                // again. Say so rather than showing a spinner for work that did
                // not happen: "it was quick" and "it was skipped" look
                // identical otherwise, and only one of them is a reason to
                // trust the numbers.
                if (r && r.skipped) {
                    this.state.busyMsg = (r.note || steps[i].label);
                }
                sync.ran = true;
                sync.connectors.push(r);
                if (r && r.error) { sync.errors.push(r.error); }
            } catch (e) {
                console.warn("pb_payrun_wizard: feed sync failed", e);
                sync.errors.push(steps[i].label);
            }
        }
        if (steps.length) {
            this.state.progress = { done: steps.length, total: steps.length };
        }
        this.state.progress = null;
        this.state.busyMsg = "Creating run and computing payslips…";

        const prep = await this.orm.silent.call("pb.payrun.wizard", "prepare_run", [payload]);
        if (prep && prep.needs_confirmation) {
            this.gotoKey("period");       // sit behind the dialog on step 1
            this._confirmOverwrite(prep);
            return;
        }
        const { run_id, name, date_start, date_end, division } = prep;

        // The file goes in FIRST, into the run that now exists. Its payslips are
        // then the ones the chunked compute below skips (compute_batch's
        // `already` guard), so nobody is paid twice for one month.
        let batch = null;
        if (sheet.file_b64 && this.wantsSheet) {
            this.state.progress = null;
            this.state.busyMsg = "Loading " + (sheet.file_name || "the pay data file")
                + (isOneTime(sheet.mode) ? " for this run only…" : "…");
            batch = await this.orm.silent.call(
                "pb.payrun.wizard", "attach_spreadsheet",
                attachArgs(
                    run_id,
                    (sheet.preflight && sheet.preflight.config_id) || sheet.gate.config_id,
                    sheet.file_b64, sheet.file_name, date_start, date_end, sheet.mode));
            if (!batch || !batch.ok) {
                sheet.error = (batch && batch.msg) || "The pay data file could not be loaded.";
                // Nothing was computed, so the empty run it would have gone into
                // is litter, not history.
                await this.orm.silent
                    .call("pb.payrun.wizard", "discard_empty_run", [run_id])
                    .catch(() => null);
                this.state.progress = null;
                this.gotoKey("data");
                this.notif.add(sheet.error, { type: "danger" });
                return;
            }
        }

        const empIds = prep.emp_ids || [];
        const total = empIds.length;
        const CHUNK = 40;
        let computed = 0;
        const exceptions = [];
        this.state.progress = { done: 0, total };
        this.state.busyMsg = "Computing payslips…";
        for (let i = 0; i < total; i += CHUNK) {
            const chunk = empIds.slice(i, i + CHUNK);
            const r = await this.orm.silent.call(
                "pb.payrun.wizard", "compute_batch",
                [{ run_id, name, date_start, date_end, division, emp_ids: chunk }]);
            computed += (r && r.computed) || 0;
            if (r && r.exceptions) { exceptions.push(...r.exceptions); }
            const done = Math.min(total, i + chunk.length);
            this.state.progress = { done, total };
        }
        const summary = await this.orm.silent.call("pb.payrun.wizard", "get_summary", [run_id]);
        // A row the file could not process is an exception in exactly the sense
        // this wizard already means it: something a person has to look at.
        // RECORDS R4 D4 — except the rows that name somebody who is not in
        // Payobook at all: those are one block with one next step, and they are
        // taken OUT of the flat list rather than listed in both places.
        const split = splitExceptions(
            exceptions
                .concat((batch && batch.errors) || [])
                .concat((sync && sync.unroutable) || []),
            (batch && batch.unmatched) || []);
        summary.exceptions = split.rest;
        summary.unmatched = split.missing;
        // Payslips prepare_run claimed from the period were never computed here,
        // so they must be counted as done or the result reads "computed 0 of 152".
        // Payslips the pay data file created are done for the same reason.
        summary.computed = computed + (prep.adopted || 0) + ((batch && batch.created) || 0);
        summary.adopted = prep.adopted || 0;
        // …but "Computed 152 of 152" over a run where 152 were adopted and NONE
        // were computed is the headline saying the opposite of what happened.
        // On the reference tenant that heading sat above payslips two days old.
        summary.fresh = computed + ((batch && batch.created) || 0);
        summary.sync = sync;
        summary.sheet = batch || null;
        summary.skipped_components = prep.skipped_components || [];
        this.state.progress = null;
        this.state.summary = summary;
    }

    _confirmOverwrite(res) {
        const historical = res.kind === "historical";
        this.dialog.add(ConfirmationDialog, {
            title: historical ? "Historical payroll is locked" : "Payroll already exists",
            body: res.message,
            confirmLabel: historical ? "Clean July & Run" : "Clean and Run",
            cancelLabel: "Cancel",
            confirm: () => {
                if (historical && res.july) {
                    this.state.form.name = res.july.name;
                    this.state.form.date_start = res.july.date_start;
                    this.state.form.date_end = res.july.date_end;
                }
                this.gotoKey("compute");
                this.state.loading = true;
                this.state.busyMsg = "Cleaning previous data and re-running payroll…";
                // Fire-and-forget (NOT awaited): returning synchronously lets the
                // confirmation dialog close immediately, so its button spinner no
                // longer stacks on top of the wizard's own compute spinner (the
                // "two running circles"). The wizard's step-2 spinner covers the
                // re-run on its own.
                (async () => {
                    try { await this._compute(true); }
                    catch (e) { this.notif.add("Re-run failed. See server logs.", { type: "danger" }); this.gotoKey("period"); }
                    finally { this.state.loading = false; this.state.progress = null; }
                })();
            },
            cancel: () => { this.gotoKey("period"); },
        });
    }

    // "Open Payroll" — leaves the run in DRAFT and opens it so the user can
    // review the payslips and submit for HR review themselves (no auto-approve).
    //
    // In a hub the destination changes and nothing else does. A terminal CTA
    // that dumps the user on a native form is the escape the Pay Run hub exists
    // to close: the host hands in `onOpenRun` and the hub switches to its Runs
    // lens with this run focused, which is the same intent expressed inside the
    // workspace. Standalone `onOpenRun` is absent and the act_window is
    // unchanged.
    openRun() {
        const runId = this.state.summary?.run_id;
        if (!runId) { return; }
        if (this.props.onOpenRun) { return this.props.onOpenRun(runId); }
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "hr.payslip.run",
            res_id: runId, views: [[false, "form"]], target: "current",
        });
    }
    cancel() { this.action.doAction("pb_dashboard.action_pb_dashboard", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_payrun_wizard", PayrunWizard);
