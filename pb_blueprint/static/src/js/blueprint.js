/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { router } from "@web/core/browser/router";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip } from "@pb_hub/js/hub_nav";

import {
    STEPS, STEP_META, nextStep, stepNumber, isDone,
    continueTarget, backTarget,
    freshSituations, freshToken, firstOfNextMonth, savedAgo, toggle,
} from "./blueprint_steps";
import { discardText } from "./finish_text";
import { PayPreview } from "./pay_preview";
import { SampleInputsDialog } from "./sample_inputs_dialog";
import { StepStart } from "./step_start";
import { StepRules } from "./step_rules";
import { StepConnect } from "./step_connect";
import { StepOutputs } from "./step_outputs";
import { StepTest } from "./step_test";
import { StepFinish } from "./step_finish";
import { Scoreboard } from "./scoreboard";
import { SettingsCards, StepSaved, settingsGroupFor, settingLabel } from "./edit_cards";

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
    static components = { PayPreview, Scoreboard, SampleInputsDialog, StepStart,
                          StepRules, StepConnect, StepOutputs, StepTest,
                          StepFinish, StepSaved, SettingsCards, HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        // GR8 — a client action with no control panel has to name itself, or
        // the breadcrumb says "Odoo" (which it may never say) or nothing.
        const arrivedEditing = String(
            (this.props.action || {}).params?.mode
            || (this.props.action || {}).context?.mode || "") === "edit";
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(
                arrivedEditing ? _t("Edit configuration") : _t("New configuration"));
        }

        // Read by the `onClose` of every dialog we open: a finished workbook
        // import RETURNS an action that remounts this journey, so the callback
        // that follows it would otherwise write state into a dead component.
        this._alive = true;

        const params = this._arrival();
        this.arrival = params;
        this.token = freshToken();

        this.state = useState({
            // --- where we are -------------------------------------------
            step: "start",
            loading: true,
            fatal: "",                 // a full-panel refusal, with a way out
            // A refusal that has a next step rather than only a reason: a
            // configuration the journey has never seen can be OPENED for
            // editing, and saying so beats a dead end (SCHEMECTX P3).
            fatalAdopt: false,
            // --- create or edit (SCHEMECTX P3) ---------------------------
            // `create` builds a new configuration through six steps. `edit`
            // opens one that already exists — often a live one — so that the
            // studio's Settings tab has somewhere better to go than a panel.
            mode: params.mode === "edit" ? "edit" : "create",
            locks: {},
            builtFrom: "",
            schemeState: "",
            schemeStateLabel: "",
            lockReason: "",
            countryLockReason: "",
            // The settings the old panel used to own, now cards on three of
            // the steps. Loaded once per draft and written card by card.
            settings: null,
            settingsDraft: {},
            settingsMeta: {},
            settingsBusy: false,
            settingsError: "",
            // Every setting that moved in this sitting, for the last page.
            changes: [],
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
            // Whether this scenario's expected numbers are already agreed, so
            // the dialog can say what changing an input will cost.
            inputsConfirmed: false,
            inputsRows: [],
            inputsBusy: false,
            confirmStarter: null,      // the starter key we are about to swap to
            confirmDiscard: false,
            kebabOpen: false,
            rulesTab: "components",
            // --- step 3, Connect ----------------------------------------
            // Which card to ring because a studio just sent us back to it, and
            // a tick that makes the step re-read its counts rather than trust
            // the ones it painted before the person left.
            connectTask: params.task || "",
            connectTick: 0,
            // Bumped every time the pay panel gets a fresh answer, so the
            // component list refreshes the value it shows for each row.
            payTick: 0,
            // --- steps 4 and 5, Outputs and Test ------------------------
            // The Test step owns the checks; the shell keeps the last answer
            // so the pay panel can become the scoreboard beside it, and so
            // pressing Run from the panel reaches the step that owns it.
            tests: null,
            testsRunning: false,
            runSignal: 0,
            // A component the coverage line asked to look at, opened on the
            // Outputs step the moment we land there.
            inspectRule: 0,
            // --- step 6, Finish -----------------------------------------
            // A component a "Go" link on the Finish step asked to open, on the
            // Pay rules step, in its own editor. The tick is what opens it, so
            // asking for the same component twice still works and closing the
            // editor is final.
            openRule: 0,
            openTick: 0,
            // The footer's primary button and the step's own button are the
            // SAME action, so the footer asks the step to run it rather than
            // keeping a second copy of the gate's refusals (the Test step's
            // `runSignal` idiom).
            finishSignal: 0,
            finishTick: 0,
            // What discarding would destroy, read from the server before the
            // dialog opens so it names the configuration and counts what goes.
            discard: null,
        });

        this.cycles = [
            { value: "regular", label: _t("Regular payroll") },
            { value: "mid_cycle", label: _t("Mid-month advance") },
            { value: "end_cycle", label: _t("End-month payroll") },
            { value: "full_final", label: _t("Full and final") },
        ];

        this._stepTimer = null;
        this._saveTimer = null;
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

        // B4 — say it again once we are on screen.
        //
        // `_rememberInUrl` runs inside `onWillStart`, and the action manager
        // writes its OWN route state when the action mounts, a moment later —
        // which wipes `?config_id=N` for any door that carried the draft in the
        // CONTEXT rather than in `params`. That is exactly the shape of the
        // return door from the two studios, so a refresh after coming back
        // landed on an empty journey. Re-asserting after mount costs one call
        // and makes every door's refresh behave the same (BP38).
        onMounted(() => {
            if (this.state.configId) {
                this._rememberInUrl(this.state.configId);
            }
        });

        // Every pending timer dies with the component, or a fired callback sets
        // state on something that is no longer mounted (W100).
        onWillUnmount(() => {
            this._alive = false;
            if (this._stepTimer) clearTimeout(this._stepTimer);
            if (this._saveTimer) clearTimeout(this._saveTimer);
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
            // B4 — a studio sending somebody back says WHICH step they left
            // from and WHICH card they were working on, so the return lands on
            // the Connect step with that card ringed rather than wherever the
            // draft happened to be saved.
            step: String(p.step || c.step || ""),
            task: String(p.task || c.task || ""),
            // SCHEMECTX P3 — "edit" means the studio's Settings tab sent us
            // here to change a configuration that already exists. It rides in
            // the URL as well, so a refresh stays in edit mode (BP14/BP38).
            mode: String(p.mode || c.mode || ""),
        };
    }

    /**
     * Put the draft in the URL so a browser refresh comes back to it.
     *
     * `router.pushState` (the module, not a service — Odoo 19 moved it) MERGES
     * into the current route, so `?config_id=N` lands next to the action and
     * the action manager hands it straight back as `action.params` on the next
     * load — exactly the key `_arrival()` already reads.
     *
     * Deliberately NOT `{ replace: true }`: that option does not mean "replace
     * the history entry", it means REPLACE THE WHOLE STATE, and
     * `computeNextState` then keeps only the locked keys — dropping `action`.
     * The URL became `/bizapp?config_id=578` with no action on it, and a
     * refresh landed on an empty app instead of the journey.
     * (`web/static/src/core/browser/router.js:45-52, 345`.)
     */
    _rememberInUrl(configId) {
        try {
            // `mode` travels with the draft: a refresh in edit mode has to come
            // back in edit mode, or somebody who was changing an Active
            // configuration's journal lands in a six-step build of it.
            const state = { config_id: configId };
            if (this.state.mode === "edit") { state.mode = "edit"; }
            router.pushState(state);
        } catch (e) {
            // A URL that did not update is a worse refresh, not a broken page.
            console.warn("pb_blueprint: could not record the draft in the URL", e);
        }
    }

    async resume(configId) {
        let res = await this.rpc("bp_load", [configId]);
        // A configuration the journey has never seen. Opening it for editing is
        // one explicit write, never a side effect of a read (BP53): it happens
        // here only because the person ASKED for edit mode, and otherwise the
        // refusal offers the button that asks for it.
        if (res && !res.ok && res.needs_adopt) {
            if (this.arrival && this.arrival.mode === "edit") {
                const adopted = await this.rpc("bp_adopt", [configId]);
                if (adopted && adopted.ok) {
                    res = await this.rpc("bp_load", [configId]);
                }
            } else {
                this.state.fatalAdopt = true;
                this.state.fatal = res.reason;
                return;
            }
        }
        if (!res || !res.ok) {
            this.state.fatal = (res && res.reason) || _t("This setup could not be opened.");
            return;
        }
        this.applyLoad(res);
        // A studio that sent somebody back names the step it sent them back to,
        // and that beats the step the draft was saved on: the person pressed a
        // chip that said "New configuration", and landing them anywhere but
        // where they left would be the chip lying (B4 return door).
        if (this.arrival && STEPS.includes(this.arrival.step)) {
            this.state.step = this.arrival.step;
            this.rememberStep();
        }
        // Edit mode opens on Start — the page that says what this
        // configuration IS — rather than on whichever step a build stopped at.
        // Somebody arriving from the Settings tab is asking "what is this and
        // what can I change", and the identity card is the answer.
        if (this.state.mode === "edit") {
            this.state.step = (this.arrival && STEPS.includes(this.arrival.step))
                ? this.arrival.step : "start";
            this._rememberInUrl(configId);
            await this.loadSettings();
            await this.refreshPreview();
            return;
        }
        // A finished setup opens on its LAST page, read only (B6).
        //
        // B1 sent it straight to the components grid, which was right while the
        // Finish step was a placeholder and wrong the moment it became the page
        // that says what was built: somebody who comes back to a completed setup
        // is asking "what did we decide", and answering by silently opening a
        // different screen loses both the answer and the way back into the
        // steps. The page offers the two things left to do — open the
        // configuration, or revisit the setup.
        if (res.blueprint.state === "finished") {
            this.state.step = "finish";
        }
        this._rememberInUrl(configId);
        await this.loadSettings();
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
        // SCHEMECTX P3 — the SERVER decides which mode this is, never the URL:
        // a stale `?mode=edit` on a half-built draft must open the build.
        this.state.mode = res.mode === "edit" ? "edit" : "create";
        this.state.locks = res.locks || {};
        this.state.builtFrom = res.built_from || "";
        this.state.schemeState = res.scheme_state || "";
        this.state.schemeStateLabel = res.scheme_state_label || "";
        this.state.lockReason = res.lock_reason || "";
        this.state.countryLockReason = res.country_lock_reason || "";
        this.state.step = res.blueprint.step || "rules";
        this.state.rulesTab = (res.blueprint.ui && res.blueprint.ui.rules_tab)
            || "components";
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
        // Deliberately NOT `sampleId = res.samples[0].id`. The SERVER decides
        // which sample the panel opens on — it is the only side that knows
        // which of them is actually paid, and a rule pack's suite leads with
        // its boundary cases (the Vietnam pack's first is "Zero income", which
        // opened the hero on a column of zeroes). Sending no sample asks the
        // server to choose; `refreshPreview` then stores what it chose.
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
    /** Where the primary button goes — a tab of this step, or the next step. */
    get continueTarget() {
        return continueTarget(this.state.step, this.state.rulesTab);
    }

    get continueLabel() {
        if (this.editing && this.state.step === "finish") { return _t("Save changes"); }
        return this.continueTarget.label;
    }

    // ==================================================================
    // Edit mode (SCHEMECTX P3)
    // ==================================================================
    get editing() { return this.state.mode === "edit"; }

    /** The page's name, in the tab, the breadcrumb and the rail. */
    get journeyTitle() {
        return this.editing ? _t("Edit configuration") : _t("New configuration");
    }

    /** Whether the pay rules of this configuration may still be changed. */
    get payLogicLocked() { return !!(this.state.locks || {}).pay_logic; }

    /** Whether the country is settled for good, because money has moved. */
    get countryLocked() { return !!(this.state.locks || {}).country; }

    /** The scheme's own state, as a chip beside the rail's EDITING eyebrow. */
    get stateChip() {
        if (!this.editing || !this.state.schemeStateLabel) { return null; }
        const live = ["active", "validated"].includes(this.state.schemeState);
        return { text: this.state.schemeStateLabel, cls: live ? "is-live" : "is-draft" };
    }

    /**
     * "Save changes" — close the sitting and go back where we came from.
     *
     * Every setting was written as its card was committed, so this generates
     * nothing, activates nothing, and leaves an Active configuration Active.
     */
    async saveChanges() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        const res = await this.rpc("bp_finish", [this.state.configId]);
        this.state.busy = false;
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("The changes could not be closed off."),
                           { type: "warning", sticky: true });
            return;
        }
        this.notif.add(
            this.state.changes.length
                ? _t("Saved. Your changes are on the configuration.")
                : _t("Nothing had changed, so nothing was saved."),
            { type: "success" });
        if (res.action) {
            this.action.doAction(res.action, { clearBreadcrumbs: true });
            return;
        }
        await this.openGrid(this.state.configId, { silent: true });
    }

    railState(step) {
        if (step === this.state.step) return "on";
        if (this.created && isDone(step, this.state.step)) return "done";
        return "idle";
    }

    railDisabled(step) { return !this.created && step !== "start"; }

    /**
     * The workbook was chosen as the starting point and nothing has come in yet.
     *
     * The workbook route seeds NOTHING on purpose — the workbook is the
     * starter — so "chose Excel" and "imported Excel" look identical on the
     * draft record apart from this: a configuration with no components. There
     * is deliberately no server flag; a count that is already in every
     * `bp_load` payload cannot drift out of step with the components it counts.
     *
     * Read from the SAVED starter, not the form: a card click that has not been
     * confirmed yet must not make the screen promise a workbook.
     */
    get needsWorkbook() {
        if (!this.created || !this.state.blueprint) return false;
        if (this.state.blueprint.template_key !== "excel") return false;
        return !((this.state.counts && this.state.counts.components) || 0);
    }

    /**
     * The rail's second line — the step's promise, or what it now KNOWS.
     *
     * Once the checks have been run the Test row stops saying "try the days
     * that aren't ordinary" and starts reporting the score, so the journey
     * answers "how much of this is proven" from two steps away (B5's own "with
     * one more hour"). Nothing new is fetched for it: the shell already holds
     * the Test step's last answer, because the pay panel becomes the scoreboard
     * from the same object.
     */
    railHint(step) {
        if (step === "test" && this.state.tests) {
            const tests = this.state.tests;
            const tally = tests.tally || {};
            const total = Number(tests.checks || 0);
            const ever = tests.evidence && tests.evidence.ever_run;
            if (ever && total) {
                if (tally.attention) {
                    return tally.attention === 1
                        ? _t("1 check needs attention")
                        : _t("%s checks need attention", tally.attention);
                }
                return _t("%(passed)s of %(total)s checks passed",
                          { passed: Number(tally.passed || 0), total });
            }
        }
        return STEP_META[step].hint;
    }

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
        // In edit mode the way back is the screen we came FROM — this
        // configuration in the components grid, not a list of all of them. A
        // chip that lands somewhere else is a chip that lied (BP-R8).
        if (this.editing && this.state.configId) {
            return { label: this.state.config && this.state.config.name
                        ? this.state.config.name : _t("Back"),
                     tag: "pb_formula_studio", xmlid: "", lens: "",
                     lensKey: "pb_lens",
                     context: { config_id: this.state.configId } };
        }
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
        // In edit mode the country IS changeable while nobody has been paid,
        // and it goes through the settings contract like every other field —
        // the server refuses it the moment a payslip exists.
        if (field === "country_code" && this.created && this.editing) {
            this.onSetting("country_code", value);
            await this.commitSettings(["country_code"]);
            return;
        }
        if (this.created && ["name", "cycle_type", "effective_from"].includes(field)) {
            if (this.editing && ["name", "cycle_type"].includes(field)) {
                const before = (this.state.settings && this.state.settings.values) || {};
                this._recordChange(field, before[field], value);
                if (this.state.settings) { this.state.settings.values[field] = value; }
                this.state.settingsDraft[field] = value;
            }
            this.queueSave();
        }
    }

    onPickStarter(key) {
        if (!this.created) {
            this.state.form.template_key = key;
            return;
        }
        // The workbook card is the one starter you can press twice. Every other
        // one is already applied the moment it is chosen, so re-pressing it can
        // only mean "do it again", which is nothing; the workbook's own import
        // may have been closed without importing, and then the card IS the way
        // back to the review. Nothing has been built yet, so nothing is at risk.
        if (key === "excel" && key === this.state.blueprint.template_key) {
            if (this.needsWorkbook) {
                this.openExcel();
                return;
            }
            // A workbook has already been imported: importing a second one over
            // the top is a replacement like any other, and says so first.
            this.state.confirmStarter = key;
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
        } else if (this.editing) {
            this.notif.add(
                this.state.countryLockReason
                    || _t("This configuration has already paid people, so its country cannot be changed."),
                { type: "warning" });
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
            if (this.editing) { await this.saveChanges(); return; }
            await this.finish();
            return;
        }
        // A step made of tabs is walked tab by tab before it is left. The
        // button already said so; this is the half that makes it true.
        const target = this.continueTarget;
        if (target.kind === "tab") {
            await this.onRulesTab(target.tab);
            return;
        }
        this.state.step = target.step;
        this.rememberStep();
        // Leaving Start with a workbook chosen and nothing imported means the
        // same thing it meant the first time: open the review. Creation is what
        // used to open it, so coming BACK to Start and pressing Continue again
        // walked past the import in silence and landed on an empty Pay rules.
        // The step moves first, so the dialog opens over the page it always did.
        if (this.state.step === "rules" && this.needsWorkbook) {
            this.openExcel();
        }
    }

    async onBack() {
        if (!this.created || this.state.step === "start") return;
        const target = backTarget(this.state.step, this.state.rulesTab);
        if (target.kind === "tab") {
            await this.onRulesTab(target.tab);
            return;
        }
        this.state.step = target.step;
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

    /** The refusal's own next step: open this configuration for editing. */
    async openForEditing() {
        const cid = this.state.configId;
        if (!cid) { return; }
        this.state.loading = true;
        const res = await this.rpc("bp_adopt", [cid]);
        if (!res || !res.ok) {
            this.state.loading = false;
            this.notif.add((res && res.reason)
                || _t("This configuration could not be opened for editing."),
                { type: "warning", sticky: true });
            return;
        }
        this.state.mode = res.mode === "create" ? "create" : "edit";
        this.state.fatal = "";
        this.state.fatalAdopt = false;
        this.arrival = Object.assign({}, this.arrival, { mode: this.state.mode });
        await this.resume(cid);
        this.state.loading = false;
    }

    // ==================================================================
    // The settings cards (SCHEMECTX P3)
    // ==================================================================
    /** Everything the old Settings panel read, once per draft. */
    async loadSettings() {
        if (!this.created) { return; }
        const res = await this.rpc("bp_settings", [this.state.configId]);
        if (!res || !res.ok) {
            // Never fatal: the journey is still the journey without its
            // advanced cards, and the step says so where the cards would be.
            this.state.settings = null;
            this.state.settingsError = (res && res.reason)
                || _t("The advanced settings could not be read.");
            return;
        }
        this.state.settings = res;
        this.state.settingsDraft = Object.assign({}, res.values);
        this.state.settingsMeta = res.meta || {};
        this.state.settingsError = "";
    }

    /** Which cards belong under the step that is open. */
    get settingsGroup() {
        return this.created && this.state.settings
            ? settingsGroupFor(this.state.step) : "";
    }

    onSetting(field, value) {
        this.state.settingsDraft[field] = value;
    }

    /**
     * Write the fields a card just changed — and nothing else.
     *
     * Card by card rather than one Save button at the end: the journey has
     * always saved as you go, and a screen that mixes "this is already saved"
     * with "press Save for this bit" is a screen nobody trusts.
     */
    async commitSettings(fields) {
        if (!this.created || this.state.settingsBusy) { return; }
        const before = (this.state.settings && this.state.settings.values) || {};
        const patch = {};
        for (const field of fields || []) {
            patch[field] = this.state.settingsDraft[field];
        }
        this.state.settingsBusy = true;
        this.state.saving = true;
        this.state.settingsError = "";
        const res = await this.rpc("bp_save_settings", [
            this.state.configId, patch,
            this.state.blueprint ? this.state.blueprint.revision : null]);
        this.state.settingsBusy = false;
        this.state.saving = false;
        if (!res || !res.ok) {
            // The value on screen is not what the server holds, so put the
            // server's version back rather than leaving a lie in the box.
            for (const field of fields || []) {
                this.state.settingsDraft[field] = before[field];
            }
            this.state.settingsError = (res && res.reason)
                || _t("That could not be saved.");
            return;
        }
        for (const [field, value] of Object.entries(res.values || {})) {
            this._recordChange(field, before[field], value);
            this.state.settingsDraft[field] = value;
            if (this.state.settings) { this.state.settings.values[field] = value; }
        }
        if (this.state.blueprint && res.revision !== undefined) {
            this.state.blueprint.revision = res.revision;
        }
        if (this.state.config) {
            this.state.config.name = res.name || this.state.config.name;
            this.state.config.code = res.code || "";
            if (res.currency) { this.state.config.currency = res.currency; }
            if (res.country_code) {
                this.state.config.country_code = res.country_code;
                this.state.form.country_code = res.country_code;
            }
        }
        this.state.savedAt = Date.now();
    }

    /** One line for the Save changes page: what moved, from what, to what. */
    _recordChange(field, before, after) {
        if (JSON.stringify(before ?? null) === JSON.stringify(after ?? null)) { return; }
        const row = {
            field,
            label: settingLabel(field),
            before: this.settingText(field, before),
            after: this.settingText(field, after),
        };
        const at = this.state.changes.findIndex((c) => c.field === field);
        if (at >= 0) {
            // Changed twice in one sitting: it moved from where it STARTED.
            row.before = this.state.changes[at].before;
            this.state.changes.splice(at, 1, row);
            return;
        }
        this.state.changes.push(row);
    }

    /** A stored value as a person reads it — never a raw id or `false`. */
    settingText(field, value) {
        if (value === true) { return _t("On"); }
        if (value === false || value === null || value === undefined || value === "") {
            return _t("Not set");
        }
        const meta = this.state.settingsMeta || {};
        const lists = {
            structure_id: meta.structures, connector_id: meta.connectors,
            payroll_journal_id: meta.journals, debit_account_id: meta.accounts,
            credit_account_id: meta.accounts, retro_component_id: meta.components,
        };
        if (lists[field]) {
            const row = (lists[field] || []).find((o) => o.id === value);
            return row ? (row.name || String(value)) : String(value);
        }
        if (field === "proration_component_ids") {
            const names = (value || []).map((id) => {
                const row = (meta.components || []).find((c) => c.id === id);
                return row ? (row.name || row.code) : String(id);
            });
            return names.length ? names.join(", ") : _t("None");
        }
        const sels = { proration_basis: meta.proration_bases,
                       cycle_type: meta.cycle_types,
                       country_code: meta.country_codes };
        if (sels[field]) {
            const row = (sels[field] || []).find((o) => o.value === value);
            if (row) { return row.label; }
        }
        return String(value);
    }

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
        this.state.payTick++;
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
        this.state.inputsConfirmed = !!res.confirmed;
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
        // A workbook has no components until it has been read, so "adds the
        // Import Excel workbook ones" would name a set nobody can picture. It
        // opens the review instead, and the sentence says that.
        if (this.state.confirmStarter === "excel") {
            return _t(
                "This removes all %s components and formulas of this draft and opens the workbook review again. Anything you edited by hand is lost.",
                n);
        }
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
        this.state.sampleId = null;   // the new components need a new choice
        await this.refreshPreview();
        if (key === "excel") {
            // The review is about to open on top of this, so "the draft is
            // empty and ready for your own components" would be the wrong last
            // word: the workbook is what fills it.
            this.notif.add(_t("The draft is clear. Your workbook opens for review next."),
                           { type: "success" });
            this.openExcel();
            return;
        }
        this.notif.add(
            res.rule_count
                ? _t("%s components are ready.", res.rule_count)
                : _t("The draft is empty and ready for your own components."),
            { type: "success" });
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
                // A FINISHED import returns the journey as a fresh action, so
                // by the time this runs the component that opened the dialog may
                // already have been replaced by its own successor. Re-reading
                // into it would be writing into a corpse.
                if (!this._alive) return;
                // The review may have been cancelled — re-read rather than
                // assume, so the component count on screen is never a guess.
                const load = await this.rpc("bp_load", [cid]);
                if (!this._alive) return;
                if (load && load.ok) {
                    this.applyLoad(load);
                    this.state.sampleId = null;   // the import changed the cast
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
    /**
     * The footer's primary button on the Finish step.
     *
     * It does not call `bp_finish` itself: the step owns the call, because the
     * step is where a refusal has to be READ — beside the button, in a list a
     * person can act on, rather than in a toast that fades. One implementation,
     * one set of words, two places to press it.
     */
    finish() {
        if (this.state.step !== "finish") {
            this.state.step = "finish";
            this.rememberStep();
            return;
        }
        this.state.finishSignal++;
    }

    /** The step finished successfully: say so once, and open the grid. */
    async onFinished(configId) {
        this.notif.add(_t("Setup complete. Opening the configuration."), { type: "success" });
        await this.openGrid(configId || this.state.configId, { silent: true });
    }

    /**
     * A "Go" link on the Finish step: the step that settles this decision.
     *
     * The Finish page lists questions somebody else has to answer; a list of
     * questions with no door beside each one is a list nobody acts on.
     */
    goTo(step, opts = {}) {
        if (!STEPS.includes(step)) { return; }
        if (opts.tab) { this.state.rulesTab = opts.tab; }
        if (opts.ruleId) {
            this.state.openRule = opts.ruleId;
            this.state.openTick++;
        }
        this.state.connectTask = opts.task || "";
        if (opts.task) { this.state.connectTick++; }
        this.state.step = step;
        this.rememberStep();
    }

    /**
     * "Discard this draft" — ask the server what that would destroy first.
     *
     * The confirmation names the configuration and counts its components, and a
     * draft that may not be discarded at all never opens the dialog: it says
     * why instead.
     */
    async askDiscard() {
        this.state.kebabOpen = false;
        const res = await this.rpc("bp_discard_check", [this.state.configId]);
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("This draft could not be read."),
                           { type: "warning" });
            return;
        }
        if (!res.allowed) {
            this.notif.add(res.reason, { type: "warning", sticky: true });
            return;
        }
        this.state.discard = res;
        this.state.confirmDiscard = true;
    }

    get discardText() {
        const d = this.state.discard || {};
        return discardText(d.name || (this.state.config && this.state.config.name) || "",
                           d.counts || this.state.counts || {});
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

    // ==================================================================
    // Step 2 — Pay rules
    // ==================================================================
    /** Which of the three tabs was open, remembered for the next visit. */
    async onRulesTab(tab) {
        this.state.rulesTab = tab;
        if (!this.created) return;
        await this.rpc("bp_set_tab", [this.state.configId, tab]);
    }

    /**
     * Something on the Pay rules step changed what a person is paid.
     *
     * The hero is the whole promise of this screen, so it is re-read from the
     * server after every save rather than adjusted client-side: the number a
     * person sees is always one the engine just worked out.
     */
    async onRulesChanged(res) {
        if (res && res.conflict) {
            this.state.saveError = res.reason || _t("Someone else changed this draft.");
            return;
        }
        const load = await this.rpc("bp_load", [this.state.configId]);
        if (load && load.ok) {
            const step = this.state.step;
            const tab = this.state.rulesTab;
            this.applyLoad(load);
            this.state.step = step;
            this.state.rulesTab = tab;
            // `applyLoad` restores the whole draft but says nothing about the
            // URL, and a refresh after an edit has to come back to the same
            // draft rather than to an empty journey.
            this._rememberInUrl(this.state.configId);
        }
        await this.refreshPreview();
    }

    // ==================================================================
    // Steps 4 and 5 — Outputs and Test
    // ==================================================================
    /** The Test step has a fresh answer: the scoreboard follows it. */
    onTests(res) {
        this.state.tests = res;
        this.state.testsRunning = false;
    }

    onTestsBusy(running) { this.state.testsRunning = !!running; }

    /**
     * "Run the checks", pressed on the pay panel rather than on the step.
     *
     * The step owns the checks — it holds the revision, the list and every
     * refusal — so the panel asks it to run rather than running a second copy
     * of the same call. One implementation, one set of words when it fails.
     */
    runChecks() {
        if (this.state.step !== "test") {
            this.state.step = "test";
            this.rememberStep();
        }
        this.state.testsRunning = true;
        this.state.runSignal++;
    }

    /** "1 is untested: NIGHTPREM" — pressed, and here is that component. */
    onInspectComponent(ruleId) {
        this.state.inspectRule = ruleId || 0;
        this.state.step = "outputs";
        this.rememberStep();
    }

    /** Walking away from Outputs clears what the coverage line asked for. */
    async gotoTest() {
        this.state.step = "test";
        this.rememberStep();
    }

    // ==================================================================
    // Step 3 — Connect
    // ==================================================================
    /** "Skip the rest & review outputs" has already skipped; walk on. */
    onConnectContinue() {
        this.state.connectTask = "";
        this.state.step = nextStep("connect");
        this.rememberStep();
    }

    onRulesRevision(revision) {
        if (this.state.blueprint && typeof revision === "number") {
            this.state.blueprint.revision = revision;
        }
    }

    get sampleName() {
        const preview = this.state.preview;
        return (preview && preview.sample && preview.sample.name) || "";
    }
}

registry.category("actions").add("pb_blueprint", PbBlueprint);
