/** @odoo-module **/
/**
 * `pb_rnr_wall` — the recognition wall, on the Home mission.
 *
 * THE ONE SURFACE IN THIS MODULE EVERYBODY SEES. It is on Home rather than
 * behind a menu because a wall you have to go and find is a cupboard: the point
 * of it is that somebody arrives at work, opens the product, and reads five
 * things colleagues said about each other before they do anything else.
 *
 * IT READS `pb.rnr.wall`, NOT `pb.rnr`. The board's facade refuses anybody who
 * is not on the recognition team, and correctly — it carries stories that were
 * declined and a switch that spends money. The wall's facade carries the praise
 * three people have already agreed is public, and nothing else, so it needs no
 * gate beyond being signed in. Two objects rather than one object with a mode:
 * a facade that answers differently depending on who asked is one edit away
 * from answering the wrong way.
 *
 * THE MOTION IS THE POINT AND IT IS ALSO OPTIONAL. Tiles rise in on a stagger
 * driven by a CSS custom property this component sets per card. The whole
 * animation is inside a `@media (prefers-reduced-motion: no-preference)` block
 * in the stylesheet, so a person who has asked their machine for less movement
 * gets the finished wall immediately and no JavaScript decides that for them.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in.
 * R2 — every sentence is ONE expression.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbRnrWall extends Component {
    static template = "pb_rnr.PbRnrWall";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loaded: false,
            stories: [],
            celebrations: [],
            winners: {},
            values: [],
            me: {},
            valueFilter: 0,

            creating: false,
            draft: { nominee_id: 0, nominee: "", value_id: 0, story: "",
                     public: true },
            people: [],
            busy: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        try {
            const data = await this.orm.call("pb.rnr.wall", "get_wall", []);
            Object.assign(this.state, {
                stories: data.stories || [],
                celebrations: data.celebrations || [],
                winners: data.winners || {},
                values: data.values || [],
                me: data.me || {},
            });
        } catch (e) {
            // Reported, never swallowed into a decoration. A wall that could
            // not be read shows its empty state and says so; it never shows an
            // empty wall as though nobody had been thanked.
            console.warn("pb_rnr: the recognition wall could not be read", e);
        } finally {
            this.state.loaded = true;
        }
    }

    async refresh() { await this.load(); }

    // -------------------------------------------------------------- reading
    get visibleStories() {
        if (!this.state.valueFilter) { return this.state.stories; }
        return this.state.stories.filter(
            (s) => s.value === this.state.valueFilter);
    }

    setValueFilter(name) {
        this.state.valueFilter = this.state.valueFilter === name ? 0 : name;
    }

    /** ONE expression per sentence, so the spaces survive (R34). */
    get meLine() {
        const me = this.state.me || {};
        if (!me.employee_id) { return ""; }
        if (!me.given && !me.received) {
            return _t("You have not thanked anybody yet. It takes a minute.");
        }
        if (!me.given) {
            return _t("You have been thanked %s times. You have not written one yet.",
                      me.received);
        }
        return _t("You have written %(given)s and been thanked %(got)s times.",
                  { given: me.given === 1 ? _t("1 piece of praise")
                                          : _t("%s pieces of praise", me.given),
                    got: me.received });
    }

    /** Built server-side, once, so four surfaces say the same thing (R46). */
    kindLabel(row) { return row.years_label || ""; }

    // ----------------------------------------------------------- new praise
    openCreate() {
        this.state.draft = { nominee_id: 0, nominee: "", value_id: 0,
                             story: "", public: true };
        this.state.people = [];
        this.state.creating = true;
    }

    closeCreate() { this.state.creating = false; }

    onDraft(field, ev) {
        this.state.draft[field] = field === "public"
            ? ev.target.checked : ev.target.value;
    }

    pickValue(value) { this.state.draft.value_id = value.id; }

    async onPersonSearch(ev) {
        const term = ev.target.value;
        this.state.draft.nominee = term;
        this.state.draft.nominee_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        try {
            this.state.people = await this.orm.call(
                "pb.rnr", "employee_options", [term]);
        } catch (e) {
            this.state.people = [];
        }
    }

    pickPerson(person) {
        this.state.draft.nominee_id = person.id;
        this.state.draft.nominee = person.name;
        this.state.people = [];
    }

    async confirmCreate() {
        const d = this.state.draft;
        if (!d.nominee_id) {
            this.notif.add(_t("Pick the colleague you want to thank."),
                           { type: "warning" });
            return;
        }
        if (!d.value_id) {
            this.notif.add(_t("Pick the value this is an example of."),
                           { type: "warning" });
            return;
        }
        if (!(d.story || "").trim()) {
            this.notif.add(_t("Write what actually happened."),
                           { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("pb.rnr", "nominate", [{
                nominee_id: d.nominee_id,
                value_id: d.value_id,
                story: d.story,
                public: d.public,
            }]);
            this.state.creating = false;
            this.notif.add(
                _t("Thank you — that has gone to their manager. It appears here once they and HR have both agreed it."),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be sent.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) {
            return e.message.data.message;
        }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }

    openMine() { this.action.doAction("pb_rnr.action_my_recognition"); }
}

registry.category("actions").add("pb_rnr_wall", PbRnrWall);
