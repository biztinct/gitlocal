/** @odoo-module **/
/**
 * `pb_hr_comm_calendar` — the Announcements lens on the People hub.
 *
 * A MONTH IS THE HERO, BECAUSE A MONTH IS THE QUESTION. Nobody plans
 * communications in a list: the reason a town hall notice must not go out on
 * the same Monday as the pay-day reminder is that both land in the same inbox
 * an hour apart, and only a grid shows that. The side rail then answers the
 * second question — what is coming in the next fortnight, and whose week it is.
 *
 * NOTHING HERE RECOMPUTES A NUMBER. The server works out every figure, the
 * grid itself and the order the rows come in; a second opinion written in
 * JavaScript would only ever disagree with the one that counts.
 *
 * EVERY COLLECTION IN THE INITIAL STATE IS A COLLECTION (R195). A panel is
 * rendered ONCE over the initial state before the `await` that fetches its
 * data has resolved, so a `{}` where the template reads `.length` throws
 * "Cannot read properties of undefined" — which the theme shows as a generic
 * "something went wrong" dialog with nothing useful in the console.
 *
 * AN OWL TEMPLATE CANNOT SEE A JAVASCRIPT GLOBAL (R205). `filter(Boolean)` is
 * ordinary JavaScript and dies inside a compiled OWL expression with
 * "undefined is not a function", two levels down an OwlError's `cause`.
 * Anything a template needs that is not a property or a method of this
 * component is built here.
 *
 * Every icon comes from the shared `ic()` registry in pb_import_kit — the set
 * is CLOSED and an unknown name renders a plain circle with no error, so a
 * name used here is a name that is in that file.
 */
