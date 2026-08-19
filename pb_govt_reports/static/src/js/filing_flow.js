/** @odoo-module **/
/**
 * `pb_filing_flow` — generating a statutory filing, as a flow.
 *
 * Flow doctrine 1, the product's worst screen. The modal this replaces is a
 * `target: "new"` form on `pb.govt.report.wizard` carrying THIRTY fields in six
 * groups, five of which are `invisible="report_type != …"` — so an officer
 * filing a headcount increase looked at a sheet whose visible half was three
 * fields and whose invisible half was twenty-seven, with two footer buttons,
 * one of which is called MAIL REPORT.
 *
 * Here it is three steps: choose the filing, set its scope, generate it.
 *
 * What this is NOT is a second implementation of a filing. `pb.filing.flow`
 * writes the wizard's fields from an allow-list, presses the wizard's OWN
 * generate button, and materialises whatever that button chose — the same
 * facade shape as C3's `pb.integration.onboarding`. Nothing here knows what a
 * BHXH630 is, and that is the point.
 *
 * Four rails worth stating:
 *
 *  1. **the mount READS.** `onWillStart` calls `start()`, which is a pure read
 *     of the country catalogue. The transient is created when the user picks a
 *     filing — a click — and nothing is generated until a second one. OWL
 *     restarts an in-flight mount whenever the parent re-renders (W21.1), so
 *     anything with a real side effect had to be out of there.
 *  2. **`state.busy` is the concurrency guard.** Two Generate clicks in flight
 *     would render the report twice and store two attachments, in separate
 *     transactions where neither can see the other — a uniqueness guard cannot
 *     fix a concurrency problem (W21.1). So the button is disabled for the
 *     whole round trip, and every call goes through `_run`.
 *  3. **the step-2 form is built from the SERVER's descriptor.** Labels, types,
 *     selection values and defaults all come from the wizard's own `_fields`,
 *     so a wizard that grows a parameter grows it here, and no label is
 *     restated in two places.
 *  4. **nothing here can send anything.** The only server methods this file
 *     names are `start`, `scope`, `save_scope`, `search_employees` and
 *     `generate`, and the facade's generate step is a constant table of one
 *     method per country. The wizard's MAIL REPORT button is not reachable from
 *     this surface by any path.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";

const MODEL = "pb.filing.flow";

const STEPS = [
    { id: "filing", label: _t("Choose the filing") },
    { id: "scope", label: _t("Scope") },
    { id: "deliver", label: _t("Generate") },
];

export class PbFilingFlow extends Component {
    static template = "pb_govt_reports.PbFilingFlow";
    static components = { HubBackChip };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        // Read ONCE, from props, never written back — the arrival protocol's
        // rule since C1's shell.
        this.back = hubBack(this.props);
        const ctx = (this.props.action && this.props.action.context) || {};

        this.state = useState({
            ready: false,
            busy: false,
            busyMsg: "",
            error: "",
            step: "filing",
            // step 1
            cat: null,
            // a board button may preselect a filing
            asked: ctx.pb_filing || "",
            askedCountry: ctx.pb_country || "",
            // step 2
            scope: null,
            form: {},
            empQuery: "",
            empHits: [],
            // step 3
            result: null,
        });

        onWillStart(async () => {
            await this.load(this.state.askedCountry || undefined);
            // A preselected filing is an instruction from the board, and it is
            // consumed AFTER the load because it needs the catalogue to say
            // whether that key exists here (W44's second rail).
            const asked = this.state.asked;
            this.state.asked = "";
            if (asked && (this.state.cat.filings || []).some((f) => f.key === asked)) {
                await this.pickFiling(asked);
            }
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get steps() { return STEPS; }
    get stepIndex() { return STEPS.findIndex((s) => s.id === this.state.step); }
    get cat() { return this.state.cat || {}; }

    // ------------------------------------------------------------------ plumbing
    /**
     * One in-flight call at a time, and an error is REPORTED.
     *
     * A catch that quietly leaves the surface where it was makes a failed
     * generate look like a slow one (W40). Every failure lands in
     * `state.error`, which the body renders above the step.
     */
    async _run(msg, fn) {
        if (this.state.busy) { return null; }
        this.state.busy = true;
        this.state.busyMsg = msg;
        this.state.error = "";
        try {
            return await fn();
        } catch (e) {
            this.state.error = this._err(e);
            return null;
        } finally {
            this.state.busy = false;
            this.state.busyMsg = "";
        }
    }

    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message)
            || _t("This step could not be completed.");
    }

    async load(country) {
        const d = await this.orm.call(MODEL, "start", [country || false]);
        this.state.cat = d;
        this.state.ready = true;
    }

    // ------------------------------------------------------------------- step 1
    /** A CLICK handler. */
    async selectCountry(cc) {
        await this._run(_t("Loading filings…"), async () => {
            await this.load(cc);
            this.state.scope = null;
            this.state.form = {};
            this.state.step = "filing";
        });
    }

    /** A CLICK handler: creates the transient and moves to Scope. */
    async pickFiling(key) {
        const c = this.cat;
        // Re-entering the SAME filing keeps its transient and its values: the
        // point of saving on Back is that coming forward finds them again.
        if (this.state.scope && this.state.scope.filing_key === key) {
            this.state.step = "scope";
            return;
        }
        await this._run(_t("Preparing the filing…"), async () => {
            const d = await this.orm.call(MODEL, "scope", [c.country_code, key]);
            this.state.scope = d;
            this.state.form = { ...d.values };
            this.state.result = null;
            this.state.step = "scope";
        });
    }

    get filing() {
        const key = this.state.scope && this.state.scope.filing_key;
        return (this.cat.filings || []).find((f) => f.key === key) || null;
    }

    // ------------------------------------------------------------------- step 2
    get fields() { return (this.state.scope && this.state.scope.fields) || []; }

    /**
     * Two sections, split by the block the SERVER put each field in.
     *
     * The alternative — deriving "is this one of the filing's own parameters"
     * from a name prefix here — would be the same fact in two places, and the
     * copy in the browser is always the one that goes stale when a wizard grows
     * a field.
     */
    get commonFields() { return this.fields.filter((f) => f.block === "common"); }
    get filingFields() { return this.fields.filter((f) => f.block === "filing"); }

    /**
     * ONE getter, ONE sentence, ONE msgid.
     *
     * A translator cannot reorder fragments assembled out of `t` nodes, and
     * word order is exactly what differs between languages (W80). These three
     * are also the strings on this surface that carry NUMBERS, which makes them
     * the three that must not silently stay English.
     */
    get hiddenLabel() {
        const n = (this.state.scope && this.state.scope.hidden_count) || 0;
        return _t("%s further parameters belong to the other filings of this "
                  + "country and are not asked for here.", n);
    }

    get employeeHint() {
        const n = this.chosenEmployees.length;
        return n
            ? _t("%s employees picked — the filing covers exactly these.", n)
            : _t("Leave empty to cover everyone in range, narrowed by the "
                 + "department and contract type above.");
    }

    get outcomeLabel() {
        const d = this.state.result || {};
        const n = (d.artifacts || []).length;
        if (n) {
            return _t("Generated %s file(s). Nothing has been sent anywhere — "
                      + "download them and file them yourself.", n);
        }
        return _t("This filing ran and produced no file.");
    }

    value(name) {
        const v = this.state.form[name];
        return v === undefined || v === false ? "" : v;
    }

    isSelected(name, id) { return String(this.state.form[name] || "") === String(id); }

    onField(name, ev) {
        const el = ev.target;
        this.state.form[name] = el.type === "checkbox" ? el.checked : el.value;
    }

    // ---- the employee typeahead ----
    async onEmpSearch(ev) {
        const q = ev.target.value || "";
        this.state.empQuery = q;
        if (q.trim().length < 2) { this.state.empHits = []; return; }
        try {
            this.state.empHits = await this.orm.call(MODEL, "search_employees", [q]);
        } catch (e) {
            // A typeahead that DISABLES itself on an error is exactly the shape
            // that deleted this program's person search for three phases (W40).
            console.warn("pb_filing_flow: employee search failed", e);
            this.state.empHits = [];
        }
    }

    get chosenEmployees() { return this.state.form.employee_ids || []; }

    addEmployee(hit) {
        const cur = this.chosenEmployees;
        if (cur.some((e) => e.id === hit.id)) { return; }
        this.state.form.employee_ids = [...cur, hit];
        this.state.empQuery = "";
        this.state.empHits = [];
    }

    removeEmployee(id) {
        this.state.form.employee_ids = this.chosenEmployees.filter((e) => e.id !== id);
    }

    /** What goes over the wire: ids for relations, values for the rest. */
    get payload() {
        const out = {};
        for (const f of this.fields) {
            const v = this.state.form[f.name];
            if (f.type === "typeahead") {
                out[f.name] = (v || []).map((e) => e.id);
            } else if (f.type === "many2one") {
                out[f.name] = v ? Number(v) : false;
            } else {
                out[f.name] = v === undefined ? false : v;
            }
        }
        return out;
    }

    /**
     * Back to the catalogue, WITHOUT losing what was typed.
     *
     * The transient survives the step change, but the typed values only live in
     * this component until something writes them — so Back saves first. Leaving
     * the write out is the version of this that looks fine and quietly discards
     * a nine-field BHXH630 scope the moment somebody checks which filing they
     * had picked.
     */
    async backToFilings() {
        const s = this.state.scope;
        if (s) {
            await this._run(_t("Saving…"), () =>
                this.orm.call(MODEL, "save_scope",
                              [s.wizard_id, s.country, s.filing_key, this.payload]));
        }
        this.state.step = "filing";
    }

    // ------------------------------------------------------------------- step 3
    /**
     * A CLICK handler, and the only method in this file that can write.
     *
     * `_run` holds `busy` for the whole round trip, so a double click is one
     * artifact set. The button is also `t-att-disabled` on the same flag, so
     * the second click never reaches this method at all.
     */
    async generate() {
        const s = this.state.scope;
        if (!s) { return; }
        const d = await this._run(_t("Generating the filing…"), () =>
            this.orm.call(MODEL, "generate",
                          [s.wizard_id, s.country, s.filing_key, this.payload]));
        if (!d) { return; }
        this.state.result = d;
        this.state.step = "deliver";
        if ((d.artifacts || []).length) {
            // One sentence, one msgid (W80).
            this.notif.add(this.producedLabel(d), { type: "success" });
        }
    }

    producedLabel(d) {
        const n = (d.artifacts || []).length;
        return _t("%s produced %s file(s) — download them below.",
                  (this.filing && this.filing.label) || _t("This filing"), n);
    }

    get artifacts() { return (this.state.result && this.state.result.artifacts) || []; }

    get resultMessage() { return (this.state.result && this.state.result.message) || ""; }

    sizeLabel(a) {
        const kb = Math.max(1, Math.round((a.size || 0) / 1024));
        return _t("%s KB", kb);
    }

    download(a) {
        // A plain navigation to `/web/content`, which re-checks the caller's
        // rights on the attachment. Nothing is emailed and nothing is filed
        // with anybody: this flow generates, and that is the whole of it.
        window.open(a.url, "_blank");
    }

    /** "Generate another" — back to step 1 with a clean slate. */
    async reset() {
        this.state.result = null;
        this.state.scope = null;
        this.state.form = {};
        this.state.empQuery = "";
        this.state.empHits = [];
        this.state.error = "";
        this.state.step = "filing";
    }

    // --------------------------------------------------------------------- doors
    /**
     * Leave the flow.
     *
     * `back` is whatever sent us here (the Compliance hub, or the Government
     * Reports board). Falling back to the board rather than to nothing means an
     * abandoned flow always lands somewhere real — a wizard whose Cancel does
     * nothing is a trap.
     */
    close() {
        if (this.back) {
            openHub(this.action, {
                tag: this.back.tag, xmlid: this.back.xmlid,
                lens: this.back.lens, lensKey: this.back.lensKey,
                context: this.back.context || {},
            });
            return;
        }
        openHub(this.action, { tag: "pb_govt_reports" });
    }
}

registry.category("actions").add("pb_filing_flow", PbFilingFlow);
