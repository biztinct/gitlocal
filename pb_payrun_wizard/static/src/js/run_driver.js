/** @odoo-module **/
/**
 * THE RUN DRIVER — the Run Payroll chain, once, for every screen that runs it.
 *
 * PAYAI P2. This is the wizard's `_compute` lifted out unchanged, so the
 * wizard and the PayAI card run payroll through exactly the same calls in
 * exactly the same order:
 *
 *     sync_plan → sync_step × n → prepare_run → [attach_spreadsheet]
 *       → compute_batch in chunks of 40 → get_summary
 *
 * It holds no component state and shows nothing. It reports through two
 * callbacks and returns what happened; the CALLER decides what to do about
 * it. In particular the driver never decides on `needs_confirmation` or
 * `blocked` from `prepare_run`: it hands `prep` back with `stage` set and
 * stops — the wizard shows its own dialog, PayAI shows its blocked card.
 * Every gate stays on the server (`@runner_only`, the period check, the
 * clean-and-run blockers); nothing here is a gate.
 *
 * @param {Object} orm       the orm service (calls go through `orm.silent`)
 * @param {Object} payload   the run's vals — name, dates, scheme, division,
 *                           statuses, employee_ids, spreadsheet_skipped,
 *                           force_clean (the wizard only; PayAI never sends it)
 * @param {Object} [opts]
 * @param {Function} [opts.onStep]      (label) — what the run is doing now
 * @param {Function} [opts.onProgress]  ({done, total, label, phase}) or null
 * @param {Object}   [opts.sheet]       the wizard's pay-data file, when wanted:
 *                                      {file_b64, file_name, oneTime: bool,
 *                                       attachArgs: (runId, dateStart,
 *                                       dateEnd) => Array}
 * @returns {Promise<Object>} `{stage, run_id, prep, summary, exceptions,
 *                              sync, batch, computed}` where `stage` is one of
 *          'blocked' | 'confirm' | 'sheet_failed' | 'pending' | 'done'
 */
export const CHUNK = 40;

export async function runPayroll(orm, payload, { onStep, onProgress, sheet } = {}) {
    const step = (label) => { if (onStep) { onStep(label); } };
    const progress = (p) => { if (onProgress) { onProgress(p); } };

    // Freshen the connected systems BEFORE anything is computed. It never
    // blocks: a feed that is down is reported and the run goes on.
    progress(null);
    const sync = { ran: false, connectors: [], errors: [] };
    let plan = { steps: [] };
    try {
        plan = await orm.silent.call("pb.payrun.wizard", "sync_plan", [payload]);
    } catch (e) {
        console.warn("pb_payrun_wizard: could not plan the feed sync", e);
    }
    const steps = (plan && plan.steps) || [];
    sync.unroutable = (plan && plan.unroutable) || [];
    for (let i = 0; i < steps.length; i++) {
        step("Syncing " + steps[i].label + "…");
        progress({ done: i, total: steps.length, label: steps[i].label, phase: "sync" });
        try {
            const r = await orm.silent.call(
                "pb.payrun.wizard", "sync_step", [steps[i], payload]);
            // RD55 — a feed already fetched for this period is not synced
            // again; say so rather than showing a spinner for nothing.
            if (r && r.skipped) {
                step(r.note || steps[i].label);
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
        progress({ done: steps.length, total: steps.length, phase: "sync" });
    }
    progress(null);
    step("Creating run and computing payslips…");

    const prep = await orm.silent.call("pb.payrun.wizard", "prepare_run", [payload]);
    if (prep && prep.blocked) {
        return { stage: "blocked", prep, sync };
    }
    if (prep && prep.needs_confirmation) {
        return { stage: "confirm", prep, sync };
    }
    const { run_id, name, date_start, date_end, division } = prep;

    // The file goes in FIRST, into the run that now exists. Its payslips are
    // then the ones the chunked compute below skips (compute_batch's
    // `already` guard), so nobody is paid twice for one month.
    let batch = null;
    if (sheet && sheet.file_b64) {
        progress(null);
        step("Loading " + (sheet.file_name || "the pay data file")
             + (sheet.oneTime ? " for this run only…" : "…"));
        batch = await orm.silent.call(
            "pb.payrun.wizard", "attach_spreadsheet",
            sheet.attachArgs(run_id, date_start, date_end));
        if (!batch || !batch.ok) {
            // Nothing was computed, so the empty run it would have gone into
            // is litter, not history.
            await orm.silent
                .call("pb.payrun.wizard", "discard_empty_run", [run_id])
                .catch(() => null);
            progress(null);
            return { stage: "sheet_failed", run_id, prep, batch, sync };
        }
        if (batch.pending) {
            progress(null);
            return { stage: "pending", run_id, prep, batch, sync };
        }
    }

    const empIds = prep.emp_ids || [];
    const total = empIds.length;
    let computed = 0;
    const exceptions = [];
    progress({ done: 0, total, phase: "compute" });
    step("Computing payslips…");
    for (let i = 0; i < total; i += CHUNK) {
        const chunk = empIds.slice(i, i + CHUNK);
        const r = await orm.silent.call(
            "pb.payrun.wizard", "compute_batch",
            [{ run_id, name, date_start, date_end, division,
                formula_config_id: prep.formula_config_id, emp_ids: chunk }]);
        computed += (r && r.computed) || 0;
        if (r && r.exceptions) { exceptions.push(...r.exceptions); }
        const done = Math.min(total, i + chunk.length);
        progress({ done, total, phase: "compute" });
    }
    const summary = await orm.silent.call("pb.payrun.wizard", "get_summary", [run_id]);
    return { stage: "done", run_id, prep, summary, exceptions, sync, batch, computed };
}

// ---------------------------------------------------------------- prefill
/**
 * PAYAI P2 — "Open in the screen instead". PayAI hands the wizard the run it
 * planned (the server built these vals; the person still presses every
 * button on the screen). Stashed once and taken once, because inside the Pay
 * hub the wizard is a lens and does not see the action's context.
 */
let PREFILL = null;

export function stashPrefill(vals) {
    PREFILL = vals && typeof vals === "object" ? { ...vals } : null;
}

export function takePrefill(actionContext) {
    const fromContext = actionContext && actionContext.pb_payai_prefill;
    const out = (fromContext && typeof fromContext === "object") ? fromContext : PREFILL;
    PREFILL = null;
    return out || null;
}
