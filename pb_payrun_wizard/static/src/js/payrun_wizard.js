/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { IC as KIT_IC } from "@pb_import_kit/js/import_icons";
import { runPayroll, takePrefill } from "@pb_payrun_wizard/js/run_driver";
import { useSetupAction } from "@web/search/action_hook";

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
// LEARN REFRESH step 2: these were plain strings, so the rail read English
// to a Vietnamese reader. `_t` at module level is lazy in Odoo 19.
const STEP_LABELS = {
    period: _t("Select period"),
    data: _t("Pay data"),
    compute: _t("Compute"),
    review: _t("Review exceptions"),
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

/** A successful preflight alone cannot authorize a missing or rejected file. */
export function isSheetReady(sheet) {
    return !!(sheet.file_b64 && sheet.file_name && sheet.preflight?.ok && !sheet.checking && !sheet.error);
}


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

/** The heading over the block — a sentence, with the count inside it.
 *
 * ERRORS E4-4. Both halves used to be bare literals, so no translation and no
 * debranding seam ever saw them and a Rize payroll officer was told somebody
 * "is not in Payobook yet". `_t` fixes both at once: it is how the string
 * reaches the catalogue in Vietnamese AND how it reaches the rewrite that puts
 * the customer's own brand in it. The count stays an interpolated ARGUMENT, so
 * the rule that a `_t` template is rewritten and its arguments are not still
 * holds. `String(...)` because callers compare the result to a plain string.
 */
export function notInPayobookHeading(count) {
    return String(count === 1
        ? _t("1 person in the file is not in Payobook yet — they were listed, not paid")
        : _t("%(count)s people in the file are not in Payobook yet — they were listed, not paid",
             { count }));
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
/**
 * SCHEMECTX P1 — the money one screen is written in.
 *
 * Pure, and exported, because the whole defect was that three different places
 * each decided the currency for themselves and one of them said "dong" for an
 * India scheme. There is one answer now and it is testable without a server.
 *
 * @param {Object|null} scheme the chosen scheme card, or nothing
 * @param {Object|null} defaults the payload's opening answer
 */
export function schemeMoney(scheme, defaults) {
    const raw = (scheme && scheme.currency)
        || (defaults && defaults.currency)
        || null;
    if (raw && typeof raw === "object") {
        return {
            name: raw.name || "",
            symbol: raw.symbol || raw.name || "",
            position: raw.position === "before" ? "before" : "after",
            decimals: typeof raw.decimals === "number" ? raw.decimals : 2,
        };
    }
    // A server that has not been upgraded yet sent a bare name such as "VND".
    const name = typeof raw === "string" ? raw : "";
    return { name, symbol: name === "VND" ? "₫" : name, position: "before", decimals: 0 };
}

/** "INR · ₹" — the name people file under, then the sign they read. */
export function moneyLabel(money) {
    const m = money || {};
    if (m.symbol && m.name && m.symbol !== m.name) { return `${m.name} · ${m.symbol}`; }
    return m.name || m.symbol || "";
}

/**
 * A short amount in a given money. The SIGN follows the scheme; the PLACE of
 * the sign does not.
 *
 * `res.currency` records dong as written after the number, and every Payobook
 * screen — studio, payslip, results — has always written it in front. Reading
 * the stored side here would have flipped every Vietnamese amount in the
 * wizard while fixing India, which is a change nobody asked for. One house
 * style, the right sign.
 */
export function formatMoney(money, n) {
    const m = money || {};
    const sym = m.symbol || m.name || "";
    const v = Number(n) || 0;
    const abs = Math.abs(v);
    let body;
    if (abs >= 1e9) { body = (v / 1e9).toFixed(1) + "B"; }
    else if (abs >= 1e6) { body = (v / 1e6).toFixed(1) + "M"; }
    else if (abs >= 1e3) { body = (v / 1e3).toFixed(0) + "K"; }
    else { body = String(Math.round(v)); }
    return `${sym}${body}`;
}

export function exceptionNames(missing) {
    return (missing || []).map((u) => u.emp).filter(Boolean).join("\n");
}

/**
 * "Which scheme is this run for?" — the cards, behind the Payroll scheme field.
 *
 * Owner 2026-10-08: the cards used to sit open above Period and Scope, which
 * pushed the two things every run needs below the fold on a company with a
 * dozen schemes. They are now one closed field that opens this pop-up; the
 * cards themselves carry the same facts (people covered, last run) so the
 * choice is still made on the numbers. Picking a card closes it.
 */
export class SchemePickerDialog extends Component {
    static template = "pb_payrun_wizard.SchemePickerDialog";
    static components = { Dialog };
    static props = {
        groups: Array,          // [{key, label, items: [card]}] — schemeGroups
        chosenId: Number,
        onPick: Function,
        close: Function,
    };

    setup() { this.state = useState({ q: "" }); }

    get title() { return _t("Which scheme is this run for?"); }
    get total() { return this.props.groups.reduce((n, g) => n + g.items.length, 0); }

    get groups() {
        const q = this.state.q.trim().toLowerCase();
        if (!q) { return this.props.groups; }
        return this.props.groups
            .map((g) => ({ ...g, items: g.items.filter((c) =>
                `${c.name} ${c.code || ""}`.toLowerCase().includes(q)) }))
            .filter((g) => g.items.length);
    }

    num(n) { return (n || 0).toLocaleString(); }

    pick(card) {
        this.props.onPick(card);
        this.props.close();
    }
}

export class PayrunWizard extends Component {
    static template = "pb_payrun_wizard.PayrunWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        const saved = this.props.state?.payrun;
        this.state = useState(saved || {
            step: 1, loading: false, busyMsg: "",
            defaults: null,
            form: {
                name: "", date_start: "", date_end: "", struct_id: null,
                division: null,
                // GROUP P2 — which scheme this run is for. 0 until the reader
                // picks one; pre-filled when the company runs exactly one, in
                // which case nothing is asked and the step reads as it always
                // did.
                formula_config_id: 0,
            },
            // What picking a scheme showed: how many people it covers and who
            // it leaves out, both known BEFORE anything is created.
            scheme: { preview: null, loading: false, open: false },
            summary: null,
            // GROUP P5 — both payslips for one person paid in two places,
            // computed in a savepoint and rolled back. Small metadata, so it
            // lives in `useState` (GR26) and not on the instance.
            split: { open: false, loading: false, data: null },
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
            application: {
                loading: false, preview: null, error: "", reason: "", zeroKeys: [], issueQuery: "", issueFilter: "all",
                channels: { leave: false, overtime: false, adjustments: false, timesheets: false },
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
        if (!this.state.application) {
            this.state.application = { loading: false, preview: null, error: "", reason: "", zeroKeys: [], issueQuery: "", issueFilter: "all",
                channels: { leave: false, overtime: false, adjustments: false, timesheets: false } };
        }
        // Breadcrumb navigation remounts client actions. Keep the selected
        // period, scope, upload and current step in the controller's memory.
        useSetupAction({ getLocalState: () => ({ payrun: JSON.parse(JSON.stringify(this.state)) }) });
        onWillStart(async () => {
            if (saved) {
                await this._refreshGate(false);
                return;
            }
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
            // One scheme, nothing to ask: it is chosen for you and the card
            // says so. More than one, and step one becomes the question.
            if (d.formula_config_id) {
                this.state.form.formula_config_id = d.formula_config_id;
                this.refreshScheme();
                // The gate above was asked before a scheme was known, so it
                // answered with the first scheme that wants a file. Ask it
                // again now that the run has one of its own.
                this._refreshGate(false);
            }
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
            // PAYAI P2 — "Open in the screen instead": the run PayAI planned,
            // filled in. Nothing is pressed for the person.
            const pre = takePrefill(this.props.action && this.props.action.context);
            if (pre) {
                this._applyPrefill(pre);
                if (pre.from_sources) {
                    await this._refreshGate(false);
                    this.gotoKey('data');
                }
            }
        });
    }

    /**
     * Fill step one with the run PayAI planned. Only what the screen itself
     * offers is taken: a scheme that is not one of this company's cards is
     * ignored rather than forced in, and every server gate still applies when
     * the person presses the buttons.
     */
    _applyPrefill(pre) {
        const form = this.state.form;
        if (pre.date_start && pre.date_end) {
            form.date_start = pre.date_start;
            form.date_end = pre.date_end;
        }
        const card = pre.formula_config_id
            ? this.schemeCards.find((c) => c.id === pre.formula_config_id) : null;
        if (card) { this.pickScheme(card); }
        if (pre.name) { form.name = pre.name; }
        const ticks = this.state.who.statuses;
        if (ticks && Array.isArray(pre.statuses)) {
            for (const key of Object.keys(ticks)) {
                ticks[key] = pre.statuses.includes(key);
            }
            this.refreshWho();
        }
        if (pre.from_sources && Array.isArray(pre.employee_ids)) {
            this.state.who.picked = pre.employee_ids.filter(id => Number.isInteger(id) && id > 0);
        }
        this.notif.add(
            pre.from_sources ? _t("Your payroll selection is restored. Check readiness again after changing sources.") :
            _t("PayAI filled this in from your request. Check it, then run it when you are ready."),
            { type: "info" });
    }

    ic(n, s = 16) { return markup(`<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${IC[n] || IC.check}</svg>`); }
    /**
     * SCHEMECTX P1 — the money this run is in, as the server described it.
     *
     * The chosen scheme decides it, so the Scope panel changes the moment
     * another card is picked. Falls back to the payload's opening answer and
     * then to the company's, so a server that has not been upgraded yet still
     * renders a currency rather than "undefined".
     */
    get money() { return schemeMoney(this.chosenScheme, this.state.defaults); }

    /** "INR · ₹" — the name people file under, then the sign they read. */
    get moneyLabel() { return moneyLabel(this.money); }

    /**
     * A short amount in the run's own money. Every figure on this screen goes
     * through here — the sign is never written into the markup, because a
     * scheme that pays in rupees showed dong for as long as it was.
     */
    amt(n) { return formatMoney(this.money, n); }

    /** Kept so nothing that already calls it breaks; it now follows the scheme. */
    vnd(n) { return this.amt(n); }
    /** A count with the reader's own thousands separator — "1,002", not "1002". */
    num(n) { return Number(n || 0).toLocaleString(); }
    get wantsSheet() { const g = this.state.sheet.gate; return !!(g && g.wanted); }
    get applicationSettings() { return this.state.sheet.gate?.application || {}; }
    get applicationEnabled() { return !!this.applicationSettings.enabled; }
    get wantsPayData() { return this.wantsSheet || this.applicationEnabled; }
    get applicationIssueGroups() {
        const q=(this.state.application.issueQuery||'').toLowerCase(), filter=this.state.application.issueFilter||'all';
        return (this.state.application.preview?.issue_groups||[]).filter(g=>(filter==='all'||g.kind===filter||(filter==='source'&&g.kind==='contract'))&&(!q||`${g.title} ${g.owner||''} ${g.message}`.toLowerCase().includes(q)||g.items.some(i=>i.employee.toLowerCase().includes(q))));
    }
    issuePeople(group) { const q=(this.state.application.issueQuery||'').toLowerCase();return group.items.filter(i=>!q||i.employee.toLowerCase().includes(q)||group.title.toLowerCase().includes(q)); }
    get applicationZeroOptions() { return this.state.application.preview?.zero_options || []; }
    async openApplicationIssue(group, employeeId=false) {
        if(group.kind==='setup')return this.openApplicationSettings();
        try { const action=await this.orm.call('pb.payrun.wizard','application_issue_action',[this.applicationPayload(),group.kind==='review'?group.channel:group.kind,group.code||'',employeeId]);
            return this.action.doAction({...action, target:'new'}, {onClose:()=>this.previewApplicationData()});
        } catch(e) {this.state.application.error=e?.data?.message||e.message;}
    }
    applicationPayload() {
        const payload = { ...this.state.form, spreadsheet_skipped: true,
            application_certifications: { channels: { ...this.state.application.channels },
                zero_keys: [...this.state.application.zeroKeys] },
            application_certification_reason: this.state.application.reason };
        if (this.hasStatusFilter) { payload.statuses = this.chosenStatuses; }
        if (this.state.who.picked.length) { payload.employee_ids = [...this.state.who.picked]; }
        return payload;
    }
    invalidateApplicationScope() {
        Object.assign(this.state.application, { preview: null, reason: "", zeroKeys: [],
            channels: { leave: false, overtime: false, adjustments: false, timesheets: false } });
    }
    changeApplicationChannel(key, ev) {
        this.state.application.channels[key] = ev.target.checked;
        this.state.application.preview = null;
    }
    changeApplicationZero(key, ev) {
        this.state.application.zeroKeys = ev.target.checked
            ? [...new Set([...this.state.application.zeroKeys, key])]
            : this.state.application.zeroKeys.filter((v) => v !== key);
        if (this.state.application.preview) { this.state.application.preview.ok = false; }
    }
    changeApplicationReason(ev) {
        this.state.application.reason = ev.target.value;
        if (this.state.application.preview) { this.state.application.preview.ok = false; }
    }
    async previewApplicationData() {
        const a = this.state.application;
        a.loading = true; a.error = "";
        try {
            a.preview = await this.orm.silent.call("pb.payrun.wizard", "application_data_preview", [this.applicationPayload()]);
            return a.preview.ok;
        } catch (e) {
            a.error = e?.data?.message || e?.message || "Application data could not be checked.";
            a.preview = null;
            return false;
        } finally { a.loading = false; }
    }
    async openApplicationSettings() {
        const id = this.sheetConfigId;
        if (!id) { return; }
        const action = await this.orm.call("hr.formula.config", "action_application_source_settings", [[id]]);
        const payload = this.applicationPayload();
        action.params = {...action.params, return_payrun: {from_sources:true,
            name:payload.name, date_start:payload.date_start, date_end:payload.date_end,
            formula_config_id:id, statuses:payload.statuses, employee_ids:payload.employee_ids}};
        await this.action.doAction(action, { onClose: () => this._refreshGate(false) });
    }
    async openApplicationEvents() {
        const id = this.sheetConfigId;
        if (!id) { return; }
        const action = await this.orm.call('pb.payrun.wizard','application_issue_action',[this.applicationPayload(),'adjustments']);
        return this.action.doAction({...action, target:'new'}, {onClose:()=>this.previewApplicationData()});
    }
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

    // ------------------------------------------------------------ GROUP P5
    /**
     * The rows of this run whose people were paid in two places this month.
     *
     * Read off the summary the server already built rather than asked for
     * again: the run has just been computed and a second round trip would be
     * a second chance for the two lists to disagree.
     */
    get splitRows() {
        const rows = (this.state.summary && this.state.summary.rows) || [];
        return rows.filter((r) => r.split);
    }

    /**
     * Both payslips for one split person, computed for real and thrown away.
     *
     * The run's payslips are drafts and the segment is already saved, so the
     * only honest preview is the payroll engine's own answer — worked out in
     * a savepoint that is rolled back, so nothing here can leave a second
     * payslip behind for a later compute to find.
     */
    async openSplitPreview(row) {
        this.state.split.loading = true;
        this.state.split.open = true;
        this.state.split.data = null;
        try {
            this.state.split.data = await this.orm.call(
                "pb.payrun.wizard", "preview_split",
                [row.employee_id || 0, this.state.form.date_start]);
        } catch (e) {
            const data = (e && e.data) || (e && e.message && e.message.data);
            this.state.split.data = {
                ok: false, slips: [],
                note: (data && data.message)
                    || "Those two payslips could not be worked out.",
            };
        } finally {
            this.state.split.loading = false;
        }
    }

    closeSplitPreview() {
        this.state.split.open = false;
        this.state.split.data = null;
    }

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
    get stepKeys() { return this.wantsPayData ? STEPS_SHEET : STEPS_PLAIN; }
    get steps() { return this.stepKeys.map((k) => STEP_LABELS[k]); }
    get stepKey() { return this.stepKeys[this.state.step - 1] || "period"; }
    gotoKey(k) { const i = this.stepKeys.indexOf(k); if (i >= 0) { this.state.step = i + 1; } }
    back() { if (this.state.step > 1) { this.state.step -= 1; } }

    onField(f, ev) {
        const automaticName = this.chosenScheme
            ? `${this.chosenScheme.name} · ${this._periodLabel()}` : null;
        this.state.form[f] = ev.target.value;
        if (f === "date_start" || f === "date_end") {
            this.invalidateApplicationScope();
            // A changed period can add a new hire or remove a leaver. Refresh
            // both scope previews before the user proceeds with that period.
            if (automaticName && this.state.form.name === automaticName) {
                this.state.form.name = `${this.chosenScheme.name} · ${this._periodLabel()}`;
            }
            this.refreshWho();
        }
    }
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
        const scheme = this.chosenScheme;
        if (scheme) { return `${base} — ${scheme.name}`; }
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
    // -------------------------------------------------- GROUP P2: the scheme
    /**
     * The schemes this company runs, grouped by kind of run.
     *
     * Grouped rather than listed flat because "End of month" and "Mid-month
     * advance" are two different runs of the same business, and a flat list of
     * thirteen cards makes them look like thirteen alternatives.
     */
    get schemeCards() { return this.state.defaults?.schemes || []; }
    get hasSchemePicker() { return this.schemeCards.length > 0; }
    get manySchemes() { return this.schemeCards.length > 1; }

    get schemeGroups() {
        const order = ["end_cycle", "regular", "mid_cycle", "full_final"];
        const seen = new Map();
        for (const card of this.schemeCards) {
            const key = card.cycle || "regular";
            if (!seen.has(key)) {
                seen.set(key, { key, label: card.cycle_label, items: [] });
            }
            seen.get(key).items.push(card);
        }
        const out = [];
        for (const key of order) {
            if (seen.has(key)) { out.push(seen.get(key)); seen.delete(key); }
        }
        for (const group of seen.values()) { out.push(group); }
        return out;
    }

    get chosenScheme() {
        const id = this.state.form.formula_config_id;
        return this.schemeCards.find((s) => s.id === id) || null;
    }

    isChosenScheme(id) { return this.state.form.formula_config_id === id; }

    pickScheme(card) {
        this.state.form.formula_config_id = card.id;
        // The demo build drives its own run from the part of the business a
        // scheme belongs to. Keeping that in step means picking a scheme keeps
        // pointing the demo path at the same place instead of two controls
        // disagreeing about one run.
        if (card.division) { this.state.form.division = card.division; }
        if (this.state.defaults && this.state.defaults.is_demo) {
            this.state.form.name = this._demoName();
        } else {
            // "<Scheme> · <Month>" — the scheme already says it is payroll, so
            // "Payroll <scheme name> <month>" says it twice.
            this.state.form.name = `${card.name} · ${this._periodLabel()}`;
        }
        this.state.scheme.open = false;
        this.refreshWho();
        // The pay-data step is ABOUT the chosen scheme: its components, its
        // filename hint, its source lanes. Asking the gate again keeps the two
        // in step, and drops a file that was picked for the scheme before —
        // that file was read under the other scheme's columns.
        this._refreshGate(true);
    }

    /**
     * Re-read the pay-data gate for the scheme this run is actually on.
     *
     * The gate is fetched once at start-up, before any scheme is chosen, so
     * its answer is "the first scheme that wants a file". Left alone, that id
     * is what the step previews with and what the file is loaded under — which
     * is how a run on one scheme was fed a file read as another.
     */
    async _refreshGate(clearFile) {
        const gate = await this.orm.silent
            .call("pb.payrun.wizard", "spreadsheet_gate",
                  [{ formula_config_id: this.state.form.formula_config_id || 0 }])
            .catch(() => null);
        if (!gate) { return; }
        if (this.state.sheet.gate?.application?.settings_stamp !== gate.application?.settings_stamp) {
            this.invalidateApplicationScope();
        }
        this.state.sheet.gate = gate;
        if (clearFile) {
            this.clearSheetFile();
            Object.assign(this.state.application, { preview: null, error: "", reason: "", zeroKeys: [],
                channels: { leave: false, overtime: false, adjustments: false, timesheets: false } });
        }
    }

    /** How many people this scheme covers, and who it leaves out. */
    async refreshScheme() {
        if (!this.state.form.formula_config_id) { return; }
        const request = this._schemePreviewRequest = (this._schemePreviewRequest || 0) + 1;
        this.state.scheme.loading = true;
        try {
            const preview = await this.orm.silent.call(
                "pb.payrun.wizard", "scheme_preview",
                [{
                    formula_config_id: this.state.form.formula_config_id,
                    statuses: this.hasStatusFilter ? this.chosenStatuses : null,
                    date_start: this.state.form.date_start,
                    date_end: this.state.form.date_end,
                }]);
            if (request === this._schemePreviewRequest) { this.state.scheme.preview = preview; }
        } catch (e) {
            console.warn("pb_payrun_wizard: could not preview the scheme", e);
            if (request === this._schemePreviewRequest) { this.state.scheme.preview = null; }
        } finally {
            if (request === this._schemePreviewRequest) { this.state.scheme.loading = false; }
        }
    }

    get notCoveredPeople() {
        return (this.state.scheme.preview && this.state.scheme.preview.people)
            || [];
    }

    toggleNotCovered() { this.state.scheme.open = !this.state.scheme.open; }

    openSchemePicker() {
        this.dialog.add(SchemePickerDialog, {
            groups: this.schemeGroups,
            chosenId: this.state.form.formula_config_id || 0,
            onPick: (card) => this.pickScheme(card),
        });
    }

    /**
     * The way OUT of the dead end: the screen where the map is drawn.
     *
     * Probed through the actions registry, because the Mapping screen is not a
     * dependency of this module and an offer that fails when it is taken is
     * worse than an offer that was never made.
     */
    get hasSchemeMap() {
        return registry.category("actions").contains("pb_mapping_studio");
    }

    openSchemeMap() {
        this.action.doAction("pb_formula_studio.action_pb_mapping_studio", {
            additionalContext: { pb_mode: "scheme" },
            clearBreadcrumbs: false,
        }).catch(() => this.notif.add(
            _t("The Mapping screen is not installed on this database."),
            { type: "warning" }));
    }

    // ------------------------------------------------- VALUEKIND P4: who
    get statusOptions() { return this.state.defaults?.statuses || []; }
    get hasStatusFilter() { return this.statusOptions.length > 0; }

    get chosenStatuses() {
        const t = this.state.who.statuses;
        return t ? Object.keys(t).filter((k) => t[k]) : null;
    }

    toggleStatus(value) {
        this.invalidateApplicationScope();
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
        this.invalidateApplicationScope();
        const picked = this.state.who.picked;
        const at = picked.indexOf(id);
        if (at >= 0) { picked.splice(at, 1); } else { picked.push(id); }
    }

    clearPicked() { this.state.who.picked = []; this.invalidateApplicationScope(); }

    /** Live count, so nobody presses Run Payroll and then discovers the scope. */
    async refreshWho() {
        const request = this._whoPreviewRequest = (this._whoPreviewRequest || 0) + 1;
        if (!this.hasStatusFilter) {
            if (this.state.form.formula_config_id) { await this.refreshScheme(); }
            return;
        }
        this.state.who.loading = true;
        try {
            const preview = await this.orm.call(
                "pb.payrun.wizard", "eligible_preview",
                [{ statuses: this.chosenStatuses, search: this.state.who.search,
                   formula_config_id: this.state.form.formula_config_id,
                   date_start: this.state.form.date_start, date_end: this.state.form.date_end }]
            );
            if (request === this._whoPreviewRequest) { this.state.who.preview = preview; }
        } catch (error) {
            if (request === this._whoPreviewRequest) { this.state.who.preview = null; }
        }
        if (request !== this._whoPreviewRequest) { return; }
        this.state.who.loading = false;
        // The scheme count is a function of the status ticks too, so the two
        // numbers on this step can never disagree about one run.
        if (this.state.form.formula_config_id) { this.refreshScheme(); }
    }

    get eligibleCount() {
        // GROUP P2 — once a scheme is chosen, the honest count is the one the
        // MAP gives, because that is who the run will actually cover.
        if (this.state.scheme.preview) {
            return this.state.who.picked.length
                || this.state.scheme.preview.covered;
        }
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
    /**
     * The scheme the pay-data step is about — the run's own, always.
     *
     * The gate's id is only a fallback for the moment before a scheme has been
     * chosen. Reading the gate first is what let a file be loaded under a
     * scheme the run was never on.
     */
    get sheetConfigId() {
        const g = this.state.sheet.gate;
        return this.state.form.formula_config_id || (g && g.config_id) || 0;
    }
    get sheetReady() { return isSheetReady(this.state.sheet); }

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
        const configId = this.sheetConfigId;
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
        ev.target.value = ''; // Let the same filename be selected again after an error.
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
        const configId = this.sheetConfigId || null;
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
    async runWithoutSheet() {
        if (this.applicationEnabled && !(await this.previewApplicationData())) { return; }
        Object.assign(this.state.sheet, {
            skipped: true, file_b64: "", file_name: "", preflight: null, error: "",
        });
        return this.toCompute();
    }

    continueWithSheet() {
        if (!this.sheetReady) {
            this.notif.add(_t('Upload and review a valid workbook before computing.'), { type: 'warning' });
            return;
        }
        this.state.sheet.skipped = false;
        return this.toCompute();
    }

    // Step 1's primary action: the pay-data step when a scheme wants a file,
    // the compute it always was when none does.
    async advanceFromPeriod() {
        // GROUP P2 — the refusal is here, in front of the cards, and not on
        // the step after: a run created for the wrong scheme looks completely
        // normal until somebody reads a payslip.
        if (this.manySchemes && !this.state.form.formula_config_id) {
            this.notif.add(
                _t("Pick the payroll scheme this run is for. The people it covers appear as soon as you do."),
                { type: "warning" });
            return;
        }
        if (this.wantsPayData) { return this.gotoKey("data"); }
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
            const reason = e?.data?.message || e?.message || "Could not compute the run. See server logs.";
            this.notif.add(reason, { type: "danger" });
            if (this.state.sheet.skipped && this.applicationEnabled) {
                this.state.application.error = reason;
                this.gotoKey("data");
            } else { this.gotoKey("period"); }
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
        const payload = { ...(sheet.skipped && this.applicationEnabled ? this.applicationPayload() : this.state.form), force_clean: force };
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
        // PAYAI P2 — the chain itself lives in the shared run driver
        // (`run_driver.js`), so this screen and the PayAI card run payroll
        // through the very same calls. What stays HERE is everything about
        // this screen: its busy message, its progress bar, its dialogs, which
        // step it shows, and the summary arithmetic the review step reads.
        // The pay-data file goes in only when the scheme wants one.
        const res = await runPayroll(this.orm, payload, {
            onStep: (label) => { this.state.busyMsg = label; },
            onProgress: (p) => {
                this.state.progress = p ? { done: p.done, total: p.total } : null;
            },
            sheet: (sheet.file_b64 && this.wantsSheet) ? {
                file_b64: sheet.file_b64,
                file_name: sheet.file_name,
                oneTime: isOneTime(sheet.mode),
                attachArgs: (runId, dateStart, dateEnd) => attachArgs(
                    runId, this.sheetConfigId,
                    sheet.file_b64, sheet.file_name, dateStart, dateEnd, sheet.mode),
            } : null,
        });
        const prep = res.prep;
        if (res.stage === "blocked") {
            // PAYAI P0 — the period's payroll is approved, paid or waiting for
            // approval. The server names the runs and the reasons; there is no
            // "Clean and Run" to offer, only the way back to step 1.
            if (prep.application_preflight) {
                this.state.application.preview = prep.application_preflight;
                this.gotoKey("data");
            } else { this.gotoKey("period"); }
            this.notif.add(prep.message, { type: "warning", sticky: true });
            return;
        }
        if (res.stage === "confirm") {
            this.gotoKey("period");       // sit behind the dialog on step 1
            this._confirmOverwrite(prep);
            return;
        }
        const batch = res.batch;
        if (res.stage === "sheet_failed") {
            sheet.error = (batch && batch.msg) || "The pay data file could not be loaded.";
            this.gotoKey("data");
            this.notif.add(sheet.error, { type: "danger" });
            return;
        }
        if (res.stage === "pending") {
            // APPROVAL MATRIX P5. The file loaded and passed its checks, and
            // somebody has to say yes before it becomes payslips.
            sheet.pending = true;
            sheet.pendingWith = batch.with_whom || "";
            sheet.requestId = batch.request_id || 0;
            this.gotoKey("data");
            this.notif.add(
                batch.with_whom
                    ? _t("The pay data is with %s for approval. The payslips are made once it is approved.",
                         batch.with_whom)
                    : _t("The pay data is waiting for its approval. The payslips are made once it is approved."),
                { type: "success", sticky: true });
            return;
        }
        const { summary, exceptions, computed, sync } = res;
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
