/** @odoo-module **/
import { Component, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { useService } from "@web/core/utils/hooks";

/** A guide over the native record, never a second copy of the editor's data. */
export class LearningAuthoringGuide extends Component {
    static template = "pb_training.AuthoringGuide";
    static props = { ...standardWidgetProps };
    setup() {
        this.root = useRef("root");
        this.state = useState({ saving: false, destination: "" });
        this.notification = useService("notification");
        onWillUnmount(() => this.clearDestination());
    }
    get isCourse() { return this.props.record.resModel === "slide.channel"; }
    get data() { return this.props.record.data; }
    get title() { return this.isCourse ? _t("Create a course worth taking") : _t("Make every question count"); }
    get subtitle() {
        return this.isCourse
            ? _t("A clear outcome. Bite-sized lessons. A confident next step for your people.")
            : _t("Build a focused assessment, set fair rules, and show learners what success looks like.");
    }
    get checks() {
        const rows = this.data[this.isCourse ? "slide_ids" : "question_and_page_ids"]?.records || [];
        const description = new DOMParser().parseFromString(String(this.data.description || ""), "text/html");
        return [
            { key: "title", label: _t("Give it a clear name"), done: Boolean(String(this.data[this.isCourse ? "name" : "title"] || "").trim()) },
            { key: "description", label: this.isCourse ? _t("Describe the learning outcome") : _t("Introduce the test"), done: Boolean(description.body.textContent.trim() || description.querySelector("img,video,iframe")) },
            { key: this.isCourse ? "content" : "questions", label: this.isCourse ? _t("Add your first lesson") : _t("Add your first question"), done: rows.some(r => !r.data[this.isCourse ? "is_category" : "is_page"]) },
        ];
    }
    get completed() { return this.checks.filter(c => c.done).length; }
    get progressLabel() { return _t("%s of 3 essentials added", this.completed); }
    get status() {
        if (!this.props.record.resId) { return _t("Not saved yet"); }
        if (this.props.record.dirty) { return _t("Unsaved changes"); }
        return this.isCourse && this.data.website_published ? _t("Published course") : _t("Saved record");
    }
    get saveLabel() { return this.state.saving ? _t("Saving…") : (this.isCourse ? _t("Save course") : _t("Save test")); }
    async save() {
        if (this.state.saving) { return; }
        this.state.saving = true;
        try {
            // Full-page records only; nested dialogs keep their native saveRecord
            // callback, which also attaches the new record to its parent.
            if (await this.props.record.save()) {
                this.notification.add(_t("Your changes are saved."), { type: "success" });
            }
        } finally { this.state.saving = false; }
    }
    get audience() {
        if (this.isCourse) {
            return this.data.visibility === "members" ? _t("Enrolled learners only") : _t("Review course visibility before sharing");
        }
        return this.data.access_mode === "token" ? _t("Invited learners only") : _t("Anyone with the link");
    }
    get rules() {
        if (this.isCourse) { return _t("Save your work, then preview and assign"); }
        return this.data.scoring_type === "no_scoring" ? _t("Scoring is switched off") : _t("Pass mark: %s%%", this.data.scoring_success_min);
    }
    clearDestination() {
        cancelAnimationFrame(this.navigationFrame);
        this.navigationForm?.removeEventListener("click", this.onTabClick);
        for (const element of this.highlighted || []) {
            element.classList.remove("pb-author-spotlight", "pb-author-tab-target");
        }
        this.highlighted = [];
    }
    go(key) {
        // Scope to this form: a nested question dialog must never switch its parent.
        const form = this.root.el.closest(".o_form_renderer");
        if (!form) { return; }
        this.clearDestination();
        this.state.destination = key;
        const tab = key !== "title" && form.querySelector(`.o_notebook_headers .nav-link[name="${key}"]`);
        if (tab) { tab.click(); }
        this.navigationForm = form;
        this.onTabClick = (event) => {
            if (event.target.closest(".o_notebook_headers .nav-link")) {
                this.clearDestination();
                this.state.destination = "";
            }
        };
        form.addEventListener("click", this.onTabClick);
        // Notebook pages mount asynchronously. Wait for the actual destination,
        // not just the tab, and cancel pending navigation on another click/unmount.
        let frames = 0;
        const reveal = () => {
            const page = form.querySelector(".o_notebook_content > .tab-pane.active");
            const field = { description: "description", content: "slide_ids", questions: "question_and_page_ids" }[key];
            const target = key === "title" ? form.querySelector(".oe_title")
                : (tab?.classList.contains("active") && (field ? page?.querySelector(`.o_field_widget[name="${field}"]`) : page));
            if (!target || !target.getClientRects().length || (key === "description" && !target.querySelector("[contenteditable=true]"))) {
                if (++frames < 120) { this.navigationFrame = requestAnimationFrame(reveal); }
                return;
            }
            target.classList.add("pb-author-spotlight");
            this.highlighted.push(target);
            if (tab) { tab.classList.add("pb-author-tab-target"); this.highlighted.push(tab); }
            const addButtons = target.querySelectorAll(".o_field_x2many_list_row_add a");
            const focus = target.querySelector("input:not([type=hidden]), textarea, [contenteditable=true]")
                || addButtons[key === "content" ? 1 : 0];
            focus?.focus({ preventScroll: true });
            target.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
        };
        this.navigationFrame = requestAnimationFrame(reveal);
    }
}
registry.category("view_widgets").add("pb_learning_authoring_guide", { component: LearningAuthoringGuide });
