/** @odoo-module **/
/**
 * The Rule Composer — Integrations Cycle 8, WP-3.
 *
 * A transformation rule is a SENTENCE: take some records, keep some, derive one
 * number, name it. This component is that sentence, as four step-cards, with
 * the data answering beside them while it is written.
 *
 * Three things about the shape of this file:
 *
 *  1. **the kernel is exported and pure.** `suggestOutputKey`, `emitSpec`,
 *     `toFormula`/`toSteps`, `railSentence`, `readOnlyReason` and `PreviewPump`
 *     are module-level functions with no `this`, because every one of them
 *     encodes a rule whose failure is INVISIBLE on a screenshot — a key that
 *     silently overwrote what the user typed, a value posted with a unary
 *     operator, a stale preview overwriting a newer one. They are tested
 *     without mounting anything (`static/tests/rule_composer.test.js`).
 *  2. **the popup chrome is the kit's**, `.pbim-modal-scrim` / `.pbim-modal`
 *     (`pb_import_kit/static/src/scss/modal.scss`), never hand-rolled — that
 *     primitive exists precisely because the recipe had been re-typed about
 *     twenty-five times with four different scrim opacities.
 *  3. **Escape is a LADDER through the hotkey service.** A plain `keydown`
 *     listener never fires: the service intercepts at capture and dispatches
 *     exactly one registration (`formula_studio.js` states the same rule). A
 *     field picker closes first, then the popup.
 *
 * WHAT THIS COMPONENT CANNOT DO. It never writes `python_code` and it never
 * emits `builder_mode: 'python'`; an advanced rule opens READ-ONLY with no save
 * affordance at all. That is the client half of a gate whose real half is
 * `pb.integrations.rule_save`'s whitelist — hiding a control is not a gate
 * (W12), and this file is the part that can be bypassed.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/**
 * The two operators that ask about the FIELD rather than about a value.
 * The server's own `UNARY_OPS`, restated here as the default for the pure
 * helpers; at runtime the set is rebuilt from the payload's vocabulary, so a
 * ninth operator arriving on the server needs no change here.
 */
export const DEFAULT_UNARY_OPS = new Set(["present", "blank"]);

/** How long an output key may be before it stops being readable in a formula. */
export const OUTPUT_KEY_MAX = 20;

/** The aggregate kinds that have no per-record value at all. */
const NO_VALUE_KINDS = new Set(["count", "date_diff", "date_check"]);

/** The two field-driven kinds, which are sentences about dates, not sums. */
const DATE_KINDS = new Set(["date_diff", "date_check"]);

/**
 * The date vocabulary.
 *
 * These mirror `hr.api.transformation.rule`'s own selections. They are
 * duplicated rather than fetched because the composer's payload carries the
 * GUIDED vocabulary only, and a rule whose kind is a date still has to be
 * readable and editable here — the "days between two dates" recipe ships one.
 * The server re-validates every one of these values against its real selection
 * and falls back to a safe default, so a drift is a wrong label and never a
 * wrong write.
 */
const DATE_COMPARE_TO = [
    { value: "period_start", label: _t("the start of the pay period") },
    { value: "period_end", label: _t("the end of the pay period") },
    { value: "today", label: _t("today") },
    { value: "fixed", label: _t("a fixed date") },
];
const DATE_UNITS = [
    { value: "days", label: _t("days") },
    { value: "months", label: _t("months") },
    { value: "years", label: _t("years") },
];
const DATE_CHECK_OPERATORS = [
    { value: "before", label: _t("is before") },
    { value: "after", label: _t("is after") },
    { value: "within", label: _t("is within N months") },
];

/** A blank rule, in the shape `rule_save` reads. */
export function blankSpec() {
    return {
        id: 0, name: "", output_key: "", description: "",
        builder_mode: "guided", rule_type: "sum",
        source_data_type: "", record_source: "records", nested_table_path: "",
        filter_conditions: { join: "all", rows: [] },
        value_steps: [], excel_formula: "", default_value: 0,
        date_source_field: "", date_compare_to: "period_end", date_unit: "days",
        date_check_operator: "", date_check_value: 0,
        active: true, plain_summary: "", python_code: "", has_python: false,
        last_error: "", last_error_at: "",
        legacy_filter: "", legacy_aggregate: "",
    };
}

/** A deep-enough copy: every value in a spec is a scalar, an array or a plain
 * object, so this is the whole of it and it never shares a row with a caller. */
