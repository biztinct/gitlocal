/** @odoo-module **/
/**
 * People › Privacy — who has answered the company's privacy notice.
 *
 * FOUR PLACES A PERSON CAN BE, and each person is at exactly one, so the
 * numbers add up to the head count: agreed on My Payobook, agreed on paper,
 * said no, not answered yet. Grey at zero; colour only where HR may act
 * ("not answered yet" and "said no").
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in.
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`).
 * R3 — every sentence a person reads is a `_t()` literal or comes from the
 *      server already translated; template sentences sit on one line.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";

export const PRIVACY_GATE = ["hr.group_hr_user"];

export class PbPrivacyLens extends Component {
    static template = "pb_me_privacy.PbPrivacyLens";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, allowed: true, why: "",
            companies: [], companyId: 0, company: "",
            notice: null, draftId: 0,
            counts: { agreed: 0, paper: 0, declined: 0, not_yet: 0 },
            total: 0, shown: 0, rows: [], more: false,
            status: "", search: "", confirmFor: 0, busy: false,
        });
        this._seq = 0;
        onWillStart(() => this.load());
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    async load() {
        const seq = ++this._seq;
        try {
            const d = await this.orm.call("pb.privacy.board", "get_board", [], {
                company_id: this.state.companyId, status: this.state.status,
                search: this.state.search,
            });
            if (seq !== this._seq) { return; }
            if (d.allowed === false) {
                Object.assign(this.state, { allowed: false, why: d.why || "" });
                return;
            }
            Object.assign(this.state, {
                allowed: true,
                companies: d.companies || [],
                companyId: d.company_id || 0,
                company: d.company || "",
                notice: d.notice,
                draftId: d.draft_id || 0,
                counts: d.counts || {},
                total: d.total || 0,
                shown: d.shown || 0,
                rows: d.rows || [],
                more: !!d.more,
            });
        } catch (e) {
            console.warn("pb_me_privacy: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The answers could not be read just now. Try again in a moment.");
        } finally {
            this.state.loaded = true;
        }
    }

    get glance() {
        const c = this.state.counts || {};
        const pick = (key) => () => this.pick(key);
        return [
            { key: "agreed", n: c.agreed || 0, label: _t("agreed on My Payobook"), tone: "", run: pick("agreed") },
            { key: "paper", n: c.paper || 0, label: _t("agreed on paper"), tone: "", run: pick("paper") },
            { key: "declined", n: c.declined || 0, label: _t("said no"), tone: c.declined ? "rose" : "", run: pick("declined") },
            { key: "not_yet", n: c.not_yet || 0, label: _t("not answered yet"), tone: c.not_yet ? "amber" : "", run: pick("not_yet") },
        ];
    }
    get glanceOn() { return this.state.status; }

    statusLabel(status) {
        return {
            agreed: _t("Agreed"),
            paper: _t("Agreed on paper"),
            declined: _t("Said no"),
            not_yet: _t("Not answered yet"),
        }[status] || "";
    }

    pick(key) {
        this.state.status = this.state.status === key ? "" : key;
        this.load();
    }
    onSearch(ev) {
        this.state.search = ev.target.value || "";
        clearTimeout(this._t);
        this._t = setTimeout(() => this.load(), 250);
    }
    onCompany(ev) {
        this.state.companyId = parseInt(ev.target.value, 10) || 0;
        this.state.status = "";
        this.load();
    }

    async openNotice(fresh = false) {
        const act = await this.orm.call("pb.privacy.board", "open_notice", [], {
            company_id: this.state.companyId, new: fresh,
        });
        if (act) { this.action.doAction(act, { onClose: () => this.load() }); }
    }

    askPaper(row) { this.state.confirmFor = row.employee_id; }
    cancelPaper() { this.state.confirmFor = 0; }
    async recordPaper(row) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call("pb.privacy.board", "record_paper", [row.employee_id], { answer: "agree" });
            this.notif.add(_t("Paper consent recorded for %s.", row.name), { type: "success" });
            this.state.confirmFor = 0;
            await this.load();
        } catch (e) {
            const msg = (e && e.data && e.data.message) || _t("That did not go through. Please try again.");
            this.notif.add(msg, { type: "warning" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category(PEOPLE_LENSES).add("privacy", {
    key: "privacy",
    icon: "shieldCheck",
    label: _t("Privacy"),
    title: _t("Privacy · who has answered the notice"),
    Component: PbPrivacyLens,
    groups: PRIVACY_GATE,
}, { sequence: 90 });
