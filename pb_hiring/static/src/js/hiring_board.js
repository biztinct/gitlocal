/** @odoo-module **/
/**
 * `pb_hiring_board` — the Hiring lens on the Lifecycle hub.
 *
 * Journeys answers "what is running", New joiners "who is arriving", Exits
 * "who is leaving". This one comes BEFORE all of them in the story and so it
 * sits first on the rail: WHO ARE WE TRYING TO HIRE, AND WHAT IS STUCK.
 *
 * THE ORDER IS THE HERO. The board is not sorted by date; it is sorted by
 * what needs a person. Anything waiting on the reader's own signature comes
 * first, then anything over budget, then an open role with nobody recruiting
 * it, then the rest by age. A hiring board sorted newest-first hides the
 * request that has been stuck for a fortnight, which is the only one that
 * matters.
 *
 * THE DRAWER IS THE OTHER HALF. One request, everything about it: the money,
 * the advert versions, the adverts prepared per job board, the referrals, and
 * the candidates with the four screening answers inline. Every door it opens
 * is a server-built action, because a second opinion written in JavaScript
 * about what a person may do would only ever disagree with the one that
 * counts.
 *
 * WHAT THIS FILE DELIBERATELY DOES NOT DO: decide who may change anything.
 * `pb.hiring._require_recruit()` / `_require_write()` and the record rules are
 * the boundary; `state.canRecruit` and `state.canWrite` only decide whether a
 * control is OFFERED, because an offer the server would refuse is worse than
 * no offer. The two tiers are different work and not one permission: adverts,
 * job boards and screening are the RECRUITER's; agreeing, closing and filling
 * a role are the hiring MANAGER's.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

/** The four screening answers, in the order a screener weighs them. */
const SCREEN_ORDER = ["shortlisted", "future_fit", "other_role", "rejected"];

const SCREEN_ICON = {
    shortlisted: "checkCircle",
    future_fit: "bookOpen",
    other_role: "arrowLeftRight",
    rejected: "xCircle",
};

const BUDGET_ICON = { within: "checkCircle", over: "alert", unknown: "info" };

export class PbHiringBoard extends Component {
    static template = "pb_hiring.PbHiringBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.screenOrder = SCREEN_ORDER;