export function cloneSpec(spec) {
    return JSON.parse(JSON.stringify(spec || {}));
}

/**
 * The output key a name SUGGESTS.
 *
 * A rule's key becomes a source path a mapping reads and, through that, a pay
 * component code — and the formula converter refuses an underscored or
 * substring-colliding code because it would rewrite the shorter inside the
 * longer and work out 0. So the suggestion is capitals and digits, nothing
 * else, and it is capped at a length a human can still read in a formula.
 */
export function suggestOutputKey(name) {
    return String(name || "")
        .toUpperCase()
        .replace(/[^A-Z0-9]/g, "")
        .slice(0, OUTPUT_KEY_MAX);
}

/**
 * What the key becomes when the NAME changes.
 *
 * The suggestion is a convenience and never a correction: once the user has
 * typed a key of their own, this function is the promise that nothing will
 * silently replace it. That promise is the reason it is a function rather than
 * two lines in an input handler — it is exactly the kind of rule that gets
 * refactored away by someone who cannot see it.
 */
export function keyAfterRename(name, currentKey, keyTouched) {
    return keyTouched ? currentKey : suggestOutputKey(name);
}

/**
 * The draft, as the wire shape `rule_preview` / `rule_save` read.
 *
 * Two narrowings happen HERE and nowhere else, so the preview and the save can
 * never disagree about what the user asked for:
 *
 *   - a UNARY operator ("is present", "is blank") posts NO value. The box is
 *     hidden on screen, and a value left behind by a previous operator would
 *     otherwise travel with the row and reappear the day somebody changed the
 *     operator back;
 *   - a kind with no per-record value (`count`, and the two date kinds) posts
 *     NO value steps. The server refuses a step with an empty field, so a
 *     half-filled step stashed under a `count` would make the rule unsaveable
 *     with no visible cause.
 */
export function emitSpec(draft, unaryOps = DEFAULT_UNARY_OPS) {
    const source = draft || {};
    const filter = source.filter_conditions || {};
    const rows = (filter.rows || []).map((row) => {
        const clean = { field: row.field || "", op: row.op || "is" };
        if (!unaryOps.has(clean.op)) {
            clean.value = row.value === undefined || row.value === null
                ? "" : String(row.value);
        }
        return clean;
    });
    const mode = source.builder_mode || "guided";
    const kind = source.rule_type || "count";
    const steps = (mode === "excel" || NO_VALUE_KINDS.has(kind))
        ? []
        : (source.value_steps || []).map((step) => ({
            field: step.field || "", contains: step.contains || "number",
        }));
    const spec = {
        id: source.id || 0,
        name: source.name || "",
        output_key: source.output_key || "",
        description: source.description || "",
        builder_mode: mode,
        rule_type: kind,
        source_data_type: source.source_data_type || "",
        record_source: source.record_source || "records",
        nested_table_path: source.record_source === "nested"
            ? (source.nested_table_path || "") : "",
        filter_conditions: { join: filter.join || "all", rows },
        value_steps: steps,
        excel_formula: mode === "excel" ? (source.excel_formula || "") : "",
        default_value: source.default_value || 0,
    };
    if (DATE_KINDS.has(kind)) {
        spec.date_source_field = source.date_source_field || "";
        spec.date_compare_to = source.date_compare_to || "period_end";
        spec.date_unit = source.date_unit || "days";
        spec.date_check_operator = source.date_check_operator || "";
        spec.date_check_value = source.date_check_value || 0;
    }
    return spec;
}

/**
 * Guided → formula. The steps are LIFTED OUT, not thrown away.
 *
 * The lane switch has to be free, or it is not a switch: a manager who tries
 * the formula lane and goes back must find their two value steps where they
 * left them. They cannot simply stay in the draft, because the save validator
 * refuses a step with no field and a half-built step would then make the
 * formula unsaveable — so they are held beside the draft and put back by
 * `toSteps`.
 */
export function toFormula(draft) {
    return {
        draft: { ...draft, builder_mode: "excel", value_steps: [] },
        stash: cloneSpec(draft.value_steps || []),
    };
}

/** Formula → guided, restoring whatever `toFormula` lifted out. */
export function toSteps(draft, stash) {
    const current = draft.value_steps || [];
    return {
        ...draft,
        builder_mode: "guided",
        value_steps: current.length ? current : cloneSpec(stash || []),
    };
}

