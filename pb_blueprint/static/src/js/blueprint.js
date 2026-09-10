/** @odoo-module **/

import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { router } from "@web/core/browser/router";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip } from "@pb_hub/js/hub_nav";

import {
    STEPS, STEP_META, nextStep, prevStep, stepNumber, isDone, continueLabel,
    freshSituations, freshToken, firstOfNextMonth, savedAgo, toggle,
} from "./blueprint_steps";
import { PayPreview } from "./pay_preview";
import { SampleInputsDialog } from "./sample_inputs_dialog";
import { StepStart } from "./step_start";
import { StepThin } from "./step_thin";
import { StepFinish } from "./step_finish";

/**
 * "New configuration" — the guided journey.
 *
 * A full page, not a pop-up (BP-R1). It owns the screen for as long as setting
 * up a payroll takes, it can be left at any point and resumed from the
 * configurations screen, and it never leaves a half-created configuration
 * behind: the draft is made in one server transaction, keyed by a setup token
 * so that a double click, a retry or a refresh all land on the SAME draft.
 *
 * Three columns at desk width: the journey rail, the step, and the pay panel
 * that shows one person's take-home pay being built. Below 1200px the panel
 * becomes a bottom bar; below 900px the rail becomes a horizontal stepper.
 * Nothing ever scrolls sideways.
 */
