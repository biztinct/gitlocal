/** @odoo-module **/
/**
 * Step 7 — "Ready to go live?" (WFSETUP P4).
 *
 * The checklist (every amber line has a Fix button that lands on its step),
 * the first full week of the roster for a few real people, and the publish
 * card. Publish asks once, inline, with the real numbers; then the roster is
 * made and published ONE WEEK PER CALL so each week visibly ticks over, and a
 * failed week stops with the sentence and "Carry on" (earlier weeks stay
 * published; carrying on publishes only what is left). The finish is the
 * green "Workforce is live." card.
 */
import { Component, onWillStart, useEffect, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { MODEL, icon, errorText } from "./setup_util";

export class StepLive extends Component {
    static template = "pb_workforce_setup.StepLive";
    static props = { studio: Object, data: Object };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.icon = icon;
        this.root = useRef("root");
        this.state = useState({
            loading: true,
            error: "",
            chk: null,
            full: null,                // the 12-week plan, split per week (P5a)
            weeks: 4,
            checking: false,
            asking: false,             // the inline "are you sure" panel
            run: null,                 // {id, weeks:[{from,to,label,status,count}], failed, sentence}
            phase: "",                 // '' | 'starting' | 'running' | 'stopped' | 'finishing'
            finish: null,
            resumeHidden: false,
        });
        useEffect(() => {
            if (this.state.asking) {
                this.root.el?.querySelector(".pbws-ask-go")?.focus();
            }
        }, () => [this.state.asking]);
        useEffect(() => {
            if (this.state.finish) {
                this.root.el?.querySelector(".pbws-done")?.focus();
            }
        }, () => [this.state.finish]);
        onWillStart(() => this.load(true));
    }

    // ------------------------------------------------------------ data
    /**
     * The checklist first (fast), then the working-week plan. The plan is the
     * engine's pass over every person and day (~12 s for 700 people), so it is
     * asked ONCE per visit for the whole 12-week window the screen offers and
     * kept on the studio with the server's fingerprint of everything it reads
     * (P5a). Changing the week count sums the first N weeks — no server call.
     * The kept plan is used again while the fingerprint is the same; any
     * change to people, working weeks, shifts, holidays, time off or the
     * roster gives a new fingerprint and a fresh plan.
     */
    async load(first = false) {
        const seq = (this.seq = (this.seq || 0) + 1);
        this.state.error = "";
        this.state.checking = true;
        try {
            const [quick, resume] = await Promise.all([
                this.orm.call(MODEL, "live_check", [this.state.weeks, false]),
                first ? this.orm.call(MODEL, "go_live_resume", []) : Promise.resolve(null),
            ]);
            if (seq !== this.seq) {
                return;
            }
            this.state.chk = quick;
            this.state.loading = false;
            if (first && resume && !this.state.run) {
                this.state.run = {
                    id: resume.run_id,
                    weeks: resume.weeks.map((w, i) => ({
                        ...w,
                        status: resume.done.includes(i) ? "done" : i === resume.failed_index ? "fail" : "wait",
                        count: null,
                    })),
                    sentence: resume.failed_text || _t("Publishing stopped before every week was done."),
                    published: resume.published,
                };
                this.state.phase = "stopped";
            }
            if (quick.can_edit) {
                const kept = this.props.studio.livePlan;
                if (kept && kept.key === quick.plan_key) {
                    this.state.full = kept;
                } else {
                    // NOT awaited: the step shows at once with the checklist and
                    // the calm "working out the roster" skeleton meanwhile
                    this.state.full = null;
                    this.loadPlan(seq);
                }
            }
        } catch (e) {
            if (seq === this.seq) {
                this.state.error = errorText(e);
            }
        } finally {
            if (seq === this.seq) {
                this.state.loading = false;
                this.state.checking = false;
            }
        }
    }
    async loadPlan(seq) {
        try {
            const full = await this.orm.call(MODEL, "live_plan", []);
            this.props.studio.livePlan = full;
            if (seq === this.seq) {
                this.state.full = full;
            }
        } catch (e) {
            if (seq === this.seq) {
                this.state.error = errorText(e);
                this.props.studio.toast(errorText(e), { kind: "error" });
            }
        }
    }
    retry() {
        this.state.loading = true;
        this.load(true);
    }

    // ------------------------------------------------------------ reading
    get chk() { return this.state.chk; }
    get canEdit() { return !!this.chk?.can_edit; }
    /** The plan for the first N weeks: the sum of the kept per-week plan. */
    get plan() {
        const full = this.state.full;
        if (!full || !this.canEdit) {
            return null;
        }
        const out = { people: 0, new_shifts: 0, already_planned: 0, shifts: 0, already_published: 0,
                      removed: 0, skipped_total: 0, skipped: {} };
        for (const w of full.weeks.slice(0, this.state.weeks)) {
            for (const k of ["people", "new_shifts", "already_planned", "shifts", "already_published", "removed", "skipped_total"]) {
                out[k] += w[k] || 0;
            }
            for (const [code, n] of Object.entries(w.skipped || {})) {
                out.skipped[code] = (out.skipped[code] || 0) + n;
            }
        }
        return out;
    }
    get slices() { return (this.chk?.all_slices || []).slice(0, this.state.weeks); }
    get canPublish() { return !!this.plan && !this.chk.blocked && this.plan.shifts > 0; }
    get publishLabel() {
        const p = this.plan;
        if (this.chk?.missing && p?.people) {
            return _t("Publish for the %s who are ready", p.people.toLocaleString());
        }
        const n = this.state.weeks;
        return n === 1 ? _t("Publish 1 week") : _t("Publish %s weeks", n);
    }
    get workingLine() {
        const n = this.chk?.headcount || 0;
        return n === 1 ? _t("Working out the roster for 1 person…")
            : _t("Working out the roster for %s people…", n.toLocaleString());
    }
    get busy() { return ["starting", "running", "finishing"].includes(this.state.phase); }
    get showRun() { return !!this.state.run && !this.state.finish && !(this.state.phase === "stopped" && this.state.resumeHidden); }

    checkClass(s) { return `pbws-check${s.ok ? "" : s.blocking ? " is-block" : " is-amber"}`; }
    get needs() { return (this.chk?.steps || []).filter((s) => !s.ok); }
    get blockers() { return (this.chk?.steps || []).filter((s) => s.blocking); }
    fixLabel(s) { return s.ok ? _t("Change") : _t("Fix this"); }

    get weeksLabel() {
        const n = this.state.weeks;
        return n === 1 ? _t("1 week") : _t("%s weeks", n);
    }
    get launchTitle() {
        const n = this.state.weeks;
        return n === 1 ? _t("Publish 1 week of roster") : _t("Publish %s weeks of roster", n);
    }
    get windowLine() {
        const sl = this.slices;
        if (!sl.length) {
            return "";
        }
        return _t("From %(from)s to %(to)s.", { from: sl[0].from_label, to: sl[sl.length - 1].to_label });
    }
    get planning() { return this.canEdit && !this.plan; }
    get launchLine() {
        if (this.planning) {
            return this.workingLine;
        }
        const b = this.blockers.length;
        if (b) {
            return b === 1 ? _t("1 thing above still needs you before you can publish.")
                : _t("%s things above still need you before you can publish.", b);
        }
        const amber = this.needs.length;
        if (amber) {
            return _t("You can publish now. The amber lines above can be finished later.");
        }
        return _t("Everything is ready. People see their shifts in My Payobook straight away.");
    }
    get bigNumber() { return this.planning ? "…" : (this.plan?.shifts || 0).toLocaleString(); }
    get bigLine() {
        if (this.planning) {
            return _t("shifts");
        }
        const p = this.plan?.people || 0;
        return p === 1 ? _t("shifts for 1 person") : _t("shifts for %s people", p.toLocaleString());
    }
    get planNote() {
        const p = this.plan;
        if (!p) {
            return "";
        }
        const parts = [];
        if (p.already_planned) {
            parts.push(_t("%s already planned", p.already_planned.toLocaleString()));
        }
        if (p.new_shifts) {
            parts.push(_t("%s new from the working weeks", p.new_shifts.toLocaleString()));
        }
        if (p.already_published) {
            parts.push(_t("%s published before", p.already_published.toLocaleString()));
        }
        return parts.join(" · ");
    }
    get skippedLine() {
        const n = this.plan?.skipped_total || 0;
        if (!n) {
            return "";
        }
        return n === 1 ? _t("1 day is left out: someone is on leave, on a public holiday or already has a shift then.")
            : _t("%s days are left out: someone is on leave, on a public holiday or already has a shift then.", n.toLocaleString());
    }
    get askLine() {
        const p = this.plan || {};
        return _t("%(weeks)s · %(people)s people · %(shifts)s shifts.", {
            weeks: this.weeksLabel,
            people: (p.people || 0).toLocaleString(),
            shifts: (p.shifts || 0).toLocaleString(),
        });
    }
    get sample() {
        const s = this.state.full?.samples;
        return s ? (this.state.weeks === 1 ? s.one : s.more) : null;
    }
    get sampleLine() {
        const s = this.sample;
        return _t("showing %(n)s of %(total)s people", { n: s.rows.length, total: s.people.toLocaleString() });
    }
    cellClass(d) { return d.start ? `pbws-rc pbws-c-${d.color}` : "pbws-rc is-off"; }
    cellTitle(d) { return d.start ? d.name : _t("Off"); }

    // live state
    get live() { return this.chk?.live || null; }
    get liveLine() {
        const l = this.live;
        if (l.ran_out) {
            return _t("The roster ran out on %s.", l.to_label);
        }
        return l.runs_out ? _t("The roster runs out on %s.", l.to_label) : _t("Roster published up to %s.", l.to_label);
    }

    // progress
    get doneWeeks() { return (this.state.run?.weeks || []).filter((w) => w.status === "done").length; }
    get progressStyle() {
        const n = this.state.run?.weeks.length || 1;
        return `width:${(this.doneWeeks / n) * 100}%`;
    }
    get progressLine() {
        const run = this.state.run;
        if (this.state.phase === "starting") {
            return _t("Making the roster and marking holiday and rest-day shifts…");
        }
        if (this.state.phase === "finishing") {
            return _t("Finishing…");
        }
        return _t("%(done)s of %(total)s weeks published", { done: this.doneWeeks, total: run.weeks.length });
    }
    weekIcon(w) {
        return { done: "check", fail: "triangleAlert", busy: "loader", wait: "circle" }[w.status] || "circle";
    }
    weekCount(w) {
        if (w.status === "done" && w.count !== null && w.count !== undefined) {
            return w.count === 1 ? _t("1 shift") : _t("%s shifts", w.count.toLocaleString());
        }
        if (w.status === "busy") {
            return _t("Publishing…");
        }
        if (w.status === "fail") {
            return _t("Stopped here");
        }
        return w.status === "done" ? _t("Published") : "";
    }
    weekNo(i) { return _t("Week %s", i + 1); }

    // finish
    get finishLine() { return this.state.finish?.summary || ""; }
    get reachLine() {
        const f = this.state.finish;
        if (!f || !f.people) {
            return "";
        }
        const parts = [];
        if (f.portal) {
            parts.push(f.portal === 1 ? _t("1 person sees their shifts in My Payobook straight away.")
                : _t("%s people see their shifts in My Payobook straight away.", f.portal.toLocaleString()));
        }
        if (f.mail_enabled && f.emailed) {
            parts.push(f.emailed === 1 ? _t("1 shift email was sent.") : _t("%s shift emails were sent.", f.emailed.toLocaleString()));
        } else if (!f.mail_enabled) {
            parts.push(_t("No emails were sent: email is switched off here."));
        }
        if (f.no_channel) {
            parts.push(f.no_channel === 1 ? _t("1 person has no login and no work email, so tell them in person.")
                : _t("%s people have no login and no work email, so tell them in person.", f.no_channel.toLocaleString()));
        }
        return parts.join(" ");
    }

    // ------------------------------------------------------------ weeks chooser
    setWeeks(n) {
        const max = this.chk?.max_weeks || 12;
        n = Math.max(1, Math.min(max, n));
        if (n === this.state.weeks || this.busy) {
            return;
        }
        this.state.weeks = n;
        this.state.asking = false;
    }
    fewer() { this.setWeeks(this.state.weeks - 1); }
    more() { this.setWeeks(this.state.weeks + 1); }

    // ------------------------------------------------------------ navigation
    fix(s) {
        if (s.key === "people" && !s.ok && !s.blocking) {
            return this.props.studio.goFiltered("people", "noweek");
        }
        return this.props.studio.go(s.fix || s.key);
    }
    openRoster() {
        this.action.doAction("pb_mission.action_pb_workforce", { additionalContext: { pb_shell_lens: "schedule" } });
    }
    async publishMore() {
        this.state.finish = null;
        this.state.run = null;
        this.state.phase = "";
        await this.load();
        this.root.el?.querySelector(".pbws-launch")?.scrollIntoView({ behavior: this.props.studio.motion, block: "center" });
    }

    // ------------------------------------------------------------ publishing
    ask() {
        if (!this.canPublish || this.busy || this.state.checking) {
            return;
        }
        this.state.asking = true;
    }
    notYet() { this.state.asking = false; }
    onAskKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            this.notYet();
        }
    }

    async publish() {
        if (this.busy) {
            return;
        }
        this.state.asking = false;
        this.state.finish = null;
        this.state.phase = "starting";
        this.state.resumeHidden = false;
        this.state.run = { id: null, weeks: this.slices.map((w) => ({ ...w, status: "wait", count: null })), sentence: "" };
        let start;
        try {
            start = await this.orm.call(MODEL, "go_live_start", [this.state.weeks]);
        } catch (e) {
            this.state.phase = "";
            this.state.run = null;
            this.props.studio.toast(errorText(e), { kind: "error" });
            await this.load();
            return;
        }
        this.state.run = {
            id: start.run_id,
            weeks: start.weeks.map((w) => ({ ...w, status: "wait", count: null })),
            sentence: "",
        };
        await this.runWeeks();
    }

    async carryOn() {
        if (this.busy || !this.state.run?.id) {
            return;
        }
        this.state.resumeHidden = false;
        await this.runWeeks();
    }
    hideResume() { this.state.resumeHidden = true; }

    async runWeeks() {
        const run = this.state.run;
        this.state.phase = "running";
        run.sentence = "";
        for (let i = 0; i < run.weeks.length; i++) {
            const w = run.weeks[i];
            if (w.status === "done") {
                continue;
            }
            w.status = "busy";
            let res;
            try {
                res = await this.orm.call(MODEL, "go_live_week", [run.id, i]);
            } catch (e) {
                res = { ok: false, sentence: errorText(e) };
            }
            if (!res.ok) {
                w.status = "fail";
                run.sentence = res.sentence;
                this.state.phase = "stopped";
                this.props.studio.refresh();
                return;
            }
            w.status = "done";
            w.count = res.published;
        }
        this.state.phase = "finishing";
        try {
            const finish = await this.orm.call(MODEL, "go_live_finish", [run.id]);
            this.state.finish = finish;
            this.state.phase = "";
            this.state.run = null;
            await this.props.studio.refresh();
            this.load();
        } catch (e) {
            run.sentence = errorText(e);
            this.state.phase = "stopped";
        }
    }
}