/**
 * The proof rail's headline — ONE msgid with named placeholders (W80).
 *
 * A translator cannot reorder fragments, and word order is the first thing that
 * differs; this sentence carries three numbers and would be the obvious one to
 * assemble out of `t-esc` nodes. The `translate` parameter exists so the test
 * can prove there is exactly one call with placeholders in it, which is the
 * only way to assert a rule about how a string was BUILT.
 */
export function railSentence(preview, translate = _t) {
    const p = preview || {};
    return translate(
        "%(records)s records → %(matched)s match → %(result)s",
        {
            records: p.records_in || 0,
            matched: p.matched || 0,
            result: p.result === undefined || p.result === null ? "—" : p.result,
        });
}

/**
 * Why this rule cannot be edited here — or `""` when it can.
 *
 * Two different refusals with two different sentences, because they mean
 * opposite things to the reader: one is about the RULE (it is an advanced one),
 * the other is about the READER (they are not a payroll manager). A single
 * "read-only" would leave both of them guessing.
 */
export function readOnlyReason(payload, draft) {
    // `builder_mode` ALONE decides the lane. NOT `has_python` — that key means
    // "a python expression is still stored on this row", and after Cycle 8's
    // migration it is true of DEPCOUNT and WORKEDHRS, which are guided rules
    // that KEEP their original program as inert provenance so the sentence can
    // be checked against what the legacy actually did. Reading it as a lane
    // locked the owner out of the only two rules this whole cycle was for, and
    // did it on the live abm board (found there, by opening WORKEDHRS).
    if ((draft || {}).builder_mode === "python") {
        return _t("This rule is maintained in the backend form by an "
                  + "administrator, so it opens here as a summary you can read "
                  + "but not change.");
    }
    if (payload && payload.can_edit === false) {
        return _t("You can read every step of this rule. Changing a "
                  + "transformation rule is a payroll manager's job.");
    }
    return "";
}

/**
 * 260 ms debounce + a monotonic supersede token.
 *
 * Exactly the mechanism `mapping_canvas._tfPreview` uses, extracted so it can
 * be tested: the failure it prevents is a STALE response overwriting a newer
 * one, which draws a plausible wrong number and reports no error at all. The
 * timer functions are injectable for the same reason — a test that has to
 * really wait 260 ms is a test that gets deleted.
 */
export class PreviewPump {
    constructor(run, apply, options = {}) {
        this._run = run;
        this._apply = apply;
        this._delay = options.delay === undefined ? 260 : options.delay;
        this._setTimeout = options.setTimeout || ((fn, ms) => setTimeout(fn, ms));
        this._clearTimeout = options.clearTimeout || ((id) => clearTimeout(id));
        this._token = 0;
        this._timer = null;
    }

    /** Drop anything pending AND anything in flight. */
    cancel() {
        this._token++;
        if (this._timer !== null) {
            this._clearTimeout(this._timer);
            this._timer = null;
        }
    }

    schedule(payload) {
        if (this._timer !== null) {
            this._clearTimeout(this._timer);
        }
        const token = ++this._token;
        this._timer = this._setTimeout(async () => {
            this._timer = null;
            let res;
            try {
                res = await this._run(payload);
            } catch (error) {
                // Reported, never swallowed into a blank rail (W40): a failed
                // preview and a rule that legitimately answers nothing look the
                // same on screen and mean opposite things.
                console.warn("pb_integrations: rule preview failed", error);
                res = { ok: false, error: _t("This rule could not be tried out.") };
            }
            if (token !== this._token) {
                return;                            // superseded — drop it
            }
            this._apply(res);
        }, this._delay);
    }
}

// ===========================================================================
//  The component
// ===========================================================================

