/** @odoo-module **/
/**
 * Learning › MY LEARNING (LEARNING L0) — every member of staff's own tab.
 *
 * HERO MOMENT: "Next up" — the one lesson to do next, how long it takes,
 * and one button, Continue, that drops the reader straight into that lesson
 * on their own training page (`/my/training/<course>/<lesson>`; the browser
 * Back button returns here). When nothing is left: a calm grey tick and
 * "Nothing to do right now."
 *
 * Under it: My courses (filters Assigned · In progress · Done, counted over
 * the cards, press again to clear), My team for a manager (with a one-tap
 * Remind, one a day — the server says so in words on a second press), and
 * My allowance when the reader has an employee record.
 *
 * Reads only `pb.my.training` — "me" is the session user and is never a
 * parameter, so nothing here can show somebody else's courses. The team
 * block is the existing `team()` read (direct reports, as the system).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.my.training";
const LATE_FIRST = { overdue: 0, assigned: 1, in_progress: 2, excused: 3 };

export class PbMyLearningLens extends Component {
    static template = "pb_training.PbMyLearningLens";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            failed: false,
            home: { courses: [] },
            team: null,
            claims: null,
            filter: "",
            reminding: 0,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        this.state.failed = false;
        try {
            const [home, claims] = await Promise.all([
                this.orm.call(MODEL, "home", []),
                this.orm.call(MODEL, "claims", []).catch((e) => {
                    // The allowance block is optional: a failure there must
                    // not take the reader's own courses down with it.
                    console.warn("pb_training: my allowance could not be read", e);
                    return null;
                }),
            ]);
            this.state.home = home || { courses: [] };
            this.state.claims = claims;
            this.state.team = home && home.manages
                ? await this.orm.call(MODEL, "team", []) : null;
        } catch (e) {
            console.warn("pb_training: my learning could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    // ------------------------------------------------------------- next up
    get courses() { return this.state.home.courses || []; }

    /** The open course that matters most: late first, then by date. */
    get nextCourse() {
        const open = this.courses.filter((c) => !c.finished);
        if (!open.length) { return null; }
        const rank = (c) => {
            const a = c.assignment;
            return a ? (LATE_FIRST[a.state] ?? 4) : 5;
        };
        const due = (c) => (c.assignment && c.assignment.due) || "9999-12-31";
        return [...open].sort((x, y) => rank(x) - rank(y)
            || due(x).localeCompare(due(y)) || x.name.localeCompare(y.name))[0];
    }

    /** What "Continue" means for a course: a lesson, the test, or the course. */
    nextStep(c) {
        if (c.next_id) {
            return { title: c.next_name, url: `/my/training/${c.id}/${c.next_id}`,
                     label: _t("Continue") };
        }
        if (c.test === "ready" || c.test === "failed") {
            return { title: _t("The test at the end"), url: `/my/training/${c.id}/test`,
                     label: _t("Take the test") };
        }
        return { title: c.name, url: `/my/training/${c.id}`, label: _t("Open") };
    }

    /** A CLICK handler: the learner page, in this tab (Back returns here). */
    go(url) { window.location.assign(url); }

    // ------------------------------------------------------------- courses
    isDone(c) { return !!c.finished; }
    isStarted(c) { return !c.finished && (c.percent || 0) > 0; }
    isAssigned(c) { return !c.finished && !(c.percent || 0); }

    get filters() {
        const list = this.courses;
        return [
            { key: "assigned", label: _t("Assigned"), n: list.filter((c) => this.isAssigned(c)).length },
            { key: "started", label: _t("In progress"), n: list.filter((c) => this.isStarted(c)).length },
            { key: "done", label: _t("Done"), n: list.filter((c) => this.isDone(c)).length },
        ];
    }

    setFilter(key) { this.state.filter = this.state.filter === key ? "" : key; }

    get shownCourses() {
        const f = this.state.filter;
        const test = { assigned: (c) => this.isAssigned(c), started: (c) => this.isStarted(c),
                       done: (c) => this.isDone(c) }[f];
        return test ? this.courses.filter(test) : this.courses;
    }

    lessonWords(c) {
        if (!c.total) { return _t("No lessons yet"); }
        return c.total === 1 ? _t("%s of 1 lesson", c.done) : _t("%s of %s lessons", c.done, c.total);
    }

    /** The test chip: locked, ready, passed with the score, not passed. */
    testChip(c) {
        switch (c.test) {
            case "locked": return { cls: "", icon: "lock", text: _t("Test locked") };
            case "ready": return { cls: "is-go", icon: "target", text: _t("Take the test") };
            case "passed": return { cls: "is-ok", icon: "award",
                                    text: c.score !== null && c.score !== undefined
                                        ? `${_t("Passed")} · ${c.score}%` : _t("Passed") };
            case "failed": return { cls: "is-bad", icon: "rotate", text: _t("Not passed yet") };
            default: return null;
        }
    }

    dueClass(a) {
        if (!a) { return ""; }
        if (a.late) { return "is-bad"; }
        return a.state === "excused" ? "is-ok" : "";
    }

    // ------------------------------------------------------------- my team
    get team() { return this.state.team; }

    stateWord(key) {
        return {
            assigned: _t("Not started"), in_progress: _t("Under way"),
            overdue: _t("Overdue"), excused: _t("More time agreed"), done: _t("Finished"),
        }[key] || "";
    }

    stateClass(key) {
        return { overdue: "is-bad", excused: "is-ok", done: "is-ok",
                 in_progress: "is-go" }[key] || "";
    }

    teamBits() {
        const t = this.team || {};
        return [
            { key: "overdue", n: t.overdue || 0, warn: true,
              text: (t.overdue || 0) === 1 ? _t("1 overdue") : _t("%s overdue", t.overdue || 0) },
            { key: "due", n: t.due || 0,
              text: (t.due || 0) === 1 ? _t("1 still to do") : _t("%s still to do", t.due || 0) },
            { key: "done", n: t.done || 0, good: true,
              text: (t.done || 0) === 1 ? _t("1 finished") : _t("%s finished", t.done || 0) },
        ];
    }

    /** A CLICK handler: one email to one person; the server keeps the rule. */
    async remind(row) {
        if (this.state.reminding) { return; }
        this.state.reminding = row.id;
        try {
            const res = await this.orm.call(MODEL, "remind", [row.id]);
            this.notif.add((res && res.message) || _t("Reminder sent."), { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message)
                || _t("The reminder could not be sent."), { type: "danger" });
        } finally {
            this.state.reminding = 0;
        }
    }

    // ------------------------------------------------------------- allowance
    get allowance() {
        const c = this.state.claims;
        return c && c.has_employee ? c : null;
    }
}
