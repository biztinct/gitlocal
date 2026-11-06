/** @odoo-module **/
/**
 * Learning › SKILLS (LEARNING L5) — each person against the skills their job
 * requires, the gap, and the course that closes it.
 *
 * HERO MOMENT: one sentence — "On average a person has 4 of 6 required
 * skills · 38 gaps across 120 people" — over the quiet numbers (people,
 * gaps, missing in rose, below the level in amber). A row per person with a
 * chip per required skill: green at the level, amber below it, rose missing;
 * a gap shows the course that closes it and "Close it" (the training team:
 * puts our course on them, or agrees the outside course on their behalf).
 * The by-skill table under it: who needs it, how many have it at the level.
 *
 * A manager sees the people under them only; the training team sees
 * everybody. The rail offers the lens to whoever `can_see_skills()` says
 * yes to. Phone: rows become cards (CSS).
 *
 * Reads `pb.training.skills_board`; writes through `pb.training.act`
 * (`close_gap`).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbSkillsLens extends Component {
    static template = "pb_training.PbSkillsLens";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            failed: false,
            data: { people: [], by_skill: [], kpis: {}, lists: { jobs: [], departments: [], skills: [] } },
            f: { q: "", department_id: 0, job_id: 0, skill_id: 0, only_gaps: false },
            tab: "people",
            busy: "",
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "skills_board", [{ ...this.state.f }]);
        } catch (e) {
            console.warn("pb_training: the skills could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() { this.state.loaded = false; await this.load(); }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get people() { return this.data.people || []; }
    get bySkill() { return this.data.by_skill || []; }
    get kpis() { return this.data.kpis || {}; }
    get lists() { return this.data.lists || { jobs: [], departments: [], skills: [] }; }

    get glance() {
        const k = this.kpis;
        const tone = (v, t) => (v ? t : "");
        return [
            { key: "people", n: k.people || 0, label: _t("People whose job lists skills"), tone: "", run: null },
            { key: "gaps", n: k.gaps || 0, label: _t("Gaps"), tone: tone(k.gaps, "amber"), run: () => this.toggleGaps() },
            { key: "missing", n: k.missing || 0, label: _t("Skills missing"), tone: tone(k.missing, "rose"), run: null },
            { key: "below", n: k.below || 0, label: _t("Below the level"), tone: tone(k.below, "amber"), run: null },
        ];
    }

    setFilter(key, ev) { this.state.f[key] = Number(ev.target.value) || 0; this.load(); }

    toggleGaps() { this.state.f.only_gaps = !this.state.f.only_gaps; this.load(); }

    onSearch(ev) {
        this.state.f.q = ev.target.value;
        clearTimeout(this._q);
        this._q = setTimeout(() => this.load(), 250);
    }

    get anyFilter() {
        const f = this.state.f;
        return !!(f.q || f.department_id || f.job_id || f.skill_id || f.only_gaps);
    }

    clearFilters() {
        Object.assign(this.state.f, { q: "", department_id: 0, job_id: 0, skill_id: 0, only_gaps: false });
        this.load();
    }

    setTab(tab) { this.state.tab = tab; }

    chipClass(req) { return { ok: "is-ok", below: "is-warn", missing: "is-bad" }[req.state] || ""; }

    chipTitle(req) {
        if (req.state === "ok") { return _t("Has it at %s", req.have_level); }
        if (req.state === "below") { return _t("Has %(have)s, the job needs %(need)s", { have: req.have_level, need: req.level }); }
        return _t("Missing — the job needs %s", req.level);
    }

    gapWords(p) {
        if (!p.gap_count) { return _t("Every required skill"); }
        return p.gap_count === 1 ? _t("1 gap") : _t("%s gaps", p.gap_count);
    }

    get capWords() {
        return _t("Showing %(shown)s of %(all)s — narrow it by department, job or skill.", { shown: this.data.shown, all: this.data.matching });
    }

    needWords(req) { return _t("%(skill)s: the job needs %(level)s", { skill: req.skill, level: req.level }); }

    closeWords(course) { return _t("Close it: %s", course.name); }

    closesWords(course) { return _t("%s closes it", course.name); }

    gaps(p) { return p.required.filter((r) => r.state !== "ok"); }

    coverageClass(row) {
        if (row.coverage_pct >= 80) { return "is-ok"; }
        if (row.coverage_pct >= 50) { return "is-warn"; }
        return "is-bad";
    }

    async closeIt(p, req, course) {
        const key = `${p.employee_id}-${req.skill_id}`;
        this.state.busy = key;
        try {
            const res = await this.orm.call("pb.training", "act", ["close_gap", {
                employee_id: p.employee_id, kind: course.kind, id: course.id, skill: req.skill,
            }]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        } finally {
            this.state.busy = "";
        }
    }
}