        this.state = useState({
            loaded: false,
            allowed: true,
            canWrite: false,
            canRecruit: false,
            canAdmin: false,
            canRaise: false,
            kpis: {},
            rows: [],
            departments: [],
            countries: [],
            recruiters: [],
            states: [],
            roleTypes: [],
            budgetStates: [],
            screenTags: [],
            ruleCount: 0,
            total: 0,
            capped: false,

            // filters
            q: "",
            dept: "all",
            country: "all",
            stage: "all",
            recruiter: "all",
            focus: "",

            // the open request
            drawer: null,
            drawerBusy: false,

            // one dialog at a time, each one plain state
            raising: null,
            writingJd: null,
            moving: null,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    screenIcon(tag) { return SCREEN_ICON[tag] || "circle"; }

    /** The word for a screening answer, from the SERVER's own list — never a
     *  second copy in JavaScript that would drift out of step. */
    screenLabel(tag) {
        const row = (this.state.screenTags || []).find((t) => t.key === tag);
        return row ? row.label : tag;
    }

    budgetIcon(status) { return BUDGET_ICON[status] || "info"; }

    // ------------------------------------------------------------------ read
    async load() {
        try {
            const d = await this.orm.call("pb.hiring", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed,
                canWrite: d.can_write,
                canRecruit: d.can_recruit,
                canAdmin: d.can_admin,
                canRaise: d.can_raise,
                kpis: d.kpis || {},
                rows: d.rows || [],
                departments: d.departments || [],
                countries: d.countries || [],
                recruiters: d.recruiters || [],
                states: d.states || [],
                roleTypes: d.role_types || [],
                budgetStates: d.budget_states || [],
                screenTags: d.screen_tags || [],
                ruleCount: d.rule_count || 0,
                total: d.total || 0,
                capped: !!d.capped,
                loaded: true,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.allowed = false;
            console.warn("pb_hiring: the board could not be read", e);
        }
    }

    async refresh() {
        this.state.loaded = false;
        await this.load();
        if (this.state.drawer) {
            await this.openDrawer(this.state.drawer.id);
        }
    }

    // --------------------------------------------------------------- filters
    get filtered() {
        const q = (this.state.q || "").trim().toLowerCase();
        return this.state.rows.filter((r) => {
            if (this.state.dept !== "all"
                && String(r.department_id) !== String(this.state.dept)) {
                return false;
            }
            if (this.state.country !== "all"
                && String(r.country_id) !== String(this.state.country)) {
                return false;
            }
            if (this.state.stage !== "all" && r.state !== this.state.stage) {
                return false;
            }
            if (this.state.recruiter !== "all"
                && String(r.recruiter_id) !== String(this.state.recruiter)) {
                return false;
            }
            if (this.state.focus === "waiting" && !r.waiting) { return false; }
            if (this.state.focus === "mine" && !r.waiting_mine) { return false; }
            if (this.state.focus === "over" && r.budget_status !== "over") {
                return false;
            }
            if (this.state.focus === "open" && r.state !== "open") {
                return false;
            }
            if (q) {
                const hay = [r.title, r.name, r.department, r.location,
                             r.recruiter, r.requested_by]
                    .join(" ").toLowerCase();
                if (!hay.includes(q)) { return false; }
            }
            return true;
        });
    }

    get anyFilter() {
        return !!(this.state.q || this.state.focus
                  || this.state.dept !== "all" || this.state.country !== "all"
                  || this.state.stage !== "all"
                  || this.state.recruiter !== "all");
    }

    clearFilters() {
        Object.assign(this.state, {
            q: "", focus: "", dept: "all", country: "all", stage: "all",
            recruiter: "all",
        });
    }

    toggleFocus(key) {
        this.state.focus = this.state.focus === key ? "" : key;
    }

    // ---------------------------------------------------------------- drawer
    async openDrawer(id) {
        this.state.drawerBusy = true;
        try {
            this.state.drawer = await this.orm.call(
                "pb.hiring", "get_requisition", [id]);
        } catch (e) {
            this.fail(e);
        } finally {
            this.state.drawerBusy = false;
        }
    }

    closeDrawer() {
        this.state.drawer = null;
        this.state.writingJd = null;
        this.state.moving = null;
    }

    // ------------------------------------------------------------------ acts
    async act(verb, payload, { reload = true, silent = false } = {}) {
        try {
            const res = await this.orm.call("pb.hiring", "act",
                                            [verb, payload || {}]);
            if (res && res.type === "ir.actions.act_window") {
                await this.action.doAction(res);
                return res;
            }
            if (res && res.note && !silent) {
                this.notif.add(res.note, { type: "success" });
            }
            if (reload) { await this.refresh(); }
            return res;
        } catch (e) {
            this.fail(e);
            return null;
        }
    }

    fail(e) {
        const message = (e && e.data && e.data.message)
            || (e && e.message) || _t("That did not work.");
        this.notif.add(message, { type: "danger" });
    }

    // ------------------------------------------------------- raise a request
    startRaise() {
        this.state.raising = {
            title: "", role_type: "new_role", department_id: "",
            headcount: 1, budget_cost: 0, location: "",
            country_id: "", target_start_date: "", requirements: "",
        };
    }

    cancelRaise() { this.state.raising = null; }

    async saveRaise() {
        const form = this.state.raising;
        if (!form.title || !form.department_id) {
            this.notif.add(
                _t("A hiring request needs a role name and the part of the business it is for."),
                { type: "warning" });
            return;
        }
        const res = await this.act("create", { ...form });
        if (res) {
            this.state.raising = null;
            if (res.id) { await this.openDrawer(res.id); }
        }
    }

    // ---------------------------------------------------------- the advert
    startJd() {
        const d = this.state.drawer;
        this.state.writingJd = { title: d ? d.title : "", summary: "", body: "" };
    }

    cancelJd() { this.state.writingJd = null; }

    async saveJd() {
        const d = this.state.drawer;
        const form = this.state.writingJd;
        if (!d) { return; }
        const res = await this.act("new_jd", {
            requisition_id: d.id, title: form.title,
            summary: form.summary, body: form.body,
        });
        if (res) { this.state.writingJd = null; }
    }

    // -------------------------------------------------------- the screening
    async screen(applicant, tag) {
        if (tag === "other_role") {
            this.state.moving = { applicant_id: applicant.id,
                                  name: applicant.name, job_id: "" };
            return;
        }
        await this.act("screen", { applicant_id: applicant.id, tag });
    }

    cancelMove() { this.state.moving = null; }

    async saveMove() {
        const move = this.state.moving;
        if (!move || !move.job_id) {
            this.notif.add(_t("Pick the role they are better suited to."),
                           { type: "warning" });
            return;
        }
        const res = await this.act("screen", {
            applicant_id: move.applicant_id, tag: "other_role",
            job_id: Number(move.job_id),
        });
        if (res) { this.state.moving = null; }
    }

    // ------------------------------------------------------------ the words
    /**
     * "1 role" and "3 roles", never "1 role(s)" (R46). Both words are passed
     * whole so the sentence can be translated as a sentence.
     */
    counted(n, one, many) { return n === 1 ? one : many; }

    daysWords(n) {
        if (!n) { return _t("opened today"); }
        if (n === 1) { return _t("open for a day"); }
        return _t("open for %s days", n);
    }

    money(amount, currency) {
        const n = Number(amount || 0);
        return `${n.toLocaleString()} ${currency || ""}`.trim();
    }
}

registry.category("actions").add("pb_hiring_board", PbHiringBoard);
