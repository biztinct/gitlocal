/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const GROUPS = ["Inputs", "Earnings", "Deductions", "Totals"];

export class PbFormulaStudio extends Component {
    static template = "pb_formula_studio.PbFormulaStudio";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            empty: false,
            view: "cards",          // cards | grid
            config: {},
            configs: [],
            components: [],
            samples: [],
            preview: { sample_id: false, values: {} },
            selectedId: null,
            aiOpen: false,
            aiMsgs: [],
            aiProposal: null,
            aiLlm: false,
            aiModel: "",
            wizardOpen: false,
            wizardStep: 1,
            wizardForm: { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" },
            wizardTemplates: [],
            wizardBusy: false,
            configPickerOpen: false,
        });
        onWillStart(async () => {
            await this.load();
            try {
                const s = await this.orm.call("pb.formula.studio", "ai_status", []);
                this.state.aiLlm = s.llm; this.state.aiModel = s.model;
            } catch (e) { /* non-fatal */ }
        });
    }

    async load(configId) {
        const d = await this.orm.call("pb.formula.studio", "get_studio_data", [configId || false]);
        this.state.empty = d.empty;
        this.state.configs = d.configs || [];
        if (d.empty) { this.state.loaded = true; return; }
        this.state.config = d.config;
        this.state.components = d.components;
        this.state.samples = d.samples;
        this.state.preview = d.preview || { sample_id: false, values: {} };
        if (!this.state.selectedId || !d.components.some(c => c.id === this.state.selectedId)) {
            const firstFormula = d.components.find(c => c.type === "formula") || d.components[0];
            this.state.selectedId = firstFormula ? firstFormula.id : null;
        }
        this.state.loaded = true;
    }

    // ---- selectors ----
    get selected() { return this.state.components.find(c => c.id === this.state.selectedId) || null; }
    groupItems(g) { return this.state.components.filter(c => c.group === g); }
    get visibleGroups() { return GROUPS.filter(g => this.groupItems(g).length); }
    get sampleName() {
        const s = this.state.samples.find(s => s.id === this.state.preview.sample_id);
        return s ? s.name : "—";
    }

    selectComponent(id) { this.state.selectedId = id; }
    setView(v) { this.state.view = v; }

    // ---- formatting ----
    vnd(n) {
        if (n === null || n === undefined) return "—";
        const cur = this.state.config.currency || "₫";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    previewVal(col) {
        const v = this.state.preview.values[col];
        return (v === undefined) ? "—" : this.vnd(v);
    }
    stageCls() {
        return { draft: "draft", testing: "testing", validated: "validated", active: "active", archived: "muted" }[this.state.config.state] || "muted";
    }
    stageLabel() {
        return { draft: "Draft", testing: "Testing", validated: "Validated", active: "Active", archived: "Archived" }[this.state.config.state] || this.state.config.state;
    }
    nextLabel() {
        return { draft: "Start testing", testing: "Validate", validated: "Activate", active: "Active" }[this.state.config.state] || "Advance";
    }
    isDeduction(c) { return c.group === "Deductions"; }
    ring(score) {
        const C = 2 * Math.PI * 19;
        return { dash: C, offset: C * (1 - (score || 0) / 100) };
    }

    // ---- sample switching ----
    async cycleSample() {
        if (this.state.samples.length < 2) return;
        const idx = this.state.samples.findIndex(s => s.id === this.state.preview.sample_id);
        const next = this.state.samples[(idx + 1) % this.state.samples.length];
        this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview",
            [this.state.config.id, next.id]);
    }

    // ---- lifecycle ----
    async advance() {
        const r = await this.orm.call("pb.formula.studio", "advance", [this.state.config.id]);
        if (!r.ok) { this.notif.add(r.message || "Action blocked", { type: "warning" }); }
        else { this.notif.add("Now " + (r.state || ""), { type: "success" }); }
        await this.load(this.state.config.id);
    }
    async runValidate() {
        const r = await this.orm.call("pb.formula.studio", "validate", [this.state.config.id]);
        this.notif.add(r.ok ? "Validation complete" : (r.message || "Validation failed"),
            { type: r.ok ? "success" : "warning" });
        await this.load(this.state.config.id);
    }
    async runTests() {
        const r = await this.orm.call("pb.formula.studio", "run_tests", [this.state.config.id]);
        if (r.ok) this.notif.add(`${r.passed}/${r.total} tests passed`, { type: r.failed ? "warning" : "success" });
        else this.notif.add(r.message || "Test run failed", { type: "danger" });
        await this.load(this.state.config.id);
    }

    // ---- config picker ----
    toggleConfigPicker() { this.state.configPickerOpen = !this.state.configPickerOpen; }
    async pickConfig(id) {
        this.state.configPickerOpen = false;
        this.state.selectedId = null;
        await this.load(id);
    }

    // ---- PayAI ----
    openAI() { this.state.aiOpen = true; }
    closeAI() { this.state.aiOpen = false; }
    async aiAsk(text) {
        if (!text || !text.trim()) return;
        this.state.aiMsgs.push({ who: "you", text });
        this.state.aiProposal = null;
        const r = await this.orm.call("pb.formula.studio", "ai_propose", [this.state.config.id, text]);
        this.state.aiMsgs.push({ who: "ai", text: r.reply || "" });
        if (r.ok && r.kind === "formula") this.state.aiProposal = r;
        const inp = document.querySelector(".pbfs-ai-input input");
        if (inp) inp.value = "";
    }
    aiAskInput(ev) { if (ev.key === "Enter") this.aiAsk(ev.target.value); }
    aiAskChip(text) { this.aiAsk(text); }
    async applyProposal() {
        const p = this.state.aiProposal;
        if (!p) return;
        if (p.target_id) {
            const r = await this.orm.call("pb.formula.studio", "apply_ai_formula", [p.target_id, p.formula]);
            if (r.ok) { this.notif.add("Formula applied to " + (p.target_name || ""), { type: "success" }); }
            else { this.notif.add(r.msg || "Could not apply", { type: "warning" }); }
        } else {
            this.notif.add("That would create a new component — open the editor to confirm name & code.", { type: "info" });
        }
        this.state.aiProposal = null;
        this.state.aiOpen = false;
        await this.load(this.state.config.id);
    }
    discardProposal() { this.state.aiProposal = null; }

    // ---- guided first-setup wizard ----
    async openWizard() {
        this.state.configPickerOpen = false;
        this.state.wizardStep = 1;
        this.state.wizardForm = { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" };
        if (!this.state.wizardTemplates.length) {
            this.state.wizardTemplates = await this.orm.call("pb.formula.studio", "wizard_templates", []);
        }
        this.state.wizardOpen = true;
    }
    closeWizard() { this.state.wizardOpen = false; }
    wizardSet(field, ev) { this.state.wizardForm[field] = ev.target.value; }
    pickTemplate(key) { this.state.wizardForm.template = key; }
    get wizardTpl() { return this.state.wizardTemplates.find(t => t.key === this.state.wizardForm.template) || {}; }
    wizardBack() { if (this.state.wizardStep > 1) this.state.wizardStep--; }
    wizardNext() {
        if (this.state.wizardStep === 1 && !this.state.wizardForm.name.trim()) {
            this.notif.add("Give the configuration a name first.", { type: "warning" });
            return;
        }
        if (this.state.wizardStep < 5) this.state.wizardStep++;
    }
    async wizardCreate() {
        if (this.state.wizardBusy) return;
        this.state.wizardBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "create_config", [this.state.wizardForm]);
            if (r.ok) {
                this.notif.add(`Created “${this.state.wizardForm.name}” with ${r.rule_count} components`, { type: "success" });
                this.state.wizardOpen = false;
                this.state.selectedId = null;
                await this.load(r.config_id);
            } else {
                this.notif.add("Could not create configuration", { type: "danger" });
            }
        } finally {
            this.state.wizardBusy = false;
        }
    }
    // open native Excel/structure importers from the wizard
    importExcel() { this.action.doAction("pb_hr_payroll_formula.action_formula_config", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_formula_studio", PbFormulaStudio);
