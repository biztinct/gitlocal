/** @odoo-module **/
/**
 * Learning › OVERVIEW (LEARNING L0) — the training team's first screen.
 *
 * HERO MOMENT: one plain sentence, 22px, built on the server ("38 people are
 * on 6 courses. 4 are past their date. 11 finished this month."), with the
 * three things somebody has to act on as chips right under it — grey at
 * zero, amber when somebody is waiting (quiet board). A chip is a door: it
 * opens the lens that holds that queue, on the right inner tab.
 *
 * One read (`pb.training.overview`), whose numbers are the boards' own
 * numbers (see the facade). Every state is drawn: reading, could not read
 * (with Try again), not for you (with the way to My learning), nothing yet
 * (calm grey), and the working page.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";
import { LEARNING_HUB_XMLID } from "@pb_learning_hub/js/learning_hub";

/** The context key a Learning lens reads its inner tab from (`propsFromContext`). */
export const TRAINING_TAB_KEY = "pb_training_tab";

/** The context key the Certificates lens reads its first filter from (LEARNING L1). */
export const CERT_FILTER_KEY = "pb_training_cert_filter";

const QUEUE_ICON = { claims: "receipt", requests: "clock", late: "alert", certs: "award", required: "listChecks", paths: "route", sessions: "calendar", course_requests: "send", followups: "messageSquare" };
/** The context key Courses reads its Sessions filter from (LEARNING L4). */
const SESSION_STATE_KEY = "pb_training_session_state";

/** The context key the Paths lens reads its arrival filter from (LEARNING L3). */
const PATH_STATE_KEY = "pb_training_path_state";

/** The context keys the Required lens reads its arrival from (LEARNING L2). */
const REQ_TAB_KEY = "pb_training_req_tab";
const REQ_STATE_KEY = "pb_training_req_state";

