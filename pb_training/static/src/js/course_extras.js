/** @odoo-module **/
/**
 * The course drawer's LEARNING L5 sections — one component dropped into the
 * Courses board's drawer (`training_board.xml`), so the board itself stays as
 * it was:
 *
 *   * VERSION — "Version 2 · since 22 Oct 2026 · What changed: …", the
 *     history, and (training managers) "Publish a new version": one line on
 *     what changed and how many days people get; everybody who finished the
 *     last version has their lesson progress reset, a short re-read on their
 *     page and one email. Nothing is deleted, a passed test stands.
 *   * WHAT PEOPLE SAID — the average rating, how many, % who would
 *     recommend it, the last comments, and the managers' 30-day answers
 *     ("has their work changed", "did they use it").
 *   * SKILLS IT GIVES — the skill and level a person gets on finishing it.
 *   * "People may ask to take it" — whether the course is offered on Ask to
 *     take a course.
 *
 * Reads `pb.training.course_extras`; writes through `pb.training.act`.
 */
import { Component, useState, onWillStart, onWillUpdateProps, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbCourseExtras extends Component {
    static template = "pb_training.PbCourseExtras";
    static props = { channelId: { type: Number }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({
            data: null, log: null, publish: false, note: "", days: 14,
            grant: false, types: [], g: { type_id: 0, skill_id: 0, level_id: 0 },
            busy: false,
        });
        onWillStart(() => this.load(this.props.channelId));
        onWillUpdateProps((next) => {
            if (next.channelId !== this.props.channelId) { return this.load(next.channelId); }
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load(id) {
        try {
            const data = await this.orm.call("pb.training", "course_extras", [id || this.props.channelId]);
            this.state.data = data;
            // Built ONCE per read: a fresh markup() on every render re-inserts
            // the DOM and flickers (ledger: OWL markup flicker).
            this.state.log = data.version_log ? markup(data.version_log) : null;
            this.state.days = data.reread_days || 14;
        } catch (e) {
            console.warn("pb_training: the course extras could not be read", e);
            this.state.data = null;
        }
    }

    get d() { return this.state.data || {}; }
    get ratings() { return this.d.ratings || {}; }

    async act(verb, payload) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.training", "act", [verb, payload]);
            if (res && res.message) { this.notif.add(res.message, { type: "success" }); }
            await this.load();
            return res || {};
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            return null;
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------- version
    get finishersWords() {
        const n = this.d.finishers || 0;
        if (!n) { return _t("Nobody has finished this version yet, so nobody would be asked to read it again."); }
        return n === 1 ? _t("1 person finished this version. They get a re-read due in the days you set, and one email.")
            : _t("%s people finished this version. Each gets a re-read due in the days you set, and one email.", n);
    }

    get workWords() {
        const r = this.ratings;
        return (r.used_pct === null || r.used_pct === undefined)
            ? _t("Managers, a month on: their work changed %s out of 5.", r.effect_avg)
            : _t("Managers, a month on: their work changed %(n)s out of 5 · %(used)s used what they learned.", { n: r.effect_avg, used: `${r.used_pct}%` });
    }

    get scoreWords() {
        const r = this.ratings;
        return (r.recommend_pct === null || r.recommend_pct === undefined) ? this.d.rating_words
            : _t("%(words)s · %(pct)s would recommend it", { words: this.d.rating_words, pct: `${r.recommend_pct}%` });
    }

    get followupsWords() {
        const n = this.d.followups_waiting || 0;
        return n === 1 ? _t("1 manager has not answered the follow-up yet.") : _t("%s managers have not answered the follow-up yet.", n);
    }

    get requestsWords() {
        const n = this.d.requests_waiting || 0;
        return n === 1 ? _t("1 request is waiting for a decision — see Claims › Requests.") : _t("%s requests are waiting for a decision — see Claims › Requests.", n);
    }

    get pendingWords() {
        const n = this.d.pending || 0;
        return n === 1 ? _t("1 person is still to be put on the re-read — the morning job carries on.") : _t("%s people are still to be put on the re-read — the morning job carries on.", n);
    }

    openPublish() { this.state.publish = true; this.state.note = ""; }
    closePublish() { this.state.publish = false; }
    onNote(ev) { this.state.note = ev.target.value; }
    onDays(ev) { this.state.days = Number(ev.target.value) || 14; }

    async confirmPublish() {
        if (!this.state.note.trim()) { return; }
        const res = await this.act("publish_version", { channel_id: this.props.channelId, note: this.state.note, reread_days: this.state.days });
        if (res) { this.closePublish(); }
    }

    // ------------------------------------------------------------- skills
    async openGrant() {
        if (!this.state.types.length) {
            try { this.state.types = (await this.orm.call("pb.training", "skill_lists", [])).types || []; } catch (e) { this.state.types = []; }
        }
        const first = this.state.types[0];
        this.state.g = { type_id: first ? first.id : 0, skill_id: 0, level_id: 0 };
        this.state.grant = true;
    }

    closeGrant() { this.state.grant = false; }
    get gType() { return this.state.types.find((t) => t.id === this.state.g.type_id) || { skills: [], levels: [] }; }

    onG(key, ev) {
        this.state.g[key] = Number(ev.target.value) || 0;
        if (key === "type_id") { this.state.g.skill_id = 0; this.state.g.level_id = 0; }
    }

    async saveGrant() {
        const g = this.state.g;
        if (!g.skill_id || !g.level_id) { return; }
        const res = await this.act("save_grant", { channel_id: this.props.channelId, skill_id: g.skill_id, skill_level_id: g.level_id });
        if (res) { this.closeGrant(); }
    }

    dropGrant(id) { return this.act("drop_grant", { grant_id: id }); }

    toggleRequestable() { return this.act("set_requestable", { channel_id: this.props.channelId, on: !this.d.requestable }); }
}