export class PbBlueprint extends Component {
    static template = "pb_blueprint.Root";
    static components = { PayPreview, SampleInputsDialog, StepStart, StepThin, StepFinish, HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        // GR8 — a client action with no control panel has to name itself, or
        // the breadcrumb says "Odoo" (which it may never say) or nothing.
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("New configuration"));
        }

        const params = this._arrival();
        this.token = freshToken();

        this.state = useState({
            // --- where we are -------------------------------------------
            step: "start",
            loading: true,
            fatal: "",                 // a full-panel refusal, with a way out
            // --- the draft ----------------------------------------------
            configId: params.config_id || null,
            config: null,
            blueprint: null,
            counts: {},
            components: [],
            starters: null,
            countries: [],
            company: "",
            // --- the start form -----------------------------------------
            form: {
                name: "",
                country_code: "VN",
                cycle_type: "regular",
                effective_from: firstOfNextMonth(),
                template_key: "",
            },
            situations: freshSituations(),
            nameError: "",
            startError: "",
            progress: [],
            // --- saving -------------------------------------------------
            busy: false,
            saving: false,
            saveError: "",
            savedAt: null,
            tick: 0,                   // forces the "saved N min ago" to refresh
            // --- the pay panel ------------------------------------------
            samples: [],
            sampleId: null,
            preview: null,
            payStatus: "waiting",
            payReason: "",
            // --- overlays -----------------------------------------------
            inputsOpen: false,
            inputsRows: [],
            inputsBusy: false,
            confirmStarter: null,      // the starter key we are about to swap to
            confirmDiscard: false,
            kebabOpen: false,
        });

        this.cycles = [
            { value: "regular", label: _t("Regular payroll") },
            { value: "mid_cycle", label: _t("Mid-month advance") },
            { value: "end_cycle", label: _t("End-month payroll") },
            { value: "full_final", label: _t("Full and final") },
        ];

        this._stepTimer = null;
        this._agoTimer = setInterval(() => { this.state.tick++; }, 30000);

        // ⌘/Ctrl+Enter always continues, wherever the caret is. Plain Enter is
        // handled on the form itself so it never steals a newline.
        useHotkey("control+enter", () => this.onContinue(), { bypassEditableProtection: true });
        useHotkey("escape", () => this.onEscape(), { bypassEditableProtection: true });

        onWillStart(async () => {
            if (this.state.configId) {
                await this.resume(this.state.configId);
            } else {
                await this.loadStarters(this.state.form.country_code);
            }
            this.state.loading = false;
        });

        onWillUnmount(() => {
            if (this._stepTimer) clearTimeout(this._stepTimer);
            if (this._agoTimer) clearInterval(this._agoTimer);
        });
    }

    // ==================================================================
    // Arrival + resume
    // ==================================================================
    /** Every arrival key is read from `params` OR `context` — both are used. */
    _arrival() {
        const a = this.props.action || {};
        const p = a.params || {};
        const c = a.context || {};
        return {
            config_id: Number(p.config_id || c.config_id || 0) || null,
        };
    }

    /**
     * Put the draft in the URL so a browser refresh comes back to it.
     *
     * `router.pushState` (the module, not a service — Odoo 19 moved it) writes
     * `?config_id=N` next to the action, and the action manager hands that
     * straight back as `action.params` on the next load, which is exactly the
     * key `_arrival()` already reads. No extra plumbing, no second source of
     * truth for "which draft am I on".
     */
    _rememberInUrl(configId) {
        try {
            router.pushState({ config_id: configId }, { replace: true });
        } catch (e) {
            // A URL that did not update is a worse refresh, not a broken page.
            console.warn("pb_blueprint: could not record the draft in the URL", e);
        }
    }

    async resume(configId) {
        const res = await this.rpc("bp_load", [configId]);
        if (!res || !res.ok) {
            this.state.fatal = (res && res.reason) || _t("This setup could not be opened.");
            return;
        }
        this.applyLoad(res);
        // A finished setup has nothing left to guide — go straight to the grid
        // rather than showing six steps that are all already behind you.
        if (res.blueprint.state === "finished") {
            await this.openGrid(configId, { silent: true });
            return;
        }
        this._rememberInUrl(configId);
        await this.refreshPreview();
    }

    applyLoad(res) {
        this.state.configId = res.config.id;
        this.state.config = res.config;
        this.state.blueprint = res.blueprint;
        this.state.counts = res.counts;
        this.state.components = res.components;
        this.state.samples = res.samples;
        this.state.starters = res.starters;
        this.state.countries = (res.starters && res.starters.countries) || [];
        this.state.company = (res.starters && res.starters.company) || res.config.company;
        this.state.step = res.blueprint.step || "rules";
        this.state.form = {
            name: res.config.name,
            country_code: res.config.country_code,
            cycle_type: res.config.cycle_type,
            effective_from: res.blueprint.effective_from || "",
            template_key: res.blueprint.template_key || "blank",
        };
        this.state.situations = {
            audiences: (res.blueprint.situations && res.blueprint.situations.audiences) || [],
            reallife: (res.blueprint.situations && res.blueprint.situations.reallife) || [],
        };
        if (!this.state.sampleId && res.samples.length) {
            this.state.sampleId = res.samples[0].id;
        }
        this.state.savedAt = Date.now();
    }

    async loadStarters(country) {
        const res = await this.rpc("bp_templates", [country]);
        if (!res || !res.ok) {
            this.state.fatal = _t("The list of starting points could not be loaded. Reload the page to try again.");
            return;
        }
        this.state.starters = res;
        this.state.countries = res.countries;
        this.state.company = res.company || this.state.company;
        const chosen = res.starters.find((s) => s.default);
        this.state.form.template_key = chosen ? chosen.key : "blank";
    }

    /**
     * One place where every server call goes, so a dropped connection is a
     * sentence with a retry and never a blank page (W40: never swallow).
     */
    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(
                reason || _t("The server could not be reached. Check your connection and try again."),
                { type: "danger", title: _t("Something did not go through") });
            return { ok: false, reason: reason, network: true };
        }
    }

    // ==================================================================
    // Small readers the template uses
    // ==================================================================
    ic(name, size = 16) { return ic(name, size); }

    get STEPS() { return STEPS; }
    get META() { return STEP_META; }
    get created() { return !!this.state.configId; }
    get stepNo() { return stepNumber(this.state.step); }
    get total() { return STEPS.length; }
    get continueLabel() { return continueLabel(this.state.step); }

    railState(step) {
        if (step === this.state.step) return "on";
        if (this.created && isDone(step, this.state.step)) return "done";
        return "idle";
    }

    railDisabled(step) { return !this.created && step !== "start"; }

    railTitle(step) {
        return this.railDisabled(step)
            ? _t("Create the configuration first")
            : STEP_META[step].label;
    }

    /**
     * The company the draft belongs to.
     *
     * Read from the SERVER (`env.company`), never from a client-side company
     * service: the draft, the starter list and every search are scoped to one
     * company, and the chip has to name the same one the server used or it is
     * lying about where the configuration is being filed (BP-R11).
     */
    get companyName() {
        if (this.state.config && this.state.config.company) return this.state.config.company;
        return this.state.company || "";
    }

    /** The status pill: what the server knows about this draft, right now. */
    get statusPill() {
        if (this.state.saveError) {
            return { cls: "err", text: _t("Could not save — retry"), retry: true };
        }
        if (this.state.saving) return { cls: "busy", text: _t("Saving…") };
        if (!this.created) return { cls: "wait", text: _t("Not saved yet") };
        const ago = savedAgo(Date.now() - (this.state.savedAt || Date.now()));
        // `tick` is read so the label re-renders as time passes.
        void this.state.tick;
        if (this.state.blueprint && this.state.blueprint.state === "finished") {
            return { cls: "ok", text: _t("Setup complete") };
        }
        return { cls: "ok", text: _t("Draft · %s", ago) };
    }

    get footerLine() {
        if (!this.created) {
            return _t("Step 1 of %s", this.total);
        }
        const bits = [_t("Step %(n)s of %(total)s", { n: this.stepNo, total: this.total })];
        const tname = this.state.blueprint && this.state.blueprint.template_name;
        if (tname) bits.push(tname);
        const n = (this.state.counts && this.state.counts.components) || 0;
        bits.push(n === 1 ? _t("1 component") : _t("%s components", n));
        return bits.join(" · ");
    }

    get backChip() {
        return { label: _t("Payroll configurations"), tag: "pb_formula_studio", xmlid: "",
                 lens: "", lensKey: "pb_lens", context: { open_switcher: true } };
    }

    // ==================================================================
    // The Start form
    // ==================================================================
    async onSet(field, value) {
        this.state.form[field] = value;
        if (field === "name" && value.trim()) this.state.nameError = "";
        if (field === "country_code" && !this.created) {
            await this.loadStarters(value);
        }
        if (this.created && ["name", "cycle_type", "effective_from"].includes(field)) {
            this.queueSave();
        }
    }

    onPickStarter(key) {
        if (!this.created) {
            this.state.form.template_key = key;
            return;
        }
        if (key === this.state.blueprint.template_key) return;
        // Replacing the components of a draft destroys hand-written work — the
        // dialog says exactly how much, in numbers, before anything happens.
        this.state.confirmStarter = key;
    }

    onToggleAudience(key) {
        this.state.situations.audiences = toggle(this.state.situations.audiences, key);
        if (this.created) this.queueSave();
    }

    onToggleReallife(key) {
        this.state.situations.reallife = toggle(this.state.situations.reallife, key);
        if (this.created) this.queueSave();
    }

    /** "Change" beside a locked field — go back to choosing. */
    onUnlock(what) {
        if (what === "starter") {
            this.notif.add(
                _t("Pick a different starting point below. You will be asked to confirm before anything is replaced."),
                { type: "info" });
        } else {
            this.notif.add(
                _t("The country cannot be changed once components exist. Discard this draft and start again to change it."),
                { type: "warning" });
        }
    }

    // ==================================================================
    // Creating the draft
    // ==================================================================
    async createDraft() {
        const name = (this.state.form.name || "").trim();
        if (!name) {
            // The message lives UNDER THE FIELD and the caret moves there. A
            // toast would tell you what is wrong somewhere you are not looking
            // (design bar: no toast-only errors). StepStart focuses the input
            // when it sees this change.
            this.state.nameError = _t("Give the configuration a name so you can find it again.");
            return false;
        }
        if (this.state.busy) return false;

        this.state.busy = true;
        this.state.startError = "";
        this.state.progress = [
            { label: _t("Creating the draft"), done: false },
            { label: _t("Adding the starter's components"), done: false },
            { label: _t("Preparing a sample employee"), done: false },
        ];
        const excel = this.state.form.template_key === "excel";
        try {
            const res = await this.rpc("bp_start", [{
                name,
                country_code: this.state.form.country_code,
                cycle_type: this.state.form.cycle_type,
                effective_from: this.state.form.effective_from || false,
                template_key: this.state.form.template_key || "blank",
                situations: {
                    audiences: this.state.situations.audiences,
                    reallife: this.state.situations.reallife,
                },
            }, this.token]);
            if (!res || !res.ok) {
                this.state.progress = [];
                this.state.startError = (res && res.reason)
                    || _t("The configuration could not be created. Nothing was saved.");
                return false;
            }
            // The three ticks land 150ms apart: the work is already done, and
            // the stagger is what makes it legible rather than a flash.
            for (let i = 0; i < 3; i++) {
                await new Promise((r) => setTimeout(r, 150));
                this.state.progress[i].done = true;
            }
            const load = await this.rpc("bp_load", [res.config_id]);
            if (load && load.ok) this.applyLoad(load);
            this.state.sampleId = res.sample_id || this.state.sampleId;
            this._rememberInUrl(res.config_id);
            this.state.progress = [];
            await this.refreshPreview();
            if (excel) {
                this.openExcel();
            }
            return true;
        } finally {
            this.state.busy = false;
        }
    }

    // ==================================================================
    // Navigation
    // ==================================================================
    async goto(step) {
        if (this.railDisabled(step)) return;
        this.state.step = step;
        this.rememberStep();
    }

    /** Persist the step, debounced — a refresh lands where you left off. */
    rememberStep() {
        if (!this.created) return;
        if (this._stepTimer) clearTimeout(this._stepTimer);
        this._stepTimer = setTimeout(async () => {
            await this.rpc("bp_close", [this.state.configId, this.state.step]);
        }, 400);
    }

    async onContinue() {
        if (this.state.busy) return;
        if (!this.created) {
            await this.createDraft();
            return;
        }
        if (this.state.step === "finish") {
            await this.finish();
            return;
        }
        this.state.step = nextStep(this.state.step);
        this.rememberStep();
    }

    onBack() {
        if (!this.created || this.state.step === "start") return;
        this.state.step = prevStep(this.state.step);
        this.rememberStep();
    }

    /**
     * Enter continues — but never while somebody is typing.
     *
     * A field where Enter means "next screen" is a field you cannot correct a
     * typo in without losing the page, so every text-like control keeps its own
     * Enter. ⌘/Ctrl+Enter is the escape hatch that works everywhere.
     */
    onKeydown(ev) {
        if (ev.key !== "Enter" || ev.metaKey || ev.ctrlKey || ev.altKey) return;
        const el = ev.target;
        const tag = (el && el.tagName) || "";
        const typing = tag === "TEXTAREA"
            || (tag === "INPUT" && !["checkbox", "radio", "button", "submit"].includes(el.type))
            || tag === "SELECT";
        if (typing) return;
        ev.preventDefault();
        this.onContinue();
    }

    onEscape() {
        if (this.state.inputsOpen) { this.state.inputsOpen = false; return; }
        if (this.state.confirmStarter) { this.state.confirmStarter = null; return; }
        if (this.state.confirmDiscard) { this.state.confirmDiscard = false; return; }
        if (this.state.kebabOpen) { this.state.kebabOpen = false; }
    }

    // ==================================================================
    // Saving
    // ==================================================================
    queueSave() {
        if (this._saveTimer) clearTimeout(this._saveTimer);
        this._saveTimer = setTimeout(() => this.save(), 500);
    }

    async save() {
        if (!this.created) return;
        this.state.saving = true;
        this.state.saveError = "";
        const res = await this.rpc("bp_save", [this.state.configId, {
            name: this.state.form.name,
            cycle_type: this.state.form.cycle_type,
            effective_from: this.state.form.effective_from || false,
            situations: {
                audiences: this.state.situations.audiences,
                reallife: this.state.situations.reallife,
            },
            step: this.state.step,
        }, this.state.blueprint.revision]);
        this.state.saving = false;
        if (!res || !res.ok) {
            this.state.saveError = (res && res.reason) || _t("Could not save.");
            return;
        }
        this.state.blueprint.revision = res.revision;
        this.state.config.name = res.name;
        this.state.config.code = res.code;
        this.state.config.cycle_label = res.cycle_label;
        this.state.savedAt = Date.now();
    }

    async retrySave() { await this.save(); }

    // ==================================================================
    // The pay panel
    // ==================================================================
    async refreshPreview() {
        if (!this.created) { this.state.payStatus = "waiting"; return; }
        if (!this.state.samples.length) {
            this.state.payStatus = "empty";
            this.state.preview = null;
            return;
        }
        this.state.payStatus = "busy";
        const res = await this.rpc("bp_preview",
            [this.state.configId, this.state.sampleId || false]);
        if (!res || !res.ok) {
            this.state.payStatus = res && res.empty ? "empty" : "error";
            this.state.payReason = (res && res.reason) || _t("The numbers could not be worked out.");
            return;
        }
        this.state.preview = res;
        this.state.sampleId = res.sample_id;
        this.state.payStatus = "live";
        this.state.payReason = "";
    }

    async onPickSample(id) {
        this.state.sampleId = id;
        await this.refreshPreview();
    }

    async onAddSample() {
        const res = await this.rpc("bp_add_sample", [this.state.configId]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The sample could not be added."),
                           { type: "warning" });
            return;
        }
        this.state.samples = res.samples;
        this.state.sampleId = res.sample_id;
        this.state.counts.samples = res.samples.length;
        await this.refreshPreview();
    }

    async onAdjust() {
        const res = await this.rpc("bp_sample_inputs",
            [this.state.configId, this.state.sampleId]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("Those inputs could not be opened."),
                           { type: "warning" });
            return;
        }
        if (!res.rows.length) {
            this.notif.add(
                _t("This configuration has no inputs to adjust yet. Add an input component first."),
                { type: "info" });
            return;
        }
        this.state.inputsRows = res.rows;
        this.state.inputsOpen = true;
    }

    async onSaveInputs(values) {
        this.state.inputsBusy = true;
        const res = await this.rpc("bp_save_sample_inputs",
            [this.state.configId, this.state.sampleId, values]);
        this.state.inputsBusy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("Those inputs could not be saved."),
                           { type: "danger" });
            return;
        }
        this.state.samples = res.samples;
        this.state.inputsOpen = false;
        await this.refreshPreview();
    }

    // ==================================================================
    // Replacing the starter
    // ==================================================================
    get confirmStarterName() {
        const key = this.state.confirmStarter;
        const list = (this.state.starters && this.state.starters.starters) || [];
        const row = list.find((s) => s.key === key);
        return row ? row.name : key;
    }

    get confirmStarterText() {
        const n = (this.state.counts && this.state.counts.components) || 0;
        return _t(
            "This removes all %(n)s components and formulas of this draft and adds the %(starter)s ones. Anything you edited by hand is lost.",
            { n, starter: this.confirmStarterName });
    }

    async doRestart() {
        const key = this.state.confirmStarter;
        this.state.confirmStarter = null;
        this.state.busy = true;
        const res = await this.rpc("bp_restart", [this.state.configId, key]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The components could not be replaced."),
                           { type: "danger", sticky: true });
            return;
        }
        const load = await this.rpc("bp_load", [this.state.configId]);
        if (load && load.ok) this.applyLoad(load);
        this.state.sampleId = this.state.samples.length ? this.state.samples[0].id : null;
        await this.refreshPreview();
        this.notif.add(
            res.rule_count
                ? _t("%s components are ready.", res.rule_count)
                : _t("The draft is empty and ready for your own components."),
            { type: "success" });
        if (key === "excel") this.openExcel();
    }

    // ==================================================================
    // Doors out
    // ==================================================================
    /** The Excel workbook review — and the way back into this journey. */
    openExcel() {
        const cid = this.state.configId;
        if (!cid) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Import from Excel"),
            res_model: "hr.formula.multisheet.import.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: { default_config_id: cid, pb_blueprint_return: true },
        }, {
            onClose: async () => {
                // The review may have been cancelled — re-read rather than
                // assume, so the component count on screen is never a guess.
                const load = await this.rpc("bp_load", [cid]);
                if (load && load.ok) {
                    this.applyLoad(load);
                    this.state.sampleId = this.state.samples.length
                        ? this.state.samples[0].id : null;
                    await this.refreshPreview();
                }
            },
        });
    }

    async openGrid(configId, opts = {}) {
        const cid = configId || this.state.configId;
        if (!cid) return;
        const res = await this.rpc("bp_studio_action", [cid]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The components grid could not be opened."),
                           { type: "warning" });
            return;
        }
        if (!opts.silent) await this.rpc("bp_close", [cid, this.state.step]);
        this.action.doAction(res.action, { clearBreadcrumbs: true });
    }

    /** Save & close — or just Close, when nothing has been created yet. */
    async saveAndClose() {
        if (!this.created) {
            this.backToConfigs();
            return;
        }
        await this.save();
        this.backToConfigs();
    }

    backToConfigs() {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "pb_formula_studio",
            target: "current",
            params: { open_switcher: true },
            context: { open_switcher: true },
        }, { clearBreadcrumbs: true });
    }

    // ==================================================================
    // Finish and discard
    // ==================================================================
    async finish() {
        this.state.busy = true;
        const res = await this.rpc("bp_finish", [this.state.configId]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.state.saveError = "";
            this.notif.add((res && res.reason) || _t("The setup could not be finished."),
                           { type: "warning", sticky: true });
            return;
        }
        this.notif.add(_t("Setup complete. Opening the configuration."), { type: "success" });
        await this.openGrid(this.state.configId, { silent: true });
    }

    async doDiscard() {
        this.state.confirmDiscard = false;
        const res = await this.rpc("bp_discard", [this.state.configId]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("This draft could not be discarded."),
                           { type: "danger", sticky: true });
            return;
        }
        this.notif.add(_t("The draft was discarded. Nothing was kept."), { type: "success" });
        this.backToConfigs();
    }

    toggleKebab() { this.state.kebabOpen = !this.state.kebabOpen; }
}

registry.category("actions").add("pb_blueprint", PbBlueprint);
