/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";

const TYPES = [
    ["simple_choice", "Single choice"], ["multiple_choice", "Multiple choice"],
    ["char_box", "Short text"], ["text_box", "Long text"], ["numerical_box", "Number"],
    ["date", "Date"], ["datetime", "Date and time"], ["matrix", "Matrix"], ["scale", "Scale"],
];

export class QuestionBankPicker extends Component {
    static template = "pb_training.QuestionBankPicker";
    static components = { Dialog, Many2XAutocomplete };
    static props = { close: Function, model: String, resId: Number, onAdded: Function };
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ filters: { query: "", state: "active", unused: true, sort: "recent" },
            labels: {}, rows: [], total: 0, offset: 0, selected: {}, preview: null, sections: [], section: "",
            loading: false, adding: false, reviewing: false, reviewCounts: {}, error: "", mode: "specific", balanced: false,
            draw: 5, basic: 0, intermediate: 0, advanced: 0, poolName: "Question pool", advancedFilters: false });
        this.generation = 0;
        this.previewGeneration = 0;
        this.timer = null;
        this.alive = true;
        this.types = this.lesson ? TYPES.slice(0, 2) : TYPES;
        this.lookupActions = { create: false, createEdit: false, write: false };
        this.lookups = [
            { key: "topic", label: "Topic and subtopics", model: "pb.training.question.topic" },
            { key: "tag", label: "Tag", model: "slide.tag" },
            { key: "skill", label: "Skill / objective", model: "hr.skill" },
            { key: "language", label: "Language", model: "res.lang" },
            { key: "owner", label: "Owner", model: "res.users" },
            { key: "source", label: "Source test", model: "survey.survey" },
        ];
        onWillStart(() => this.search());
        onWillUnmount(() => { this.alive = false; clearTimeout(this.timer); });
    }
    get lesson() { return this.props.model === "slide.slide"; }
    get selection() { return Object.values(this.state.selected); }
    get selectedCount() { return this.selection.length; }
    typeLabel(type) { return TYPES.find(t => t[0] === type)?.[1] || type; }
    html(value) { return markup(value || ""); } // server-sanitised native question description
    domain() { return []; }
    get end() { return Math.min(this.state.offset + 20, this.state.total); }
    get poolCounts() {
        return Object.fromEntries(["basic", "intermediate", "advanced"].map(d => [d, this.selection.filter(q => q.difficulty === d).length]));
    }
    get poolError() {
        if (this.state.mode !== "pool") { return ""; }
        if (this.selection.some(q => !q.scored)) { return "Random pools require scored questions. Remove unscored selections."; }
        if (this.state.balanced) {
            let total = 0;
            for (const d of ["basic", "intermediate", "advanced"]) {
                const count = Number(this.state[d]);
                if (!Number.isInteger(count) || count < 0 || count > this.poolCounts[d] || (this.poolCounts[d] > 0 && count === 0)) { return "Choose at least one draw for each selected difficulty, up to the number selected."; }
                total += count;
            }
            if (!total) { return "Choose how many questions to draw at each difficulty."; }
            if (total && this.selection.some(q => !["basic", "intermediate", "advanced"].includes(q.difficulty))) { return "Set a difficulty for all selected questions before building a balanced pool."; }
        } else if (!Number.isInteger(Number(this.state.draw)) || Number(this.state.draw) < 1 || Number(this.state.draw) > this.selectedCount) {
            return "Questions per attempt must be between 1 and the selected pool size.";
        }
        return "";
    }
    get canAdd() { return this.selectedCount > 0 && this.selectedCount <= 200 && !this.poolError && !this.state.adding; }
    async search(reset = false) {
        if (reset) { this.state.offset = 0; }
        const generation = ++this.generation;
        this.state.loading = true;
        this.state.error = "";
        try {
            const data = await this.orm.call("pb.training.question.bank", "browse_bank", [
                { ...this.state.filters }, this.state.offset, this.props.model, this.props.resId,
            ]);
            if (!this.alive || generation !== this.generation) { return; }
            Object.assign(this.state, { rows: data.rows, total: data.total, sections: data.sections, reviewCounts: data.review_counts || {} });
        } catch (error) {
            if (this.alive && generation === this.generation) { this.state.error = error.data?.message || error.message; }
        } finally {
            if (this.alive && generation === this.generation) { this.state.loading = false; }
        }
    }
    queryChanged(ev) {
        this.state.filters.query = ev.target.value;
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.search(true), 250);
    }
    async reviewStatus(status) { this.state.filters.state = status; await this.search(true); }
    async filterChanged(key, ev) { this.state.filters[key] = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value; await this.search(true); }
    async lookupChanged(key, records) {
        this.state.filters[key] = records?.[0]?.id || "";
        this.state.labels[key] = records?.[0]?.display_name || "";
        await this.search(true);
    }
    async reset() {
        this.state.filters = { query: "", state: "active", unused: true, sort: "recent" };
        this.state.labels = {};
        await this.search(true);
    }
    async page(delta) { this.state.offset += delta * 20; await this.search(); }
    toggle(q) {
        if (this.state.selected[q.id]) { delete this.state.selected[q.id]; }
        else if (!q.used && !q.problem && q.state === "approved") { this.state.selected[q.id] = q; }
    }
    selectPage() { for (const q of this.state.rows) { if (!q.used && !q.problem && q.state === "approved") { this.state.selected[q.id] = q; } } }
    clearSelection() { this.state.selected = {}; }
    async preview(q) {
        const generation = ++this.previewGeneration;
        try {
            const data = await this.orm.call("pb.training.question.bank", "preview", [q.id]);
            if (this.alive && generation === this.previewGeneration) { this.state.preview = { ...data, used: q.used, problem: q.problem }; }
        } catch (error) { if (this.alive) { this.state.error = error.data?.message || error.message; } }
    }
    async approveAndSelect() {
        const q = this.state.preview;
        if (!q || q.state !== "draft" || q.approval_problem || q.problem || q.used || this.state.reviewing) { return; }
        this.state.reviewing = true;
        this.state.error = "";
        try {
            await this.orm.call("survey.question", "action_bank_approve", [[q.id]]);
            const approved = await this.orm.call("pb.training.question.bank", "preview", [q.id]);
            this.state.selected[q.id] = approved;
            this.state.preview = approved;
            await this.search();
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.reviewing = false; }
    }
    async editQuestion() {
        const q = this.state.preview;
        await this.action.doAction({ type: "ir.actions.act_window", res_model: "survey.question", res_id: q.id,
            views: [[q.editor_view_id, "form"]], target: "new" }, { onClose: async () => {
                if (!this.alive) { return; }
                delete this.state.selected[q.id];
                await this.search();
                const row = this.state.rows.find(r => r.id === q.id);
                await this.preview(row || q);
            } });
    }
    async add() {
        if (!this.canAdd) { return; }
        this.state.adding = true;
        this.state.error = "";
        try {
            const pool = this.state.mode === "pool" ? { balanced: this.state.balanced, draw: Number(this.state.draw),
                basic: Number(this.state.basic), intermediate: Number(this.state.intermediate), advanced: Number(this.state.advanced), name: this.state.poolName } : null;
            await this.orm.call("pb.training.question.bank", "add_questions", [this.props.model, this.props.resId,
                this.selection.map(q => q.id), Number(this.state.section) || false, pool]);
            await this.props.onAdded();
            this.props.close();
        } catch (error) { this.state.error = error.data?.message || error.message; }
        finally { this.state.adding = false; }
    }
}

