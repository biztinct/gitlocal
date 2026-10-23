/** @odoo-module **/
/**
 * My learning's LEARNING L5 blocks, one component dropped into the lens:
 *
 *   * TELL US HOW IT WENT — the course feedback (and, for a manager, the
 *     30-day follow-ups) waiting for an answer, each one press away.
 *   * ASK TO TAKE A COURSE — a drawer: one of our courses, an outside one
 *     from the list (cost, hours, provider), or something else (name, link,
 *     cost); when, and why. The manager decides; the HR lead too when it
 *     costs money. The allowance left is said before anything is sent.
 *   * MY REQUESTS — where each one is, the reason when one was turned down,
 *     "Claim this course back" on an agreed outside course, Cancel while it
 *     waits.
 *   * MY SKILLS — what is on the reader's record, and the skills their job
 *     needs that they do not have yet.
 *
 * Reads `pb.my.training.my_requests` / `request_options` / `my_skills` /
 * `my_feedback`; writes `ask_course` / `cancel_request`. "Me" is the session
 * user — nothing here takes a person.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.my.training";

export class PbMyRequestsBlock extends Component {
    static template = "pb_training.PbMyRequestsBlock";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            mine: { rows: [] },
            skills: null,
            feedback: [],
            drawer: false,
            options: null,
            form: { kind: "ours", channel_id: 0, outside_course_id: 0, course_name: "", provider: "", url: "", amount: 0, when_words: "", why: "" },
            busy: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const [mine, skills, feedback] = await Promise.all([
                this.orm.call(MODEL, "my_requests", []).catch(() => ({ rows: [] })),
                this.orm.call(MODEL, "my_skills", []).catch(() => null),
                this.orm.call(MODEL, "my_feedback", []).catch(() => []),
            ]);
            this.state.mine = mine || { rows: [] };
            this.state.skills = skills;
            this.state.feedback = feedback || [];
        } finally {
            this.state.loaded = true;
        }
    }

    get rows() { return (this.state.mine && this.state.mine.rows) || []; }
    get hasEmployee() { return !!(this.state.mine && this.state.mine.has_employee); }
    get skills() { return this.state.skills || { skills: [], required: [] }; }
    get gaps() { return (this.skills.required || []).filter((r) => r.state !== "ok"); }

    stateClass(row) {
        if (row.state === "submitted" || row.state === "draft") { return "is-warn"; }
        if (row.state === "refused" || row.state === "cancelled") { return "is-bad"; }
        return "is-ok";
    }

    feedbackWords(fb) {
        return fb.kind === "training" ? _t("Rate %s", fb.course)
            : _t("Has %(who)s's work changed since %(course)s?", { who: fb.about, course: fb.course });
    }

    go(url) { window.location.href = url; }

    // ------------------------------------------------------------- asking
    async openAsk() {
        this.state.drawer = true;
        try {
            this.state.options = await this.orm.call(MODEL, "request_options", []);
            const o = this.state.options;
            const kind = (o.ours || []).length ? "ours" : ((o.outside || []).length ? "outside" : "other");
            this.state.form = { kind, channel_id: 0, outside_course_id: 0, course_name: "", provider: "", url: "", amount: 0, when_words: "", why: "" };
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That could not be opened."), { type: "danger" });
            this.state.drawer = false;
        }
    }

    closeAsk() { this.state.drawer = false; }
    setKind(kind) { this.state.form.kind = kind; }

    setField(key, ev, kind = "") {
        let value = ev.target.value;
        if (kind === "num") { value = Number(value) || 0; }
        this.state.form[key] = value;
    }

    pickOutside(id) { this.state.form.outside_course_id = id; }

    get pickedOutside() {
        const o = this.state.options || {};
        return (o.outside || []).find((x) => x.id === this.state.form.outside_course_id) || null;
    }

    get allowanceWords() {
        const a = (this.state.options || {}).allowance || {};
        if (!a.set) { return _t("No training allowance is set for this year, so only free courses and ours can be agreed."); }
        return a.committed_words
            ? _t("Your allowance for %(year)s: %(left)s left, after %(set)s set aside for courses already agreed.", { year: a.year, left: a.left_words, set: a.committed_words })
            : _t("Your allowance for %(year)s: %(left)s left.", { year: a.year, left: a.left_words });
    }

    get askHint() {
        const f = this.state.form;
        if (f.kind === "ours" && !f.channel_id) { return _t("Pick one of our courses."); }
        if (f.kind === "outside" && !f.outside_course_id) { return _t("Pick an outside course."); }
        if (f.kind === "other" && !(f.course_name || "").trim()) { return _t("Say what the course is called."); }
        if (!(f.why || "").trim()) { return _t("Say in a line why — your manager reads it."); }
        return "";
    }

    get whoDecides() {
        const o = this.state.options || {};
        const costs = this.state.form.kind === "other" ? this.state.form.amount > 0
            : this.state.form.kind === "outside" ? !!(this.pickedOutside && this.pickedOutside.cost > 0) : false;
        if (!o.manager) {
            return costs ? _t("Your manager decides first, then the HR lead, because it costs money.") : _t("Your manager decides.");
        }
        return costs ? _t("%s decides first, then the HR lead, because it costs money.", o.manager)
            : _t("%s decides.", o.manager);
    }

    async send() {
        if (this.askHint) { return; }
        this.state.busy = true;
        try {
            const f = this.state.form;
            const res = await this.orm.call(MODEL, "ask_course", [{
                kind: f.kind, channel_id: Number(f.channel_id) || 0, outside_course_id: f.outside_course_id,
                course_name: f.course_name, provider: f.provider, url: f.url, amount: f.amount,
                when_words: f.when_words, why: f.why,
            }]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            this.state.drawer = false;
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That request could not be sent."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async cancel(row) {
        try {
            const res = await this.orm.call(MODEL, "cancel_request", [row.id]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        }
    }
}