import { Component, markup, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The chip colour for each status. Problem first, and never by spelling. */
const STATE_TONE = {
    draft: "wait",
    submitted: "wait",
    scheduled: "go",
    sending: "go",
    sent: "ok",
    cancelled: "off",
};

const STATE_ICON = {
    draft: "pencil",
    submitted: "clock",
    scheduled: "calendar",
    sending: "send",
    sent: "checkCircle",
    cancelled: "xCircle",
};

/** The days across the top, short enough for a narrow column. */
const WEEKDAYS = [
    _t("Mon"), _t("Tue"), _t("Wed"), _t("Thu"), _t("Fri"), _t("Sat"),
    _t("Sun"),
];

export class PbHrCommCalendar extends Component {
    static template = "pb_hr_comm.PbHrCommCalendar";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.state = useState({
            loaded: false,
            allowed: true,
            busy: false,
            why: "",
            isHr: false,
            mayWrite: false,
            scope: "",
            headline: "",
            today: "",
            month: "",
            monthLabel: "",
            weeks: [],
            rows: [],
            coming: [],
            celebrations: [],
            stats: [],
            companies: [],
            states: [],
            cardsOn: false,
            cardsSwitch: "",
            sendingOn: true,
            timeNote: "",
            filters: { state: "", q: "", responsible_id: 0, company_ids: [] },
            // The drawer. Every nested object carries the keys the template
            // reads, because the drawer is rendered before its payload lands.
            open: false,
            post: { ok: false, departments: [], jobs: [], history: [],
                    no_email_names: [] },
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    /**
     * HTML that was built on the server, rendered as HTML.
     *
     * `t-out` ESCAPES A PLAIN STRING AND ONLY RENDERS `markup()` RAW (R51).
     * An Html field crossing JSON-RPC arrives as a plain string, so a drawer
     * that hands it straight to `t-out` puts the announcement's own source
     * code on the screen. Both values wrapped here are sanitised where they
     * were written — the body by the `Html` field, the history lines by the
     * chatter — and nothing else in this component is ever wrapped.
     */
    html(value) { return markup(value || ""); }

    /**
     * WHAT THE PILL CANNOT SHOW, THE HOVER DOES. A day column is about a
     * hundred pixels wide, so a subject is clamped to two lines and the
     * whole sentence lives in the title — the drawer is one click away and
     * the calendar's job is to show WHEN, not to read the announcement out.
     */
    pillTitle(row) {
        return [row.time, row.subject, row.audience, row.state_word]
            .filter((v) => !!v).join(" · ");
    }

    tone(key) { return STATE_TONE[key] || "wait"; }
    stateIcon(key) { return STATE_ICON[key] || "circle"; }

    get weekdays() { return WEEKDAYS; }

    get anyFilter() {
        const f = this.state.filters;
        return !!(f.state || f.q || f.responsible_id);
    }

    /** The drawer's one-line subtitle, built HERE and not in the template. */
    get drawerSub() {
        const p = this.state.post;
        return [p.company, p.audience, p.recurrence_word]
            .filter((v) => !!v).join(" · ");
    }

    // =================================================================
    //  reading
    // =================================================================
    async load() {
        this.state.busy = true;
        try {
            const f = this.state.filters;
            const payload = { month: this.state.month };
            if (f.state) { payload.state = f.state; }
            if (f.q) { payload.q = f.q; }
            if (f.responsible_id) { payload.responsible_id = f.responsible_id; }
            if (f.company_ids.length) { payload.company_ids = f.company_ids; }
            const d = await this.orm.call("pb.hr.comm", "get_calendar",
                                          [payload]);
            if (d.allowed === false) {
                Object.assign(this.state, {
                    loaded: true, allowed: false, why: d.why || "" });
                return;
            }
            Object.assign(this.state, {
                loaded: true,
                allowed: true,
                isHr: !!d.is_hr,
                mayWrite: !!d.may_write,
                scope: d.scope || "",
                headline: d.headline || "",
                today: d.today || "",
                month: d.month || "",
                monthLabel: d.month_label || "",
                weeks: d.weeks || [],
                rows: d.rows || [],
                coming: d.coming || [],
                celebrations: d.celebrations || [],
                stats: d.stats || [],
                companies: d.companies || [],
                states: d.states || [],
                cardsOn: !!d.cards_on,
                cardsSwitch: d.cards_switch || "",
                sendingOn: d.sending_on !== false,
                timeNote: d.time_note || "",
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            this.state.why = _t("The calendar could not be read just now.");
            console.warn("pb_hr_comm: the calendar could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    // =================================================================
    //  moving around
    // =================================================================
    shiftMonth(step) {
        const parts = (this.state.month || "").split("-");
        let year = parseInt(parts[0], 10);
        let month = parseInt(parts[1], 10) + step;
        while (month > 12) { month -= 12; year += 1; }
        while (month < 1) { month += 12; year -= 1; }
        this.state.month = `${year}-${String(month).padStart(2, "0")}`;
        this.load();
    }

    thisMonth() {
        this.state.month = (this.state.today || "").slice(0, 7);
        this.load();
    }

    toggleCompany(id) {
        const chosen = this.state.filters.company_ids;
        const at = chosen.indexOf(id);
        if (at >= 0) { chosen.splice(at, 1); } else { chosen.push(id); }
        this.load();
    }

    setState(key) {
        this.state.filters.state = this.state.filters.state === key ? "" : key;
        this.load();
    }

    onSearch(ev) {
        this.state.filters.q = ev.target.value || "";
        this.load();
    }

    clearFilters() {
        this.state.filters.state = "";
        this.state.filters.q = "";
        this.state.filters.responsible_id = 0;
        this.load();
    }

    // =================================================================
    //  the drawer
    // =================================================================
    async openDrawer(id) {
        this.state.open = true;
        this.state.post = { ok: false, departments: [], jobs: [],
                            history: [], no_email_names: [] };
        try {
            const d = await this.orm.call("pb.hr.comm", "get_post", [id]);
            this.state.post = Object.assign(
                { departments: [], jobs: [], history: [],
                  no_email_names: [] }, d);
            if (d.ok === false) {
                this.notif.add(d.why || _t("That could not be opened."),
                               { type: "warning" });
            }
        } catch (e) {
            this.state.open = false;
            this.notif.add(_t("That announcement could not be read."),
                           { type: "warning" });
            console.warn("pb_hr_comm: the drawer could not be read", e);
        }
    }

    closeDrawer() {
        this.state.open = false;
    }

    // =================================================================
    //  the doors
    // =================================================================
    async openPost(id) {
        try {
            const action = await this.orm.call("pb.hr.comm", "open_post", [id]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(_t("That could not be opened."),
                           { type: "warning" });
            console.warn("pb_hr_comm: a post could not be opened", e);
        }
    }

    async newPost(day) {
        if (!this.state.mayWrite) { return; }
        try {
            const action = await this.orm.call("pb.hr.comm", "new_post",
                                               [day || false]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(
                _t("A new announcement could not be started just now."),
                { type: "warning" });
            console.warn("pb_hr_comm: new post failed", e);
        }
    }

    async openTemplates() {
        try {
            const action = await this.orm.call("pb.hr.comm", "open_templates",
                                               []);
            if (action) { await this.action.doAction(action); }
        } catch (e) {
            this.notif.add(_t("The template library could not be opened."),
                           { type: "warning" });
            console.warn("pb_hr_comm: templates failed", e);
        }
    }

    async checkAudience(id) {
        try {
            await this.orm.call("pb.hr.comm.post", "action_check_audience",
                                [[id]]);
            this.notif.add(_t("Counted. The number is on the announcement."),
                           { type: "success" });
            await this.openDrawer(id);
            await this.load();
        } catch (e) {
            this.notif.add(_t("Who gets it could not be counted."),
                           { type: "warning" });
            console.warn("pb_hr_comm: the audience could not be counted", e);
        }
    }
}

registry.category("actions").add("pb_hr_comm_calendar", PbHrCommCalendar);