export class PbLearningOverview extends Component {
    static template = "pb_training.PbLearningOverview";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loaded: false, failed: false, data: {} });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return ic(n, s); }

    async load() {
        this.state.failed = false;
        try {
            this.state.data = await this.orm.call("pb.training", "overview", []);
        } catch (e) {
            console.warn("pb_training: the learning overview could not be read", e);
            this.state.failed = true;
        } finally {
            this.state.loaded = true;
        }
    }

    async retry() {
        this.state.loaded = false;
        await this.load();
    }

    get data() { return this.state.data || {}; }
    get allowed() { return this.data.allowed !== false; }
    get queue() { return this.data.queue || []; }
    get month() { return this.data.month || { due: 0, past: 0, finished: 0 }; }
    get departments() { return this.data.departments || []; }
    get certificates() { return this.data.certificates || {}; }

    /** The certificate line under the departments: four counts, as words. */
    get certBits() {
        const c = this.certificates;
        return [
            { key: "expiring_30", n: c.expiring_30 || 0, warn: true,
              text: (c.expiring_30 || 0) === 1 ? _t("1 expires within 30 days") : _t("%s expire within 30 days", c.expiring_30 || 0) },
            { key: "expired", n: c.expired || 0, bad: true,
              text: (c.expired || 0) === 1 ? _t("1 has expired") : _t("%s have expired", c.expired || 0) },
            { key: "valid", n: c.valid || 0, good: true,
              text: (c.valid || 0) === 1 ? _t("1 in date") : _t("%s in date", c.valid || 0) },
            { key: "no_expiry", n: c.no_expiry || 0,
              text: (c.no_expiry || 0) === 1 ? _t("1 never expires") : _t("%s never expire", c.no_expiry || 0) },
        ];
    }

    /** A CLICK handler: the Certificates register on one filter. */
    openCerts(filter) {
        openHub(this.action, {
            xmlid: LEARNING_HUB_XMLID,
            lens: "certificates",
            context: filter ? { [CERT_FILTER_KEY]: filter } : {},
        });
    }

    queueIcon(row) { return QUEUE_ICON[row.key] || "info"; }

    /** The month line, as words — never a number without its noun. */
    get monthBits() {
        const m = this.month;
        return [
            { key: "due", n: m.due,
              text: m.due === 1 ? _t("1 due this month") : _t("%s due this month", m.due) },
            { key: "past", n: m.past, warn: true,
              text: m.past === 1 ? _t("1 past their date") : _t("%s past their date", m.past) },
            { key: "finished", n: m.finished, good: true,
              text: m.finished === 1 ? _t("1 finished") : _t("%s finished", m.finished) },
        ];
    }

    peopleWords(n) { return n === 1 ? _t("1 person") : _t("%s people", n); }

    lateWords(n) {
        return n === 1 ? _t("1 past their date") : _t("%s past their date", n);
    }

    /** A CLICK handler: the lens that holds this queue, on its own tab. */
    openQueue(row) {
        if (row.filter) { return this.openCerts(row.filter); }
        if (row.lens === "required") { return this.openRequired(row.state || ""); }
        if (row.lens === "paths") { return this.openPaths(row.count ? row.path_state : ""); }
        if (row.key === "sessions") { return this.openSessions(row.count ? "to_close" : ""); }
        openHub(this.action, {
            xmlid: LEARNING_HUB_XMLID,
            lens: row.lens,
            context: row.tab ? { [TRAINING_TAB_KEY]: row.tab } : {},
        });
    }

    /** LEARNING L2: the required-training block. */
    get required() { return this.data.required || {}; }

    get requiredWords() {
        const r = this.required;
        if (r.percent === null || r.percent === undefined) {
            return _t("Nothing is due yet.");
        }
        return _t("%s%% in date", r.percent);
    }

    get requiredBits() {
        const r = this.required;
        return [
            { key: "missing", n: r.missing || 0, bad: true,
              text: (r.missing || 0) === 1 ? _t("1 missing") : _t("%s missing", r.missing || 0) },
            { key: "expiring", n: r.expiring || 0, warn: true,
              text: (r.expiring || 0) === 1 ? _t("1 expiring") : _t("%s expiring", r.expiring || 0) },
        ];
    }

    openRequired(state) {
        const context = { [REQ_TAB_KEY]: "matrix" };
        if (state) { context[REQ_STATE_KEY] = state; }
        openHub(this.action, { xmlid: LEARNING_HUB_XMLID, lens: "required", context });
    }

    /** LEARNING L3: the learning-paths block. */
    get paths() { return this.data.paths || {}; }

    get pathBits() {
        const p = this.paths;
        return [
            { key: "paths", n: p.paths || 0,
              text: (p.paths || 0) === 1 ? _t("1 path") : _t("%s paths", p.paths || 0) },
            { key: "people", n: p.people || 0,
              text: (p.people || 0) === 1 ? _t("1 person on a path") : _t("%s people on a path", p.people || 0) },
            { key: "done", n: p.done_quarter || 0, good: true,
              text: (p.done_quarter || 0) === 1 ? _t("1 finished this quarter") : _t("%s finished this quarter", p.done_quarter || 0) },
            { key: "late", n: p.late || 0, bad: true,
              text: (p.late || 0) === 1 ? _t("1 late on a path") : _t("%s late on a path", p.late || 0) },
        ];
    }

    openPaths(state) {
        openHub(this.action, {
            xmlid: LEARNING_HUB_XMLID,
            lens: "paths",
            context: state ? { [PATH_STATE_KEY]: state } : {},
        });
    }

    /** LEARNING L4: the sessions block. */
    get sessions() { return this.data.sessions || {}; }

    get sessionBits() {
        const x = this.sessions;
        return [
            { key: "week", n: x.this_week || 0,
              text: (x.this_week || 0) === 1 ? _t("1 session this week") : _t("%s sessions this week", x.this_week || 0) },
            { key: "seats", n: x.seats_booked || 0,
              text: (x.seats_booked || 0) === 1 ? _t("1 seat booked") : _t("%s seats booked", x.seats_booked || 0) },
            { key: "waiting", n: x.waiting || 0, warn: true,
              text: (x.waiting || 0) === 1 ? _t("1 waiting for a seat") : _t("%s waiting for a seat", x.waiting || 0) },
            { key: "to_close", n: x.to_close || 0, warn: true,
              text: (x.to_close || 0) === 1 ? _t("1 session to close") : _t("%s sessions to close", x.to_close || 0) },
        ];
    }

    openSessions(state) {
        const context = { [TRAINING_TAB_KEY]: "sessions" };
        if (state) { context[SESSION_STATE_KEY] = state; }
        openHub(this.action, { xmlid: LEARNING_HUB_XMLID, lens: "courses", context });
    }

    openLens(lens) {
        openHub(this.action, { xmlid: LEARNING_HUB_XMLID, lens });
    }
}