export class RuleComposer extends Component {
    static template = "pb_integrations.RuleComposer";
    static props = {
        connectorId: { type: Number, optional: true },
        ruleId: { type: Number, optional: true },
        /**
         * The board's connector list, so a rule can be started from the Data
         * view where no connector scope is in force. Optional: with a
         * `connectorId` the composer never asks.
         */
        connectors: { type: Array, optional: true },
        onClose: { type: Function },
        onSaved: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            loadError: "",
            data: null,
            connectorId: this.props.connectorId || 0,
            draft: null,                    // null = the front door is showing
            keyTouched: false,
            dirty: false,
            saving: false,
            confirmClose: false,
            picker: null,                   // {kind, index, q}
            preview: { loading: false, ok: null },
            ribbon: "",
            ribbonSource: "",
            ai: { text: "", busy: false, error: "" },
        });

        // Held BESIDE the draft while the formula lane is active (see
        // `toFormula`), so the switch back is free.
        this._stash = [];
        this._pump = new PreviewPump(
            (spec) => this.orm.call("pb.integrations", "rule_preview",
                                    [this.state.connectorId, spec]),
            (res) => this._applyPreview(res));

        // A ladder, through the hotkey service. A plain keydown never fires:
        // the service intercepts at capture and dispatches one registration.
        useHotkey("escape", () => {
            if (this.state.picker) {
                this.state.picker = null;
            } else if (this.state.confirmClose) {
                this.state.confirmClose = false;
            } else {
                this.requestClose();
            }
        }, { global: true });

        onWillStart(async () => {
            if (this.state.connectorId) {
                await this.load();
            } else if (this.connectorChoices.length === 1) {
                this.state.connectorId = this.connectorChoices[0].id;
                await this.load();
            } else {
                this.state.loading = false;
            }
        });
    }

    // ------------------------------------------------------------- plumbing
    ic(n, s = 16) { return ic(n, s); }

    /**
     * The popup's own two lines. Whole sentences from a getter, never `<t>`
     * fragments assembled in the template (W80) — both of these carry a name,
     * and a name is exactly the token a language wants to move.
     */
    get headTitle() {
        const d = this.state.draft;
        if (!d) { return _t("New transformation rule"); }
        return d.name || _t("New transformation rule");
    }

    get headSub() {
        const connector = (this.payload.connector || {}).name || "";
        const d = this.state.draft;
        if (d && d.output_key) {
            return _t("%(key)s on %(connector)s",
                      { key: d.output_key, connector: connector });
        }
        if (connector) {
            return _t("Take some records, keep some, derive one number — on %s",
                      connector);
        }
        return _t("Take some records, keep some, derive one number.");
    }

    get connectorChoices() { return this.props.connectors || []; }

    async pickConnector(id) {
        this.state.connectorId = Number(id) || 0;
        this.state.loading = true;
        await this.load();
    }

    async load() {
        this.state.loading = true;
        try {
            const d = await this.orm.call(
                "pb.integrations", "rule_composer_data",
                [this.state.connectorId, this.props.ruleId || false]);
            if (!d || d.ok === false) {
                this.state.loadError = (d && d.error)
                    || _t("This rule could not be opened.");
                this.state.data = null;
                return;
            }
            this.state.data = d;
            if (d.rule) {
                this.state.draft = { ...blankSpec(), ...cloneSpec(d.rule) };
                this.state.keyTouched = true;   // an existing key is the user's
                this._queuePreview();
            } else if (this.props.ruleId) {
                // Asked for a rule and got none back: it was archived away or
                // deleted while the table was on screen. Saying so beats
                // silently offering the recipe gallery, which reads as "your
                // click did something else".
                this.state.loadError = _t("That rule is no longer on this connector.");
            }
        } catch (error) {
            // Reported, never swallowed (W40).
            console.warn("pb_integrations: rule_composer_data failed", error);
            this.state.loadError = _t("This rule could not be opened.");
            this.state.data = null;
        } finally {
            this.state.loading = false;
        }
    }

    // ----------------------------------------------------------- the gates
    get payload() { return this.state.data || {}; }
    get vocabulary() { return this.payload.vocabulary || {}; }

    get unaryOps() {
        const set = new Set();
        for (const op of (this.vocabulary.operators || [])) {
            if (op.unary) { set.add(op.op); }
        }
        return set.size ? set : DEFAULT_UNARY_OPS;
    }

    isUnary(op) { return this.unaryOps.has(op); }

    /** The LANE, which is `builder_mode` and nothing else — see readOnlyReason. */
    get isPython() {
        return (this.state.draft || {}).builder_mode === "python";
    }

    /**
     * Is there a python expression still stored on this row?
     *
     * PROVENANCE, not a lane. Cycle 8's migration left the original program in
     * place on DEPCOUNT and WORKEDHRS precisely so the generated sentence can
     * be checked against what the legacy actually did, and an administrator
     * looking at a converted rule should be able to see both.
     */
    get hasLegacyPython() {
        return !!(this.state.draft || {}).has_python;
    }

    get readOnly() {
        return !!readOnlyReason(this.payload, this.state.draft || {});
    }

    get readOnlyNote() {
        return readOnlyReason(this.payload, this.state.draft || {});
    }

    get canSave() {
        if (this.readOnly || this.state.saving || !this.state.draft) { return false; }
        // A formula that does not parse must not reach a row: it would run on
        // the next pull, fail for every employee and answer with the default.
        if (this.state.draft.builder_mode === "excel"
            && this.state.preview.ok === false && !this.state.preview.readonly) {
            return false;
        }
        return true;
    }

    // --------------------------------------------------------- the front door
    get showFrontDoor() { return !this.state.draft; }
    get recipes() { return this.payload.recipes || []; }

    startFrom(recipe) {
        if (recipe.exists) { return; }
        const spec = { ...blankSpec(), ...cloneSpec(recipe.spec || {}) };
        spec.id = 0;
        if (!spec.source_data_type) { spec.source_data_type = this.defaultFeed; }
        if (!spec.name && recipe.vendor) { spec.name = recipe.title || ""; }
        if (!spec.output_key) { spec.output_key = suggestOutputKey(spec.name); }
        this.state.keyTouched = !!spec.output_key;
        this.state.draft = spec;
        this.state.dirty = true;
        this._queuePreview();
    }

    get defaultFeed() {
        const feeds = this.payload.feeds || [];
        const synced = feeds.find((f) => f.synced);
        return (synced || feeds[0] || {}).data_type || "";
    }

    onAiText(ev) { this.state.ai.text = ev.target.value || ""; }

    /**
     * "Describe it" — a DRAFT, never a save.
     *
     * When the assistant is unconfigured the server answers from a
     * deterministic keyword mapper instead, and the ribbon says so in its own
     * complete sentence rather than appending a fragment to another one (W80):
     * a translator cannot reorder a fragment, and "how this was drafted" is
     * exactly the clause a language will want to move.
     */
    async draftIt() {
        const text = (this.state.ai.text || "").trim();
        if (!text || this.state.ai.busy) { return; }
        this.state.ai.busy = true;
        this.state.ai.error = "";
        try {
            const res = await this.orm.call("pb.integrations", "rule_propose",
                                            [this.state.connectorId, text]);
            if (!res || res.ok === false) {
                this.state.ai.error = (res && res.error)
                    || _t("That could not be turned into steps. Build it with "
                          + "the steps instead.");
                return;
            }
            const spec = { ...blankSpec(), ...cloneSpec(res.spec || {}) };
            spec.id = 0;
            this.state.draft = spec;
            this.state.keyTouched = !!spec.output_key;
            this.state.dirty = true;
            this._setRibbon(res.source);
            this._queuePreview();
        } catch (error) {
            console.warn("pb_integrations: rule_propose failed", error);
            this.state.ai.error = _t("That could not be turned into steps.");
        } finally {
            this.state.ai.busy = false;
        }
    }

    /** Two whole sentences, never one sentence with a clause bolted on (W80). */
    _setRibbon(source) {
        this.state.ribbon = _t("Drafted for review — check each step.");
        this.state.ribbonSource = source === "deterministic"
            ? _t("The assistant is not configured, so these steps were matched "
                 + "from the words you used.")
            : "";
    }

    get ribbonSource() { return this.state.ribbonSource || ""; }

    dismissRibbon() {
        this.state.ribbon = "";
        this.state.ribbonSource = "";
    }

    // ----------------------------------------------------------- the catalogue
    /** Every field this connector can offer, grouped by the feed it came from. */
    get fieldGroups() {
        const d = this.payload;
        const groups = [];
        const draft = this.state.draft || {};
        if (draft.record_source === "nested" && draft.nested_table_path) {
            const table = (d.nested_tables || []).find(
                (t) => t.path === draft.nested_table_path
                    && t.data_type === draft.source_data_type);
            if (table) {
                groups.push({
                    key: "nested:" + table.path,
                    label: table.label || table.path,
                    fields: (table.columns || []).map((c) => ({
                        path: c, label: c, sample: "",
                    })),
                });
            }
        }
        for (const feed of (d.feeds || [])) {
            const fields = (d.fields || {})[feed.data_type] || [];
            if (!fields.length) { continue; }
            groups.push({ key: feed.data_type, label: feed.label, fields });
        }
        return groups;
    }

    /** The feed the TAKE step is currently pointed at. */
    get selectedFeed() {
        const wanted = (this.state.draft || {}).source_data_type;
        return (this.payload.feeds || []).find((f) => f.data_type === wanted) || null;
    }

    /**
     * Could the server learn ANYTHING about this feed's fields?
     *
     * `=== false`, never falsy — an older server that does not send the key at
     * all must not be reported as a feed with no catalogue. That is the same
     * count-honesty rule the board's `feedsKnown` follows two files over, and
     * it matters more here: this flag decides whether the composer tells the
     * user their picker is empty ON PURPOSE.
     */
    get feedFieldsUnknown() {
        const feed = this.selectedFeed;
        return !!feed && feed.fields_known === false;
    }

    /** Is there nothing at all to pick, as opposed to nothing MATCHING? */
    get catalogueEmpty() {
        return !this.fieldGroups.some((g) => g.fields.length);
    }

    /**
     * The honest empty state, in one complete sentence (W80).
     *
     * The server used to answer a never-synced connector with this product's
     * OWN `hr.employee` schema, so the picker offered two hundred native
     * columns as though the source had promised them. They are filtered out
     * now, which means an empty picker is a real and correct answer — and an
     * empty list with no explanation reads as a broken control, which is why
     * this says so and then says what to do instead. A hand-typed name is
     * still accepted: the save validator only refuses a name when it has a
     * catalogue to refuse it against.
     */
    get emptyCatalogueNote() {
        return _t("This feed has not sent anything yet, so there is nothing to "
                  + "pick from — type the field name exactly as the source "
                  + "spells it.");
    }

    /** The typed name, when the user is naming a field the catalogue lacks. */
    get typedFieldName() {
        return ((this.state.picker || {}).q || "").trim();
    }

    /** Its own msgid, and a whole phrase — never a label glued to a value. */
    get useTypedLabel() {
        return _t("Use “%s”", this.typedFieldName);
    }

    useTypedField() {
        const name = this.typedFieldName;
        if (!name) { return; }
        this.choosePickerField({ path: name, label: name });
    }

    get pickerGroups() {
        const q = ((this.state.picker || {}).q || "").toLowerCase();
        const out = [];
        for (const group of this.fieldGroups) {
            const fields = q
                ? group.fields.filter(
                    (f) => (f.label || "").toLowerCase().includes(q)
                        || (f.path || "").toLowerCase().includes(q))
                : group.fields;
            if (fields.length) {
                out.push({ ...group, fields: fields.slice(0, 60) });
            }
        }
        return out;
    }

    /** The label a chosen path should read as, or the path when it is unknown. */
    fieldLabel(path) {
        if (!path) { return _t("Choose a field"); }
        for (const group of this.fieldGroups) {
            for (const field of group.fields) {
                if (field.path === path) { return field.label || field.path; }
            }
        }
        return path;
    }

    // ----------------------------------------------------------- the pickers
    openPicker(kind, index) {
        if (this.readOnly) { return; }
        const open = this.state.picker;
        if (open && open.kind === kind && open.index === index) {
            this.state.picker = null;
            return;
        }
        this.state.picker = { kind, index, q: "" };
    }

    isPickerOpen(kind, index) {
        const p = this.state.picker;
        return !!p && p.kind === kind && p.index === index;
    }

    onPickerSearch(ev) {
        if (this.state.picker) { this.state.picker.q = ev.target.value || ""; }
    }

    /** Any click that is not inside a picker closes the open one. */
    onBodyClick(ev) {
        if (this.state.picker && !ev.target.closest(".itgrc-pick")) {
            this.state.picker = null;
        }
    }

    choosePickerField(field) {
        const p = this.state.picker;
        if (!p) { return; }
        if (p.kind === "cond") {
            this.state.draft.filter_conditions.rows[p.index].field = field.path;
        } else if (p.kind === "step") {
            this.state.draft.value_steps[p.index].field = field.path;
        } else if (p.kind === "date") {
            this.state.draft.date_source_field = field.path;
        }
        this.state.picker = null;
        this._touch();
    }

    /** The formula lane's "click a field to insert it" list. */
    insertRef(field) {
        const draft = this.state.draft;
        draft.excel_formula = (draft.excel_formula || "") + "[" + field.path + "]";
        this.state.picker = null;
        this._touch();
    }

    // ------------------------------------------------------------- step TAKE
    get feeds() { return this.payload.feeds || []; }

    feedLabel(feed) {
        return feed.synced
            ? _t("%(label)s — %(rows)s records", { label: feed.label, rows: feed.rows })
            : _t("%(label)s — never synced", { label: feed.label });
    }

    setFeed(dataType) {
        if (this.readOnly) { return; }
        this.state.draft.source_data_type = dataType;
        this.state.draft.nested_table_path = "";
        this._touch();
    }

    get nestedTables() {
        const draft = this.state.draft || {};
        return (this.payload.nested_tables || []).filter(
            (t) => t.data_type === draft.source_data_type);
    }

    setRecordSource(source) {
        if (this.readOnly) { return; }
        this.state.draft.record_source = source;
        if (source === "records") { this.state.draft.nested_table_path = ""; }
        else if (!this.state.draft.nested_table_path && this.nestedTables.length) {
            this.state.draft.nested_table_path = this.nestedTables[0].path;
        }
        this._touch();
    }

    onNestedTable(ev) {
        this.state.draft.nested_table_path = ev.target.value || "";
        this._touch();
    }

    nestedLabel(table) {
        return _t("%(label)s — %(rows)s rows in the sample",
                  { label: table.label, rows: table.rows });
    }

    // ------------------------------------------------------------- step KEEP
    get conditions() {
        return ((this.state.draft || {}).filter_conditions || {}).rows || [];
    }

    setJoin(join) {
        if (this.readOnly) { return; }
        this.state.draft.filter_conditions.join = join;
        this._touch();
    }

    addCondition() {
        if (this.readOnly) { return; }
        this.state.draft.filter_conditions.rows.push(
            { field: "", op: "is", value: "" });
        this._touch();
    }

    dropCondition(index) {
        if (this.readOnly) { return; }
        this.state.draft.filter_conditions.rows.splice(index, 1);
        this._touch();
    }

    onConditionOp(index, ev) {
        this.state.draft.filter_conditions.rows[index].op = ev.target.value;
        this._touch();
    }

    onConditionValue(index, ev) {
        this.state.draft.filter_conditions.rows[index].value = ev.target.value;
        this._touch();
    }

    // ----------------------------------------------------------- step DERIVE
    get ruleTypes() { return this.vocabulary.rule_types || []; }
    get units() { return this.vocabulary.units || []; }
    get functions() { return this.payload.functions || []; }

    get isCount() { return (this.state.draft || {}).rule_type === "count"; }
    get isDateKind() { return DATE_KINDS.has((this.state.draft || {}).rule_type); }
    get isFormulaLane() { return (this.state.draft || {}).builder_mode === "excel"; }

    /** One sentence saying why there is nothing to choose here. */
    get countNote() {
        return _t("Counting needs no field: the answer is how many records are "
                  + "left after the conditions above.");
    }

    onRuleType(ev) {
        this.state.draft.rule_type = ev.target.value;
        this._touch();
    }

    addStep() {
        if (this.readOnly) { return; }
        this.state.draft.value_steps.push({ field: "", contains: "number" });
        this._touch();
    }

    dropStep(index) {
        if (this.readOnly) { return; }
        this.state.draft.value_steps.splice(index, 1);
        this._touch();
    }

    onStepUnit(index, ev) {
        this.state.draft.value_steps[index].contains = ev.target.value;
        this._touch();
    }

    switchToFormula() {
        if (this.readOnly) { return; }
        const out = toFormula(this.state.draft);
        this._stash = out.stash;
        this.state.draft = out.draft;
        this.state.picker = null;
        this._touch();
    }

    switchToSteps() {
        if (this.readOnly) { return; }
        this.state.draft = toSteps(this.state.draft, this._stash);
        this.state.picker = null;
        this._touch();
    }

    onFormula(ev) {
        this.state.draft.excel_formula = ev.target.value || "";
        this._touch();
    }

    // ------------------------------------------------------------- the dates
    get dateCompareTo() { return DATE_COMPARE_TO; }
    get dateUnits() { return DATE_UNITS; }
    get dateCheckOperators() { return DATE_CHECK_OPERATORS; }

    onDateField(key, ev) {
        this.state.draft[key] = ev.target.value || "";
        this._touch();
    }

    // ---------------------------------------------------------- step CALL IT
    onName(ev) {
        const name = ev.target.value || "";
        this.state.draft.name = name;
        this.state.draft.output_key = keyAfterRename(
            name, this.state.draft.output_key, this.state.keyTouched);
        this._touch();
    }

    onKey(ev) {
        this.state.keyTouched = true;
        this.state.draft.output_key = (ev.target.value || "").toUpperCase();
        this._touch();
    }

    onDescription(ev) {
        this.state.draft.description = ev.target.value || "";
        this._touch();
    }

    onDefault(ev) {
        this.state.draft.default_value = ev.target.value;
        this._touch();
    }

    // ---------------------------------------------------------- the proof rail
    /**
     * Every draft change lands here: mark it dirty, then ask the server what it
     * would compute. Nothing schedules itself from a render, so there is no
     * recompute→state→patch loop to run forever (W148).
     */
    _touch() {
        this.state.dirty = true;
        this._queuePreview();
    }

    _queuePreview() {
        if (!this.state.draft) { return; }
        if (this.isPython) { return; }
        this.state.preview = { ...this.state.preview, loading: true };
        this._pump.schedule(emitSpec(this.state.draft, this.unaryOps));
    }

    _applyPreview(res) {
        if (res && res.ok) {
            this.state.preview = { loading: false, ok: true, ...res };
        } else {
            this.state.preview = {
                loading: false, ok: false,
                error: (res && (res.error || res.msg))
                    || _t("This rule could not be tried out."),
                readonly: !!(res && res.readonly),
            };
        }
    }

    get railSentence() { return railSentence(this.state.preview); }

    /**
     * The rule read back as a sentence, in the footer.
     *
     * It comes from the PREVIEW, not from `draft.plain_summary`: that field is
     * the SAVED row's summary and would stay one edit behind — plausible and
     * wrong, which is worse than absent. An advanced rule has no preview, so it
     * keeps its stored summary, which for it is the current one.
     */
    get footSummary() {
        if (this.isPython) { return (this.state.draft || {}).plain_summary || ""; }
        return this.state.preview.summary || "";
    }

    get previewRows() { return (this.state.preview.rows || []).slice(0, 24); }

    /** The big number. An em dash while nothing has been computed, because a
     * blank where a result belongs reads as "the answer is nothing". */
    get resultText() {
        const r = this.state.preview.result;
        return r === undefined || r === null ? "—" : r;
    }

    /** The count chip beside a step-card — one msgid each, never a fragment. */
    get chipRecords() {
        return _t("%s records in", this.state.preview.records_in || 0);
    }
    get chipMatched() {
        return _t("%s match", this.state.preview.matched || 0);
    }
    get chipValued() {
        return _t("%s with a value", this.state.preview.valued || 0);
    }

    /**
     * The synthetic banner.
     *
     * `hr.integration.endpoint.field.sample_value`'s docstring is load-bearing:
     * a sample is an ILLUSTRATION and is never presentable as data that was
     * received. This is that rule, on the surface, in a complete sentence.
     */
    get syntheticNote() {
        return _t("These rows are illustrations of what this source will send. "
                  + "They are not records that were received.");
    }

    get lastErrorNote() {
        const d = this.state.draft || {};
        if (!d.last_error) { return ""; }
        return _t("The last time this rule ran it failed: %s", d.last_error);
    }

    // -------------------------------------------------------------- the write
    async save() {
        if (!this.canSave) { return; }
        this.state.saving = true;
        try {
            const res = await this.orm.call(
                "pb.integrations", "rule_save",
                [this.state.connectorId,
                 emitSpec(this.state.draft, this.unaryOps),
                 this.props.ruleId || false]);
            if (!res || res.ok === false) {
                this.notif.add((res && res.msg) || _t("This rule was not saved."),
                               { type: "danger" });
                return;
            }
            this.state.dirty = false;
            this.notif.add(_t("Rule saved."), { type: "success" });
            if (this.props.onSaved) { this.props.onSaved(res.rule || null); }
            this.props.onClose();
        } catch (error) {
            console.warn("pb_integrations: rule_save failed", error);
            this.notif.add(_t("This rule was not saved."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // -------------------------------------------------------------- the close
    requestClose() {
        if (this.state.dirty && !this.readOnly) {
            this.state.confirmClose = true;
            return;
        }
        this._close();
    }

    keepEditing() { this.state.confirmClose = false; }

    discardAndClose() {
        this.state.confirmClose = false;
        this._close();
    }

    _close() {
        this._pump.cancel();
        this.props.onClose();
    }

    /** The scrim closes; the card does not (its own handler stops the click). */
    onScrimClick() { this.requestClose(); }

    /**
     * The card's own click handler. It exists ONLY to carry the `.stop`
     * modifier that keeps a click inside the dialog from reaching the scrim
     * behind it — a named no-op rather than an inline empty arrow, because an
     * OWL template expression is compiled by OWL's own parser and the one that
     * needs no thought is the one that reads as a method (W96's neighbourhood).
     */
    onCardClick() {}
}
