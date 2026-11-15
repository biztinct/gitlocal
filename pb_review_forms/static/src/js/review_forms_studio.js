/** @odoo-module **/
/**
 * `pb_review_forms_studio` — Settings › HR › Review forms (WDGAP S9-A).
 *
 * A GUIDED FIVE-STEP SCREEN, ONE GOAL YEAR AT A TIME: how the overall result
 * is mixed, the skills and values, HR's questions, when the employee sees the
 * manager's part, and a last check before the form is put in use. Every
 * "Next" saves; the server checks every rule again (shares total 100, at most
 * eight questions, a locked form only takes a new "shown from" day).
 *
 * NOTHING HERE WORKS OUT A RULE. The problems list, the lock and the counts
 * all come from `pb.review.forms`; this file draws them.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";

const STEPS = [
    { key: "shares", label: _t("The result"), icon: "percent" },
    { key: "skills", label: _t("Skills and values"), icon: "star" },
    { key: "questions", label: _t("Questions"), icon: "messageSquare" },
    { key: "reveal", label: _t("Showing it"), icon: "eye" },
    { key: "check", label: _t("Check and use"), icon: "checkCircle" },
];

function reason(e) {
    return (e && e.data && e.data.message) || (e && e.message)
        || _t("That did not work.");
}

export class PbReviewFormsStudio extends Component {
    static template = "pb_review_forms.Studio";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        this.steps = STEPS;
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false, ok: true, why: "", busy: false,
            years: [], cycleId: 0, mayEdit: false,
            form: null, draft: null, step: "shares",
            limits: { skills: 8, questions: 8 },
            questionTypes: [], whoAnswers: [], revealModes: [],
            hasValues: false, copyTo: 0,
        });
        onWillStart(() => this.load());
    }

    async load(cycleId) {
        try {
            const d = await this.orm.call("pb.review.forms", "studio_load",
                                          [cycleId || this.state.cycleId || null]);
            this.state.ok = !!d.ok;
            this.state.why = d.why || "";
            if (d.ok) {
                Object.assign(this.state, {
                    years: d.years || [], cycleId: d.cycle_id || 0,
                    mayEdit: !!d.may_edit, limits: d.limits,
                    questionTypes: d.question_types || [],
                    whoAnswers: d.who_answers || [],
                    revealModes: d.reveal_modes || [],
                    hasValues: !!d.has_values,
                });
                this.setForm(d.form);
            }
        } catch (e) {
            this.state.ok = false;
            this.state.why = reason(e);
        } finally {
            this.state.loaded = true;
        }
    }

    setForm(form) {
        this.state.form = form;
        this.state.draft = form ? JSON.parse(JSON.stringify(form)) : null;
        this.state.copyTo = 0;
    }

    // ------------------------------------------------------------- reading
    get year() {
        return this.state.years.find((y) => y.id === this.state.cycleId) || null;
    }
    get readOnly() {
        const f = this.state.form;
        return !this.state.mayEdit || !f || f.locked || f.cycle_closed;
    }
    get revealOnly() {
        const f = this.state.form;
        return this.state.mayEdit && f && f.locked && !f.cycle_closed;
    }
    get shareTotal() {
        const d = this.state.draft || {};
        return (Number(d.share_goals) || 0) + (Number(d.share_skills) || 0)
            + (Number(d.share_questions) || 0);
    }
    get copyTargets() {
        return this.state.years.filter(
            (y) => !y.has_form && !y.closed && y.id !== this.state.cycleId);
    }
    get hasCopyTo() { return Number(this.state.copyTo) > 0; }
    stepIndex(key) { return STEPS.findIndex((s) => s.key === key); }
    yearTone(y) {
        if (!y.has_form) { return "quiet"; }
        return y.state === "published" ? "ok" : "wait";
    }

    // ---------------------------------------------------------- the presses
    async pickYear(id) {
        if (id === this.state.cycleId) { return; }
        this.state.cycleId = id;
        this.state.step = "shares";
        await this.load(id);
    }

    async goStep(key) {
        if (key === this.state.step) { return; }
        if (!this.readOnly || this.revealOnly) {
            const saved = await this.save(false);
            if (!saved) { return; }
        }
        this.state.step = key;
    }

    async next() {
        const i = this.stepIndex(this.state.step);
        if (i < STEPS.length - 1) { await this.goStep(STEPS[i + 1].key); }
    }

    async prev() {
        const i = this.stepIndex(this.state.step);
        if (i > 0) { await this.goStep(STEPS[i - 1].key); }
    }

    payload() {
        const d = this.state.draft;
        const out = {
            name: d.name, intro: d.intro, share_goals: d.share_goals,
            share_skills: d.share_skills, share_questions: d.share_questions,
            reveal: d.reveal, reveal_date: d.reveal_date || false,
        };
        if (!this.readOnly) {
            out.skills = d.skills.map((l) => ({ id: l.id || 0, name: l.name,
                                                description: l.description }));
            out.questions = d.questions.map((l) => ({
                id: l.id || 0, name: l.name, description: l.description,
                qtype: l.qtype, choices: l.choices, who: l.who,
                required: !!l.required }));
        }
        return out;
    }

    async save(say = true) {
        if (!this.state.draft) { return true; }
        this.state.busy = true;
        try {
            const form = await this.orm.call("pb.review.forms", "studio_save",
                                             [this.state.cycleId, this.payload()]);
            this.setForm(form);
            await this.refreshYears();
            if (say) { this.notif.add(_t("Saved."), { type: "success" }); }
            return true;
        } catch (e) {
            this.notif.add(reason(e), { type: "danger" });
            return false;
        } finally {
            this.state.busy = false;
        }
    }

    async refreshYears() {
        const d = await this.orm.call("pb.review.forms", "studio_load",
                                      [this.state.cycleId]);
        if (d.ok) { this.state.years = d.years || []; }
    }

    async run(method, args, sentence) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.review.forms", method, args);
            if (res && res.cycle_id !== undefined && res.share_goals !== undefined) {
                this.setForm(res);
            }
            await this.refreshYears();
            this.notif.add((res && res.sentence) || sentence, { type: "success" });
            return res;
        } catch (e) {
            this.notif.add(reason(e), { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    async publish() {
        if (!(await this.save(false))) { return; }
        await this.run("studio_publish", [this.state.cycleId],
                       _t("The form is in use for this goal year."));
    }
    async unpublish() {
        await this.run("studio_unpublish", [this.state.cycleId],
                       _t("The form is back to being written."));
    }
    async showNow() {
        await this.run("studio_show_now", [this.state.cycleId],
                       _t("Shared."));
    }
    async copy() {
        if (!this.hasCopyTo) { return; }
        const res = await this.run("studio_copy",
                                   [this.state.cycleId, Number(this.state.copyTo)],
                                   _t("Copied."));
        if (res && res.cycle_id) { await this.pickYear(res.cycle_id); }
    }
    preview() {
        const url = this.state.form && this.state.form.preview_url;
        if (url) { window.open(url, "_blank", "noopener"); }
    }

    // -------------------------------------------------------- editing rows
    setField(key, ev) {
        const v = ev.target.value;
        this.state.draft[key] = key.startsWith("share_") ? (parseInt(v, 10) || 0) : v;
    }
    addLine(section) {
        const list = section === "skill" ? this.state.draft.skills
            : this.state.draft.questions;
        const cap = section === "skill" ? this.state.limits.skills
            : this.state.limits.questions;
        if (list.length >= cap) { return; }
        list.push({ id: 0, section, name: "", description: "", qtype: "rating",
                    choices: "", who: "both", required: true });
    }
    removeLine(section, index) {
        const list = section === "skill" ? this.state.draft.skills
            : this.state.draft.questions;
        list.splice(index, 1);
    }
    moveLine(section, index, by) {
        const list = section === "skill" ? this.state.draft.skills
            : this.state.draft.questions;
        const to = index + by;
        if (to < 0 || to >= list.length) { return; }
        const [row] = list.splice(index, 1);
        list.splice(to, 0, row);
    }
    setLine(row, key, ev) {
        row[key] = ev.target.type === "checkbox" ? ev.target.checked : ev.target.value;
    }
    async fillValues() {
        try {
            const values = await this.orm.call("pb.review.forms", "studio_values", []);
            const have = new Set(this.state.draft.skills.map((s) => (s.name || "").trim()));
            for (const v of values) {
                if (this.state.draft.skills.length >= this.state.limits.skills) { break; }
                if (have.has(v.name)) { continue; }
                this.state.draft.skills.push({ id: 0, section: "skill", name: v.name,
                                               description: v.description,
                                               qtype: "rating", who: "both",
                                               required: true });
            }
            if (!values.length) {
                this.notif.add(_t("No company values are written yet."), { type: "info" });
            }
        } catch (e) {
            this.notif.add(reason(e), { type: "danger" });
        }
    }
}

registry.category("actions").add("pb_review_forms_studio", PbReviewFormsStudio);

/* ------------------------------------------------------------- Settings ---- */
registry.category(SETTINGS_CATEGORIES).add("reviews", {
    key: "reviews",
    group: "hr",
    icon: "listChecks",
    label: _t("Review forms"),
    blurb: _t("One form for each goal year: the goals score, a few skills or "
              + "values, and your own questions."),
    groups: ["pb_goals.group_goals_user"],
    cards: [{
        id: "review_forms",
        tag: "pb_review_forms_studio",
        icon: "listChecks",
        label: _t("Review forms"),
        sub: _t("What the end-of-year review asks, and how the overall result "
                + "is worked out."),
    }],
}, { sequence: 60 });

/* ---------------------------------------------------------- command bar --- */
registry.category("pb_hub_palette").add("review_forms", {
    id: "review_forms",
    label: _t("Review forms"),
    sublabel: _t("Goals"),
    icon: "listChecks",
    groups: ["pb_goals.group_goals_user"],
    probe: { model: "pb.review.forms", method: "can_open" },
    requires: "pb_review_forms_studio",
    action: { xmlid: "pb_review_forms.action_review_forms" },
    keywords: ["appraisal", "review", "đánh giá", "penilaian"],
}, { sequence: 3640 });