export class QuestionBankWidget extends Component {
    static template = "pb_training.QuestionBankWidget";
    static props = { ...standardWidgetProps };
    setup() {
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({ busy: false });
    }
    get needsSave() { return !this.props.record.resId || this.props.record.dirty; }
    async open() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const record = this.props.record;
            if (this.needsSave && !await record.save()) { return; }
            this.dialog.add(QuestionBankPicker, { model: record.resModel, resId: record.resId,
                onAdded: async () => { await record.load(); this.notification.add("Library questions added. Your draft has been saved.", { type: "success" }); } });
        } finally { this.state.busy = false; }
    }
}

export class QuestionBankRefresh extends Component {
    static template = "pb_training.QuestionBankRefresh";
    static props = { ...standardWidgetProps };
    setup() { this.orm = useService("orm"); this.notification = useService("notification"); this.state = useState({ busy: false }); }
    async refresh() {
        this.state.busy = true;
        try {
            const r = this.props.record;
            if (!await r.save()) { return; }
            await this.orm.call("pb.training.question.bank", "refresh_copy", [r.resModel, r.resId]);
            await r.load();
            this.notification.add("Draft updated from the approved library version.", { type: "success" });
        } finally { this.state.busy = false; }
    }
}
registry.category("view_widgets").add("pb_question_bank", { component: QuestionBankWidget });
registry.category("view_widgets").add("pb_bank_refresh", { component: QuestionBankRefresh });
