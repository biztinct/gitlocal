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
 * the cards, press again to clear), My certificates (LEARNING L1: a chip per
 * certificate in its state colour, "Start renewal" when the refresher course
 * is open, links to the wallet page and the learning record PDF), My team
 * for a manager (with a one-tap Remind, one a day — the server says so in
 * words on a second press), and My allowance when the reader has an
 * employee record.
 *
 * LEARNING L3: "My path" right under the hero — one card per path the reader
 * is on, with the dot rail (done tick, now ring, waiting grey with "after
 * <the step it waits for>"), "At step 2 of 4: …" and Continue. The hero
 * prefers a path's current step, so the reader sees one thing to do.
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
            certs: null,
            required: null,
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
            const [home, claims, certs, required] = await Promise.all([
                this.orm.call(MODEL, "home", []),
                this.orm.call(MODEL, "claims", []).catch((e) => {
                    // The allowance block is optional: a failure there must
                    // not take the reader's own courses down with it.
                    console.warn("pb_training: my allowance could not be read", e);
                    return null;
                }),
                this.orm.call(MODEL, "my_certificates", []).catch((e) => {
                    console.warn("pb_training: my certificates could not be read", e);
                    return null;
                }),
                // LEARNING L2: "Required for you" — optional like the others.
                this.orm.call(MODEL, "required_for_me", []).catch((e) => {
                    console.warn("pb_training: required training could not be read", e);
                    return null;
                }),
            ]);
            this.state.home = home || { courses: [] };
            this.state.claims = claims;
            this.state.certs = certs;
            this.state.required = required;
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

    // ------------------------------------------------------------- my paths
    get paths() { return this.state.home.paths || []; }

    /** The path whose current step the hero shows (late paths come first). */
    get nextPath() {
        return this.paths.find((p) => p.state !== "done" && p.next && p.next.channel_id
            && this.courses.some((c) => c.id === p.next.channel_id && !c.finished)) || null;
    }

    pathDotClass(step) { return `pbml-dot--${step.state}`; }

    pathDotTitle(step) {
        const word = { done: _t("Finished"), now: _t("On it now"), next: _t("Open"),
                       waits: step.after ? _t("Opens after %s", step.after) : _t("Waiting") }[step.state] || "";
        return `${step.name} — ${word}`;
    }

    afterWords(step) { return _t("after %s", step.after); }

    pathStyle(p) { return `--pbml-cols: ${Math.max((p.steps || []).length, 1)};`; }

    /** A CLICK handler: the current step — its next lesson when we know it. */
    continuePath(p) {
        if (!p.next || !p.next.channel_id) { return; }
        const tile = this.courses.find((c) => c.id === p.next.channel_id);
        this.go(tile ? this.nextStep(tile).url : `/my/training/${p.next.channel_id}`);
    }

    /** The open course that matters most: a path's current step first (one
     *  thing to do), then late, then by date. */
    get nextCourse() {
        const viaPath = this.nextPath;
        if (viaPath) {
            return this.courses.find((c) => c.id === viaPath.next.channel_id);
        }
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

    /**
     * "3 days left" / "8 days overdue", in the reader's language. The server
     * sends English words (`due_words`, a pre-existing gap in the module's
     * translations), so the lens says it from the date itself — the same five
     * whole sentences, never a frame with a number dropped in (R117).
     */
    dueWords(due) {
        if (!due) { return ""; }
        const [y, m, d] = due.split("-").map(Number);
        const now = new Date();
        const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate());
        const days = Math.round((Date.UTC(y, m - 1, d) - today) / 86400000);
        if (days === 0) { return _t("Due today"); }
        if (days === 1) { return _t("1 day left"); }
        if (days > 1) { return _t("%s days left", days); }
        if (days === -1) { return _t("1 day overdue"); }
        return _t("%s days overdue", -days);
    }

    /** Why they are on it, in the reader's language (server word as fallback). */
    reasonWord(key, fallback) {
        return {
            day_one: _t("Day one"), probation: _t("Trial period"),
            compliance: _t("Compliance"), adhoc: _t("One-off"),
            leadership: _t("Leadership programme"), renewal: _t("Renewal"),
            required: _t("Required"),
        }[key] || fallback || "";
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

    // ------------------------------------------------------------- certificates
    get certs() {
        const c = this.state.certs;
        return c && c.has_employee ? c : null;
    }

    /** The certificates worth a chip: everything not replaced by a newer one. */
    get certRows() {
        return ((this.certs && this.certs.rows) || []).filter((r) => r.state !== "renewed");
    }

    certClass(row) {
        return { expired: "is-bad", soon: "is-warn", valid: "is-ok" }[row.state] || "";
    }

    /** The certificate on a course card, when that course has one. */
    courseCertClass(c) { return c.certificate ? this.certClass(c.certificate) : ""; }

    // ------------------------------------------------------------- required
    get requiredRows() {
        const r = this.state.required;
        return (r && r.has_employee && r.rows) || [];
    }

    requiredClass(row) {
        return { missing: "is-bad", expiring: "is-warn", valid: "is-ok" }[row.state] || "";
    }

    // ------------------------------------------------------------- allowance
    get allowance() {
        const c = this.state.claims;
        return c && c.has_employee ? c : null;
    }
}
