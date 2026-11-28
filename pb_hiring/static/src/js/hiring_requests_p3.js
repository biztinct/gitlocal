/** @odoo-module **/
/**
 * RECRUIT P3 — requests without friction, on the Hiring board.
 *
 * A PATCH on the board rather than a second component: the role page, the
 * home cards and every dialog already live in `PbHiringBoard`, and this
 * phase adds presses to them — "Open a role", "Ask a manager", "Remind now",
 * "Send in", "Agree", the budget, Confidential and the shared advert. Every
 * press names an intention to the server (`pb.hiring.act`); nothing here
 * decides who may do what (the server does, and says so in a sentence).
 *
 * The HERO of the phase is the manager's page (`request_page.js`); the hero
 * on THIS screen is the role card that says "Waiting on Budi · reminded 2
 * days ago · Remind now" and the Request section's trail from asked to
 * agreed.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbHiringBoard } from "./hiring_board";

const ASK_DEBOUNCE = 250;

patch(PbHiringBoard.prototype, {
    // ------------------------------------------------------- open a role
    startOpenRole() {
        const j = this.state.journey || {};
        this.state.openingRole = {
            title: "", department_id: "", country_id: "", headcount: 1,
            recruiter_id: j.me && (j.recruiters || []).some((u) => u.id === j.me) ? j.me : "",
            busy: false,
        };
    },

    async saveOpenRole() {
        const f = this.state.openingRole;
        if (!f || f.busy) { return; }
        if (!f.title.trim() || !f.department_id) {
            this.notif.add(_t("A role needs a name and a department."), { type: "warning" });
            return;
        }
        f.busy = true;
        const res = await this.act("new_role", {
            title: f.title, department_id: Number(f.department_id),
            country_id: Number(f.country_id) || false,
            headcount: Number(f.headcount) || 1,
            recruiter_id: Number(f.recruiter_id) || false,
        }, { reload: false });
        f.busy = false;
        if (res && res.id) {
            this.state.openingRole = null;
            await this.load();
            await this.openRole(res.id, { tab: "board" });
        }
    },

    // ---------------------------------------------------- ask a manager
    startAsk(row = null) {
        const d = row || null;
        this.state.asking = {
            requisition_id: d ? d.id : false,
            role_title: d ? d.title : "",
            title: "", department_id: d ? d.department_id : "", country_id: "", headcount: 1,
            employee_id: "", employee_name: "", q: "", message: "",
            remind_every_days: 2, busy: false, link: "",
        };
        this.state.askPeople = [];
        this.searchAskPeople();
    },

    onAskQuery(ev) {
        this.state.asking.q = ev.target.value;
        clearTimeout(this._askTimer);
        this._askTimer = setTimeout(() => this.searchAskPeople(), ASK_DEBOUNCE);
    },

    async searchAskPeople() {
        const f = this.state.asking;
        if (!f) { return; }
        try {
            this.state.askPeople = await this.orm.call("pb.hiring", "ask_people",
                [f.q || "", Number(f.department_id) || false, 30]);
        } catch (e) {
            this.state.askPeople = [];
        }
    },

    pickAskPerson(p) {
        const f = this.state.asking;
        f.employee_id = p.id;
        f.employee_name = p.name;
        f.no_email = !p.has_email;
    },

    get askReady() {
        const f = this.state.asking;
        if (!f || !f.employee_id) { return false; }
        return f.requisition_id ? true : !!(f.title.trim() && f.department_id);
    },

    async saveAsk() {
        const f = this.state.asking;
        if (!f || f.busy || !this.askReady) { return; }
        f.busy = true;
        const payload = {
            employee_id: f.employee_id, message: f.message,
            remind_every_days: Number(f.remind_every_days) || 2,
        };
        if (f.requisition_id) {
            payload.requisition_id = f.requisition_id;
        } else {
            Object.assign(payload, {
                title: f.title, department_id: Number(f.department_id),
                country_id: Number(f.country_id) || false, headcount: Number(f.headcount) || 1,
            });
        }
        const res = await this.act("ask_manager", payload, { reload: false });
        f.busy = false;
        if (!res) { return; }
        if (res.link) {
            f.link = res.link;
            return;
        }
        this.state.asking = null;
        await this.refresh();
        if (!payload.requisition_id && res.id) { await this.openRole(res.id, { tab: "details", section: "request" }); }
    },

    async copyText(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.notif.add(_t("Copied."), { type: "success" });
        } catch {
            this.notif.add(text, { type: "info", sticky: true, title: _t("The link") });
        }
    },

    async remindNow(row) {
        const id = row ? row.id : this.state.drawer && this.state.drawer.id;
        if (!id) { return; }
        await this.act("remind_now", { requisition_id: id });
    },

    async copyRequestLink() {
        const res = await this.act("copy_request_link", { requisition_id: this.state.drawer.id }, { reload: false, silent: true });
        if (res && res.link) { await this.copyText(res.link); }
    },

    // -------------------------------------------------- the request itself
    get req() { return (this.state.drawer && this.state.drawer.request) || {}; },

    async sendInMyself() {
        await this.act("send_in", { requisition_id: this.state.drawer.id });
    },

    async agreeRequest() {
        await this.act("request_agree", { requisition_id: this.state.drawer.id });
    },

    startDecline() { this.state.declining = { note: "" }; },

    async saveDecline() {
        const f = this.state.declining;
        const res = await this.act("request_decline", { requisition_id: this.state.drawer.id, note: f.note });
        if (res) { this.state.declining = null; }
    },

    startBudgetEdit() {
        const fig = this.req.figures || {};
        this.state.budgetEdit = { confirmed: fig.confirmed ? String(Math.round(fig.confirmed)) : "" };
    },

    async saveBudgetEdit() {
        const f = this.state.budgetEdit;
        const res = await this.act("set_budget", { requisition_id: this.state.drawer.id, budget_confirmed: f.confirmed || 0 });
        if (res) { this.state.budgetEdit = null; }
    },

    async setBudgetAgreement(key) {
        await this.act("set_budget", { requisition_id: this.state.drawer.id, budget_agreement: key }, { silent: true });
    },

    async toggleConfidential() {
        const on = !this.req.is_confidential;
        await this.act("set_confidential", { requisition_id: this.state.drawer.id, on });
    },

    async openForCandidates() {
        await this.act("open_role", { requisition_id: this.state.drawer.id });
    },

    openWhoDoesWhat() {
        this.action.doAction("pb_hiring.action_pb_hiring_setup");
    },

    /** The role page's own Next sentence (a role never waits for its request). */
    get roleNext() {
        const d = this.state.drawer;
        if (!d || !this.state.canRecruit) { return null; }
        const r = this.req;
        if (d.state === "setup" && r.state === "none") {
            return { text: _t("Publish it, add candidates, or ask a manager for the hiring request. The request only matters when you send an offer."),
                     ask: true, publish: !d.is_confidential };
        }
        if (d.state === "setup" && ["asked", "writing"].includes(r.state) && r.asked) {
            return { text: _t("%(who)s has the request · %(when)s. Meanwhile, publish it or add candidates.", { who: r.asked.name, when: r.reminded_ago || "" }),
                     remind: true, publish: !d.is_confidential };
        }
        if (d.state === "setup") {
            return { text: _t("Open it for candidates whenever you are ready."), publish: !d.is_confidential, open: !!d.is_confidential };
        }
        return null;
    },

    // --------------------------------------------------------- the advert
    get advert() { return (this.state.drawer && this.state.drawer.advert) || { versions: [], templates: [] }; },

    async jdFromTemplate() {
        const tid = Number(this.state.jdTemplatePick) || this.advert.suggested_id;
        if (!tid) { return; }
        const res = await this.act("jd_from_template", { requisition_id: this.state.drawer.id, template_id: tid });
        if (res && res.jd_id) { this.state.jdTemplatePick = ""; }
    },

    async shareJd(jd) {
        const res = await this.act("share_jd", { jd_id: jd.id });
        if (res && res.link) { await this.copyText(res.link); }
    },

    async copyJdLink(jd) {
        const res = await this.act("copy_jd_link", { jd_id: jd.id }, { reload: false, silent: true });
        if (res && res.link) { await this.copyText(res.link); }
    },

    async makeFinal(jd) {
        await this.act("make_final", { jd_id: jd.id });
    },

    async republish() {
        await this.act("republish", { requisition_id: this.state.drawer.id });
    },

    /** Esc closes a P3 sheet (a statement in a handler must be a method, RC32). */
    onSheetKey(ev, which) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            this.state[which] = null;
        }
    },

    trailWhen(stored) {
        return stored ? this.dayShort(stored) : "";
    },
});
