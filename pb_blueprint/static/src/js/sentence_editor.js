/** @odoo-module **/

import { Component, useState, useRef, onWillStart, onMounted, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

import {
    cloneRecipe, codeFromName, codeProblem, detailFor, num, sameRecipe,
    treatmentChips,
} from "./recipe_text";

/**
 * One component, as a sentence you can change a word at a time.
 *
 * Two lanes. **Guided** builds the rule out of inline choices in one flowing
 * paragraph — "For everyone, calculate the contract salary, prorated by paid
 * working days." — and shows the Excel it produces underneath, with the value
 * it would pay the sample employee beside it. **Excel** is the same rule with
 * the formula typed by hand; saving from that lane means the person owns the
 * formula and nothing will ever rewrite it.
 *
 * Everything shown here is worked out by the SERVER. The proof strip is a real
 * evaluation of a candidate formula inside a savepoint that is always rolled
 * back, so a preview cannot change what anybody is paid — including by
 * accident, including half-way through.
 */
export class SentenceEditor extends Component {
    static template = "pb_blueprint.SentenceEditor";
    static props = {
        configId: { type: Number },
        ruleId: { type: [Number, Boolean], optional: true },
        sampleId: { type: [Number, Boolean], optional: true },
        sampleName: { type: String, optional: true },
        revision: { type: Number, optional: true },
        newGroup: { type: String, optional: true },
        takenCodes: { type: Array, optional: true },
        currency: { type: String, optional: true },
        onSaved: { type: Function },
        onRemoved: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.rootRef = useRef("root");
        this.nameRef = useRef("name");
        this.excelRef = useRef("excel");

        this.state = useState({
            loading: true,
            error: "",
            lane: "guided",
            rule: null,
            recipe: null,
            options: null,
            provenance: null,
            hasRecipe: false,
            source: "manual",
            name: "",
            code: "",
            codeTouched: false,
            excel: "",
            open: false,               // the tax/insurance disclosure
            // the proof strip
            proof: { state: "idle", value: null, message: "", formula: "",
                     needs: [] },
            saving: false,
            confirmClose: false,
        });

        this._pristine = null;
        this._debounce = null;

        useHotkey("control+enter", () => this.onSave(),
                  { bypassEditableProtection: true });
        useHotkey("escape", () => this.onEscape(),
                  { bypassEditableProtection: true });

        onWillStart(async () => {
            await this.load();
            this.state.loading = false;
        });
        onMounted(() => {
            // Focus lands INSIDE the dialog, always. Without this the caret
            // stays on the row that opened it, Escape never reaches the editor,
            // and a screen reader keeps reading the list behind the modal.
            if (this.isNew && this.nameRef.el) {
                this.nameRef.el.focus();
            } else if (this.rootRef.el) {
                this.rootRef.el.focus();
            }
            this.syncExcel();
            this.refreshProof();
        });
        // A textarea's `value` attribute is not its content, so the Excel lane
        // is filled imperatively — and never while somebody is typing in it,
        // which would put their caret back at the start of the line.
        onPatched(() => this.syncExcel());
    }

    ic(name, size = 16) { return ic(name, size); }

    /**
     * The dialog's own keys.
     *
     * Registered on the element as well as through the hotkey service, because
     * this modal is hand-built markup rather than a framework Dialog: the
     * service only routes a key to the surface holding focus, and "the surface
     * holding focus" is exactly what a hand-built modal has to claim for
     * itself. Both paths stop here so Escape cannot also reach the journey
     * shell, where it means something else.
     */
    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            ev.preventDefault();
            this.onEscape();
            return;
        }
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
            ev.stopPropagation();
            ev.preventDefault();
            this.onSave();
        }
    }

    syncExcel() {
        const el = this.excelRef.el;
        if (el && el.value !== (this.state.excel || "")
                && document.activeElement !== el) {
            el.value = this.state.excel || "";
        }
    }

    get isNew() { return !this.props.ruleId; }

    async load() {
        if (this.isNew) {
            const res = await this.rpc("bp_component_get_new",
                                       [this.props.configId, this.props.newGroup || "earning"]);
            if (!res || !res.ok) {
                this.state.error = (res && res.reason)
                    || _t("This component could not be opened.");
                return;
            }
            this.apply(res);
            this.state.name = "";
            this.state.code = "";
            this._pristine = cloneRecipe(this.state.recipe);
            return;
        }
        const res = await this.rpc("bp_component_get", [this.props.ruleId]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("This component could not be opened.");
            return;
        }
        this.apply(res);
    }

    apply(res) {
        this.state.rule = res.rule;
        this.state.recipe = cloneRecipe(res.recipe);
        this.state.options = res.options;
        this.state.provenance = res.provenance;
        this.state.hasRecipe = !!res.has_recipe;
        this.state.source = (res.rule && res.rule.source) || "manual";
        this.state.name = (res.rule && res.rule.name) || "";
        this.state.code = (res.rule && res.rule.code) || "";
        this.state.excel = res.display_formula || "";
        this.state.lane = this.state.source === "manual" && res.display_formula
            ? "excel" : "guided";
        this._pristine = cloneRecipe(this.state.recipe);
        this._pristineExcel = this.state.excel;
    }

    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            return { ok: false, reason: reason || _t("The server could not be reached.") };
        }
    }

    // ==================================================================
    // Reading the sentence
    // ==================================================================
    get recipe() { return this.state.recipe || {}; }
    get amount() { return this.recipe.amount || {}; }
    get treatment() { return this.recipe.treatment || {}; }
    get options() { return this.state.options || {}; }

    get details() { return detailFor(this.amount.kind); }
    needs(key) { return this.details.includes(key); }

    get chips() { return treatmentChips(this.recipe); }

    get isDeduction() { return this.recipe.group === "deduction"; }
    get isBenefit() { return this.recipe.group === "benefit"; }
    get isEarning() { return this.recipe.group === "earning"; }

    get title() {
        if (this.isNew) return _t("Add a component");
        return this.state.name || this.state.code;
    }

    get codeProblem() {
        if (!this.isNew) return "";
        return codeProblem(this.state.code, this.props.takenCodes || []);
    }

    get dirty() {
        if (this.state.lane === "excel") {
            return this.state.excel !== this._pristineExcel;
        }
        return !sameRecipe(this.state.recipe, this._pristine)
            || (this.state.rule && this.state.name !== this.state.rule.name);
    }

    get canSave() {
        if (this.state.saving) return false;
        if (this.isNew && (this.codeProblem || !this.state.name.trim())) return false;
        return this.state.proof.state !== "bad";
    }

    /** The banner on the Guided lane when somebody typed the formula. */
    get showRestore() {
        return this.state.source === "manual" && this.state.hasRecipe
            && this.state.lane === "guided";
    }

    // ==================================================================
    // Changing the sentence
    // ==================================================================
    setRecipe(path, value) {
        const parts = path.split(".");
        let node = this.state.recipe;
        for (const part of parts.slice(0, -1)) {
            if (!node[part] || typeof node[part] !== "object") node[part] = {};
            node = node[part];
        }
        node[parts[parts.length - 1]] = value;
        this.queueProof();
    }

    onPick(path, ev) { this.setRecipe(path, ev.target.value); }

    onNumber(path, ev) {
        const value = num(ev.target.value);
        this.setRecipe(path, value === null ? 0 : value);
    }

    onGrade(index, ev) {
        const grades = (this.amount.grades || [0, 0, 0]).slice();
        grades[index] = num(ev.target.value) || 0;
        this.setRecipe("amount.grades", grades);
    }

    onMonth(ev) {
        this.setRecipe("amount.payout_month", Number(ev.target.value) || 1);
    }

    /**
     * A rate a configuration STORES beats a percentage somebody types.
     *
     * The Vietnam pack keeps 8% in a component called SIRATE, so the rule reads
     * "at the rate held in Social Insurance Rate" and changing that one number
     * changes every rule that uses it. Choosing the empty option goes back to a
     * plain percentage typed here.
     */
    onRate(ev) {
        const code = ev.target.value;
        if (code) {
            this.state.recipe.amount.rate_code = code;
            delete this.state.recipe.amount.percent;
        } else {
            delete this.state.recipe.amount.rate_code;
            this.state.recipe.amount.percent = 0;
        }
        this.queueProof();
    }

    onKind(ev) {
        const kind = ev.target.value;
        // Keep only what the new amount can use — a leftover percentage on a
        // fixed amount is a number nobody can see and the server would reject.
        this.state.recipe.amount = { kind };
        if (kind === "role") this.state.recipe.amount.grades = [0, 0, 0];
        if (kind === "hourly") this.state.recipe.amount.rate_pct = 150;
        if (kind === "annual_ratio") this.state.recipe.amount.payout_month = 1;
        if (kind === "sum_group") {
            this.state.recipe.amount.of = { group: "earning", cash: "cash" };
        }
        this.queueProof();
    }

    onName(ev) {
        this.state.name = ev.target.value;
        if (this.isNew && !this.state.codeTouched) {
            this.state.code = codeFromName(this.state.name);
        }
    }

    onCode(ev) {
        this.state.codeTouched = true;
        this.state.code = (ev.target.value || "").toUpperCase()
            .replace(/[^A-Z0-9]/g, "").slice(0, 12);
    }

    onExcel(ev) {
        this.state.excel = ev.target.value;
        this.queueProof();
    }

    onLane(lane) {
        this.state.lane = lane;
        this.refreshProof();
    }

    /** Insert a code at the caret — the Excel lane's helper chips. */
    insertCode(code) {
        const el = this.excelRef.el;
        if (!el) return;
        const start = el.selectionStart || 0;
        const end = el.selectionEnd || start;
        const text = this.state.excel || "";
        this.state.excel = text.slice(0, start) + code + text.slice(end);
        this.queueProof();
        requestAnimationFrame(() => {
            el.focus();
            el.setSelectionRange(start + code.length, start + code.length);
        });
    }

    // ==================================================================
    // The proof strip
    // ==================================================================
    queueProof() {
        if (this._debounce) clearTimeout(this._debounce);
        this.state.proof.state = "busy";
        this._debounce = setTimeout(() => this.refreshProof(), 300);
    }

    async refreshProof() {
        if (!this.state.recipe) return;
        this.state.proof.state = "busy";
        const args = [this.props.configId, this.props.ruleId || false];
        const kwargs = {
            recipe: this.state.lane === "guided" ? this.state.recipe : null,
            excel_codes: this.state.lane === "excel" ? this.state.excel : null,
            sample_id: this.props.sampleId || false,
            name: this.state.name || null,
            code: this.state.code || null,
            group: this.recipe.group || null,
        };
        let res;
        try {
            res = await this.orm.call("pb.blueprint.studio", "bp_recipe_preview",
                                      args, kwargs);
        } catch (e) {
            this.state.proof.state = "bad";
            this.state.proof.message = _t("The value could not be worked out.");
            return;
        }
        if (!res || !res.ok) {
            this.state.proof.state = "bad";
            this.state.proof.message = (res && res.reason) || _t("Something went wrong.");
            return;
        }
        this.state.proof.needs = res.needs || [];
        this.state.proof.formula = res.excel_codes || "";
        if (!res.valid) {
            this.state.proof.state = "bad";
            this.state.proof.message = res.message || _t("This calculation cannot be read.");
            return;
        }
        this.state.proof.state = "ok";
        this.state.proof.message = "";
        this.state.proof.value = res.value;
        if (this.state.lane === "guided" && res.excel_codes) {
            this.state.excel = res.excel_codes;
        }
    }

    get proofText() {
        const value = this.state.proof.value;
        if (value === null || value === undefined) {
            return _t("Add a sample employee on the right to see a value");
        }
        return Number(value).toLocaleString("en-US", { maximumFractionDigits: 2 });
    }

    get proofWho() {
        return this.props.sampleName
            ? _t("For %s", this.props.sampleName)
            : _t("For the sample employee");
    }

    get needsLine() {
        const needs = this.state.proof.needs || [];
        if (!needs.length) return "";
        // The server sends these as NAMES, not codes: "Paid working days" is
        // something a payroll manager can look for on the Inputs tab, and
        // "PAIDDAYS" is not.
        return needs.length === 1
            ? _t("This adds one number the payroll will be given: %s.", needs[0])
            : _t("This adds numbers the payroll will be given: %s.", needs.join(", "));
    }

    // ==================================================================
    // Saving, removing, restoring
    // ==================================================================
    async onSave() {
        if (!this.canSave) return;
        this.state.saving = true;
        const payload = {
            name: this.state.name,
            code: this.state.code,
            group: this.recipe.group,
            lane: this.state.lane,
            recipe: this.state.recipe,
            excel_codes: this.state.excel,
            on_payslip: this.state.rule ? this.state.rule.on_payslip : true,
            revision: this.props.revision,
        };
        const res = await this.rpc("bp_component_save",
                                   [this.props.configId, this.props.ruleId || false, payload]);
        this.state.saving = false;
        if (!res || !res.ok) {
            if (res && res.conflict) {
                this.state.error = res.reason;
                return;
            }
            this.notif.add((res && res.reason) || _t("That rule could not be saved."),
                           { type: "danger" });
            return;
        }
        this.props.onSaved(res);
    }

    async onRestoreGuided() {
        const res = await this.rpc("bp_component_restore_guided",
                                   [this.props.ruleId, this.props.revision]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The guided version could not be brought back."),
                           { type: "warning" });
            return;
        }
        this.notif.add(_t("Back to the guided rule. Your Excel is kept in the history."),
                       { type: "success" });
        this.props.onSaved(res);
    }

    onRemove() {
        this.props.onRemoved(this.props.ruleId, this.state.name || this.state.code);
    }

    onEscape() {
        if (this.state.confirmClose) { this.state.confirmClose = false; return; }
        this.tryClose();
    }

    tryClose() {
        if (this.dirty) {
            this.state.confirmClose = true;
            return;
        }
        this.props.onClose();
    }

    discardAndClose() {
        this.state.confirmClose = false;
        this.props.onClose();
    }
}
